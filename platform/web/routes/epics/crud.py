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


@router.get("/epics", response_class=HTMLResponse)
@router.get("/missions", response_class=HTMLResponse)
async def missions_page(request: Request):
    """List all missions — shell with skeleton; grid loaded via HTMX."""
    from ....projects.manager import get_project_store

    project_store = get_project_store()

    filter_status = request.query_params.get("status")
    filter_project = request.query_params.get("project")
    show_new = request.query_params.get("action") == "new"

    all_projects = project_store.list_all()
    project_ids = [p.id for p in all_projects]

    from ....workflows.store import get_workflow_store

    all_workflows = get_workflow_store().list_all()

    # Grid loaded via HTMX deferred skeleton
    return _templates(request).TemplateResponse(
        "missions.html",
        {
            "request": request,
            "page_title": "PI Board",
            "project_ids": project_ids,
            "filter_status": filter_status,
            "filter_project": filter_project,
            "show_new_form": show_new,
            "workflows": all_workflows,
        },
    )


@router.get("/epics/{epic_id}", response_class=HTMLResponse)
@router.get("/missions/{epic_id}", response_class=HTMLResponse)
async def mission_detail_page(request: Request, epic_id: str):
    """Mission cockpit — sprints, board, team."""
    from ....agents.store import get_agent_store
    from ....epics.store import get_epic_store
    from ....projects.manager import get_project_store

    epic_store = get_epic_store()
    mission = epic_store.get_mission(epic_id)
    if not mission:
        return RedirectResponse("/missions", status_code=303)

    project = get_project_store().get(mission.project_id)
    sprints = epic_store.list_sprints(epic_id)
    stats = epic_store.mission_stats(epic_id)

    # Selected sprint (from query or active or last)
    sel_id = request.query_params.get("sprint")
    selected_sprint = None
    if sel_id:
        selected_sprint = epic_store.get_sprint(sel_id)
    if not selected_sprint:
        selected_sprint = next((s for s in sprints if s.status == "active"), None)
    if not selected_sprint and sprints:
        selected_sprint = sprints[-1]

    # Tasks by status for kanban
    tasks_by_status = {}
    if selected_sprint:
        tasks = epic_store.list_tasks(sprint_id=selected_sprint.id)
        for t in tasks:
            col = (
                t.status
                if t.status in ("pending", "in_progress", "review", "done")
                else "pending"
            )
            tasks_by_status.setdefault(col, []).append(t)

    # Velocity history (live from DB)
    velocity_history = epic_store.get_velocity_history(epic_id)
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

    # Features linked to this epic (SAFe: Epic → Features → Stories)
    from ....missions.product import ProductBacklog

    backlog = ProductBacklog()
    epic_features = backlog.list_features(epic_id)
    epic_stories = {}
    for feat in epic_features:
        epic_stories[feat.id] = backlog.list_stories(feat.id)

    return _templates(request).TemplateResponse(
        "mission_detail.html",
        {
            "request": request,
            "page_title": "Epic",
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
            "epic_features": epic_features,
            "epic_stories": epic_stories,
        },
    )


@router.post("/api/missions", responses={200: {"model": OkResponse}})
async def create_mission(request: Request):
    """Create a new mission."""
    from fastapi import HTTPException

    from ....epics.store import MissionDef, get_epic_store

    data = await _parse_body(request)
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422, detail="Request body must be a JSON object"
        )

    # Validate field lengths to prevent abuse
    _MAX = 10_000
    for field in ("name", "title", "description", "goal"):
        val = data.get(field)
        if isinstance(val, str) and len(val) > _MAX:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field}' exceeds maximum length of {_MAX}",
            )

    try:
        wsjf = float(data.get("wsjf_score", 0))
    except (TypeError, ValueError):
        wsjf = 0.0

    m = MissionDef(
        project_id=data.get("project_id", ""),
        name=data.get(
            "name", t("mission_default_name", lang=getattr(request.state, "lang", "en"))
        ),
        description=data.get("description", ""),
        goal=data.get("goal", ""),
        type=data.get("type", "feature"),
        workflow_id=data.get("workflow_id", ""),
        wsjf_score=wsjf,
        created_by="user",
    )
    epic_store = get_epic_store()
    m = epic_store.create_mission(m)
    if _is_json_request(request):
        return JSONResponse({"ok": True, "mission": {"id": m.id, "name": m.name}})
    return RedirectResponse(f"/missions/{m.id}", status_code=303)


