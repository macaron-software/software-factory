"""Traceability routes — why_log + ac_items query API."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/traceability/artifact/{artifact_ref:path}")
async def api_trace_artifact(artifact_ref: str):
    """Get why_log lineage chain for an artifact reference (filename, phase id, etc.)."""
    try:
        from ...traceability.store import get_why
        entries = get_why(artifact_ref)
        return JSONResponse({
            "artifact_ref": artifact_ref,
            "entries": [
                {
                    "id": e.id,
                    "session_id": e.session_id,
                    "artifact_type": e.artifact_type,
                    "lineage_chain": e.lineage_chain,
                    "lineage": e.lineage,
                    "rationale": e.rationale,
                    "created_at": e.created_at,
                }
                for e in entries
            ],
        })
    except Exception as e:
        logger.error("traceability artifact query error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/traceability/session/{session_id}")
async def api_trace_session(session_id: str):
    """Get full why_log chain for all artifacts produced in a PACMAN session."""
    try:
        from ...traceability.store import get_session_why
        entries = get_session_why(session_id)
        return JSONResponse({
            "session_id": session_id,
            "count": len(entries),
            "chain": [
                {
                    "artifact_type": e.artifact_type,
                    "artifact_ref": e.artifact_ref,
                    "lineage_chain": e.lineage_chain,
                    "rationale": e.rationale,
                    "created_at": e.created_at,
                }
                for e in entries
            ],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/traceability/ac/{ac_id}")
async def api_trace_ac_item(ac_id: str):
    """Get a single AC item with its full traceability data."""
    try:
        from ...epics.ac_items import get_ac_item
        from ...traceability.store import get_why
        item = get_ac_item(ac_id)
        if not item:
            return JSONResponse({"error": f"AC item {ac_id!r} not found"}, status_code=404)
        # Also get why_log entries linked to this AC
        why = get_why(ac_id)
        return JSONResponse({
            "id": item.id,
            "story_id": item.story_id,
            "feature_id": item.feature_id,
            "epic_id": item.epic_id,
            "project_id": item.project_id,
            "description": item.description,
            "verify_cmd": item.verify_cmd,
            "status": item.status,
            "session_id": item.session_id,
            "created_at": item.created_at,
            "verified_at": item.verified_at,
            "why_log": [e.lineage_chain for e in why],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/traceability/project/{project_id}")
async def api_trace_project(project_id: str):
    """Get all AC items for a project with pass/fail status summary."""
    try:
        from ...epics.ac_items import list_ac_items, ac_summary
        items = list_ac_items(project_id=project_id)
        summary = ac_summary(project_id=project_id)
        return JSONResponse({
            "project_id": project_id,
            "summary": summary,
            "ac_items": [
                {
                    "id": i.id,
                    "story_id": i.story_id,
                    "description": i.description,
                    "verify_cmd": i.verify_cmd,
                    "status": i.status,
                    "verified_at": i.verified_at,
                }
                for i in items
            ],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
