"""Multi-tenant project isolation — separate SQLite databases per project.

Architecture:
  data/platform.db           — global tables (agents, workflows, patterns, users, plugins)
  data/projects/<id>.db      — per-project (missions, runs, sessions, memory, tickets, events)

Backward compatible: without project_id, uses platform.db as before.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_PLATFORM_DB = _DATA_DIR / "platform.db"
_PROJECTS_DIR = _DATA_DIR / "projects"

_PROJECT_TABLES = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY, name TEXT, description TEXT, workflow_id TEXT,
    project_id TEXT, status TEXT DEFAULT 'created', created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS mission_runs (
    id TEXT PRIMARY KEY, mission_id TEXT, status TEXT DEFAULT 'pending',
    current_phase TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY, mission_id TEXT, name TEXT, status TEXT DEFAULT 'planned',
    start_date TEXT, end_date TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, sprint_id TEXT, mission_id TEXT, title TEXT,
    assigned_to TEXT, status TEXT DEFAULT 'pending', created_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, mission_id TEXT, name TEXT, status TEXT DEFAULT 'active',
    lead_agent TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL, actor TEXT DEFAULT 'system',
    payload TEXT DEFAULT '{}', timestamp REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, mission_id TEXT,
    event TEXT, title TEXT, message TEXT, severity TEXT DEFAULT 'info',
    read INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_proj_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_proj_events_agg ON events(aggregate_type, aggregate_id);
"""


def get_platform_db() -> sqlite3.Connection:
    """Get connection to the global platform database."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_PLATFORM_DB))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def get_project_db(project_id: str) -> sqlite3.Connection:
    """Get connection to a project-specific database. Creates if needed."""
    _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in project_id if c.isalnum() or c in "-_")
    db_path = _PROJECTS_DIR / f"{safe_id}.db"

    is_new = not db_path.exists()
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    if is_new:
        db.executescript(_PROJECT_TABLES)
        logger.info("Created project database: %s", db_path)

    return db


def list_project_dbs() -> list[dict]:
    """List all project databases with size info."""
    if not _PROJECTS_DIR.exists():
        return []
    return [
        {"project_id": f.stem, "path": str(f), "size_kb": f.stat().st_size // 1024}
        for f in sorted(_PROJECTS_DIR.glob("*.db"))
    ]


def delete_project_db(project_id: str) -> bool:
    """Delete a project database."""
    safe_id = "".join(c for c in project_id if c.isalnum() or c in "-_")
    db_path = _PROJECTS_DIR / f"{safe_id}.db"
    if db_path.exists():
        db_path.unlink()
        for suffix in (".db-wal", ".db-shm"):
            p = _PROJECTS_DIR / f"{safe_id}{suffix}"
            if p.exists():
                p.unlink()
        return True
    return False
