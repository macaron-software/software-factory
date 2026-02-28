"""Web routes — Project management routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import select
import pty
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
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


@router.post("/api/projects/{project_id}/phase")
async def project_set_phase(project_id: str, request: Request):
    """Set the current phase of a project (triggers mission status update).
    Accepts ?force=true to bypass gate check."""
    from ...projects.manager import get_project_store

    body = await _parse_body(request)
    phase_id = body.get("phase", "")
    force = str(body.get("force", "false")).lower() == "true"
    ps = get_project_store()
    try:
        proj = ps.set_phase(project_id, phase_id, force=force)
    except ValueError as e:
        return JSONResponse(
            {"ok": False, "error": str(e), "blocked": True}, status_code=409
        )
    if not proj:
        from fastapi import HTTPException

        raise HTTPException(404, "project not found")
    return {"ok": True, "project_id": project_id, "current_phase": phase_id}


@router.get("/api/projects/{project_id}/gate")
async def project_gate(project_id: str, target_phase: str = "mvp"):
    """Check if project can transition to target_phase."""
    from ...projects.manager import get_project_store

    ps = get_project_store()
    return ps.get_phase_gate(project_id, target_phase)


@router.get("/api/projects/{project_id}/health")
async def project_health(project_id: str):
    """Return project health score + missions by category."""
    from ...projects.manager import get_project_store
    from ...missions.store import get_mission_store

    proj = get_project_store().get(project_id)
    if not proj:
        from fastapi import HTTPException

        raise HTTPException(404, "project not found")

    ms = get_mission_store()
    all_m = ms.list_missions(limit=500)
    proj_m = [m for m in all_m if m.project_id == project_id]

    system_m = [m for m in proj_m if m.category == "system"]
    functional_m = [m for m in proj_m if m.category == "functional"]
    custom_m = [m for m in proj_m if m.category == "custom"]

    active_count = sum(1 for m in proj_m if m.status == "active")
    completed_count = sum(1 for m in proj_m if m.status == "completed")
    blocked_count = sum(1 for m in proj_m if m.status == "blocked")
    total = len(proj_m) or 1

    # Simple health score: penalize blocked, reward completed
    health = max(
        0,
        min(
            100,
            int(
                (active_count / total) * 40
                + (completed_count / total) * 50
                - (blocked_count / total) * 30
                + (20 if proj.exists else 0)
                + (10 if proj.has_git else 0)
            ),
        ),
    )

    def _m_dict(m):
        return {
            "id": m.id,
            "name": m.name,
            "type": m.type,
            "status": m.status,
            "wsjf_score": m.wsjf_score,
        }

    return {
        "project_id": project_id,
        "current_phase": proj.current_phase,
        "phases": proj.phases or proj.DEFAULT_PHASES,
        "health": health,
        "missions": {
            "system": [_m_dict(m) for m in system_m],
            "functional": [_m_dict(m) for m in functional_m],
            "custom": [_m_dict(m) for m in custom_m],
        },
        "stats": {
            "total": len(proj_m),
            "active": active_count,
            "completed": completed_count,
            "blocked": blocked_count,
            "has_workspace": proj.exists,
            "has_git": proj.has_git,
        },
    }


@router.get("/api/projects/{project_id}/phase")
async def project_get_phase(project_id: str):
    """Get current phase of a project."""
    from ...projects.manager import get_project_store

    ps = get_project_store()
    p = ps.get(project_id)
    if not p:
        from fastapi import HTTPException

        raise HTTPException(404, "project not found")
    return JSONResponse(
        {
            "project_id": project_id,
            "current_phase": p.current_phase or "discovery",
            "phases": p.phases or p.DEFAULT_PHASES,
        }
    )


@router.get("/api/projects/{project_id}/missions/suggest")
async def project_missions_suggest(project_id: str):
    """Suggest next missions based on current phase and existing missions."""
    from ...projects.manager import get_project_store
    from ...missions.store import get_mission_store

    ps = get_project_store()
    p = ps.get(project_id)
    if not p:
        from fastapi import HTTPException

        raise HTTPException(404, "project not found")
    phase = p.current_phase or "discovery"
    ms = get_mission_store()
    all_m = ms.list_missions(limit=500)
    existing = {m.name.lower() for m in all_m if m.project_id == project_id}
    SUGGESTIONS = {
        "discovery": [
            "Exploration marché",
            "Analyse concurrentielle",
            "Identification des besoins",
            "Proof of Concept",
        ],
        "mvp": [
            "Architecture technique",
            "Sprint MVP 1",
            "Tests utilisateurs",
            "CI/CD setup",
        ],
        "v1": [
            "Feature dev Sprint 1",
            "Optimisation performance",
            "Documentation",
            "Beta test",
        ],
        "run": [
            "Monitoring production",
            "Sprint amélioration",
            "Scalabilité",
            "Sécurité audit",
        ],
        "maintenance": ["Patch sécurité", "Dette technique", "Migration", "Archivage"],
    }
    candidates = SUGGESTIONS.get(phase, SUGGESTIONS["discovery"])
    suggestions = [s for s in candidates if s.lower() not in existing][:5]
    return JSONResponse(
        {
            "project_id": project_id,
            "current_phase": phase,
            "suggestions": suggestions,
        }
    )


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


@router.get("/projects/{project_id}/hub", response_class=HTMLResponse)
async def project_hub(request: Request, project_id: str):
    """Project Hub — unified lifecycle view with phases, missions by category, active agents."""
    from ...projects.manager import get_project_store
    from ...missions.store import get_mission_store
    from ...sessions.store import get_session_store

    ps = get_project_store()
    project = ps.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    ms = get_mission_store()
    all_m = ms.list_missions(limit=500)
    proj_m = [m for m in all_m if m.project_id == project_id]

    system_m = sorted(
        [m for m in proj_m if m.category == "system"],
        key=lambda m: m.wsjf_score,
        reverse=True,
    )
    functional_m = sorted(
        [m for m in proj_m if m.category != "system"],
        key=lambda m: m.wsjf_score,
        reverse=True,
    )

    # Active sessions/agents for this project
    sess_store = get_session_store()
    recent_sessions = (
        sess_store.list_sessions(project_id=project_id, limit=5)
        if hasattr(sess_store, "list_sessions")
        else []
    )

    phases = project.phases or project.DEFAULT_PHASES

    # Health score
    active_count = sum(1 for m in proj_m if m.status == "active")
    completed_count = sum(1 for m in proj_m if m.status == "completed")
    blocked_count = sum(1 for m in proj_m if m.status == "blocked")
    total = len(proj_m) or 1
    health = max(
        0,
        min(
            100,
            int(
                (active_count / total) * 40
                + (completed_count / total) * 50
                - (blocked_count / total) * 30
                + (20 if project.exists else 0)
                + (10 if project.has_git else 0)
            ),
        ),
    )

    return _templates(request).TemplateResponse(
        "project_hub.html",
        {
            "request": request,
            "page_title": f"{project.name} — Hub",
            "project": project,
            "phases": phases,
            "system_missions": system_m,
            "functional_missions": functional_m,
            "health": health,
            "recent_sessions": recent_sessions,
            "stats": {
                "total": len(proj_m),
                "active": active_count,
                "completed": completed_count,
                "blocked": blocked_count,
            },
        },
    )


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


_BLOCKED_CMDS = (
    "rm -rf /",
    "mkfs",
    "dd if=",
    "> /dev/",
    ":(){:|:&};:",
    "/etc/passwd",
    "/etc/shadow",
    "base64 -d",
    "curl.*|.*sh",
    "wget.*|.*sh",
)


@router.get("/api/projects/{project_id}/workspace/run")
async def ws_run_command(project_id: str, cmd: str, request: Request):
    """SSE endpoint — runs a shell command in project root and streams output."""
    import shlex
    from ...auth.middleware import get_current_user
    from ...projects.manager import get_project_store

    user = await get_current_user(request)
    if not user:

        async def _deny():
            yield "data: ERROR: Authentication required\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_deny(), media_type="text/event-stream")

    import re as _re

    for pattern in _BLOCKED_CMDS:
        if _re.search(pattern, cmd, _re.IGNORECASE):

            async def _blocked():
                yield "data: ERROR: Command blocked by security policy\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(_blocked(), media_type="text/event-stream")

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


@router.get("/api/projects/{project_id}/workspace/live")
async def ws_live_stream(project_id: str, since: str = "", request: Request = None):
    """SSE multi-channel live stream: tool_call, agent_status, file_write, git_commit, message, mission_phase."""
    import time as _time
    from ...db.migrations import get_db

    # Determine cursor timestamp
    cursor = since.strip() if since.strip() else None
    if not cursor:
        # Default: last 30s
        from datetime import timedelta

        cursor = (datetime.utcnow() - timedelta(seconds=30)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    async def event_stream():
        nonlocal cursor
        deadline = _time.monotonic() + 300  # 5 min max
        last_keepalive = _time.monotonic()
        _loop_n = 0

        while _time.monotonic() < deadline:
            # Check client disconnect
            if request and await request.is_disconnected():
                break

            try:
                db = get_db()
                batch = []

                # 1. New tool calls for this project
                try:
                    rows = db.execute(
                        """
                        SELECT tc.agent_id, tc.tool_name, tc.success, tc.parameters_json, tc.timestamp
                        FROM tool_calls tc
                        LEFT JOIN sessions s ON tc.session_id = s.id
                        WHERE s.project_id = ? AND tc.timestamp > ?
                        ORDER BY tc.timestamp ASC LIMIT 20
                        """,
                        (project_id, cursor),
                    ).fetchall()
                    for r in rows:
                        params = {}
                        try:
                            params = json.loads(r[3] or "{}")
                        except Exception:
                            pass
                        file_path = params.get("path", "")
                        preview = (
                            str(params.get("content", ""))[:60]
                            if params.get("content")
                            else ""
                        )
                        batch.append(
                            (
                                "tool_call",
                                {
                                    "agent_id": r[0] or "",
                                    "tool_name": r[1] or "",
                                    "success": bool(r[2]),
                                    "file": file_path,
                                    "preview": preview,
                                    "ts": str(r[4] or ""),
                                },
                            )
                        )
                        # File write secondary event
                        if (
                            r[1] in ("code_write", "code_edit", "code_create")
                            and file_path
                        ):
                            batch.append(
                                (
                                    "file_write",
                                    {
                                        "path": file_path,
                                        "agent_id": r[0] or "",
                                        "ts": str(r[4] or ""),
                                    },
                                )
                            )
                except Exception:
                    pass

                # 2. Agent/session status changes
                try:
                    sess_rows = db.execute(
                        """
                        SELECT id, agent_id, status, title, updated_at
                        FROM sessions
                        WHERE project_id = ? AND updated_at > ?
                        ORDER BY updated_at ASC LIMIT 10
                        """,
                        (project_id, cursor),
                    ).fetchall()
                    for r in sess_rows:
                        batch.append(
                            (
                                "agent_status",
                                {
                                    "session_id": r[0] or "",
                                    "agent_id": r[1] or "",
                                    "status": r[2] or "",
                                    "mission": r[3] or "",
                                    "ts": str(r[4] or ""),
                                },
                            )
                        )
                except Exception:
                    pass

                # 3. Recent agent messages
                try:
                    msg_rows = db.execute(
                        """
                        SELECT m.from_agent, m.session_id, m.content, m.created_at
                        FROM messages m
                        LEFT JOIN sessions s ON m.session_id = s.id
                        WHERE s.project_id = ? AND m.created_at > ?
                        AND m.role != 'tool'
                        ORDER BY m.created_at ASC LIMIT 10
                        """,
                        (project_id, cursor),
                    ).fetchall()
                    for r in msg_rows:
                        content = str(r[2] or "")
                        if content.startswith("[") or len(content) < 5:
                            continue
                        batch.append(
                            (
                                "message",
                                {
                                    "agent_id": r[0] or "",
                                    "session_id": r[1] or "",
                                    "preview": content[:120],
                                    "ts": str(r[3] or ""),
                                },
                            )
                        )
                except Exception:
                    pass

                # 4. Mission run phase changes (keep existing numbering)
                try:
                    run_rows = db.execute(
                        """
                        SELECT mr.id, mr.workflow_id, mr.status, mr.current_phase, mr.updated_at
                        FROM mission_runs mr
                        WHERE mr.project_id = ? AND mr.updated_at > ?
                        ORDER BY mr.updated_at ASC LIMIT 5
                        """,
                        (project_id, cursor),
                    ).fetchall()
                    for r in run_rows:
                        batch.append(
                            (
                                "mission_phase",
                                {
                                    "mission_id": r[0] or "",
                                    "workflow": r[1] or "",
                                    "status": r[2] or "",
                                    "phase": r[3] or "",
                                    "ts": str(r[4] or ""),
                                },
                            )
                        )
                except Exception:
                    pass

                # 5. Cost update every 10 iterations (~20s)
                if _loop_n % 10 == 0:
                    try:
                        from datetime import timedelta as _td

                        cost_since = (datetime.utcnow() - _td(hours=1)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        crow = db.execute(
                            """
                            SELECT SUM(lu.tokens_in), SUM(lu.tokens_out), SUM(lu.cost_usd)
                            FROM llm_usage lu
                            JOIN mission_runs mr ON lu.mission_run_id = mr.id
                            WHERE mr.project_id = ? AND lu.created_at > ?
                            """,
                            (project_id, cost_since),
                        ).fetchone()
                        ti = int(crow[0] or 0)
                        to_ = int(crow[1] or 0)
                        cost = float(crow[2] or 0.0)
                        yield (
                            f"event: cost_update\ndata: {json.dumps({'type': 'cost_update', 'tokens_in': ti, 'tokens_out': to_, 'cost_usd': cost, 'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})}\n\n"
                        )
                    except Exception:
                        pass

                # Advance cursor to latest ts seen
                if batch:
                    latest = max(
                        (e[1].get("ts", "") for e in batch),
                        default=cursor,
                    )
                    if latest and latest > cursor:
                        cursor = latest

                    # Emit events (max 20)
                    for ev_type, ev_data in batch[:20]:
                        yield f"event: {ev_type}\ndata: {json.dumps(ev_data)}\n\n"

            except Exception:
                pass

            # Keepalive every 25s
            now = _time.monotonic()
            if now - last_keepalive >= 25:
                yield ": ping\n\n"
                last_keepalive = now

            await asyncio.sleep(2)
            _loop_n += 1

        yield "event: close\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/projects/{project_id}/workspace/metrics")
async def ws_metrics(project_id: str):
    """Workspace metrics: active agents, tool calls/h, files written, commits today."""
    from ...db.migrations import get_db
    from ...projects.manager import get_project_store
    from ...projects import git_service

    db = get_db()
    proj = get_project_store().get(project_id)
    metrics: dict = {
        "active_agents": 0,
        "tool_calls_last_hour": 0,
        "tool_calls_per_min": 0.0,
        "files_written": 0,
        "commits_today": 0,
        "last_commit_hash": "",
        "last_commit_msg": "",
        "mission_runs_active": 0,
    }
    try:
        # Active sessions
        r = db.execute(
            "SELECT COUNT(*) FROM sessions WHERE project_id=? AND status IN ('active','running')",
            (project_id,),
        ).fetchone()
        metrics["active_agents"] = r[0] if r else 0

        # Tool calls last hour
        r = db.execute(
            """
            SELECT COUNT(*) FROM tool_calls tc
            LEFT JOIN sessions s ON tc.session_id = s.id
            WHERE s.project_id = ? AND tc.timestamp > datetime('now','-1 hour')
            """,
            (project_id,),
        ).fetchone()
        hourly = r[0] if r else 0
        metrics["tool_calls_last_hour"] = hourly
        metrics["tool_calls_per_min"] = round(hourly / 60.0, 1)

        # Files written today
        r = db.execute(
            """
            SELECT COUNT(*) FROM tool_calls tc
            LEFT JOIN sessions s ON tc.session_id = s.id
            WHERE s.project_id = ? AND tc.tool_name IN ('code_write','code_edit','code_create')
            AND tc.timestamp > datetime('now','-24 hours')
            """,
            (project_id,),
        ).fetchone()
        metrics["files_written"] = r[0] if r else 0

        # Active mission runs
        r = db.execute(
            "SELECT COUNT(*) FROM mission_runs WHERE project_id=? AND status IN ('running','active')",
            (project_id,),
        ).fetchone()
        metrics["mission_runs_active"] = r[0] if r else 0
    except Exception:
        pass

    # Git: commits today + last commit
    if proj and proj.has_git:
        try:
            commits = git_service.get_log(proj.path, 10)
            if commits:
                c0 = (
                    commits[0].__dict__
                    if hasattr(commits[0], "__dict__")
                    else dict(commits[0])
                )
                metrics["last_commit_hash"] = str(c0.get("hash") or "")[:8]
                metrics["last_commit_msg"] = str(
                    c0.get("message") or c0.get("subject") or ""
                )[:60]
            # Count today
            import subprocess as _sp

            result = _sp.run(
                ["git", "log", "--oneline", "--since=midnight"],
                cwd=proj.path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            metrics["commits_today"] = sum(
                1 for line in result.stdout.splitlines() if line.strip()
            )
        except Exception:
            pass

    return JSONResponse(metrics)


@router.get("/api/projects/{project_id}/workspace/progress")
async def ws_progress(project_id: str):
    """Read PROGRESS.md from project workspace."""
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"exists": False, "content": "", "mtime": ""})

    progress_path = Path(proj.path) / "PROGRESS.md"
    if not progress_path.exists():
        return JSONResponse({"exists": False, "content": "", "mtime": ""})

    try:
        content = progress_path.read_text(errors="replace")
        mtime = datetime.fromtimestamp(progress_path.stat().st_mtime).isoformat()
        return JSONResponse({"exists": True, "content": content[:8000], "mtime": mtime})
    except Exception as e:
        return JSONResponse(
            {"exists": False, "content": "", "mtime": "", "error": str(e)}
        )


@router.get("/api/projects/{project_id}/workspace/messages")
async def ws_messages(project_id: str, limit: int = 30):
    """Return recent agent messages for this project's live feed."""
    from ...db.migrations import get_db

    db = get_db()
    items = []
    try:
        rows = db.execute(
            """
            SELECT m.from_agent, m.session_id, m.content, m.role, m.created_at
            FROM messages m
            LEFT JOIN sessions s ON m.session_id = s.id
            WHERE s.project_id = ? AND m.role NOT IN ('tool','system')
            ORDER BY m.created_at DESC LIMIT ?
            """,
            (project_id, min(limit, 50)),
        ).fetchall()
        for r in rows:
            content = str(r[2] or "")
            if len(content) < 3:
                continue
            items.append(
                {
                    "agent_id": r[0] or "",
                    "session_id": r[1] or "",
                    "preview": content[:200],
                    "role": r[3] or "assistant",
                    "ts": str(r[4] or ""),
                }
            )
    except Exception:
        pass
    return JSONResponse({"items": items})


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
                if entry.name in SKIP:
                    continue
                # Skip hidden dirs (like .git, .next) but show hidden files (like .env)
                if entry.is_dir() and entry.name.startswith("."):
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


