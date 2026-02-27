"""Web routes — Project management routes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from .helpers import _templates, _parse_body, _is_json_request
from ..schemas import ProjectOut, OkResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_DOMAIN_MARKERS = {
    "Cargo.toml": "rust",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "tsconfig.json": "typescript",
    "angular.json": "angular",
    "svelte.config.js": "svelte",
    "next.config.js": "next",
    "Gemfile": "ruby",
    "go.mod": "go",
    "build.gradle": "kotlin",
    "Package.swift": "swift",
}


def _detect_domains(project_path: str) -> list[str]:
    """Auto-detect tech stack from project files."""
    p = Path(project_path)
    if not p.is_dir():
        return []
    return list({d for f, d in _DOMAIN_MARKERS.items() if (p / f).exists()})


def _auto_git_init(project):
    """Initialize git repo with .gitignore + README if not already a repo."""
    import subprocess

    p = Path(project.path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if (p / ".git").exists():
        return
    try:
        subprocess.run(["git", "init"], cwd=str(p), capture_output=True, timeout=10)
        # .gitignore
        gitignore = p / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "node_modules/\n__pycache__/\n*.pyc\n.env\n.DS_Store\ntarget/\ndist/\nbuild/\n"
            )
        # README
        readme = p / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {project.name}\n\n{project.description or 'A new project.'}\n"
            )
        subprocess.run(["git", "add", "."], cwd=str(p), capture_output=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(p),
            capture_output=True,
            timeout=10,
        )
        logger.info("git init done for %s at %s", project.id, p)
    except Exception as e:
        logger.warning("git init failed for %s: %s", project.id, e)


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Projects list with search + type filter + pagination."""
    from ...projects.manager import get_project_store

    q = request.query_params.get("q", "").strip()
    factory_type = request.query_params.get("type", "").strip()
    has_workspace = request.query_params.get("ws", "").strip()
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 24
    offset = (page - 1) * per_page

    store = get_project_store()
    projects, total = store.search(
        q=q,
        factory_type=factory_type,
        has_workspace=has_workspace,
        limit=per_page,
        offset=offset,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    return _templates(request).TemplateResponse(
        "projects.html",
        {
            "request": request,
            "page_title": "Projects",
            "projects": [
                {"info": p, "git": None, "tasks": None, "has_workspace": p.exists}
                for p in projects
            ],
            "q": q,
            "factory_type": factory_type,
            "has_workspace": has_workspace,
            "page": page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.post("/api/projects/heal")
async def projects_heal():
    """Scaffold all projects: ensure workspace + git + docker + docs + code exist."""
    import asyncio
    from ...projects.manager import heal_all_projects

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, heal_all_projects)
    return result


@router.post("/api/projects/{project_id}/scaffold")
async def project_scaffold(project_id: str):
    """Scaffold a single project (idempotent)."""
    import asyncio
    import functools
    from ...projects.manager import get_project_store, scaffold_project

    p = get_project_store().get(project_id)
    if not p:
        from fastapi import HTTPException

        raise HTTPException(404, "project not found")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(scaffold_project, p))


@router.get("/api/projects/{project_id}/git-status")
async def project_git_status(project_id: str):
    """Lazy-load git status for a single project (called via HTMX)."""
    import asyncio
    import functools
    from ...projects.manager import get_project_store
    from ...projects import git_service

    project = get_project_store().get(project_id)
    if not project or not project.has_git:
        return HTMLResponse("")
    loop = asyncio.get_event_loop()
    git = await loop.run_in_executor(
        None, functools.partial(git_service.get_status, project.path)
    )
    if not git:
        return HTMLResponse('<span class="text-muted">no git</span>')
    branch = git.get("branch", "?")
    clean = git.get("clean", True)
    parts = [
        f'<div class="git-branch">'
        f'<svg class="icon icon-xs"><use href="#icon-git-branch"/></svg> {branch}</div>'
    ]
    if not clean:
        counts = []
        if git.get("staged"):
            counts.append(f'<span class="git-count staged">+{git["staged"]}</span>')
        if git.get("modified"):
            counts.append(f'<span class="git-count modified">~{git["modified"]}</span>')
        if git.get("untracked"):
            counts.append(
                f'<span class="git-count untracked">?{git["untracked"]}</span>'
            )
        if counts:
            parts.append(f'<div class="git-dirty">{"".join(counts)}</div>')
    else:
        parts.append('<span class="git-clean-badge">clean</span>')
    msg = git.get("commit_message", "")
    if msg:
        short = msg[:50] + ("..." if len(msg) > 50 else "")
        date = git.get("commit_date", "")
        parts.append(
            f'<div class="project-card-commit">'
            f'<svg class="icon icon-xs"><use href="#icon-git-commit"/></svg>'
            f'<span class="commit-msg">{short}</span>'
            f'<span class="commit-date">{date}</span></div>'
        )
    return HTMLResponse("\n".join(parts))


@router.get("/projects/{project_id}/overview", response_class=HTMLResponse)
async def project_overview(request: Request, project_id: str):
    """Project overview page — created from ideation, shows epic/features/team."""
    from ...projects.manager import get_project_store
    from ...missions.store import get_mission_store
    from ...missions.product import get_product_backlog
    from ...agents.store import get_agent_store

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
            features_enriched.append(
                {
                    "id": f.id,
                    "name": f.name,
                    "description": f.description,
                    "acceptance_criteria": f.acceptance_criteria,
                    "story_points": f.story_points,
                    "status": f.status,
                    "stories": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "story_points": s.story_points,
                            "status": s.status,
                            "acceptance_criteria": s.acceptance_criteria,
                        }
                        for s in stories
                    ],
                }
            )
        team_data = (ep.config or {}).get("team", [])
        stack = (ep.config or {}).get("stack", [])
        epics_enriched.append(
            {
                "id": ep.id,
                "name": ep.name,
                "description": ep.description,
                "goal": ep.goal,
                "status": ep.status,
                "features": features_enriched,
                "team": team_data,
                "stack": stack,
            }
        )

    # Resolve team agents with photos
    team_agents = []
    if epics_enriched:
        for t in epics_enriched[0].get("team", []):
            role = t.get("role", "")
            agent = agent_store.get(role)
            avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
            avatar_url = ""
            if agent and (avatar_dir / f"{agent.id}.jpg").exists():
                avatar_url = f"/static/avatars/{agent.id}.jpg"
            team_agents.append(
                {
                    "role": role,
                    "label": t.get("label", role),
                    "name": agent.name if agent else t.get("label", role),
                    "avatar_url": avatar_url,
                    "persona": (agent.persona or "") if agent else "",
                }
            )

    return _templates(request).TemplateResponse(
        "project_overview.html",
        {
            "request": request,
            "page_title": f"Projet: {project.name}",
            "project": project,
            "epics": epics_enriched,
            "team_agents": team_agents,
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    """Single project detail view with vision, agents, sessions."""
    from ...projects.manager import get_project_store
    from ...projects import git_service, factory_tasks
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store

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
    # Resolve lead avatar photo
    lead_avatar_url = ""
    if lead:
        from pathlib import Path as _Path

        _av_dir = _Path(__file__).parent.parent / "static" / "avatars"
        for ext in ("jpg", "svg"):
            if (_av_dir / f"{lead.id}.{ext}").exists():
                lead_avatar_url = f"/static/avatars/{lead.id}.{ext}"
                break
    # Get workflows linked to this project
    workflows = []
    try:
        from ...workflows.store import get_workflow_store

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
            from ...memory.project_files import get_project_memory

            pmem = get_project_memory(project_id, project.path)
            memory_files = pmem.files
        except Exception:
            pass
    # Load missions for this project
    project_missions = []
    try:
        from ...missions.store import get_mission_store

        m_store = get_mission_store()
        project_missions = m_store.list_missions(project_id=project_id)
    except Exception:
        pass
    return _templates(request).TemplateResponse(
        "project_detail.html",
        {
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
            "lead_avatar_url": lead_avatar_url,
            "messages": messages,
            "memory_files": memory_files,
            "workflows": workflows,
            "missions": project_missions,
        },
    )


# ── Project Board (Kanban) ───────────────────────────────────────


@router.get("/projects/{project_id}/board", response_class=HTMLResponse)
async def project_board_page(request: Request, project_id: str):
    """Kanban board view for a project."""
    from ...projects.manager import get_project_store
    from ...agents.store import get_agent_store
    from ...missions.store import get_mission_store, get_mission_run_store
    from ...missions.product import get_product_backlog

    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    agents_by_id = {a.id: a for a in all_agents}

    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    def _avatar(agent_id):
        jpg = avatar_dir / f"{agent_id}.jpg"
        svg = avatar_dir / f"{agent_id}.svg"
        if jpg.exists():
            return f"/static/avatars/{agent_id}.jpg"
        if svg.exists():
            return f"/static/avatars/{agent_id}.svg"
        return ""

    # Build task list from missions + mission_run phases (live)
    tasks = []
    try:
        m_store = get_mission_store()
        run_store = get_mission_run_store()
        missions = m_store.list_missions(project_id=project_id)
        all_runs = run_store.list_runs(limit=100)
        runs_by_mission = {}
        for r in all_runs:
            if r.parent_mission_id:
                runs_by_mission[r.parent_mission_id] = r
            runs_by_mission[r.id] = r

        status_col = {
            "planning": "backlog",
            "active": "active",
            "review": "review",
            "completed": "done",
            "deployed": "done",
        }
        status_labels = {
            "planning": "Planifié",
            "active": "En cours",
            "review": "En revue",
            "completed": "Terminé",
            "deployed": "Déployé",
        }
        for m in missions:
            col = status_col.get(m.status, "backlog")
            agent = agents_by_id.get(m.lead_agent_id) if m.lead_agent_id else None
            tasks.append(
                {
                    "title": m.title,
                    "col": col,
                    "status_label": status_labels.get(m.status, m.status),
                    "avatar_url": _avatar(agent.id) if agent else "",
                    "agent_name": agent.name if agent else "",
                }
            )
            # Also add phases from mission_run as sub-tasks
            run = runs_by_mission.get(m.id)
            if run and run.phases:
                phase_col_map = {
                    "done": "done",
                    "done_with_issues": "done",
                    "running": "active",
                    "pending": "backlog",
                    "failed": "review",
                }
                for ph in run.phases:
                    ph_status = (
                        ph.status.value
                        if hasattr(ph.status, "value")
                        else str(ph.status)
                    )
                    tasks.append(
                        {
                            "title": ph.phase_name or ph.phase_id,
                            "col": phase_col_map.get(ph_status, "backlog"),
                            "status_label": ph_status.replace("_", " ").title(),
                            "avatar_url": "",
                            "agent_name": "",
                        }
                    )
    except Exception:
        pass

    # Agent flow nodes (project team)
    flow_nodes = []
    flow_edges = []
    team_agents = [a for a in all_agents if _avatar(a.id)][:6]
    positions = [(60, 100), (160, 50), (160, 150), (280, 100), (380, 50), (380, 150)]
    for i, ag in enumerate(team_agents[:6]):
        x, y = positions[i] if i < len(positions) else (60 + i * 80, 100)
        flow_nodes.append(
            {"x": x, "y": y, "label": ag.name.split()[-1] if ag.name else "Agent"}
        )
    for i in range(len(flow_nodes) - 1):
        n1, n2 = flow_nodes[i], flow_nodes[i + 1]
        flow_edges.append(
            {"x1": n1["x"] + 25, "y1": n1["y"], "x2": n2["x"] - 25, "y2": n2["y"]}
        )

    # Backlog items (live from DB)
    backlog = get_product_backlog()
    story_count = 0
    feature_count = 0
    unestimated = 0
    try:
        for m in missions:
            features = backlog.list_features(m.id)
            feature_count += len(features)
            for f in features:
                stories = backlog.list_stories(f.id)
                story_count += len(stories)
                unestimated += sum(1 for s in stories if not s.story_points)
    except Exception:
        pass
    backlog_items = [
        {
            "title": "Stories non estimées",
            "count": unestimated,
            "color": "var(--yellow)",
        },
        {"title": "Features", "count": feature_count, "color": "var(--blue)"},
        {"title": "User stories", "count": story_count, "color": "var(--green)"},
    ]

    # Git activity (live from project workspace)
    pull_requests = []
    try:
        if project.path and project.has_git:
            import subprocess

            result = subprocess.run(
                ["git", "--no-pager", "log", "--oneline", "-5"],
                cwd=project.path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in (result.stdout or "").strip().split("\n"):
                if line.strip():
                    pull_requests.append({"title": line.strip(), "status": "Commit"})
    except Exception:
        pass

    # Operational missions (TMA, Security, Debt — auto-provisioned)
    ops_missions = {"tma": None, "security": None, "debt": None}
    epics_list = []
    for m in missions:
        cfg = m.config or {}
        if cfg.get("auto_provisioned"):
            if m.type == "program" and "tma" in (m.workflow_id or ""):
                incidents = cfg.get("recurring_incidents", {})
                ops_missions["tma"] = {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "incident_count": sum(incidents.values()),
                    "recurring": sum(1 for v in incidents.values() if v >= 3),
                }
            elif m.type == "security":
                ops_missions["security"] = {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "schedule": cfg.get("schedule", "weekly"),
                }
            elif m.type == "debt":
                ops_missions["debt"] = {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "schedule": cfg.get("schedule", "monthly"),
                }
        else:
            epics_list.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "type": m.type,
                    "wsjf": m.wsjf_score,
                }
            )

    # CI/CD pipeline status
    cicd_file = None
    if project.path:
        ci_path = Path(project.path) / ".github" / "workflows" / "ci.yml"
        if ci_path.exists():
            cicd_file = str(ci_path)

    # Velocity metrics
    total_sp_planned = 0
    total_sp_done = 0
    for m in missions:
        features = backlog.list_features(m.id)
        for f in features:
            stories = backlog.list_stories(f.id)
            for s in stories:
                sp = s.story_points or 0
                total_sp_planned += sp
                if s.status in ("done", "accepted"):
                    total_sp_done += sp
    velocity_pct = (
        round(total_sp_done * 100 / total_sp_planned) if total_sp_planned else 0
    )

    # PI cadence — phases from active mission runs
    pi_phases = []
    for m in missions:
        run = runs_by_mission.get(m.id)
        if run and run.phases:
            for ph in run.phases:
                ph_status = (
                    ph.status.value if hasattr(ph.status, "value") else str(ph.status)
                )
                pi_phases.append(
                    {
                        "name": ph.phase_name or ph.phase_id,
                        "status": ph_status,
                        "mission": m.name[:25],
                    }
                )

    return _templates(request).TemplateResponse(
        "project_board.html",
        {
            "request": request,
            "page_title": f"Board — {project.name}",
            "project": project,
            "tasks": tasks,
            "flow_nodes": flow_nodes,
            "flow_edges": flow_edges,
            "backlog_items": backlog_items,
            "pull_requests": pull_requests,
            "ops_missions": ops_missions,
            "epics_list": epics_list,
            "has_cicd": cicd_file is not None,
            "velocity": {
                "planned": total_sp_planned,
                "done": total_sp_done,
                "pct": velocity_pct,
            },
            "pi_phases": pi_phases,
        },
    )


# ── API: Projects ────────────────────────────────────────────────


@router.get("/api/projects", responses={200: {"model": list[ProjectOut]}})
async def api_projects():
    """List all projects (JSON)."""
    from ...projects.manager import get_project_store

    store = get_project_store()
    return JSONResponse(
        [
            {
                "id": p.id,
                "name": p.name,
                "path": p.path,
                "factory_type": p.factory_type,
                "domains": p.domains,
                "lead_agent_id": p.lead_agent_id,
                "status": p.status,
                "has_vision": bool(p.vision),
                "values": p.values,
            }
            for p in store.list_all()
        ]
    )


@router.post("/api/projects", responses={200: {"model": OkResponse}})
async def create_project(request: Request):
    """Create a new project."""
    from ...projects.manager import get_project_store, Project

    form = await _parse_body(request)
    store = get_project_store()
    p = Project(
        id=str(form.get("id", "")),
        name=str(form.get("name", "")),
        path=str(form.get("path", "")),
        description=str(form.get("description", "")),
        factory_type=str(form.get("factory_type", "standalone")),
        lead_agent_id=str(form.get("lead_agent_id", "brain")),
        values=[
            v.strip()
            for v in str(form.get("values", "quality,feedback")).split(",")
            if v.strip()
        ],
    )
    # Auto-detect domains from path
    if p.path and not p.domains:
        p.domains = _detect_domains(p.path)
    # Auto-load vision
    if p.exists:
        p.vision = p.load_vision_from_file()
    store.create(p)

    # Auto-provision TMA, Security, Tech Debt missions
    try:
        store.auto_provision(p.id, p.name)
    except Exception as e:
        logger.warning("auto_provision failed for %s: %s", p.id, e)

    # Auto-generate CI/CD pipeline
    if p.path:
        try:
            from ...projects.manager import ProjectStore

            ProjectStore.generate_cicd(p.path, p.domains or [])
        except Exception as e:
            logger.warning("generate_cicd failed for %s: %s", p.id, e)

    # Auto-init git repo if path specified and not already a repo
    if p.path:
        _auto_git_init(p)

    if _is_json_request(request):
        return JSONResponse({"ok": True, "project": {"id": p.id, "name": p.name}})
    return RedirectResponse(f"/projects/{p.id}", status_code=303)


@router.post("/api/projects/{project_id}/vision")
async def update_vision(request: Request, project_id: str):
    """Update project vision."""
    from ...projects.manager import get_project_store

    data = await _parse_body(request)
    store = get_project_store()
    store.update_vision(project_id, str(data.get("vision", "")))
    return HTMLResponse('<span class="badge badge-green">Saved</span>')


@router.post("/api/projects/{project_id}/chat")
async def project_chat(request: Request, project_id: str):
    """Quick chat with a project's lead agent — creates or reuses session."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...sessions.runner import handle_user_message
    from ...projects.manager import get_project_store

    data = await _parse_body(request)
    content = str(data.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    proj = get_project_store().get(project_id)
    if not proj:
        return HTMLResponse("Project not found", status_code=404)

    store = get_session_store()
    # Find or create active session for this project
    sessions = [
        s
        for s in store.list_all()
        if s.project_id == project_id and s.status == "active"
    ]
    sessions.sort(key=lambda s: s.created_at or "", reverse=True)
    if sessions:
        session = sessions[0]
    else:
        session = store.create(
            SessionDef(
                name=f"{proj.name} — Chat",
                goal="Project conversation",
                project_id=project_id,
                status="active",
                config={"lead_agent": proj.lead_agent_id or "brain"},
            )
        )
        store.add_message(
            MessageDef(
                session_id=session.id,
                from_agent="system",
                message_type="system",
                content=f"Session started for project {proj.name}",
            )
        )

    # Store user message
    store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="user",
            message_type="text",
            content=content,
        )
    )

    # Get agent response
    agent_msg = await handle_user_message(session.id, content, proj.lead_agent_id or "")

    # For HTMX: return both the user message and agent response as chat bubbles
    import html as html_mod
    import markdown as md_lib

    user_html = (
        f'<div class="chat-msg chat-msg-user">'
        f'<div class="chat-msg-body"><div class="chat-msg-text">{html_mod.escape(content)}</div></div>'
        f'<div class="chat-msg-avatar user">S</div>'
        f"</div>"
    )
    if agent_msg:
        agent_content = (
            agent_msg.get("content", "")
            if isinstance(agent_msg, dict)
            else getattr(agent_msg, "content", str(agent_msg))
        )
        # Render tool calls if present
        tools_html = ""
        tool_calls = None
        if isinstance(agent_msg, dict):
            tool_calls = (
                agent_msg.get("metadata", {}).get("tool_calls")
                if agent_msg.get("metadata")
                else None
            )
        elif hasattr(agent_msg, "metadata") and agent_msg.metadata:
            tool_calls = agent_msg.metadata.get("tool_calls")
        if tool_calls:
            pills = "".join(
                f'<span class="chat-tool-pill"><svg class="icon icon-xs"><use href="#icon-wrench"/></svg> {html_mod.escape(str(tc.get("name", tc) if isinstance(tc, dict) else tc))}</span>'
                for tc in tool_calls
            )
            tools_html = f'<div class="chat-msg-tools">{pills}</div>'
        # Render markdown to HTML
        rendered = md_lib.markdown(
            str(agent_content), extensions=["fenced_code", "tables", "nl2br"]
        )
        agent_html = (
            f'<div class="chat-msg chat-msg-agent">'
            f'<div class="chat-msg-avatar"><svg class="icon icon-sm"><use href="#icon-bot"/></svg></div>'
            f'<div class="chat-msg-body">'
            f'<div class="chat-msg-sender">{html_mod.escape(proj.name)}</div>'
            f'<div class="chat-msg-text md-rendered">{rendered}</div>'
            f"{tools_html}"
            f"</div></div>"
        )
        return HTMLResponse(user_html + agent_html)
    return HTMLResponse(user_html)


# ── Conversation Management ──────────────────────────────────────


@router.post("/api/projects/{project_id}/conversations")
async def create_conversation(request: Request, project_id: str):
    """Create a new conversation session for a project."""
    from ...sessions.store import get_session_store, SessionDef
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    store = get_session_store()
    # Archive any existing active CHAT sessions (not workflow sessions)
    active = [
        s
        for s in store.list_all()
        if s.project_id == project_id
        and s.status == "active"
        and not (s.config or {}).get("workflow_id")
    ]
    for s in active:
        store.update_status(s.id, "completed")

    session = store.create(
        SessionDef(
            name=f"{proj.name} — {datetime.utcnow().strftime('%b %d, %H:%M')}",
            goal="Project conversation",
            project_id=project_id,
            status="active",
            config={"lead_agent": proj.lead_agent_id or "brain"},
        )
    )
    return JSONResponse({"session_id": session.id})


# ── Streaming Chat (SSE) ────────────────────────────────────────


@router.post("/api/projects/{project_id}/chat/stream")
async def project_chat_stream(request: Request, project_id: str):
    """Stream agent response via SSE — shows live progress to the user."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...sessions.runner import _build_context
    from ...projects.manager import get_project_store
    from ...agents.store import get_agent_store
    from ...agents.executor import get_executor

    data = await _parse_body(request)
    content = str(data.get("content", "")).strip()
    session_id = str(data.get("session_id", "")).strip()
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
        sessions = [
            s
            for s in store.list_all()
            if s.project_id == project_id and s.status == "active"
        ]
        sessions.sort(key=lambda s: s.created_at or "", reverse=True)
        if sessions:
            session = sessions[0]
    if not session:
        session = store.create(
            SessionDef(
                name=f"{proj.name} — {datetime.utcnow().strftime('%b %d, %H:%M')}",
                goal="Project conversation",
                project_id=project_id,
                status="active",
                config={"lead_agent": proj.lead_agent_id or "brain"},
            )
        )

    # Store user message
    store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="user",
            message_type="text",
            content=content,
        )
    )

    # Find agent
    agent_store = get_agent_store()
    agent_id = proj.lead_agent_id or "brain"
    agent = agent_store.get(agent_id)
    if not agent:
        all_agents = agent_store.list_all()
        agent = all_agents[0] if all_agents else None

    async def event_generator():
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
                if (
                    name == "deep_search"
                    and isinstance(args, dict)
                    and "status" in args
                ):
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
            store.add_message(
                MessageDef(
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
                )
            )

            # Build final HTML
            rendered = md_lib.markdown(
                str(result.content), extensions=["fenced_code", "tables", "nl2br"]
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
    from ...sessions.runner import add_sse_listener, remove_sse_listener

    queue = add_sse_listener(session_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    payload = (
                        json.dumps(event) if isinstance(event, dict) else str(event)
                    )
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
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Project Workspace ──────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/workspace", response_class=HTMLResponse)
async def project_workspace(request: Request, project_id: str):
    """Replit-style workspace view for a project."""
    from ...projects.manager import get_project_store

    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    # Detect preview URL from docker-compose / package.json / .env
    preview_url = _detect_preview_url(project.path)

    templates = _templates(request)
    return templates.TemplateResponse(
        "project_workspace.html",
        {
            "request": request,
            "project": project,
            "preview_url": preview_url,
        },
    )


def _detect_preview_url(root_path: str) -> str:
    """Detect the app preview URL from project config files."""
    import re as _re

    p = Path(root_path)
    # docker-compose ports: "HOST:CONTAINER"
    for compose_name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        cf = p / compose_name
        if cf.exists():
            try:
                text = cf.read_text(errors="ignore")
                m = _re.search(r'["\']?(\d{4,5}):(\d{2,5})["\']?', text)
                if m:
                    return f"http://localhost:{m.group(1)}"
            except Exception:
                pass
    # .env PORT=XXXX
    env_file = p / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(errors="ignore").splitlines():
                m = _re.match(r"PORT\s*=\s*(\d+)", line.strip())
                if m:
                    return f"http://localhost:{m.group(1)}"
        except Exception:
            pass
    # package.json scripts.start contains port
    pkg = p / "package.json"
    if pkg.exists():
        try:
            import json as _json

            data = _json.loads(pkg.read_text())
            start = (data.get("scripts") or {}).get("start", "")
            m = _re.search(r"PORT=(\d+)|--port[= ](\d+)", start)
            if m:
                port = m.group(1) or m.group(2)
                return f"http://localhost:{port}"
        except Exception:
            pass
    return ""


@router.get("/api/projects/{project_id}/workspace/tool-calls")
async def ws_tool_calls(project_id: str):
    """Return last 50 tool calls for sessions linked to this project."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT tc.tool_name, tc.parameters_json, tc.result_json, tc.success, tc.duration_ms, tc.timestamp
            FROM tool_calls tc
            LEFT JOIN sessions s ON tc.session_id = s.id
            WHERE s.project_id = ?
            ORDER BY tc.timestamp DESC LIMIT 50
        """,
            (project_id,),
        ).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        result = r[2] or ""
        try:
            import json as _json

            rd = _json.loads(result)
            output = rd.get("output") or rd.get("stdout") or str(rd)[:200]
        except Exception:
            output = result[:200]
        items.append(
            {
                "tool_name": r[0],
                "parameters_json": r[1],
                "success": bool(r[3]),
                "duration_ms": r[4],
                "timestamp": str(r[5] or ""),
                "output": output,
            }
        )
    return JSONResponse({"items": items})


@router.get("/api/projects/{project_id}/workspace/run")
async def ws_run_command(project_id: str, cmd: str, request: Request):
    """SSE endpoint — runs a shell command in project root and streams output."""
    import asyncio
    import shlex
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    cwd = proj.path if proj else "."

    async def stream():
        try:
            args = shlex.split(cmd)
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            async for line in proc.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                yield f"data: {text}\n\n"
            await proc.wait()
        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/projects/{project_id}/workspace/files")
async def ws_list_files(project_id: str, path: str = "."):
    """List directory contents for the project."""
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"items": []})
    root = Path(proj.path)
    target = (root / path).resolve()
    # Security: stay within root
    try:
        target.relative_to(root)
    except ValueError:
        target = root
    items = []
    SKIP = {".git", "__pycache__", "node_modules", ".next", "dist", ".venv", "venv"}
    if target.is_dir():
        try:
            for entry in sorted(
                target.iterdir(), key=lambda e: (e.is_file(), e.name.lower())
            ):
                if entry.name in SKIP or entry.name.startswith("."):
                    continue
                rel = str(entry.relative_to(root))
                items.append(
                    {
                        "name": entry.name,
                        "path": rel,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    }
                )
        except PermissionError:
            pass
    return JSONResponse({"items": items, "cwd": str(target.relative_to(root))})


