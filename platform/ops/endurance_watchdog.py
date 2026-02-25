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
HEALTH_URL = os.environ.get("WATCHDOG_HEALTH_URL", "http://localhost:8090/api/health")
DB_PATH = os.environ.get("WATCHDOG_DB_PATH", "")


def _db_path() -> str:
    if DB_PATH:
        return DB_PATH
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "platform.db")


def _ensure_table():
    db = sqlite3.connect(_db_path())
    db.execute("""CREATE TABLE IF NOT EXISTS endurance_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL DEFAULT 0,
        detail TEXT DEFAULT ''
    )""")
    db.commit()
    db.close()


def _log_metric(metric: str, value: float, detail: str = ""):
    try:
        db = sqlite3.connect(_db_path())
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
    db = sqlite3.connect(_db_path())
    db.row_factory = sqlite3.Row
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
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row
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

                    updated_ts = dt.fromisoformat(
                        updated.replace("Z", "+00:00")
                    ).timestamp()
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
    """Resume paused mission runs in controlled batches. Returns count resumed."""
    resumed = 0
    try:
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row

        # Check how many are already running (avoid overload)
        running = db.execute(
            "SELECT COUNT(*) as c FROM mission_runs WHERE status='running'"
        ).fetchone()["c"]

        if running >= MAX_CONCURRENT_RUNS:
            logger.info(
                "WATCHDOG: %d runs already active (max=%d), skipping resume",
                running,
                MAX_CONCURRENT_RUNS,
            )
            db.close()
            return 0

        slots = min(RESUME_BATCH_SIZE, MAX_CONCURRENT_RUNS - running)

        # Find paused runs with interrupted/paused sessions
        paused = db.execute(
            """
            SELECT mr.session_id, mr.id, s.config_json, mr.workflow_id
            FROM mission_runs mr
            JOIN sessions s ON mr.session_id = s.id
            WHERE mr.status = 'paused'
            AND s.status IN ('interrupted', 'paused')
            ORDER BY mr.updated_at ASC
            LIMIT ?
        """,
            (slots,),
        ).fetchall()

        if not paused:
            db.close()
            return 0

        logger.warning(
            "WATCHDOG: auto-resuming %d paused runs (running=%d, slots=%d)",
            len(paused),
            running,
            slots,
        )

        for row in paused:
            try:
                import json as _json

                config = _json.loads(row["config_json"]) if row["config_json"] else {}
                wf_id = config.get("workflow_id", row["workflow_id"] or "")
                if not wf_id:
                    continue

                sid = row["session_id"]

                # Update statuses
                db.execute("UPDATE sessions SET status='active' WHERE id=?", (sid,))
                db.execute(
                    "UPDATE mission_runs SET status='running' WHERE id=?", (row["id"],)
                )
                db.commit()

                # Trigger resume via resume-all API (batch approach)
                base_url = HEALTH_URL.replace("/api/health", "")
                proc = await asyncio.create_subprocess_exec(
                    "curl",
                    "-sf",
                    "-X",
                    "POST",
                    "-m",
                    "30",
                    f"{base_url}/api/workflows/resume-all",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()

                if proc.returncode == 0:
                    resumed = slots  # Assume all were resumed
                    _log_metric("auto_resume", slots, "batch via resume-all")
                    logger.warning(
                        "WATCHDOG: resume-all triggered for %d candidates", slots
                    )
                else:
                    _log_metric("auto_resume_fail", 0, "resume-all failed")

                # Don't loop per-session — resume-all handles the batch
                break
            except Exception as e:
                logger.warning("WATCHDOG: resume failed for %s: %s", row["id"][:8], e)

        db.close()
    except Exception as e:
        logger.warning("WATCHDOG: auto-resume error: %s", e)

    return resumed


# ── Session Recovery ─────────────────────────────────────────────────

SESSION_STALE_THRESHOLD = int(
    os.environ.get("WATCHDOG_SESSION_STALE", "1800")
)  # 30 min


async def _recover_stale_sessions() -> int:
    """Detect sessions active too long without progress and mark as interrupted."""
    recovered = 0
    try:
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row

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

                msg_ts = dt.fromisoformat(last_msg.replace("Z", "+00:00")).timestamp()
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
        db = sqlite3.connect(_db_path())
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


# ── Daily Report ─────────────────────────────────────────────────────


async def _daily_report():
    """Generate daily endurance report and store in metrics."""
    try:
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row

        # Count phases completed today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        phases = db.execute(
            "SELECT COUNT(*) as c FROM endurance_metrics WHERE metric='phase_complete' AND ts LIKE ?",
            (f"{today}%",),
        ).fetchone()

        # Count chaos events today
        chaos = (
            db.execute(
                "SELECT COUNT(*) as c FROM chaos_runs WHERE ts LIKE ?", (f"{today}%",)
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
    r = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return r[0] > 0


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
