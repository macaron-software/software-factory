"""Web routes — HTMX-driven pages and API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _templates(request: Request):
    return request.app.state.templates


_AVATAR_DIR = Path(__file__).parent / "static" / "avatars"


def _avatar_url(agent_id: str) -> str:
    """Get avatar photo URL for an agent, or empty string."""
    jpg = _AVATAR_DIR / f"{agent_id}.jpg"
    if jpg.exists():
        return f"/static/avatars/{agent_id}.jpg"
    svg = _AVATAR_DIR / f"{agent_id}.svg"
    if svg.exists():
        return f"/static/avatars/{agent_id}.svg"
    return ""


def _agent_map_for_template(agents) -> dict:
    """Build agent_map dict suitable for msg_unified.html, including avatar_url."""
    m = {}
    for a in agents:
        if hasattr(a, 'id'):  # AgentDef dataclass
            m[a.id] = {
                "name": a.name, "icon": a.icon or "bot",
                "color": a.color or "#8b949e", "role": a.role or "",
                "avatar": getattr(a, "avatar", "") or "bot",
                "avatar_url": _avatar_url(a.id),
            }
        elif isinstance(a, dict):  # already a dict
            aid = a.get("id", "")
            m[aid] = {
                "name": a.get("name", ""), "icon": a.get("icon", "bot"),
                "color": a.get("color", "#8b949e"), "role": a.get("role", ""),
                "avatar": a.get("avatar", "bot"),
                "avatar_url": a.get("avatar_url", "") or _avatar_url(aid),
            }
    return m


# ── Pages ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio dashboard — tour de contrôle DSI."""
    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store
    from ..missions.store import get_mission_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    mission_store = get_mission_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = mission_store.list_missions()

    strategic_raw = [a for a in all_agents if any(t == 'strategy' for t in (a.tags or []))]
    avatar_dir = Path(__file__).parent / "static" / "avatars"
    strategic = []
    for a in strategic_raw:
        jpg = avatar_dir / f"{a.id}.jpg"
        svg = avatar_dir / f"{a.id}.svg"
        avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg.exists() else "")
        strategic.append({
            "id": a.id, "name": a.name, "role": a.role,
            "avatar": a.avatar or a.icon or "bot", "color": a.color or "#7c3aed",
            "avatar_url": avatar_url,
            "tagline": a.tagline or "", "persona": a.persona or "",
            "description": a.description or "",
            "motivation": a.motivation or "",
            "skills": a.skills or [], "tools": a.tools or [],
            "mcps": a.mcps or [],
            "model": getattr(a, "model", "") or "", "provider": getattr(a, "provider", "") or "",
        })

    # Build project cards with missions
    projects_data = []
    total_tasks = 0
    total_done = 0
    active_count = 0
    for p in all_projects:
        p_missions = [m for m in all_missions if m.project_id == p.id]
        p_agents = [a for a in all_agents
                    if a.id.startswith(p.id[:4] + '-') or a.id.startswith(p.id + '-')]
        team_avatars = [{"name": a.name, "icon": a.avatar or a.icon or "bot"} for a in p_agents[:8]]

        p_total = 0
        p_done = 0
        p_active = 0
        mission_cards = []
        for m in p_missions:
            stats = mission_store.mission_stats(m.id)
            t_total = stats.get("total", 0)
            t_done = stats.get("done", 0)
            p_total += t_total
            p_done += t_done
            if m.status == "active":
                p_active += 1
            progress = f"{t_done}/{t_total}" if t_total > 0 else ""
            mission_cards.append({"name": m.name, "status": m.status, "task_progress": progress})
        total_tasks += p_total
        total_done += p_done
        active_count += p_active

        projects_data.append({
            "id": p.id, "name": p.name, "factory_type": p.factory_type,
            "description": p.description or (p.vision or "")[:100],
            "missions": mission_cards, "mission_count": len(p_missions),
            "active_mission_count": p_active,
            "team_avatars": team_avatars,
            "total_tasks": p_total, "done_tasks": p_done,
        })

    # Build epics progression table
    epics_data = []
    for m in all_missions:
        stats = mission_store.mission_stats(m.id)
        t_total = stats.get("total", 0)
        t_done = stats.get("done", 0)
        pct = int(t_done / t_total * 100) if t_total > 0 else 0
        p = next((p for p in all_projects if p.id == m.project_id), None)
        epics_data.append({
            "id": m.id, "name": m.name, "status": m.status,
            "project_name": p.name if p else m.project_id or "—",
            "done": t_done, "total": t_total, "pct": pct,
            "wsjf": getattr(m, "wsjf", 0) or 0,
        })
    epics_data.sort(key=lambda e: e["pct"], reverse=True)

    # Load strategic committee graph from workflow
    strat_graph = {"nodes": [], "edges": []}
    try:
        from ..workflows.store import get_workflow_store
        wf_store = get_workflow_store()
        strat_wf = wf_store.get("strategic-committee")
        if strat_wf and strat_wf.config:
            sg = strat_wf.config.get("graph", {})
            if sg.get("nodes"):
                agent_map = {a.id: a for a in all_agents}
                for n in sg["nodes"]:
                    aid = n.get("agent_id", "")
                    a = agent_map.get(aid)
                    jpg = avatar_dir / f"{aid}.jpg"
                    svg_f = avatar_dir / f"{aid}.svg"
                    av_url = f"/static/avatars/{aid}.jpg" if jpg.exists() else (f"/static/avatars/{aid}.svg" if svg_f.exists() else "")
                    strat_graph["nodes"].append({
                        "id": n["id"], "agent_id": aid,
                        "label": n.get("label", a.name if a else aid),
                        "x": n.get("x", 0), "y": n.get("y", 0),
                        "color": a.color if a else "#7c3aed",
                        "avatar_url": av_url,
                    })
                strat_graph["edges"] = sg.get("edges", [])
    except Exception:
        pass

    return _templates(request).TemplateResponse("portfolio.html", {
        "request": request, "page_title": "Portfolio",
        "projects": projects_data,
        "strategic_agents": strategic,
        "strat_graph": strat_graph,
        "epics": epics_data,
        "total_missions": len(all_missions),
        "active_missions": active_count,
        "total_tasks": total_tasks,
        "total_tasks_done": total_done,
        "total_agents": len(all_agents),
    })


@router.post("/api/strategic-committee/launch")
async def launch_strategic_committee(request: Request):
    """Launch a strategic committee session from the portfolio page."""
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..workflows.store import get_workflow_store

    wf_store = get_workflow_store()
    wf = wf_store.get("strategic-committee")
    if not wf:
        return JSONResponse({"error": "Workflow 'strategic-committee' not found"}, status_code=404)

    session_store = get_session_store()
    session = SessionDef(
        name="Comité Stratégique",
        goal="Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO",
        status="active",
        config={"workflow_id": "strategic-committee"},
    )
    session = session_store.create(session)
    session_store.add_message(MessageDef(
        session_id=session.id,
        from_agent="system",
        message_type="system",
        content="Comité Stratégique lancé. Les agents du comité vont débattre des priorités portfolio.",
    ))

    # Auto-start workflow — agents debate autonomously
    import asyncio
    asyncio.create_task(_run_workflow_background(
        wf, session.id,
        "Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO sur les projets en cours",
        "",
    ))

    return JSONResponse({"session_id": session.id})


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Projects list (legacy)."""
    from ..projects.manager import get_project_store
    store = get_project_store()
    projects = store.list_all()
    return _templates(request).TemplateResponse("projects.html", {
        "request": request,
        "page_title": "Projects",
        "projects": [{"info": p, "git": None, "tasks": None} for p in projects],
    })


@router.get("/api/projects/{project_id}/git-status")
async def project_git_status(project_id: str):
    """Lazy-load git status for a single project (called via HTMX)."""
    import asyncio, functools
    from ..projects.manager import get_project_store
    from ..projects import git_service
    project = get_project_store().get(project_id)
    if not project or not project.has_git:
        return HTMLResponse("")
    loop = asyncio.get_event_loop()
    git = await loop.run_in_executor(None, functools.partial(git_service.get_status, project.path))
    if not git:
        return HTMLResponse('<span class="text-muted">no git</span>')
    branch = git.get("branch", "?")
    clean = git.get("clean", True)
    parts = [f'<div class="git-branch">'
             f'<svg class="icon icon-xs"><use href="#icon-git-branch"/></svg> {branch}</div>']
    if not clean:
        counts = []
        if git.get("staged"): counts.append(f'<span class="git-count staged">+{git["staged"]}</span>')
        if git.get("modified"): counts.append(f'<span class="git-count modified">~{git["modified"]}</span>')
        if git.get("untracked"): counts.append(f'<span class="git-count untracked">?{git["untracked"]}</span>')
        if counts:
            parts.append(f'<div class="git-dirty">{"".join(counts)}</div>')
    else:
        parts.append('<span class="git-clean-badge">clean</span>')
    msg = git.get("commit_message", "")
    if msg:
        short = msg[:50] + ("..." if len(msg) > 50 else "")
        date = git.get("commit_date", "")
        parts.append(f'<div class="project-card-commit">'
                     f'<svg class="icon icon-xs"><use href="#icon-git-commit"/></svg>'
                     f'<span class="commit-msg">{short}</span>'
                     f'<span class="commit-date">{date}</span></div>')
    return HTMLResponse("\n".join(parts))


@router.get("/projects/{project_id}/overview", response_class=HTMLResponse)
async def project_overview(request: Request, project_id: str):
    """Project overview page — created from ideation, shows epic/features/team."""
    from ..projects.manager import get_project_store
    from ..missions.store import get_mission_store
    from ..missions.product import get_product_backlog
    from ..agents.store import get_agent_store

    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    mission_store = get_mission_store()
    epics = mission_store.list_missions(project_id=project_id)

    backlog = get_product_backlog()
    agent_store = get_agent_store()

    epics_enriched = []
    for ep in epics:
        features = backlog.list_features(ep.id)
        features_enriched = []
        for f in features:
            stories = backlog.list_stories(f.id)
            features_enriched.append({
                "id": f.id, "name": f.name, "description": f.description,
                "acceptance_criteria": f.acceptance_criteria,
                "story_points": f.story_points, "status": f.status,
                "stories": [{"id": s.id, "title": s.title,
                             "story_points": s.story_points, "status": s.status,
                             "acceptance_criteria": s.acceptance_criteria}
                            for s in stories],
            })
        team_data = (ep.config or {}).get("team", [])
        stack = (ep.config or {}).get("stack", [])
        epics_enriched.append({
            "id": ep.id, "name": ep.name, "description": ep.description,
            "goal": ep.goal, "status": ep.status,
            "features": features_enriched,
            "team": team_data, "stack": stack,
        })

    # Resolve team agents with photos
    team_agents = []
    if epics_enriched:
        for t in epics_enriched[0].get("team", []):
            role = t.get("role", "")
            agent = agent_store.get(role)
            avatar_dir = Path(__file__).parent / "static" / "avatars"
            avatar_url = ""
            if agent and (avatar_dir / f"{agent.id}.jpg").exists():
                avatar_url = f"/static/avatars/{agent.id}.jpg"
            team_agents.append({
                "role": role, "label": t.get("label", role),
                "name": agent.name if agent else t.get("label", role),
                "avatar_url": avatar_url,
                "persona": (agent.persona or "") if agent else "",
            })

    return _templates(request).TemplateResponse("project_overview.html", {
        "request": request, "page_title": f"Projet: {project.name}",
        "project": project,
        "epics": epics_enriched,
        "team_agents": team_agents,
    })


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    """Single project detail view with vision, agents, sessions."""
    from ..projects.manager import get_project_store
    from ..projects import git_service, factory_tasks
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)
    git = git_service.get_status(project.path) if project.has_git else None
    commits = git_service.get_log(project.path, 15) if project.has_git else []
    changes = git_service.get_changes(project.path) if project.has_git else []
    branches = git_service.get_branches(project.path) if project.has_git else []
    tasks = factory_tasks.get_task_summary(project.id)
    recent_tasks = factory_tasks.get_recent_tasks(project.id, 15)
    # Get sessions for this project
    sess_store = get_session_store()
    sessions = [s for s in sess_store.list_all() if s.project_id == project_id]
    sessions.sort(key=lambda s: s.created_at or "", reverse=True)
    # Select active session — from query param or most recent active
    requested_session = request.query_params.get("session")
    active_session = None
    if requested_session:
        active_session = sess_store.get(requested_session)
    if not active_session:
        active_sessions = [s for s in sessions if s.status == "active"]
        if active_sessions:
            active_session = active_sessions[0]
    # Load messages for selected session
    messages = []
    if active_session:
        messages = sess_store.get_messages(active_session.id)
        messages = [m for m in messages if m.from_agent != "system"]
    # Get agents
    agent_store = get_agent_store()
    agents = agent_store.list_all()
    lead = agent_store.get(project.lead_agent_id) if project.lead_agent_id else None
    # Get workflows linked to this project
    workflows = []
    try:
        from ..workflows.store import get_workflow_store
        wf_store = get_workflow_store()
        for wf in wf_store.list_all():
            cfg = wf.config or {}
            if cfg.get("project_ref") == project_id:
                # Find linked session
                linked_session = None
                for s in sessions:
                    if (s.config or {}).get("workflow_id") == wf.id:
                        linked_session = s
                        break
                workflows.append({"wf": wf, "session": linked_session})
    except Exception:
        pass
    # Load project memory files (CLAUDE.md, copilot-instructions.md, etc.)
    memory_files = []
    if project.path:
        try:
            from ..memory.project_files import get_project_memory
            pmem = get_project_memory(project_id, project.path)
            memory_files = pmem.files
        except Exception:
            pass
    # Load missions for this project
    project_missions = []
    try:
        from ..missions.store import get_mission_store
        m_store = get_mission_store()
        project_missions = m_store.list_missions(project_id=project_id)
    except Exception:
        pass
    return _templates(request).TemplateResponse("project_detail.html", {
        "request": request,
        "page_title": project.name,
        "project": project,
        "git": git,
        "commits": commits,
        "changes": changes,
        "branches": branches,
        "tasks": tasks,
        "recent_tasks": recent_tasks,
        "sessions": sessions,
        "active_session": active_session,
        "agents": agents,
        "lead_agent": lead,
        "messages": messages,
        "memory_files": memory_files,
        "workflows": workflows,
        "missions": project_missions,
    })


# ── Project Board (Kanban) ───────────────────────────────────────

@router.get("/projects/{project_id}/board", response_class=HTMLResponse)
async def project_board_page(request: Request, project_id: str):
    """Kanban board view for a project."""
    from ..projects.manager import get_project_store
    from ..projects import factory_tasks
    from ..agents.store import get_agent_store
    from ..missions.store import get_mission_store
    import random

    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    agents_by_id = {a.id: a for a in all_agents}

    # Helper to get avatar URL
    avatar_dir = Path(__file__).parent / "static" / "avatars"
    def _avatar(agent_id):
        jpg = avatar_dir / f"{agent_id}.jpg"
        svg = avatar_dir / f"{agent_id}.svg"
        if jpg.exists(): return f"/static/avatars/{agent_id}.jpg"
        if svg.exists(): return f"/static/avatars/{agent_id}.svg"
        return ""

    # Build task list from missions/stories
    tasks = []
    try:
        m_store = get_mission_store()
        missions = m_store.list_missions(project_id=project_id)
        status_col = {"planning": "backlog", "active": "active", "review": "review",
                       "completed": "done", "deployed": "done"}
        status_labels = {"planning": "Planifié", "active": "En cours", "review": "En revue",
                          "completed": "Terminé", "deployed": "Déployé"}
        for m in missions:
            col = status_col.get(m.status, "backlog")
            agent = agents_by_id.get(m.lead_agent_id) if m.lead_agent_id else None
            tasks.append({
                "title": m.title,
                "col": col,
                "status_label": status_labels.get(m.status, m.status),
                "avatar_url": _avatar(agent.id) if agent else "",
                "agent_name": agent.name if agent else "",
            })
    except Exception:
        pass

    # If no real tasks, show demo
    if not tasks:
        demo = [
            ("Setup projet initial", "done", "Terminé"),
            ("Endpoint /api/users", "active", "En cours"),
            ("Authentification JWT", "active", "En cours"),
            ("Tests E2E smoke", "review", "En revue"),
            ("Documentation API", "backlog", "Planifié"),
            ("Dashboard admin", "backlog", "Planifié"),
            ("Revue sécurité", "backlog", "Planifié"),
        ]
        sample_agents = [a for a in all_agents if _avatar(a.id)][:5]
        for i, (title, col, label) in enumerate(demo):
            ag = sample_agents[i % len(sample_agents)] if sample_agents else None
            tasks.append({
                "title": title, "col": col, "status_label": label,
                "avatar_url": _avatar(ag.id) if ag else "",
                "agent_name": ag.name if ag else "",
            })

    # Agent flow nodes (project team or general agents)
    flow_nodes = []
    flow_edges = []
    team_agents = [a for a in all_agents if _avatar(a.id)][:6]
    positions = [(60, 100), (160, 50), (160, 150), (280, 100), (380, 50), (380, 150)]
    for i, ag in enumerate(team_agents[:6]):
        x, y = positions[i] if i < len(positions) else (60 + i * 80, 100)
        flow_nodes.append({"x": x, "y": y, "label": ag.name.split()[-1] if ag.name else "Agent"})
    # Connect nodes sequentially + some cross-links
    for i in range(len(flow_nodes) - 1):
        n1, n2 = flow_nodes[i], flow_nodes[i + 1]
        flow_edges.append({"x1": n1["x"] + 25, "y1": n1["y"], "x2": n2["x"] - 25, "y2": n2["y"]})

    # Backlog items
    backlog_items = [
        {"title": "User stories non estimées", "count": random.randint(2, 8), "color": "var(--yellow)"},
        {"title": "Bugs P2 en attente", "count": random.randint(0, 3), "color": "var(--red, #ef4444)"},
        {"title": "Features priorisées", "count": random.randint(1, 5), "color": "var(--blue)"},
    ]

    # Pull requests (demo)
    pull_requests = [
        {"title": "feat: add /api/users endpoint", "status": "Open"},
        {"title": "fix: JWT expiration handling", "status": "Review"},
        {"title": "chore: update dependencies", "status": "Merged"},
    ]

    return _templates(request).TemplateResponse("project_board.html", {
        "request": request,
        "page_title": f"Board — {project.name}",
        "project": project,
        "tasks": tasks,
        "flow_nodes": flow_nodes,
        "flow_edges": flow_edges,
        "backlog_items": backlog_items,
        "pull_requests": pull_requests,
    })


# ── Missions ─────────────────────────────────────────────────────

@router.get("/missions", response_class=HTMLResponse)
async def missions_page(request: Request):
    """List all missions with filters."""
    from ..missions.store import get_mission_store
    from ..projects.manager import get_project_store

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
        current = next((s.number for s in sprints if s.status == "active"), len(sprints))
        total_t = stats.get("total", 0)
        done_t = stats.get("done", 0)
        mission_cards.append({
            "mission": m,
            "project_name": project_names.get(m.project_id, m.project_id),
            "sprint_count": len(sprints),
            "current_sprint": current,
            "total_tasks": total_t,
            "done_tasks": done_t,
            "progress_pct": round(done_t / total_t * 100) if total_t > 0 else 0,
        })

    return _templates(request).TemplateResponse("missions.html", {
        "request": request, "page_title": "Missions",
        "missions": mission_cards,
        "project_ids": project_ids,
        "filter_status": filter_status,
        "filter_project": filter_project,
        "show_new_form": show_new,
    })


@router.get("/missions/{mission_id}", response_class=HTMLResponse)
async def mission_detail_page(request: Request, mission_id: str):
    """Mission cockpit — sprints, board, team."""
    from ..missions.store import get_mission_store
    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store

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
            col = t.status if t.status in ("pending", "in_progress", "review", "done") else "pending"
            tasks_by_status.setdefault(col, []).append(t)

    # Team agents
    agent_store = get_agent_store()
    prefix = mission.project_id[:4] if len(mission.project_id) >= 4 else mission.project_id
    all_agents = agent_store.list_all()
    team_agents = [a for a in all_agents if a.id.startswith(prefix + '-') or a.id.startswith(mission.project_id + '-')]

    return _templates(request).TemplateResponse("mission_detail.html", {
        "request": request, "page_title": "Mission",
        "mission": mission, "project": project,
        "sprints": sprints, "stats": stats,
        "selected_sprint": selected_sprint,
        "tasks_by_status": tasks_by_status,
        "team_agents": team_agents,
    })


@router.post("/api/missions")
async def create_mission(request: Request):
    """Create a new mission."""
    from ..missions.store import get_mission_store, MissionDef
    form = await request.form()
    m = MissionDef(
        project_id=form.get("project_id", ""),
        name=form.get("name", "Nouvelle mission"),
        goal=form.get("goal", ""),
        wsjf_score=float(form.get("wsjf_score", 0)),
        created_by="user",
    )
    mission_store = get_mission_store()
    m = mission_store.create_mission(m)
    return RedirectResponse(f"/missions/{m.id}", status_code=303)


@router.post("/api/missions/{mission_id}/start")
async def start_mission(mission_id: str):
    """Activate a mission."""
    from ..missions.store import get_mission_store
    get_mission_store().update_mission_status(mission_id, "active")
    return JSONResponse({"ok": True})


@router.post("/api/missions/{mission_id}/sprints")
async def create_sprint(mission_id: str):
    """Add a sprint to a mission."""
    from ..missions.store import get_mission_store, SprintDef
    store = get_mission_store()
    existing = store.list_sprints(mission_id)
    num = len(existing) + 1
    s = SprintDef(mission_id=mission_id, number=num, name=f"Sprint {num}")
    store.create_sprint(s)
    return JSONResponse({"ok": True})


@router.post("/api/missions/{mission_id}/tasks")
async def create_task(request: Request, mission_id: str):
    """Create a task in a mission sprint (inline kanban creation)."""
    from ..missions.store import get_mission_store, TaskDef
    data = await request.json()
    title = data.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "Title required"}, status_code=400)
    store = get_mission_store()
    sprint_id = data.get("sprint_id", "")
    if not sprint_id:
        sprints = store.list_sprints(mission_id)
        if sprints:
            sprint_id = sprints[-1].id
        else:
            return JSONResponse({"error": "No sprint"}, status_code=400)
    task = TaskDef(
        sprint_id=sprint_id,
        mission_id=mission_id,
        title=title,
        type=data.get("type", "feature"),
        domain=data.get("domain", ""),
        status="pending",
    )
    task = store.create_task(task)
    return JSONResponse({"ok": True, "task_id": task.id})


@router.post("/api/missions/{mission_id}/launch-workflow")
async def launch_mission_workflow(request: Request, mission_id: str):
    """Create a session from mission's workflow and redirect to live view."""
    from ..missions.store import get_mission_store
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..workflows.store import get_workflow_store

    mission_store = get_mission_store()
    mission = mission_store.get_mission(mission_id)
    if not mission:
        return JSONResponse({"error": "Mission not found"}, status_code=404)

    wf_id = mission.workflow_id
    if not wf_id:
        # Pick a default workflow based on project type
        wf_id = "feature-request"

    wf_store = get_workflow_store()
    wf = wf_store.get(wf_id)
    if not wf:
        return JSONResponse({"error": f"Workflow '{wf_id}' not found"}, status_code=404)

    session_store = get_session_store()
    session = SessionDef(
        name=f"{mission.name}",
        goal=mission.goal or mission.description or "",
        project_id=mission.project_id,
        status="active",
        config={
            "workflow_id": wf_id,
            "mission_id": mission_id,
        },
    )
    session = session_store.create(session)
    session_store.add_message(MessageDef(
        session_id=session.id,
        from_agent="system",
        message_type="system",
        content=f"Workflow \"{wf_id}\" lancé pour la mission \"{mission.name}\". Goal: {mission.goal or 'not specified'}",
    ))

    # Auto-start workflow execution — agents will dialogue via patterns
    import asyncio
    task_desc = mission.goal or mission.description or mission.name
    asyncio.create_task(_run_workflow_background(wf, session.id, task_desc, mission.project_id or ""))

    return JSONResponse({"session_id": session.id, "workflow_id": wf_id})


