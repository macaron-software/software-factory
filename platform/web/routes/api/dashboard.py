"""Dashboard KPIs, quality, sprints, backlog & activity feed endpoints."""

from __future__ import annotations

import html as html_mod
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...schemas import FeatureOut
from ..helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/dashboard/kpis")
async def dashboard_kpis(request: Request, perspective: str = "admin"):
    """KPI cards adapted to perspective."""
    from ....agents.store import get_agent_store
    from ....missions.store import get_mission_run_store, get_mission_store
    from ....sessions.store import get_session_store

    mission_store = get_mission_store()
    run_store = get_mission_run_store()
    agent_store = get_agent_store()
    session_store = get_session_store()

    missions = mission_store.list_missions(limit=500)
    runs = run_store.list_runs(limit=500)
    agents = agent_store.list_all()
    sessions = session_store.list_all(limit=100)

    active_missions = sum(1 for m in missions if m.status in ("active", "running"))
    total_epics = len(missions)
    active_agents = len(agents)
    active_sessions = sum(1 for s in sessions if s.status in ("active", "running"))

    # Compute completion rate
    completed = sum(1 for m in missions if m.status in ("completed", "done"))
    completion_rate = int(completed / total_epics * 100) if total_epics > 0 else 0

    # KPIs vary by perspective
    cards = []
    if perspective in (
        "overview",
        "dsi",
        "portfolio_manager",
        "business_owner",
        "admin",
    ):
        cards = [
            {"value": str(total_epics), "label": "Total Epics"},
            {"value": str(active_missions), "label": "Active Missions"},
            {"value": f"{completion_rate}%", "label": "Completion Rate"},
            {"value": str(active_agents), "label": "Agents"},
        ]
    elif perspective in ("rte", "scrum_master"):
        sprints_active = sum(
            1
            for r in runs
            if r.status
            and str(getattr(r.status, "value", r.status)) in ("running", "active")
        )
        cards = [
            {"value": str(active_missions), "label": "Active Missions"},
            {"value": str(sprints_active), "label": "Running Sprints"},
            {"value": str(active_sessions), "label": "Live Sessions"},
            {"value": str(active_agents), "label": "Agents"},
        ]
    elif perspective in ("product_owner",):
        cards = [
            {"value": str(total_epics), "label": "Epics"},
            {"value": str(active_missions), "label": "In Progress"},
            {"value": f"{completion_rate}%", "label": "Done Rate"},
            {"value": str(active_sessions), "label": "Sessions"},
        ]
    elif perspective in ("developer", "architect"):
        from ....projects.manager import get_project_store

        projects = get_project_store().list_all()
        cards = [
            {"value": str(len(projects)), "label": "Projects"},
            {"value": str(active_sessions), "label": "Active Sessions"},
            {"value": str(active_missions), "label": "Missions"},
            {"value": str(active_agents), "label": "Agents"},
        ]
    elif perspective == "qa_security":
        cards = [
            {"value": str(active_missions), "label": "Missions"},
            {"value": str(active_sessions), "label": "Test Sessions"},
            {"value": f"{completion_rate}%", "label": "Pass Rate"},
            {"value": str(active_agents), "label": "Agents"},
        ]
    else:
        cards = [
            {"value": str(total_epics), "label": "Epics"},
            {"value": str(active_missions), "label": "Active"},
            {"value": str(active_sessions), "label": "Sessions"},
            {"value": str(active_agents), "label": "Agents"},
        ]

    html = ""
    for c in cards:
        html += f'<div class="kpi-card"><div class="kpi-value">{c["value"]}</div><div class="kpi-label">{c["label"]}</div></div>'
    return HTMLResponse(html)


@router.get("/api/dashboard/missions")
async def dashboard_missions(request: Request):
    """Active missions with progress bars."""
    from ....missions.store import get_mission_run_store, get_mission_store

    mission_store = get_mission_store()
    run_store = get_mission_run_store()
    missions = mission_store.list_missions(limit=50)
    runs = run_store.list_runs(limit=50)
    runs_map = {r.parent_mission_id: r for r in runs if r.parent_mission_id}

    html = ""
    active = [m for m in missions if m.status in ("active", "running")][:8]
    if not active:
        html = '<p class="text-muted">No active missions</p>'
    for m in active:
        run = runs_map.get(m.id)
        if run and run.phases:
            done = sum(
                1
                for ph in run.phases
                if ph.status.value in ("done", "done_with_issues")
            )
            total = len(run.phases)
            pct = int(done / total * 100) if total > 0 else 0
        else:
            pct = 0
        name = html_mod.escape(m.name[:40])
        html += f"""<div class="dash-mission">
            <div class="dash-mission-name">{name}</div>
            <div class="dash-mission-bar"><div class="dash-mission-fill" style="width:{pct}%"></div></div>
            <div class="dash-mission-pct">{pct}%</div>
        </div>"""
    return HTMLResponse(html)


