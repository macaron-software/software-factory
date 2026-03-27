"""WebSocket real-time channel — bidirectional push for mission progress and notifications.

Provides /ws/live endpoint for:
  - Server → Client: mission progress, phase events, agent messages, notifications
  - Client → Server: pause/resume/cancel commands

Integrates with the EventStore and MessageBus for event sourcing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections with topic subscriptions."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}  # conn_id → ws
        self._subscriptions: dict[str, set[str]] = {}  # topic → {conn_ids}
        self._stats = {"connected": 0, "messages_sent": 0, "messages_received": 0}

    async def connect(self, websocket: WebSocket, conn_id: str) -> None:
        await websocket.accept()
        self._connections[conn_id] = websocket
        self._stats["connected"] = len(self._connections)
        logger.info("WS connected: %s (total: %d)", conn_id, len(self._connections))

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)
        for topic, conns in self._subscriptions.items():
            conns.discard(conn_id)
        self._stats["connected"] = len(self._connections)
        logger.info("WS disconnected: %s (total: %d)", conn_id, len(self._connections))

    def subscribe(self, conn_id: str, topic: str) -> None:
        """Subscribe a connection to a topic (e.g., 'mission:m-1', 'notifications')."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = set()
        self._subscriptions[topic].add(conn_id)

    def unsubscribe(self, conn_id: str, topic: str) -> None:
        if topic in self._subscriptions:
            self._subscriptions[topic].discard(conn_id)

    async def broadcast(self, topic: str, data: dict) -> int:
        """Send data to all connections subscribed to a topic. Returns send count."""
        conn_ids = self._subscriptions.get(topic, set())
        sent = 0
        dead = []
        message = json.dumps({"topic": topic, "data": data, "ts": time.time()})
        for conn_id in conn_ids:
            ws = self._connections.get(conn_id)
            if ws:
                try:
                    await ws.send_text(message)
                    sent += 1
                except Exception:
                    dead.append(conn_id)
        for d in dead:
            self.disconnect(d)
        self._stats["messages_sent"] += sent
        return sent

    async def send_to(self, conn_id: str, data: dict) -> bool:
        """Send data to a specific connection."""
        ws = self._connections.get(conn_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
                self._stats["messages_sent"] += 1
                return True
            except Exception:
                self.disconnect(conn_id)
        return False

    @property
    def stats(self) -> dict:
        return {**self._stats, "subscriptions": {t: len(c) for t, c in self._subscriptions.items() if c}}


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Bidirectional WebSocket for real-time platform updates."""
    import uuid

    conn_id = str(uuid.uuid4())[:8]
    await manager.connect(websocket, conn_id)

    # Auto-subscribe to global notifications
    manager.subscribe(conn_id, "notifications")

    try:
        while True:
            raw = await websocket.receive_text()
            manager._stats["messages_received"] += 1

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            action = msg.get("action", "")

            if action == "subscribe":
                topic = msg.get("topic", "")
                if topic:
                    manager.subscribe(conn_id, topic)
                    await websocket.send_text(json.dumps({"ack": "subscribed", "topic": topic}))

            elif action == "unsubscribe":
                topic = msg.get("topic", "")
                if topic:
                    manager.unsubscribe(conn_id, topic)
                    await websocket.send_text(json.dumps({"ack": "unsubscribed", "topic": topic}))

            elif action == "ping":
                await websocket.send_text(json.dumps({"pong": time.time()}))

            elif action in ("pause", "resume", "cancel"):
                mission_id = msg.get("mission_id", "")
                if mission_id:
                    # Emit command event for the orchestrator to pick up
                    try:
                        from ..events import get_event_store

                        get_event_store().emit_simple(
                            f"command_{action}",
                            "mission",
                            mission_id,
                            actor=f"ws:{conn_id}",
                        )
                    except Exception:
                        pass
                    await websocket.send_text(
                        json.dumps({"ack": action, "mission_id": mission_id})
                    )
            else:
                await websocket.send_text(json.dumps({"error": f"Unknown action: {action}"}))

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception:
        manager.disconnect(conn_id)


@router.get("/api/ws/stats")
async def ws_stats():
    """WebSocket connection statistics."""
    return manager.stats