@router.post("/api/missions/{mission_id}/wsjf")
async def compute_wsjf(mission_id: str, request: Request):
    """Compute and store WSJF score from components."""
    from ..missions.store import get_mission_store
    from ..db.migrations import get_db as _gdb
    data = await request.json()
    bv = float(data.get("business_value", 0))
    tc = float(data.get("time_criticality", 0))
    rr = float(data.get("risk_reduction", 0))
    jd = max(float(data.get("job_duration", 1)), 0.1)
    cost_of_delay = bv + tc + rr
    wsjf = round(cost_of_delay / jd, 1)
    # Update mission
    db = _gdb()
    try:
        db.execute(
            "UPDATE missions SET wsjf_score=?, business_value=?, time_criticality=?, risk_reduction=?, job_duration=? WHERE id=?",
            (wsjf, bv, tc, rr, jd, mission_id))
        db.commit()
    finally:
        db.close()
    return JSONResponse({"wsjf": wsjf, "cost_of_delay": cost_of_delay, "job_duration": jd})


@router.get("/api/missions/{mission_id}/board", response_class=HTMLResponse)
async def mission_board_partial(request: Request, mission_id: str):
    """HTMX partial — kanban board for a sprint."""
    from ..missions.store import get_mission_store
    store = get_mission_store()
    sprint_id = request.query_params.get("sprint")
    if not sprint_id:
        return HTMLResponse("")
    tasks = store.list_tasks(sprint_id=sprint_id)
    tasks_by_status = {}
    for t in tasks:
        col = t.status if t.status in ("pending", "in_progress", "review", "done") else "pending"
        tasks_by_status.setdefault(col, []).append(t)

    cols = [("pending", "Backlog", "clipboard"), ("in_progress", "In Progress", "zap"),
            ("review", "Review", "eye"), ("done", "Done", "check")]
    html_parts = []
    for col_status, col_name, col_icon in cols:
        col_tasks = tasks_by_status.get(col_status, [])
        cards = ""
        for t in col_tasks:
            agent = f'<span class="kanban-task-agent"><svg class="icon icon-xs"><use href="#icon-user"/></svg> {t.assigned_to}</span>' if t.assigned_to else ""
            domain = f"<span>{t.domain}</span>" if t.domain else ""
            cards += f'''<div class="kanban-task">
                <div class="kanban-task-title">{t.title}</div>
                <div class="kanban-task-meta">
                    <span class="kanban-task-type {t.type}">{t.type}</span>
                    {domain}{agent}
                </div></div>'''
        if not cards:
            cards = '<div class="kanban-empty">—</div>'
        html_parts.append(f'''<div class="kanban-col">
            <div class="kanban-col-title"><svg class="icon icon-xs"><use href="#icon-{col_icon}"/></svg> {col_name}
                <span class="kanban-col-count">{len(col_tasks)}</span>
            </div>{cards}</div>''')
    return HTMLResponse("".join(html_parts))


# ── Agents ───────────────────────────────────────────────────────

@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    """Agent builder — list all agents."""
    from ..agents.store import get_agent_store
    store = get_agent_store()
    agents = store.list_all()
    return _templates(request).TemplateResponse("agents.html", {
        "request": request,
        "page_title": "Agents",
        "agents": agents,
    })


@router.get("/agents/new", response_class=HTMLResponse)
async def agent_new(request: Request):
    """Create new agent form."""
    from ..agents.store import AgentDef
    from ..llm.providers import list_providers, get_all_models
    return _templates(request).TemplateResponse("agent_edit.html", {
        "request": request,
        "page_title": "New Agent",
        "agent": AgentDef(),
        "providers": list_providers(),
        "models": get_all_models(),
        "roles": ["brain", "worker", "critic", "devops", "pm", "tester", "domain", "custom"],
        "icons": ["bot", "code", "building", "lock", "eye", "rocket", "clipboard",
                  "briefcase", "flask", "palette", "filetext", "hardhat", "shield",
                  "chart", "terminal", "zap", "database", "brain"],
    })


@router.get("/agents/{agent_id}/edit", response_class=HTMLResponse)
async def agent_edit(request: Request, agent_id: str):
    """Edit agent form."""
    from ..agents.store import get_agent_store
    from ..llm.providers import list_providers, get_all_models
    agent = get_agent_store().get(agent_id)
    if not agent:
        return HTMLResponse("<h2>Agent not found</h2>", status_code=404)
    return _templates(request).TemplateResponse("agent_edit.html", {
        "request": request,
        "page_title": f"Edit {agent.name}",
        "agent": agent,
        "providers": list_providers(),
        "models": get_all_models(),
        "roles": ["brain", "worker", "critic", "devops", "pm", "tester", "domain", "custom"],
        "icons": ["bot", "code", "building", "lock", "eye", "rocket", "clipboard",
                  "briefcase", "flask", "palette", "filetext", "hardhat", "shield",
                  "chart", "terminal", "zap", "database", "brain"],
    })


@router.post("/api/agents", response_class=HTMLResponse)
@router.post("/api/agents/{agent_id}", response_class=HTMLResponse)
async def agent_save(request: Request, agent_id: str = ""):
    """Create or update an agent."""
    from ..agents.store import get_agent_store, AgentDef
    form = await request.form()
    store = get_agent_store()

    tags = [t.strip() for t in str(form.get("tags", "")).split(",") if t.strip()]
    permissions = {
        "can_veto": "can_veto" in form,
        "can_approve": "can_approve" in form,
        "can_delegate": "can_delegate" in form,
    }

    existing = store.get(agent_id) if agent_id else None
    agent = existing or AgentDef()
    agent.name = str(form.get("name", ""))
    agent.role = str(form.get("role", "worker"))
    agent.description = str(form.get("description", ""))
    agent.system_prompt = str(form.get("system_prompt", ""))
    agent.provider = str(form.get("provider", "anthropic"))
    agent.model = str(form.get("model", ""))
    agent.temperature = float(form.get("temperature", 0.7))
    agent.max_tokens = int(form.get("max_tokens", 4096))
    agent.tags = tags
    agent.permissions = permissions
    agent.icon = str(form.get("icon", "bot"))
    agent.color = str(form.get("color", "#f78166"))
    agent.avatar = str(form.get("avatar", ""))
    agent.tagline = str(form.get("tagline", ""))

    if existing:
        store.update(agent)
    else:
        store.create(agent)

    return RedirectResponse("/agents", status_code=303)


@router.delete("/api/agents/{agent_id}")
async def agent_delete(agent_id: str):
    """Delete an agent."""
    from ..agents.store import get_agent_store
    get_agent_store().delete(agent_id)
    return HTMLResponse("")


# ── Patterns ─────────────────────────────────────────────────────

@router.get("/patterns", response_class=HTMLResponse)
async def patterns_page(request: Request):
    """Pattern builder — list workflows."""
    from ..patterns.store import get_pattern_store
    patterns = get_pattern_store().list_all()
    return _templates(request).TemplateResponse("patterns.html", {
        "request": request,
        "page_title": "Patterns",
        "patterns": patterns,
    })


@router.get("/patterns/new", response_class=HTMLResponse)
async def pattern_new(request: Request):
    """Create new pattern form."""
    from ..patterns.store import PatternDef
    from ..agents.store import get_agent_store
    agents = get_agent_store().list_all()
    agents_data = [{"id": a.id, "name": a.name, "role": a.role, "icon": a.icon, "color": a.color} for a in agents]
    return _templates(request).TemplateResponse("pattern_edit.html", {
        "request": request,
        "page_title": "New Pattern",
        "pattern": PatternDef(),
        "agents": agents_data,
        "pattern_types": ["solo", "sequential", "parallel", "loop", "router",
                          "aggregator", "hierarchical", "network", "human-in-loop"],
    })


@router.get("/patterns/{pattern_id}/edit", response_class=HTMLResponse)
async def pattern_edit(request: Request, pattern_id: str):
    """Edit pattern form."""
    from ..patterns.store import get_pattern_store
    from ..agents.store import get_agent_store
    pattern = get_pattern_store().get(pattern_id)
    if not pattern:
        return HTMLResponse("<h2>Pattern not found</h2>", status_code=404)
    agents = get_agent_store().list_all()
    agents_data = [{"id": a.id, "name": a.name, "role": a.role, "icon": a.icon, "color": a.color} for a in agents]
    return _templates(request).TemplateResponse("pattern_edit.html", {
        "request": request,
        "page_title": f"Edit {pattern.name}",
        "pattern": pattern,
        "agents": agents_data,
        "pattern_types": ["solo", "sequential", "parallel", "loop", "router",
                          "aggregator", "hierarchical", "network", "human-in-loop"],
    })


@router.post("/api/patterns", response_class=HTMLResponse)
@router.post("/api/patterns/{pattern_id}", response_class=HTMLResponse)
async def pattern_save(request: Request, pattern_id: str = ""):
    """Create or update a pattern from form data."""
    from ..patterns.store import get_pattern_store, PatternDef
    form = await request.form()
    store = get_pattern_store()
    existing = store.get(pattern_id) if pattern_id else None
    p = existing or PatternDef()
    p.name = str(form.get("name", ""))
    p.description = str(form.get("description", ""))
    p.type = str(form.get("type", "sequential"))
    p.icon = str(form.get("icon", "workflow"))
    # agents_json and edges_json come from the canvas JS
    import json as _json
    try:
        p.agents = _json.loads(str(form.get("agents_json", "[]")))
    except Exception:
        p.agents = []
    try:
        p.edges = _json.loads(str(form.get("edges_json", "[]")))
    except Exception:
        p.edges = []
    if existing:
        store.update(p)
    else:
        store.create(p)
    return RedirectResponse("/patterns", status_code=303)


@router.delete("/api/patterns/{pattern_id}")
async def pattern_delete(pattern_id: str):
    """Delete a pattern."""
    from ..patterns.store import get_pattern_store
    get_pattern_store().delete(pattern_id)
    return HTMLResponse("")


# ── Skills ───────────────────────────────────────────────────────

@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    """Skill library — local + GitHub skills with pagination & filtering."""
    from ..skills.library import get_skill_library
    library = get_skill_library()
    all_skills = library.scan_all()
    gh_sources = library.get_github_sources()

    # Query params
    q = request.query_params.get("q", "").strip().lower()
    source_filter = request.query_params.get("source", "")
    repo_filter = request.query_params.get("repo", "")
    page = int(request.query_params.get("page", "1"))
    per_page = int(request.query_params.get("per_page", "50"))

    # Filter
    filtered = all_skills
    if q:
        filtered = [s for s in filtered if q in s.name.lower() or q in s.description.lower() or q in s.id.lower() or any(q in t.lower() for t in s.tags)]
    if source_filter:
        filtered = [s for s in filtered if s.source == source_filter]
    if repo_filter:
        filtered = [s for s in filtered if s.repo == repo_filter]

    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    skills = filtered[(page - 1) * per_page : page * per_page]

    # Unique repos for filter dropdown
    repos = sorted(set(s.repo for s in all_skills if s.repo))

    # Source counts
    from collections import Counter
    source_counts = Counter(s.source for s in all_skills)

    # Check if HTMX partial request (for infinite scroll / filter)
    is_htmx = request.headers.get("HX-Request") == "true"
    target = request.headers.get("HX-Target", "")

    if is_htmx and target == "skills-grid":
        return _templates(request).TemplateResponse("partials/skills_grid.html", {
            "request": request, "skills": skills, "page": page,
            "total_pages": total_pages, "total": total, "q": q,
            "source_filter": source_filter, "repo_filter": repo_filter,
        })

    return _templates(request).TemplateResponse("skills.html", {
        "request": request,
        "page_title": "Skills",
        "skills": skills,
        "github_sources": gh_sources,
        "total": total,
        "total_all": len(all_skills),
        "page": page,
        "total_pages": total_pages,
        "per_page": per_page,
        "q": q,
        "source_filter": source_filter,
        "repo_filter": repo_filter,
        "repos": repos,
        "source_counts": dict(source_counts),
    })


@router.get("/skills/{skill_id}", response_class=HTMLResponse)
async def skill_detail(request: Request, skill_id: str):
    """Skill detail partial for HTMX."""
    from ..skills.library import get_skill_library
    skill = get_skill_library().get(skill_id)
    if not skill:
        return HTMLResponse("<p>Skill not found</p>", status_code=404)
    return _templates(request).TemplateResponse("partials/skill_detail.html", {
        "request": request,
        "skill": skill,
    })


# ── MCPs ─────────────────────────────────────────────────────────

@router.get("/mcps", response_class=HTMLResponse)
async def mcps_page(request: Request):
    """MCP registry."""
    return _templates(request).TemplateResponse("mcps.html", {
        "request": request,
        "page_title": "MCPs",
        "mcps": [],  # TODO: MCPStore
    })


# ── Org Tree ─────────────────────────────────────────────────────

@router.get("/org", response_class=HTMLResponse)
async def org_page(request: Request):
    """SAFe Org Tree — Portfolio → ART → Team."""
    from ..agents.org import get_org_store
    org = get_org_store()
    tree = org.get_org_tree()
    portfolios = org.list_portfolios()
    all_arts = org.list_arts()
    all_teams = org.list_teams()
    total_members = sum(len(t.members) for t in all_teams)

    return _templates(request).TemplateResponse("org.html", {
        "request": request,
        "page_title": "Organisation SAFe",
        "org_tree": tree,
        "portfolios": portfolios,
        "total_arts": len(all_arts),
        "total_teams": len(all_teams),
        "total_members": total_members,
    })


@router.get("/api/org/tree")
async def org_tree_api():
    """JSON org tree for programmatic access."""
    from ..agents.org import get_org_store
    return JSONResponse(get_org_store().get_org_tree())


# ── Memory ───────────────────────────────────────────────────────

@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    """Memory dashboard."""
    from ..memory.manager import get_memory_manager
    from ..projects.manager import get_project_store
    mem = get_memory_manager()
    stats = mem.stats()
    recent_global = mem.global_get(limit=20)

    # Project memories grouped by project
    project_store = get_project_store()
    projects = project_store.list_all()
    project_memories = []
    for p in projects:
        entries = mem.project_get(p.id, limit=10)
        if entries:
            project_memories.append({
                "project_id": p.id,
                "project_name": p.name,
                "entries": entries,
                "count": len(entries),
            })

    return _templates(request).TemplateResponse("memory.html", {
        "request": request,
        "page_title": "Memory",
        "stats": stats,
        "recent_global": recent_global,
        "project_memories": project_memories,
    })


# ── Sessions ─────────────────────────────────────────────────────

