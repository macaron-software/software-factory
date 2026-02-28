"""LLM Metrics routes — observability dashboard for LLM calls."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..routes.helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_tracer():
    from ...llm.observability import get_tracer

    return get_tracer()


@router.get("/metrics/tab/llm", response_class=HTMLResponse)
async def metrics_tab_llm(request: Request):
    """LLM metrics tab partial (HTMX)."""
    return _templates(request).TemplateResponse(
        "metrics.html",
        {"request": request},
    )


@router.get("/api/metrics/llm")
async def api_metrics_llm():
    """LLM stats — 24h and 7d windows."""
    tracer = _get_tracer()
    stats_24h = tracer.stats(hours=24)
    stats_7d = tracer.stats(hours=168)
    return JSONResponse({"h24": stats_24h, "h168": stats_7d})


@router.get("/api/metrics/llm/traces")
async def api_metrics_llm_traces(limit: int = 100, session_id: str = ""):
    """Recent LLM traces."""
    tracer = _get_tracer()
    return JSONResponse({"traces": tracer.recent(limit=limit, session_id=session_id)})


@router.get("/api/metrics/llm/top-agents")
async def api_metrics_llm_top_agents(hours: int = 168):
    """Top 10 agents by cost (last N hours)."""
    tracer = _get_tracer()
    stats = tracer.stats(hours=hours)
    top = sorted(
        stats.get("by_agent", []), key=lambda x: x.get("cost_usd", 0), reverse=True
    )[:10]
    return JSONResponse({"top_agents": top, "hours": hours})
