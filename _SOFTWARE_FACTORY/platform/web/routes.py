"""Web routes — HTMX-driven pages and API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Workspace file serving (screenshots, artifacts) ──
@router.get("/workspace/{path:path}")
async def serve_workspace_file(path: str):
    """Serve files from project workspaces (screenshots, artifacts)."""
    from ..config import FACTORY_ROOT
    workspaces = FACTORY_ROOT / "data" / "workspaces"
    # Direct match: /workspace/{mission_id}/screenshots/file.png
    for base in [workspaces, FACTORY_ROOT.parent]:
        full_path = base / path
        if full_path.exists() and full_path.is_file():
            import mimetypes
            media = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
            return FileResponse(str(full_path), media_type=media)
    # Fallback: search across all workspace subdirectories
    if workspaces.exists():
        for ws_dir in workspaces.iterdir():
            if ws_dir.is_dir():
                full_path = ws_dir / path
                if full_path.exists() and full_path.is_file():
                    import mimetypes
                    media = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
                    return FileResponse(str(full_path), media_type=media)
    return JSONResponse({"error": "Not found"}, status_code=404)


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
                "hierarchy_rank": getattr(a, "hierarchy_rank", 50),
                "tagline": getattr(a, "tagline", "") or "",
                "skills": getattr(a, "skills", []) or [],
                "tools": getattr(a, "tools", []) or [],
                "persona": getattr(a, "persona", "") or "",
                "motivation": getattr(a, "motivation", "") or "",
            }
        elif isinstance(a, dict):  # already a dict
            aid = a.get("id", "")
            m[aid] = {
                "name": a.get("name", ""), "icon": a.get("icon", "bot"),
                "color": a.get("color", "#8b949e"), "role": a.get("role", ""),
                "avatar": a.get("avatar", "bot"),
                "avatar_url": a.get("avatar_url", "") or _avatar_url(aid),
                "hierarchy_rank": a.get("hierarchy_rank", 50),
                "tagline": a.get("tagline", ""),
                "skills": a.get("skills", []),
                "tools": a.get("tools", []),
                "persona": a.get("persona", ""),
                "motivation": a.get("motivation", ""),
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
        "active_tab": request.query_params.get("tab", "overview"),
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


# ── SAFe consolidated pages (tabbed) ─────────────────────────────

@router.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request, tab: str = "backlog"):
    """Backlog — Product + Discovery (ideation) in tabs."""
    return _templates(request).TemplateResponse("backlog.html", {
        "request": request, "page_title": "Backlog",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/pi", response_class=HTMLResponse)
async def pi_board_page(request: Request):
    """PI Board — Epics + Control in tabs."""
    return _templates(request).TemplateResponse("pi_board.html", {
        "request": request, "page_title": "PI Board",
    })

@router.get("/ceremonies", response_class=HTMLResponse)
async def ceremonies_page(request: Request, tab: str = "templates"):
    """Ceremonies — Workflow templates + Patterns in tabs."""
    return _templates(request).TemplateResponse("ceremonies.html", {
        "request": request, "page_title": "Ceremonies",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/live", response_class=HTMLResponse)
async def live_page(request: Request):
    """Live — redirect to sessions list."""
    from starlette.responses import RedirectResponse
    return RedirectResponse("/sessions", status_code=302)

@router.get("/live/{session_id}", response_class=HTMLResponse)
async def live_session_page(request: Request, session_id: str):
    """Live ceremony — redirect to session live view."""
    from starlette.responses import RedirectResponse
    return RedirectResponse(f"/sessions/{session_id}/live", status_code=302)

@router.get("/art", response_class=HTMLResponse)
async def art_page(request: Request, tab: str = "agents"):
    """ART — Agents + Organisation + Generator in tabs."""
    return _templates(request).TemplateResponse("art.html", {
        "request": request, "page_title": "ART",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/toolbox", response_class=HTMLResponse)
async def toolbox_page(request: Request, tab: str = "skills"):
    """Toolbox — Skills + Memory + MCPs in tabs."""
    return _templates(request).TemplateResponse("toolbox.html", {
        "request": request, "page_title": "Toolbox",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/design-system", response_class=HTMLResponse)
async def design_system_page(request: Request):
    """Design System — tokens, colors, icons, atoms, molecules, patterns."""
    import re
    # Extract icon names from SVG sprites
    sprites_path = Path(__file__).resolve().parent / "templates" / "partials" / "svg_sprites.html"
    icons = []
    if sprites_path.exists():
        text = sprites_path.read_text()
        icons = re.findall(r'id="icon-([^"]+)"', text)
    return _templates(request).TemplateResponse("design_system.html", {
        "request": request, "page_title": "Design System",
        "icons": icons,
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
        "request": request, "page_title": "PI Board",
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
        "request": request, "page_title": "PI",
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
        "page_title": "Live",
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


@router.post("/api/memory/global")
async def global_memory_store(request: Request):
    """Store a global memory entry."""
    from ..memory.manager import get_memory_manager
    data = await request.json()
    cat = data.get("category", "general")
    key = data.get("key", "")
    val = data.get("value", "")
    if not key or not val:
        return JSONResponse({"error": "key and value required"}, status_code=400)
    get_memory_manager().global_store(key, val, category=cat, confidence=data.get("confidence", 0.8))
    return JSONResponse({"ok": True})


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
                status = "OK" if t["success"] else "FAIL"
                context_parts.append(f"  Tool {t['tool_name']}: {status} {(t['result'] or '')[:100]}")

        elif scope == "global":
            # Aggregate all recent tool calls + sessions
            tool_rows = db.execute(
                "SELECT tool_name, success, COUNT(*) as cnt FROM tool_calls "
                "GROUP BY tool_name, success ORDER BY cnt DESC LIMIT 30"
            ).fetchall()
            for t in tool_rows:
                status = "OK" if t["success"] else "FAIL"
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


@router.get("/api/projects/{project_id}/si-blueprint")
async def api_get_si_blueprint(project_id: str):
    """Read SI blueprint for a project."""
    import yaml
    bp_path = Path(__file__).resolve().parents[2] / "data" / "si_blueprints" / f"{project_id}.yaml"
    if not bp_path.exists():
        return JSONResponse({"error": "No SI blueprint found", "project_id": project_id}, status_code=404)
    with open(bp_path) as f:
        return JSONResponse(yaml.safe_load(f))


@router.put("/api/projects/{project_id}/si-blueprint")
async def api_put_si_blueprint(request: Request, project_id: str):
    """Write SI blueprint for a project."""
    import yaml
    bp_dir = Path(__file__).resolve().parents[2] / "data" / "si_blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)
    data = await request.json()
    data["project_id"] = project_id
    with open(bp_dir / f"{project_id}.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return JSONResponse({"ok": True, "project_id": project_id})


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
        return HTMLResponse('<div class="msg-system-text">Prompt requis</div>', status_code=400)

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

        kickoff = f"""**Phase 1 : {phase1['name']}**

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
        kickoff = f"""**Phase {current_idx + 2} : {next_phase['name']}**

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

@router.get("/mission-control", response_class=HTMLResponse)
async def missions_list_page(request: Request):
    """List all mission runs."""
    from ..missions.store import get_mission_run_store
    store = get_mission_run_store()
    runs = store.list_runs(limit=50)
    return _templates(request).TemplateResponse("mission_control_list.html", {
        "request": request, "page_title": "Epic Control",
        "runs": runs,
    })


@router.get("/missions/start/{workflow_id}", response_class=HTMLResponse)
async def mission_start_page(request: Request, workflow_id: str):
    """Start a new mission — show brief form."""
    from ..workflows.store import get_workflow_store
    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return RedirectResponse("/pi", status_code=302)
    return _templates(request).TemplateResponse("mission_start.html", {
        "request": request, "page_title": f"New Epic — {wf.name}",
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

    # Create workspace directory for agent tools (code, git, docker)
    import subprocess
    from pathlib import Path
    workspace_root = Path(__file__).resolve().parent.parent.parent / "data" / "workspaces" / mission_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    # Init git repo + README with brief
    subprocess.run(["git", "init"], cwd=str(workspace_root), capture_output=True)
    readme = workspace_root / "README.md"
    readme.write_text(f"# {wf.name}\n\n{brief}\n\nMission ID: {mission_id}\n")
    subprocess.run(["git", "add", "."], cwd=str(workspace_root), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit — mission workspace"], cwd=str(workspace_root), capture_output=True)
    workspace_path = str(workspace_root)

    mission = MissionRun(
        id=mission_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief,
        status=MissionStatus.RUNNING,
        phases=phases,
        project_id=project_id or mission_id,
        workspace_path=workspace_path,
    )

    run_store = get_mission_run_store()
    run_store.create(mission)

    # Create a session for the CDP agent
    session_store = get_session_store()
    session_id = uuid.uuid4().hex[:8]
    session_store.create(SessionDef(
        id=session_id,
        name=f"Epic: {wf.name}",
        project_id=mission.project_id or None,
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
        message_type="instruction",
        content=brief,
    ))

    # Start the CDP agent loop with workspace path
    mgr = get_loop_manager()
    try:
        await mgr.start_agent("chef_de_programme", session_id, mission.project_id, workspace_path)
    except Exception as e:
        logger.error("Failed to start CDP agent: %s", e)

    return JSONResponse({"mission_id": mission_id, "session_id": session_id,
                         "redirect": f"/missions/{mission_id}/control"})


@router.post("/api/missions/{mission_id}/chat/stream")
async def mission_chat_stream(request: Request, mission_id: str):
    """Stream a conversation with the CDP agent in mission context."""
    from ..missions.store import get_mission_run_store
    from ..sessions.store import get_session_store, MessageDef
    from ..agents.store import get_agent_store
    from ..agents.executor import get_executor, ExecutionContext
    from ..sessions.runner import _build_context
    from ..memory.manager import get_memory_manager

    form = await request.form()
    content = str(form.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return HTMLResponse("Mission not found", status_code=404)

    session_id = str(form.get("session_id", "")).strip() or mission.session_id
    sess_store = get_session_store()
    session = sess_store.get(session_id) if session_id else None
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    agent_store = get_agent_store()
    agent = agent_store.get("chef_de_programme")
    if not agent:
        agents = agent_store.list_all()
        agent = agents[0] if agents else None
    if not agent:
        return HTMLResponse("No agent", status_code=500)

    # Store user message
    sess_store.add_message(MessageDef(
        session_id=session_id, from_agent="user",
        to_agent="chef_de_programme", message_type="text", content=content,
    ))

    # Build mission-specific context summary
    phase_summary = []
    if mission.phases:
        for p in mission.phases:
            phase_summary.append(f"- {p.phase_id}: {p.status.value if hasattr(p.status, 'value') else p.status}")
    phases_str = "\n".join(phase_summary) if phase_summary else "No phases yet"

    # Gather memory
    mem_ctx = ""
    try:
        mem = get_memory_manager()
        entries = mem.project_get(mission_id, limit=20)
        if entries:
            mem_ctx = "\n".join(f"[{e['category']}] {e['key']}: {e['value'][:200]}" for e in entries)
    except Exception:
        pass

    # Gather recent agent messages from this session
    recent = sess_store.get_messages(session_id, limit=30)
    agent_msgs = []
    for m in recent:
        if m.from_agent not in ("user", "system") and m.content:
            agent_msgs.append(f"[{m.from_agent}] {m.content[:300]}")
    agent_conv = "\n".join(agent_msgs[-10:]) if agent_msgs else "No agent conversations yet"

    mission_context = f"""MISSION BRIEF: {mission.brief or 'N/A'}