@router.get("/api/projects/{project_id}/workspace/file")
async def ws_read_file(project_id: str, path: str):
    """Return file content (max 100KB)."""
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "project not found"})
    root = Path(proj.path)
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return JSONResponse({"error": "access denied"})
    if not target.is_file():
        return JSONResponse({"error": "not a file"})
    if target.stat().st_size > 200_000:
        return JSONResponse({"error": "file too large (>200KB)"})
    try:
        content = target.read_text(errors="replace")
    except Exception as e:
        return JSONResponse({"error": str(e)})
    return JSONResponse({"content": content, "path": path})


@router.get("/api/projects/{project_id}/workspace/docker")
async def ws_docker_status(project_id: str):
    """Return docker container status for this project."""
    import subprocess
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"containers": []})
    project_name = (proj.name or project_id).lower().replace(" ", "-").replace("_", "-")
    containers = []
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            name, image, status = parts[0], parts[1], parts[2]
            ports = parts[3] if len(parts) > 3 else ""
            # Filter: container name contains project name or project path fragment
            if project_name not in name.lower() and project_id[:8] not in name.lower():
                continue
            # Get last 30 log lines
            logs = ""
            try:
                lr = subprocess.run(
                    ["docker", "logs", "--tail", "30", name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                logs = (lr.stdout + lr.stderr).strip()[-2000:]
            except Exception:
                pass
            containers.append(
                {
                    "name": name,
                    "image": image,
                    "status": status,
                    "ports": ports,
                    "logs": logs,
                }
            )
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Detect Docker config files in project path regardless of running containers
    docker_files = []
    if proj.path:
        import os

        for fname in [
            "docker-compose.yml",
            "docker-compose.yaml",
            "Dockerfile",
            "Dockerfile.dev",
        ]:
            fpath = os.path.join(proj.path, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(8000)
                    docker_files.append({"name": fname, "content": content})
                except Exception:
                    docker_files.append({"name": fname, "content": ""})

    return JSONResponse({"containers": containers, "docker_files": docker_files})


@router.post("/api/projects/{project_id}/workspace/docker/{action}")
async def ws_docker_action(project_id: str, action: str, request: Request):
    """Perform docker action: start / stop / rebuild / compose_up."""
    import shutil
    import subprocess

    if not shutil.which("docker"):
        return JSONResponse(
            {"error": "Docker n'est pas disponible sur ce serveur"}, status_code=503
        )

    body = await _parse_body(request)
    container = body.get("container", "")
    if action not in ("start", "stop", "rebuild", "compose_up"):
        return JSONResponse({"error": "invalid"}, status_code=400)
    try:
        from ...projects.manager import get_project_store

        proj = get_project_store().get(project_id)
        cwd = proj.path if proj else None

        if action == "compose_up":
            if not cwd:
                return JSONResponse(
                    {"error": "workspace path not configured"}, status_code=400
                )
            compose_file = Path(cwd) / "docker-compose.yml"
            if not compose_file.exists():
                return JSONResponse(
                    {"error": "docker-compose.yml not found"}, status_code=400
                )
            result = subprocess.run(
                ["docker", "compose", "up", "--build", "-d"],
                cwd=cwd,
                timeout=180,
                capture_output=True,
                text=True,
            )
            return JSONResponse(
                {
                    "ok": result.returncode == 0,
                    "output": (result.stdout + result.stderr)[-2000:],
                }
            )
        elif not container:
            return JSONResponse({"error": "container required"}, status_code=400)
        elif action == "start":
            subprocess.run(["docker", "start", container], timeout=15)
        elif action == "stop":
            subprocess.run(["docker", "stop", container], timeout=15)
        elif action == "rebuild":
            if cwd and (Path(cwd) / "docker-compose.yml").exists():
                subprocess.run(
                    ["docker", "compose", "up", "--build", "-d"], cwd=cwd, timeout=120
                )
            else:
                subprocess.run(["docker", "restart", container], timeout=15)
    except Exception as e:
        return JSONResponse({"error": str(e)})
    return JSONResponse({"ok": True})


@router.get("/api/projects/{project_id}/workspace/agents")
async def ws_agents(project_id: str):
    """Return active agents/sessions for this project."""
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store

    sess_store = get_session_store()
    agent_store = get_agent_store()
    sessions = [
        s
        for s in sess_store.list_all()
        if s.project_id == project_id and s.status in ("active", "running", "pending")
    ]
    items = []
    for s in sessions[:20]:
        agent = agent_store.get(s.agent_id or "") if s.agent_id else None
        avatar = ""
        if agent:
            from pathlib import Path as _P

            av = _P(__file__).parent.parent / "static" / "avatars" / f"{agent.id}.jpg"
            if av.exists():
                avatar = f"/static/avatars/{agent.id}.jpg"
        items.append(
            {
                "session_id": s.id,
                "agent_id": s.agent_id or "",
                "agent_name": agent.name if agent else (s.agent_id or "Agent"),
                "mission_title": s.title or s.id,
                "status": s.status,
                "phase": getattr(s, "current_phase", "") or "",
                "progress": getattr(s, "progress_pct", 0) or 0,
                "avatar": avatar,
            }
        )
    return JSONResponse({"items": items})


@router.get("/api/projects/{project_id}/workspace/git")
async def ws_git(project_id: str):
    """Return git log, changes and branch for this project."""
    from ...projects.manager import get_project_store
    from ...projects import git_service

    proj = get_project_store().get(project_id)
    if not proj or not proj.has_git:
        return JSONResponse({"commits": [], "changes": [], "branch": ""})
    commits = [
        c.__dict__ if hasattr(c, "__dict__") else dict(c)
        for c in git_service.get_log(proj.path, 20)
    ]
    changes = [
        c.__dict__ if hasattr(c, "__dict__") else dict(c)
        for c in git_service.get_changes(proj.path)
    ]
    git_status = git_service.get_status(proj.path)
    branch = git_status.branch if git_status else ""
    return JSONResponse({"commits": commits, "changes": changes, "branch": branch})


@router.post("/api/projects/{project_id}/workspace/git/commit")
async def ws_git_commit(project_id: str, request: Request):
    """Run git commit (and optionally push) in project directory."""
    import subprocess

    body = await _parse_body(request)
    message = body.get("message", "").strip()
    do_push = bool(body.get("push"))
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "project not found"}, status_code=404)
    try:
        subprocess.run(["git", "add", "-A"], cwd=proj.path, timeout=10, check=True)
        subprocess.run(
            ["git", "commit", "-m", message], cwd=proj.path, timeout=15, check=True
        )
        if do_push:
            subprocess.run(["git", "push"], cwd=proj.path, timeout=30, check=True)
    except subprocess.CalledProcessError as e:
        return JSONResponse({"error": str(e)})
    return JSONResponse({"ok": True})


@router.get("/api/projects/{project_id}/workspace/git/diff")
async def ws_git_diff(project_id: str, file: str = ""):
    """Return git diff for a specific file or full diff."""
    import subprocess
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"diff": ""})
    try:
        args = ["git", "diff", "HEAD", "--", file] if file else ["git", "diff", "HEAD"]
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=proj.path, timeout=10
        )
        diff = result.stdout[:50000]
        if not diff:
            result2 = subprocess.run(
                ["git", "diff", "--cached", "--", file]
                if file
                else ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                cwd=proj.path,
                timeout=10,
            )
            diff = result2.stdout[:50000]
    except Exception as e:
        return JSONResponse({"diff": str(e)})
    return JSONResponse({"diff": diff or "(no diff)"})


