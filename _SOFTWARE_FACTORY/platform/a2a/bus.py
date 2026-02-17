"""
A2A Message Bus - Internal pub/sub for agent communication.
=============================================================
Async message routing with per-agent queues, persistence, and SSE bridge.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Callable, Optional

from ..models import A2AMessage, MessageType

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Central message bus for Agent-to-Agent communication.
    Supports direct messages, broadcasts, topic subscriptions, and SSE streaming.
    """

    def __init__(self, db_conn: sqlite3.Connection = None):
        self.db = db_conn
        self._agent_queues: dict[str, asyncio.Queue[A2AMessage]] = {}
        self._topic_subscribers: dict[str, list[str]] = {}  # topic → [agent_ids]
        self._sse_listeners: list[asyncio.Queue[A2AMessage]] = []
        self._dead_letter: list[A2AMessage] = []
        self._max_dead_letter = 1000
        self._handlers: dict[str, Callable] = {}  # agent_id → receive callback
        self._stats = {"published": 0, "delivered": 0, "dead_letter": 0}

    # ── Registration ──────────────────────────────────────────────────

    def register_agent(self, agent_id: str, handler: Callable = None):
        """Register an agent on the bus."""
        if agent_id not in self._agent_queues:
            self._agent_queues[agent_id] = asyncio.Queue(maxsize=500)
        if handler:
            self._handlers[agent_id] = handler

    def unregister_agent(self, agent_id: str):
        """Remove an agent from the bus."""
        self._agent_queues.pop(agent_id, None)
        self._handlers.pop(agent_id, None)
        # Remove from all topics
        for subscribers in self._topic_subscribers.values():
            if agent_id in subscribers:
                subscribers.remove(agent_id)

    def subscribe(self, agent_id: str, topic: str):
        """Subscribe an agent to a topic."""
        if topic not in self._topic_subscribers:
            self._topic_subscribers[topic] = []
        if agent_id not in self._topic_subscribers[topic]:
            self._topic_subscribers[topic].append(agent_id)

    def unsubscribe(self, agent_id: str, topic: str):
        if topic in self._topic_subscribers:
            self._topic_subscribers[topic] = [
                a for a in self._topic_subscribers[topic] if a != agent_id
            ]

    # ── Publishing ────────────────────────────────────────────────────

    async def publish(self, message: A2AMessage):
        """Publish a message to the bus."""
        self._stats["published"] += 1

        # Persist to DB
        if self.db:
            self._persist_message(message)

        # Route the message
        if message.to_agent:
            # Direct message
            await self._deliver(message.to_agent, message)
        else:
            # Broadcast to all agents in the session
            await self._broadcast(message)

        # Notify SSE listeners (for web UI)
        await self._notify_sse(message)

    async def _deliver(self, agent_id: str, message: A2AMessage):
        """Deliver a message to a specific agent."""
        # Try handler first (direct callback)
        handler = self._handlers.get(agent_id)
        if handler:
            try:
                await handler(message)
                self._stats["delivered"] += 1
                return
            except Exception as e:
                logger.error(f"Handler error for {agent_id}: {e}")

        # Fall back to queue
        queue = self._agent_queues.get(agent_id)
        if queue:
            try:
                queue.put_nowait(message)
                self._stats["delivered"] += 1
            except asyncio.QueueFull:
                self._dead_letter_add(message)
                logger.warning(f"Queue full for agent {agent_id[:8]}, dead-lettered")
        else:
            self._dead_letter_add(message)

    async def _broadcast(self, message: A2AMessage):
        """Broadcast to all agents in the same session."""
        targets = set()

        # All agents with queues (session filtering done by agents themselves)
        for agent_id in self._agent_queues:
            if agent_id != message.from_agent:
                targets.add(agent_id)

        # Topic subscribers if channel specified
        channel = message.metadata.get("channel")
        if channel and channel in self._topic_subscribers:
            for agent_id in self._topic_subscribers[channel]:
                targets.add(agent_id)

        for agent_id in targets:
            await self._deliver(agent_id, message)

    # ── SSE Bridge ────────────────────────────────────────────────────

    def add_sse_listener(self) -> asyncio.Queue[A2AMessage]:
        """Add a SSE listener (for web UI real-time updates)."""
        queue: asyncio.Queue[A2AMessage] = asyncio.Queue(maxsize=200)
        self._sse_listeners.append(queue)
        return queue

    def remove_sse_listener(self, queue: asyncio.Queue):
        """Remove a SSE listener."""
        if queue in self._sse_listeners:
            self._sse_listeners.remove(queue)

    async def _notify_sse(self, message: A2AMessage):
        """Push message to all SSE listeners."""
        dead = []
        for q in self._sse_listeners:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._sse_listeners.remove(q)

    # ── Dead Letter ───────────────────────────────────────────────────

    def _dead_letter_add(self, message: A2AMessage):
        self._dead_letter.append(message)
        self._stats["dead_letter"] += 1
        if len(self._dead_letter) > self._max_dead_letter:
            self._dead_letter = self._dead_letter[-self._max_dead_letter:]

    def get_dead_letters(self, limit: int = 50) -> list[A2AMessage]:
        return self._dead_letter[-limit:]

    # ── Persistence ───────────────────────────────────────────────────

    def _persist_message(self, message: A2AMessage):
        """Save message to database."""
        try:
            self.db.execute(
                """INSERT INTO messages
                   (id, session_id, from_agent, to_agent, message_type,
                    content, metadata_json, artifacts_json, parent_id,
                    priority, requires_response, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.id, message.session_id, message.from_agent,
                    message.to_agent, message.message_type.value,
                    message.content, json.dumps(message.metadata),
                    json.dumps(message.artifacts), message.parent_id,
                    message.priority, int(message.requires_response),
                    message.timestamp.isoformat(),
                ),
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

    # ── Query ─────────────────────────────────────────────────────────

    def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Get messages for a session from DB."""
        if not self.db:
            return []
        rows = self.db.execute(
            """SELECT * FROM messages
               WHERE session_id = ?
               ORDER BY timestamp ASC
               LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_messages(self, query: str, session_id: str = None, limit: int = 20) -> list[dict]:
        """Full-text search on messages."""
        if not self.db:
            return []
        if session_id:
            rows = self.db.execute(
                """SELECT m.* FROM messages m
                   JOIN messages_fts f ON m.rowid = f.rowid
                   WHERE messages_fts MATCH ? AND m.session_id = ?
                   ORDER BY rank LIMIT ?""",
                (query, session_id, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                """SELECT m.* FROM messages m
                   JOIN messages_fts f ON m.rowid = f.rowid
                   WHERE messages_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "registered_agents": len(self._agent_queues),
            "topics": len(self._topic_subscribers),
            "sse_listeners": len(self._sse_listeners),
            "dead_letter_count": len(self._dead_letter),
        }


# Singleton
_bus: MessageBus | None = None


def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