MISSION STATUS: {mission.status.value if hasattr(mission.status, 'value') else mission.status}
WORKSPACE: {mission.workspace_path or 'N/A'}

PHASES STATUS:
{phases_str}

PROJECT MEMORY (knowledge from agents):
{mem_ctx or 'No memory entries yet'}

RECENT AGENT CONVERSATIONS (last 10):
{agent_conv}

Answer the user's question about this mission with concrete data.
If they ask about PRs, features, sprints, git — use the appropriate tools to search.
Answer in the same language as the user. Be precise and data-driven."""

    async def event_generator():
        import html as html_mod
        import markdown as md_lib

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield sse("status", {"label": "Analyse en cours..."})

        try:
            ctx = await _build_context(agent, session)
            # Inject mission context into project_context
            ctx.project_context = mission_context + "\n\n" + (ctx.project_context or "")
            if mission.workspace_path:
                ctx.project_path = mission.workspace_path
            ctx.mission_run_id = mission_id
            # Disable tools for conversational chat — context already injected
            ctx.tools_enabled = False

            executor = get_executor()
            accumulated = ""
            llm_error = ""
            _in_think = False

            async for evt, data_s in executor.run_streaming(ctx, content):
                if evt == "delta":
                    accumulated += data_s
                    # Filter <think> blocks from streaming output
                    if '<think>' in data_s:
                        _in_think = True
                    if _in_think:
                        if '</think>' in data_s:
                            _in_think = False
                            # Send text after </think>
                            after = data_s.split('</think>', 1)[1]
                            if after.strip():
                                yield sse("chunk", {"text": after})
                        continue
                    yield sse("chunk", {"text": data_s})
                elif evt == "result":
                    if hasattr(data_s, "error") and data_s.error:
                        llm_error = data_s.error
                    elif hasattr(data_s, "content") and data_s.content and not accumulated:
                        accumulated = data_s.content

            # Strip <think> blocks from accumulated content
            import re as _re
            accumulated = _re.sub(r'<think>[\s\S]*?</think>\s*', '', accumulated).strip()

            # If LLM failed and no real content, send error
            if llm_error and not accumulated:
                yield sse("error", {"message": f"LLM indisponible: {llm_error[:150]}"})
                return

            # Store agent response
            if accumulated:
                sess_store.add_message(MessageDef(
                    session_id=session_id, from_agent="chef_de_programme",
                    to_agent="user", message_type="text", content=accumulated,
                ))

            rendered = md_lib.markdown(accumulated, extensions=["fenced_code", "tables", "nl2br"]) if accumulated else ""
            yield sse("done", {"html": rendered})

        except Exception as exc:
            logger.exception("Mission chat stream error")
            yield sse("error", {"message": str(exc)[:200]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/missions/{mission_id}/control", response_class=HTMLResponse)
async def mission_control_page(request: Request, mission_id: str):
    """Mission Control dashboard — pipeline visualization + CDP activity."""
    from ..missions.store import get_mission_run_store
    from ..agents.store import get_agent_store
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store
    from ..memory.manager import get_memory_manager

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return RedirectResponse("/pi", status_code=302)
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)

    # Build phase→agents mapping + per-phase sub-graphs from workflow config
    phase_agents = {}
    phase_graphs = {}  # phase_id → {nodes:[], edges:[]}
    wf = get_workflow_store().get(mission.workflow_id)
    if wf:
        # Global graph from workflow config
        global_graph = (wf.config or {}).get("graph", {})
        all_nodes = global_graph.get("nodes", [])
        all_edges = global_graph.get("edges", [])
        nid_to_agent = {n["id"]: n.get("agent_id", "") for n in all_nodes}

        # Pre-fetch full agent defs for enriching phase_agents
        agent_defs = {a.id: a for a in agents}

        for wp in wf.phases:
            cfg = wp.config or {}
            aids = cfg.get("agent_ids", cfg.get("agents", []))
            entries = []
            for a in aids:
                adef = agent_defs.get(a)
                am = agent_map.get(a, {})
                entries.append({
                    "id": a,
                    "name": am.get("name", a),
                    "role": am.get("role", ""),
                    "avatar_url": am.get("avatar_url", ""),
                    "color": am.get("color", "#8b949e"),
                    "tagline": getattr(adef, "tagline", "") or "" if adef else "",
                    "persona": getattr(adef, "persona", "") or "" if adef else "",
                    "motivation": getattr(adef, "motivation", "") or "" if adef else "",
                    "skills": getattr(adef, "skills", []) or [] if adef else [],
                    "tools": getattr(adef, "tools", []) or [] if adef else [],
                    "model": getattr(adef, "model", "") or "" if adef else "",
                    "provider": getattr(adef, "provider", "") or "" if adef else "",
                })
            phase_agents[wp.id] = entries
            # Extract sub-graph: nodes in this phase + edges between them
            agent_set = set(aids)
            p_nodes = [n for n in all_nodes if n.get("agent_id") in agent_set]
            p_node_ids = {n["id"] for n in p_nodes}
            p_edges = [e for e in all_edges if e["from"] in p_node_ids and e["to"] in p_node_ids]

            # Auto-generate rich multi-pattern edges reflecting real organizational topology
            pattern_id = wp.pattern_id or ""
            if len(p_nodes) >= 2:
                pids = [n["id"] for n in p_nodes]
                aids_list = [n.get("agent_id", "") for n in p_nodes]
                aid_to_nid = {n.get("agent_id", ""): n["id"] for n in p_nodes}
                # Sort by hierarchy_rank to identify leaders
                ranked = sorted(p_nodes, key=lambda n: agent_map.get(n.get("agent_id",""), {}).get("hierarchy_rank", 50))
                leader_nid = ranked[0]["id"]  # Lowest rank = leader
                # Color palette for multi-pattern layers
                C_HIER   = "#f59e0b"  # hierarchical delegation
                C_NET    = "#8b5cf6"  # network discussion
                C_SEQ    = "#3b82f6"  # sequential flow
                C_LOOP   = "#ec4899"  # loop/feedback
                C_PAR    = "#10b981"  # parallel execution
                C_GATE   = "#ef4444"  # gate/veto/checkpoint
                C_AGG    = "#06b6d4"  # aggregation
                C_ROUTE  = "#f97316"  # routing

                def _add(f, t, **kw):
                    if not any(e["from"] == f and e["to"] == t for e in p_edges):
                        p_edges.append({"from": f, "to": t, **kw})

                if pattern_id == "network":
                    # Network brainstorming: mesh discussion + facilitator synthesis
                    for i, a in enumerate(pids):
                        for b in pids[i+1:]:
                            _add(a, b, color=C_NET, label="")
                            _add(b, a, color=C_NET, label="")
                    # Leader acts as facilitator — receives summaries
                    others = [p for p in pids if p != leader_nid]
                    for a in others:
                        _add(a, leader_nid, color=C_AGG, label="synthèse")

                elif pattern_id == "human-in-the-loop":
                    # Decision body: leader at center, advisors report + debate
                    advisors = [p for p in pids if p != leader_nid]
                    # Advisors → Leader (recommendations)
                    for a in advisors:
                        _add(a, leader_nid, color=C_HIER, label="avis")
                    # Cross-debate between advisors (network layer)
                    for i, a in enumerate(advisors):
                        for b in advisors[i+1:]:
                            _add(a, b, color=C_NET, label="débat")
                            _add(b, a, color=C_NET, label="")
                    # Leader → checkpoint gate
                    if advisors:
                        _add(leader_nid, advisors[0], color=C_GATE, label="GO/NOGO")

                elif pattern_id == "sequential":
                    # Chain flow + feedback arrows for rework
                    for i in range(len(pids) - 1):
                        _add(pids[i], pids[i+1], color=C_SEQ, label="")
                    # Feedback loop: last → first for iterations
                    if len(pids) >= 3:
                        _add(pids[-1], pids[0], color=C_LOOP, label="feedback")

                elif pattern_id == "aggregator":
                    # All contribute → last agent aggregates + cross-review
                    # Aggregator = last agent in list (by convention)
                    aggregator = pids[-1]
                    contributors = [p for p in pids if p != aggregator]
                    # Contributors → Aggregator
                    for a in contributors:
                        _add(a, aggregator, color=C_AGG, label="")
                    # Aggregator → Contributors (feedback/validation)
                    for a in contributors:
                        _add(aggregator, a, color=C_LOOP, label="review")
                    # Cross-review between contributors
                    for i, a in enumerate(contributors):
                        for b in contributors[i+1:]:
                            _add(a, b, color=C_NET, label="")

                elif pattern_id == "hierarchical":
                    # Leader (highest rank) delegates + team collaborates + review loop
                    team = [p for p in pids if p != leader_nid]
                    # Leader → team (delegation)
                    for t in team:
                        _add(leader_nid, t, color=C_HIER, label="")
                    # Team → Leader (report back / PR review)
                    for t in team:
                        _add(t, leader_nid, color=C_LOOP, label="review")
                    # Peer collaboration among team members
                    for i, a in enumerate(team):
                        for b in team[i+1:]:
                            _add(a, b, color=C_NET, label="")

                elif pattern_id == "parallel":
                    # Fan-out → parallel execution → fan-in aggregation
                    workers = [p for p in pids if p != leader_nid]
                    # Dispatch from leader
                    for w in workers:
                        _add(leader_nid, w, color=C_PAR, label="")
                    # Results back to leader
                    for w in workers:
                        _add(w, leader_nid, color=C_AGG, label="résultat")
                    # Workers can cross-communicate
                    for i, a in enumerate(workers):
                        for b in workers[i+1:]:
                            _add(a, b, color=C_NET, label="")

                elif pattern_id == "loop":
                    # Bidirectional iteration loop + escalation
                    for i in range(len(pids)):
                        f, t = pids[i], pids[(i+1) % len(pids)]
                        _add(f, t, color=C_LOOP, label="")
                        _add(t, f, color=C_LOOP, label="feedback")

                elif pattern_id == "router":
                    # Hub routes to specialists + specialists can cross-consult
                    specialists = [p for p in pids if p != leader_nid]
                    # Router → each specialist
                    for s in specialists:
                        _add(leader_nid, s, color=C_ROUTE, label="route")
                    # Specialists report back
                    for s in specialists:
                        _add(s, leader_nid, color=C_AGG, label="résolu")
                    # Cross-consultation between specialists
                    for i, a in enumerate(specialists):
                        for b in specialists[i+1:]:
                            _add(a, b, color=C_NET, label="")

                else:
                    # Fallback: simple chain
                    for i in range(len(pids) - 1):
                        _add(pids[i], pids[i+1], color="#8b949e")

            # Enrich nodes with agent info
            enriched_nodes = []
            for n in p_nodes:
                aid = n.get("agent_id", "")
                am = agent_map.get(aid, {})
                enriched_nodes.append({
                    "id": n["id"], "agent_id": aid,
                    "label": am.get("name", n.get("label", aid)),
                    "role": am.get("role", ""),
                    "avatar": am.get("avatar_url", ""),
                    "hierarchy_rank": am.get("hierarchy_rank", 50),
                })
            phase_graphs[wp.id] = {"nodes": enriched_nodes, "edges": p_edges}

    # Session messages for discussions
    messages = []
    phase_messages: dict[str, list] = {}  # phase_id → list of message dicts
    # Build agent→phase mapping for fallback routing
    _agent_to_phase: dict[str, str] = {}
    if wf:
        for wp in wf.phases:
            cfg = wp.config or {}
            for aid in cfg.get("agent_ids", cfg.get("agents", [])):
                _agent_to_phase.setdefault(aid, wp.id)
    # Track current phase from system messages (Pattern started)
    _current_phase_infer = ""
    if mission.session_id:
        session_store = get_session_store()
        msgs = session_store.get_messages(mission.session_id)
        for m in msgs:
            # Track phase transitions from system messages
            if m.from_agent == "system" and m.content:
                for wp in (wf.phases if wf else []):
                    if wp.name and wp.name in m.content and "started" in m.content:
                        _current_phase_infer = wp.id
                        break
            if m.message_type == "system" and m.from_agent == "system":
                continue  # skip internal system messages from display
            # Skip raw tool call XML and empty messages
            _c = (m.content or "").strip()
            if not _c or _c.startswith(("<FunctionCall", "<tool_code", "[TOOL_CALL]{")):
                continue
            ag = agent_map.get(m.from_agent)
            meta = {}
            if hasattr(m, "metadata") and m.metadata:
                meta = m.metadata if isinstance(m.metadata, dict) else {}
            msg_dict = {
                "from_agent": m.from_agent,
                "to_agent": getattr(m, "to_agent", "") or "",
                "content": m.content,
                "message_type": m.message_type,
                "timestamp": m.created_at if hasattr(m, "created_at") else "",
                "metadata": meta,
            }
            messages.append(msg_dict)
            # Route to phase via metadata or fallback
            pid = meta.get("phase_id", "") or _current_phase_infer or _agent_to_phase.get(m.from_agent, "")
            if pid:
                phase_messages.setdefault(pid, []).append(msg_dict)

    # Extract screenshot paths per phase from messages
    import re as _re_shots
    phase_screenshots: dict[str, list[str]] = {}
    for pid, pmsgs in phase_messages.items():
        shots = []
        for m in pmsgs:
            for match in _re_shots.finditer(r'\[SCREENSHOT:([^\]]+)\]', m.get("content", "")):
                p = match.group(1).strip().lstrip("./")
                shots.append(p)
        if shots:
            phase_screenshots[pid] = shots[:6]  # max 6 thumbnails per phase

    # Memory entries — project-specific only, filtered to meaningful content
    memories = []
    _useful_cats = {"product", "architecture", "security", "development", "quality",
                    "phase-summary", "vision", "convention", "team",
                    "decisions", "infrastructure"}
    try:
        mem_mgr = get_memory_manager()
        # Use mission.id as memory scope — each epic has its own memory
        proj_mems = mem_mgr.project_get(mission.id, limit=80) or []
        for pm in proj_mems:
            if not isinstance(pm, dict):
                continue
            cat = pm.get("category", "")
            key = pm.get("key", "")
            if key.startswith("agent:"):
                continue
            if cat in _useful_cats:
                memories.append(pm)
    except Exception:
        pass

    # Group memories by category for template rendering
    memory_groups: dict = {}
    for pm in memories:
        c = pm.get("category", "general")
        memory_groups.setdefault(c, []).append(pm)

    # Extract tool calls from session messages for Git & Features panels
    tool_commits = []
    tool_prs = []
    tool_features = []
    try:
        session_store = get_session_store()
        all_msgs = session_store.get_messages(mission.session_id) if mission.session_id else []
        for m in all_msgs:
            content = m.content or ""
            # Extract git commits from tool calls
            if "git_commit" in content or "[TOOL_CALL]" in content:
                import re as _re_tc
                for match in _re_tc.finditer(r'(?:git_commit|git commit)[^\n]*?["\']([^"\']{5,80})["\']', content):
                    tool_commits.append({"hash": f"{hash(match.group(1)) & 0xfffffff:07x}", "message": match.group(1)})
                # Also catch commit-like patterns
                for match in _re_tc.finditer(r'(?:feat|fix|chore|refactor|test|docs)\([^)]+\):\s*(.{10,80})', content):
                    msg = match.group(0)
                    if msg not in [c["message"] for c in tool_commits]:
                        tool_commits.append({"hash": f"{hash(msg) & 0xfffffff:07x}", "message": msg})
            # Extract PRs
            if "create_pull_request" in content.lower() or "[PR]" in content:
                import re as _re_pr
                for match in _re_pr.finditer(r'\[PR\]\s*(.{5,80})', content):
                    tool_prs.append({"number": len(tool_prs) + 1, "title": match.group(1).strip(), "status": "Open"})
            # Extract features/deliverables
            if any(kw in content.lower() for kw in ("implement", "create ", "add ", "[pr]", "livrable")):
                import re as _re_ft
                for match in _re_ft.finditer(r'\[PR\]\s*(.{5,100})', content):
                    feat = match.group(1).strip()
                    if feat not in tool_features:
                        tool_features.append(feat)
    except Exception:
        pass

    # Pull requests — scan workspace git branches + merge tool-extracted PRs
    pull_requests = list(tool_prs)
    workspace_commits = list(tool_commits)
    if mission.workspace_path:
        import subprocess
        try:
            result = subprocess.run(
                ["git", "branch", "-a", "--format=%(refname:short)"],
                cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
            )
            branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip() and b.strip() not in ("master", "main")]
            for i, branch in enumerate(branches[:10]):
                status = "Open"
                merged = subprocess.run(
                    ["git", "branch", "--merged", "HEAD", "--format=%(refname:short)"],
                    cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                )
                if branch in merged.stdout:
                    status = "Merged"
                pull_requests.append({"number": i + 1, "title": branch, "status": status})
        except Exception:
            pass
        # Recent commits
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--no-decorate", "-15"],
                cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.strip().split(" ", 1)
                    workspace_commits.append({"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""})
        except Exception:
            pass

    # SI Blueprint for the project
    si_blueprint = None
    try:
        import yaml as _yaml
        bp_path = Path(__file__).resolve().parents[2] / "data" / "si_blueprints" / f"{mission.project_id}.yaml"
        if bp_path.exists():
            with open(bp_path) as _f:
                si_blueprint = _yaml.safe_load(_f)
    except Exception:
        pass

    # Global lessons from past epics
    lessons = []
    try:
        mem_mgr = get_memory_manager()
        global_mems = mem_mgr.global_get(category="lesson", limit=20) or []
        global_mems += mem_mgr.global_get(category="improvement", limit=10) or []
        for gm in global_mems:
            if isinstance(gm, dict):
                lessons.append(gm)
    except Exception:
        pass

    # ── Mission Result: screenshots, build command, deploy URL ──
    result_screenshots = []
    result_build_cmd = ""
    result_run_cmd = ""
    result_launch_cmd = ""
    result_deploy_url = ""
    result_project_type = ""
    ws_path = mission.workspace_path or ""
    if ws_path:
        ws = Path(ws_path)
        if ws.exists():
            # Collect REAL screenshots (skip tiny placeholders < 5KB)
            for img_dir in [ws / "screenshots", ws]:
                if img_dir.exists():
                    for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"):
                        for img in sorted(img_dir.glob(ext)):
                            if img.stat().st_size > 5000:  # skip placeholders
                                rel = img.relative_to(ws)
                                result_screenshots.append(str(rel))
            result_screenshots = result_screenshots[:12]

            # Auto-detect project platform
            detected = _detect_project_platform(ws_path)
            result_project_type = detected

            if detected == "macos-native" or detected == "ios-native":
                if (ws / "Package.swift").exists():
                    result_build_cmd = "swift build"
                    result_run_cmd = "swift run"
                    result_launch_cmd = "open -a Simulator && swift run"
                elif (ws / "project.yml").exists():
                    scheme = "App"
                    try:
                        import yaml as _y
                        proj = _y.safe_load((ws / "project.yml").read_text())
                        scheme = proj.get("name", "App")
                    except Exception:
                        pass
                    result_build_cmd = f"xcodegen generate && xcodebuild -scheme {scheme} -configuration Debug build"
                    result_run_cmd = f"open build/Debug/{scheme}.app"
                    result_launch_cmd = f"open -a Simulator && open build/Debug/{scheme}.app"
                else:
                    result_build_cmd = "swift build"
                    result_run_cmd = "swift run"
                    result_launch_cmd = "open -a Simulator && swift run"
            elif detected == "android-native":
                result_build_cmd = "./gradlew assembleDebug"
                result_run_cmd = "./gradlew installDebug"
                result_launch_cmd = "adb shell am start -n com.app/.MainActivity"
            elif detected == "web-docker":
                if (ws / "docker-compose.yml").exists():
                    result_build_cmd = "docker compose build"
                    result_run_cmd = "docker compose up"
                else:
                    result_build_cmd = "docker build -t app ."
                    result_run_cmd = "docker run -p 8080:8080 app"
                result_deploy_url = "http://localhost:8080"
            elif detected == "web-node":
                result_build_cmd = "npm install && npm run build"
                result_run_cmd = "npm start"
                result_deploy_url = "http://localhost:3000"
            elif (ws / "Makefile").exists():
                result_build_cmd = "make build"
                result_run_cmd = "make run"

            # Deploy URL — only for web projects (search in config files)
            if detected.startswith("web") and not result_deploy_url:
                for env_file in (ws / "environments.md", ws / ".env", ws / "deploy.md"):
                    if env_file.exists():
                        try:
                            env_text = env_file.read_text()[:2000]
                            import re as _re_url
                            urls = _re_url.findall(r'https?://[^\s\)\"\']+', env_text)
                            for u in urls:
                                if any(d in u for d in ("azurewebsites", "azure", "herokuapp", "vercel", "netlify", "localhost")):
                                    result_deploy_url = u
                                    break
                        except Exception:
                            pass

    # ── Tab data: Workspace files, PO kanban, QA scores ──
    import os
    workspace_files = []
    if ws_path:
        ws = Path(ws_path)
        if ws.exists():
            for root, dirs, files in os.walk(ws):
                level = root.replace(str(ws), "").count(os.sep)
                if level >= 3:
                    dirs.clear()
                    continue
                rel = os.path.relpath(root, ws)
                if rel == ".":
                    rel = ""
                # Skip hidden dirs
                dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")][:20]
                for f in sorted(files)[:30]:
                    fpath = os.path.join(rel, f) if rel else f
                    workspace_files.append({"path": fpath, "is_dir": False})
            workspace_files = workspace_files[:100]

    # PO Kanban: features from DB or extracted from tool_features
    po_backlog, po_sprint, po_done = [], [], []
    try:
        from ..db.migrations import get_db
        db = get_db()
        rows = db.execute("SELECT name, description, acceptance_criteria, priority, status, story_points, assigned_to FROM features WHERE epic_id=?", (mission_id,)).fetchall()
        for r in rows:
            feat = {"name": r[0], "description": r[1] or "", "acceptance_criteria": r[2] or "", "priority": r[3] or 5, "story_points": r[5] or 0, "assigned_to": r[6] or ""}
            if r[4] == "done":
                po_done.append(feat)
            elif r[4] in ("in_progress", "sprint"):
                po_sprint.append(feat)
            else:
                po_backlog.append(feat)
    except Exception:
        pass
    # Fallback: use tool_features if no DB features
    if not po_backlog and not po_sprint and not po_done and tool_features:
        for f in tool_features:
            po_done.append({"name": f, "description": "", "acceptance_criteria": "", "priority": 5, "story_points": 0, "assigned_to": ""})

    # QA: Agent adversarial scores
    agent_scores = []
    qa_total_accepted = 0
    qa_total_rejected = 0
    qa_total_iterations = 0
    try:
        from ..db.migrations import get_db as _gdb_qa
        db = _gdb_qa()
        rows = db.execute("SELECT agent_id, accepted, rejected, iterations, quality_score FROM agent_scores WHERE epic_id=?", (mission_id,)).fetchall()
        for r in rows:
            agent_scores.append({"agent_id": r[0], "accepted": r[1], "rejected": r[2], "iterations": r[3], "quality_score": r[4]})
            qa_total_accepted += r[1]
            qa_total_rejected += r[2]
            qa_total_iterations += r[3]
    except Exception:
        pass
    qa_pass_rate = round(qa_total_accepted / qa_total_iterations * 100) if qa_total_iterations > 0 else 0

    return _templates(request).TemplateResponse("mission_control.html", {
        "request": request,
        "page_title": f"Epic Control — {mission.workflow_name}",
        "mission": mission,
        "agent_map": agent_map,
        "phase_agents": phase_agents,
        "phase_graphs": phase_graphs,
        "messages": messages,
        "phase_messages": phase_messages,
        "phase_screenshots": phase_screenshots,
        "memories": memories,
        "memory_groups": memory_groups,
        "pull_requests": pull_requests,
        "workspace_commits": workspace_commits,
        "si_blueprint": si_blueprint,
        "lessons": lessons,
        "features": tool_features,
        "session_id": mission.session_id or "",
        "result_screenshots": result_screenshots,
        "result_build_cmd": result_build_cmd,
        "result_run_cmd": result_run_cmd,
        "result_launch_cmd": result_launch_cmd,
        "result_deploy_url": result_deploy_url,
        "result_project_type": result_project_type,
        "workspace_files": workspace_files,
        "po_backlog": po_backlog,
        "po_sprint": po_sprint,
        "po_done": po_done,
        "agent_scores": agent_scores,
        "qa_pass_rate": qa_pass_rate,
        "qa_total_accepted": qa_total_accepted,
        "qa_total_rejected": qa_total_rejected,
        "qa_total_iterations": qa_total_iterations,
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


@router.post("/api/missions/{mission_id}/exec")
async def api_mission_exec(request: Request, mission_id: str):
    """Execute a command in the mission workspace. Returns JSON {stdout, stderr, returncode}."""
    import os as _os
    import subprocess as _sp
    from ..missions.store import get_mission_run_store
    store = get_mission_run_store()
    mission = store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Mission not found"}, status_code=404)
    ws = mission.workspace_path
    if not ws or not Path(ws).exists():
        return JSONResponse({"error": "No workspace"}, status_code=400)

    body = await request.json()
    cmd = body.get("command", "").strip()
    if not cmd:
        return JSONResponse({"error": "No command"}, status_code=400)

    # Security: block dangerous commands
    blocked = ["rm -rf /", "sudo", "chmod 777", "mkfs", "dd if=", "> /dev/"]
    if any(b in cmd for b in blocked):
        return JSONResponse({"error": "Command blocked"}, status_code=403)

    try:
        result = _sp.run(
            cmd, shell=True, cwd=ws,
            capture_output=True, text=True, timeout=60,
            env={**_os.environ, "TERM": "dumb"},
        )
        return JSONResponse({
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-2000:],
            "returncode": result.returncode,
            "command": cmd,
        })
    except _sp.TimeoutExpired:
        return JSONResponse({"error": "Timeout (60s)", "command": cmd}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e), "command": cmd}, status_code=500)


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


@router.post("/api/missions/{mission_id}/reset")
async def api_mission_reset(request: Request, mission_id: str):
    """Reset a mission: all phases back to pending, clear messages, ready to re-run."""
    from ..missions.store import get_mission_run_store
    from ..sessions.store import get_session_store, MessageDef
    from ..models import PhaseStatus, MissionStatus
    from ..sessions.runner import _push_sse

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Reset all phases to pending
    for p in mission.phases:
        p.status = PhaseStatus.PENDING
        p.started_at = None
        p.completed_at = None
        p.summary = ""
        p.agent_count = 0

    mission.status = MissionStatus.RUNNING
    mission.current_phase = ""
    run_store.update(mission)

    # Clear session messages (keep the session itself)
    if mission.session_id:
        from ..db.migrations import get_db
        conn = get_db()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (mission.session_id,))
        conn.commit()
        conn.close()

        # Add reset marker
        store = get_session_store()
        store.add_message(MessageDef(
            session_id=mission.session_id,
            from_agent="system",
            to_agent="all",
            message_type="system",
            content="Epic réinitialisée — prête pour une nouvelle exécution.",
        ))

        # Notify frontend
        await _push_sse(mission.session_id, {
            "type": "mission_reset",
            "mission_id": mission_id,
        })

    return JSONResponse({"status": "reset", "mission_id": mission_id})


@router.post("/api/missions/{mission_id}/run")
async def api_mission_run(request: Request, mission_id: str):
    """Drive mission execution: CDP orchestrates phases sequentially.

    Uses the REAL pattern engine (run_pattern) for each phase — agents
    think with LLM, stream their responses, and interact per pattern type.
    """
    import asyncio
    from ..missions.store import get_mission_run_store
    from ..workflows.store import get_workflow_store
    from ..agents.store import get_agent_store
    from ..models import PhaseStatus, MissionStatus
    from ..sessions.runner import _push_sse
    from ..patterns.engine import run_pattern, NodeStatus
    from ..patterns.store import PatternDef
    from datetime import datetime

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    wf = get_workflow_store().get(mission.workflow_id)
    if not wf:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)

    session_id = mission.session_id or ""
    agent_store = get_agent_store()

    async def _run_phases():
        """Execute phases sequentially using the real pattern engine."""
        phases_done = 0
        phases_failed = 0
        phase_summaries = []  # accumulated phase results for cross-phase context

        for i, phase in enumerate(mission.phases):
            wf_phase = wf.phases[i] if i < len(wf.phases) else None
            if not wf_phase:
                continue

            # Skip already-completed phases (for resume/fast-forward)
            if phase.status in (PhaseStatus.DONE, PhaseStatus.SKIPPED):
                phases_done += 1
                if phase.summary:
                    phase_summaries.append(f"## {wf_phase.name}\n{phase.summary}")
                continue

            cfg = wf_phase.config or {}
            aids = cfg.get("agent_ids", cfg.get("agents", []))
            pattern_type = wf_phase.pattern_id

            # Build CDP context: workspace state + previous phase summaries
            cdp_context = ""
            if mission.workspace_path:
                try:
                    import subprocess
                    ws = mission.workspace_path
                    # Workspace file count
                    file_count = subprocess.run(
                        ["find", ws, "-type", "f", "-not", "-path", "*/.git/*"],
                        capture_output=True, text=True, timeout=5
                    )
                    n_files = len(file_count.stdout.strip().split("\n")) if file_count.stdout.strip() else 0
                    # Recent git log
                    git_log = subprocess.run(
                        ["git", "log", "--oneline", "-5"],
                        cwd=ws, capture_output=True, text=True, timeout=5
                    )
                    cdp_context = f"Workspace: {n_files} fichiers"
                    if git_log.stdout.strip():
                        cdp_context += f" | Git: {git_log.stdout.strip().split(chr(10))[0]}"
                except Exception:
                    pass

            # Previous phase summaries for context
            prev_context = ""
            if phase_summaries:
                prev_context = "\n".join(
                    s if isinstance(s, str) else f"- Phase {s.get('name','?')}: {s.get('summary','')}"
                    for s in phase_summaries[-5:]  # last 5 phases max
                )

            # CDP announces the phase with context + platform detection
            detected_platform = _detect_project_platform(workspace) if workspace else ""
            platform_display = {
                "macos-native": "🖥️ macOS native (Swift/SwiftUI)",
                "ios-native": "📱 iOS native (Swift/SwiftUI)",
                "android-native": "🤖 Android native (Kotlin)",
                "web-docker": "🌐 Web (Docker)",
                "web-node": "🌐 Web (Node.js)",
                "web-static": "🌐 Web statique",
            }.get(detected_platform, "")
            cdp_announce = f"Lancement phase {i+1}/{len(mission.phases)} : **{wf_phase.name}** (pattern: {pattern_type})"
            if platform_display:
                cdp_announce += f"\nPlateforme détectée : {platform_display}"
            if cdp_context:
                cdp_announce += f"\n{cdp_context}"
            await _push_sse(session_id, {
                "type": "message",
                "from_agent": "chef_de_programme",
                "from_name": "Alexandre Moreau",
                "from_role": "Chef de Programme",
                "from_avatar": "/static/avatars/chef_de_programme.jpg",
                "content": cdp_announce,
                "phase_id": phase.phase_id,
                "msg_type": "text",
            })
            await asyncio.sleep(0.5)

            # Snapshot message count before phase starts (for summary extraction)
            from ..sessions.store import get_session_store as _get_ss
            _ss_pre = _get_ss()
            _pre_phase_msg_count = len(_ss_pre.get_messages(session_id))

            # Update phase status
            phase.status = PhaseStatus.RUNNING
            phase.started_at = datetime.utcnow()
            phase.agent_count = len(aids)
            mission.current_phase = phase.phase_id
            run_store.update(mission)

            await _push_sse(session_id, {
                "type": "phase_started",
                "mission_id": mission.id,
                "phase_id": phase.phase_id,
                "phase_name": wf_phase.name,
                "pattern": pattern_type,
                "agents": aids,
            })

            # Build PatternDef for this phase
            agent_nodes = [{"id": aid, "agent_id": aid} for aid in aids]

            # Resolve leader: workflow config > hierarchy_rank > first agent
            leader = cfg.get("leader", "")
            if not leader and aids:
                ranked = sorted(aids, key=lambda a: agent_store.get(a).hierarchy_rank if agent_store.get(a) else 50)
                leader = ranked[0]

            # Build edges — multi-pattern: leader structures + peer collaboration
            edges = []
            others = [a for a in aids if a != leader] if leader else aids

            if pattern_type == "network":
                # Leader briefs team (hierarchical), debaters discuss (network mesh), report back
                if leader:
                    for o in others:
                        edges.append({"from": leader, "to": o, "type": "delegate"})
                for idx_a, a in enumerate(others):
                    for b in others[idx_a+1:]:
                        edges.append({"from": a, "to": b, "type": "bidirectional"})
                if leader:
                    for o in others:
                        edges.append({"from": o, "to": leader, "type": "report"})

            elif pattern_type == "sequential":
                for idx_a in range(len(aids) - 1):
                    edges.append({"from": aids[idx_a], "to": aids[idx_a+1], "type": "sequential"})
                # Feedback loop from last to first
                if len(aids) > 2:
                    edges.append({"from": aids[-1], "to": aids[0], "type": "feedback"})

            elif pattern_type == "hierarchical" and leader:
                for sub in others:
                    edges.append({"from": leader, "to": sub, "type": "delegate"})
                # Peer collaboration between workers
                workers = [a for a in others if (agent_store.get(a) or type('',(),{'hierarchy_rank':50})).hierarchy_rank >= 40]
                for idx_a, a in enumerate(workers):
                    for b in workers[idx_a+1:]:
                        edges.append({"from": a, "to": b, "type": "bidirectional"})
                # Review loops back to leader
                for sub in others:
                    edges.append({"from": sub, "to": leader, "type": "report"})

            elif pattern_type == "aggregator" and aids:
                aggregator_id = leader or (aids[-1] if len(aids) > 1 else aids[0])
                contributors = [a for a in aids if a != aggregator_id]
                for a in contributors:
                    edges.append({"from": a, "to": aggregator_id, "type": "report"})
                # Cross-review between contributors
                for idx_a, a in enumerate(contributors):
                    for b in contributors[idx_a+1:]:
                        edges.append({"from": a, "to": b, "type": "bidirectional"})

            elif pattern_type == "router" and aids:
                router_id = leader or aids[0]
                specialists = [a for a in aids if a != router_id]
                for a in specialists:
                    edges.append({"from": router_id, "to": a, "type": "route"})
                    edges.append({"from": a, "to": router_id, "type": "report"})

            elif pattern_type == "human-in-the-loop" and aids:
                # Leader (DSI/CDP) receives from advisors, cross-debate between them
                for o in others:
                    edges.append({"from": o, "to": leader, "type": "report"})
                for idx_a, a in enumerate(others):
                    for b in others[idx_a+1:]:
                        edges.append({"from": a, "to": b, "type": "bidirectional"})

            elif pattern_type == "loop" and len(aids) >= 2:
                edges.append({"from": aids[0], "to": aids[1], "type": "sequential"})
                edges.append({"from": aids[1], "to": aids[0], "type": "feedback"})

            elif pattern_type == "parallel" and aids:
                dispatcher = leader or aids[0]
                workers = [a for a in aids if a != dispatcher]
                for w in workers:
                    edges.append({"from": dispatcher, "to": w, "type": "delegate"})
                    edges.append({"from": w, "to": dispatcher, "type": "report"})

            phase_pattern = PatternDef(
                id=f"mission-{mission.id}-phase-{phase.phase_id}",
                name=wf_phase.name,
                type=pattern_type,
                agents=agent_nodes,
                edges=edges,
                config={"max_rounds": 2, "max_iterations": 3},
            )

            # Build the task prompt for this phase
            phase_task = _build_phase_prompt(wf_phase.name, pattern_type, mission.brief, i, len(mission.phases), prev_context, workspace_path=workspace)

            # Sprint loop — dev-sprint runs multiple iterations (sprints)
            phase_key_check = wf_phase.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
            max_sprints = wf_phase.config.get("max_iterations", 3) if "sprint" in phase_key_check or "dev" in phase_key_check else 1

            # Run the real pattern engine — NO fake success on error
            phase_success = False
            phase_error = ""

            for sprint_num in range(1, max_sprints + 1):
                sprint_label = f"Sprint {sprint_num}/{max_sprints}" if max_sprints > 1 else ""

                if max_sprints > 1:
                    # Announce sprint start
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": "chef_de_programme",
                        "from_name": "Alexandre Moreau",
                        "from_role": "Chef de Programme",
                        "from_avatar": "/static/avatars/chef_de_programme.jpg",
                        "content": f"Lancement {sprint_label} pour «{wf_phase.name}»",
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    await asyncio.sleep(0.5)
                    # Update prompt with sprint context
                    phase_task = _build_phase_prompt(wf_phase.name, pattern_type, mission.brief, i, len(mission.phases), prev_context, workspace_path=workspace)
                    phase_task += (
                        f"\n\n--- {sprint_label} ---\n"
                        f"C'est le sprint {sprint_num} sur {max_sprints} prévus.\n"
                    )
                    if sprint_num == 1:
                        phase_task += "Focus: mise en place structure projet, première feature MVP.\n"
                    elif sprint_num < max_sprints:
                        phase_task += "Focus: itérez sur les features suivantes du backlog, utilisez le code existant.\n"
                    else:
                        phase_task += "Focus: sprint final — finalisez, nettoyez, préparez le handoff CI/CD.\n"

                    # Inject backlog from earlier phases (architecture, project-setup)
                    if mission.id:
                        try:
                            from ..memory.manager import get_memory_manager
                            mem = get_memory_manager()
                            backlog_items = mem.project_get(mission.id, category="product")
                            arch_items = mem.project_get(mission.id, category="architecture")
                            if backlog_items or arch_items:
                                phase_task += "\n\n--- Backlog et architecture (phases précédentes) ---\n"
                                for item in (backlog_items or [])[:5]:
                                    phase_task += f"- [Backlog] {item.get('key', '')}: {item.get('value', '')[:200]}\n"
                                for item in (arch_items or [])[:5]:
                                    phase_task += f"- [Archi] {item.get('key', '')}: {item.get('value', '')[:200]}\n"
                        except Exception:
                            pass

                try:
                    result = await run_pattern(
                        phase_pattern, session_id, phase_task,
                        project_id=mission.id,
                        project_path=mission.workspace_path,
                        phase_id=phase.phase_id,
                    )
                    phase_success = result.success
                    if not phase_success:
                        # Collect error details from failed nodes
                        failed_nodes = [
                            n for n in result.nodes.values()
                            if n.status not in (NodeStatus.COMPLETED, NodeStatus.PENDING)
                        ]
                        if result.error:
                            phase_error = result.error
                        elif failed_nodes:
                            errors = []
                            for fn in failed_nodes:
                                err = (fn.result.error if fn.result else "") or fn.output or ""
                                errors.append(f"{fn.agent_id}: {err[:100]}")
                            phase_error = "; ".join(errors)
                        else:
                            phase_error = "Pattern returned success=False"
                except Exception as exc:
                    import traceback
                    logger.error("Phase %s pattern crashed: %s\n%s", phase.phase_id, exc, traceback.format_exc())
                    phase_error = str(exc)

                # Sprint iteration handling:
                # - Success → continue to next sprint (more features)
                # - Failure/VETO in dev sprints → remediation: retry with feedback
                # - Failure in non-dev phases → break immediately
                if not phase_success:
                    if max_sprints > 1 and sprint_num < max_sprints:
                        # Dev sprint: inject veto feedback and retry
                        remediation_msg = f"{sprint_label} terminé avec des vetoes. Relance avec feedback correctif…"
                        await _push_sse(session_id, {
                            "type": "message",
                            "from_agent": "chef_de_programme",
                            "from_name": "Alexandre Moreau",
                            "from_role": "Chef de Programme",
                            "from_avatar": "/static/avatars/chef_de_programme.jpg",
                            "content": remediation_msg,
                            "phase_id": phase.phase_id,
                            "msg_type": "text",
                        })
                        await asyncio.sleep(0.8)
                        # Add veto feedback to next sprint prompt
                        prev_context += f"\n- VETO sprint {sprint_num}: {phase_error[:300]}"
                        phase_error = ""  # reset for next attempt
                        continue
                    else:
                        break  # Last sprint or single-iteration phase: stop

                # Announce sprint completion (only for multi-sprint phases)
                if max_sprints > 1 and sprint_num < max_sprints:
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": "chef_de_programme",
                        "from_name": "Alexandre Moreau",
                        "from_role": "Chef de Programme",
                        "from_avatar": "/static/avatars/chef_de_programme.jpg",
                        "content": f"{sprint_label} terminé. Passage au sprint suivant…",
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    await asyncio.sleep(0.8)

            # Human-in-the-loop checkpoint after pattern completes
            if pattern_type == "human-in-the-loop":
                phase.status = PhaseStatus.WAITING_VALIDATION
                run_store.update(mission)
                await _push_sse(session_id, {
                    "type": "checkpoint",
                    "mission_id": mission.id,
                    "phase_id": phase.phase_id,
                    "question": f"Validation requise pour «{wf_phase.name}»",
                    "options": ["GO", "NOGO", "PIVOT"],
                })
                for _ in range(600):
                    await asyncio.sleep(1)
                    m = run_store.get(mission.id)
                    if m:
                        for p in m.phases:
                            if p.phase_id == phase.phase_id and p.status != PhaseStatus.WAITING_VALIDATION:
                                phase.status = p.status
                                break
                        if phase.status != PhaseStatus.WAITING_VALIDATION:
                            break
                if phase.status == PhaseStatus.WAITING_VALIDATION:
                    phase.status = PhaseStatus.DONE
                if phase.status == PhaseStatus.FAILED:
                    run_store.update(mission)
                    await _push_sse(session_id, {
                        "type": "phase_failed",
                        "mission_id": mission.id,
                        "phase_id": phase.phase_id,
                    })
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": "chef_de_programme",
                        "from_name": "Alexandre Moreau",
                        "from_role": "Chef de Programme",
                        "from_avatar": "/static/avatars/chef_de_programme.jpg",
                        "content": "Epic arrêtée — décision NOGO.",
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    mission.status = MissionStatus.FAILED
                    run_store.update(mission)
                    return
            else:
                phase.status = PhaseStatus.DONE if phase_success else PhaseStatus.FAILED

            # For HITL phases, the human decision overrides pattern success
            # (user clicked GO = success, even if some LLM nodes had issues)
            phase_success = (phase.status == PhaseStatus.DONE)

            # Phase complete — real status
            phase.completed_at = datetime.utcnow()
            if phase_success:
                # Build LLM summary from agent messages in this phase
                try:
                    from ..sessions.store import get_session_store
                    from ..llm.client import get_llm_client, LLMMessage
                    ss = get_session_store()
                    phase_msgs = ss.get_messages(session_id)
                    # Collect messages produced during THIS phase (after snapshot)
                    convo = []
                    for m in phase_msgs[_pre_phase_msg_count:]:
                        txt = (getattr(m, 'content', '') or '').strip()
                        if not txt or len(txt) < 20:
                            continue
                        agent = getattr(m, 'from_agent', '') or ''
                        if agent in ('system', 'user', 'chef_de_programme'):
                            continue
                        name = getattr(m, 'from_name', '') or agent
                        convo.append(f"{name}: {txt[:500]}")
                    if convo:
                        transcript = "\n\n".join(convo[-15:])  # last 15 messages max
                        llm = get_llm_client()
                        resp = await llm.chat([
                            LLMMessage(role="user", content=f"Summarize this team discussion in 2-3 sentences. Focus on decisions made, key proposals, and conclusions. Be factual and specific. Answer in the same language as the discussion.\n\n{transcript[:4000]}")
                        ], max_tokens=200, temperature=0.3)
                        phase.summary = (resp.content or "").strip()[:500]
                    if not getattr(phase, 'summary', None):
                        phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                except Exception:
                    phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                phases_done += 1

                # Generate cross-phase summary for next phases
                summary_text = f"[{wf_phase.name}] terminée"
                if mission.workspace_path:
                    try:
                        import subprocess as _sp
                        # Get files changed during this phase
                        diff_stat = _sp.run(
                            ["git", "diff", "--stat", "HEAD~1"],
                            cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                        )
                        if diff_stat.stdout.strip():
                            summary_text += f" | Fichiers: {diff_stat.stdout.strip().split(chr(10))[-1]}"
                    except Exception:
                        pass
                # Store decisions from agent messages in memory
                try:
                    from ..memory.manager import get_memory_manager
                    mem = get_memory_manager()
                    if mission.project_id:
                        mem.project_store(
                            mission.project_id,
                            key=f"phase:{wf_phase.name}",
                            value=summary_text[:500],
                            category="phase-summary",
                            source="mission-control",
                        )
                except Exception:
                    pass
                phase_summaries.append(f"## {wf_phase.name}\n{summary_text[:200]}")

                # Post-phase CI/CD hooks — run real commands in workspace
                await _run_post_phase_hooks(
                    phase.phase_id, wf_phase.name, mission, session_id, _push_sse
                )
            else:
                phase.summary = f"Phase échouée — {phase_error[:200]}"
                phases_failed += 1
            run_store.update(mission)

            await _push_sse(session_id, {
                "type": "phase_completed",
                "mission_id": mission.id,
                "phase_id": phase.phase_id,
                "success": phase_success,
            })

            # CDP announces result honestly
            if i < len(mission.phases) - 1:
                if phase_success:
                    cdp_msg = f"Phase «{wf_phase.name}» réussie. Passage à la phase suivante…"
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": "chef_de_programme",
                        "from_name": "Alexandre Moreau",
                        "from_role": "Chef de Programme",
                        "from_avatar": "/static/avatars/chef_de_programme.jpg",
                        "content": cdp_msg,
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    await asyncio.sleep(0.8)
                else:
                    # Phase failed — check if it's a blocking phase
                    # Dev sprints and CI/CD can fail without killing the entire mission
                    # Only strategic gates (committees, deploy-prod) are mission-critical
                    blocking = pattern_type in ("human-in-the-loop",) or "deploy" in phase.phase_id
                    short_err = phase_error[:200] if phase_error else "erreur inconnue"
                    if blocking:
                        cdp_msg = f"Phase «{wf_phase.name}» échouée ({short_err}). Epic arrêtée — corrigez puis relancez via le bouton Réinitialiser."
                    else:
                        cdp_msg = f"Phase «{wf_phase.name}» terminée avec des problèmes ({short_err}). Passage à la phase suivante malgré tout…"
                        phase.status = PhaseStatus.DONE  # downgrade to done with issues
                        phases_done += 1
                        phases_failed -= 1  # undo the +1 from above
                        # Rebuild summary from agent messages (not "Phase échouée")
                        try:
                            from ..sessions.store import get_session_store
                            ss = get_session_store()
                            phase_msgs = ss.get_messages(session_id)
                            convo = []
                            for pm in phase_msgs[_pre_phase_msg_count:]:
                                txt = (getattr(pm, 'content', '') or '').strip()
                                if not txt or len(txt) < 20:
                                    continue
                                agent = getattr(pm, 'from_agent', '') or ''
                                if agent in ('system', 'user', 'chef_de_programme'):
                                    continue
                                name = getattr(pm, 'from_name', '') or agent
                                convo.append(f"{name}: {txt[:300]}")
                            if convo:
                                from ..llm.client import get_llm_client, LLMMessage
                                llm = get_llm_client()
                                transcript = "\n\n".join(convo[-10:])
                                resp = await llm.chat([
                                    LLMMessage(role="user", content=f"Résume cette discussion d'équipe en 2-3 phrases. Focus sur les décisions et conclusions. Même langue que la discussion.\n\n{transcript[:3000]}")
                                ], max_tokens=200, temperature=0.3)
                                phase.summary = (resp.content or "").strip()[:500]
                        except Exception:
                            phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": "chef_de_programme",
                        "from_name": "Alexandre Moreau",
                        "from_role": "Chef de Programme",
                        "from_avatar": "/static/avatars/chef_de_programme.jpg",
                        "content": cdp_msg,
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    if blocking:
                        mission.status = MissionStatus.FAILED
                        run_store.update(mission)
                        await _push_sse(session_id, {
                            "type": "mission_failed",
                            "mission_id": mission.id,
                            "phase_id": phase.phase_id,
                            "error": short_err,
                        })
                        return
                    else:
                        await asyncio.sleep(0.8)

        # Mission complete — real summary
        if phases_failed == 0:
            mission.status = MissionStatus.COMPLETED
            final_msg = f"Epic terminée avec succès — {phases_done}/{phases_done + phases_failed} phases réussies."
        else:
            mission.status = MissionStatus.COMPLETED if phases_done > 0 else MissionStatus.FAILED
            final_msg = f"Epic terminée — {phases_done} réussies, {phases_failed} échouées sur {phases_done + phases_failed} phases."
        run_store.update(mission)
        await _push_sse(session_id, {
            "type": "message",
            "from_agent": "chef_de_programme",
            "from_name": "Alexandre Moreau",
            "from_role": "Chef de Programme",
            "from_avatar": "/static/avatars/chef_de_programme.jpg",
            "content": final_msg,
            "msg_type": "text",
        })

        # Auto-trigger retrospective on epic completion
        try:
            await _auto_retrospective(mission, session_id, phase_summaries, _push_sse)
        except Exception as retro_err:
            logger.warning(f"Auto-retrospective failed: {retro_err}")

    asyncio.create_task(_run_phases())
    return JSONResponse({"status": "running", "mission_id": mission_id})


async def _auto_retrospective(mission, session_id: str, phase_summaries: list, push_sse):
    """Auto-generate retrospective when epic completes, store lessons in global memory."""
    from ..memory.manager import get_memory_manager
    from ..sessions.store import get_session_store
    from ..llm.client import get_llm_client, LLMMessage
    import json as _json

    ss = get_session_store()
    msgs = ss.get_messages(session_id)

    # Build context from phase summaries + messages
    ctx_parts = [f"Epic: {mission.brief[:200]}"]
    for ps in phase_summaries[-8:]:
        ctx_parts.append(ps[:300] if isinstance(ps, str) else str(ps)[:300])
    for m in msgs[-30:]:
        agent = m.get("from_agent", "") if isinstance(m, dict) else getattr(m, "from_agent", "")
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if content:
            ctx_parts.append(f"{agent}: {content[:150]}")

    context = "\n".join(ctx_parts)[:6000]

    prompt = f"""Analyse cette epic terminée et génère une rétrospective.

