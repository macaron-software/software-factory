"""Web routes — Project management routes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

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
    """Projects list (legacy)."""
    from ...projects.manager import get_project_store

    store = get_project_store()
    projects = store.list_all()
    return _templates(request).TemplateResponse(
        "projects.html",
        {
            "request": request,
            "page_title": "Projects",
            "projects": [{"info": p, "git": None, "tasks": None} for p in projects],
        },
    )


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


# ── Workspace: File Tree & File Content ─────────────────────────


@router.get("/api/projects/{project_id}/workspace/files")
async def ws_file_tree(project_id: str, request: Request, path: str = ""):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    base = Path(proj.path)
    rel = Path(path) if path else Path(".")
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    SKIP = {
        ".git",
        "node_modules",
        "__pycache__",
        ".env",
        "venv",
        ".venv",
        "dist",
        "build",
        ".next",
    }
    items = []
    try:
        for entry in sorted(
            target.iterdir(), key=lambda e: (e.is_file(), e.name.lower())
        ):
            if entry.name.startswith(".") and entry.name not in (".env",):
                if entry.name in (".git",):
                    continue
            if entry.name in SKIP:
                continue
            item = {
                "name": entry.name,
                "path": str(entry.relative_to(base)),
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            }
            items.append(item)
    except PermissionError:
        pass
    return JSONResponse({"items": items, "path": str(rel)})


@router.get("/api/projects/{project_id}/workspace/file-content")
async def ws_file_content(project_id: str, request: Request, path: str = ""):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    base = Path(proj.path)
    target = (base / path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    if not target.is_file():
        return JSONResponse({"error": "Not a file"}, status_code=404)
    if target.stat().st_size > 500_000:
        return JSONResponse(
            {"error": "File too large", "size": target.stat().st_size}, status_code=400
        )
    try:
        content = target.read_text(errors="replace")
        ext = target.suffix.lstrip(".")
        return JSONResponse({"content": content, "path": path, "ext": ext})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Workspace: GitHub Import ─────────────────────────────────────


@router.post("/api/projects/{project_id}/workspace/import-git")
async def ws_import_git(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    url = body.get("url", "").strip()
    import re

    if not re.match(
        r"^https://(github\.com|gitlab\.com)/[\w\-\.]+/[\w\-\.]+(?:\.git)?$", url
    ):
        return JSONResponse(
            {"error": "URL invalide. Format: https://github.com/user/repo"},
            status_code=400,
        )
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    import subprocess

    workspace_dir = Path(proj.path)
    repo_name = url.rstrip("/").rstrip(".git").split("/")[-1]
    target = workspace_dir / repo_name
    if target.exists():
        return JSONResponse(
            {"error": f"Le dossier '{repo_name}' existe déjà"}, status_code=400
        )

    async def _stream():
        yield f"data: {json.dumps({'type': 'log', 'msg': f'Clonage de {url}…'})}\n\n"
        proc = subprocess.Popen(
            ["git", "clone", "--depth=1", "--progress", url, str(target)],
            cwd=str(workspace_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            yield f"data: {json.dumps({'type': 'log', 'msg': line.rstrip()})}\n\n"
        proc.wait()
        if proc.returncode == 0:
            yield f"data: {json.dumps({'type': 'done', 'msg': f'✅ Cloné dans {repo_name}/', 'dir': repo_name})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'msg': '❌ Erreur lors du clone'})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── Workspace: AI Chat ────────────────────────────────────────


@router.post("/api/projects/{project_id}/workspace/chat")
async def ws_workspace_chat(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    message = body.get("message", "").strip()
    context = body.get("context", "")
    if not message:
        return JSONResponse({"error": "Message required"}, status_code=400)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)

    system = f"""Tu es un assistant de développement intégré au workspace du projet "{proj.name}".