@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    """Session list."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    store = get_session_store()
    sessions_raw = store.list_all()
    # Enrich with pattern/project names and message counts
    patterns_map = {}
    try:
        from ..db.migrations import get_db as _gdb
        conn = _gdb()
        for r in conn.execute("SELECT id, name FROM patterns").fetchall():
            patterns_map[r["id"]] = r["name"]
        conn.close()
    except Exception:
        pass
    projects_map = {}
    try:
        from ..projects.manager import get_project_store
        for p in get_project_store().list_all():
            projects_map[p.id] = p.name
    except Exception:
        pass
    sessions = []
    for s in sessions_raw:
        sessions.append({
            "session": s,
            "pattern_name": patterns_map.get(s.pattern_id, ""),
            "project_name": projects_map.get(s.project_id, ""),
            "message_count": store.count_messages(s.id),
        })
    return _templates(request).TemplateResponse("sessions.html", {
        "request": request,
        "page_title": "Sessions",
        "sessions": sessions,
    })


@router.get("/sessions/new", response_class=HTMLResponse)
async def new_session_page(request: Request):
    """New session form."""
    from ..agents.store import get_agent_store
    from ..patterns.store import get_pattern_store
    from ..workflows.store import get_workflow_store
    agents = get_agent_store().list_all()
    patterns = get_pattern_store().list_all()
    workflows = get_workflow_store().list_all()
    projects = []
    try:
        from ..projects.manager import get_project_store
        projects = get_project_store().list_all()
    except Exception:
        pass
    patterns_json = json.dumps({
        p.id: {"name": p.name, "type": p.type, "description": p.description,
               "agents": p.agents, "edges": p.edges}
        for p in patterns
    })
    return _templates(request).TemplateResponse("new_session.html", {
        "request": request,
        "page_title": "New Session",
        "agents": agents,
        "patterns": patterns,
        "workflows": workflows,
        "projects": projects,
        "patterns_json": patterns_json,
    })



# ── Live session (multi-agent real-time view) ─────────────────────

@router.get("/sessions/{session_id}/live", response_class=HTMLResponse)
async def session_live_page(request: Request, session_id: str):
    """Live multi-agent session view with 3 modes: Thread, Chat+Panel, Graph."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    from ..agents.loop import get_loop_manager

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("<h2>Session not found</h2>", status_code=404)

    messages = store.get_messages(session_id, limit=200)
    all_agents = get_agent_store().list_all()
    agent_map = {a.id: a for a in all_agents}

    # Get running loop statuses
    mgr = get_loop_manager()

    # Build agent list with status — filtered after graph is built
    import os
    avatar_dir = Path(__file__).parent / "static" / "avatars"

    def _build_agent_entry(a, mgr_ref, session_id_ref):
        loop = mgr_ref.get_loop(a.id, session_id_ref)
        avatar_jpg = avatar_dir / f"{a.id}.jpg"
        avatar_svg = avatar_dir / f"{a.id}.svg"
        avatar_url = ""
        if avatar_jpg.exists():
            avatar_url = f"/static/avatars/{a.id}.jpg"
        elif avatar_svg.exists():
            avatar_url = f"/static/avatars/{a.id}.svg"
        return {
            "id": a.id, "name": a.name, "role": a.role,
            "icon": a.icon, "color": a.color,
            "avatar": getattr(a, "avatar", "") or "bot",
            "avatar_url": avatar_url,
            "status": loop.status.value if loop else "idle",
            "description": a.description,
            "skills": getattr(a, "skills", []) or [],
            "tools": getattr(a, "tools", []) or [],
            "mcps": getattr(a, "mcps", []) or [],
            "model": getattr(a, "model", "") or "",
            "provider": getattr(a, "provider", "") or "",
            "tagline": getattr(a, "tagline", "") or "",
            "persona": getattr(a, "persona", "") or "",
            "motivation": getattr(a, "motivation", "") or "",
        }

    # Build graph from workflow/pattern definition (structure defined BEFORE execution)
    # Then enrich edges with live message activity counts
    graph = {"nodes": [], "edges": []}
    wf_id = (session.config or {}).get("workflow_id", "")
    wf_graph_loaded = False

    # 1) Try loading graph from workflow config (primary source)
    if wf_id:
        from platform.workflows.store import WorkflowStore
        wf_store = WorkflowStore()
        wf = wf_store.get(wf_id)
        if wf:
            wf_config = wf.config if isinstance(wf.config, dict) else {}
            wf_graph = wf_config.get("graph", {})
            if wf_graph.get("nodes"):
                # Resolve node IDs (n1, n2...) to agent_ids
                node_id_to_agent = {}
                for n in wf_graph["nodes"]:
                    aid = n.get("agent_id", "")
                    a = agent_map.get(aid)
                    node_id_to_agent[n["id"]] = aid
                    graph["nodes"].append({
                        "id": aid,
                        "agent_id": aid,
                        "label": n.get("label") or (a.name if a else aid),
                        "x": n.get("x"),
                        "y": n.get("y"),
                        "hierarchy_rank": a.hierarchy_rank if a else 50,
                    })
                for e in wf_graph.get("edges", []):
                    f_agent = node_id_to_agent.get(e["from"], e["from"])
                    t_agent = node_id_to_agent.get(e["to"], e["to"])
                    graph["edges"].append({
                        "from": f_agent, "to": t_agent,
                        "count": 0,
                        "label": e.get("label", ""),
                        "types": [e.get("type", "sequential")],
                        "patterns": [e.get("type", "sequential")],
                        "color": e.get("color"),
                    })
                wf_graph_loaded = True

            # Fallback: build graph from workflow phases if no explicit graph config
            if not wf_graph_loaded and wf.phases:
                seen_agents = set()
                for phase in wf.phases:
                    phase_agent_ids = (phase.config or {}).get("agents", [])
                    for aid in phase_agent_ids:
                        if aid not in seen_agents:
                            seen_agents.add(aid)
                            a = agent_map.get(aid)
                            graph["nodes"].append({
                                "id": aid, "agent_id": aid,
                                "label": a.name if a else aid,
                                "hierarchy_rank": a.hierarchy_rank if a else 50,
                            })
                    # Infer edges from phase pattern type + agent list
                    ptype = phase.pattern_id or "sequential"
                    if len(phase_agent_ids) >= 2:
                        if ptype == "sequential":
                            for j in range(len(phase_agent_ids) - 1):
                                graph["edges"].append({
                                    "from": phase_agent_ids[j], "to": phase_agent_ids[j + 1],
                                    "count": 0, "types": ["sequential"], "patterns": ["sequential"],
                                })
                        elif ptype in ("hierarchical", "adversarial-cascade"):
                            leader = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append({
                                    "from": leader, "to": w,
                                    "count": 0, "types": [ptype], "patterns": [ptype],
                                })
                        elif ptype == "parallel":
                            dispatcher = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append({
                                    "from": dispatcher, "to": w,
                                    "count": 0, "types": ["parallel"], "patterns": ["parallel"],
                                })
                        elif ptype in ("network", "adversarial-pair", "debate"):
                            for j, a1 in enumerate(phase_agent_ids):
                                for a2 in phase_agent_ids[j + 1:]:
                                    graph["edges"].append({
                                        "from": a1, "to": a2,
                                        "count": 0, "types": [ptype], "patterns": [ptype],
                                    })
                        elif ptype == "router":
                            router = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append({
                                    "from": router, "to": w,
                                    "count": 0, "types": ["route"], "patterns": ["router"],
                                })
                        elif ptype == "aggregator":
                            agg = phase_agent_ids[-1]
                            for w in phase_agent_ids[:-1]:
                                graph["edges"].append({
                                    "from": w, "to": agg,
                                    "count": 0, "types": ["aggregate"], "patterns": ["aggregator"],
                                })
                        elif ptype == "human-in-the-loop":
                            for j in range(len(phase_agent_ids) - 1):
                                graph["edges"].append({
                                    "from": phase_agent_ids[j], "to": phase_agent_ids[j + 1],
                                    "count": 0, "types": ["checkpoint"], "patterns": ["human-in-the-loop"],
                                })
                wf_graph_loaded = bool(seen_agents)

    # 2) Fallback: build from session pattern if no workflow
    if not wf_graph_loaded and session.pattern_id:
        from platform.patterns.store import get_pattern_store
        pat = get_pattern_store().get(session.pattern_id)
        if pat and pat.agents:
            nid_to_aid = {}
            for n in pat.agents:
                aid = n.get("agent_id", "")
                nid_to_aid[n["id"]] = aid
                a = agent_map.get(aid)
                graph["nodes"].append({
                    "id": aid, "agent_id": aid,
                    "label": n.get("label") or (a.name if a else aid),
                    "x": n.get("x"), "y": n.get("y"),
                    "hierarchy_rank": a.hierarchy_rank if a else 50,
                })
            for e in (pat.edges or []):
                f_agent = nid_to_aid.get(e.get("from", ""), e.get("from", ""))
                t_agent = nid_to_aid.get(e.get("to", ""), e.get("to", ""))
                graph["edges"].append({
                    "from": f_agent, "to": t_agent,
                    "count": 0,
                    "types": [e.get("type", "sequential")],
                    "patterns": [e.get("type", "sequential")],
                })

    # 3) Enrich edges with live message activity (counts, veto/approve types)
    edge_index = {}
    for i, e in enumerate(graph["edges"]):
        edge_index[(e["from"], e["to"])] = i

    for m in messages:
        if m.from_agent in ("system", "user"):
            continue
        to = getattr(m, "to_agent", "") or ""
        if not to or to in ("all", "system", "user", "session"):
            continue
        key = (m.from_agent, to)
        if key in edge_index:
            graph["edges"][edge_index[key]]["count"] += 1
            if m.message_type in ("veto", "approve"):
                types_list = graph["edges"][edge_index[key]]["types"]
                if m.message_type not in types_list:
                    types_list.append(m.message_type)

    # 4) Fallback: if graph still empty, build from message participants
    if not graph["nodes"]:
        seen = set()
        for m in messages:
            if m.from_agent in ("system", "user"):
                continue
            if m.from_agent not in seen:
                seen.add(m.from_agent)
                a = agent_map.get(m.from_agent)
                graph["nodes"].append({
                    "id": m.from_agent, "agent_id": m.from_agent,
                    "label": a.name if a else m.from_agent,
                    "hierarchy_rank": a.hierarchy_rank if a else 50,
                })

    # Filter agents to only those in the graph (or all if no graph)
    graph_agent_ids = {n["agent_id"] for n in graph["nodes"]}
    if graph_agent_ids:
        agents = [_build_agent_entry(a, mgr, session_id) for a in all_agents if a.id in graph_agent_ids]
    else:
        agents = [_build_agent_entry(a, mgr, session_id) for a in all_agents]

    # Serialize messages for template
    msg_list = []
    for m in messages:
        a = agent_map.get(m.from_agent)
        # Extract tool activity from metadata
        meta = m.metadata if isinstance(m.metadata, dict) else {}
        tcs = meta.get("tool_calls") or []
        edit_count = sum(1 for tc in tcs if isinstance(tc, dict) and tc.get("name") in ("code_edit", "code_write"))
        read_count = sum(1 for tc in tcs if isinstance(tc, dict) and tc.get("name") in ("code_read", "code_search", "list_files"))
        shell_count = sum(1 for tc in tcs if isinstance(tc, dict) and tc.get("name") in ("shell", "git_status", "git_log"))
        msg_list.append({
            "id": m.id, "from_agent": m.from_agent, "to_agent": getattr(m, "to_agent", ""),
            "type": m.message_type, "content": m.content,
            "timestamp": m.timestamp if isinstance(m.timestamp, str) else m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            "from_name": a.name if a else m.from_agent,
            "from_color": a.color if a else "#6b7280",
            "from_avatar": getattr(a, "avatar", "bot") if a else "message-circle",
            "edits": edit_count,
            "reads": read_count,
            "shells": shell_count,
            "tool_count": len(tcs),
        })

    # Load memory for this session
    # Extract artifacts from messages (decisions, reports, tool usage)
    artifacts = []
    # Extract PRs/deliverables from messages — [PR] pattern
    import re as _re
    pr_list = []
    pr_seen = set()
    for m in messages:
        if m.from_agent in ("system", "user"):
            continue
        a = agent_map.get(m.from_agent)
        agent_name = a.name if a else m.from_agent
        content = (m.content or "")

        # Extract [PR] items from agent messages
        for pr_match in _re.finditer(r'\[PR\]\s*(.+?)(?:\n|$)', content):
            pr_title = pr_match.group(1).strip()
            pr_title = _re.sub(r'[*_`#]', '', pr_title).strip()[:80]
            if pr_title and pr_title not in pr_seen:
                pr_seen.add(pr_title)
                pr_list.append({
                    "title": pr_title,
                    "agent": agent_name,
                    "agent_id": m.from_agent,
                    "done": False,
                })

        # Mark PRs as done if later approved
        if m.message_type == "approve":
            for pr in pr_list:
                if pr["agent_id"] == m.from_agent or m.from_agent in ("qa_lead", "lead_dev"):
                    pr["done"] = True

        # Extract title (first ## heading or first line)
        title_match = _re.search(r'^##\s*(.+)', content, _re.MULTILINE)
        title = title_match.group(1).strip()[:60] if title_match else content[:60].strip()
        title = _re.sub(r'[*_`#]', '', title).strip()

        if m.message_type in ("veto", "approve"):
            artifacts.append({
                "type": m.message_type,
                "title": title,
                "agent": agent_name,
                "agent_id": m.from_agent,
                "icon": "x-circle" if m.message_type == "veto" else "check-circle",
            })
        elif any(kw in content[:200].lower() for kw in ("rapport", "audit", "analyse", "synthèse", "conclusion", "décomposition")):
            meta = {}
            if hasattr(m, "metadata") and m.metadata:
                meta = m.metadata if isinstance(m.metadata, dict) else {}
            has_tools = bool(meta.get("tool_calls"))
            artifacts.append({
                "type": "report",
                "title": title,
                "agent": agent_name,
                "agent_id": m.from_agent,
                "icon": "wrench" if has_tools else "file-text",
            })

    memory_data = {"session": [], "project": [], "shared": [], "artifacts": artifacts, "prs": pr_list}
    try:
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        memory_data["session"] = mem.pattern_get(session_id, limit=20)
        if session.project_id:
            memory_data["project"] = mem.project_get(session.project_id, limit=20)
        memory_data["shared"] = mem.global_get(limit=10)
    except Exception:
        pass

    agent_map_dict = _agent_map_for_template(agents)

    # Build prompt suggestions based on workflow/session goal
    suggestions = []
    if wf_id:
        from platform.workflows.store import WorkflowStore as _WS2
        _wf2 = _WS2().get(wf_id)
        if _wf2:
            _WORKFLOW_SUGGESTIONS = {
                "strategic-committee": [
                    ("bar-chart-2", "Arbitrage portfolio", "Analysez le portfolio actuel et recommandez les arbitrages d'investissement pour le trimestre"),
                    ("target", "Priorisation WSJF", "Priorisez les initiatives en cours avec la méthode WSJF et identifiez les quick wins"),
                    ("check-circle", "GO/NOGO projet", "Évaluez la faisabilité et décidez GO ou NOGO pour les projets en attente"),
                    ("dollar-sign", "Revue budget", "Passez en revue les budgets par projet et identifiez les dépassements potentiels"),
                ],
                "sf-pipeline": [
                    ("cpu", "Analyse codebase", "Analysez la codebase et décomposez les prochaines tâches de développement"),
                    ("alert-triangle", "Fix bugs critiques", "Identifiez et corrigez les bugs critiques en production"),
                    ("shield", "Audit sécurité", "Lancez un audit de sécurité OWASP sur le code actuel"),
                    ("trending-up", "Optimisation perf", "Analysez les performances et proposez des optimisations"),
                ],
                "migration-sharelook": [
                    ("refresh-cw", "Démarrer migration", "Lancez la migration Angular 16→17 en commençant par l'inventaire des modules"),
                    ("check-square", "Vérifier golden files", "Comparez les golden files legacy vs migration pour valider l'ISO 100%"),
                    ("package", "Migrer module", "Migrez le prochain module standalone avec les codemods"),
                    ("activity", "Tests de régression", "Exécutez les tests de régression post-migration"),
                ],
                "review-cycle": [
                    ("eye", "Review derniers commits", "Passez en revue les derniers commits et identifiez les problèmes"),
                    ("search", "Analyse qualité", "Analysez la qualité du code : complexité, duplication, couverture"),
                    ("shield", "Audit sécurité", "Vérifiez les vulnérabilités de sécurité dans le code récent"),
                ],
                "debate-decide": [
                    ("zap", "Proposition technique", "Débattez des options d'architecture pour la prochaine feature"),
                    ("layers", "Choix de stack", "Comparez les stacks techniques et décidez la meilleure approche"),
                ],
                "ideation-to-prod": [
                    ("compass", "Nouvelle idée", "Explorons une nouvelle idée de produit — de l'idéation jusqu'au MVP"),
                    ("box", "Architecture MVP", "Définissez l'architecture du MVP et les composants nécessaires"),
                    ("play", "Sprint dev", "Lancez un sprint de développement sur les user stories prioritaires"),
                ],
                "feature-request": [
                    ("file-text", "Nouveau besoin", "J'ai un besoin métier à exprimer pour challenge et implémentation"),
                    ("target", "User story", "Transformez ce besoin en user stories priorisées"),
                ],
                "tech-debt-reduction": [
                    ("tool", "Audit dette", "Lancez un audit cross-projet de la dette technique"),
                    ("bar-chart-2", "Prioriser fixes", "Priorisez les corrections de dette par impact WSJF"),
                ],
                "tma-maintenance": [
                    ("alert-triangle", "Triage incidents", "Triez les incidents ouverts par sévérité et assignez les correctifs"),
                    ("search", "Diagnostic bug", "Diagnostiquez le bug suivant avec analyse root cause et impact"),
                    ("zap", "Hotfix urgent", "Lancez un correctif hotfix P0 avec deploy express"),
                    ("bar-chart-2", "Bilan TMA", "Faites un bilan des SLA, incidents résolus et dette technique restante"),
                ],
                "test-campaign": [
                    ("clipboard", "Plan de test", "Définissez la matrice de couverture et les parcours critiques à tester"),
                    ("terminal", "Automatiser tests", "Écrivez les tests E2E Playwright pour les parcours identifiés"),
                    ("play-circle", "Lancer campagne", "Exécutez la campagne complète: E2E, API, smoke, performance"),
                    ("bar-chart-2", "Rapport qualité", "Consolidez les résultats et décidez GO/NOGO pour la release"),
                ],
                "cicd-pipeline": [
                    ("settings", "Setup pipeline", "Configurez le pipeline CI/CD GitHub Actions pour le projet"),
                    ("refresh-cw", "Optimiser CI", "Analysez et optimisez les temps de build du pipeline actuel"),
                    ("shield", "Quality gates", "Configurez les quality gates: couverture, sécurité, performance"),
                    ("upload-cloud", "Deploy canary", "Lancez un déploiement canary avec monitoring et rollback automatique"),
                ],
                "product-lifecycle": [
                    ("compass", "Nouvelle idée produit", "J'ai une idée de produit à explorer — lancez l'idéation avec le métier, l'UX et l'architecte"),
                    ("git-merge", "Cycle complet depuis un besoin", "Voici un besoin métier — faites-le passer par le cycle complet: idéation → comité strat → dev → CICD → QA → prod → TMA"),
                    ("refresh-cw", "Reprendre au sprint dev", "Le comité stratégique a validé le GO — lancez les sprints de développement"),
                    ("activity", "Lancer la campagne QA", "Le code est prêt — lancez la campagne de tests QA complète avant le deploy"),
                ],
            }
            suggestions = _WORKFLOW_SUGGESTIONS.get(wf_id, [])
            if not suggestions and _wf2.description:
                suggestions = [
                    ("play", "Démarrer", f"Démarrons : {_wf2.description}"),
                    ("help-circle", "État des lieux", "Faites un état des lieux avant de commencer"),
                ]
    if not suggestions and session.goal:
        suggestions = [
            ("play", "Démarrer", f"Commençons : {session.goal}"),
            ("clipboard", "Plan d'action", f"Proposez un plan d'action pour : {session.goal}"),
        ]

    return _templates(request).TemplateResponse("session_live.html", {
        "request": request,
        "page_title": f"Live: {session.name}",
        "session": {"id": session.id, "name": session.name, "goal": session.goal,
                     "status": session.status, "pattern": getattr(session, "pattern_id", ""),
                     "project_id": session.project_id},
        "agents": agents,
        "agent_map": agent_map_dict,
        "messages": msg_list,
        "graph": graph,
        "memory": memory_data,
        "suggestions": suggestions,
    })


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_page(request: Request, session_id: str):
    """Active session conversation view."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    from ..patterns.store import get_pattern_store
    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("<h2>Session not found</h2>", status_code=404)
    messages = store.get_messages(session_id)
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)
    pattern_name = ""
    if session.pattern_id:
        pat = get_pattern_store().get(session.pattern_id)
        if pat:
            pattern_name = pat.name
    workflow_name = ""
    wf_id = (session.config or {}).get("workflow_id", "")
    if wf_id:
        from ..workflows.store import get_workflow_store
        wf = get_workflow_store().get(wf_id)
        if wf:
            workflow_name = wf.name
    return _templates(request).TemplateResponse("conversation.html", {
        "request": request,
        "page_title": session.name,
        "session": session,
        "messages": messages,
        "agents": agents,
        "agent_map": agent_map,
        "pattern_name": pattern_name,
        "workflow_name": workflow_name,
    })


@router.post("/api/sessions")
async def create_session(request: Request):
    """Create a new session from form data."""
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    form = await request.form()
    store = get_session_store()
    session = SessionDef(
        name=str(form.get("name", "Untitled")),
        goal=str(form.get("goal", "")),
        pattern_id=str(form.get("pattern_id", "")) or None,
        project_id=str(form.get("project_id", "")) or None,
        status="active",
        config={
            "lead_agent": str(form.get("lead_agent", "")),
            "workflow_id": str(form.get("workflow_id", "")),
        },
    )
    session = store.create(session)
    # Add system message
    store.add_message(MessageDef(
        session_id=session.id,
        from_agent="system",
        message_type="system",
        content=f"Session \"{session.name}\" started. Goal: {session.goal or 'not specified'}",
    ))
    return RedirectResponse(f"/sessions/{session.id}", status_code=303)


@router.post("/api/sessions/{session_id}/messages", response_class=HTMLResponse)
async def send_message(request: Request, session_id: str):
    """User sends a message — agent responds via LLM."""
    from ..sessions.store import get_session_store, MessageDef
    from ..sessions.runner import handle_user_message
    from ..agents.store import get_agent_store
    form = await request.form()
    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)
    # Auto-resume if stopped
    if session.status in ("completed", "failed"):
        store.update_status(session_id, "active")
    content = str(form.get("content", "")).strip()
    if not content:
        return HTMLResponse("")
    to_agent = str(form.get("to_agent", "")) or session.config.get("lead_agent") or None

    # Store user message
    user_msg = store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        to_agent=to_agent,
        message_type="text",
        content=content,
    ))

    # Get agent map for rendering
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)

    # Render user bubble
    user_html = _templates(request).TemplateResponse("partials/msg_unified.html", {
        "request": request, "msg": user_msg, "agent_map": agent_map, "msg_mode": "chat",
    }).body.decode()

    # Call agent (async LLM)
    agent_msg = await handle_user_message(session_id, content, to_agent or "")

    if agent_msg:
        agent_html = _templates(request).TemplateResponse("partials/msg_unified.html", {
            "request": request, "msg": agent_msg, "agent_map": agent_map, "msg_mode": "chat",
        }).body.decode()
        return HTMLResponse(user_html + agent_html)

    return HTMLResponse(user_html)


@router.get("/api/sessions/{session_id}/messages", response_class=HTMLResponse)
async def poll_messages(request: Request, session_id: str, after: str = ""):
    """Poll for new messages (HTMX polling endpoint)."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    store = get_session_store()
    if not after:
        return HTMLResponse("")
    messages = store.get_messages_after(session_id, after)
    if not messages:
        return HTMLResponse("")
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)
    html_parts = []
    for msg in messages:
        html_parts.append(_templates(request).TemplateResponse("partials/msg_unified.html", {
            "request": request,
            "msg": msg,
            "agent_map": agent_map,
            "msg_mode": "chat",
        }).body.decode())
    return HTMLResponse("".join(html_parts))


