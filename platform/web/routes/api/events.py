"""Event store API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/events-stats")
async def events_stats():
    """Event store statistics."""
    from ....events import get_event_store
    return get_event_store().stats()


@router.get("/api/events/{aggregate_id}")
async def get_events(aggregate_id: str, event_type: str = "", limit: int = 100):
    """Get audit trail for a mission/project/agent."""
    from ....events import get_event_store
    store = get_event_store()
    events = store.query(
        aggregate_id=aggregate_id,
        event_type=event_type or None,
        limit=min(limit, 1000),
    )
    return [
        {
            "id": e.id,
            "type": e.event_type,
            "aggregate": e.aggregate_id,
            "actor": e.actor,
            "payload": e.payload,
            "timestamp": e.timestamp,
        }
        for e in events
    ]
