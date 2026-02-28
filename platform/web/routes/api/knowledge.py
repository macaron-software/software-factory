"""Knowledge API — manual trigger + health check for knowledge management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/refresh")
async def knowledge_refresh(project_id: str | None = None):
    """Manually trigger a knowledge-maintenance mission."""
    from ...ops.knowledge_scheduler import run_knowledge_maintenance

    mission_id = await run_knowledge_maintenance(project_id=project_id)
    if mission_id:
        return {"status": "started", "mission_id": mission_id, "project_id": project_id}
    return {"status": "no_projects", "mission_id": None}


@router.get("/health")
async def knowledge_health():
    """Return memory health stats for the knowledge dashboard."""
    from ...memory.compactor import get_memory_health

    health = get_memory_health()

    # Last knowledge-maintenance run
    try:
        from ...db.migrations import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT mr.id, mr.status, mr.completed_at, mr.llm_cost_usd "
            "FROM mission_runs mr "
            "JOIN missions m ON mr.mission_id = m.id "
            "WHERE m.workflow_id = 'knowledge-maintenance' "
            "ORDER BY mr.started_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        last_run = dict(row) if row else None
    except Exception:
        last_run = None

    return {
        "memory": health,
        "last_run": last_run,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
