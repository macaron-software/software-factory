"""Event store — append-only log for mission/agent/system events.

Usage:
    from platform.events.store import get_event_store
    store = get_event_store()
    store.emit("mission.started", {"mission_id": "abc", "workflow": "tdd"})
    events = store.query(entity_id="abc", limit=50)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform.db"

# Event types
MISSION_STARTED = "mission.started"
MISSION_COMPLETED = "mission.completed"
MISSION_FAILED = "mission.failed"
MISSION_PAUSED = "mission.paused"
MISSION_RESUMED = "mission.resumed"
PHASE_STARTED = "phase.started"
PHASE_COMPLETED = "phase.completed"
PHASE_FAILED = "phase.failed"
PHASE_TIMEOUT = "phase.timeout"
AGENT_ASSIGNED = "agent.assigned"
AGENT_COMPLETED = "agent.completed"
AGENT_ERROR = "agent.error"
SESSION_CREATED = "session.created"
SESSION_ENDED = "session.ended"
DEPLOY_STARTED = "deploy.started"
DEPLOY_COMPLETED = "deploy.completed"
QUALITY_SCANNED = "quality.scanned"
INCIDENT_CREATED = "incident.created"
INCIDENT_RESOLVED = "incident.resolved"


class EventStore:
    """Append-only event log backed by SQLite."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        conn = self._conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT '',
                    entity_id TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL DEFAULT '',
                    data TEXT NOT NULL DEFAULT '{}',
                    project_id TEXT NOT NULL DEFAULT '',
                    mission_id TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_mission ON events(mission_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)"
            )
            conn.commit()
        finally:
            conn.close()

    def emit(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        entity_type: str = "",
        entity_id: str = "",
        actor: str = "",
        project_id: str = "",
        mission_id: str = "",
    ) -> str:
        """Append an event to the log. Returns event ID."""
        event_id = uuid.uuid4().hex[:16]
        ts = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO events (id, timestamp, event_type, entity_type, entity_id, actor, data, project_id, mission_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    ts,
                    event_type,
                    entity_type,
                    entity_id,
                    actor,
                    json.dumps(data or {}, default=str),
                    project_id,
                    mission_id,
                ),
            )
            conn.commit()
            logger.debug("Event %s: %s entity=%s/%s", event_id, event_type, entity_type, entity_id)
            return event_id
        finally:
            conn.close()

    def query(
        self,
        *,
        event_type: str = "",
        entity_type: str = "",
        entity_id: str = "",
        mission_id: str = "",
        project_id: str = "",
        since: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """Query events with optional filters."""
        conditions = []
        params: list[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        if mission_id:
            conditions.append("mission_id = ?")
            params.append(mission_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM events WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                params,
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def replay(self, mission_id: str) -> list[dict]:
        """Replay all events for a mission in chronological order."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM events WHERE mission_id = ? ORDER BY timestamp ASC",
                (mission_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def count(self, event_type: str = "", since: str = "") -> int:
        """Count events, optionally filtered."""
        conditions = []
        params: list[Any] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1=1"
        conn = self._conn()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params).fetchone()[0]
        finally:
            conn.close()

    def stats(self, since: str = "") -> dict:
        """Get event statistics."""
        conn = self._conn()
        try:
            where = f"timestamp >= '{since}'" if since else "1=1"
            rows = conn.execute(
                f"SELECT event_type, COUNT(*) as cnt FROM events WHERE {where} GROUP BY event_type ORDER BY cnt DESC"
            ).fetchall()
            total = sum(r["cnt"] for r in rows)
            return {
                "total": total,
                "by_type": {r["event_type"]: r["cnt"] for r in rows},
            }
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        if "data" in d and isinstance(d["data"], str):
            try:
                d["data"] = json.loads(d["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d


# Singleton
_store: EventStore | None = None


def get_event_store() -> EventStore:
    """Get or create the singleton EventStore."""
    global _store
    if _store is None:
        _store = EventStore()
    return _store
