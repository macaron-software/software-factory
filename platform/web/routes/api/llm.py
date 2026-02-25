"""LLM observability endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...schemas import LlmStatsResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/llm/stats", responses={200: {"model": LlmStatsResponse}})
async def llm_stats(hours: int = 24, session_id: str = ""):
    """LLM usage statistics: calls, tokens, cost, by provider/agent."""
    from ....llm.observability import get_tracer

    return JSONResponse(get_tracer().stats(session_id=session_id, hours=hours))


@router.get("/api/llm/traces")
async def llm_traces(limit: int = 50, session_id: str = ""):
    """Recent LLM call traces."""
    from ....llm.observability import get_tracer

    return JSONResponse(get_tracer().recent(limit=limit, session_id=session_id))


@router.get("/api/llm/usage")
async def llm_usage_stats():
    """Get LLM usage aggregate (cost by day/phase/agent)."""
    try:
        from ....llm.client import get_llm_client

        client = get_llm_client()
        data = await client.aggregate_usage(days=7)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