@router.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active session."""
    from ..sessions.store import get_session_store, MessageDef
    store = get_session_store()
    session = store.get(session_id)
    if session and session.status == "completed":
        return HTMLResponse("")  # already stopped
    store.update_status(session_id, "completed")
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        message_type="system",
        content="Session stopped by user.",
    ))
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a completed/stopped session back to active."""
    from ..sessions.store import get_session_store, MessageDef
    store = get_session_store()
    store.update_status(session_id, "active")
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        message_type="system",
        content="Session resumed.",
    ))
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/run-pattern")
async def run_session_pattern(request: Request, session_id: str):
    """Execute the pattern assigned to this session."""
    from ..sessions.store import get_session_store, MessageDef
    from ..patterns.store import get_pattern_store
    from ..patterns.engine import run_pattern

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    form = await request.form()
    task = str(form.get("task", session.goal or "Execute the pattern")).strip()
    pattern_id = str(form.get("pattern_id", session.pattern_id or "")).strip()

    if not pattern_id:
        return HTMLResponse('<div class="msg-system-text">No pattern assigned to this session.</div>')

    pattern = get_pattern_store().get(pattern_id)
    if not pattern:
        return HTMLResponse(f'<div class="msg-system-text">Pattern {pattern_id} not found.</div>')

    # Store user's task as a message
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        message_type="text",
        content=f"Run pattern **{pattern.name}**: {task}",
    ))

    # Run pattern asynchronously (agents will post messages to the session)
    asyncio.create_task(_run_pattern_background(
        pattern, session_id, task, session.project_id or ""))

    return HTMLResponse(
        '<div class="msg-system-text">Pattern started — agents are working...</div>')


async def _run_pattern_background(pattern, session_id: str, task: str, project_id: str):
    """Background task for pattern execution."""
    from ..patterns.engine import run_pattern
    try:
        await run_pattern(pattern, session_id, task, project_id)
    except Exception as e:
        logger.error("Pattern execution failed: %s", e)
        from ..sessions.store import get_session_store, MessageDef
        get_session_store().add_message(MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content=f"Pattern execution error: {e}",
        ))



@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    from ..sessions.store import get_session_store
    get_session_store().delete(session_id)
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/agents/start")
async def start_session_agents(request: Request, session_id: str):
    """Start agent loops for a session — the agents begin thinking autonomously."""
    from ..sessions.store import get_session_store
    from ..agents.loop import get_loop_manager
    from ..projects.manager import get_project_store

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    form = await request.form()
    agent_ids = str(form.get("agent_ids", "")).split(",")
    agent_ids = [a.strip() for a in agent_ids if a.strip()]
    if not agent_ids:
        return JSONResponse({"error": "No agent_ids provided"}, status_code=400)

    # Resolve project path
    project_path = ""
    if session.project_id:
        try:
            proj = get_project_store().get(session.project_id)
            if proj:
                project_path = proj.path
        except Exception:
            pass

    mgr = get_loop_manager()
    started = []
    for aid in agent_ids:
        try:
            await mgr.start_agent(aid, session_id, session.project_id or "", project_path)
            started.append(aid)
        except Exception as e:
            logger.error("Failed to start agent %s: %s", aid, e)

    return JSONResponse({"started": started, "count": len(started)})


@router.post("/api/sessions/{session_id}/agents/stop")
async def stop_session_agents(session_id: str):
    """Stop all agent loops for a session."""
    from ..agents.loop import get_loop_manager
    mgr = get_loop_manager()
    await mgr.stop_session(session_id)
    return JSONResponse({"stopped": True})


@router.post("/api/sessions/{session_id}/agents/{agent_id}/message")
async def send_to_agent(request: Request, session_id: str, agent_id: str):
    """Send a message to a specific agent via the bus (user → agent)."""
    from ..a2a.bus import get_bus
    from ..models import A2AMessage, MessageType
    from ..sessions.store import get_session_store, MessageDef

    form = await request.form()
    content = str(form.get("content", "")).strip()
    if not content:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    # Store user message in session
    store = get_session_store()
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        message_type="text",
        content=content,
    ))

    # Publish to bus so the agent's loop picks it up
    bus = get_bus()
    msg = A2AMessage(
        session_id=session_id,
        from_agent="user",
        to_agent=agent_id,
        message_type=MessageType.REQUEST,
        content=content,
        requires_response=True,
    )
    await bus.publish(msg)

    return JSONResponse({"sent": True, "to": agent_id})


