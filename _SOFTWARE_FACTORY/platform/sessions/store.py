"""Session & message store — manages conversations between agents and users."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..db.migrations import get_db


@dataclass
class SessionDef:
    """A collaboration session."""
    id: str = ""
    name: str = ""
    description: str = ""
    pattern_id: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "planning"  # planning | active | completed | failed
    goal: str = ""
    config: dict = field(default_factory=dict)
    created_at: str = ""
    completed_at: Optional[str] = None


@dataclass
class MessageDef:
    """A message in a session conversation."""
    id: str = ""
    session_id: str = ""
    from_agent: str = "user"  # agent_id or "user"
    to_agent: Optional[str] = None  # agent_id or None for broadcast
    message_type: str = "text"  # text|code|veto|approval|delegation|instruction|artifact|system
    content: str = ""
    metadata: dict = field(default_factory=dict)
    artifacts: list = field(default_factory=list)
    parent_id: Optional[str] = None
    priority: int = 5
    timestamp: str = ""


def _row_to_session(row) -> SessionDef:
    return SessionDef(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        pattern_id=row["pattern_id"],
        project_id=row["project_id"],
        status=row["status"] or "planning",
        goal=row["goal"] or "",
        config=json.loads(row["config_json"] or "{}"),
        created_at=row["created_at"] or "",
        completed_at=row["completed_at"],
    )


def _row_to_message(row) -> MessageDef:
    return MessageDef(
        id=row["id"],
        session_id=row["session_id"],
        from_agent=row["from_agent"],
        to_agent=row["to_agent"],
        message_type=row["message_type"] or "text",
        content=row["content"] or "",
        metadata=json.loads(row["metadata_json"] or "{}"),
        artifacts=json.loads(row["artifacts_json"] or "[]"),
        parent_id=row["parent_id"],
        priority=row["priority"] or 5,
        timestamp=row["timestamp"] or "",
    )


class SessionStore:
    """CRUD for sessions and messages."""

    # ── Sessions ─────────────────────────────────────────────────

    def list_all(self, limit: int = 50) -> list[SessionDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [_row_to_session(r) for r in rows]
        finally:
            db.close()

    def get(self, session_id: str) -> Optional[SessionDef]:
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return _row_to_session(row) if row else None
        finally:
            db.close()

    def create(self, session: SessionDef) -> SessionDef:
        if not session.id:
            session.id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        session.created_at = now
        db = get_db()
        try:
            db.execute(
                """INSERT INTO sessions (id, name, description, pattern_id, project_id,
                   status, goal, config_json, created_at, completed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (session.id, session.name, session.description, session.pattern_id,
                 session.project_id, session.status, session.goal,
                 json.dumps(session.config), session.created_at, session.completed_at),
            )
            db.commit()
        finally:
            db.close()
        return session

    def update_status(self, session_id: str, status: str) -> bool:
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status in ("completed", "failed") else None
            cur = db.execute(
                "UPDATE sessions SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed, session_id),
            )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def update_config(self, session_id: str, config: dict) -> bool:
        db = get_db()
        try:
            cur = db.execute(
                "UPDATE sessions SET config_json = ? WHERE id = ?",
                (json.dumps(config), session_id),
            )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def delete(self, session_id: str) -> bool:
        db = get_db()
        try:
            db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cur = db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    # ── Messages ─────────────────────────────────────────────────

    def get_messages(self, session_id: str, limit: int = 100) -> list[MessageDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return [_row_to_message(r) for r in rows]
        finally:
            db.close()

    def get_messages_after(self, session_id: str, after_id: str, limit: int = 100) -> list[MessageDef]:
        """Get messages newer than a given message ID (for polling)."""
        db = get_db()
        try:
            ref = db.execute(
                "SELECT timestamp FROM messages WHERE id = ?", (after_id,)
            ).fetchone()
            if not ref:
                return []
            rows = db.execute(
                """SELECT * FROM messages
                   WHERE session_id = ? AND timestamp > ? AND id != ?
                   ORDER BY timestamp ASC LIMIT ?""",
                (session_id, ref["timestamp"], after_id, limit),
            ).fetchall()
            return [_row_to_message(r) for r in rows]
        finally:
            db.close()

    def add_message(self, msg: MessageDef) -> MessageDef:
        if not msg.id:
            msg.id = str(uuid.uuid4())[:8]
        if not msg.timestamp:
            msg.timestamp = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT INTO messages (id, session_id, from_agent, to_agent,
                   message_type, content, metadata_json, artifacts_json,
                   parent_id, priority, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (msg.id, msg.session_id, msg.from_agent, msg.to_agent,
                 msg.message_type, msg.content,
                 json.dumps(msg.metadata), json.dumps(msg.artifacts),
                 msg.parent_id, msg.priority, msg.timestamp),
            )
            db.commit()
        finally:
            db.close()
        return msg

    # ── Counts ───────────────────────────────────────────────────

    def count_sessions(self) -> int:
        db = get_db()
        try:
            return db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            db.close()

    def count_messages(self, session_id: str) -> int:
        db = get_db()
        try:
            return db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
        finally:
            db.close()


_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
