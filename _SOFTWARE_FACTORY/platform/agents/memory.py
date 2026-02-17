"""
Agent Memory - Short-term, long-term, and shared memory management.
====================================================================
Uses SQLite FTS5 for semantic search over memory entries.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional

from ..models import A2AMessage


class AgentMemory:
    """Memory system for agents: short-term buffer + long-term FTS5 store."""

    def __init__(self, db_conn: sqlite3.Connection, window_size: int = 50):
        self.db = db_conn
        self.window_size = window_size
        # Short-term: per-agent sliding window of recent messages
        self._short_term: dict[str, list[dict]] = {}

    # ── Short-term (conversation buffer) ──────────────────────────────

    def get_recent(self, agent_id: str, limit: int = None) -> list[dict]:
        """Get recent messages for an agent (short-term memory)."""
        limit = limit or self.window_size
        buffer = self._short_term.get(agent_id, [])
        return buffer[-limit:]

    async def store_message(self, agent_id: str, message: A2AMessage):
        """Store a message in short-term memory."""
        if agent_id not in self._short_term:
            self._short_term[agent_id] = []

        entry = {
            "id": message.id,
            "from": message.from_agent,
            "to": message.to_agent,
            "type": message.message_type.value,
            "content": message.content[:2000],  # cap for memory
            "timestamp": message.timestamp.isoformat(),
        }
        self._short_term[agent_id].append(entry)

        # Sliding window
        if len(self._short_term[agent_id]) > self.window_size * 2:
            self._short_term[agent_id] = self._short_term[agent_id][-self.window_size:]

    def get_context_summary(self, agent_id: str, max_chars: int = 3000) -> str:
        """Build a context summary from recent messages."""
        recent = self.get_recent(agent_id, limit=20)
        if not recent:
            return ""

        lines = []
        chars = 0
        for msg in reversed(recent):
            line = f"[{msg['type']}] {msg['from']}: {msg['content'][:200]}"
            if chars + len(line) > max_chars:
                break
            lines.append(line)
            chars += len(line)

        lines.reverse()
        return "\n".join(lines)

    # ── Long-term (persistent FTS5 store) ─────────────────────────────

    async def store(self, agent_id: str, key: str, value: str, importance: float = 0.5):
        """Store a key-value pair in long-term memory."""
        self.db.execute(
            """INSERT INTO memory_entries (agent_id, key, value, importance)
               VALUES (?, ?, ?, ?)""",
            (agent_id, key, value, importance),
        )
        self.db.commit()

    async def search(self, agent_id: str, query: str, limit: int = 10) -> list[str]:
        """Search long-term memory using FTS5."""
        rows = self.db.execute(
            """SELECT m.value, m.key, m.importance
               FROM memory_entries m
               JOIN memory_fts f ON m.id = f.rowid
               WHERE memory_fts MATCH ? AND m.agent_id = ?
               ORDER BY rank
               LIMIT ?""",
            (query, agent_id, limit),
        ).fetchall()

        # Update access timestamps
        for row in rows:
            self.db.execute(
                """UPDATE memory_entries
                   SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1
                   WHERE agent_id = ? AND key = ?""",
                (agent_id, row["key"]),
            )
        self.db.commit()

        return [row["value"] for row in rows]

    async def search_all(self, query: str, limit: int = 20) -> list[dict]:
        """Search across all agents' memories."""
        rows = self.db.execute(
            """SELECT m.agent_id, m.key, m.value, m.importance
               FROM memory_entries m
               JOIN memory_fts f ON m.id = f.rowid
               WHERE memory_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()

        return [dict(row) for row in rows]

    async def get_by_key(self, agent_id: str, key: str) -> Optional[str]:
        """Get a specific memory entry by key."""
        row = self.db.execute(
            """SELECT value FROM memory_entries
               WHERE agent_id = ? AND key = ?
               ORDER BY created_at DESC LIMIT 1""",
            (agent_id, key),
        ).fetchone()
        return row["value"] if row else None

    async def forget(self, agent_id: str, key: str):
        """Remove a memory entry."""
        self.db.execute(
            "DELETE FROM memory_entries WHERE agent_id = ? AND key = ?",
            (agent_id, key),
        )
        self.db.commit()

    async def consolidate(self, agent_id: str, max_entries: int = 500):
        """Remove low-importance, rarely accessed entries to keep memory lean."""
        count = self.db.execute(
            "SELECT COUNT(*) as cnt FROM memory_entries WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()["cnt"]

        if count > max_entries:
            # Delete oldest, least accessed, lowest importance entries
            to_delete = count - max_entries
            self.db.execute(
                """DELETE FROM memory_entries WHERE id IN (
                    SELECT id FROM memory_entries
                    WHERE agent_id = ?
                    ORDER BY importance ASC, access_count ASC, accessed_at ASC
                    LIMIT ?
                )""",
                (agent_id, to_delete),
            )
            self.db.commit()

    def clear_short_term(self, agent_id: str):
        """Clear short-term memory for an agent."""
        self._short_term.pop(agent_id, None)