@router.post("/api/sessions/{session_id}/conversation")
async def start_conversation(request: Request, session_id: str):
    """Start a real multi-agent conversation with streaming.

    Each agent is called individually with its own persona/LLM,
    sees the full conversation history, and responds in real-time via SSE.
    """
    from ..sessions.runner import run_conversation

    form = await request.form()
    message = str(form.get("message", "")).strip()
    agent_ids_raw = str(form.get("agent_ids", ""))
    agent_ids = [a.strip() for a in agent_ids_raw.split(",") if a.strip()]
    lead = str(form.get("lead_agent", ""))
    max_rounds = int(form.get("max_rounds", 6))

    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    if not agent_ids:
        return JSONResponse({"error": "agent_ids required"}, status_code=400)

    # Run in background — SSE will stream the conversation
    async def _run_conv():
        try:
            await run_conversation(
                session_id=session_id,
                initial_message=message,
                agent_ids=agent_ids,
                max_rounds=max_rounds,
                lead_agent_id=lead,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Conversation failed: %s", exc, exc_info=True)

    asyncio.create_task(_run_conv())

    return JSONResponse({"status": "started", "agents": agent_ids, "max_rounds": max_rounds})


@router.get("/api/sessions/{session_id}/messages/json")
async def session_messages_json(session_id: str):
    """JSON list of all agent messages for a session (for fallback on pattern_end)."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    store = get_session_store()
    msgs = store.get_messages(session_id)
    agents = {a.id: a for a in get_agent_store().list_all()}
    result = []
    for m in msgs:
        if m.from_agent in ("system", "user"):
            continue
        a = agents.get(m.from_agent)
        result.append({
            "agent_id": m.from_agent,
            "agent_name": a.name if a else m.from_agent,
            "role": a.role if a else "",
            "content": m.content,
            "to_agent": m.to_agent,
        })
    return JSONResponse(result)


@router.get("/api/sessions/{session_id}/sse")
async def session_sse(request: Request, session_id: str):
    """SSE endpoint for real-time session updates."""
    from ..sessions.runner import add_sse_listener, remove_sse_listener

    q = add_sse_listener(session_id)

    async def event_generator():
        try:
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            remove_sse_listener(session_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Workflows ────────────────────────────────────────────────────

@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    """Workflow templates listing."""
    from ..workflows.store import get_workflow_store
    from ..patterns.store import get_pattern_store
    workflows = get_workflow_store().list_all()
    patterns = {p.id: p for p in get_pattern_store().list_all()}
    return _templates(request).TemplateResponse("workflows.html", {
        "request": request,
        "page_title": "Workflows",
        "workflows": workflows,
        "patterns": patterns,
    })


@router.get("/workflows/new", response_class=HTMLResponse)
async def workflow_new(request: Request):
    """New workflow form."""
    from ..patterns.store import get_pattern_store
    from ..agents.store import get_agent_store
    patterns = [{"id": p.id, "name": p.name, "type": p.type} for p in get_pattern_store().list_all()]
    agents = [{"id": a.id, "name": a.name, "role": a.role, "icon": a.icon, "color": a.color,
               "skills": a.skills, "description": a.description}
              for a in get_agent_store().list_all()]
    return _templates(request).TemplateResponse("workflow_edit.html", {
        "request": request,
        "page_title": "New Workflow",
        "workflow": None,
        "patterns": patterns,
        "agents": agents,
    })


@router.get("/workflows/{wf_id}/edit", response_class=HTMLResponse)
async def workflow_edit(request: Request, wf_id: str):
    """Edit workflow form."""
    from ..workflows.store import get_workflow_store
    from ..patterns.store import get_pattern_store
    from ..agents.store import get_agent_store
    wf = get_workflow_store().get(wf_id)
    if not wf:
        return HTMLResponse("<h2>Workflow not found</h2>", status_code=404)
    patterns = [{"id": p.id, "name": p.name, "type": p.type} for p in get_pattern_store().list_all()]
    agents = [{"id": a.id, "name": a.name, "role": a.role, "icon": a.icon, "color": a.color,
               "skills": a.skills, "description": a.description}
              for a in get_agent_store().list_all()]
    return _templates(request).TemplateResponse("workflow_edit.html", {
        "request": request,
        "page_title": f"Edit: {wf.name}",
        "workflow": wf,
        "patterns": patterns,
        "agents": agents,
    })


@router.post("/api/workflows")
async def create_workflow(request: Request):
    """Create or update a workflow."""
    from ..workflows.store import get_workflow_store, WorkflowDef, WorkflowPhase
    import json as _json
    form = await request.form()
    wf_id = str(form.get("id", ""))
    name = str(form.get("name", "New Workflow"))
    description = str(form.get("description", ""))
    icon = str(form.get("icon", "workflow"))
    phases_raw = str(form.get("phases_json", "[]"))
    try:
        phases_data = _json.loads(phases_raw)
    except Exception:
        phases_data = []
    phases = [WorkflowPhase(
        id=p.get("id", f"p{i+1}"),
        pattern_id=p.get("pattern_id", ""),
        name=p.get("name", f"Phase {i+1}"),
        description=p.get("description", ""),
        gate=p.get("gate", "always"),
    ) for i, p in enumerate(phases_data)]

    config_raw = str(form.get("config_json", "{}"))
    try:
        config = _json.loads(config_raw)
    except Exception:
        config = {}
    wf = WorkflowDef(id=wf_id, name=name, description=description, icon=icon, phases=phases, config=config)
    store = get_workflow_store()
    store.create(wf)
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/workflows/{wf_id}")
async def update_workflow(request: Request, wf_id: str):
    """Update an existing workflow."""
    from ..workflows.store import get_workflow_store, WorkflowDef, WorkflowPhase
    import json as _json
    form = await request.form()
    name = str(form.get("name", ""))
    description = str(form.get("description", ""))
    icon = str(form.get("icon", "workflow"))
    phases_raw = str(form.get("phases_json", "[]"))
    try:
        phases_data = _json.loads(phases_raw)
    except Exception:
        phases_data = []
    phases = [WorkflowPhase(
        id=p.get("id", f"p{i+1}"),
        pattern_id=p.get("pattern_id", ""),
        name=p.get("name", f"Phase {i+1}"),
        description=p.get("description", ""),
        gate=p.get("gate", "always"),
    ) for i, p in enumerate(phases_data)]

    config_raw = str(form.get("config_json", "{}"))
    try:
        config = _json.loads(config_raw)
    except Exception:
        config = {}
    wf = WorkflowDef(id=wf_id, name=name, description=description, icon=icon, phases=phases, config=config)
    store = get_workflow_store()
    store.create(wf)  # INSERT OR REPLACE
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/workflows/{wf_id}/delete")
async def delete_workflow(request: Request, wf_id: str):
    """Delete a workflow."""
    from ..workflows.store import get_workflow_store
    get_workflow_store().delete(wf_id)
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/sessions/{session_id}/run-workflow")
async def run_session_workflow(request: Request, session_id: str):
    """Execute a workflow in a session."""
    from ..sessions.store import get_session_store, MessageDef
    from ..workflows.store import get_workflow_store, run_workflow

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    form = await request.form()
    workflow_id = str(form.get("workflow_id", "")).strip()
    task = str(form.get("task", session.goal or "Execute workflow")).strip()

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return HTMLResponse(f'<div class="msg-system-text">Workflow {workflow_id} not found.</div>')

    # User message targets the workflow leader (first agent of first phase)
    leader = ""
    if wf.phases:
        first_agents = wf.phases[0].config.get("agents", [])
        if first_agents:
            leader = first_agents[0]

    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        to_agent=leader or "all",
        message_type="text",
        content=f"Run workflow **{wf.name}**: {task}",
    ))

    # Save workflow_id in session config (needed for graph rendering)
    from ..sessions.store import get_db
    import json as _json
    db = get_db()
    try:
        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["workflow_id"] = workflow_id
        if leader:
            existing_config["lead_agent"] = leader
        db.execute("UPDATE sessions SET config_json=? WHERE id=?",
                   (_json.dumps(existing_config), session_id))
        db.commit()
    finally:
        db.close()

    # Resolve project_id: from session, or from workflow config
    project_id = session.project_id or ""
    if not project_id and wf.config:
        project_id = wf.config.get("project_ref", "")
    if project_id and not session.project_id:
        db = get_db()
        try:
            db.execute("UPDATE sessions SET project_id=? WHERE id=?", (project_id, session_id))
            db.commit()
        finally:
            db.close()

    asyncio.create_task(_run_workflow_background(wf, session_id, task, project_id))
    return HTMLResponse(
        f'<div class="msg-system-text">Workflow "{wf.name}" started — {len(wf.phases)} phases.</div>')


async def _run_workflow_background(wf, session_id: str, task: str, project_id: str):
    """Background workflow execution."""
    from ..workflows.store import run_workflow
    try:
        await run_workflow(wf, session_id, task, project_id)
    except Exception as e:
        logger.error("Workflow failed: %s", e)
        from ..sessions.store import get_session_store, MessageDef
        get_session_store().add_message(MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content=f"Workflow error: {e}",
        ))


# ── Workflow Resume ───────────────────────────────────────────────

@router.post("/api/workflow/{session_id}/resume")
async def workflow_resume(session_id: str):
    """Resume a workflow that was interrupted (e.g. server crash)."""
    from ..sessions.store import get_session_store
    from ..workflows.store import get_workflow_store
    store = get_session_store()
    sess = store.get(session_id)
    if not sess:
        return {"error": "Session not found"}
    config = sess.config or {}
    wf_id = config.get("workflow_id")
    if not wf_id:
        return {"error": "No workflow_id in session config"}
    wf = get_workflow_store().get(wf_id)
    if not wf:
        return {"error": f"Workflow {wf_id} not found"}
    task = sess.goal or sess.name
    project_id = sess.project_id or ""
    asyncio.create_task(_run_workflow_background(wf, session_id, task, project_id))
    return {"status": "resumed", "session_id": session_id, "workflow_id": wf_id}


# ── Monitoring / Settings ────────────────────────────────────────

@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    return _templates(request).TemplateResponse("monitoring.html", {
        "request": request,
        "page_title": "Monitoring",
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    from ..config import get_config
    from ..llm.providers import list_providers
    cfg = get_config()
    return _templates(request).TemplateResponse("settings.html", {
        "request": request,
        "page_title": "Settings",
        "config": cfg,
        "providers": list_providers(),
    })


# ── API: Projects ────────────────────────────────────────────────

@router.get("/api/projects")
async def api_projects():
    """List all projects (JSON)."""
    from ..projects.manager import get_project_store
    store = get_project_store()
    return JSONResponse([{
        "id": p.id, "name": p.name, "path": p.path,
        "factory_type": p.factory_type, "domains": p.domains,
        "lead_agent_id": p.lead_agent_id, "status": p.status,
        "has_vision": bool(p.vision), "values": p.values,
    } for p in store.list_all()])


@router.post("/api/projects")
async def create_project(request: Request):
    """Create a new project."""
    from ..projects.manager import get_project_store, Project
    form = await request.form()
    store = get_project_store()
    p = Project(
        id=str(form.get("id", "")),
        name=str(form.get("name", "")),
        path=str(form.get("path", "")),
        description=str(form.get("description", "")),
        factory_type=str(form.get("factory_type", "standalone")),
        lead_agent_id=str(form.get("lead_agent_id", "brain")),
        values=[v.strip() for v in str(form.get("values", "quality,feedback")).split(",") if v.strip()],
    )
    # Auto-load vision
    if p.exists:
        p.vision = p.load_vision_from_file()
    store.create(p)
    return RedirectResponse(f"/projects/{p.id}", status_code=303)


@router.post("/api/projects/{project_id}/vision")
async def update_vision(request: Request, project_id: str):
    """Update project vision."""
    from ..projects.manager import get_project_store
    form = await request.form()
    store = get_project_store()
    store.update_vision(project_id, str(form.get("vision", "")))
    return HTMLResponse('<span class="badge badge-green">Saved</span>')


@router.post("/api/projects/{project_id}/chat")
async def project_chat(request: Request, project_id: str):
    """Quick chat with a project's lead agent — creates or reuses session."""
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..sessions.runner import handle_user_message
    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store

    form = await request.form()
    content = str(form.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    proj = get_project_store().get(project_id)
    if not proj:
        return HTMLResponse("Project not found", status_code=404)

    store = get_session_store()
    # Find or create active session for this project
    sessions = [s for s in store.list_all() if s.project_id == project_id and s.status == "active"]
    sessions.sort(key=lambda s: s.created_at or "", reverse=True)
    if sessions:
        session = sessions[0]
    else:
        session = store.create(SessionDef(
            name=f"{proj.name} — Chat",
            goal="Project conversation",
            project_id=project_id,
            status="active",
            config={"lead_agent": proj.lead_agent_id or "brain"},
        ))
        store.add_message(MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content=f"Session started for project {proj.name}",
        ))

    # Store user message
    store.add_message(MessageDef(
        session_id=session.id,
        from_agent="user",
        message_type="text",
        content=content,
    ))

    # Get agent response
    agent_msg = await handle_user_message(session.id, content, proj.lead_agent_id or "")

    # For HTMX: return both the user message and agent response as chat bubbles
    import html as html_mod
    import markdown as md_lib
    user_html = (
        f'<div class="chat-msg chat-msg-user">'
        f'<div class="chat-msg-body"><div class="chat-msg-text">{html_mod.escape(content)}</div></div>'
        f'<div class="chat-msg-avatar user">S</div>'
        f'</div>'
    )
    if agent_msg:
        agent_content = agent_msg.get("content", "") if isinstance(agent_msg, dict) else getattr(agent_msg, "content", str(agent_msg))
        # Render tool calls if present
        tools_html = ""
        tool_calls = None
        if isinstance(agent_msg, dict):
            tool_calls = agent_msg.get("metadata", {}).get("tool_calls") if agent_msg.get("metadata") else None
        elif hasattr(agent_msg, "metadata") and agent_msg.metadata:
            tool_calls = agent_msg.metadata.get("tool_calls")
        if tool_calls:
            pills = "".join(f'<span class="chat-tool-pill"><svg class="icon icon-xs"><use href="#icon-wrench"/></svg> {html_mod.escape(str(tc.get("name", tc) if isinstance(tc, dict) else tc))}</span>' for tc in tool_calls)
            tools_html = f'<div class="chat-msg-tools">{pills}</div>'
        # Render markdown to HTML
        rendered = md_lib.markdown(str(agent_content), extensions=["fenced_code", "tables", "nl2br"])
        agent_html = (
            f'<div class="chat-msg chat-msg-agent">'
            f'<div class="chat-msg-avatar"><svg class="icon icon-sm"><use href="#icon-bot"/></svg></div>'
            f'<div class="chat-msg-body">'
            f'<div class="chat-msg-sender">{html_mod.escape(proj.name)}</div>'
            f'<div class="chat-msg-text md-rendered">{rendered}</div>'
            f'{tools_html}'
            f'</div></div>'
        )
        return HTMLResponse(user_html + agent_html)
    return HTMLResponse(user_html)


# ── Conversation Management ──────────────────────────────────────

@router.post("/api/projects/{project_id}/conversations")
async def create_conversation(request: Request, project_id: str):
    """Create a new conversation session for a project."""
    from ..sessions.store import get_session_store, SessionDef
    from ..projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    store = get_session_store()
    # Archive any existing active CHAT sessions (not workflow sessions)
    active = [s for s in store.list_all()
              if s.project_id == project_id and s.status == "active"
              and not (s.config or {}).get("workflow_id")]
    for s in active:
        store.update_status(s.id, "completed")

    session = store.create(SessionDef(
        name=f"{proj.name} — {datetime.utcnow().strftime('%b %d, %H:%M')}",
        goal="Project conversation",
        project_id=project_id,
        status="active",
        config={"lead_agent": proj.lead_agent_id or "brain"},
    ))
    return JSONResponse({"session_id": session.id})


# ── Streaming Chat (SSE) ────────────────────────────────────────

@router.post("/api/projects/{project_id}/chat/stream")
async def project_chat_stream(request: Request, project_id: str):
    """Stream agent response via SSE — shows live progress to the user."""
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..sessions.runner import _build_context
    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store
    from ..agents.executor import get_executor, ExecutionContext

    form = await request.form()
    content = str(form.get("content", "")).strip()
    session_id = str(form.get("session_id", "")).strip()
    if not content:
        return HTMLResponse("")

    proj = get_project_store().get(project_id)
    if not proj:
        return HTMLResponse("Project not found", status_code=404)

    store = get_session_store()
    session = None
    if session_id:
        session = store.get(session_id)
    if not session:
        sessions = [s for s in store.list_all() if s.project_id == project_id and s.status == "active"]
        sessions.sort(key=lambda s: s.created_at or "", reverse=True)
        if sessions:
            session = sessions[0]
    if not session:
        session = store.create(SessionDef(
            name=f"{proj.name} — {datetime.utcnow().strftime('%b %d, %H:%M')}",
            goal="Project conversation",
            project_id=project_id,
            status="active",
            config={"lead_agent": proj.lead_agent_id or "brain"},
        ))

    # Store user message
    store.add_message(MessageDef(
        session_id=session.id, from_agent="user",
        message_type="text", content=content,
    ))

    # Find agent
    agent_store = get_agent_store()
    agent_id = proj.lead_agent_id or "brain"
    agent = agent_store.get(agent_id)
    if not agent:
        all_agents = agent_store.list_all()
        agent = all_agents[0] if all_agents else None

    async def event_generator():
        import html as html_mod
        import markdown as md_lib

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield sse("status", {"label": "Thinking…"})

        if not agent:
            yield sse("error", {"message": "No agent available"})
            return

        try:
            # Build context
            ctx = await _build_context(agent, session)

            # Progress callback — called by executor for each tool invocation
            progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

            async def on_tool_call(name: str, args: dict, result: str):
                # RLM sub-events: args contains {"status": "label"}
                if name == "deep_search" and isinstance(args, dict) and "status" in args:
                    label = args["status"]
                    await progress_queue.put(("status", name, label))
                    return
                labels = {
                    "deep_search": "Deep search…",
                    "code_read": "Reading files…",
                    "code_search": "Searching code…",
                    "git_log": "Checking git…",
                    "git_diff": "Checking diff…",
                    "memory_search": "Searching memory…",
                    "memory_store": "Storing to memory…",
                }
                label = labels.get(name, f"{name}…")
                await progress_queue.put(("tool", name, label))

            ctx.on_tool_call = on_tool_call

            # Run executor with streaming
            executor = get_executor()
            result = None
            accumulated_content = ""

            async for event_type_s, data_s in executor.run_streaming(ctx, content):
                if event_type_s == "delta":
                    accumulated_content += data_s
                    yield sse("chunk", {"text": data_s})
                elif event_type_s == "result":
                    result = data_s

            if not result:
                yield sse("error", {"message": "No response from agent"})
                return

            # Store agent message
            store.add_message(MessageDef(
                session_id=session.id,
                from_agent=agent.id,
                to_agent="user",
                message_type="text",
                content=result.content,
                metadata={
                    "model": result.model,
                    "provider": result.provider,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "duration_ms": result.duration_ms,
                    "tool_calls": result.tool_calls if result.tool_calls else None,
                },
            ))

            # Build final HTML
            rendered = md_lib.markdown(
                str(result.content),
                extensions=["fenced_code", "tables", "nl2br"]
            )
            yield sse("done", {"html": rendered})

        except Exception as exc:
            logger.exception("Streaming chat error")
            yield sse("error", {"message": str(exc)[:200]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/api/sessions/{session_id}/stream")
async def session_sse_stream(request: Request, session_id: str):
    """SSE stream for live session updates (messages, status changes)."""
    import asyncio
    from ..sessions.runner import add_sse_listener, remove_sse_listener

    queue = add_sse_listener(session_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    payload = json.dumps(event) if isinstance(event, dict) else str(event)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            remove_sse_listener(session_id, queue)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Memory API ───────────────────────────────────────────────────

@router.get("/api/memory/stats")
async def memory_stats():
    """Memory layer statistics."""
    from ..memory.manager import get_memory_manager
    return JSONResponse(get_memory_manager().stats())


@router.get("/api/memory/project/{project_id}")
async def project_memory(project_id: str, q: str = "", category: str = ""):
    """Get or search project memory."""
    from ..memory.manager import get_memory_manager
    mem = get_memory_manager()
    if q:
        entries = mem.project_search(project_id, q)
    else:
        entries = mem.project_get(project_id, category=category or None)
    return JSONResponse(entries)


@router.get("/api/memory/global")
async def global_memory(category: str = ""):
    """Get global memory entries."""
    from ..memory.manager import get_memory_manager
    entries = get_memory_manager().global_get(category=category or None)
    return JSONResponse(entries)


@router.get("/api/memory/search")
async def memory_search(q: str = ""):
    """Search across all memory layers."""
    from ..memory.manager import get_memory_manager
    if not q:
        return HTMLResponse('<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Tapez une requête…</div>')
    mem = get_memory_manager()
    results = mem.global_search(q, limit=20)
    if not results:
        return HTMLResponse(f'<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Aucun résultat pour "{q}"</div>')
    html = ""
    for r in results:
        cat = r.get("category", "")
        conf = r.get("confidence", 0)
        html += f'''<div class="mem-entry">
            <div><span class="mem-badge {cat}">{cat}</span> <span class="mem-key">{r.get("key","")}</span></div>
            <div class="mem-val">{str(r.get("value",""))[:300]}</div>
            <div class="mem-meta"><span>{int(conf*100)}% confidence</span></div>
        </div>'''
    return HTMLResponse(html)


# ── Retrospectives & Self-Improvement ────────────────────────────

@router.get("/api/retrospectives")
async def list_retrospectives(scope: str = "", limit: int = 20):
    """List retrospectives, optionally filtered by scope."""
    from ..db.migrations import get_db
    db = get_db()
    try:
        if scope:
            rows = db.execute(
                "SELECT * FROM retrospectives WHERE scope=? ORDER BY created_at DESC LIMIT ?",
                (scope, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM retrospectives ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return JSONResponse([{
            "id": r["id"], "scope": r["scope"], "scope_id": r["scope_id"],
            "successes": json.loads(r["successes"] or "[]"),
            "failures": json.loads(r["failures"] or "[]"),
            "lessons": json.loads(r["lessons"] or "[]"),
            "improvements": json.loads(r["improvements"] or "[]"),
            "metrics": json.loads(r["metrics_json"] or "{}"),
            "created_at": r["created_at"] or "",
        } for r in rows])
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.post("/api/retrospectives/generate")
async def generate_retrospective(request: Request):
    """Auto-generate a retrospective from session/ideation data using LLM."""
    from ..db.migrations import get_db
    from ..llm.client import get_llm_client, LLMMessage
    from ..memory.manager import get_memory_manager
    import uuid

    data = await request.json()
    scope = data.get("scope", "session")
    scope_id = data.get("scope_id", "")

    db = get_db()
    context_parts = []
    try:
        # Gather context based on scope
        if scope == "ideation" and scope_id:
            msgs = db.execute(
                "SELECT agent_name, role, content FROM ideation_messages WHERE session_id=? ORDER BY created_at",
                (scope_id,),
            ).fetchall()
            findings = db.execute(
                "SELECT type, text FROM ideation_findings WHERE session_id=?",
                (scope_id,),
            ).fetchall()
            context_parts.append(f"Ideation session {scope_id}:")
            for m in msgs:
                role_str = f" ({m['role']})" if "role" in m.keys() and m["role"] else ""
                context_parts.append(f"  {m['agent_name']}{role_str}: {m['content'][:200]}")
            for f in findings:
                context_parts.append(f"  Finding [{f['type']}]: {f['text']}")

        elif scope == "project" and scope_id:
            # Gather tool calls, sessions, and mission data
            tool_rows = db.execute(
                "SELECT tool_name, success, result FROM tool_calls WHERE session_id IN "
                "(SELECT id FROM sessions WHERE id LIKE ?) ORDER BY created_at DESC LIMIT 50",
                (f"%{scope_id}%",),
            ).fetchall()
            for t in tool_rows:
                status = "✅" if t["success"] else "❌"
                context_parts.append(f"  Tool {t['tool_name']}: {status} {(t['result'] or '')[:100]}")

        elif scope == "global":
            # Aggregate all recent tool calls + sessions
            tool_rows = db.execute(
                "SELECT tool_name, success, COUNT(*) as cnt FROM tool_calls "
                "GROUP BY tool_name, success ORDER BY cnt DESC LIMIT 30"
            ).fetchall()
            for t in tool_rows:
                status = "✅" if t["success"] else "❌"
                context_parts.append(f"  Tool {t['tool_name']}: {status} × {t['cnt']}")
    except Exception:
        pass
    finally:
        db.close()

    if not context_parts:
        context_parts = ["No detailed data available — generate a general retrospective about the platform usage."]

    context = "\n".join(context_parts)

    # LLM generates the retrospective
    retro_prompt = f"""Analyse cette activité et génère une rétrospective structurée.

Contexte:
{context}

Produis un JSON:
{{
  "successes": ["Ce qui a bien fonctionné (3-5 items)"],
  "failures": ["Ce qui a échoué ou peut être amélioré (2-4 items)"],
  "lessons": ["Leçons apprises, patterns identifiés (3-5 items)"],
  "improvements": ["Actions concrètes d'amélioration pour la prochaine itération (2-4 items)"]
}}

Sois CONCRET et ACTIONNABLE. Pas de généralités.
Réponds UNIQUEMENT avec le JSON."""

    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=retro_prompt)],
            system_prompt="Tu es un coach Agile expert en rétrospectives SAFe.",
            temperature=0.5, max_tokens=2048,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        retro_data = json.loads(raw)
    except Exception as e:
        retro_data = {
            "successes": ["Retrospective generation completed"],
            "failures": [f"LLM parsing issue: {str(e)[:100]}"],
            "lessons": ["Auto-retrospective needs more structured data"],
            "improvements": ["Add more instrumentation to sessions"],
        }

    retro_id = str(uuid.uuid4())[:8]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO retrospectives (id, scope, scope_id, successes, failures, lessons, improvements) VALUES (?,?,?,?,?,?,?)",
            (retro_id, scope, scope_id,
             json.dumps(retro_data.get("successes", []), ensure_ascii=False),
             json.dumps(retro_data.get("failures", []), ensure_ascii=False),
             json.dumps(retro_data.get("lessons", []), ensure_ascii=False),
             json.dumps(retro_data.get("improvements", []), ensure_ascii=False)),
        )
        db.commit()

        # Feed lessons into global memory for recursive self-improvement
        mem = get_memory_manager()
        for lesson in retro_data.get("lessons", []):
            mem.global_store(
                key=f"lesson:{scope}:{scope_id}",
                value=lesson,
                category="lesson",
                project_id=scope_id if scope == "project" else "",
                confidence=0.7,
            )
        for improvement in retro_data.get("improvements", []):
            mem.global_store(
                key=f"improvement:{scope}:{scope_id}",
                value=improvement,
                category="improvement",
                project_id=scope_id if scope == "project" else "",
                confidence=0.8,
            )
    finally:
        db.close()

    return JSONResponse({"id": retro_id, **retro_data})


@router.get("/api/projects/{project_id}/git", response_class=HTMLResponse)
async def api_project_git(request: Request, project_id: str):
    """Git panel partial (HTMX)."""
    from ..projects.manager import get_project_store
    from ..projects import git_service
    project = get_project_store().get(project_id)
    if not project:
        return HTMLResponse("")
    git = git_service.get_status(project.path) if project.has_git else None
    commits = git_service.get_log(project.path, 10) if project.has_git else []
    changes = git_service.get_changes(project.path) if project.has_git else []
    return _templates(request).TemplateResponse("partials/git_panel.html", {
        "request": request, "git": git, "commits": commits, "changes": changes,
    })


@router.get("/api/projects/{project_id}/tasks", response_class=HTMLResponse)
async def api_project_tasks(request: Request, project_id: str):
    """Task panel partial (HTMX)."""
    from ..projects import factory_tasks
    tasks = factory_tasks.get_task_summary(project_id)
    recent = factory_tasks.get_recent_tasks(project_id, 15)
    return _templates(request).TemplateResponse("partials/task_panel.html", {
        "request": request, "tasks": tasks, "recent_tasks": recent,
    })


# ── API: Agents ──────────────────────────────────────────────────

@router.get("/api/agents")
async def api_agents():
    """List all agents (JSON)."""
    from ..agents.store import get_agent_store
    agents = get_agent_store().list_all()
    return JSONResponse([{
        "id": a.id, "name": a.name, "role": a.role,
        "provider": a.provider, "model": a.model,
        "description": a.description, "icon": a.icon,
        "color": a.color, "tags": a.tags, "is_builtin": a.is_builtin,
    } for a in agents])


@router.get("/api/llm/providers")
async def api_providers():
    """List LLM providers with availability (JSON)."""
    from ..llm.client import get_llm_client
    client = get_llm_client()
    providers = client.available_providers()
    return JSONResponse(providers)


@router.post("/api/skills/reload")
async def reload_skills():
    """Hot-reload skill definitions."""
    from ..skills.loader import get_skill_loader
    count = get_skill_loader().reload()
    return {"reloaded": count}


@router.post("/api/skills/github/add")
async def add_github_skill_source(request: Request):
    """Add a GitHub repo as skill source."""
    from ..skills.library import get_skill_library
    form = await request.form()
    repo = str(form.get("repo", "")).strip()
    path = str(form.get("path", "")).strip()
    branch = str(form.get("branch", "main")).strip() or "main"
    if not repo or "/" not in repo:
        return HTMLResponse(
            '<div class="alert alert-error">Invalid repo format. Use owner/repo</div>',
            status_code=400,
        )
    library = get_skill_library()
    result = library.add_github_source(repo, path, branch)
    if result.get("errors"):
        errs = "; ".join(result["errors"])
        return HTMLResponse(
            f'<div class="gh-sync-result error"><svg class="icon icon-xs"><use href="#icon-alert-triangle"/></svg> {repo}: {errs}</div>'
        )
    return HTMLResponse(
        f'<div class="gh-sync-result success"><svg class="icon icon-xs"><use href="#icon-check"/></svg> {repo}: {result["fetched"]} skills fetched</div>'
    )


@router.post("/api/skills/github/sync")
async def sync_github_skills():
    """Sync all GitHub skill sources via git clone (runs in thread)."""
    import asyncio
    from ..skills.library import get_skill_library
    library = get_skill_library()
    results = await asyncio.get_event_loop().run_in_executor(None, library.sync_all_github)
    total = sum(r.get("fetched", 0) for r in results)
    errors = [e for r in results for e in r.get("errors", [])]
    if errors:
        return HTMLResponse(
            f'<div class="gh-sync-result">Synced {total} skills, {len(errors)} errors</div>'
        )
    return HTMLResponse(
        f'<div class="gh-sync-result success"><svg class="icon icon-xs"><use href="#icon-check"/></svg> Synced {total} skills from {len(results)} repos</div>'
    )


@router.post("/api/skills/github/remove")
async def remove_github_skill_source(request: Request):
    """Remove a GitHub skill source."""
    from ..skills.library import get_skill_library
    form = await request.form()
    repo = str(form.get("repo", "")).strip()
    if repo:
        get_skill_library().remove_github_source(repo)
    return HTMLResponse("")


# ── Team Generator ───────────────────────────────────────────────

@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    """Team & Workflow Generator page."""
    return _templates(request).TemplateResponse("generate.html", {
        "request": request,
        "page_title": "Team Generator",
    })


@router.post("/api/generate-team")
async def generate_team(request: Request):
    """Generate team + workflow from natural language prompt, launch it."""
    from ..generators.team import TeamGenerator

    form = await request.form()
    prompt = str(form.get("prompt", "")).strip()
    if not prompt:
        return HTMLResponse('<div class="msg-system-text">❌ Prompt requis</div>', status_code=400)

    try:
        gen = TeamGenerator()
        result = await gen.generate(prompt)

        # Launch workflow in background
        from ..workflows.store import get_workflow_store, run_workflow
        wf = get_workflow_store().get(result["workflow_id"])
        if wf:
            asyncio.create_task(_run_workflow_background(
                wf, result["session_id"],
                result["spec"].mission_goal,
                "",
            ))

        return JSONResponse({
            "session_id": result["session_id"],
            "workflow_id": result["workflow_id"],
            "team_size": result["team_size"],
            "agents": result["agents"],
            "redirect": f"/sessions/{result['session_id']}/live",
        })
    except Exception as e:
        logger.error("Team generation failed: %s", e, exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ── DORA Metrics ─────────────────────────────────────────────────

@router.get("/metrics", response_class=HTMLResponse)
async def dora_dashboard_page(request: Request):
    """DORA Metrics dashboard page."""
    from ..metrics.dora import get_dora_metrics
    from ..projects.manager import get_project_store

    projects = get_project_store().list_all()
    project_id = request.query_params.get("project", "")
    period = int(request.query_params.get("period", "30"))

    dora = get_dora_metrics()
    summary = dora.summary(project_id, period)
    trend = dora.trend(project_id, weeks=12)

    return _templates(request).TemplateResponse("dora_dashboard.html", {
        "request": request,
        "page_title": "DORA Metrics",
        "projects": projects,
        "selected_project": project_id,
        "period": period,
        "dora": summary,
        "trend": trend,
    })


@router.get("/api/metrics/dora/{project_id}")
async def dora_api(request: Request, project_id: str):
    """DORA metrics JSON API."""
    from ..metrics.dora import get_dora_metrics
    period = int(request.query_params.get("period", "30"))
    pid = "" if project_id == "all" else project_id
    return JSONResponse(get_dora_metrics().summary(pid, period))


# ── RBAC ─────────────────────────────────────────────────────────

@router.get("/api/rbac/agent/{agent_id}")
async def rbac_agent_permissions(agent_id: str):
    """Get RBAC permissions for an agent."""
    from ..rbac import agent_permissions_summary, get_agent_category
    return JSONResponse({
        "agent_id": agent_id,
        "category": get_agent_category(agent_id),
        "permissions": agent_permissions_summary(agent_id),
    })


@router.get("/api/rbac/check")
async def rbac_check(request: Request):
    """Check a specific permission. Query: ?actor=agent_id&type=agent&artifact=code&action=create"""
    from ..rbac import check_agent_permission, check_human_permission
    actor = request.query_params.get("actor", "")
    actor_type = request.query_params.get("type", "agent")
    artifact = request.query_params.get("artifact", "")
    action = request.query_params.get("action", "")

    if actor_type == "agent":
        ok, reason = check_agent_permission(actor, artifact, action)
    else:
        ok, reason = check_human_permission(actor, artifact, action)

    return JSONResponse({"allowed": ok, "reason": reason})


# ── DSI Board ────────────────────────────────────────────────────

@router.get("/dsi", response_class=HTMLResponse)
async def dsi_board_page(request: Request):
    """DSI strategic dashboard — kanban pipeline + KPIs."""
    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store
    from ..missions.store import get_mission_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    mission_store = get_mission_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = mission_store.list_missions()

    # KPIs
    active_missions = sum(1 for m in all_missions if m.status == "active")
    blocked_missions = sum(1 for m in all_missions if m.status == "blocked")
    total_tasks = 0
    total_done = 0
    for m in all_missions:
        stats = mission_store.mission_stats(m.id)
        total_tasks += stats.get("total", 0)
        total_done += stats.get("done", 0)

    # Pipeline kanban columns
    project_names = {p.id: p.name for p in all_projects}
    statuses = [
        ("backlog", "Backlog", "planning"),
        ("planning", "Planning", "planning"),
        ("active", "En cours", "active"),
        ("review", "Review", "completed"),
        ("completed", "Terminé", "completed"),
    ]
    pipeline = []
    for status_key, label, match_status in statuses:
        col_missions = []
        # "backlog" = missions in planning with no sprint
        if status_key == "backlog":
            for m in all_missions:
                if m.status == "planning":
                    sprints = mission_store.list_sprints(m.id)
                    if not sprints:
                        stats = mission_store.mission_stats(m.id)
                        col_missions.append({
                            "id": m.id, "name": m.name,
                            "project_name": project_names.get(m.project_id, m.project_id),
                            "wsjf": m.wsjf_score, "total": stats.get("total", 0),
                            "done": stats.get("done", 0),
                        })
        elif status_key == "planning":
            for m in all_missions:
                if m.status == "planning":
                    sprints = mission_store.list_sprints(m.id)
                    if sprints:
                        stats = mission_store.mission_stats(m.id)
                        col_missions.append({
                            "id": m.id, "name": m.name,
                            "project_name": project_names.get(m.project_id, m.project_id),
                            "wsjf": m.wsjf_score, "total": stats.get("total", 0),
                            "done": stats.get("done", 0),
                        })
        elif status_key == "review":
            # Missions with status "completed" but also any "review" sprints
            for m in all_missions:
                sprints = mission_store.list_sprints(m.id)
                if any(s.status == "review" for s in sprints) and m.status == "active":
                    stats = mission_store.mission_stats(m.id)
                    col_missions.append({
                        "id": m.id, "name": m.name,
                        "project_name": project_names.get(m.project_id, m.project_id),
                        "wsjf": m.wsjf_score, "total": stats.get("total", 0),
                        "done": stats.get("done", 0),
                    })
        else:
            for m in all_missions:
                if m.status == match_status:
                    # Skip those already in backlog/planning/review
                    if status_key == "active":
                        sprints = mission_store.list_sprints(m.id)
                        if any(s.status == "review" for s in sprints):
                            continue
                    stats = mission_store.mission_stats(m.id)
                    col_missions.append({
                        "id": m.id, "name": m.name,
                        "project_name": project_names.get(m.project_id, m.project_id),
                        "wsjf": m.wsjf_score, "total": stats.get("total", 0),
                        "done": stats.get("done", 0),
                    })
        pipeline.append({"status": status_key, "label": label, "missions": col_missions})

    # Resource allocation per project
    resources = []
    project_colors = ["var(--purple)", "var(--blue)", "var(--green)", "var(--yellow)", "var(--red)", "#06b6d4", "#8b5cf6"]
    for i, p in enumerate(all_projects):
        p_missions = [m for m in all_missions if m.project_id == p.id]
        p_active = sum(1 for m in p_missions if m.status == "active")
        if p_missions:
            resources.append({
                "name": p.name,
                "total": len(p_missions),
                "active": p_active,
                "pct": round(p_active / max(len(p_missions), 1) * 100),
                "color": project_colors[i % len(project_colors)],
            })

    # Strategic agents
    avatar_dir = Path(__file__).parent / "static" / "avatars"
    strategic = []
    for a in all_agents:
        if any(t == "strategy" for t in (a.tags or [])):
            jpg = avatar_dir / f"{a.id}.jpg"
            svg_f = avatar_dir / f"{a.id}.svg"
            avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
            strategic.append({
                "id": a.id, "name": a.name, "role": a.role,
                "avatar": a.avatar or a.icon or "bot", "color": a.color or "#7c3aed",
                "avatar_url": avatar_url,
                "description": a.description or "",
                "tagline": a.tagline or "",
                "persona": a.persona or "",
                "motivation": a.motivation or "",
                "skills": a.skills or [],
                "tools": a.tools or [],
                "mcps": a.mcps or [],
                "model": a.model or "",
                "provider": getattr(a, "provider", "") or "",
            })

    # Recent session messages for decisions feed
    from ..sessions.store import get_session_store
    session_store = get_session_store()
    recent_sessions = session_store.list_all(limit=5)
    decisions = []
    for sess in recent_sessions:
        msgs = session_store.get_messages(sess.id, limit=3)
        for msg in msgs:
            if msg.from_agent != "user" and len(msg.content) > 20:
                decisions.append({
                    "session_name": sess.name or sess.id[:8],
                    "agent_name": msg.from_agent or "Agent",
                    "content": msg.content[:120],
                    "time": msg.timestamp[:16] if msg.timestamp else "",
                    "status": "approved",
                })
        if len(decisions) >= 6:
            break

    # Workflow patterns for system map
    from ..workflows.store import get_workflow_store
    wf_store = get_workflow_store()
    all_workflows = wf_store.list_all()
    system_patterns = []
    for wf in all_workflows:
        cfg = wf.config or {}
        graph = cfg.get("graph", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        pattern = wf.phases[0].pattern_id if wf.phases else "sequential"
        system_patterns.append({
            "id": wf.id, "name": wf.name,
            "pattern": pattern,
            "node_count": len(nodes),
            "edge_count": len(edges),
        })

    # DORA metrics
    from ..metrics.dora import get_dora_metrics
    dora = get_dora_metrics().summary(period_days=30)

    # Org summary
    from ..agents.org import get_org_store
    org = get_org_store()
    org_portfolios = org.list_portfolios()
    org_arts = org.list_arts()
    org_teams = org.list_teams()

    return _templates(request).TemplateResponse("dsi.html", {
        "request": request, "page_title": "Vue DSI",
        "total_missions": len(all_missions),
        "active_missions": active_missions,
        "blocked_missions": blocked_missions,
        "total_tasks": total_tasks,
        "total_done": total_done,
        "total_agents": len(all_agents),
        "total_projects": len(all_projects),
        "pipeline": pipeline,
        "resources": resources,
        "strategic_agents": strategic,
        "decisions": decisions,
        "system_patterns": system_patterns,
        "dora": dora,
        "org_portfolios": len(org_portfolios),
        "org_arts": len(org_arts),
        "org_teams": len(org_teams),
    })


# ── DSI Workflow Phases ──────────────────────────────────────────

@router.get("/dsi/workflow/{workflow_id}", response_class=HTMLResponse)
async def dsi_workflow_page(request: Request, workflow_id: str):
    """DSI workflow with phased timeline, agent graph, and message feed."""
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    from pathlib import Path

    wf_store = get_workflow_store()
    session_store = get_session_store()
    agent_store = get_agent_store()

    wf = wf_store.get(workflow_id)
    if not wf:
        return HTMLResponse("<h2>Workflow introuvable</h2>", 404)

    cfg = wf.config or {}
    graph_cfg = cfg.get("graph", {})
    # Phases from WorkflowPhase objects (phases_json) or fallback to config
    if wf.phases:
        phases_cfg = []
        for wp in wf.phases:
            pc = wp.config or {}
            phases_cfg.append({
                "id": wp.id, "name": wp.name, "pattern_id": wp.pattern_id,
                "gate": wp.gate, "description": wp.description,
                "agents": pc.get("agents", []), "leader": pc.get("leader", ""),
                "deliverables": pc.get("deliverables", []),
            })
    else:
        phases_cfg = cfg.get("phases", [])
    avatar_dir = Path(__file__).parent / "static" / "avatars"

    # Find active session for this workflow
    all_sessions = session_store.list_all(limit=50)
    session = None
    for s in all_sessions:
        s_cfg = s.config or {}
        if s_cfg.get("workflow_id") == workflow_id:
            session = s
            break

    # Determine current phase from session config
    current_phase_id = None
    phase_statuses = {}
    if session:
        s_cfg = session.config or {}
        current_phase_id = s_cfg.get("current_phase", phases_cfg[0]["id"] if phases_cfg else None)
        phase_statuses = s_cfg.get("phase_statuses", {})

    # Build phases list with status
    phase_colors = ["#a855f7", "#3b82f6", "#f59e0b", "#34d399"]
    phases = []
    current_phase = None
    current_phase_idx = 0
    for i, p in enumerate(phases_cfg):
        status = phase_statuses.get(p["id"], "waiting")
        if current_phase_id and p["id"] == current_phase_id:
            status = "active"
            current_phase_idx = i
        elif current_phase_id:
            idx_current = next((j for j, pp in enumerate(phases_cfg) if pp["id"] == current_phase_id), 0)
            if i < idx_current:
                status = "done"
        phase_data = {
            "id": p["id"], "name": p["name"], "pattern_id": p.get("pattern_id", ""),
            "gate": p.get("gate", ""), "description": p.get("description", ""),
            "agents": p.get("agents", []), "leader": p.get("leader", ""),
            "deliverables": p.get("deliverables", []), "status": status,
            "color": phase_colors[i % len(phase_colors)],
        }
        phases.append(phase_data)
        if status == "active":
            current_phase = phase_data

    if not current_phase and phases:
        current_phase = phases[0]
        current_phase["status"] = "active"
        current_phase_idx = 0

    # Build phase agents
    phase_agents = []
    if current_phase:
        for aid in current_phase["agents"]:
            a = agent_store.get(aid)
            if a:
                jpg = avatar_dir / f"{a.id}.jpg"
                svg_f = avatar_dir / f"{a.id}.svg"
                avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
                phase_agents.append({
                    "id": a.id, "name": a.name, "role": a.role,
                    "avatar_url": avatar_url,
                    "color": a.color or "#7c3aed",
                    "is_leader": aid == current_phase.get("leader"),
                    "status": "idle",
                })

    # Deliverables for current phase
    deliverables = []
    if current_phase:
        for d in current_phase.get("deliverables", []):
            deliverables.append({"label": d, "done": False})

    # Messages from session
    messages = []
    agent_names = {}
    # Build agent_map for unified message component
    dsi_agent_map = {}
    def _resolve_agent(aid):
        if aid and aid not in agent_names:
            a = agent_store.get(aid)
            if a:
                jpg = avatar_dir / f"{a.id}.jpg"
                svg_f = avatar_dir / f"{a.id}.svg"
                agent_names[aid] = {
                    "name": a.name,
                    "avatar_url": f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else ""),
                }
                dsi_agent_map[aid] = {"name": a.name, "icon": a.icon or "bot", "color": a.color or "#8b949e", "role": a.role or "", "avatar": getattr(a, "avatar", "bot"), "avatar_url": _avatar_url(a.id)}
            else:
                agent_names[aid] = {"name": aid, "avatar_url": ""}
        return agent_names.get(aid, {"name": aid or "?", "avatar_url": ""})

    if session:
        all_msgs = session_store.get_messages(session.id, limit=100)
        for msg in all_msgs:
            if msg.message_type == "system" or msg.from_agent == "system":
                continue
            content = (msg.content or "").strip()
            if not content:
                continue
            from_info = _resolve_agent(msg.from_agent)
            to_info = _resolve_agent(msg.to_agent) if msg.to_agent else None
            action = None
            if "[DELEGATE" in content:
                action = "delegate"
            elif "[VETO" in content:
                action = "veto"
            elif "[APPROVE" in content:
                action = "approve"
            # Clean action tags from display content
            import re as _re
            display = _re.sub(r'\[DELEGATE:[^\]]*\]\s*', '', content)
            display = _re.sub(r'\[VETO[^\]]*\]\s*', '', display)
            display = _re.sub(r'\[APPROVE\]\s*', '', display)
            display = _re.sub(r'\[ASK:[^\]]*\]\s*', '', display)
            display = _re.sub(r'\[ESCALATE[^\]]*\]\s*', '', display)
            display = display.strip()[:800]
            messages.append({
                "from_name": from_info["name"],
                "from_id": msg.from_agent,
                "avatar_url": from_info["avatar_url"],
                "to_name": to_info["name"] if to_info else None,
                "to_id": msg.to_agent,
                "content": display,
                "time": (msg.timestamp or "")[:16],
                "action": action,
                "message_type": msg.message_type,
            })

    # Build graph nodes with positions
    graph_nodes_cfg = graph_cfg.get("nodes", [])
    graph_edges_cfg = graph_cfg.get("edges", [])

    # Map node positions — remap Y to fit phase bands
    phase_y_bands = {"p1-cadrage": 55, "p2-architecture": 145, "p3-sprint-setup": 240, "p4-delivery": 335}
    node_positions = {}
    graph_nodes = []
    for n in graph_nodes_cfg:
        node_phases = (n.get("phase") or "").split(",")
        primary_phase = node_phases[0] if node_phases else ""
        phase_color = "#7c3aed"
        y = n.get("y", 100)
        if primary_phase in phase_y_bands:
            y = phase_y_bands[primary_phase]
            idx = list(phase_y_bands.keys()).index(primary_phase)
            phase_color = phase_colors[idx % len(phase_colors)]
        # Scale x to fit 850px viewbox
        x = max(40, min(810, n.get("x", 400)))

        a = agent_store.get(n.get("agent_id", ""))
        avatar_url = ""
        if a:
            jpg = avatar_dir / f"{a.id}.jpg"
            svg_f = avatar_dir / f"{a.id}.svg"
            avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")

        is_active = current_phase and n.get("agent_id") in current_phase.get("agents", [])
        node_positions[n["id"]] = (x, y)
        graph_nodes.append({
            "id": n["id"], "agent_id": n.get("agent_id", ""),
            "x": x, "y": y, "label": n.get("label", ""),
            "phase_color": phase_color, "avatar_url": avatar_url,
            "is_active": is_active,
        })

    # Build graph edges
    graph_edges = []
    for e in graph_edges_cfg:
        from_pos = node_positions.get(e["from"])
        to_pos = node_positions.get(e["to"])
        if from_pos and to_pos:
            graph_edges.append({
                "x1": from_pos[0], "y1": from_pos[1],
                "x2": to_pos[0], "y2": to_pos[1],
                "color": e.get("color", "#7c3aed"),
            })

    # All agents JSON for popover
    all_agents_json = {}
    for a in agent_store.list_all():
        jpg = avatar_dir / f"{a.id}.jpg"
        svg_f = avatar_dir / f"{a.id}.svg"
        avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
        all_agents_json[a.id] = {
            "name": a.name, "role": a.role,
            "avatar_url": avatar_url,
            "color": a.color or "#7c3aed",
            "description": a.description or "",
            "tagline": a.tagline or "",
            "persona": a.persona or "",
            "motivation": a.motivation or "",
            "skills": a.skills or [],
            "tools": a.tools or [],
        }

    return _templates(request).TemplateResponse("dsi_workflow.html", {
        "request": request, "page_title": f"DSI — {wf.name}",
        "workflow": wf,
        "phases": phases,
        "current_phase": current_phase,
        "current_phase_idx": current_phase_idx,
        "phase_agents": phase_agents,
        "deliverables": deliverables,
        "messages": messages,
        "agent_map": dsi_agent_map,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "session": session,
        "session_id": session.id if session else None,
        "all_agents_json": all_agents_json,
    })


@router.api_route("/api/dsi/workflow/{workflow_id}/start", methods=["GET", "POST"], response_class=HTMLResponse)
async def dsi_workflow_start(request: Request, workflow_id: str):
    """Start phase 1 of a DSI workflow — creates session and launches agents."""
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store, SessionDef
    from ..agents.loop import get_loop_manager
    from ..a2a.bus import get_bus
    import uuid

    wf_store = get_workflow_store()
    wf = wf_store.get(workflow_id)
    if not wf:
        return HTMLResponse("Workflow introuvable", 404)

    cfg = wf.config or {}
    # Read phases from wf.phases (WorkflowPhase objects), fallback to config
    if wf.phases:
        phases = []
        for p in wf.phases:
            pd = {"id": p.id, "name": p.name, "description": p.description,
                  "pattern_id": p.pattern_id, "gate": p.gate}
            pd.update(p.config or {})
            phases.append(pd)
    else:
        phases = cfg.get("phases", [])
    if not phases:
        return HTMLResponse("Pas de phases", 400)

    phase1 = phases[0]
    project_id = cfg.get("project_id", "")

    # Create session
    session_store = get_session_store()
    session = SessionDef(
        name=f"{wf.name} — {phase1['name']}",
        description=wf.description,
        project_id=project_id,
        status="active",
        goal=phase1.get("description", ""),
        config={
            "workflow_id": workflow_id,
            "current_phase": phase1["id"],
            "phase_statuses": {phase1["id"]: "active"},
        },
    )
    session = session_store.create(session)

    # Start agent loops for phase 1
    manager = get_loop_manager()
    bus = get_bus()
    # Load project for path
    from ..projects.manager import get_project_store
    project = get_project_store().get(project_id)
    project_path = project.path if project and project.path else ""
    for aid in phase1.get("agents", []):
        await manager.start_agent(aid, session.id, project_id=project_id, project_path=project_path)

    # Send kickoff message to the leader
    leader = phase1.get("leader", phase1.get("agents", [""])[0] if phase1.get("agents") else "")
    if leader:
        # Load project VISION if exists
        vision = ""
        if project and project.path:
            import os
            vision_path = os.path.join(project.path, "VISION.md")
            if os.path.exists(vision_path):
                with open(vision_path, "r") as f:
                    vision = f.read()[:3000]

        kickoff = f"""🚀 **Phase 1 : {phase1['name']}**

**Objectif:** {phase1.get('description', '')}

**Livrables attendus:** {', '.join(phase1.get('deliverables', []))}

**Équipe disponible:** {', '.join(phase1.get('agents', []))}

**Pattern:** {phase1.get('pattern_id', 'hierarchical')}

{f'**VISION du projet:**{chr(10)}{vision}' if vision else ''}

**INSTRUCTIONS:**
1. Vous êtes le leader de cette phase. Coordonnez votre équipe.
2. Utilisez `[DELEGATE:agent_id] instruction` pour assigner des tâches aux membres de l'équipe.
3. Utilisez les outils `deep_search` et `code_read` pour analyser le code source du projet.
4. Produisez chaque livrable de façon concrète et détaillée.
5. Quand tous les livrables sont prêts, utilisez `[APPROVE]` pour valider la phase.
6. Si un problème bloque, utilisez `[ESCALATE]` pour remonter.

Commencez par analyser la situation et déléguer les premières tâches."""

        from ..models import A2AMessage, MessageType
        msg = A2AMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            from_agent="user",
            to_agent=leader,
            message_type=MessageType.REQUEST,
            content=kickoff,
        )
        await bus.publish(msg)

    from starlette.responses import RedirectResponse
    return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)


@router.get("/api/debug/agents")
async def debug_agents():
    """Debug endpoint: show running agent loops and their status."""
    from ..agents.loop import get_loop_manager
    manager = get_loop_manager()
    import asyncio
    result = []
    for key, loop in manager._loops.items():
        task_done = loop._task.done() if loop._task else True
        task_exception = None
        if task_done and loop._task:
            try:
                exc = loop._task.exception()
                task_exception = str(exc) if exc else None
            except (asyncio.CancelledError, asyncio.InvalidStateError):
                pass
        result.append({
            "key": key,
            "agent_id": loop.agent.id,
            "session_id": loop.session_id,
            "status": loop.status.value,
            "task_done": task_done,
            "task_exception": task_exception,
            "inbox_size": loop._inbox.qsize(),
            "messages_sent": loop.instance.messages_sent,
            "messages_received": loop.instance.messages_received,
            "tokens_used": loop.instance.tokens_used,
        })
    return JSONResponse(result)


@router.api_route("/api/dsi/workflow/{workflow_id}/next-phase", methods=["GET", "POST"], response_class=HTMLResponse)
async def dsi_workflow_next_phase(request: Request, workflow_id: str):
    """Advance to next phase in workflow."""
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store
    from ..agents.loop import get_loop_manager
    from ..a2a.bus import get_bus
    import uuid

    if request.method == "POST":
        form = await request.form()
        session_id = form.get("session_id", "")
    else:
        session_id = request.query_params.get("session_id", "")

    wf_store = get_workflow_store()
    session_store = get_session_store()
    wf = wf_store.get(workflow_id)
    session = session_store.get_session(session_id)
    if not wf or not session:
        return HTMLResponse("Not found", 404)

    cfg = wf.config or {}
    # Read phases from wf.phases (WorkflowPhase objects), fallback to config
    if wf.phases:
        phases = []
        for p in wf.phases:
            pd = {"id": p.id, "name": p.name, "description": p.description,
                  "pattern_id": p.pattern_id, "gate": p.gate}
            pd.update(p.config or {})
            phases.append(pd)
    else:
        phases = cfg.get("phases", [])
    s_cfg = session.config or {}
    current_phase_id = s_cfg.get("current_phase", "")
    phase_statuses = s_cfg.get("phase_statuses", {})

    # Find next phase
    current_idx = next((i for i, p in enumerate(phases) if p["id"] == current_phase_id), 0)
    if current_idx >= len(phases) - 1:
        from starlette.responses import RedirectResponse
        return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)

    # Mark current as done, advance
    phase_statuses[current_phase_id] = "done"
    next_phase = phases[current_idx + 1]
    phase_statuses[next_phase["id"]] = "active"
    s_cfg["current_phase"] = next_phase["id"]
    s_cfg["phase_statuses"] = phase_statuses

    # Update session
    from ..db.migrations import get_db
    import json
    db = get_db()
    db.execute("UPDATE sessions SET config_json=?, name=? WHERE id=?",
               (json.dumps(s_cfg), f"{wf.name} — {next_phase['name']}", session_id))
    db.commit()

    # Stop old loops, start new ones
    manager = get_loop_manager()
    await manager.stop_session(session_id)
    project_id = cfg.get("project_id", "")
    from ..projects.manager import get_project_store
    project = get_project_store().get(project_id) if project_id else None
    project_path = project.path if project and project.path else ""
    for aid in next_phase.get("agents", []):
        await manager.start_agent(aid, session_id, project_id=project_id, project_path=project_path)

    # Send kickoff to new phase leader
    leader = next_phase.get("leader", next_phase["agents"][0] if next_phase["agents"] else "")
    if leader:
        kickoff = f"""🚀 **Phase {current_idx + 2} : {next_phase['name']}**

**Objectif:** {next_phase.get('description', '')}

**Livrables attendus:** {', '.join(next_phase.get('deliverables', []))}

**Équipe:** {', '.join(next_phase.get('agents', []))}

La phase précédente est terminée. Prenez le relais et produisez les livrables de cette phase.
Utilisez [DELEGATE:agent_id] pour assigner des tâches."""

        from ..models import A2AMessage, MessageType
        msg = A2AMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            from_agent="user",
            to_agent=leader,
            message_type=MessageType.REQUEST,
            content=kickoff,
        )
        bus = get_bus()
        await bus.publish(msg)

    from starlette.responses import RedirectResponse
    return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)


