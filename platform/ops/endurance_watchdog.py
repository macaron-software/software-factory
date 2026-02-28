"""Endurance Watchdog — monitors mission progression + platform health.

Runs every 60s, detects:
- Phase stalls (>15 min no progress) → auto-retry
- Zombie missions (status=running but no asyncio task)
- Disk usage >90% → cleanup temp files
- LLM health (provider reachable)
- Daily report generation

Can run as:
  - In-process asyncio task (server lifespan)
  - Standalone: python3 -m platform.ops.endurance_watchdog
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────
CHECK_INTERVAL = int(os.environ.get("WATCHDOG_INTERVAL", "60"))  # seconds
PHASE_STALL_THRESHOLD = int(os.environ.get("WATCHDOG_STALL_THRESHOLD", "900"))  # 15 min
DISK_ALERT_PCT = int(os.environ.get("WATCHDOG_DISK_ALERT", "90"))
ENABLED = os.environ.get("WATCHDOG_ENABLED", "1") == "1"
HEALTH_URL = os.environ.get("WATCHDOG_HEALTH_URL", "http://localhost:8099/api/health")
DB_PATH = os.environ.get("WATCHDOG_DB_PATH", "")


def _db_path() -> str:
    if DB_PATH:
        return DB_PATH
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "platform.db")


def _get_db():
    """Get a platform DB connection (SQLite or PostgreSQL depending on env)."""
    try:
        from ..db.migrations import get_db

        return get_db()
    except Exception:
        # Fallback to direct SQLite (standalone mode)
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        return conn


def _ensure_table():
    db = _get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS endurance_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL DEFAULT 0,
        detail TEXT DEFAULT ''
    )""")
    db.commit()
    # Reset PG sequence if out of sync (can happen after restore/restart)
    try:
        from ..db.migrations import is_postgresql

        if is_postgresql():
            db.execute(
                "SELECT setval(pg_get_serial_sequence('endurance_metrics', 'id'), "
                "COALESCE((SELECT MAX(id) FROM endurance_metrics), 0) + 1, false)"
            )
            db.commit()
    except Exception:
        pass
    db.close()


def _log_metric(metric: str, value: float, detail: str = ""):
    try:
        db = _get_db()
        ts = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO endurance_metrics (ts, metric, value, detail) VALUES (?,?,?,?)",
            (ts, metric, value, detail),
        )
        db.commit()
        db.close()
    except Exception as e:
        logger.warning("Failed to log metric %s: %s", metric, e)


