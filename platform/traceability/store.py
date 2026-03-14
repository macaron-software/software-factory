"""Traceability store — why_log: records the causal chain for every artifact.

Every time an agent produces an artifact (code file, test, story, ADR, decision),
we log WHY it was created: the full lineage chain from vision down to the task.

Answers: "Why does this code/test exist?"

Rationale: using get_db() ensures why_log goes into the same backend (SQLite dev /
PostgreSQL prod) as all other platform tables, instead of a hard-coded SQLite path.
The why_log schema is created by _ensure_table() on first use so no migration needed.
Source: TinyAGI/fractals traceability concept + ADR-0015.
"""
# Ref: feat-annotate

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


def _ensure_table() -> None:
    conn = get_db()
    try:
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
        conn.commit()
    finally:
        conn.close()


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
    conn = get_db()
    try:
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
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_why(artifact_ref: str) -> list[WhyEntry]:
    """Get all why_log entries matching an artifact ref (filename, story id, etc.)."""
    _ensure_table()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM why_log WHERE artifact_ref LIKE ? ORDER BY created_at DESC",
            (f"%{artifact_ref}%",),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_entry(r) for r in rows]


def get_session_why(session_id: str) -> list[WhyEntry]:
    """Get full why-chain for all artifacts produced in a session."""
    _ensure_table()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM why_log WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_entry(r) for r in rows]


def _row_to_entry(row) -> WhyEntry:
    return WhyEntry(
        id=row["id"],
        session_id=row["session_id"],
        artifact_type=row["artifact_type"],
        artifact_ref=row["artifact_ref"],
        lineage=json.loads(row["lineage_json"] or "[]"),
        rationale=row["rationale"] or "",
        created_at=row["created_at"],
    )