# ── Vue Métier ───────────────────────────────────────────────────

@router.get("/metier", response_class=HTMLResponse)
async def metier_page(request: Request):
    """Vue Métier — business process flows by department."""
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    import random

    wf_store = get_workflow_store()
    session_store = get_session_store()
    all_workflows = wf_store.list_all()
    all_sessions = session_store.list_all()

    # Build department swim lanes from workflows
    dept_map = {
        "Sales": {"color": "var(--blue)", "icon": "trending-up", "workflows": []},
        "Supply Chain": {"color": "var(--green)", "icon": "truck", "workflows": []},
        "Support": {"color": "var(--yellow)", "icon": "headphones", "workflows": []},
    }
    for wf in all_workflows:
        pattern = wf.phases[0].pattern_id if wf.phases else "sequential"
        entry = {"name": wf.name, "pattern": pattern}
        # Distribute workflows across departments
        if "migration" in wf.id or "pipeline" in wf.id:
            dept_map["Supply Chain"]["workflows"].append(entry)
        elif "review" in wf.id or "debate" in wf.id:
            dept_map["Support"]["workflows"].append(entry)
        else:
            dept_map["Sales"]["workflows"].append(entry)

    departments = []
    for dept_name, dept_data in dept_map.items():
        nodes = []
        # Agent node
        nodes.append({"type": "agent", "icon": dept_data["icon"], "label": dept_name, "active": True})
        nodes.append({"type": "agent", "icon": "layers", "label": "Sequential", "active": False})
        nodes.append({"type": "agent", "icon": "users", "label": "Agent", "active": False})
        # Pattern box
        if dept_data["workflows"]:
            patterns = ", ".join(set(w["pattern"] for w in dept_data["workflows"]))
            nodes.append({"type": "pattern", "label": f"Patterns\n{patterns.title()}", "active": False})
        nodes.append({"type": "agent", "icon": "check-circle", "label": "Agent", "active": False})
        departments.append({
            "name": dept_name,
            "nodes": nodes,
            "efficiency": random.randint(55, 95),
            "color": dept_data["color"],
        })

    # Productivity
    total_efficiency = sum(d["efficiency"] for d in departments) // max(len(departments), 1)

    # Calendar heatmap (31 days)
    calendar_days = []
    for i in range(1, 32):
        level = random.choice([0, 0, 1, 1, 2, 3, 4]) if i <= 28 else random.choice([0, 1])
        calendar_days.append({"num": i, "level": level})

    return _templates(request).TemplateResponse("metier.html", {
        "request": request, "page_title": "Vue Métier",
        "departments": departments,
        "productivity_pct": total_efficiency,
        "calendar_days": calendar_days,
    })


