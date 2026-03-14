"""API routes for traceability — why_log query endpoints."""
# Ref: feat-annotate

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ....traceability.store import get_session_why, get_why

router = APIRouter()


@router.get("/api/traceability")
async def get_artifact_why(artifact: str = "") -> JSONResponse:
    """Get why-chain for an artifact ref (filename, story id, etc.)."""
    if not artifact:
        return JSONResponse({"error": "artifact param required"}, status_code=400)
    entries = get_why(artifact)
    return JSONResponse({
        "artifact": artifact,
        "why_chain": [
            {
                "artifact_type": e.artifact_type,
                "lineage_chain": e.lineage_chain,
                "rationale": e.rationale,
                "created_at": e.created_at,
            }
            for e in entries
        ],
    })


@router.get("/api/traceability/{session_id}")
async def get_session_traceability(session_id: str) -> JSONResponse:
    """Get full why-chain for all artifacts produced in a session."""
    entries = get_session_why(session_id)
    by_type: dict[str, list] = {}
    for e in entries:
        by_type.setdefault(e.artifact_type, []).append({
            "artifact_ref": e.artifact_ref,
            "lineage_chain": e.lineage_chain,
            "rationale": e.rationale,
            "created_at": e.created_at,
        })
    return JSONResponse({
        "session_id": session_id,
        "artifacts": by_type,
        "total": len(entries),
    })