@router.post("/api/projects/{project_id}/workspace/file/save")
async def ws_save_file(project_id: str, request: Request):
    """Save file content (write to disk)."""
    from ...projects.manager import get_project_store
    from ...web.routes.helpers import _parse_body

    body = await _parse_body(request)
    path = body.get("path", "")
    content = body.get("content", "")
    if not path:
        return JSONResponse({"error": "path required"})
    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"error": "project not found"}, status_code=404)
    root = Path(proj.path)
    target = (root / path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return JSONResponse({"error": "access denied"})
    if not target.is_file():
        return JSONResponse({"error": "not a file"})
    try:
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return JSONResponse({"error": str(e)})
    return JSONResponse({"ok": True})


@router.get("/api/projects/{project_id}/workspace/diff")
async def ws_diff(project_id: str, ref: str = "HEAD~1", request: Request = None):
    """Return git diff as structured data for inline display."""
    import subprocess
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"error": "project not found"}, status_code=404)

    try:
        result = subprocess.run(
            ["git", "diff", ref],
            cwd=str(proj.path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        raw = result.stdout
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "git diff timed out"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    files = []
    current_file = None
    current_hunk = None
    for line in raw.splitlines():
        if line.startswith("+++ "):
            path = line[4:].lstrip("b/")
            if current_file is not None:
                files.append(current_file)
            current_file = {"path": path, "additions": 0, "deletions": 0, "hunks": []}
            current_hunk = None
        elif line.startswith("--- "):
            pass
        elif line.startswith("@@ "):
            if current_file is None:
                current_file = {"path": "", "additions": 0, "deletions": 0, "hunks": []}
            header = line.split("@@")[1].strip() if "@@" in line[2:] else line
            header = "@@ " + line[3:].split("@@")[0].strip() + " @@"
            current_hunk = {"header": header, "lines": []}
            current_file["hunks"].append(current_hunk)
        elif current_hunk is not None:
            if line.startswith("+"):
                current_hunk["lines"].append({"type": "add", "content": line[1:]})
                current_file["additions"] += 1
            elif line.startswith("-"):
                current_hunk["lines"].append({"type": "del", "content": line[1:]})
                current_file["deletions"] += 1
            else:
                current_hunk["lines"].append(
                    {"type": "context", "content": line[1:] if line else ""}
                )
    if current_file is not None:
        files.append(current_file)

    return JSONResponse({"ref": ref, "files": files})


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
    from ...missions.store import get_mission_store

    proj = get_project_store().get(project_id)
    if not proj:
        return JSONResponse({"missions": []})

    missions_out = []
    try:
        store = get_mission_store()
        all_missions = store.list_missions(project_id=project_id)
        for m in all_missions[:20]:
            tasks = []
            try:
                task_list = store.list_tasks(mission_id=m.id)
                for t in task_list[:30]:
                    tasks.append(
                        {
                            "id": getattr(t, "id", ""),
                            "title": getattr(
                                t,
                                "name",
                                getattr(t, "description", getattr(t, "title", "")),
                            )[:60],
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
                    "title": getattr(m, "name", None)
                    or getattr(m, "title", None)
                    or getattr(m, "description", m.id)[:60],
                    "type": getattr(m, "type", ""),
                    "status": getattr(m, "status", ""),
                    "goal": getattr(m, "goal", ""),
                    "tasks": tasks,
                }
            )
    except Exception:
        pass

    return JSONResponse({"missions": missions_out})


@router.get("/api/projects/{project_id}/workspace/secrets")
async def ws_get_secrets(project_id: str):
    """List .env files and their KEY=VALUE pairs."""
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"files": []})

    root = Path(proj.path)
    env_names = [
        ".env",
        ".env.local",
        ".env.development",
        ".env.production",
        ".env.test",
        ".env.example",
        ".env.staging",
    ]
    files = []
    for fname in env_names:
        fpath = root / fname
        if not fpath.is_file():
            continue
        vars_list = []
        try:
            content = fpath.read_text(errors="replace")
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, _, val = stripped.partition("=")
                    vars_list.append({"key": key.strip(), "value": val.strip()})
        except Exception:
            pass
        files.append({"name": fname, "path": fname, "vars": vars_list})

    return JSONResponse({"files": files})