# ── Product Management ───────────────────────────────────────────

@router.get("/product", response_class=HTMLResponse)
async def product_page(request: Request):
    """Product backlog — Epic → Feature → User Story hierarchy."""
    from ..missions.store import get_mission_store
    from ..missions.product import get_product_backlog
    from ..projects.manager import get_project_store

    mission_store = get_mission_store()
    backlog = get_product_backlog()
    project_store = get_project_store()

    all_projects = project_store.list_all()
    all_missions = mission_store.list_missions()
    filter_project = request.query_params.get("project", "")

    if filter_project:
        all_missions = [m for m in all_missions if m.project_id == filter_project]

    project_names = {p.id: p.name for p in all_projects}

    # Build epic → features → stories tree
    epics = []
    total_features = 0
    total_stories = 0
    total_points = 0
    total_done_stories = 0

    for m in all_missions:
        features = backlog.list_features(m.id)
        epic_features = []
        epic_points = 0
        epic_stories = 0
        epic_done = 0

        for f in features:
            stories = backlog.list_stories(f.id)
            f_points = f.story_points or sum(s.story_points for s in stories)
            epic_points += f_points
            epic_stories += len(stories)
            epic_done += sum(1 for s in stories if s.status == "done")
            total_stories += len(stories)
            total_points += f_points

            epic_features.append({
                "id": f.id, "name": f.name, "status": f.status,
                "story_points": f_points, "assigned_to": f.assigned_to,
                "stories": [{"id": s.id, "title": s.title, "status": s.status,
                             "story_points": s.story_points} for s in stories],
            })

        total_features += len(features)
        total_done_stories += epic_done

        epics.append({
            "id": m.id, "name": m.name, "status": m.status,
            "project_name": project_names.get(m.project_id, m.project_id),
            "features": epic_features,
            "total_points": epic_points,
            "total_stories": epic_stories,
            "done_pct": round(epic_done / max(epic_stories, 1) * 100),
        })

    done_pct = round(total_done_stories / max(total_stories, 1) * 100)

    return _templates(request).TemplateResponse("product.html", {
        "request": request, "page_title": "Product",
        "epics": epics,
        "projects": all_projects,
        "filter_project": filter_project,
        "summary": {
            "epics": len(epics),
            "features": total_features,
            "stories": total_stories,
            "total_points": total_points,
            "done_pct": done_pct,
        },
    })


# ── Ideation Workspace ───────────────────────────────────────────

_IDEATION_AGENTS = [
    {"id": "metier", "name": "Camille Durand", "short_role": "Business Analyst", "color": "#2563eb"},
    {"id": "architecte", "name": "Pierre Duval", "short_role": "Solution Architect", "color": "#0891b2"},
    {"id": "ux_designer", "name": "Chloé Bertrand", "short_role": "UX Designer", "color": "#8b5cf6"},
    {"id": "securite", "name": "Nadia Benali", "short_role": "Sécurité", "color": "#dc2626"},
    {"id": "product_manager", "name": "Alexandre Faure", "short_role": "Product Manager", "color": "#16a34a"},
]


@router.get("/ideation", response_class=HTMLResponse)
async def ideation_page(request: Request):
    """Ideation workspace — brainstorm with expert agents."""
    from ..agents.store import get_agent_store
    from ..projects.manager import get_project_store

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    avatar_dir = Path(__file__).parent / "static" / "avatars"

    # Map DB agents by id for enrichment
    db_map = {a.id: a for a in all_agents}

    enriched = []
    for ia in _IDEATION_AGENTS:
        a = db_map.get(ia["id"])
        jpg = avatar_dir / f"{ia['id']}.jpg"
        svg_f = avatar_dir / f"{ia['id']}.svg"
        avatar_url = f"/static/avatars/{ia['id']}.jpg" if jpg.exists() else (f"/static/avatars/{ia['id']}.svg" if svg_f.exists() else "")
        enriched.append({
            **ia,
            "avatar_url": avatar_url,
            "description": (a.description or "") if a else "",
            "tagline": (a.tagline or "") if a else "",
            "persona": (a.persona or "") if a else "",
            "motivation": (a.motivation or "") if a else "",
            "skills": (a.skills or []) if a else [],
            "tools": (a.tools or []) if a else [],
            "mcps": (a.mcps or []) if a else [],
            "model": (a.model or "") if a else "",
            "provider": (getattr(a, "provider", "") or "") if a else "",
        })

    # Load past ideation sessions for sidebar
    from ..db.migrations import get_db as _gdb
    _db = _gdb()
    try:
        _rows = _db.execute(
            "SELECT id, title, status, created_at FROM ideation_sessions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        past_sessions = [{"id": r["id"], "title": r["title"], "status": r["status"],
                          "created_at": r["created_at"] or ""} for r in _rows]
    except Exception:
        past_sessions = []
    finally:
        _db.close()

    return _templates(request).TemplateResponse("ideation.html", {
        "request": request, "page_title": "Idéation",
        "agents": enriched,
        "projects": [{"id": p.id, "name": p.name} for p in get_project_store().list_all()],
        "past_sessions": past_sessions,
    })


@router.post("/api/ideation")
async def ideation_submit(request: Request):
    """Launch a REAL multi-agent ideation via the pattern engine (network pattern).

    Creates a session, builds a network pattern with the 5 ideation agents,
    launches run_pattern() in background. The frontend listens via SSE.
    Returns the session_id immediately so the frontend can connect to SSE.
    """
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..patterns.engine import run_pattern
    from ..patterns.store import PatternDef
    import uuid

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return JSONResponse({"error": "Prompt requis"}, status_code=400)

    session_id = data.get("session_id", "") or str(uuid.uuid4())[:8]

    # Create a real session
    session_store = get_session_store()
    existing = session_store.get(session_id)
    if not existing:
        session = SessionDef(
            id=session_id,
            name=f"Idéation: {prompt[:60]}",
            goal=prompt,
            status="active",
            config={"type": "ideation", "pattern": "network"},
        )
        session = session_store.create(session)
    else:
        session = existing

    # Store user message
    session_store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        message_type="delegate",
        content=prompt,
    ))

    # Build a network pattern with the 5 ideation agents
    agent_nodes = []
    agent_ids = []
    for ia in _IDEATION_AGENTS:
        agent_nodes.append({"id": ia["id"], "agent_id": ia["id"]})
        agent_ids.append(ia["id"])

    # Build bidirectional edges between all debaters + report edges to PO
    edges = []
    debaters = [a for a in agent_ids if a != "product_manager"]
    for i, a in enumerate(debaters):
        for b in debaters[i+1:]:
            edges.append({"from": a, "to": b, "type": "bidirectional"})
    # All debaters report to product_manager (judge)
    for a in debaters:
        edges.append({"from": a, "to": "product_manager", "type": "report"})

    pattern = PatternDef(
        id=f"ideation-{session_id}",
        name="Idéation multi-expert",
        type="network",
        agents=agent_nodes,
        edges=edges,
        config={"max_rounds": 2},
    )

    # Launch pattern in background — small delay lets SSE connect first
    async def _run_ideation():
        try:
            await asyncio.sleep(0.5)  # Let frontend SSE connect before first events
            await run_pattern(pattern, session_id, prompt)
        except Exception as e:
            logger.error("Ideation pattern failed: %s", e)
            session_store.add_message(MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"Erreur idéation: {e}",
            ))

    asyncio.create_task(_run_ideation())

    return JSONResponse({
        "session_id": session_id,
        "status": "started",
        "sse_url": f"/api/sessions/{session_id}/sse",
    })