@router.get("/api/missions", responses={200: {"model": MissionListResponse}})
async def list_missions_api(request: Request):
    """JSON API: list all missions with run progress."""
    from ....epics.store import get_epic_run_store, get_epic_store

    epic_store = get_epic_store()
    run_store = get_epic_run_store()
    missions = epic_store.list_missions(limit=200)
    runs = run_store.list_runs(limit=200)
    runs_by_parent = {}
    for r in runs:
        if r.parent_epic_id:
            runs_by_parent[r.parent_epic_id] = r
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
    return JSONResponse({"epics": result, "total": len(result)})


@router.delete("/api/epics/{epic_id}", responses={200: {"model": OkResponse}})
@router.delete("/api/missions/{epic_id}", responses={200: {"model": OkResponse}})
async def delete_mission(epic_id: str):
    """Delete a mission (epic) and ALL its runs + associated data."""
    from ....db.migrations import get_db

    conn = get_db()
    mission = conn.execute(
        "SELECT id, name FROM epics WHERE id = ?", (epic_id,)
    ).fetchone()
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Delete all runs for this mission
    runs = conn.execute(
        "SELECT id, session_id FROM epic_runs WHERE parent_epic_id = ?",
        (epic_id,),
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
    conn.execute("DELETE FROM epic_runs WHERE parent_epic_id = ?", (epic_id,))
    # Delete features, stories, sprints, tasks linked to mission
    conn.execute(
        "DELETE FROM user_stories WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
        (epic_id,),
    )
    try:
        conn.execute(
            "DELETE FROM feature_deps WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
            (epic_id,),
        )
        conn.execute(
            "DELETE FROM feature_deps WHERE depends_on IN (SELECT id FROM features WHERE epic_id = ?)",
            (epic_id,),
        )
    except Exception:
        pass
    conn.execute("DELETE FROM features WHERE epic_id = ?", (epic_id,))
    conn.execute("DELETE FROM sprints WHERE mission_id = ?", (epic_id,))
    conn.execute("DELETE FROM tasks WHERE mission_id = ?", (epic_id,))
    try:
        conn.execute(
            "DELETE FROM ideation_findings WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
            (epic_id,),
        )
        conn.execute(
            "DELETE FROM ideation_messages WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
            (epic_id,),
        )
        conn.execute("DELETE FROM ideation_sessions WHERE mission_id = ?", (epic_id,))
    except Exception:
        pass
    conn.execute("DELETE FROM epics WHERE id = ?", (epic_id,))
    conn.commit()
    return JSONResponse({"status": "deleted", "name": mission[1]})


@router.get(
    "/api/missions/{epic_id}",
    responses={200: {"model": MissionDetail}, 404: {"model": ErrorResponse}},
)
async def api_mission_status(request: Request, epic_id: str):
    """Get mission status as JSON."""
    from ....epics.store import get_epic_run_store

    store = get_epic_run_store()
    mission = store.get(epic_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(mission.model_dump(mode="json"))


@router.get("/api/epics/{epic_id}/children")
@router.get("/api/missions/{epic_id}/children")
async def api_mission_children(request: Request, epic_id: str):
    """List sub-missions (Features) of a parent mission (Epic)."""
    from ....epics.store import get_epic_run_store, get_epic_store

    run_store = get_epic_run_store()
    epic_store = get_epic_store()
    # Get children from both stores
    run_children = run_store.list_children_runs(epic_id)
    def_children = epic_store.list_children(epic_id)
    return JSONResponse(
        {
            "parent_id": epic_id,
            "sub_epic_runs": [r.model_dump(mode="json") for r in run_children],
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


@router.get("/epics/start/{workflow_id}", response_class=HTMLResponse)
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
    from ....epics.store import get_epic_run_store
    from ....projects.manager import get_project_store
    from ....workflows.store import get_workflow_store

    store = get_epic_run_store()
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


@router.get("/epics/{epic_id}/control", response_class=HTMLResponse)
@router.get("/missions/{epic_id}/control", response_class=HTMLResponse)
async def mission_control_page(request: Request, epic_id: str):
    """Mission Control dashboard — pipeline visualization + CDP activity."""
    from ....services.epic_context import EpicContextBuilder

    builder = EpicContextBuilder(epic_id)
    ctx = await builder.build_context()
    if ctx is None:
        return RedirectResponse("/pi", status_code=302)

    ctx["request"] = request
    return _templates(request).TemplateResponse("mission_control.html", ctx)


@router.get("/epics/{epic_id}/replay", response_class=HTMLResponse)
@router.get("/missions/{epic_id}/replay", response_class=HTMLResponse)
async def mission_replay_page(request: Request, epic_id: str):
    """Mission Replay — step-by-step timeline visualization."""
    return _templates(request).TemplateResponse(
        "mission_replay.html",
        {
            "request": request,
            "page_title": "Mission Replay",
            "mission_id": epic_id,
        },
    )