@router.post("/api/projects/{project_id}/workspace/secrets/save")
async def ws_save_secrets(project_id: str, request: Request):
    """Save .env file with updated KEY=VALUE pairs."""
    from ...projects.manager import get_project_store
    from ...web.routes.helpers import _parse_body

    body = await _parse_body(request)
    path = body.get("path", ".env")
    vars_list = body.get("vars", [])

    if not path or not str(path).startswith(".env"):
        return JSONResponse({"error": "only .env* files allowed"})

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"error": "project not found"}, status_code=404)

    root = Path(proj.path).resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return JSONResponse({"error": "access denied"})

    lines = []
    for v in vars_list:
        key = str(v.get("key", "")).strip()
        val = str(v.get("value", "")).strip()
        if key:
            # Quote value if it contains spaces and isn't already quoted
            if " " in val and not (val.startswith('"') or val.startswith("'")):
                val = f'"{val}"'
            lines.append(f"{key}={val}")

    try:
        target.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    except Exception as e:
        return JSONResponse({"error": str(e)})

    return JSONResponse({"ok": True})


@router.post("/api/projects/{project_id}/workspace/dbgate/configure")
async def ws_dbgate_configure(project_id: str):
    """Auto-configure DbGate connections from project .env files."""
    import httpx
    import os
    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path:
        return JSONResponse({"error": "project not found"}, status_code=404)

    root = Path(proj.path)
    env_names = [".env", ".env.local", ".env.development", ".env.production"]
    all_vars: dict = {}
    for fname in env_names:
        fpath = root / fname
        if not fpath.is_file():
            continue
        try:
            for line in fpath.read_text(errors="replace").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, v = stripped.partition("=")
                    all_vars[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    # Collect connections to create
    conns = []
    _id_counter = 0

    def _next_id():
        nonlocal _id_counter
        _id_counter += 1
        return f"{project_id[:12]}_conn{_id_counter}"

    # SQLite files
    for root2, dirs, fnames in os.walk(proj.path):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", "venv", ".git")
        ]
        for fname in fnames:
            if fname.endswith((".db", ".sqlite", ".sqlite3")):
                fpath2 = os.path.join(root2, fname)
                conns.append(
                    {
                        "_id": _next_id(),
                        "engine": "sqlite@dbgate-plugin-sqlite",
                        "databaseFile": fpath2,
                        "label": f"SQLite: {fname}",
                    }
                )

    # Postgres from env
    pg_url = (
        all_vars.get("DATABASE_URL")
        or all_vars.get("POSTGRES_URL")
        or all_vars.get("PG_URL")
        or all_vars.get("DB_URL")
    )
    if pg_url and (pg_url.startswith("postgres")):
        conns.append(
            {
                "_id": _next_id(),
                "engine": "postgres@dbgate-plugin-postgres",
                "url": pg_url,
                "label": "PostgreSQL",
            }
        )
    elif all_vars.get("POSTGRES_HOST") or all_vars.get("PG_HOST"):
        host = all_vars.get("POSTGRES_HOST") or all_vars.get("PG_HOST")
        conns.append(
            {
                "_id": _next_id(),
                "engine": "postgres@dbgate-plugin-postgres",
                "server": host,
                "port": all_vars.get("POSTGRES_PORT", "5432"),
                "user": all_vars.get("POSTGRES_USER") or all_vars.get("PG_USER", ""),
                "password": all_vars.get("POSTGRES_PASSWORD")
                or all_vars.get("PG_PASSWORD", ""),
                "database": all_vars.get("POSTGRES_DB")
                or all_vars.get("PG_DATABASE", ""),
                "label": "PostgreSQL",
            }
        )

    # MySQL from env
    mysql_url = all_vars.get("MYSQL_URL") or all_vars.get("DATABASE_URL")
    if mysql_url and mysql_url.startswith("mysql"):
        conns.append(
            {
                "_id": _next_id(),
                "engine": "mysql@dbgate-plugin-mysql",
                "url": mysql_url,
                "label": "MySQL",
            }
        )

    if not conns:
        return JSONResponse({"configured": 0, "message": "No databases detected"})

    # Login to DbGate and create connections
    import os

    dbgate_url = os.environ.get("DBGATE_URL", "http://dbgate:3000")
    dbgate_password = os.environ.get("DBGATE_PASSWORD", "dbgate2024")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            login = await client.post(
                f"{dbgate_url}/auth/login",
                json={"login": "admin", "password": dbgate_password},
            )
            if login.status_code != 200:
                return JSONResponse({"configured": 0, "error": "DbGate auth failed"})
            token = login.json().get("accessToken")
            headers = {"Authorization": f"Bearer {token}"}
            saved = 0
            for conn in conns:
                r = await client.post(
                    f"{dbgate_url}/connections/save", json=conn, headers=headers
                )
                if r.status_code == 200:
                    saved += 1
        return JSONResponse({"configured": saved, "total": len(conns)})
    except Exception as e:
        return JSONResponse({"configured": 0, "error": str(e)})