def get_metrics(metric: Optional[str] = None, limit: int = 100) -> list[dict]:
    db = _get_db()
    if metric:
        rows = db.execute(
            "SELECT * FROM endurance_metrics WHERE metric=? ORDER BY ts DESC LIMIT ?",
            (metric, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM endurance_metrics ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Check Functions ──────────────────────────────────────────────────


async def _check_health() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-sf",
            "-m",
            "5",
            HEALTH_URL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def _check_stalled_missions() -> list[dict]:
    """Find mission runs that are running but haven't progressed recently."""
    stalls = []
    try:
        db = _get_db()
        rows = db.execute("""
            SELECT mr.id, mr.workflow_name as name, mr.status, mr.current_phase, mr.updated_at
            FROM mission_runs mr
            WHERE mr.status = 'running'
        """).fetchall()
        db.close()

        now = time.time()
        for r in rows:
            updated = r["updated_at"] or ""
            if updated:
                try:
                    from datetime import datetime as dt

                    updated_ts = (
                        updated.timestamp()
                        if hasattr(updated, "timestamp")
                        else dt.fromisoformat(
                            updated.replace("Z", "+00:00")
                        ).timestamp()
                    )
                    age = now - updated_ts
                    if age > PHASE_STALL_THRESHOLD:
                        stalls.append(
                            {
                                "id": r["id"],
                                "name": r["name"],
                                "phase": r["current_phase"],
                                "stall_seconds": int(age),
                            }
                        )
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        logger.warning("stall check failed: %s", e)
    return stalls


async def _check_disk_usage() -> float:
    """Return disk usage percentage."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "df",
            "-h",
            "/",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode().strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            for p in parts:
                if p.endswith("%"):
                    return float(p.rstrip("%"))
    except Exception:
        pass
    return 0.0


async def _cleanup_temp_files():
    """Remove old temp files to free disk space."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "find",
            "/tmp",
            "-name",
            "macaron_*",
            "-mtime",
            "+7",
            "-delete",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
    except Exception:
        pass


async def _check_llm_health() -> bool:
    """Check if LLM endpoint is reachable via /api/llm/stats."""
    try:
        url = HEALTH_URL.replace("/api/health", "/api/llm/stats")
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-sf",
            "-m",
            "5",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


# ── Auto-Retry Stalled Missions ─────────────────────────────────────


async def _retry_stalled(stalls: list[dict]):
    """Attempt to resume stalled missions via API."""
    for s in stalls[:3]:  # max 3 retries per check
        logger.warning(
            "WATCHDOG: mission %s stalled %ds in phase %s — triggering retry",
            s["id"],
            s["stall_seconds"],
            s["phase"],
        )
        _log_metric(
            "stall_detected",
            s["stall_seconds"],
            f"mission={s['id']} phase={s['phase']}",
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl",
                "-sf",
                "-X",
                "POST",
                "-m",
                "10",
                f"{HEALTH_URL.replace('/api/health', '')}/api/missions/{s['id']}/retry",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            _log_metric(
                "stall_retry", 1 if proc.returncode == 0 else 0, f"mission={s['id']}"
            )
        except Exception as e:
            logger.warning("retry failed for %s: %s", s["id"], e)


# ── Continuous Auto-Resume ───────────────────────────────────────────

RESUME_BATCH_SIZE = int(os.environ.get("WATCHDOG_RESUME_BATCH", "5"))
RESUME_INTERVAL = int(os.environ.get("WATCHDOG_RESUME_INTERVAL", "300"))  # 5 min
MAX_CONCURRENT_RUNS = int(os.environ.get("WATCHDOG_MAX_CONCURRENT", "10"))


async def _auto_resume_paused() -> int:
    """Resume paused mission runs in controlled batches with backoff. Returns count resumed."""
    MAX_RESUME_ATTEMPTS = 5  # abandon after 5 failed resumes
    BACKOFF_MINUTES = [0, 5, 15, 30, 60]  # wait between retries

    resumed = 0

    # ── Phase 1: all DB reads + pre-resume writes, then close connection ──
    eligible = []
    no_wf_ids = []
    new_attempts_map = {}
    now_iso = ""
    try:
        from datetime import datetime, timedelta
        import json as _json

        db = _get_db()
        try:
            running = db.execute(
                "SELECT COUNT(*) as c FROM mission_runs WHERE status='running'"
            ).fetchone()["c"]

            if running >= MAX_CONCURRENT_RUNS:
                logger.info(
                    "WATCHDOG: %d runs already active (max=%d), skipping resume",
                    running,
                    MAX_CONCURRENT_RUNS,
                )
                return 0

            slots = min(RESUME_BATCH_SIZE, MAX_CONCURRENT_RUNS - running)
            paused = db.execute(
                """
                SELECT mr.session_id, mr.id, s.config_json, mr.workflow_id,
                       COALESCE(mr.resume_attempts, 0) as attempts,
                       mr.last_resume_at, mr.project_id, mr.brief
                FROM mission_runs mr
                JOIN sessions s ON mr.session_id = s.id
                WHERE mr.status = 'paused'
                AND s.status IN ('interrupted', 'paused')
                AND COALESCE(mr.human_input_required, 0) = 0
                AND COALESCE(mr.resume_attempts, 0) < ?
                ORDER BY mr.updated_at ASC
                LIMIT ?
                """,
                (MAX_RESUME_ATTEMPTS, slots * 3),
            ).fetchall()

            if not paused:
                return 0

            now = datetime.utcnow()
            now_iso = now.isoformat()
            for row in paused:
                last_at = row["last_resume_at"]
                if last_at:
                    try:
                        last_dt = datetime.fromisoformat(last_at.replace("Z", ""))
                        wait_min = BACKOFF_MINUTES[
                            min(row["attempts"], len(BACKOFF_MINUTES) - 1)
                        ]
                        if now - last_dt < timedelta(minutes=wait_min):
                            continue
                    except Exception:
                        pass
                eligible.append(dict(row))
                if len(eligible) >= slots:
                    break

            if not eligible:
                return 0

            stalled = [r for r in eligible if r["attempts"] >= 2]
            if stalled:
                logger.warning(
                    "WATCHDOG: %d missions with %d+ failed resumes: %s",
                    len(stalled),
                    2,
                    [r["id"][:8] for r in stalled],
                )
            logger.warning(
                "WATCHDOG: auto-resuming %d/%d paused runs (running=%d, slots=%d)",
                len(eligible),
                len(paused),
                running,
                slots,
            )

            # Write pre-resume status updates while we still hold the connection
            for row in eligible:
                config = _json.loads(row["config_json"]) if row["config_json"] else {}
                wf_id = config.get("workflow_id", row["workflow_id"] or "")
                if not wf_id:
                    no_wf_ids.append(row["id"])
                    db.execute(
                        "UPDATE mission_runs SET human_input_required=1 WHERE id=?",
                        (row["id"],),
                    )
                    continue
                new_attempts = row["attempts"] + 1
                new_attempts_map[row["id"]] = new_attempts
                db.execute(
                    "UPDATE sessions SET status='active' WHERE id=?",
                    (row["session_id"],),
                )
                db.execute(
                    "UPDATE mission_runs SET status='running', resume_attempts=?, last_resume_at=? WHERE id=?",
                    (new_attempts, now_iso, row["id"]),
                )
            db.commit()

            # Auto-abandon exhausted missions
            abandoned = db.execute(
                """UPDATE mission_runs SET status='abandoned', updated_at=datetime('now')
                   WHERE status='paused'
                   AND COALESCE(resume_attempts, 0) >= ?
                   AND COALESCE(human_input_required, 0) = 0""",
                (MAX_RESUME_ATTEMPTS,),
            ).rowcount
            if abandoned:
                db.commit()
                logger.warning(
                    "WATCHDOG: abandoned %d missions that exhausted resume retries",
                    abandoned,
                )
        finally:
            db.close()  # Release before any await
    except Exception as e:
        logger.warning("WATCHDOG: auto-resume error: %s", e)
        return resumed

    # Filter to only rows that have a workflow
    to_resume = [
        r for r in eligible if r["id"] not in no_wf_ids and r["id"] in new_attempts_map
    ]
    if not to_resume:
        return resumed

    # ── Phase 2: async resume, no DB connection held ──
    row = to_resume[0]  # batch handles the rest
    new_attempts = new_attempts_map[row["id"]]
    try:
        from ..services.auto_resume import _resume_batch

        resumed = await _resume_batch(stagger=5.0)
        _log_metric(
            "auto_resume", resumed, f"batch via _resume_batch (attempt {new_attempts})"
        )
        logger.warning(
            "WATCHDOG: auto-resumed %d runs (attempt %d)", resumed, new_attempts
        )
    except Exception as _re:
        _log_metric("auto_resume_fail", 0, str(_re))
        # Revert to paused on failure
        try:
            db2 = _get_db()
            try:
                db2.execute(
                    "UPDATE mission_runs SET status='paused' WHERE id=?", (row["id"],)
                )
                db2.commit()
            finally:
                db2.close()
        except Exception:
            pass

    return resumed


# ── Session Recovery ─────────────────────────────────────────────────

SESSION_STALE_THRESHOLD = int(
    os.environ.get("WATCHDOG_SESSION_STALE", "1800")
)  # 30 min


async def _recover_stale_sessions() -> int:
    """Detect sessions active too long without progress and mark as interrupted."""
    recovered = 0
    try:
        db = _get_db()
        # Find "active" sessions with no recent messages (stale)
        rows = db.execute("""
            SELECT s.id, s.name,
                   (SELECT MAX(timestamp) FROM messages WHERE session_id=s.id) as last_msg
            FROM sessions s
            WHERE s.status = 'active'
        """).fetchall()

        now = time.time()
        for row in rows:
            last_msg = row["last_msg"] or ""
            if not last_msg:
                continue
            try:
                from datetime import datetime as dt

                msg_ts = (
                    last_msg.timestamp()
                    if hasattr(last_msg, "timestamp")
                    else dt.fromisoformat(last_msg.replace("Z", "+00:00")).timestamp()
                )
                age = now - msg_ts
                if age > SESSION_STALE_THRESHOLD:
                    # Mark as interrupted — will be picked up by auto-resume
                    db.execute(
                        "UPDATE sessions SET status='interrupted' WHERE id=?",
                        (row["id"],),
                    )
                    db.execute(
                        "UPDATE mission_runs SET status='paused' WHERE session_id=? AND status='running'",
                        (row["id"],),
                    )
                    recovered += 1
                    _log_metric(
                        "session_stale_recovered",
                        age,
                        f"session={row['id'][:8]} name={row['name'][:30]}",
                    )
                    logger.warning(
                        "WATCHDOG: stale session %s (no msg for %ds) → interrupted",
                        row["id"][:8],
                        int(age),
                    )
            except (ValueError, TypeError):
                pass

        if recovered:
            db.commit()
        db.close()
    except Exception as e:
        logger.warning("WATCHDOG: session recovery error: %s", e)

    return recovered


# ── Failed Run Cleanup ───────────────────────────────────────────────


async def _cleanup_failed_sessions() -> int:
    """Mark sessions for failed runs as 'failed' (avoid zombie active sessions)."""
    cleaned = 0
    try:
        db = _get_db()
        cleaned = db.execute("""
            UPDATE sessions SET status='failed'
            WHERE id IN (
                SELECT session_id FROM mission_runs
                WHERE status='failed'
            ) AND status IN ('active', 'interrupted')
        """).rowcount
        if cleaned:
            db.commit()
            _log_metric("session_cleanup", cleaned)
            logger.info("WATCHDOG: cleaned %d zombie sessions for failed runs", cleaned)
        db.close()
    except Exception as e:
        logger.warning("WATCHDOG: session cleanup error: %s", e)
    return cleaned


async def _cleanup_phantom_runs() -> int:
    """Mark mission runs that have been running/paused > 48h without activity as 'abandoned'."""
    abandoned = 0
    try:
        db = _get_db()
        result = db.execute("""
            UPDATE mission_runs SET status='abandoned'
            WHERE status IN ('running', 'paused')
            AND (
                updated_at IS NULL
                OR datetime(updated_at) < datetime('now', '-48 hours')
            )
        """)
        abandoned = result.rowcount
        if abandoned:
            db.commit()
            _log_metric("phantom_runs_abandoned", abandoned)
            logger.info(
                "WATCHDOG: abandoned %d phantom mission runs (stale > 48h)", abandoned
            )
        db.close()
    except Exception as e:
        logger.warning("WATCHDOG: phantom run cleanup error: %s", e)
    return abandoned


async def _daily_report():
    """Generate daily endurance report and store in metrics."""
    try:
        db = _get_db()
        # Count phases completed today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        phases = db.execute(
            "SELECT COUNT(*) as c FROM endurance_metrics WHERE metric='phase_complete' AND ts LIKE ?",
            (f"{today}%",),
        ).fetchone()

        # Count chaos events today
        chaos = (
            db.execute(
                "SELECT COUNT(*) as c FROM chaos_runs WHERE ran_at LIKE ?",
                (f"{today}%",),
            ).fetchone()
            if _table_exists(db, "chaos_runs")
            else None
        )

        # Count stalls today
        stalls = db.execute(
            "SELECT COUNT(*) as c FROM endurance_metrics WHERE metric='stall_detected' AND ts LIKE ?",
            (f"{today}%",),
        ).fetchone()

        db.close()

        report = (
            f"phases={phases['c'] if phases else 0}, "
            f"chaos={chaos['c'] if chaos else 0}, "
            f"stalls={stalls['c'] if stalls else 0}"
        )
        _log_metric("daily_report", 1, report)
        logger.info("WATCHDOG daily report: %s", report)
    except Exception as e:
        logger.warning("daily report failed: %s", e)


def _table_exists(db, name: str) -> bool:
    try:
        from ..db.migrations import is_postgresql

        if is_postgresql():
            r = db.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name=?",
                (name,),
            ).fetchone()
            return bool(r and r[0] > 0)
    except Exception:
        pass
    r = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(r and r[0] > 0)


# ── Main Loop ────────────────────────────────────────────────────────


async def watchdog_loop():
    """Main watchdog loop — checks every CHECK_INTERVAL seconds."""
    _ensure_table()
    logger.info(
        "Endurance watchdog started (interval=%ds, stall=%ds, disk=%d%%, resume_interval=%ds)",
        CHECK_INTERVAL,
        PHASE_STALL_THRESHOLD,
        DISK_ALERT_PCT,
        RESUME_INTERVAL,
    )

    last_daily = ""
    last_resume = 0.0
    check_count = 0

    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        check_count += 1

        try:
            # Health check
            healthy = await _check_health()
            if not healthy:
                _log_metric("health_down", 1)
                logger.error("WATCHDOG: platform health check FAILED")
                continue

            # Stalled missions
            stalls = await _check_stalled_missions()
            if stalls:
                await _retry_stalled(stalls)

            # Stale session recovery (every 2 min)
            if check_count % 2 == 0:
                recovered = await _recover_stale_sessions()
                if recovered:
                    _log_metric("sessions_recovered", recovered)

            # Failed session cleanup (every 5 min)
            if check_count % 5 == 0:
                await _cleanup_failed_sessions()

            # Phantom run cleanup (every 30 min — stale runs > 48h → abandoned)
            if check_count % 30 == 0:
                await _cleanup_phantom_runs()

            # Auto-resume paused runs (every RESUME_INTERVAL)
            now = time.time()
            if now - last_resume > RESUME_INTERVAL:
                resumed = await _auto_resume_paused()
                if resumed:
                    _log_metric("batch_resumed", resumed)
                last_resume = now

            # Disk usage (every 5 min)
            if check_count % 5 == 0:
                disk = await _check_disk_usage()
                _log_metric("disk_usage_pct", disk)
                if disk > DISK_ALERT_PCT:
                    logger.warning(
                        "WATCHDOG: disk usage %.0f%% > %d%% — cleaning up",
                        disk,
                        DISK_ALERT_PCT,
                    )
                    await _cleanup_temp_files()

            # LLM health (every 5 min)
            if check_count % 5 == 0:
                llm_ok = await _check_llm_health()
                _log_metric("llm_health", 1 if llm_ok else 0)
                if not llm_ok:
                    logger.warning("WATCHDOG: LLM health check failed")

            # Daily report (once per day)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today != last_daily:
                await _daily_report()
                last_daily = today

        except Exception as e:
            logger.error("WATCHDOG check error: %s", e)


# ── CLI ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Endurance Watchdog")
    parser.add_argument(
        "--once", action="store_true", help="Run one check cycle and exit"
    )
    parser.add_argument(
        "--loop", action="store_true", help="Start continuous watchdog loop"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if args.once:

        async def _once():
            _ensure_table()
            healthy = await _check_health()
            print(f"Health: {'OK' if healthy else 'FAIL'}")
            stalls = await _check_stalled_missions()
            print(f"Stalled missions: {len(stalls)}")
            for s in stalls:
                print(f"  - {s['id']} ({s['phase']}) stalled {s['stall_seconds']}s")
            disk = await _check_disk_usage()
            print(f"Disk: {disk:.0f}%")

        asyncio.run(_once())
    elif args.loop:
        asyncio.run(watchdog_loop())
    else:
        parser.print_help()