_PO_EPIC_SYSTEM = """Tu es Alexandre Faure, Product Owner senior.
Tu reçois la synthèse d'un atelier d'idéation et tu dois structurer un projet complet.

À partir de l'idée et des analyses des experts, produis un JSON avec:
1. Le projet (nom, description, stack technique, factory_type)
2. L'epic principal (nom, description, critères d'acceptation)
3. 3 à 5 features découpées depuis l'epic
4. 2 à 3 user stories par feature (format "En tant que... je veux... afin de...")
5. L'équipe proposée (rôles nécessaires)

Réponds UNIQUEMENT avec ce JSON:
{
  "project": {
    "id": "slug-kebab-case",
    "name": "Nom du Projet",
    "description": "Description courte",
    "stack": ["SvelteKit", "Rust", "PostgreSQL"],
    "factory_type": "sf"
  },
  "epic": {
    "name": "Nom de l'Epic",
    "description": "Description détaillée de l'epic",
    "goal": "Critères d'acceptation clairs et mesurables"
  },
  "features": [
    {
      "name": "Nom Feature",
      "description": "Description",
      "acceptance_criteria": "Given/When/Then",
      "story_points": 8,
      "stories": [
        {
          "title": "En tant que [persona] je veux [action] afin de [bénéfice]",
          "description": "Détails",
          "acceptance_criteria": "Given/When/Then",
          "story_points": 3
        }
      ]
    }
  ],
  "team": [
    {"role": "lead_dev", "label": "Lead Developer"},
    {"role": "developer", "label": "Développeur Backend"},
    {"role": "developer", "label": "Développeur Frontend"},
    {"role": "tester", "label": "QA Engineer"},
    {"role": "devops", "label": "DevOps"},
    {"role": "security", "label": "Expert Sécurité"}
  ]
}

Sois pragmatique et concret. Les features doivent être actionnables.
Réponds UNIQUEMENT avec le JSON, rien d'autre."""


@router.post("/api/ideation/create-epic")
async def ideation_create_epic(request: Request):
    """PO agent structures project + epic + features + stories from ideation."""
    import subprocess as _sp
    from ..llm.client import get_llm_client, LLMMessage
    from ..missions.store import get_mission_store, MissionDef
    from ..missions.product import get_product_backlog, FeatureDef, UserStoryDef
    from ..projects.manager import get_project_store, Project
    from ..config import FACTORY_ROOT

    data = await request.json()
    idea = data.get("goal", "") or data.get("name", "")
    findings = data.get("description", "")

    # ── Step 1: PO agent structures via LLM ──
    client = get_llm_client()
    prompt = f"Idée originale:\n{idea}\n\nAnalyses des experts:\n{findings}"
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt=_PO_EPIC_SYSTEM,
            temperature=0.5,
            max_tokens=4096,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        plan = json.loads(raw)
    except Exception as e:
        logger.error("PO epic structuring failed: %s", e)
        slug = idea[:30].lower().replace(" ", "-").replace("'", "")
        slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
        plan = {
            "project": {"id": slug or "new-project", "name": idea[:60] or "New Project",
                        "description": idea, "stack": [], "factory_type": "standalone"},
            "epic": {"name": data.get("name", idea[:100]),
                     "description": findings, "goal": idea},
            "features": [], "team": [],
        }

    proj_data = plan.get("project", {})
    epic_data = plan.get("epic", {})
    features_data = plan.get("features", [])
    team_data = plan.get("team", [])

    # ── Step 2 & 3: Create project or use existing ──
    existing_project_id = data.get("project_id", "").strip()
    project_store = get_project_store()

    if existing_project_id:
        # Use existing project
        project_id = existing_project_id
        existing = project_store.get(project_id)
        project_name = existing.name if existing else project_id
        stack = proj_data.get("stack", [])
    else:
        # Create new project directory + git init
        project_id = proj_data.get("id", "new-project")
        project_path = str(FACTORY_ROOT.parent / project_id)
        proj_dir = Path(project_path)
        vision_content = ""

        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
            for d in ("src", "tests", "docs"):
                (proj_dir / d).mkdir(exist_ok=True)

            stack = proj_data.get("stack", [])
            vision_content = f"# {proj_data.get('name', project_id)}\n\n"
            vision_content += f"## Vision\n\n{proj_data.get('description', '')}\n\n"
            vision_content += f"## Epic: {epic_data.get('name', '')}\n\n{epic_data.get('description', '')}\n\n"
            vision_content += f"## Objectifs\n\n{epic_data.get('goal', '')}\n\n"
            if features_data:
                vision_content += "## Features\n\n"
                for f in features_data:
                    vision_content += f"- **{f.get('name', '')}**: {f.get('description', '')}\n"
            vision_content += f"\n## Stack technique\n\n{', '.join(stack)}\n"
            (proj_dir / "VISION.md").write_text(vision_content, encoding="utf-8")

            readme = f"# {proj_data.get('name', project_id)}\n\n{proj_data.get('description', '')}\n\n"
            readme += f"Stack: {', '.join(stack)}\n"
            (proj_dir / "README.md").write_text(readme, encoding="utf-8")

            if not (proj_dir / ".git").exists():
                _sp.run(["git", "init"], cwd=str(proj_dir), capture_output=True, timeout=10)
                _sp.run(["git", "add", "."], cwd=str(proj_dir), capture_output=True, timeout=10)
                _sp.run(["git", "commit", "-m", "Initial commit from ideation"],
                        cwd=str(proj_dir), capture_output=True, timeout=10)
        except Exception as e:
            logger.warning("Project dir creation: %s", e)

        project = Project(
            id=project_id,
            name=proj_data.get("name", project_id),
            path=project_path,
            description=proj_data.get("description", ""),
            factory_type=proj_data.get("factory_type", "standalone"),
            domains=[s.lower() for s in stack],
            vision=vision_content,
            values=["quality", "feedback", "tdd"],
            lead_agent_id="product_manager",
            agents=[t.get("role", "") for t in team_data],
            status="active",
        )
        project_store.create(project)
        project_name = project.name

    # ── Step 4: Create epic (mission) with type & workflow routing ──
    request_type = data.get("request_type", "new_project")
    type_map = {
        "new_project": "epic", "new_feature": "feature", "bug_fix": "bug",
        "tech_debt": "debt", "migration": "migration", "security_audit": "security",
    }
    workflow_map = {
        "new_project": "ideation-to-prod", "new_feature": "feature-request",
        "bug_fix": "sf-pipeline", "tech_debt": "tech-debt-reduction",
        "migration": "migration-sharelook", "security_audit": "review-cycle",
    }
    mission_type = type_map.get(request_type, "epic")
    workflow_id = workflow_map.get(request_type, "feature-request")
    po = data.get("po_proposal", {})

    mission_store = get_mission_store()
    mission = MissionDef(
        name=epic_data.get("name", "Epic from ideation"),
        description=epic_data.get("description", ""),
        goal=epic_data.get("goal", ""),
        status="planning",
        type=mission_type,
        project_id=project_id,
        workflow_id=workflow_id,
        wsjf_score=po.get("priority_wsjf", 0),
        created_by="product_manager",
        config={"team": team_data, "stack": stack, "idea": idea,
                "request_type": request_type, "po_proposal": po},
    )
    mission = mission_store.create_mission(mission)

    # ── Step 5: Create features + user stories ──
    backlog = get_product_backlog()
    created_features = []
    for fd in features_data:
        feat = backlog.create_feature(FeatureDef(
            epic_id=mission.id,
            name=fd.get("name", ""),
            description=fd.get("description", ""),
            acceptance_criteria=fd.get("acceptance_criteria", ""),
            story_points=fd.get("story_points", 5),
        ))
        stories_out = []
        for sd in fd.get("stories", []):
            story = backlog.create_story(UserStoryDef(
                feature_id=feat.id,
                title=sd.get("title", ""),
                description=sd.get("description", ""),
                acceptance_criteria=sd.get("acceptance_criteria", ""),
                story_points=sd.get("story_points", 3),
            ))
            stories_out.append({"id": story.id, "title": story.title,
                                "points": story.story_points})
        created_features.append({"id": feat.id, "name": feat.name,
                                 "points": feat.story_points, "stories": stories_out})

    # ── Step 6: Link ideation session → epic ──
    ideation_sid = data.get("session_id", "")
    if ideation_sid:
        from ..db.migrations import get_db as _get_db
        db = _get_db()
        try:
            db.execute(
                "UPDATE ideation_sessions SET status='epic_created', mission_id=?, project_id=? WHERE id=?",
                (mission.id, project_id, ideation_sid),
            )
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    # ── Step 7: Populate project memory (wiki-like knowledge) ──
    try:
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        if stack:
            mem.project_store(project_id, "stack", ", ".join(stack),
                              category="architecture", source="ideation", confidence=0.9)
        mem.project_store(project_id, "epic", epic_data.get("name", ""),
                          category="vision", source="ideation", confidence=0.9)
        if epic_data.get("goal"):
            mem.project_store(project_id, "goal", epic_data["goal"],
                              category="vision", source="ideation", confidence=0.9)
        for t in team_data:
            mem.project_store(project_id, f"team:{t.get('role','')}",
                              t.get("justification", ""),
                              category="team", source="ideation", confidence=0.8)
        mem.project_store(project_id, "workflow", workflow_id,
                          category="process", source="ideation", confidence=0.85)
        for fd in features_data:
            mem.project_store(project_id, f"feature:{fd.get('name','')}",
                              fd.get("description", ""),
                              category="backlog", source="ideation", confidence=0.85)
        if ideation_sid:
            from ..db.migrations import get_db as _gdb2
            _db2 = _gdb2()
            try:
                findings_rows = _db2.execute(
                    "SELECT type, text FROM ideation_findings WHERE session_id=?",
                    (ideation_sid,),
                ).fetchall()
                for fr in findings_rows:
                    cat = "risk" if fr["type"] == "risk" else "opportunity" if fr["type"] == "opportunity" else "decision"
                    mem.project_store(project_id, f"{fr['type']}:{fr['text'][:50]}",
                                      fr["text"], category=cat, source="ideation", confidence=0.75)
            except Exception:
                pass
            finally:
                _db2.close()
    except Exception as e:
        logger.warning("Memory auto-populate: %s", e)

    # ── Step 8: Auto-launch workflow (agents take over) ──
    session_id_live = None
    try:
        from ..sessions.store import get_session_store, SessionDef, MessageDef
        from ..workflows.store import get_workflow_store

        wf_store = get_workflow_store()
        wf = wf_store.get(workflow_id)
        if wf:
            session_store = get_session_store()
            session = SessionDef(
                name=f"{mission.name}",
                goal=mission.goal or mission.description or "",
                project_id=project_id,
                status="active",
                config={"workflow_id": workflow_id, "mission_id": mission.id},
            )
            session = session_store.create(session)
            session_store.add_message(MessageDef(
                session_id=session.id,
                from_agent="system",
                message_type="system",
                content=f"Workflow **{wf.name}** lancé pour l'epic **{mission.name}**.\nStack: {', '.join(stack)}\nGoal: {mission.goal or 'N/A'}",
            ))
            task_desc = (
                f"Projet: {project_name}\n"
                f"Epic: {mission.name}\n"
                f"Goal: {mission.goal or mission.description}\n"
                f"Stack: {', '.join(stack)}\n"
                f"Features: {', '.join(f.get('name','') for f in features_data)}\n"
                f"Répertoire projet: {str(FACTORY_ROOT.parent / project_id)}"
            )
            asyncio.create_task(_run_workflow_background(wf, session.id, task_desc, project_id))
            session_id_live = session.id
            logger.info("Auto-launched workflow %s for project %s (session %s)", workflow_id, project_id, session.id)
    except Exception as e:
        logger.warning("Auto-launch workflow: %s", e)

    return JSONResponse({
        "project_id": project_id,
        "project_name": project_name,
        "mission_id": mission.id,
        "mission_name": mission.name,
        "type": mission_type,
        "workflow_id": workflow_id,
        "features": created_features,
        "team": team_data,
        "stack": stack,
        "session_id": session_id_live,
        "redirect": f"/sessions/{session_id_live}/live" if session_id_live else f"/projects/{project_id}/overview",
    })


# ── Ideation History ─────────────────────────────────────────────

@router.get("/api/ideation/sessions")
async def ideation_sessions_list():
    """List all ideation sessions (most recent first)."""
    from ..db.migrations import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM ideation_sessions ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return JSONResponse([{
            "id": r["id"], "title": r["title"], "prompt": r["prompt"],
            "status": r["status"], "mission_id": r["mission_id"] or "",
            "project_id": r["project_id"] or "",
            "created_at": r["created_at"] or "",
        } for r in rows])
    finally:
        db.close()


@router.get("/api/ideation/sessions/{session_id}")
async def ideation_session_detail(session_id: str):
    """Get full ideation session with messages and findings."""
    from ..db.migrations import get_db
    db = get_db()
    try:
        sess = db.execute(
            "SELECT * FROM ideation_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not sess:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        messages = db.execute(
            "SELECT * FROM ideation_messages WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        findings = db.execute(
            "SELECT * FROM ideation_findings WHERE session_id=?", (session_id,),
        ).fetchall()
        return JSONResponse({
            "id": sess["id"], "title": sess["title"], "prompt": sess["prompt"],
            "status": sess["status"], "mission_id": sess["mission_id"] or "",
            "project_id": sess["project_id"] or "",
            "created_at": sess["created_at"] or "",
            "messages": [{"agent_id": m["agent_id"], "agent_name": m["agent_name"],
                          "role": m["role"] if "role" in m.keys() else "",
                          "target": m["target"] if "target" in m.keys() else "",
                          "content": m["content"], "color": m["color"],
                          "avatar_url": m["avatar_url"] or "",
                          "created_at": m["created_at"] or ""} for m in messages],
            "findings": [{"type": f["type"], "text": f["text"]} for f in findings],
        })
    finally:
        db.close()


@router.get("/ideation/history", response_class=HTMLResponse)
async def ideation_history_page(request: Request):
    """Dedicated ideation history page."""
    from ..db.migrations import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM ideation_sessions ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        sessions = []
        for r in rows:
            msg_count = db.execute(
                "SELECT COUNT(*) as c FROM ideation_messages WHERE session_id=?",
                (r["id"],),
            ).fetchone()["c"]
            finding_count = db.execute(
                "SELECT COUNT(*) as c FROM ideation_findings WHERE session_id=?",
                (r["id"],),
            ).fetchone()["c"]
            sessions.append({
                "id": r["id"], "title": r["title"], "prompt": r["prompt"],
                "status": r["status"], "mission_id": r["mission_id"] or "",
                "project_id": r["project_id"] or "",
                "created_at": r["created_at"] or "",
                "msg_count": msg_count, "finding_count": finding_count,
            })
    finally:
        db.close()
    return _templates(request).TemplateResponse("ideation_history.html", {
        "request": request, "page_title": "Historique Idéation",
        "sessions": sessions,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  MISSION CONTROL — CDP orchestrator dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/missions", response_class=HTMLResponse)
async def missions_list_page(request: Request):
    """List all mission runs."""
    from ..missions.store import get_mission_run_store
    store = get_mission_run_store()
    runs = store.list_runs(limit=50)
    return _templates(request).TemplateResponse("missions.html", {
        "request": request, "page_title": "Mission Control",
        "runs": runs,
    })


@router.get("/missions/start/{workflow_id}", response_class=HTMLResponse)
async def mission_start_page(request: Request, workflow_id: str):
    """Start a new mission — show brief form."""
    from ..workflows.store import get_workflow_store
    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return RedirectResponse("/missions", status_code=302)
    return _templates(request).TemplateResponse("mission_start.html", {
        "request": request, "page_title": f"New Mission — {wf.name}",
        "workflow": wf,
    })


@router.post("/api/missions/start")
async def api_mission_start(request: Request):
    """Create a mission run and start the CDP agent."""
    from ..missions.store import get_mission_run_store
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store, SessionDef, MessageDef
    from ..agents.loop import get_loop_manager
    from ..agents.store import get_agent_store
    from ..models import PhaseRun, PhaseStatus, MissionRun, MissionStatus
    import uuid
    from datetime import datetime

    form = await request.form()
    workflow_id = str(form.get("workflow_id", ""))
    brief = str(form.get("brief", "")).strip()
    project_id = str(form.get("project_id", ""))

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    if not brief:
        return JSONResponse({"error": "Brief is required"}, status_code=400)

    # Build phase runs from workflow
    phases = []
    for wp in wf.phases:
        phases.append(PhaseRun(
            phase_id=wp.id,
            phase_name=wp.name,
            pattern_id=wp.pattern_id,
            status=PhaseStatus.PENDING,
        ))

    mission_id = uuid.uuid4().hex[:8]
    mission = MissionRun(
        id=mission_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief,
        status=MissionStatus.RUNNING,
        phases=phases,
        project_id=project_id or None,
        created_at=datetime.utcnow(),
    )

    run_store = get_mission_run_store()
    run_store.create(mission)

    # Create a session for the CDP agent
    session_store = get_session_store()
    session_id = uuid.uuid4().hex[:8]
    session_store.create(SessionDef(
        id=session_id,
        name=f"Mission: {wf.name}",
        workflow_id=workflow_id,
        project_id=project_id or None,
        status="active",
    ))
    # Update mission with session_id
    mission.session_id = session_id
    run_store.update(mission)

    # Send the brief as initial message
    session_store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        to_agent="chef_de_programme",
        message_type="request",
        content=brief,
    ))

    # Start the CDP agent loop
    mgr = get_loop_manager()
    try:
        await mgr.start_agent("chef_de_programme", session_id, project_id or "", "")
    except Exception as e:
        logger.error("Failed to start CDP agent: %s", e)

    return JSONResponse({"mission_id": mission_id, "session_id": session_id,
                         "redirect": f"/missions/{mission_id}/control"})


@router.get("/missions/{mission_id}/control", response_class=HTMLResponse)
async def mission_control_page(request: Request, mission_id: str):
    """Mission Control dashboard — pipeline visualization + CDP activity."""
    from ..missions.store import get_mission_run_store
    from ..agents.store import get_agent_store

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return RedirectResponse("/missions", status_code=302)

    # Build agent map for avatars
    agents = get_agent_store().list()
    agent_map = _agent_map_for_template(agents)

    return _templates(request).TemplateResponse("mission_control.html", {
        "request": request,
        "page_title": f"Mission Control — {mission.workflow_name}",
        "mission": mission,
        "agent_map": agent_map,
        "session_id": mission.session_id or "",
    })


@router.get("/api/missions/{mission_id}")
async def api_mission_status(request: Request, mission_id: str):
    """Get mission status as JSON."""
    from ..missions.store import get_mission_run_store
    store = get_mission_run_store()
    mission = store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(mission.model_dump(mode="json"))


@router.post("/api/missions/{mission_id}/validate")
async def api_mission_validate(request: Request, mission_id: str):
    """Human validates a checkpoint (GO/NOGO/PIVOT)."""
    from ..missions.store import get_mission_run_store
    from ..sessions.store import get_session_store, MessageDef
    from ..a2a.bus import get_bus
    from ..models import A2AMessage, MessageType, PhaseStatus

    form = await request.form()
    decision = str(form.get("decision", "GO")).upper()

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Update phase status
    if mission.current_phase:
        for p in mission.phases:
            if p.phase_id == mission.current_phase and p.status == PhaseStatus.WAITING_VALIDATION:
                p.status = PhaseStatus.DONE if decision == "GO" else PhaseStatus.FAILED
        run_store.update(mission)

    # Send decision to CDP agent via bus
    if mission.session_id:
        session_store = get_session_store()
        session_store.add_message(MessageDef(
            session_id=mission.session_id,
            from_agent="user",
            to_agent="chef_de_programme",
            message_type="response",
            content=f"DECISION: {decision}",
        ))
        # Also publish to bus for agent loop
        bus = get_bus()
        import uuid
        from datetime import datetime
        await bus.publish(A2AMessage(
            id=uuid.uuid4().hex[:8],
            session_id=mission.session_id,
            from_agent="user",
            to_agent="chef_de_programme",
            message_type=MessageType.RESPONSE,
            content=f"DECISION: {decision}",
            timestamp=datetime.utcnow(),
        ))

    return JSONResponse({"decision": decision, "phase": mission.current_phase})
