"""Event Store — append-only event log for audit, replay, and observability.

Every significant action in the platform emits an event:
  mission_created, phase_started, phase_completed, phase_failed,
  agent_called, tool_executed, veto_raised, pipeline_resumed, etc.

Events are immutable (INSERT only, never UPDATE/DELETE).
Query by aggregate_id (mission/project) for full audit trail.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform.db"


@dataclass
class Event:
    """Immutable event record."""

    id: str = ""
    event_type: str = ""
    aggregate_type: str = ""  # "mission", "project", "agent", "pipeline"
    aggregate_id: str = ""
    actor: str = ""  # agent_id or "system" or "user:<name>"
    payload: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()


# Common event types
MISSION_CREATED = "mission_created"
MISSION_STARTED = "mission_started"
MISSION_COMPLETED = "mission_completed"
MISSION_FAILED = "mission_failed"
PHASE_STARTED = "phase_started"
PHASE_COMPLETED = "phase_completed"
PHASE_FAILED = "phase_failed"
PHASE_SKIPPED = "phase_skipped"
AGENT_CALLED = "agent_called"
AGENT_RESPONDED = "agent_responded"
TOOL_EXECUTED = "tool_executed"
VETO_RAISED = "veto_raised"
PIPELINE_RESUMED = "pipeline_resumed"
QUALITY_GATE_PASSED = "quality_gate_passed"
QUALITY_GATE_FAILED = "quality_gate_failed"


def _ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id             TEXT PRIMARY KEY,
            event_type     TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id   TEXT NOT NULL,
            actor          TEXT DEFAULT 'system',
            payload        TEXT DEFAULT '{}',
            timestamp      REAL NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(aggregate_type, aggregate_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)")


class EventStore:
    """Append-only event store backed by SQLite."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else _DB_PATH
        self._listeners: list = []
        self._initialized = False

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self._db_path))
        db.row_factory = sqlite3.Row
        if not self._initialized:
            _ensure_table(db)
            self._initialized = True
        return db

    def emit(self, event: Event) -> Event:
        """Append an event to the store and notify listeners."""
        db = self._db()
        try:
            db.execute(
                "INSERT INTO events (id, event_type, aggregate_type, aggregate_id, actor, payload, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.event_type,
                    event.aggregate_type,
                    event.aggregate_id,
                    event.actor,
                    json.dumps(event.payload, default=str),
                    event.timestamp,
                ),
            )
            db.commit()
        finally:
            db.close()

        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Event listener error")

        return event

    def emit_simple(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor: str = "system",
        **payload,
    ) -> Event:
        """Convenience: create and emit an event in one call."""
        return self.emit(
            Event(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                actor=actor,
                payload=payload,
            )
        )

    def query(
        self,
        aggregate_id: str | None = None,
        aggregate_type: str | None = None,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query events with filters."""
        conditions = []
        params: list = []
        if aggregate_id:
            conditions.append("aggregate_id = ?")
            params.append(aggregate_id)
        if aggregate_type:
            conditions.append("aggregate_type = ?")
            params.append(aggregate_type)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM events {where} ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        db = self._db()
        try:
            rows = db.execute(sql, params).fetchall()
            return [
                Event(
                    id=r["id"],
                    event_type=r["event_type"],
                    aggregate_type=r["aggregate_type"],
                    aggregate_id=r["aggregate_id"],
                    actor=r["actor"],
                    payload=json.loads(r["payload"]) if r["payload"] else {},
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]
        finally:
            db.close()

    def replay(self, aggregate_id: str) -> list[Event]:
        """Replay all events for an aggregate (full audit trail)."""
        return self.query(aggregate_id=aggregate_id, limit=10000)

    def count(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
    ) -> int:
        """Count events matching filters."""
        conditions = []
        params: list = []
        if aggregate_id:
            conditions.append("aggregate_id = ?")
            params.append(aggregate_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        db = self._db()
        try:
            return db.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]
        finally:
            db.close()

    def on_event(self, listener) -> None:
        """Register a synchronous listener for all events."""
        self._listeners.append(listener)

    def stats(self) -> dict:
        """Return event store statistics."""
        db = self._db()
        try:
            total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            by_type = dict(
                db.execute(
                    "SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC LIMIT 20"
                ).fetchall()
            )
            by_aggregate = dict(
                db.execute(
                    "SELECT aggregate_type, COUNT(*) FROM events GROUP BY aggregate_type ORDER BY COUNT(*) DESC"
                ).fetchall()
            )
            return {"total": total, "by_type": by_type, "by_aggregate": by_aggregate}
        finally:
            db.close()


# Singleton
_store = EventStore()


def get_event_store() -> EventStore:
    """Return the global event store instance."""
    return _store