Contexte:
{context}

Produis un JSON:
{{
  "successes": ["Ce qui a bien fonctionné (3-5 items)"],
  "failures": ["Ce qui a échoué ou peut être amélioré (2-4 items)"],
  "lessons": ["Leçons techniques concrètes et actionnables (3-5 items)"],
  "improvements": ["Actions d'amélioration pour les prochaines epics (2-4 items)"]
}}

Sois CONCRET, TECHNIQUE et ACTIONNABLE. Réponds UNIQUEMENT avec le JSON."""

    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt="Coach Agile expert en rétrospectives SAFe. Analyse factuelle.",
            temperature=0.4, max_tokens=1500,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        retro = _json.loads(raw)
    except Exception:
        retro = {
            "successes": ["Epic completed"],
            "lessons": ["Auto-retrospective needs LLM availability"],
            "failures": [], "improvements": [],
        }

    # Store lessons + improvements in global memory
    mem = get_memory_manager()
    for lesson in retro.get("lessons", []):
        mem.global_store(
            key=f"lesson:epic:{mission.id}",
            value=lesson,
            category="lesson",
            project_id=mission.project_id,
            confidence=0.7,
        )
    for imp in retro.get("improvements", []):
        mem.global_store(
            key=f"improvement:epic:{mission.id}",
            value=imp,
            category="improvement",
            project_id=mission.project_id,
            confidence=0.8,
        )

    # Push retrospective as SSE message
    retro_text = "## Rétrospective automatique\n\n"
    if retro.get("successes"):
        retro_text += "**Réussites:**\n" + "\n".join(f"- {s}" for s in retro["successes"]) + "\n\n"
    if retro.get("lessons"):
        retro_text += "**Leçons:**\n" + "\n".join(f"- {l}" for l in retro["lessons"]) + "\n\n"
    if retro.get("improvements"):
        retro_text += "**Améliorations:**\n" + "\n".join(f"- {i}" for i in retro["improvements"])

    await push_sse(session_id, {
        "type": "message",
        "from_agent": "scrum_master",
        "from_name": "Retrospective",
        "from_role": "Scrum Master",
        "content": retro_text,
        "msg_type": "text",
    })


async def _run_post_phase_hooks(
    phase_id: str, phase_name: str, mission, session_id: str, push_sse
):
    """Run real CI/CD actions after phase completion based on phase type."""
    import subprocess
    from pathlib import Path

    workspace = mission.workspace_path
    if not workspace or not Path(workspace).is_dir():
        return

    phase_key = phase_name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")

    # After dev sprint: auto-commit any uncommitted code + auto screenshots
    if "dev" in phase_key or "sprint" in phase_key:
        try:
            result = subprocess.run(
                ["git", "add", "-A"], cwd=workspace, capture_output=True, text=True, timeout=10
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True, timeout=10
            )
            if status.stdout.strip():
                subprocess.run(
                    ["git", "commit", "-m", f"feat: sprint deliverables — {phase_name}"],
                    cwd=workspace, capture_output=True, text=True, timeout=10
                )
                await push_sse(session_id, {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "CI/CD",
                    "from_role": "Pipeline",
                    "content": f"Code commité dans le workspace ({status.stdout.strip().count(chr(10)) + 1} fichiers)",
                    "phase_id": phase_id,
                    "msg_type": "text",
                })

            # Auto-screenshot: check if any HTML files exist and take screenshots
            ws = Path(workspace)
            html_files = list(ws.glob("*.html")) + list(ws.glob("public/*.html")) + list(ws.glob("src/*.html"))
            if html_files:
                screenshots_dir = ws / "screenshots"
                screenshots_dir.mkdir(exist_ok=True)
                # Take a screenshot of each HTML file using a file:// URL
                shot_paths = []
                for hf in html_files[:3]:  # max 3 screenshots
                    fname = f"{hf.stem}.png"
                    shot_script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage({{ viewport: {{ width: 1280, height: 720 }} }});
    await page.goto('file://{hf}', {{ waitUntil: 'load', timeout: 10000 }});
    await page.screenshot({{ path: '{screenshots_dir / fname}' }});
    await browser.close();
}})();
"""
                    r = subprocess.run(
                        ["node", "-e", shot_script],
                        capture_output=True, text=True, cwd=workspace, timeout=30
                    )
                    if r.returncode == 0 and (screenshots_dir / fname).exists():
                        shot_paths.append(f"screenshots/{fname}")

                if shot_paths:
                    shot_content = "Screenshots automatiques du workspace :\n" + "\n".join(
                        f"[SCREENSHOT:{p}]" for p in shot_paths
                    )
                    await push_sse(session_id, {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "CI/CD",
                        "from_role": "Pipeline",
                        "content": shot_content,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    })
        except Exception as e:
            logger.error("Post-phase git commit/screenshot failed: %s", e)

    # After CI/CD phase: run build if package.json or Dockerfile exists
    if "cicd" in phase_key or "pipeline" in phase_key:
        ws = Path(workspace)
        try:
            if (ws / "package.json").exists():
                result = subprocess.run(
                    ["npm", "install"], cwd=workspace, capture_output=True, text=True, timeout=120
                )
                build_msg = "npm install réussi" if result.returncode == 0 else f"npm install échoué: {result.stderr[:200]}"
                await push_sse(session_id, {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "CI/CD",
                    "from_role": "Pipeline",
                    "content": build_msg,
                    "phase_id": phase_id,
                    "msg_type": "text",
                })
            if (ws / "Dockerfile").exists():
                result = subprocess.run(
                    ["docker", "build", "-t", f"mission-{mission.id}", "."],
                    cwd=workspace, capture_output=True, text=True, timeout=300
                )
                build_msg = f"Docker image mission-{mission.id} construite" if result.returncode == 0 else f"Docker build échoué: {result.stderr[:200]}"
                await push_sse(session_id, {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "CI/CD",
                    "from_role": "Pipeline",
                    "content": build_msg,
                    "phase_id": phase_id,
                    "msg_type": "text",
                })
        except Exception as e:
            logger.error("Post-phase build failed: %s", e)

    # After deploy phase: list workspace files as proof
    if "deploy" in phase_key:
        ws = Path(workspace)
        try:
            files = list(ws.rglob("*"))
            real_files = [f.relative_to(ws) for f in files if f.is_file() and ".git" not in str(f)]
            git_log = subprocess.run(
                ["git", "log", "--oneline", "-10"], cwd=workspace, capture_output=True, text=True, timeout=10
            )
            summary = f"Workspace: {len(real_files)} fichiers\n"
            if real_files:
                summary += "```\n" + "\n".join(str(f) for f in sorted(real_files)[:20]) + "\n```\n"
            if git_log.stdout:
                summary += f"\nGit log:\n```\n{git_log.stdout.strip()}\n```"
            await push_sse(session_id, {
                "type": "message",
                "from_agent": "system",
                "from_name": "CI/CD",
                "from_role": "Pipeline",
                "content": summary,
                "phase_id": phase_id,
                "msg_type": "text",
            })
        except Exception as e:
            logger.error("Post-phase deploy summary failed: %s", e)