@router.get("/api/dashboard/sprints")
async def dashboard_sprints(request: Request):
    """Active sprints summary."""
    from ....missions.store import get_mission_store

    store = get_mission_store()
    try:
        sprints = store.list_sprints(limit=10)
    except Exception:
        sprints = []

    active = [s for s in sprints if getattr(s, "status", "") in ("active", "planning")][
        :5
    ]
    if not active:
        return HTMLResponse('<p class="text-muted">No active sprints</p>')

    html = ""
    for s in active:
        name = html_mod.escape(getattr(s, "name", "Sprint")[:30])
        vel = getattr(s, "velocity", 0) or 0
        planned = getattr(s, "planned_sp", 0) or 0
        pct = int(vel / planned * 100) if planned > 0 else 0
        html += f"""<div class="dash-stat">
            <span class="dash-stat-label">{name}</span>
            <span class="dash-stat-value">{vel}/{planned} SP ({pct}%)</span>
        </div>"""
    return HTMLResponse(html)


@router.get("/api/dashboard/backlog")
async def dashboard_backlog(request: Request):
    """Backlog stats for PO."""
    from ....missions.store import get_mission_store

    store = get_mission_store()
    try:
        features = store.list_features(limit=100)
    except Exception:
        features = []

    try:
        stories = store.list_user_stories(limit=200)
    except Exception:
        stories = []

    html = f"""<div class="dash-stat"><span class="dash-stat-label">Features</span><span class="dash-stat-value">{len(features)}</span></div>
    <div class="dash-stat"><span class="dash-stat-label">User Stories</span><span class="dash-stat-value">{len(stories)}</span></div>"""
    return HTMLResponse(html)


@router.get("/api/dashboard/projects")
async def dashboard_projects(request: Request):
    """Projects list for dev."""
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()[:8]
    if not projects:
        return HTMLResponse('<p class="text-muted">No projects</p>')

    html = ""
    for p in projects:
        name = html_mod.escape(p.name[:30])
        ftype = html_mod.escape((p.factory_type or "")[:20])
        html += f"""<div class="dash-stat">
            <a href="/projects/{p.id}" class="dash-stat-label" style="color:var(--text-primary);text-decoration:none">{name}</a>
            <span class="dash-stat-value" style="font-size:0.75rem;color:var(--text-secondary)">{ftype}</span>
        </div>"""
    return HTMLResponse(html)


@router.get("/api/dashboard/quality")
async def dashboard_quality(request: Request):
    """Quality metrics summary for dashboard."""
    from ....metrics.quality import QualityScanner

    scores = QualityScanner.get_all_projects_scores()
    if not scores:
        return HTMLResponse("""<div class="dash-stat"><span class="dash-stat-label">Quality Score</span><span class="dash-stat-value">--</span></div>
        <div class="dash-stat"><span class="dash-stat-label">Projects Scanned</span><span class="dash-stat-value">0</span></div>
        <div class="dash-stat"><span class="dash-stat-label">Run quality_scan to start</span><span class="dash-stat-value"></span></div>""")

    avg_score = sum(s["global_score"] for s in scores) / len(scores) if scores else 0
    low_count = sum(1 for s in scores if s["global_score"] < 60)
    color = (
        "#16a34a" if avg_score >= 80 else "#ea580c" if avg_score >= 60 else "#dc2626"
    )

    html = f"""<div class="dash-stat">
        <span class="dash-stat-label">Avg Quality</span>
        <span class="dash-stat-value" style="color:{color}">{avg_score:.0f}/100</span>
    </div>
    <div class="dash-stat">
        <span class="dash-stat-label">Projects Scanned</span>
        <span class="dash-stat-value">{len(scores)}</span>
    </div>
    <div class="dash-stat">
        <span class="dash-stat-label">Below Threshold</span>
        <span class="dash-stat-value" style="color:{"#dc2626" if low_count else "var(--text-secondary)"}">{low_count}</span>
    </div>"""
    return HTMLResponse(html)


@router.get("/api/quality/{project_id}")
async def api_quality_project(request: Request, project_id: str):
    """Get quality scorecard for a project."""
    from ....metrics.quality import QualityScanner

    snapshot = QualityScanner.get_latest_snapshot(project_id)
    trend = QualityScanner.get_trend(project_id, limit=20)
    return {"snapshot": snapshot, "trend": trend}


