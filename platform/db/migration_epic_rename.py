"""
DB migration: rename missions/mission_runs tables to epics/epic_runs.
Run once. Idempotent (checks if already done).
"""

import logging
from .migrations import get_db

logger = logging.getLogger(__name__)


def run_migration():
    db = get_db()
    try:
        tables = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "epics" not in tables and "missions" in tables:
            logger.info("Migrating: missions -> epics")
            db.execute("ALTER TABLE missions RENAME TO epics")
            db.commit()
            logger.info("epics table ready")
        elif "epics" in tables:
            logger.info("epics table already exists — skipping")

        if "epic_runs" not in tables and "mission_runs" in tables:
            logger.info("Migrating: mission_runs -> epic_runs")
            db.execute("ALTER TABLE mission_runs RENAME TO epic_runs")
            db.commit()
            logger.info("epic_runs table ready")
        elif "epic_runs" in tables:
            logger.info("epic_runs table already exists — skipping")

        # Rename column parent_mission_id -> parent_epic_id in epics if needed
        cols_epics = [r[1] for r in db.execute("PRAGMA table_info(epics)").fetchall()]
        if "parent_mission_id" in cols_epics and "parent_epic_id" not in cols_epics:
            db.execute(
                "ALTER TABLE epics RENAME COLUMN parent_mission_id TO parent_epic_id"
            )
            db.commit()
            logger.info("epics.parent_epic_id renamed")

        # Same for epic_runs
        cols_runs = [
            r[1] for r in db.execute("PRAGMA table_info(epic_runs)").fetchall()
        ]
        if "parent_mission_id" in cols_runs and "parent_epic_id" not in cols_runs:
            db.execute(
                "ALTER TABLE epic_runs RENAME COLUMN parent_mission_id TO parent_epic_id"
            )
            db.commit()
            logger.info("epic_runs.parent_epic_id renamed")

    finally:
        db.close()