@router.get("/api/projects/{project_id}/workspace/db")
async def ws_db_list(project_id: str):
    """Detect SQLite database files in project and list their tables."""
    import sqlite3
    import os
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"files": []})

    files = []
    try:
        for root, dirs, fnames in os.walk(proj.path):
            # Skip hidden dirs and common non-project dirs
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", "venv", ".git")
            ]
            for fname in fnames:
                if fname.endswith((".db", ".sqlite", ".sqlite3")):
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, proj.path)
                    tables = []
                    try:
                        conn = sqlite3.connect(fpath)
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                        )
                        for (tname,) in cur.fetchall():
                            try:
                                cur.execute(f'SELECT COUNT(*) FROM "{tname}"')
                                count = cur.fetchone()[0]
                            except Exception:
                                count = 0
                            tables.append({"name": tname, "row_count": count})
                        conn.close()
                    except Exception:
                        pass
                    files.append({"name": fname, "file": rel, "tables": tables})
    except Exception:
        pass

    return JSONResponse({"files": files})


@router.post("/api/projects/{project_id}/workspace/db/query")
async def ws_db_query(project_id: str, request: Request):
    """Execute a SELECT query on a SQLite database file."""
    import sqlite3
    import os
    from ...projects.manager import get_project_store

    body = await _parse_body(request)
    file_rel = body.get("file", "")
    sql = body.get("sql", "").strip()

    if not sql:
        return JSONResponse({"error": "No SQL provided"})

    # Security: only allow SELECT / PRAGMA
    sql_upper = sql.upper().lstrip()
    if not (
        sql_upper.startswith("SELECT")
        or sql_upper.startswith("PRAGMA")
        or sql_upper.startswith("WITH")
    ):
        return JSONResponse(
            {"error": "Only SELECT, WITH, and PRAGMA queries are allowed"}
        )

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"error": "Project not found"})

    fpath = os.path.normpath(os.path.join(proj.path, file_rel))
    if not fpath.startswith(proj.path):
        return JSONResponse({"error": "Access denied"})
    if not os.path.isfile(fpath):
        return JSONResponse({"error": f"File not found: {file_rel}"})

    try:
        conn = sqlite3.connect(f"file:{fpath}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows_raw = cur.fetchmany(500)
        if rows_raw:
            columns = [d[0] for d in cur.description]
            rows = [list(row) for row in rows_raw]
        else:
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = []
        conn.close()
    except Exception as e:
        return JSONResponse({"error": str(e)})

    return JSONResponse({"columns": columns, "rows": rows})


@router.get("/api/projects/{project_id}/workspace/backlog")
async def ws_backlog(project_id: str):
    """Return missions and tasks for the project backlog view."""
    from ...projects.manager import get_project_store
    from ...missions.manager import get_mission_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"missions": []})

    missions_out = []
    try:
        store = get_mission_store()
        all_missions = store.list(project_id=project_id)
        for m in all_missions[:20]:
            tasks = []
            try:
                task_list = getattr(m, "tasks", []) or []
                for t in task_list[:30]:
                    tasks.append(
                        {
                            "id": getattr(t, "id", ""),
                            "title": getattr(
                                t, "title", getattr(t, "description", "")[:60]
                            ),
                            "type": getattr(t, "type", ""),
                            "status": getattr(t, "status", ""),
                            "agent": getattr(t, "agent_id", ""),
                        }
                    )
            except Exception:
                pass
            missions_out.append(
                {
                    "id": m.id,
                    "title": getattr(m, "title", m.id),
                    "status": getattr(m, "status", ""),
                    "tasks": tasks,
                }
            )
    except Exception:
        pass

    return JSONResponse({"missions": missions_out})