@router.get("/api/dbgate/token")
async def dbgate_get_token():
    """Return a fresh DbGate access token for iframe auto-login."""
    import httpx
    import os

    dbgate_url = os.environ.get("DBGATE_URL", "http://dbgate:3000")
    dbgate_password = os.environ.get("DBGATE_PASSWORD", "dbgate2024")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{dbgate_url}/auth/login",
                json={"login": "admin", "password": dbgate_password},
            )
            if r.status_code == 200:
                token = r.json().get("accessToken", "")
                return JSONResponse({"token": token})
    except Exception:
        pass
    return JSONResponse({"token": ""})


@router.get("/api/projects/{project_id}/workspace/timeline")
async def ws_timeline(project_id: str, filter: str = "all"):
    """Return unified timeline events: git commits + missions + deployments."""
    try:
        from ...projects.manager import get_project_store
        from ...projects import git_service

        proj = get_project_store().get(project_id)
        if not proj:
            return JSONResponse({"events": []})
    except Exception as exc:
        logger.warning("ws_timeline init error: %s", exc)
        return JSONResponse({"events": [], "error": str(exc)})

    events: list[dict] = []

    # Git commits
    if filter in ("all", "commit") and proj.has_git:
        try:
            commits = git_service.get_log(proj.path, 30)
            for c in commits:
                cd = c.__dict__ if hasattr(c, "__dict__") else dict(c)
                events.append(
                    {
                        "type": "commit",
                        "title": cd.get("message") or cd.get("subject") or "commit",
                        "description": cd.get("hash", "")[:8],
                        "author": cd.get("author") or cd.get("author_name", ""),
                        "ts": cd.get("date") or cd.get("timestamp") or "",
                    }
                )
        except Exception:
            pass

    # Missions
    if filter in ("all", "mission"):
        try:
            from ...missions.store import MissionStore

            missions = MissionStore().list_missions(project_id=project_id, limit=30)
            for m in missions:
                md = m.__dict__ if hasattr(m, "__dict__") else dict(m)
                events.append(
                    {
                        "type": "mission",
                        "title": md.get("title") or md.get("name") or "Mission",
                        "description": md.get("status", ""),
                        "author": md.get("created_by", ""),
                        "ts": md.get("updated_at") or md.get("created_at") or "",
                    }
                )
        except Exception:
            pass

    # Deployments from git log (commits with "deploy" in message)
    if filter in ("all", "deploy") and proj.has_git:
        try:
            all_commits = git_service.get_log(proj.path, 50)
            for c in all_commits:
                cd = c.__dict__ if hasattr(c, "__dict__") else dict(c)
                msg = (cd.get("message") or "").lower()
                if any(kw in msg for kw in ("deploy", "release", "publish", "prod")):
                    events.append(
                        {
                            "type": "deploy",
                            "title": cd.get("message") or "deploy",
                            "description": cd.get("hash", "")[:8],
                            "author": cd.get("author") or cd.get("author_name", ""),
                            "ts": cd.get("date") or cd.get("timestamp") or "",
                        }
                    )
        except Exception:
            pass

    # Sort by timestamp descending
    def sort_key(e: dict) -> str:
        return str(e.get("ts") or "")

    events.sort(key=sort_key, reverse=True)
    return JSONResponse({"events": events[:60]})