def _detect_project_platform(workspace_path: str) -> str:
    """Detect project platform from workspace files.

    Returns one of: macos-native, ios-native, android-native, web-docker, web-node, web-static, unknown
    """
    if not workspace_path:
        return "unknown"
    ws = Path(workspace_path)
    if not ws.exists():
        return "unknown"

    has_swift = (ws / "Package.swift").exists() or (ws / "Sources").exists()
    has_xcode = any(ws.glob("*.xcodeproj")) or any(ws.glob("*.xcworkspace")) or (ws / "project.yml").exists()
    has_kotlin = (ws / "build.gradle").exists() or (ws / "build.gradle.kts").exists()
    has_android = (ws / "app" / "build.gradle").exists() or (ws / "app" / "build.gradle.kts").exists() or (ws / "AndroidManifest.xml").exists()
    has_node = (ws / "package.json").exists()
    has_docker = (ws / "Dockerfile").exists() or (ws / "docker-compose.yml").exists()

    # Check Swift targets: iOS vs macOS
    if has_swift or has_xcode:
        # Look for iOS-specific indicators
        is_ios = False
        for f in [ws / "Package.swift", ws / "project.yml"]:
            if f.exists():
                try:
                    text = f.read_text()[:3000].lower()
                    if "ios" in text or "uikit" in text or "iphone" in text:
                        is_ios = True
                except Exception:
                    pass
        # Check source files for UIKit/SwiftUI with iOS patterns
        if not is_ios:
            for src in list((ws / "Sources").rglob("*.swift"))[:20] if (ws / "Sources").exists() else []:
                try:
                    txt = src.read_text()[:500].lower()
                    if "uiapplication" in txt or "uiscene" in txt or "uidevice" in txt:
                        is_ios = True
                        break
                except Exception:
                    pass
        return "ios-native" if is_ios else "macos-native"

    if has_android or (has_kotlin and not has_node):
        return "android-native"

    if has_docker:
        return "web-docker"

    if has_node:
        return "web-node"

    if (ws / "index.html").exists():
        return "web-static"

    return "unknown"


