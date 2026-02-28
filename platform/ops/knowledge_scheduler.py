"""Knowledge Scheduler — nightly knowledge maintenance at 04:00 UTC.

Triggers the 'knowledge-maintenance' workflow automatically on all active projects.
Runs after memory compactor (03:00) and before business hours.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

KNOWLEDGE_HOUR_UTC = 4  # 04:00 UTC


async def run_knowledge_maintenance(project_id: str | None = None) -> str | None:
    """Launch a knowledge-maintenance mission. Returns mission_id or None on error."""
    try:
        from ..missions.engine import get_engine
        from ..missions.store import MissionStore, MissionRunStore

        engine = get_engine()

        # If no project given, pick the most active project
        if not project_id:
            from ..db.migrations import get_db

            conn = get_db()
            row = conn.execute(
                "SELECT id FROM projects WHERE status='active' ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if not row:
                logger.info("[KnowledgeScheduler] No active projects found, skipping")
                return None
            project_id = row["id"]

        mission_store = MissionStore()
        mission = mission_store.create(
            name="Knowledge Maintenance (scheduled)",
            workflow_id="knowledge-maintenance",
            project_id=project_id,
            goal="Nightly knowledge maintenance: audit memory health, seed fresh facts, curate, refresh docs, consolidate.",
            tags=["knowledge", "scheduled", "nightly"],
        )

        run_store = MissionRunStore()
        run = run_store.create(mission_id=mission.id)

        asyncio.create_task(engine.run(run.id))
        logger.info(
            "[KnowledgeScheduler] Launched knowledge-maintenance mission %s for project %s",
            run.id,
            project_id,
        )
        return run.id

    except Exception as e:
        logger.error(
            "[KnowledgeScheduler] Failed to launch knowledge maintenance: %s", e
        )
        return None


async def knowledge_scheduler_loop() -> None:
    """Background task: run knowledge maintenance nightly at 04:00 UTC."""
    logger.info(
        "Knowledge scheduler loop started (nightly at %02d:00 UTC)", KNOWLEDGE_HOUR_UTC
    )
    while True:
        try:
            now = datetime.now(timezone.utc)
            target = now.replace(
                hour=KNOWLEDGE_HOUR_UTC, minute=0, second=0, microsecond=0
            )
            if target <= now:
                target += timedelta(days=1)
            wait_secs = (target - now).total_seconds()
            logger.info(
                "Knowledge scheduler: next run at %s (in %.1fh)",
                target.isoformat(),
                wait_secs / 3600,
            )
            await asyncio.sleep(wait_secs)

            # Run maintenance on all active projects
            from ..db.migrations import get_db

            conn = get_db()
            active_projects = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM projects WHERE status='active' ORDER BY updated_at DESC LIMIT 10"
                ).fetchall()
            ]
            conn.close()

            if active_projects:
                for pid in active_projects:
                    await run_knowledge_maintenance(project_id=pid)
                    await asyncio.sleep(60)  # stagger launches by 1 minute
            else:
                logger.info(
                    "[KnowledgeScheduler] No active projects, skipping nightly run"
                )

        except asyncio.CancelledError:
            logger.info("Knowledge scheduler loop cancelled")
            return
        except Exception as e:
            logger.error("[KnowledgeScheduler] Unexpected error: %s", e)
            await asyncio.sleep(3600)  # retry in 1h on error