@router.get("/api/projects/{project_id}/workspace/search")
async def ws_search(
    project_id: str,
    q: str = "",
    glob: str = "",
    case: bool = False,
    regex: bool = False,
):
    """Full-text search across project files using ripgrep or grep fallback."""
    import subprocess

    from ...projects.manager import get_project_store

    proj = get_project_store().get(project_id)
    if not proj or not proj.path or not q:
        return JSONResponse({"matches": [], "total_matches": 0})

    MAX_FILES = 50
    MAX_LINES_PER_FILE = 30

    # Build ripgrep command
    cmd = ["rg", "--line-number", "--no-heading", "--color=never", "--max-count=30"]
    if not case:
        cmd.append("--ignore-case")
    if not regex:
        cmd.append("--fixed-strings")
    if glob:
        cmd += ["--glob", glob]
    cmd += ["--", q, "."]

    # Fallback to grep if rg not available
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, cwd=proj.path
        )
        output = result.stdout
    except FileNotFoundError:
        cmd2 = ["grep", "-rn", "--include=" + (glob or "*"), "-m", "30"]
        if not case:
            cmd2.append("-i")
        if not regex:
            cmd2.append("-F")
        cmd2 += ["--", q, "."]
        try:
            result = subprocess.run(
                cmd2, capture_output=True, text=True, timeout=15, cwd=proj.path
            )
            output = result.stdout
        except Exception:
            output = ""
    except Exception:
        output = ""

    # Parse output: "filepath:linenum:text"
    files_dict: dict[str, list[dict]] = {}
    total = 0
    for line in output.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        fpath, lnum, text = parts[0].lstrip("./"), parts[1], parts[2]
        if fpath not in files_dict:
            if len(files_dict) >= MAX_FILES:
                continue
            files_dict[fpath] = []
        if len(files_dict[fpath]) < MAX_LINES_PER_FILE:
            files_dict[fpath].append(
                {"line": int(lnum) if lnum.isdigit() else 0, "text": text[:200]}
            )
            total += 1

    matches = [{"file": f, "lines": lines} for f, lines in files_dict.items()]
    return JSONResponse({"matches": matches, "total_matches": total})


