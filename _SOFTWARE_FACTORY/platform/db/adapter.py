"""
Dual-backend database adapter: SQLite (local) / PostgreSQL (production).

Provides a unified interface so all 22+ modules keep using:
    db = get_db()
    rows = db.execute("SELECT * FROM agents WHERE id=?", (aid,)).fetchall()
    db.commit()

Backend selected via DATABASE_URL env var:
    - Not set / "sqlite:///..." → SQLite (default, local dev)
    - "postgresql://..." → PostgreSQL (production)

Handles:
    - ? → %s placeholder translation
    - Row dict-like access for both backends
    - Connection pooling for PostgreSQL
    - PRAGMA skip for PostgreSQL
"""

import os
import re
import sqlite3
from typing import Any, Optional, Sequence

_PG_URL = os.environ.get("DATABASE_URL", "")
_USE_PG = _PG_URL.startswith("postgresql://") or _PG_URL.startswith("postgres://")

# Lazy import psycopg only when needed
_pg_pool = None


def _get_pg_connection():
    """Get a direct psycopg connection (no pool for now)."""
    import psycopg
    # Add connect_timeout if not present
    conninfo = _PG_URL
    if "connect_timeout" not in conninfo:
        sep = "&" if "?" in conninfo else "?"
        conninfo += f"{sep}connect_timeout=10"
    return psycopg.connect(conninfo)


# ── Placeholder translation ─────────────────────────────────────────────────

# SQLite uses ? for params, PostgreSQL uses %s
# Also handle named :name → %(name)s (not used in our codebase but safe)
_Q_RE = re.compile(r"\?")


def _translate_sql(sql: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s."""
    return _Q_RE.sub("%s", sql)


# ── Row wrapper ──────────────────────────────────────────────────────────────

class DictRow:
    """Dict-like row compatible with sqlite3.Row access patterns."""

    __slots__ = ("_data", "_keys")

    def __init__(self, keys: Sequence[str], values: Sequence[Any]):
        self._keys = tuple(keys)
        self._data = dict(zip(self._keys, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._keys

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return f"DictRow({self._data})"


# ── Cursor wrapper ───────────────────────────────────────────────────────────

class PgCursorWrapper:
    """Wraps psycopg cursor to return DictRow objects like sqlite3.Row."""

    def __init__(self, cursor):
        self._cur = cursor
        self._description = None

    @property
    def lastrowid(self):
        return getattr(self._cur, "lastrowid", None)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def _wrap_row(self, row):
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return DictRow(cols, row)

    def fetchone(self):
        row = self._cur.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows or not self._cur.description:
            return rows
        cols = [d[0] for d in self._cur.description]
        return [DictRow(cols, r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        if not rows or not self._cur.description:
            return rows
        cols = [d[0] for d in self._cur.description]
        return [DictRow(cols, r) for r in rows]

    def close(self):
        self._cur.close()

    def __iter__(self):
        cols = None
        for row in self._cur:
            if cols is None:
                cols = [d[0] for d in self._cur.description]
            yield DictRow(cols, row)


# ── Connection wrapper ───────────────────────────────────────────────────────

class PgConnectionWrapper:
    """Wraps psycopg connection to match sqlite3.Connection API.

    Key translations:
    - execute("...?...", params) → execute("...%s...", params)
    - Skips PRAGMA commands
    - executescript → splits and executes statements
    - Returns PgCursorWrapper for dict-like row access
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()) -> PgCursorWrapper:
        # Skip SQLite PRAGMAs
        stripped = sql.strip().upper()
        if stripped.startswith("PRAGMA"):
            return PgCursorWrapper(_NullCursor())

        # Skip SQLite FTS5 virtual tables and FTS triggers
        if "USING FTS5" in sql.upper():
            return PgCursorWrapper(_NullCursor())
        if "CREATE TRIGGER" in sql.upper() and "_fts" in sql.lower():
            return PgCursorWrapper(_NullCursor())

        translated = _translate_sql(sql)

        # AUTOINCREMENT → GENERATED ALWAYS not needed: just remove keyword
        translated = translated.replace("AUTOINCREMENT", "")

        # datetime('now') → CURRENT_TIMESTAMP
        translated = translated.replace("datetime('now')", "CURRENT_TIMESTAMP")

        cur = self._conn.cursor()
        try:
            cur.execute(translated, params)
        except Exception:
            self._conn.rollback()
            raise
        return PgCursorWrapper(cur)

    def executemany(self, sql: str, params_seq) -> PgCursorWrapper:
        translated = _translate_sql(sql)
        cur = self._conn.cursor()
        for params in params_seq:
            cur.execute(translated, params)
        return PgCursorWrapper(cur)

    def executescript(self, sql: str):
        """Execute multiple SQL statements (for schema init)."""
        # Filter out SQLite-specific statements
        lines = []
        skip = False
        for line in sql.split("\n"):
            up = line.strip().upper()
            if "USING FTS5" in up or ("CREATE TRIGGER" in up and "_fts" in line.lower()):
                skip = True
            if skip:
                if ";" in line:
                    skip = False
                continue
            if up.startswith("PRAGMA"):
                continue
            lines.append(line)

        cleaned = "\n".join(lines)
        # Replace AUTOINCREMENT and datetime('now')
        cleaned = cleaned.replace("AUTOINCREMENT", "")
        cleaned = cleaned.replace("datetime('now')", "CURRENT_TIMESTAMP")

        cur = self._conn.cursor()
        cur.execute(cleaned)
        return PgCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        pass  # No-op for PG — we use DictRow wrapper

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _NullCursor:
    """No-op cursor for skipped statements (PRAGMAs, FTS5)."""
    description = None
    lastrowid = None
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=None):
        return []

    def close(self):
        pass

    def __iter__(self):
        return iter([])


# ── Public API ───────────────────────────────────────────────────────────────

def is_postgresql() -> bool:
    """Check if using PostgreSQL backend."""
    return _USE_PG


def get_connection(db_path=None) -> Any:
    """Get a database connection (SQLite or PostgreSQL).

    For SQLite: returns sqlite3.Connection (with row_factory set)
    For PostgreSQL: returns PgConnectionWrapper
    """
    if _USE_PG:
        conn = _get_pg_connection()
        conn.autocommit = False
        return PgConnectionWrapper(conn)
    else:
        # SQLite path — same as original get_db()
        from pathlib import Path
        from ..config import DB_PATH
        path = db_path or DB_PATH
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def return_connection(conn):
    """Close a connection (for both backends)."""
    if conn:
        conn.close()
