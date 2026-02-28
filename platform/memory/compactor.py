"""Memory Compactor — periodic compression, deduplication, pruning and health checks.

Runs nightly at 03:00 UTC (after evolution scheduler at 02:00).
Also callable on-demand via POST /api/memory/compact.

Compaction rules:
  1. Prune stale pattern memory (> MAX_PATTERN_AGE_DAYS, default 7d)
  2. Prune low-confidence stale project entries (conf < 0.4, > 60d)
  3. Compress oversized values (> MAX_VALUE_LEN) to first MAX_VALUE_LEN chars
  4. Re-score global entries: boost confidence when key appears in 2+ projects
  5. Deduplicate global entries with same key (merge, keep highest-confidence value)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_PATTERN_AGE_DAYS = 7
MAX_VALUE_LEN = 800       # chars kept per entry value
STALE_PROJECT_DAYS = 60   # days before low-confidence entries expire
LOW_CONF_THRESHOLD = 0.4


@dataclass
class CompactionStats:
    pattern_pruned: int = 0
    project_pruned: int = 0
    project_compressed: int = 0
    global_deduped: int = 0
    global_rescored: int = 0
    errors: list[str] = field(default_factory=list)
    ran_at: str = ""

    def summary(self) -> str:
        return (
            f"pattern_pruned={self.pattern_pruned} "
            f"project_pruned={self.project_pruned} "
            f"project_compressed={self.project_compressed} "
            f"global_deduped={self.global_deduped} "
            f"global_rescored={self.global_rescored}"
        )


def run_compaction() -> CompactionStats:
    """Run all compaction rules synchronously. Safe to call from any context."""
    from ..db.migrations import get_db

    stats = CompactionStats(ran_at=datetime.now(timezone.utc).isoformat())
    conn = get_db()
    try:
        # ── 1. Prune old pattern memory ──────────────────────────────────
        try:
            result = conn.execute(
                f"DELETE FROM memory_pattern WHERE "
                f"julianday('now') - julianday(created_at) > {MAX_PATTERN_AGE_DAYS}"
            )
            stats.pattern_pruned = result.rowcount
            conn.commit()
        except Exception as e:
            stats.errors.append(f"pattern_prune: {e}")

        # ── 2. Prune stale low-confidence project entries ─────────────────
        try:
            result = conn.execute(
                f"DELETE FROM memory_project WHERE "
                f"confidence < {LOW_CONF_THRESHOLD} AND "
                f"julianday('now') - julianday(updated_at) > {STALE_PROJECT_DAYS}"
            )
            stats.project_pruned = result.rowcount
            conn.commit()
        except Exception as e:
            stats.errors.append(f"project_prune: {e}")

        # ── 3. Compress oversized project values ──────────────────────────
        try:
            oversized = conn.execute(
                f"SELECT id, value FROM memory_project WHERE length(value) > {MAX_VALUE_LEN}"
            ).fetchall()
            for row in oversized:
                truncated = row["value"][:MAX_VALUE_LEN]
                conn.execute(
                    "UPDATE memory_project SET value=? WHERE id=?",
                    (truncated, row["id"]),
                )
            if oversized:
                conn.commit()
            stats.project_compressed = len(oversized)
        except Exception as e:
            stats.errors.append(f"project_compress: {e}")

        # ── 4. Deduplicate global entries (same key, different categories merged) ──
        try:
            dupes = conn.execute(
                """
                SELECT key, COUNT(*) as cnt
                FROM memory_global
                GROUP BY key
                HAVING cnt > 1
                """
            ).fetchall()
            for dupe in dupes:
                key = dupe["key"]
                entries = conn.execute(
                    "SELECT * FROM memory_global WHERE key=? ORDER BY confidence DESC, updated_at DESC",
                    (key,),
                ).fetchall()
                if len(entries) < 2:
                    continue
                # Keep the best entry, merge project lists, delete the rest
                best = entries[0]
                all_projects: list[str] = []
                for e in entries:
                    all_projects.extend(json.loads(e["projects_json"] or "[]"))
                merged_projects = list(dict.fromkeys(all_projects))  # dedupe preserving order
                conn.execute(
                    "UPDATE memory_global SET projects_json=? WHERE id=?",
                    (json.dumps(merged_projects), best["id"]),
                )
                ids_to_delete = [e["id"] for e in entries[1:]]
                conn.execute(
                    f"DELETE FROM memory_global WHERE id IN ({','.join('?' for _ in ids_to_delete)})",
                    ids_to_delete,
                )
                stats.global_deduped += len(ids_to_delete)
            if dupes:
                conn.commit()
        except Exception as e:
            stats.errors.append(f"global_dedup: {e}")

        # ── 5. Re-score global entries: boost confidence by project count ──
        try:
            entries = conn.execute(
                "SELECT id, confidence, occurrences, projects_json FROM memory_global"
            ).fetchall()
            boosted = 0
            for e in entries:
                projects = json.loads(e["projects_json"] or "[]")
                n_projects = len(projects)
                if n_projects >= 2:
                    # Each additional project adds 0.05 confidence, capped at 1.0
                    boosted_conf = min(1.0, e["confidence"] + 0.05 * (n_projects - 1))
                    if boosted_conf > e["confidence"]:
                        conn.execute(
                            "UPDATE memory_global SET confidence=? WHERE id=?",
                            (boosted_conf, e["id"]),
                        )
                        boosted += 1
            if boosted:
                conn.commit()
            stats.global_rescored = boosted
        except Exception as e:
            stats.errors.append(f"global_rescore: {e}")

    finally:
        conn.close()

    logger.info("Memory compaction done: %s", stats.summary())
    return stats


def get_memory_health() -> dict:
    """Return a health snapshot of all memory layers."""
    from ..db.migrations import get_db

    conn = get_db()
    try:
        def q(sql, *params):
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else {}

        project_total = (q("SELECT count(*) as n FROM memory_project") or {}).get("n", 0)
        project_low_conf = (q(
            f"SELECT count(*) as n FROM memory_project WHERE confidence < {LOW_CONF_THRESHOLD}"
        ) or {}).get("n", 0)
        project_stale = (q(
            f"SELECT count(*) as n FROM memory_project WHERE "
            f"julianday('now') - julianday(updated_at) > {STALE_PROJECT_DAYS}"
        ) or {}).get("n", 0)
        project_oversized = (q(
            f"SELECT count(*) as n FROM memory_project WHERE length(value) > {MAX_VALUE_LEN}"
        ) or {}).get("n", 0)

        # Category breakdown
        project_by_cat = [
            dict(r) for r in conn.execute(
                "SELECT category, count(*) as n, round(avg(confidence),2) as avg_conf "
                "FROM memory_project GROUP BY category ORDER BY n DESC"
            ).fetchall()
        ]

        global_total = (q("SELECT count(*) as n FROM memory_global") or {}).get("n", 0)
        global_dupes = (q(
            "SELECT count(*) as n FROM (SELECT key FROM memory_global GROUP BY key HAVING count(*)>1)"
        ) or {}).get("n", 0)
        global_by_cat = [
            dict(r) for r in conn.execute(
                "SELECT category, count(*) as n, round(avg(confidence),2) as avg_conf, "
                "round(avg(occurrences),1) as avg_occ "
                "FROM memory_global GROUP BY category ORDER BY n DESC"
            ).fetchall()
        ]

        pattern_total = (q("SELECT count(*) as n FROM memory_pattern") or {}).get("n", 0)
        pattern_old = (q(
            f"SELECT count(*) as n FROM memory_pattern WHERE "
            f"julianday('now') - julianday(created_at) > {MAX_PATTERN_AGE_DAYS}"
        ) or {}).get("n", 0)

        # Role-scoped entries
        role_stats = [
            dict(r) for r in conn.execute(
                "SELECT COALESCE(agent_role,'') as role, count(*) as n "
                "FROM memory_project GROUP BY agent_role ORDER BY n DESC"
            ).fetchall()
        ]

    finally:
        conn.close()

    return {
        "project": {
            "total": project_total,
            "low_confidence": project_low_conf,
            "stale": project_stale,
            "oversized": project_oversized,
            "by_category": project_by_cat,
            "by_role": role_stats,
        },
        "global": {
            "total": global_total,
            "duplicates": global_dupes,
            "by_category": global_by_cat,
        },
        "pattern": {
            "total": pattern_total,
            "old": pattern_old,
        },
        "thresholds": {
            "pattern_max_age_days": MAX_PATTERN_AGE_DAYS,
            "project_stale_days": STALE_PROJECT_DAYS,
            "low_conf_threshold": LOW_CONF_THRESHOLD,
            "max_value_len": MAX_VALUE_LEN,
        },
    }


async def memory_compactor_loop() -> None:
    """Background task: run compaction nightly at 03:00 UTC."""
    import asyncio
    from datetime import timedelta

    logger.info("Memory compactor loop started (nightly at 03:00 UTC)")
    while True:
        try:
            now = datetime.now(timezone.utc)
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            wait_secs = (target - now).total_seconds()
            logger.info(
                "Memory compactor: next run at %s (in %.1fh)",
                target.isoformat(),
                wait_secs / 3600,
            )
            await asyncio.sleep(wait_secs)
            stats = run_compaction()
            if stats.errors:
                logger.warning("Memory compaction errors: %s", stats.errors)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Memory compactor loop error: %s", e)
            await asyncio.sleep(3600)  # retry in 1h on unexpected error
