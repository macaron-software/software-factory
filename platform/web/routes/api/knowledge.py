"""Knowledge API — manual trigger + health check for knowledge management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

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
async def knowledge_health(request: Request):
    """Return memory health stats. Returns HTML fragment when called via HTMX, JSON otherwise."""
    from ...memory.compactor import get_memory_health

    health = get_memory_health()
    proj = health.get("project", {})
    glob = health.get("global", {})

    # Last knowledge-maintenance run
    last_run = None
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
        pass

    # Return HTML badge fragment for HTMX requests
    if request.headers.get("hx-request"):
        total = proj.get("total", 0)
        avg_rel = float(proj.get("avg_relevance") or 0)
        stale = proj.get("stale", 0)
        low_rel = proj.get("low_relevance", 0)
        glob_total = glob.get("total", 0)

        rel_color = (
            "var(--green)"
            if avg_rel >= 0.6
            else ("var(--yellow)" if avg_rel >= 0.3 else "var(--red)")
        )
        stale_color = (
            "var(--red)"
            if stale > 20
            else ("var(--yellow)" if stale > 5 else "var(--green)")
        )

        if last_run:
            run_status = last_run["status"] or "?"
            run_color = (
                "var(--green)"
                if run_status == "completed"
                else ("var(--red)" if run_status == "failed" else "var(--yellow)")
            )
            run_html = f'<span style="color:{run_color};font-weight:600;font-size:0.8rem">{run_status.upper()}</span>'
        else:
            run_html = '<span style="color:var(--text-secondary);font-size:0.8rem">Never run</span>'

        html = f"""<div style="display:flex;flex-wrap:wrap;gap:0.6rem;align-items:center">
  <span style="background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:0.3rem 0.7rem;font-size:0.78rem">
    <strong>{total}</strong> <span style="color:var(--text-secondary)">project</span>
  </span>
  <span style="background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:0.3rem 0.7rem;font-size:0.78rem">
    <strong>{glob_total}</strong> <span style="color:var(--text-secondary)">global</span>
  </span>
  <span style="background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:0.3rem 0.7rem;font-size:0.78rem">
    Relevance <strong style="color:{rel_color}">{avg_rel:.2f}</strong>
  </span>
  <span style="background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;padding:0.3rem 0.7rem;font-size:0.78rem">
    <span style="color:{stale_color}">{stale}</span> <span style="color:var(--text-secondary)">stale</span> · {low_rel} low-rel
  </span>
  <span style="font-size:0.78rem;color:var(--text-secondary)">Last run: {run_html}</span>
</div>"""
        return HTMLResponse(content=html)

    return {
        "memory": health,
        "last_run": last_run,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
