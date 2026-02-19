"""
Database migrations and initialization for the platform.
"""

import sqlite3
from pathlib import Path

from ..config import DB_PATH, DATA_DIR

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initialize database with schema. Safe to call multiple times."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)

    conn.execute("PRAGMA foreign_keys=ON")

    # Migrations — add columns safely
    _migrate(conn)

    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection):
    """Run incremental migrations. Safe to call multiple times."""
    # Check existing columns
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "avatar" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN avatar TEXT DEFAULT ''")
    if "tagline" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN tagline TEXT DEFAULT ''")
    if "motivation" not in cols:
        conn.execute("ALTER TABLE agents ADD COLUMN motivation TEXT DEFAULT ''")

    # Ideation messages: add role + target columns
    try:
        im_cols = {r[1] for r in conn.execute("PRAGMA table_info(ideation_messages)").fetchall()}
        if im_cols and "role" not in im_cols:
            conn.execute("ALTER TABLE ideation_messages ADD COLUMN role TEXT DEFAULT ''")
        if im_cols and "target" not in im_cols:
            conn.execute("ALTER TABLE ideation_messages ADD COLUMN target TEXT DEFAULT ''")
    except Exception:
        pass

    # Missions: add WSJF component fields
    try:
        m_cols = {r[1] for r in conn.execute("PRAGMA table_info(missions)").fetchall()}
        for col, default in [("business_value", "0"), ("time_criticality", "0"),
                             ("risk_reduction", "0"), ("job_duration", "1")]:
            if col not in m_cols:
                conn.execute(f"ALTER TABLE missions ADD COLUMN {col} REAL DEFAULT {default}")
    except Exception:
        pass

    # Mission runs: add workspace_path
    try:
        mr_cols = {r[1] for r in conn.execute("PRAGMA table_info(mission_runs)").fetchall()}
        if mr_cols and "workspace_path" not in mr_cols:
            conn.execute("ALTER TABLE mission_runs ADD COLUMN workspace_path TEXT DEFAULT ''")
    except Exception:
        pass

    # Agent scores: performance tracking across epics
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

    # Retrospectives table
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

def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a database connection."""
    if not db_path.exists():
        return init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
