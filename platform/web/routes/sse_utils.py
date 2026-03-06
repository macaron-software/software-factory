"""Shared SSE (Server-Sent Events) utilities for route handlers.

Rationale: the `sse()` formatter was duplicated in cto.py, projects.py, and
epics/execution.py with identical bodies. Centralised here to avoid drift.
Pattern: SSE frame = "event: <name>\ndata: <json>\n\n"
"""

from __future__ import annotations

import json

from fastapi.responses import StreamingResponse


def sse(event: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_stream(generator) -> StreamingResponse:
    """Wrap an async generator in a StreamingResponse with SSE media type."""
    return StreamingResponse(generator, media_type="text/event-stream")
