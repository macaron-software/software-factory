"""Web routes — Agent Marketplace."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/marketplace", response_class=HTMLResponse)
async def marketplace_page(request: Request):
    """Agent Marketplace — browse all agents."""
    return _templates(request).TemplateResponse(
        "marketplace.html",
        {
            "request": request,
            "page_title": "Marketplace",
        },
    )


@router.get("/api/marketplace/agents")
async def api_marketplace_agents(
    request: Request,
    art: str = "",
    role: str = "",
    search: str = "",
):
    """List agents with optional filters."""
    from ...agents.store import get_agent_store

    agents = get_agent_store().list_all()
    result = []
    for a in agents:
        if role and a.role != role:
            continue
        if (
            art
            and "art" not in " ".join(a.tags).lower()
            and art.lower() not in " ".join(a.tags).lower()
        ):
            continue
        if search:
            q = search.lower()
            if (
                q not in a.name.lower()
                and q not in a.description.lower()
                and not any(q in t.lower() for t in a.tags)
            ):
                continue
        result.append(
            {
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "description": a.description,
                "tagline": a.tagline,
                "icon": a.icon,
                "color": a.color,
                "avatar": a.avatar,
                "skills": a.skills[:3],
                "tools": a.tools,
                "tags": a.tags,
                "is_builtin": a.is_builtin,
            }
        )
    return JSONResponse(result)


@router.get("/api/marketplace/agents/{agent_id}")
async def api_marketplace_agent_detail(agent_id: str):
    """Return full agent detail."""
    from ...agents.store import get_agent_store

    agent = get_agent_store().get(agent_id)
    if not agent:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(
        {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "description": agent.description,
            "tagline": agent.tagline,
            "icon": agent.icon,
            "color": agent.color,
            "avatar": agent.avatar,
            "skills": agent.skills,
            "tools": agent.tools,
            "mcps": agent.mcps,
            "tags": agent.tags,
            "provider": agent.provider,
            "model": agent.model,
            "is_builtin": agent.is_builtin,
            "persona": getattr(agent, "persona", ""),
            "motivation": getattr(agent, "motivation", ""),
        }
    )
