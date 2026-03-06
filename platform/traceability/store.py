"""Traceability store — why_log: records the causal chain for every artifact.

Every time an agent produces an artifact (code file, test, story, ADR, decision),
we log WHY it was created: the full lineage chain from vision down to the task.

Answers: "Why does this code/test exist?"

Design: SQLite table why_log (lightweight, no external deps, same DB as platform).
Inspired by our own practice of documenting sources in code comments
(ADR-0015, TinyAGI/fractals, OWASP LLM01 etc.) — now applied systematically.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Platform's main SQLite DB
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "platform.db"


@contextmanager
def _db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_table() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS why_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT    NOT NULL,
                artifact_type TEXT    NOT NULL,
                artifact_ref  TEXT    NOT NULL,
                lineage_json  TEXT    NOT NULL DEFAULT '[]',
                rationale     TEXT    DEFAULT '',
                created_at    TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_why_log_session  ON why_log(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_why_log_artifact ON why_log(artifact_ref)")


@dataclass
class WhyEntry:
    id: int
    session_id: str
    artifact_type: str
    artifact_ref: str
    lineage: list[str]
    rationale: str
    created_at: str

    @property
    def lineage_chain(self) -> str:
        return " → ".join(self.lineage)


def log_artifact(
    session_id: str,
    artifact_type: str,  # code | test | story | decision | qa
    artifact_ref: str,
    lineage: list[str],
    rationale: str = "",
) -> int:
    """Log WHY an artifact was created. Returns the why_log row id."""
    _ensure_table()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO why_log "
            "(session_id, artifact_type, artifact_ref, lineage_json, rationale, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                artifact_type,
                artifact_ref,
                json.dumps(lineage, ensure_ascii=False),
                rationale,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


def get_why(artifact_ref: str) -> list[WhyEntry]:
    """Get all why_log entries matching an artifact ref (filename, story id, etc.)."""
    _ensure_table()
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM why_log WHERE artifact_ref LIKE ? ORDER BY created_at DESC",
            (f"%{artifact_ref}%",),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_session_why(session_id: str) -> list[WhyEntry]:
    """Get full why-chain for all artifacts produced in a session."""
    _ensure_table()
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM why_log WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def _row_to_entry(row: sqlite3.Row) -> WhyEntry:
    return WhyEntry(
        id=row["id"],
        session_id=row["session_id"],
        artifact_type=row["artifact_type"],
        artifact_ref=row["artifact_ref"],
        lineage=json.loads(row["lineage_json"] or "[]"),
        rationale=row["rationale"] or "",
        created_at=row["created_at"],
    )