Chemin du projet: {proj.path}
Tu aides avec le code, les erreurs, les questions techniques. Sois concis et précis."""
    if context:
        system += f"\n\nContexte fourni par l'utilisateur:\n{context[:2000]}"

    async def _stream_response():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        full_response = ""
        try:
            from ...llm.client import get_llm_client, LLMMessage

            llm = get_llm_client()
            async for chunk in llm.stream(
                messages=[LLMMessage(role="user", content=message)],
                system_prompt=system,
                max_tokens=1500,
            ):
                if chunk.delta:
                    full_response += chunk.delta
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.delta})}\n\n"
                if chunk.done:
                    break
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'full': full_response})}\n\n"

    return StreamingResponse(
        _stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Workspace: PR Viewer ──────────────────────────────────────


@router.get("/api/projects/{project_id}/workspace/prs")
async def ws_get_prs(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        import subprocess as _sp
        import re
        import urllib.request

        result = _sp.run(
            ["git", "remote", "get-url", "origin"],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        remote_url = result.stdout.strip()
        m = re.search(r"github\.com[:/]([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", remote_url)
        if not m:
            return JSONResponse(
                {"prs": [], "error": "Not a GitHub repo", "remote": remote_url}
            )
        owner, repo = m.group(1), m.group(2)
        gh_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page=10"
        )
        req = urllib.request.Request(
            gh_url,
            headers={
                "User-Agent": "SoftwareFactory/1.0",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            prs_data = json.loads(resp.read())
        prs = [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["user"]["login"],
                "branch": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "url": pr["html_url"],
                "created_at": pr["created_at"][:10],
                "draft": pr.get("draft", False),
            }
            for pr in prs_data
        ]
        return JSONResponse({"prs": prs, "repo": f"{owner}/{repo}"})
    except Exception as e:
        return JSONResponse({"prs": [], "error": str(e)})


# ── Workspace: Deploy Logs ────────────────────────────────────


@router.get("/api/projects/{project_id}/workspace/deploy-logs")
async def ws_deploy_logs(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)

    async def _stream_logs():
        import subprocess as _sp
        import select as sel
        import time as _time

        container_name = getattr(
            proj, "docker_container", None
        ) or proj.name.lower().replace(" ", "-")
        try:
            proc = _sp.Popen(
                ["docker", "logs", "--tail=100", "--follow", container_name],
                stdout=_sp.PIPE,
                stderr=_sp.STDOUT,
                text=True,
            )
            start = _time.time()
            while _time.time() - start < 60:
                ready = sel.select([proc.stdout], [], [], 1.0)[0]
                if ready:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    yield f"data: {json.dumps({'line': line.rstrip(), 'src': 'docker'})}\n\n"
                if await request.is_disconnected():
                    break
            proc.terminate()
        except FileNotFoundError:
            yield f"data: {json.dumps({'line': 'Docker non disponible', 'src': 'system'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'line': f'Erreur: {e}', 'src': 'error'})}\n\n"
        yield f"data: {json.dumps({'line': '[FIN DU STREAM]', 'src': 'system'})}\n\n"

    return StreamingResponse(
        _stream_logs(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Workspace: Page ──────────────────────────────────────────────


@router.get("/projects/{project_id}/workspace", response_class=HTMLResponse)
async def project_workspace_page(request: Request, project_id: str):
    """Full workspace IDE view for a project."""
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    from ...projects.manager import get_project_store
    from ...projects import git_service

    proj = get_project_store().get(project_id)
    if not proj:
        return HTMLResponse("<h1>Project not found</h1>", status_code=404)
    import asyncio

    loop = asyncio.get_event_loop()
    git = None
    try:
        git = await loop.run_in_executor(
            None, lambda: git_service.get_status(proj.path) if proj.has_git else None
        )
    except Exception:
        pass
    preview_url = _detect_preview_url(proj.path) if proj.path else ""
    return _templates(request).TemplateResponse(
        "project_workspace.html",
        {
            "request": request,
            "page_title": f"{proj.name} — Workspace",
            "project": proj,
            "proj": proj,
            "git": git,
            "preview_url": preview_url,
        },
    )


# ── Workspace: Live SSE stream ────────────────────────────────────


@router.get("/api/projects/{project_id}/workspace/live")
async def ws_live_stream(project_id: str, request: Request):
    """SSE stream for workspace live updates (cost, system stats)."""
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    async def _stream():
        iteration = 0
        while True:
            if await request.is_disconnected():
                break
            if iteration % 10 == 0 and _psutil is not None:
                try:
                    cpu = _psutil.cpu_percent(interval=0.1)
                    mem = _psutil.virtual_memory()
                    disk = _psutil.disk_usage("/")
                    yield f"data: {json.dumps({'type': 'system_stats', 'cpu': cpu, 'ram': mem.percent, 'ram_used_mb': round(mem.used / 1024 / 1024), 'ram_total_mb': round(mem.total / 1024 / 1024), 'disk': disk.percent})}\n\n"
                except Exception:
                    pass
            await asyncio.sleep(2)
            iteration += 1

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Workspace: Branch switcher ────────────────────────────────────


@router.get("/api/projects/{project_id}/workspace/branches")
async def ws_get_branches(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store
    import subprocess

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        result = subprocess.run(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        branches = [b.strip() for b in result.stdout.splitlines() if b.strip()]
        current = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        return JSONResponse({"branches": branches, "current": current})
    except Exception as e:
        return JSONResponse({"branches": [], "current": "main", "error": str(e)})


@router.post("/api/projects/{project_id}/workspace/checkout")
async def ws_checkout_branch(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    branch = body.get("branch", "")
    if not branch or ".." in branch:
        return JSONResponse({"error": "Invalid branch"}, status_code=400)
    from ...projects.manager import get_project_store
    import subprocess

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        result = subprocess.run(
            ["git", "checkout", branch],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return JSONResponse({"error": result.stderr[:500]}, status_code=400)
        return JSONResponse({"ok": True, "branch": branch})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Workspace: Git commit UI ──────────────────────────────────────


@router.get("/api/projects/{project_id}/workspace/git/status")
async def ws_git_status(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from ...projects.manager import get_project_store
    import subprocess

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = []
        for line in result.stdout.splitlines():
            if len(line) >= 3:
                status_code = line[:2].strip()
                filepath = line[3:]
                files.append({"status": status_code, "path": filepath})
        return JSONResponse({"files": files})
    except Exception as e:
        return JSONResponse({"files": [], "error": str(e)})


@router.post("/api/projects/{project_id}/workspace/git/commit")
async def ws_git_commit(project_id: str, request: Request):
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    message = body.get("message", "").strip()
    files = body.get("files", [])
    if not message:
        return JSONResponse({"error": "Commit message required"}, status_code=400)
    from ...projects.manager import get_project_store
    import subprocess

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "Not found"}, status_code=404)
    try:
        stage_files = files if files else ["."]
        subprocess.run(
            ["git", "add"] + stage_files, cwd=proj.path, capture_output=True, timeout=30
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=proj.path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return JSONResponse({"error": result.stderr[:500]}, status_code=400)
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=proj.path,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return JSONResponse({"ok": True, "sha": sha})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Preview URL detection + Proxy ─────────────────────────────────────────────


def _detect_preview_url(root_path: str) -> str:
    """Detect the app preview URL from project config files."""
    import re as _re
    from pathlib import Path as _Path

    p = _Path(root_path)
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        cf = p / name
        if cf.exists():
            try:
                m = _re.search(
                    r'["\']?(\d{4,5}):(\d{2,5})["\']?', cf.read_text(errors="ignore")
                )
                if m:
                    return f"http://localhost:{m.group(1)}"
            except Exception:
                pass
    env_file = p / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(errors="ignore").splitlines():
                m = _re.match(r"PORT\s*=\s*(\d+)", line.strip())
                if m:
                    return f"http://localhost:{m.group(1)}"
        except Exception:
            pass
    pkg = p / "package.json"
    if pkg.exists():
        try:
            import json as _json

            data = _json.loads(pkg.read_text())
            start = (data.get("scripts") or {}).get("start", "")
            m = _re.search(r"PORT=(\d+)|--port[= ](\d+)", start)
            if m:
                return f"http://localhost:{m.group(1) or m.group(2)}"
        except Exception:
            pass
    return ""


@router.api_route(
    "/projects/{project_id}/preview/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def ws_preview_proxy(request: Request, project_id: str, path: str):
    """Reverse-proxy the preview app so the workspace iframe works regardless of port access."""
    import httpx
    from fastapi.responses import Response as _Resp
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return _Resp(content=b"project not found", status_code=404)
    base_url = _detect_preview_url(proj.path or "")
    if not base_url:
        return _Resp(content=b"no preview URL detected", status_code=502)
    proxy_prefix = f"/projects/{project_id}/preview/"
    target = f"{base_url}/{path}"
    if request.url.query:
        target += f"?{request.url.query}"
    _skip = {
        "host",
        "connection",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "keep-alive",
        "proxy-authorization",
        "proxy-authenticate",
    }
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _skip}
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.request(
                method=request.method, url=target, headers=headers, content=body
            )
    except Exception as exc:
        return _Resp(content=f"proxy error: {exc}".encode(), status_code=502)
    content = resp.content
    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        try:
            html = content.decode("utf-8", errors="replace")
            base_tag = f'<base href="{proxy_prefix}">'
            if "<head>" in html:
                html = html.replace("<head>", f"<head>{base_tag}", 1)
            elif "<HEAD>" in html:
                html = html.replace("<HEAD>", f"<HEAD>{base_tag}", 1)
            else:
                html = base_tag + html
            content = html.encode("utf-8")
        except Exception:
            pass
    _skip_resp = {
        "transfer-encoding",
        "connection",
        "content-encoding",
        "content-length",
        "x-frame-options",
        "content-security-policy",
    }
    resp_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in _skip_resp
    }
    return _Resp(
        content=content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=content_type or None,
    )
