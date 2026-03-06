"""
DB migration: rename missions/mission_runs tables to epics/epic_runs.
Run once. Idempotent (checks if already done).
"""

import logging
from .migrations import get_db

logger = logging.getLogger(__name__)


def _pg_table_exists(db, name: str) -> bool:
    """Check if table exists in PostgreSQL."""
    r = db.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=?",
        (name,),
    ).fetchone()
    return bool(r)


def _pg_column_exists(db, table: str, column: str) -> bool:
    """Check if column exists in PostgreSQL table."""
    r = db.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=? AND column_name=?",
        (table, column),
    ).fetchone()
    return bool(r)


def run_migration():
    from .adapter import _USE_PG

    db = get_db()
    try:
        if _USE_PG:
            # PostgreSQL: schema_pg.sql already uses epics/epic_runs (new names)
            # Only handle legacy DBs that still have the old names
            if _pg_table_exists(db, "missions") and not _pg_table_exists(db, "epics"):
                logger.info("PG Migrating: missions -> epics")
                db.execute("ALTER TABLE missions RENAME TO epics")
                db.commit()
            if _pg_table_exists(db, "mission_runs") and not _pg_table_exists(
                db, "epic_runs"
            ):
                logger.info("PG Migrating: mission_runs -> epic_runs")
                db.execute("ALTER TABLE mission_runs RENAME TO epic_runs")
                db.commit()
            # Column renames
            if _pg_table_exists(db, "epics") and _pg_column_exists(
                db, "epics", "parent_mission_id"
            ):
                db.execute(
                    "ALTER TABLE epics RENAME COLUMN parent_mission_id TO parent_epic_id"
                )
                db.commit()
            if _pg_table_exists(db, "epic_runs") and _pg_column_exists(
                db, "epic_runs", "parent_mission_id"
            ):
                db.execute(
                    "ALTER TABLE epic_runs RENAME COLUMN parent_mission_id TO parent_epic_id"
                )
                db.commit()
        else:
            tables = {
                r[0]
                for r in db.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
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
            cols_epics = [
                r[1] for r in db.execute("PRAGMA table_info(epics)").fetchall()
            ]
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
