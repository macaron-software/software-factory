"""RBAC & permission endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/rbac/agent/{agent_id}")
async def rbac_agent_permissions(agent_id: str):
    """Get RBAC permissions for an agent."""
    from ....rbac import agent_permissions_summary, get_agent_category

    return JSONResponse(
        {
            "agent_id": agent_id,
            "category": get_agent_category(agent_id),
            "permissions": agent_permissions_summary(agent_id),
        }
    )


@router.get("/api/rbac/check")
async def rbac_check(request: Request):
    """Check a specific permission. Query: ?actor=agent_id&type=agent&artifact=code&action=create"""
    from ....rbac import check_agent_permission, check_human_permission

    actor = request.query_params.get("actor", "")
    actor_type = request.query_params.get("type", "agent")
    artifact = request.query_params.get("artifact", "")
    action = request.query_params.get("action", "")

    if actor_type == "agent":
        ok, reason = check_agent_permission(actor, artifact, action)
    else:
        ok, reason = check_human_permission(actor, artifact, action)

    return JSONResponse({"allowed": ok, "reason": reason})


@router.get("/api/permissions/denials")
async def permission_denials(limit: int = 50, agent_id: str = ""):
    """Recent permission denials (audit log)."""
    from ....agents.permissions import get_permission_guard

    return JSONResponse(
        get_permission_guard().recent_denials(limit=limit, agent_id=agent_id)
    )


@router.get("/api/permissions/stats")
async def permission_stats():
    """Permission denial statistics."""
    from ....agents.permissions import get_permission_guard

    return JSONResponse(get_permission_guard().denial_stats())
