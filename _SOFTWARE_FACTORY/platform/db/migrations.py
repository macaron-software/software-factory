"""
Database migrations and initialization for the platform.
Supports dual backend: SQLite (local) / PostgreSQL (production).
Backend selected via DATABASE_URL env var.
"""

import os
import sqlite3
from pathlib import Path

from ..config import DB_PATH, DATA_DIR
from .adapter import is_postgresql, get_connection

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
SCHEMA_PG_PATH = Path(__file__).parent / "schema_pg.sql"

_USE_PG = is_postgresql()


def _pg_column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a PostgreSQL table."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=? AND column_name=?",
        (table, column)
    ).fetchone()
    return row is not None


def _pg_table_exists(conn, table: str) -> bool:
    """Check if a table exists in PostgreSQL."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name=?",
        (table,)
    ).fetchone()
    return row is not None


def init_db(db_path: Path = DB_PATH):
    """Initialize database with schema. Safe to call multiple times."""
    if _USE_PG:
        return _init_pg()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)

    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    conn.commit()
    return conn


def _init_pg():
    """Initialize PostgreSQL schema."""
    conn = get_connection()
    schema = SCHEMA_PG_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    return conn


def _migrate(conn):
    """Run incremental migrations. Safe to call multiple times."""
    if _USE_PG:
        _migrate_pg(conn)
        return

    # SQLite migrations (unchanged)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "avatar" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN avatar TEXT DEFAULT ''")
    if "tagline" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN tagline TEXT DEFAULT ''")
    if "motivation" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN motivation TEXT DEFAULT ''")

    try:
        im_cols = {r[1] for r in conn.execute("PRAGMA table_info(ideation_messages)").fetchall()}
        if im_cols and "role" not in im_cols:
            conn.execute("ALTER TABLE ideation_messages ADD COLUMN role TEXT DEFAULT ''")
        if im_cols and "target" not in im_cols:
            conn.execute("ALTER TABLE ideation_messages ADD COLUMN target TEXT DEFAULT ''")
    except Exception:
        pass

    try:
        m_cols = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        for col, default in [("business_value", "0"), ("time_criticality", "0"),
                             ("risk_reduction", "0"), ("job_duration", "1")]:
            if col not in m_cols:
                conn.execute(f"ALTER TABLE missions ADD COLUMN {col} REAL DEFAULT {default}")
    except Exception:
        pass

    try:
        mr_cols = {r[1] for r in conn.execute("PRAGMA table_info(mission_runs)").fetchall()}
        if mr_cols and "workspace_path" not in mr_cols:
            conn.execute("ALTER TABLE mission_runs ADD COLUMN workspace_path TEXT DEFAULT ''")
        if mr_cols and "parent_mission_id" not in mr_cols:
            conn.execute("ALTER TABLE mission_runs ADD COLUMN parent_mission_id TEXT DEFAULT ''")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            epic_id TEXT NOT NULL,
            accepted INTEGER DEFAULT 0,
            rejected INTEGER DEFAULT 0,
            iterations INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, epic_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS retrospectives (
            id TEXT PRIMARY KEY,
            scope TEXT DEFAULT 'epic',
            scope_id TEXT DEFAULT '',
            successes TEXT DEFAULT '[]',
            failures TEXT DEFAULT '[]',
            lessons TEXT DEFAULT '[]',
            improvements TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id TEXT PRIMARY KEY,
            epic_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            acceptance_criteria TEXT DEFAULT '',
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'backlog',
            story_points INTEGER DEFAULT 0,
            assigned_to TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_epic ON features(epic_id)")

    try:
        sp_cols = {r[1] for r in conn.execute("PRAGMA table_info(sprints)").fetchall()}
        if sp_cols:
            if "velocity" not in sp_cols:
                conn.execute("ALTER TABLE sprints ADD COLUMN velocity INTEGER DEFAULT 0")
            if "planned_sp" not in sp_cols:
                conn.execute("ALTER TABLE sprints ADD COLUMN planned_sp INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        m_cols2 = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if m_cols2 and "kanban_status" not in m_cols2:
            conn.execute("ALTER TABLE missions ADD COLUMN kanban_status TEXT DEFAULT 'funnel'")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS feature_deps (
            feature_id TEXT NOT NULL,
            depends_on TEXT NOT NULL,
            dep_type TEXT DEFAULT 'blocked_by',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (feature_id, depends_on)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS program_increments (
            id TEXT PRIMARY KEY,
            art_id TEXT DEFAULT '',
            number INTEGER DEFAULT 1,
            name TEXT DEFAULT '',
            goal TEXT DEFAULT '',
            status TEXT DEFAULT 'planning',
            start_date TEXT,
            end_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pi_art ON program_increments(art_id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS confluence_pages (
            mission_id TEXT NOT NULL,
            tab TEXT NOT NULL,
            confluence_page_id TEXT NOT NULL,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (mission_id, tab)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            severity TEXT DEFAULT 'P3',
            category TEXT DEFAULT 'incident',
            status TEXT DEFAULT 'open',
            reporter TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            resolution TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_mission ON support_tickets(mission_id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_incidents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            severity TEXT DEFAULT 'P3',
            status TEXT DEFAULT 'open',
            source TEXT DEFAULT 'auto',
            error_type TEXT,
            error_detail TEXT,
            mission_id TEXT,
            agent_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON platform_incidents(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON platform_incidents(severity)")


def _migrate_pg(conn):
    """PostgreSQL incremental migrations (safe ALTER TABLE IF NOT EXISTS)."""
    # PG schema_pg.sql already includes all columns, but for future migrations:
    pass


def get_db(db_path: Path = DB_PATH):
    """Get a database connection. Returns SQLite or PostgreSQL adapter."""
    if _USE_PG:
        conn = get_connection()
        return conn

    if not db_path.exists():
        return init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
