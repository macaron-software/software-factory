"""Mission CRUD routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ....i18n import t
from ...schemas import (
    ErrorResponse,
    MissionDetail,
    MissionListResponse,
    OkResponse,
)
from ..helpers import _is_json_request, _parse_body, _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/missions", response_class=HTMLResponse)
async def missions_page(request: Request):
    """List all missions with filters."""
    from ....missions.store import get_mission_store
    from ....projects.manager import get_project_store

    mission_store = get_mission_store()
    project_store = get_project_store()

    filter_status = request.query_params.get("status")
    filter_project = request.query_params.get("project")
    show_new = request.query_params.get("action") == "new"

    all_missions = mission_store.list_missions()
    all_projects = project_store.list_all()
    project_ids = [p.id for p in all_projects]
    project_names = {p.id: p.name for p in all_projects}

    # Apply filters
    filtered = all_missions
    if filter_status:
        filtered = [m for m in filtered if m.status == filter_status]
    if filter_project:
        filtered = [m for m in filtered if m.project_id == filter_project]

    # Enrich with stats
    mission_cards = []
    for m in filtered:
        stats = mission_store.mission_stats(m.id)
        sprints = mission_store.list_sprints(m.id)
        current = next(
            (s.number for s in sprints if s.status == "active"), len(sprints)
        )
        total_t = stats.get("total", 0)
        done_t = stats.get("done", 0)
        mission_cards.append(
            {
                "mission": m,
                "project_name": project_names.get(m.project_id, m.project_id),
                "sprint_count": len(sprints),
                "current_sprint": current,
                "total_tasks": total_t,
                "done_tasks": done_t,
                "progress_pct": round(done_t / total_t * 100) if total_t > 0 else 0,
            }
        )

    from ....workflows.store import get_workflow_store

    all_workflows = get_workflow_store().list_all()

    return _templates(request).TemplateResponse(
        "missions.html",
        {
            "request": request,
            "page_title": "PI Board",
            "missions": mission_cards,
            "project_ids": project_ids,
            "filter_status": filter_status,
            "filter_project": filter_project,
            "show_new_form": show_new,
            "workflows": all_workflows,
        },
    )


@router.get("/missions/{mission_id}", response_class=HTMLResponse)
async def mission_detail_page(request: Request, mission_id: str):
    """Mission cockpit — sprints, board, team."""
    from ....agents.store import get_agent_store
    from ....missions.store import get_mission_store
    from ....projects.manager import get_project_store

    mission_store = get_mission_store()
    mission = mission_store.get_mission(mission_id)
    if not mission:
        return RedirectResponse("/missions", status_code=303)

    project = get_project_store().get(mission.project_id)
    sprints = mission_store.list_sprints(mission_id)
    stats = mission_store.mission_stats(mission_id)

    # Selected sprint (from query or active or last)
    sel_id = request.query_params.get("sprint")
    selected_sprint = None
    if sel_id:
        selected_sprint = mission_store.get_sprint(sel_id)
    if not selected_sprint:
        selected_sprint = next((s for s in sprints if s.status == "active"), None)
    if not selected_sprint and sprints:
        selected_sprint = sprints[-1]

    # Tasks by status for kanban
    tasks_by_status = {}
    if selected_sprint:
        tasks = mission_store.list_tasks(sprint_id=selected_sprint.id)
        for t in tasks:
            col = (
                t.status
                if t.status in ("pending", "in_progress", "review", "done")
                else "pending"
            )
            tasks_by_status.setdefault(col, []).append(t)

    # Velocity history (live from DB)
    velocity_history = mission_store.get_velocity_history(mission_id)
    total_velocity = sum(v["velocity"] for v in velocity_history)
    total_planned = sum(v["planned_sp"] for v in velocity_history)
    avg_velocity = (
        round(total_velocity / len(velocity_history), 1) if velocity_history else 0
    )

    # Team agents
    agent_store = get_agent_store()
    prefix = (
        mission.project_id[:4] if len(mission.project_id) >= 4 else mission.project_id
    )
    all_agents = agent_store.list_all()
    team_agents = [
        a
        for a in all_agents
        if a.id.startswith(prefix + "-") or a.id.startswith(mission.project_id + "-")
    ]

    return _templates(request).TemplateResponse(
        "mission_detail.html",
        {
            "request": request,
            "page_title": "PI",
            "mission": mission,
            "project": project,
            "sprints": sprints,
            "stats": stats,
            "selected_sprint": selected_sprint,
            "tasks_by_status": tasks_by_status,
            "team_agents": team_agents,
            "velocity_history": velocity_history,
            "total_velocity": total_velocity,
            "total_planned": total_planned,
            "avg_velocity": avg_velocity,
        },
    )


@router.post("/api/missions", responses={200: {"model": OkResponse}})
async def create_mission(request: Request):
    """Create a new mission."""
    from ....missions.store import MissionDef, get_mission_store

    data = await _parse_body(request)
    m = MissionDef(
        project_id=data.get("project_id", ""),
        name=data.get(
            "name", t("mission_default_name", lang=getattr(request.state, "lang", "en"))
        ),
        description=data.get("description", ""),
        goal=data.get("goal", ""),
        type=data.get("type", "feature"),
        workflow_id=data.get("workflow_id", ""),
        wsjf_score=float(data.get("wsjf_score", 0)),
        created_by="user",
    )
    mission_store = get_mission_store()
    m = mission_store.create_mission(m)
    if _is_json_request(request):
        return JSONResponse({"ok": True, "mission": {"id": m.id, "name": m.name}})
    return RedirectResponse(f"/missions/{m.id}", status_code=303)


@router.get("/api/missions", responses={200: {"model": MissionListResponse}})
async def list_missions_api(request: Request):
    """JSON API: list all missions with run progress."""
    from ....missions.store import get_mission_run_store, get_mission_store

    mission_store = get_mission_store()
    run_store = get_mission_run_store()
    missions = mission_store.list_missions(limit=200)
    runs = run_store.list_runs(limit=200)
    runs_by_parent = {}
    for r in runs:
        if r.parent_mission_id:
            runs_by_parent[r.parent_mission_id] = r
        runs_by_parent[r.id] = r
    result = []
    for m in missions:
        run = runs_by_parent.get(m.id)
        phases_total = len(run.phases) if run and run.phases else 0
        phases_done = (
            sum(
                1
                for p in (run.phases or [])
                if p.status.value in ("done", "done_with_issues")
            )
            if run
            else 0
        )
        result.append(
            {
                "id": m.id,
                "name": m.name,
                "status": m.status,
                "type": m.type,
                "project_id": m.project_id,
                "phases_total": phases_total,
                "phases_done": phases_done,
                "current_phase": run.current_phase if run else "",
                "run_status": run.status.value if run else "",
            }
        )
    return JSONResponse({"missions": result, "total": len(result)})


@router.delete("/api/missions/{mission_id}", responses={200: {"model": OkResponse}})
async def delete_mission(mission_id: str):
    """Delete a mission (epic) and ALL its runs + associated data."""
    from ....db.migrations import get_db

    conn = get_db()
    mission = conn.execute(
        "SELECT id, name FROM missions WHERE id = ?", (mission_id,)
    ).fetchone()
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Delete all runs for this mission
    runs = conn.execute(
        "SELECT id, session_id FROM mission_runs WHERE parent_mission_id = ?",
        (mission_id,),
    ).fetchall()
    for run_id, session_id in runs:
        if session_id:
            conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM sprints WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM tasks WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM confluence_pages WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM llm_traces WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM llm_usage WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM platform_incidents WHERE mission_id = ?", (run_id,))
        conn.execute("DELETE FROM support_tickets WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_runs WHERE parent_mission_id = ?", (mission_id,))
    # Delete features, stories, sprints, tasks linked to mission
    conn.execute(
        "DELETE FROM user_stories WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
        (mission_id,),
    )
    try:
        conn.execute(
            "DELETE FROM feature_deps WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
            (mission_id,),
        )
        conn.execute(
            "DELETE FROM feature_deps WHERE depends_on IN (SELECT id FROM features WHERE epic_id = ?)",
            (mission_id,),
        )
    except Exception:
        pass
    conn.execute("DELETE FROM features WHERE epic_id = ?", (mission_id,))
    conn.execute("DELETE FROM sprints WHERE mission_id = ?", (mission_id,))
    conn.execute("DELETE FROM tasks WHERE mission_id = ?", (mission_id,))
    try:
        conn.execute(
            "DELETE FROM ideation_findings WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
            (mission_id,),
        )
        conn.execute(
            "DELETE FROM ideation_messages WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
            (mission_id,),
        )
        conn.execute(
            "DELETE FROM ideation_sessions WHERE mission_id = ?", (mission_id,)
        )
    except Exception:
        pass
    conn.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
    conn.commit()
    return JSONResponse({"status": "deleted", "name": mission[1]})


@router.get(
    "/api/missions/{mission_id}",
    responses={200: {"model": MissionDetail}, 404: {"model": ErrorResponse}},
)
async def api_mission_status(request: Request, mission_id: str):
    """Get mission status as JSON."""
    from ....missions.store import get_mission_run_store

    store = get_mission_run_store()
    mission = store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(mission.model_dump(mode="json"))


@router.get("/api/missions/{mission_id}/children")
async def api_mission_children(request: Request, mission_id: str):
    """List sub-missions (Features) of a parent mission (Epic)."""
    from ....missions.store import get_mission_run_store, get_mission_store

    run_store = get_mission_run_store()
    mission_store = get_mission_store()
    # Get children from both stores
    run_children = run_store.list_children_runs(mission_id)
    def_children = mission_store.list_children(mission_id)
    return JSONResponse(
        {
            "parent_id": mission_id,
            "sub_mission_runs": [r.model_dump(mode="json") for r in run_children],
            "sub_mission_defs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.type,
                    "status": c.status,
                    "wsjf_score": c.wsjf_score,
                    "workflow_id": c.workflow_id,
                }
                for c in def_children
            ],
        }
    )


@router.get("/missions/start/{workflow_id}", response_class=HTMLResponse)
async def mission_start_page(request: Request, workflow_id: str):
    """Start a new mission — show brief form."""
    from ....workflows.store import get_workflow_store

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return RedirectResponse("/pi", status_code=302)
    return _templates(request).TemplateResponse(
        "mission_start.html",
        {
            "request": request,
            "page_title": f"New Epic — {wf.name}",
            "workflow": wf,
        },
    )


@router.get("/mission-control", response_class=HTMLResponse)
async def missions_list_page(request: Request):
    """List all mission runs."""
    from ....missions.store import get_mission_run_store
    from ....projects.manager import get_project_store
    from ....workflows.store import get_workflow_store

    store = get_mission_run_store()
    runs = store.list_runs(limit=50)
    projects = get_project_store().list_all()
    workflows = get_workflow_store().list_all()
    return _templates(request).TemplateResponse(
        "mission_control_list.html",
        {
            "request": request,
            "page_title": "Epic Control",
            "runs": runs,
            "projects": projects,
            "workflows": workflows,
        },
    )


@router.get("/missions/{mission_id}/control", response_class=HTMLResponse)
async def mission_control_page(request: Request, mission_id: str):
    """Mission Control dashboard — pipeline visualization + CDP activity."""
    from ....services.mission_context import MissionContextBuilder

    builder = MissionContextBuilder(mission_id)
    ctx = await builder.build_context()
    if ctx is None:
        return RedirectResponse("/pi", status_code=302)

    ctx["request"] = request
    return _templates(request).TemplateResponse("mission_control.html", ctx)


@router.get("/missions/{mission_id}/replay", response_class=HTMLResponse)
async def mission_replay_page(request: Request, mission_id: str):
    """Mission Replay — step-by-step timeline visualization."""
    return _templates(request).TemplateResponse(
        "mission_replay.html",
        {
            "request": request,
            "page_title": "Mission Replay",
            "mission_id": mission_id,
        },
    )