@router.get("/api/quality")
async def api_quality_all(request: Request):
    """Get quality scores for all projects."""
    from ....metrics.quality import QualityScanner

    return {"projects": QualityScanner.get_all_projects_scores()}


@router.get("/quality", response_class=HTMLResponse)
async def quality_dashboard_page(request: Request):
    """Quality Scorecard dashboard page."""
    from ....metrics.quality import QualityScanner
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    project_id = request.query_params.get("project_id", "")

    snapshot = QualityScanner.get_latest_snapshot(project_id) if project_id else None
    trend = QualityScanner.get_trend(project_id) if project_id else []
    all_scores = QualityScanner.get_all_projects_scores()

    return _templates(request).TemplateResponse(
        "quality.html",
        {
            "request": request,
            "page_title": "Quality Scorecard",
            "projects": projects,
            "selected_project": project_id,
            "snapshot": snapshot,
            "trend": trend,
            "all_scores": all_scores,
        },
    )


@router.get("/api/dashboard/quality-badge")
async def dashboard_quality_badge(request: Request, project_id: str = ""):
    """Quality badge for project header — shows score as colored circle."""
    if not project_id:
        return HTMLResponse("")
    from ....metrics.quality import QualityScanner

    snapshot = QualityScanner.get_latest_snapshot(project_id)
    if not snapshot or not snapshot.get("global_score"):
        return HTMLResponse(
            '<span style="color:var(--text-tertiary); font-size:0.8rem;">No scan</span>'
        )

    score = snapshot["global_score"]
    color = (
        "#16a34a"
        if score >= 80
        else "#3b82f6"
        if score >= 60
        else "#ea580c"
        if score >= 40
        else "#dc2626"
    )
    return HTMLResponse(
        f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:0.85rem;">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{color};display:inline-block;"></span>'
        f'<strong style="color:{color}">{score:.0f}</strong>/100'
        f"</span>"
    )


@router.get("/api/dashboard/quality-mission")
async def dashboard_quality_mission(request: Request, project_id: str = ""):
    """Quality scorecard for mission detail sidebar."""
    if not project_id:
        return HTMLResponse('<p style="color:var(--text-tertiary)">No project</p>')
    from ....metrics.quality import QualityScanner

    snapshot = QualityScanner.get_latest_snapshot(project_id)
    if not snapshot or not snapshot.get("global_score"):
        return HTMLResponse(
            '<p style="color:var(--text-tertiary); font-size:0.85rem;">No quality scan yet</p>'
        )

    score = snapshot["global_score"]
    color = (
        "#16a34a"
        if score >= 80
        else "#3b82f6"
        if score >= 60
        else "#ea580c"
        if score >= 40
        else "#dc2626"
    )
    dims = snapshot.get("dimensions", {})

    html = '<div style="font-size:0.85rem;">'
    html += f'<div style="text-align:center;margin-bottom:8px;"><span style="font-size:1.5rem;font-weight:700;color:{color}">{score:.0f}</span><span style="color:var(--text-tertiary)">/100</span></div>'
    for dim_name, dim_val in list(dims.items())[:6]:
        dcolor = (
            "#16a34a"
            if dim_val >= 80
            else "#3b82f6"
            if dim_val >= 60
            else "#ea580c"
            if dim_val >= 40
            else "#dc2626"
        )
        label = dim_name.replace("_", " ").title()
        html += f'<div style="display:flex;justify-content:space-between;margin:2px 0;"><span>{label}</span><span style="color:{dcolor};font-weight:600">{dim_val:.0f}</span></div>'
    html += "</div>"
    return HTMLResponse(html)


@router.get("/api/dashboard/activity")
async def dashboard_activity_feed(request: Request):
    """Recent activity feed."""
    from ....sessions.store import get_session_store

    store = get_session_store()
    sessions = store.list_all(limit=10)
    recent = sorted(sessions, key=lambda s: s.created_at or "", reverse=True)[:6]

    if not recent:
        return HTMLResponse('<p class="text-muted">No recent activity</p>')

    html = ""
    for s in recent:
        ts = (s.created_at or "")[:16].replace("T", " ")[-5:]  # HH:MM
        name = html_mod.escape((s.name or "Session")[:35])
        status = getattr(s, "status", "")
        badge = "var(--purple)" if status == "active" else "var(--text-secondary)"
        html += f"""<div class="dash-activity-item">
            <span class="dash-activity-time">{ts}</span>
            <span class="dash-activity-text">{name}</span>
        </div>"""
    return HTMLResponse(html)