# Platform-specific QA/deploy/CI prompts
_PLATFORM_QA = {
    "macos-native": {
        "qa-campaign": (
            "TYPE: Application macOS native (Swift/SwiftUI)\n"
            "OUTILS QA ADAPTÉS — PAS de Playwright, PAS de Docker :\n"
            "1. list_files + code_read pour comprendre la structure\n"
            "2. Créez tests/PLAN.md (code_write) — plan de test macOS natif\n"
            "3. Build: build command='swift build'\n"
            "4. Tests unitaires: build command='swift test'\n"
            "5. Bootez simulateur: build command='open -a Simulator'\n"
            "6. SCREENSHOTS par parcours utilisateur (simulator_screenshot) :\n"
            "   - simulator_screenshot filename='01_launch.png'\n"
            "   - simulator_screenshot filename='02_main_view.png'\n"
            "   - simulator_screenshot filename='03_feature_1.png'\n"
            "   - simulator_screenshot filename='04_feature_2.png'\n"
            "   - simulator_screenshot filename='05_settings.png'\n"
            "7. Documentez bugs dans tests/BUGS.md, commitez\n"
            "IMPORTANT: Chaque parcours DOIT avoir un screenshot réel."
        ),
        "qa-execution": (
            "TYPE: Application macOS native (Swift/SwiftUI)\n"
            "1. build command='swift test'\n"
            "2. build command='open -a Simulator'\n"
            "3. SCREENSHOTS: simulator_screenshot pour chaque écran\n"
            "4. tests/REPORT.md avec résultats + screenshots\n"
            "PAS de Playwright. PAS de Docker."
        ),
        "deploy-prod": (
            "TYPE: Application macOS native — PAS de Docker/Azure\n"
            "1. build command='swift build -c release'\n"
            "2. Créez .app bundle ou archive\n"
            "3. simulator_screenshot filename='release_final.png'\n"
            "4. Documentez installation dans INSTALL.md\n"
            "Distribution: TestFlight, .dmg, ou Mac App Store."
        ),
        "cicd": (
            "TYPE: Application macOS native\n"
            "1. Créez .github/workflows/ci.yml avec xcodebuild ou swift build\n"
            "2. Créez scripts/build.sh + scripts/test.sh\n"
            "3. build command='swift build && swift test'\n"
            "4. git_commit\n"
            "PAS de Dockerfile. PAS de docker-compose."
        ),
    },
    "ios-native": {
        "qa-campaign": (
            "TYPE: Application iOS native (Swift/SwiftUI/UIKit)\n"
            "OUTILS QA iOS — simulateur iPhone :\n"
            "1. list_files + code_read\n"
            "2. Créez tests/PLAN.md (code_write)\n"
            "3. Build: build command='xcodebuild -scheme App -sdk iphonesimulator -destination \"platform=iOS Simulator,name=iPhone 16\" build'\n"
            "4. Tests: build command='xcodebuild test -scheme App -sdk iphonesimulator -destination \"platform=iOS Simulator,name=iPhone 16\"'\n"
            "5. SCREENSHOTS par parcours (simulator_screenshot) :\n"
            "   - simulator_screenshot filename='01_splash.png'\n"
            "   - simulator_screenshot filename='02_onboarding.png'\n"
            "   - simulator_screenshot filename='03_main_screen.png'\n"
            "   - simulator_screenshot filename='04_detail.png'\n"
            "   - simulator_screenshot filename='05_profile.png'\n"
            "6. Documentez bugs dans tests/BUGS.md\n"
            "IMPORTANT: Screenshots RÉELS du simulateur iPhone."
        ),
        "qa-execution": (
            "TYPE: Application iOS native\n"
            "1. build command='xcodebuild test -scheme App -sdk iphonesimulator'\n"
            "2. simulator_screenshot pour chaque écran\n"
            "3. tests/REPORT.md\n"
            "PAS de Playwright. PAS de Docker."
        ),
        "deploy-prod": (
            "TYPE: Application iOS — TestFlight ou App Store\n"
            "1. build command='xcodebuild archive -scheme App'\n"
            "2. Export IPA pour TestFlight\n"
            "3. simulator_screenshot filename='release_final.png'\n"
            "Distribution: TestFlight → App Store Connect."
        ),
        "cicd": (
            "TYPE: Application iOS native\n"
            "1. .github/workflows/ci.yml avec xcodebuild + simulateur\n"
            "2. Fastlane si disponible\n"
            "3. build + test command\n"
            "PAS de Docker."
        ),
    },
    "android-native": {
        "qa-campaign": (
            "TYPE: Application Android native (Kotlin/Java)\n"
            "OUTILS QA Android — émulateur :\n"
            "1. list_files + code_read\n"
            "2. Créez tests/PLAN.md (code_write)\n"
            "3. Build: build command='./gradlew assembleDebug'\n"
            "4. Tests: build command='./gradlew testDebugUnitTest'\n"
            "5. Tests instrumentés: build command='./gradlew connectedAndroidTest'\n"
            "6. SCREENSHOTS: build command='adb exec-out screencap -p > screenshots/NOM.png'\n"
            "7. Documentez bugs dans tests/BUGS.md\n"
            "IMPORTANT: Lancez l'émulateur et prenez des screenshots réels."
        ),
        "qa-execution": (
            "TYPE: Application Android native\n"
            "1. build command='./gradlew testDebugUnitTest'\n"
            "2. build command='./gradlew connectedAndroidTest'\n"
            "3. Screenshots via adb\n"
            "4. tests/REPORT.md\n"
            "PAS de Playwright."
        ),
        "deploy-prod": (
            "TYPE: Application Android — Play Store\n"
            "1. build command='./gradlew assembleRelease'\n"
            "2. Signer l'APK/AAB\n"
            "3. Screenshot final\n"
            "Distribution: Google Play Console."
        ),
        "cicd": (
            "TYPE: Application Android native\n"
            "1. .github/workflows/ci.yml avec Gradle + JDK\n"
            "2. Android SDK setup\n"
            "3. ./gradlew build + test\n"
            "PAS de Docker pour le build."
        ),
    },
}

