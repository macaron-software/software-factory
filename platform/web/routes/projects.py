"""Web routes — Project management routes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
)

from .helpers import _templates

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
    """Projects list."""
    from ...projects.manager import get_project_store

    store = get_project_store()
    q = request.query_params.get("q", "").strip()
    factory_type = request.query_params.get("type", "").strip()
    has_workspace = request.query_params.get("ws", "").strip()
    all_projects = store.list_all()
    # Server-side filter
    projects_raw = [
        p
        for p in all_projects
        if (not q or q.lower() in p.name.lower() or q.lower() in p.id.lower())
        and (not factory_type or p.factory_type == factory_type)
    ]
    projects = [
        {"info": p, "git": None, "tasks": None, "has_workspace": p.exists}
        for p in projects_raw
    ]
    # Build domain groups (preserving insertion order: domains with projects come first)
    _domain_order: list[str] = []
    _domain_map: dict[str, list] = {}
    for proj in projects:
        dom = proj["info"].client_domain or ""
        if dom:
            if dom not in _domain_map:
                _domain_order.append(dom)
                _domain_map[dom] = []
            _domain_map[dom].append(proj)
    domain_groups = [{"domain": d, "projects": _domain_map[d]} for d in _domain_order]
    ungrouped = [p for p in projects if not p["info"].client_domain]

    return _templates(request).TemplateResponse(
        "projects.html",
        {
            "request": request,
            "page_title": "Projects",
            "projects": projects,
            "domain_groups": domain_groups,
            "ungrouped": ungrouped,
            "total_pages": 1,
            "page": 1,
            "q": q,
            "factory_type": factory_type,
            "has_workspace": has_workspace,
            "total": len(projects),
        },
    )


@router.get("/api/projects/{project_id}/git-status")
async def project_git_status(project_id: str):
    """Lazy-load git status for a single project (called via HTMX)."""
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
    from ...epics.store import get_epic_store
    from ...missions.product import get_product_backlog
    from ...agents.store import get_agent_store

    proj_store = get_project_store()
    project = proj_store.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    epic_store = get_epic_store()
    epics = epic_store.list_missions(project_id=project_id)

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


@router.get("/projects/{project_id}/hub", response_class=HTMLResponse)
async def project_hub(request: Request, project_id: str):
    """Project Hub — default project view: SAFe hierarchy + lifecycle + chat."""
    from ...projects.manager import get_project_store
    from ...epics.store import get_epic_store
    from ...missions.product import get_product_backlog
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store

    ps = get_project_store()
    project = ps.get(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    epic_store = get_epic_store()
    proj_epics = epic_store.list_missions(project_id=project_id)

    system_epics = sorted(
        [e for e in proj_epics if e.category == "system"],
        key=lambda e: e.wsjf_score,
        reverse=True,
    )
    functional_epics = sorted(
        [e for e in proj_epics if e.category != "system"],
        key=lambda e: e.wsjf_score,
        reverse=True,
    )

    # SAFe hierarchy: epics → features → stories
    backlog = get_product_backlog()
    epics_tree = []
    for ep in proj_epics:
        features = backlog.list_features(ep.id)
        features_data = []
        for f in features:
            stories = backlog.list_stories(f.id)
            features_data.append(
                {
                    "id": f.id,
                    "name": f.name,
                    "status": f.status,
                    "story_points": f.story_points,
                    "stories": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "status": s.status,
                            "story_points": s.story_points,
                        }
                        for s in stories
                    ],
                }
            )
        epics_tree.append(
            {
                "id": ep.id,
                "name": ep.name,
                "status": ep.status,
                "category": ep.category,
                "type": ep.type,
                "wsjf_score": ep.wsjf_score,
                "features": features_data,
            }
        )

    # Backlog: all stories not yet done
    all_stories_backlog = []
    for ep_data in epics_tree:
        for f in ep_data["features"]:
            for s in f["stories"]:
                if s["status"] not in ("done", "completed"):
                    all_stories_backlog.append(
                        {**s, "feature": f["name"], "epic": ep_data["name"]}
                    )

    # Sessions for chat
    sess_store = get_session_store()
    sessions = [s for s in sess_store.list_all() if s.project_id == project_id]
    sessions.sort(key=lambda s: s.created_at or "", reverse=True)
    requested_session = request.query_params.get("session")
    active_session = None
    if requested_session:
        active_session = sess_store.get(requested_session)
    if not active_session:
        active_sessions = [s for s in sessions if s.status == "active"]
        if active_sessions:
            active_session = active_sessions[0]
    messages = []
    if active_session:
        messages = sess_store.get_messages(active_session.id)
        messages = [m for m in messages if m.from_agent != "system"]

    # Lead agent
    agent_store = get_agent_store()
    lead = agent_store.get(project.lead_agent_id) if project.lead_agent_id else None
    lead_avatar_url = ""
    if lead:
        _av_dir = Path(__file__).parent.parent / "static" / "avatars"
        for ext in ("jpg", "svg"):
            if (_av_dir / f"{lead.id}.{ext}").exists():
                lead_avatar_url = f"/static/avatars/{lead.id}.{ext}"
                break

    phases = project.phases if hasattr(project, "phases") and project.phases else []

    active_count = sum(1 for e in proj_epics if e.status == "active")
    completed_count = sum(1 for e in proj_epics if e.status == "completed")
    blocked_count = sum(1 for e in proj_epics if e.status == "blocked")
    total = len(proj_epics) or 1
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
            "system_missions": system_epics,
            "functional_missions": functional_epics,
            "epics_tree": epics_tree,
            "backlog_stories": all_stories_backlog,
            "health": health,
            "sessions": sessions[:10],
            "active_session": active_session,
            "messages": messages,
            "lead_agent": lead,
            "lead_avatar_url": lead_avatar_url,
            "stats": {
                "total": len(proj_epics),
                "active": active_count,
                "completed": completed_count,
                "blocked": blocked_count,
                "features": sum(len(e["features"]) for e in epics_tree),
                "stories": len(all_stories_backlog),
            },
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    """Redirect to hub — the default project view."""
    from fastapi.responses import RedirectResponse as _Redir

    return _Redir(url=f"/projects/{project_id}/hub", status_code=302)


# ── Project Board (Kanban) ───────────────────────────────────────