@router.get("/api/docker/stats")
async def docker_global_stats():
    """Return global Docker stats: total and running containers."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        lines = [s.strip() for s in result.stdout.strip().splitlines() if s.strip()]
        total = len(lines)
        running = sum(1 for s in lines if s.startswith("Up"))
        return JSONResponse({"total": total, "running": running})
    except Exception:
        pass
    return JSONResponse({"total": 0, "running": 0})


@router.get("/api/projects/{project_id}/export")
async def project_export(project_id: str):
    """Export a project as a ZIP archive (config + memories, no workspace files)."""
    import io
    import zipfile

    from ...projects.store import get_project_store
    from ...missions.store import get_mission_run_store, get_mission_store
    from ...db.migrations import get_db

    project = get_project_store().get(project_id)
    if not project:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Project config
        proj_dict = (
            project.model_dump() if hasattr(project, "model_dump") else vars(project)
        )
        zf.writestr("project.json", json.dumps(proj_dict, default=str, indent=2))

        # Missions list
        missions = get_mission_store().list_missions(project_id=project_id)
        zf.writestr(
            "missions.json",
            json.dumps(
                [
                    m.model_dump() if hasattr(m, "model_dump") else vars(m)
                    for m in missions
                ],
                default=str,
                indent=2,
            ),
        )

        # Mission runs
        runs = get_mission_run_store().list_runs(project_id=project_id, limit=50)
        zf.writestr(
            "mission_runs.json",
            json.dumps(
                [r.model_dump() if hasattr(r, "model_dump") else vars(r) for r in runs],
                default=str,
                indent=2,
            ),
        )

        # Memories (project scope)
        try:
            db = get_db()
            rows = db.execute(
                "SELECT key, value, scope, updated_at FROM memory_entries WHERE scope LIKE ?",
                (f"project:{project_id}%",),
            ).fetchall()
            db.close()
            zf.writestr(
                "memories.json",
                json.dumps([dict(r) for r in rows], default=str, indent=2),
            )
        except Exception:
            pass

    buf.seek(0)
    filename = f"project-{project_id}-export.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/projects/import")
async def project_import(request: Request):
    """Import a project from a ZIP archive (previously exported)."""
    import io
    import zipfile

    from ...projects.store import get_project_store

    form = await request.form()
    upload = form.get("file")
    if not upload:
        return JSONResponse({"error": "No file uploaded"}, status_code=400)

    data = await upload.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        if "project.json" not in names:
            return JSONResponse(
                {"error": "Invalid export: missing project.json"}, status_code=400
            )

        proj_data = json.loads(zf.read("project.json"))
    except Exception as e:
        return JSONResponse({"error": f"Invalid ZIP: {e}"}, status_code=400)

    # Check for duplicates
    store = get_project_store()
    existing = store.get(proj_data.get("id", ""))
    if existing:
        # Generate new ID
        import uuid

        proj_data["id"] = uuid.uuid4().hex[:8]
        proj_data["name"] = proj_data.get("name", "Imported") + " (import)"

    try:
        from ...projects.store import ProjectDef

        project = ProjectDef(
            **{k: v for k, v in proj_data.items() if k in ProjectDef.model_fields}
        )
        store.create(project)
        return JSONResponse(
            {"ok": True, "project_id": project.id, "name": project.name}
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/projects/{project_id}/wallet")
async def project_wallet(project_id: str):
    """Return wallet balance and last 10 transactions for a project."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        row = db.execute(
            "SELECT balance, total_earned, total_spent FROM project_wallets WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if not row:
            return JSONResponse(
                {
                    "balance": 100.0,
                    "total_earned": 100.0,
                    "total_spent": 0.0,
                    "transactions": [],
                }
            )
        txns = db.execute(
            "SELECT id, amount, reason, reference_id, created_at FROM token_transactions"
            " WHERE project_id=? ORDER BY created_at DESC LIMIT 10",
            (project_id,),
        ).fetchall()
        return JSONResponse(
            {
                "balance": round(row["balance"], 6),
                "total_earned": round(row["total_earned"], 6),
                "total_spent": round(row["total_spent"], 6),
                "transactions": [dict(t) for t in txns],
            }
        )
    finally:
        db.close()


