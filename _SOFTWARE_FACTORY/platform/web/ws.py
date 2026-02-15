"""SSE (Server-Sent Events) handlers for real-time updates.

Provides live streaming of:
- Agent messages (A2A bus) per session
- Agent status changes
- Monitoring metrics
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _sse_stream(queue: asyncio.Queue, request: Request):
    """Generic SSE generator from an asyncio queue."""
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                payload = json.dumps(data) if isinstance(data, dict) else str(data)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/session/{session_id}")
async def sse_session(request: Request, session_id: str):
    """Stream ALL events for a session: messages, status changes, tool calls."""
    from ..a2a.bus import get_bus
    bus = get_bus()
    queue = bus.add_sse_listener()

    async def filtered_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Filter to this session only
                    sid = getattr(msg, "session_id", "") if not isinstance(msg, dict) else msg.get("session_id", "")
                    if sid != session_id:
                        continue
                    # Build SSE payload
                    if hasattr(msg, "message_type"):
                        # A2AMessage object
                        mt = msg.message_type.value if hasattr(msg.message_type, "value") else str(msg.message_type)
                        is_status = mt == "system" and msg.metadata.get("event") == "status_change"
                        payload = {
                            "type": "status" if is_status else "message",
                            "id": msg.id,
                            "from_agent": msg.from_agent,
                            "to_agent": msg.to_agent,
                            "msg_type": mt,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, "isoformat") else str(msg.timestamp),
                            "metadata": msg.metadata,
                        }
                    else:
                        payload = msg if isinstance(msg, dict) else {"type": "raw", "content": str(msg)}
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            bus.remove_sse_listener(queue)

    return StreamingResponse(
        filtered_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/agents/status")
async def sse_agent_status(request: Request):
    """Stream agent loop statuses."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    async def poll_status():
        from ..agents.loop import get_loop_manager
        mgr = get_loop_manager()
        last_snapshot = {}
        while not await request.is_disconnected():
            snapshot = mgr.get_all_statuses()
            if snapshot != last_snapshot:
                for key, info in snapshot.items():
                    await queue.put({"type": "agent_status", **info})
                last_snapshot = dict(snapshot)
            await asyncio.sleep(2)

    task = asyncio.create_task(poll_status())

    async def stream():
        try:
            async for chunk in _sse_stream(queue, request):
                yield chunk
        finally:
            task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/monitoring")
async def sse_monitoring(request: Request):
    """Stream platform metrics."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    async def poll_metrics():
        from ..a2a.bus import get_bus
        from ..agents.loop import get_loop_manager
        bus = get_bus()
        mgr = get_loop_manager()
        while not await request.is_disconnected():
            bus_stats = bus.get_stats()
            loops = mgr.get_all_statuses()
            active = sum(1 for v in loops.values() if v.get("status") not in ("idle", "stopped"))
            await queue.put({
                "type": "metrics",
                "agents_active": active,
                "agents_total": len(loops),
                "messages_total": bus_stats.get("published", 0),
                "dead_letters": bus_stats.get("dead_letter_count", 0),
            })
            await asyncio.sleep(5)

    task = asyncio.create_task(poll_metrics())

    async def stream():
        try:
            async for chunk in _sse_stream(queue, request):
                yield chunk
        finally:
            task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
