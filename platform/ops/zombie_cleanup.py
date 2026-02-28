"""Zombie mission cleanup — runs every 10 minutes on startup.

Rules:
- running > 6h without updated_at change → status = 'failed', error = 'zombie: stale for >6h'
- paused > 24h without updated_at change → status = 'abandoned'
- running > 48h → always failed (no matter updated_at)
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600  # 10 minutes


def run_zombie_cleanup() -> dict:
    """Mark stale running/paused missions as failed/abandoned. Returns counts."""
    try:
        from ..db.migrations import get_db
    except ImportError:
        from platform.db.migrations import get_db  # type: ignore

    failed = 0
    abandoned = 0

    try:
        db = get_db()
        try:
            # running > 48h → failed (unconditional)
            cur = db.execute(
                """
                UPDATE mission_runs
                SET status = 'failed',
                    current_phase = 'zombie: running for >48h'
                WHERE status = 'running'
                  AND updated_at < datetime('now', '-48 hours')
                """
            )
            failed += cur.rowcount

            # running > 6h without update → failed
            cur = db.execute(
                """
                UPDATE mission_runs
                SET status = 'failed',
                    current_phase = 'zombie: stale for >6h'
                WHERE status = 'running'
                  AND updated_at < datetime('now', '-6 hours')
                """
            )
            failed += cur.rowcount

            # paused > 24h → abandoned
            cur = db.execute(
                """
                UPDATE mission_runs
                SET status = 'abandoned'
                WHERE status = 'paused'
                  AND updated_at < datetime('now', '-24 hours')
                """
            )
            abandoned += cur.rowcount

            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Zombie cleanup DB error: %s", exc)

    if failed or abandoned:
        logger.info("Zombie cleanup: %d failed, %d abandoned", failed, abandoned)
    else:
        logger.debug("Zombie cleanup: nothing to clean")

    return {"failed": failed, "abandoned": abandoned}


async def start_zombie_watchdog() -> None:
    """Background task: run zombie cleanup every 10 minutes."""
    logger.info("Zombie watchdog started (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            result = await asyncio.to_thread(run_zombie_cleanup)
            if result["failed"] or result["abandoned"]:
                logger.info("Zombie watchdog cleaned: %s", result)
        except Exception as exc:
            logger.exception("Zombie watchdog error: %s", exc)
        await asyncio.sleep(INTERVAL_SECONDS)