# ── Package Manager ──────────────────────────────────────────────────────────

_PKG_MANAGERS = {
    "package.json": {
        "type": "npm",
        "list_cmd": ["npm", "list", "--depth=0", "--json"],
        "install_cmd": ["npm", "install"],
        "install_pkg_cmd": ["npm", "install"],
    },
    "requirements.txt": {
        "type": "pip",
        "list_cmd": ["pip", "list", "--format=json"],
        "install_cmd": ["pip", "install", "-r", "requirements.txt"],
        "install_pkg_cmd": ["pip", "install"],
    },
    "pyproject.toml": {
        "type": "pip",
        "list_cmd": ["pip", "list", "--format=json"],
        "install_cmd": ["pip", "install", "-e", "."],
        "install_pkg_cmd": ["pip", "install"],
    },
    "Cargo.toml": {
        "type": "cargo",
        "list_cmd": ["cargo", "tree", "--depth=1"],
        "install_cmd": ["cargo", "build"],
        "install_pkg_cmd": ["cargo", "add"],
    },
    "pom.xml": {
        "type": "maven",
        "list_cmd": ["mvn", "dependency:list", "-q"],
        "install_cmd": ["mvn", "install", "-q"],
        "install_pkg_cmd": None,
    },
    "build.gradle": {
        "type": "gradle",
        "list_cmd": [
            "gradle",
            "dependencies",
            "--configuration=runtimeClasspath",
            "-q",
        ],
        "install_cmd": ["gradle", "build", "-q"],
        "install_pkg_cmd": None,
    },
}


def _detect_pkg_manager(project_path: str) -> tuple[str, dict] | tuple[None, None]:
    """Return (manifest_file, manager_info) or (None, None)."""
    p = Path(project_path)
    for manifest, info in _PKG_MANAGERS.items():
        if (p / manifest).exists():
            return manifest, info
    return None, None