# Web fallback (docker / node / static)
_WEB_QA = {
    "qa-campaign": (
        "TYPE: Application web\n"
        "1. list_files + code_read\n"
        "2. Créez tests/PLAN.md (code_write)\n"
        "3. Tests E2E Playwright :\n"
        "   - tests/e2e/smoke.spec.ts (HTTP 200, 0 erreurs console)\n"
        "   - tests/e2e/journey.spec.ts (parcours complets)\n"
        "4. Lancez: playwright_test spec=tests/e2e/smoke.spec.ts\n"
        "5. SCREENSHOTS par page/parcours :\n"
        "   - screenshot url=http://localhost:3000 filename='01_home.png'\n"
        "   - screenshot url=http://localhost:3000/dashboard filename='02_dashboard.png'\n"
        "   UN SCREENSHOT PAR PAGE\n"
        "6. tests/BUGS.md + git_commit\n"
        "IMPORTANT: Screenshots réels, pas simulés."
    ),
    "qa-execution": (
        "TYPE: Application web\n"
        "1. playwright_test spec=tests/e2e/smoke.spec.ts\n"
        "2. screenshot par page\n"
        "3. tests/REPORT.md"
    ),
    "deploy-prod": (
        "TYPE: Application web\n"
        "1. docker_build pour image\n"
        "2. deploy_azure\n"
        "3. screenshot url=URL_DEPLOYEE filename='deploy_final.png'\n"
        "4. Validation finale"
    ),
    "cicd": (
        "TYPE: Application web\n"
        "1. Dockerfile + docker-compose.yml\n"
        "2. .github/workflows/ci.yml\n"
        "3. scripts/build.sh + test.sh\n"
        "4. build + verify"
    ),
}


