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


def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a database connection."""
    if not db_path.exists():
        return init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