async def _run_cmd_safe(cmd: list[str], cwd: str, timeout: int = 30) -> str:
    """Run a command and return stdout+stderr as string. Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return out.decode(errors="replace")
    except asyncio.TimeoutError:
        return f"[timeout after {timeout}s]"
    except FileNotFoundError:
        return f"[command not found: {cmd[0]}]"
    except Exception as exc:
        return f"[error: {exc}]"


def _parse_npm_list(raw: str) -> list[dict]:
    """Parse npm list --json output into [{name, version, dev}]."""
    try:
        data = json.loads(raw)
        deps = data.get("dependencies", {})
        result = []
        for name, info in deps.items():
            result.append(
                {
                    "name": name,
                    "version": info.get("version", "?"),
                    "dev": False,
                }
            )
        return sorted(result, key=lambda x: x["name"])
    except Exception:
        return []


def _parse_pip_list(raw: str) -> list[dict]:
    """Parse pip list --format=json output."""
    try:
        pkgs = json.loads(raw)
        return [
            {"name": p["name"], "version": p["version"], "dev": False} for p in pkgs
        ]
    except Exception:
        return []


def _parse_generic_list(raw: str, pkg_type: str) -> list[dict]:
    """Parse cargo tree / maven / gradle output as raw lines."""
    lines = [
        ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("[")
    ]
    return [
        {"name": ln[:80], "version": "", "dev": False, "raw": True} for ln in lines[:50]
    ]


@router.get("/api/projects/{project_id}/workspace/packages")
async def ws_packages(project_id: str, request: Request):
    """List installed packages for the project."""
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    from ..projects.registry import get_project_registry

    proj = get_project_registry().get(project_id)
    if not proj or not proj.path or not Path(proj.path).is_dir():
        return JSONResponse({"manifest": None, "type": None, "packages": []})

    manifest, info = _detect_pkg_manager(proj.path)
    if not manifest:
        return JSONResponse({"manifest": None, "type": None, "packages": []})

    raw = await _run_cmd_safe(info["list_cmd"], proj.path, timeout=20)
    pkg_type = info["type"]

    if pkg_type == "npm":
        packages = _parse_npm_list(raw)
    elif pkg_type == "pip":
        packages = _parse_pip_list(raw)
    else:
        packages = _parse_generic_list(raw, pkg_type)

    # Also read manifest for declared deps
    manifest_content = ""
    try:
        manifest_content = (Path(proj.path) / manifest).read_text(errors="replace")[
            :3000
        ]
    except Exception:
        pass

    return JSONResponse(
        {
            "manifest": manifest,
            "type": pkg_type,
            "packages": packages,
            "manifest_preview": manifest_content[:500],
            "count": len(packages),
        }
    )


@router.post("/api/projects/{project_id}/workspace/packages/install")
async def ws_packages_install(project_id: str, request: Request):
    """Install a package or run the full install command. Returns SSE stream."""
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    if not user:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    body = await _parse_body(request)
    package_name = (body.get("package") or "").strip()

    from ..projects.registry import get_project_registry

    proj = get_project_registry().get(project_id)
    if not proj or not proj.path or not Path(proj.path).is_dir():
        return JSONResponse({"ok": False, "error": "Project path not found"})

    manifest, info = _detect_pkg_manager(proj.path)
    if not manifest:
        return JSONResponse({"ok": False, "error": "No package manager detected"})

    if package_name and info["install_pkg_cmd"]:
        cmd = info["install_pkg_cmd"] + [package_name]
    else:
        cmd = info["install_cmd"]

    async def _stream():
        yield f"data: $ {' '.join(cmd)}\n\n"
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=proj.path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                text = line.decode(errors="replace").rstrip()
                yield f"data: {text}\n\n"
            await asyncio.wait_for(proc.wait(), timeout=120)
            code = proc.returncode
            yield f"data: [exit {code}]\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.TimeoutError:
            yield "data: [timeout after 120s]\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: [error: {exc}]\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── PTY WebSocket Terminal ─────────────────────────────────────────────────────


@router.websocket("/api/projects/{project_id}/workspace/terminal")
async def ws_terminal(websocket: WebSocket, project_id: str):
    """True PTY terminal over WebSocket. Client sends bytes; server streams PTY output."""
    await websocket.accept()

    from ..projects.registry import get_project_registry

    proj = get_project_registry().get(project_id)
    cwd = proj.path if proj and proj.path and Path(proj.path).is_dir() else "/tmp"

    master_fd, slave_fd = pty.openpty()

    proc = await asyncio.create_subprocess_exec(
        "bash",
        "--login",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=cwd,
        env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "220", "LINES": "50"},
        close_fds=True,
    )
    os.close(slave_fd)

    loop = asyncio.get_event_loop()
    alive = True

    async def _read_pty():
        nonlocal alive
        try:
            while alive and proc.returncode is None:
                ready, _, _ = await loop.run_in_executor(
                    None, lambda: select.select([master_fd], [], [], 0.05)
                )
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if data:
                        await websocket.send_bytes(data)
        except Exception:
            pass
        finally:
            alive = False

    async def _read_ws():
        nonlocal alive
        try:
            while alive:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                raw = msg.get("bytes") or (msg.get("text") or "").encode()
                if not raw:
                    continue
                # Handle resize JSON: {"type":"resize","cols":N,"rows":N}
                try:
                    jmsg = json.loads(raw)
                    if jmsg.get("type") == "resize":
                        import struct
                        import fcntl
                        import termios

                        cols, rows = (
                            int(jmsg.get("cols", 80)),
                            int(jmsg.get("rows", 24)),
                        )
                        winsize = struct.pack("HHHH", rows, cols, 0, 0)
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                        continue
                except Exception:
                    pass
                os.write(master_fd, raw)
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            alive = False

    try:
        await asyncio.gather(_read_pty(), _read_ws())
    finally:
        alive = False
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
