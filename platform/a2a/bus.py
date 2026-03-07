"""
A2A Message Bus - Internal pub/sub for agent communication.
=============================================================
Async message routing with per-agent queues, persistence, and SSE bridge.

Redis pub/sub (optional):
  - If REDIS_URL is set, all SSE events are also published to Redis channel
    ``a2a:events``, enabling cross-process (IHM ↔ Factory) event delivery.
  - Fallback: in-memory only when Redis is unavailable or not configured.
  - Call ``start_redis_listener(redis_url)`` in the UI process to receive
    factory events and forward them to local SSE listeners.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Callable

from ..models import A2AMessage, MessageType

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "a2a:events"
PG_NOTIFY_CHANNEL = "a2a_events"  # PostgreSQL LISTEN/NOTIFY channel (cross-node)


class MessageBus:
    """
    Central message bus for Agent-to-Agent communication.
    Supports direct messages, broadcasts, topic subscriptions, and SSE streaming.
    Optionally backed by Redis pub/sub for cross-process event delivery.
    """

    def __init__(self, db_conn=None):
        self.db = db_conn
        self._agent_queues: dict[str, asyncio.Queue[A2AMessage]] = {}
        self._topic_subscribers: dict[str, list[str]] = {}  # topic → [agent_ids]
        self._sse_listeners: list[asyncio.Queue[A2AMessage]] = []
        self._dead_letter: list[A2AMessage] = []
        self._max_dead_letter = 1000
        self._handlers: dict[str, Callable] = {}  # agent_id → receive callback
        self._stats = {"published": 0, "delivered": 0, "dead_letter": 0}
        self._redis: Any = None  # redis.asyncio client (set via connect_redis)
        self._pg_notify_conn: Any = None  # psycopg async conn for NOTIFY
        self._pg_listen_task: asyncio.Task | None = None  # background LISTEN task

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

        # REF: arXiv:2602.20021 — SBD-06: validate from_agent to detect identity spoofing.
        _sender = message.from_agent
        _trusted_senders = {"user", "system", "platform", ""}
        if (
            _sender
            and _sender not in _trusted_senders
            and _sender not in self._agent_queues
            and _sender not in self._handlers
        ):
            logger.warning(
                "A2A IDENTITY_SPOOF: from_agent='%s' not registered in bus (session='%s'). "
                "Message type=%s — relaying but flagging for audit.",
                _sender[:40],
                (message.session_id or "?")[:20],
                message.message_type,
            )
            self._stats["spoofed"] = self._stats.get("spoofed", 0) + 1

        # Scope delegation guard: log warning if project-scoped agent delegates to platform
        if message.message_type and str(message.message_type) in (
            "delegate",
            "MessageType.DELEGATE",
        ):
            self._check_delegation_scope(message)

        # Persist to DB asynchronously (non-blocking)
        if self.db:
            asyncio.get_event_loop().call_soon(self._persist_message, message)

        # Route the message
        if message.to_agent:
            # Direct message
            await self._deliver(message.to_agent, message)
        else:
            # Broadcast to all agents in the session
            await self._broadcast(message)

        # Notify SSE listeners (for web UI)
        await self._notify_sse(message)

    def _check_delegation_scope(self, message: A2AMessage) -> None:
        """Warn when a non-platform agent tries to delegate to a platform agent.

        Scope hierarchy:  platform → art → project → self
        project/art agents may only delegate to agents at the same or lower scope.
        Enforcement is advisory (log-only) at the bus level; hard enforcement
        is in PermissionGuard.check_scope().
        """
        try:
            from ..agents.store import get_agent_store

            store = get_agent_store()
            sender = store.get(message.from_agent) if message.from_agent else None
            receiver = store.get(message.to_agent) if message.to_agent else None
            if not sender or not receiver:
                return
            sender_scope = (sender.permissions or {}).get("scope", "project")
            receiver_scope = (receiver.permissions or {}).get("scope", "project")
            _rank = {"platform": 0, "art": 1, "project": 2, "self": 3}
            if _rank.get(sender_scope, 2) > _rank.get(receiver_scope, 2):
                logger.warning(
                    "A2A scope mismatch: %s (scope=%s) delegating to %s (scope=%s) — "
                    "lower-scope agents should escalate via Jarvis",
                    message.from_agent,
                    sender_scope,
                    message.to_agent,
                    receiver_scope,
                )
        except Exception:
            pass  # non-blocking — never break message delivery

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
        """Broadcast to all agents in the same session (session-scoped)."""
        targets = set()

        for agent_id, handler in self._handlers.items():
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
        queue: asyncio.Queue[A2AMessage] = asyncio.Queue(maxsize=5000)
        self._sse_listeners.append(queue)
        return queue

    def remove_sse_listener(self, queue: asyncio.Queue):
        """Remove a SSE listener."""
        if queue in self._sse_listeners:
            self._sse_listeners.remove(queue)

    async def _notify_sse(self, message: A2AMessage):
        """Push message to all local SSE listeners, and publish to Redis if connected."""
        for q in self._sse_listeners:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Drop event but keep listener alive — streaming produces many deltas
                pass

        # Publish to Redis for cross-process delivery (IHM ↔ Factory)
        if self._redis is not None:
            try:
                payload = json.dumps(
                    {
                        "id": message.id,
                        "session_id": message.session_id,
                        "from_agent": message.from_agent,
                        "to_agent": message.to_agent,
                        "message_type": message.message_type.value,
                        "content": message.content,
                        "metadata": message.metadata,
                        "artifacts": message.artifacts,
                        "parent_id": message.parent_id,
                        "priority": message.priority,
                        "requires_response": message.requires_response,
                        "timestamp": message.timestamp.isoformat(),
                    }
                )
                await self._redis.publish(REDIS_CHANNEL, payload)
            except Exception as exc:
                logger.debug("Redis publish error (non-fatal): %s", exc)

        # Publish to PG NOTIFY for cross-node delivery
        if self._pg_notify_conn is not None:
            try:
                payload = json.dumps(
                    {
                        "id": message.id,
                        "session_id": message.session_id,
                        "from_agent": message.from_agent,
                        "to_agent": message.to_agent,
                        "message_type": message.message_type.value,
                        "content": message.content[
                            :2000
                        ],  # PG NOTIFY limit: 8000 bytes
                        "metadata": message.metadata,
                        "priority": message.priority,
                        "timestamp": message.timestamp.isoformat(),
                    }
                )
                await self._pg_notify_conn.execute(
                    f"NOTIFY {PG_NOTIFY_CHANNEL}, %s", (payload,)
                )
            except Exception as exc:
                logger.debug("PG NOTIFY error (non-fatal): %s", exc)

    async def connect_pg_notify(self, database_url: str | None = None) -> bool:
        """Open a dedicated async PG connection for cross-node LISTEN/NOTIFY.

        Enables SSE events to be shared across cluster nodes via PostgreSQL.
        Falls back silently if psycopg async is unavailable or DB is not PG.
        """
        from ..db.adapter import is_postgresql

        if not is_postgresql():
            return False
        db_url = database_url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            return False
        try:
            import psycopg

            conn = await psycopg.AsyncConnection.connect(db_url, autocommit=True)
            self._pg_notify_conn = conn
            logger.info(
                "MessageBus: PG NOTIFY connected on channel %s", PG_NOTIFY_CHANNEL
            )
            return True
        except Exception as exc:
            logger.warning("PG NOTIFY unavailable (%s) — bus cross-node disabled", exc)
            self._pg_notify_conn = None
            return False

    async def start_pg_listen(self, database_url: str | None = None) -> None:
        """Subscribe to PG LISTEN and fan out incoming NOTIFY to local SSE listeners.

        Run as a background asyncio task. Reconnects automatically on failure.
        Messages from other nodes are forwarded to local SSE clients.
        """
        from ..db.adapter import is_postgresql

        if not is_postgresql():
            return
        db_url = database_url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            return

        node_id = os.environ.get("SF_NODE_ID", "unknown")

        while True:
            try:
                import psycopg

                async with await psycopg.AsyncConnection.connect(
                    db_url, autocommit=True
                ) as conn:
                    await conn.execute(f"LISTEN {PG_NOTIFY_CHANNEL}")
                    logger.info("MessageBus: PG LISTEN started (node=%s)", node_id)
                    async for notify in conn.notifies():
                        if not notify.payload:
                            continue
                        try:
                            data = json.loads(notify.payload)
                            msg = A2AMessage(
                                id=data.get("id", ""),
                                session_id=data.get("session_id", ""),
                                from_agent=data.get("from_agent", ""),
                                to_agent=data.get("to_agent"),
                                message_type=MessageType(
                                    data.get("message_type", "chat")
                                ),
                                content=data.get("content", ""),
                                metadata=data.get("metadata", {}),
                                priority=data.get("priority", 5),
                                timestamp=datetime.fromisoformat(data["timestamp"])
                                if data.get("timestamp")
                                else datetime.now(),
                            )
                            for q in self._sse_listeners:
                                try:
                                    q.put_nowait(msg)
                                except asyncio.QueueFull:
                                    pass
                        except Exception as exc:
                            logger.debug("PG LISTEN parse error: %s", exc)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("PG LISTEN error (%s) — reconnecting in 5s", exc)
                await asyncio.sleep(5)

    async def connect_redis(self, redis_url: str) -> bool:
        """Connect to Redis for cross-process pub/sub. Returns True on success."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                redis_url, decode_responses=True, socket_connect_timeout=5
            )
            await self._redis.ping()
            logger.info("MessageBus: Redis connected at %s", redis_url)
            return True
        except ImportError:
            logger.warning("redis[asyncio] not installed — bus running in-memory only")
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — bus running in-memory only", exc)
        self._redis = None
        return False

    async def start_redis_listener(self, redis_url: str) -> None:
        """Subscribe to Redis a2a:events and fan out to local SSE listeners.

        Run this as a background task in the UI process to receive events
        published by the factory process.
        """
        try:
            import redis.asyncio as aioredis
        except ImportError:
            logger.warning("redis[asyncio] not installed — Redis listener not started")
            return

        while True:
            try:
                client = aioredis.from_url(
                    redis_url, decode_responses=True, socket_connect_timeout=5
                )
                pubsub = client.pubsub()
                await pubsub.subscribe(REDIS_CHANNEL)
                logger.info(
                    "MessageBus: Redis subscriber started on channel %s", REDIS_CHANNEL
                )
                async for raw in pubsub.listen():
                    if raw["type"] != "message":
                        continue
                    try:
                        data = json.loads(raw["data"])
                        msg = A2AMessage(
                            id=data.get("id", ""),
                            session_id=data.get("session_id", ""),
                            from_agent=data.get("from_agent", ""),
                            to_agent=data.get("to_agent"),
                            message_type=MessageType(data.get("message_type", "chat")),
                            content=data.get("content", ""),
                            metadata=data.get("metadata", {}),
                            artifacts=data.get("artifacts", []),
                            parent_id=data.get("parent_id"),
                            priority=data.get("priority", 5),
                            requires_response=bool(
                                data.get("requires_response", False)
                            ),
                            timestamp=datetime.fromisoformat(data["timestamp"])
                            if data.get("timestamp")
                            else datetime.now(),
                        )
                        for q in self._sse_listeners:
                            try:
                                q.put_nowait(msg)
                            except asyncio.QueueFull:
                                pass
                    except Exception as exc:
                        logger.debug("Redis message parse error: %s", exc)
            except asyncio.CancelledError:
                return
            except RuntimeError as exc:
                # Python 3.12+: aclose() called on a running async generator (shutdown race)
                if "aclose" in str(exc) or "asynchronous generator" in str(exc):
                    return
                logger.warning(
                    "Redis listener RuntimeError (%s) — reconnecting in 5s", exc
                )
                await asyncio.sleep(5)
            except Exception as exc:
                logger.warning("Redis listener error (%s) — reconnecting in 5s", exc)
                await asyncio.sleep(5)

    # ── Dead Letter ───────────────────────────────────────────────────

    def _dead_letter_add(self, message: A2AMessage):
        self._dead_letter.append(message)
        self._stats["dead_letter"] += 1
        if len(self._dead_letter) > self._max_dead_letter:
            self._dead_letter = self._dead_letter[-self._max_dead_letter :]

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
                    message.id,
                    message.session_id,
                    message.from_agent,
                    message.to_agent,
                    message.message_type.value,
                    message.content,
                    json.dumps(message.metadata),
                    json.dumps(message.artifacts),
                    message.parent_id,
                    message.priority,
                    int(message.requires_response),
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

    def search_messages(
        self, query: str, session_id: str = None, limit: int = 20
    ) -> list[dict]:
        """Full-text search on messages (PostgreSQL tsvector)."""
        if not self.db:
            return []
        if session_id:
            rows = self.db.execute(
                """SELECT m.* FROM messages m
                   WHERE m.content_tsv @@ plainto_tsquery('simple', ?) AND m.session_id = ?
                   ORDER BY ts_rank(m.content_tsv, plainto_tsquery('simple', ?)) DESC LIMIT ?""",
                (query, session_id, query, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                """SELECT m.* FROM messages m
                   WHERE m.content_tsv @@ plainto_tsquery('simple', ?)
                   ORDER BY ts_rank(m.content_tsv, plainto_tsquery('simple', ?)) DESC LIMIT ?""",
                (query, query, limit),
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
        from ..db.migrations import get_db

        _bus = MessageBus(db_conn=get_db())
    return _bus