def _build_phase_prompt(phase_name: str, pattern: str, brief: str, idx: int, total: int, prev_context: str = "", workspace_path: str = "") -> str:
    """Build a contextual task prompt for each lifecycle phase."""
    platform = _detect_project_platform(workspace_path)

    # Get platform-specific QA/deploy/cicd prompts
    platform_prompts = _PLATFORM_QA.get(platform, {})

    def _qa(key: str) -> str:
        base = platform_prompts.get(key, _WEB_QA.get(key, ""))
        return f"{key.replace('-', ' ').title()} pour «{brief}».\n{base}\nIMPORTANT: Commandes réelles, pas de simulation."

    platform_label = {
        "macos-native": "macOS native (Swift/SwiftUI)",
        "ios-native": "iOS native (Swift/SwiftUI/UIKit)",
        "android-native": "Android native (Kotlin/Java)",
        "web-docker": "web (Docker)",
        "web-node": "web (Node.js)",
        "web-static": "web statique",
    }.get(platform, "")

    prompts = {
        "ideation": (
            f"Nous démarrons l'idéation pour le projet : «{brief}».\n"
            "Chaque expert doit donner son avis selon sa spécialité :\n"
            "- Business Analyst : besoin métier, personas, pain points\n"
            "- UX Designer : parcours utilisateur, wireframes, ergonomie\n"
            "- Architecte : faisabilité technique, stack recommandée\n"
            "- Product Manager : valeur business, ROI, priorisation\n"
            "Débattez et convergez vers une vision produit cohérente."
        ),
        "strategic-committee": (
            f"Comité stratégique GO/NOGO pour le projet : «{brief}».\n"
            "Analysez selon vos rôles respectifs :\n"
            "- CPO : alignement vision produit, roadmap\n"
            "- CTO : risques techniques, capacité équipe\n"
            "- Portfolio Manager : WSJF score, priorisation portefeuille\n"
            "- Lean Portfolio Manager : budget, ROI, lean metrics\n"
            "- DSI : alignement stratégique SI, gouvernance\n"
            "Donnez votre avis : GO, NOGO, ou PIVOT avec justification."
        ),
        "project-setup": (
            f"Constitution du projet «{brief}».\n"
            "- Scrum Master : cérémonie, cadence sprints, outils\n"
            "- RH : staffing, compétences requises, planning\n"
            "- Lead Dev : stack technique, repo, CI/CD setup\n"
            "- Product Owner : backlog initial, user stories prioritisées\n"
            "Définissez l'organisation projet complète."
        ),
        "architecture": (
            f"Design architecture pour «{brief}».\n"
            + (f"PLATEFORME CIBLE: {platform_label}\n" if platform_label else "")
            + "- Architecte : patterns, layers, composants, API design\n"
            "- UX Designer : maquettes, design system, composants UI\n"
            "- Expert Sécurité : threat model, auth, OWASP\n"
            "- DevOps : infra, CI/CD, monitoring, environnements\n"
            "- Lead Dev : revue technique, standards code\n"
            "Produisez le dossier d'architecture consolidé."
        ),
        "dev-sprint": (
            f"Sprint de développement pour «{brief}».\n"
            + (f"PLATEFORME: {platform_label}\n" if platform_label else "")
            + "VOUS DEVEZ UTILISER VOS OUTILS pour écrire du VRAI code dans le workspace.\n\n"
            "WORKFLOW OBLIGATOIRE:\n"
            "1. LIRE LE WORKSPACE: list_files pour voir la structure actuelle\n"
            "2. LIRE L'ARCHITECTURE: code_read sur les fichiers existants (README, Package.swift, etc.)\n"
            "3. DECOMPOSER: Lead Dev donne des tâches fichier-par-fichier aux devs\n"
            "4. CODER: Chaque dev utilise code_write pour créer les fichiers de son périmètre\n"
            "5. TESTER: Utiliser test ou build pour vérifier que le code compile\n"
            "6. COMMITTER: git_commit avec un message descriptif\n\n"
            "IMPORTANT:\n"
            "- Utilisez la stack technique décidée en phase Architecture (voir contexte ci-dessous)\n"
            "- Ne réinventez PAS l'architecture — lisez le workspace et continuez le travail\n"
            "- Chaque dev DOIT appeler code_write au moins 3 fois (fichiers réels, pas du pseudo-code)\n"
            "- NE DISCUTEZ PAS du code. ECRIVEZ-LE avec code_write."
        ),
        "cicd": _qa("cicd"),
        "qa-campaign": _qa("qa-campaign"),
        "qa-execution": _qa("qa-execution"),
        "deploy-prod": _qa("deploy-prod"),
        "tma-routing": (
            f"Routage incidents TMA pour «{brief}».\n"
            "- Support N1 : classification, triage incident\n"
            "- Support N2 : diagnostic technique\n"
            "- QA : reproduction, test regression\n"
            "- Lead Dev : évaluation impact, assignation\n"
            "Classifiez et routez l'incident."
        ),
        "tma-fix": (
            f"Correctif TMA pour «{brief}».\n"
            "UTILISEZ VOS OUTILS pour corriger :\n"
            "1. Lisez le code concerné avec code_read\n"
            "2. Corrigez avec code_edit\n"
            "3. Ecrivez le test de non-regression avec code_write\n"
            "4. Lancez les tests avec playwright_test ou build_tool\n"
            "5. Commitez avec git_commit"
        ),
    }
    # Fallback to generic prompt
    phase_key = phase_name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
    # Try matching by index order
    ordered_keys = list(prompts.keys())
    if idx < len(ordered_keys):
        prompt = prompts[ordered_keys[idx]]
    else:
        prompt = prompts.get(phase_key, (
            f"Phase {idx+1}/{total} : {phase_name} (pattern: {pattern}) pour le projet «{brief}».\n"
            "Chaque agent contribue selon son rôle. Produisez un livrable concret."
        ))

    # Inject previous phase context
    if prev_context:
        prompt += (
            "\n\n--- Contexte des phases précédentes ---\n"
            f"{prev_context}\n"
            "Utilisez ce contexte. Lisez le workspace avec list_files et code_read pour voir le travail déjà fait."
        )

    return prompt
