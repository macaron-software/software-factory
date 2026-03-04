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

    # ── Enrich epics_tree with stories progress ──────────────────────────────
    for ep_data in epics_tree:
        stories_done = sum(
            1
            for f in ep_data["features"]
            for s in f["stories"]
            if s["status"] in ("done", "completed")
        )
        stories_total = sum(len(f["stories"]) for f in ep_data["features"])
        ep_data["stories_done"] = stories_done
        ep_data["stories_total"] = stories_total
        ep_data["progress_pct"] = (
            int(stories_done / stories_total * 100) if stories_total else 0
        )
        ep_data["kanban_status"] = next(
            (e.kanban_status for e in proj_epics if e.id == ep_data["id"]), "funnel"
        )

    # ── Epic Kanban (grouped by kanban_status) ───────────────────────────────
    _kanban_cols = ["funnel", "analyzing", "backlog", "implementing", "done"]
    epics_kanban = {col: [] for col in _kanban_cols}
    for ep_data in epics_tree:
        col = ep_data.get("kanban_status", "funnel")
        epics_kanban.get(col, epics_kanban["funnel"]).append(ep_data)

    # ── Epic Runs (active + history) ─────────────────────────────────────────
    from ...epics.store import get_epic_run_store

    run_store = get_epic_run_store()
    all_runs_raw = run_store.list_runs(project_id=project_id, limit=50)
    epic_runs_active = []
    epic_runs_history = []
    for run in all_runs_raw:
        phases_data = []
        for ph in run.phases:
            ph_dict = ph.model_dump() if hasattr(ph, "model_dump") else dict(ph)
            phases_data.append(ph_dict)
        run_dict = {
            "id": run.id,
            "workflow_id": run.workflow_id,
            "workflow_name": run.workflow_name,
            "project_id": run.project_id,
            "status": run.status.value
            if hasattr(run.status, "value")
            else str(run.status),
            "current_phase": run.current_phase,
            "phases": phases_data,
            "created_at": run.created_at.isoformat() if run.created_at else "",
            "completed_at": run.completed_at.isoformat() if run.completed_at else "",
            "brief": (run.brief or "")[:120],
        }
        if run_dict["status"] in ("running", "pending"):
            epic_runs_active.append(run_dict)
        else:
            epic_runs_history.append(run_dict)

    # ── Sprint Stories (current sprint) ──────────────────────────────────────
    current_sprint = None
    sprint_stories_by_status = {
        "backlog": [],
        "in_progress": [],
        "review": [],
        "done": [],
        "blocked": [],
    }
    try:
        # Find active sprint across all epics of this project
        for ep in proj_epics:
            sprints = epic_store.list_sprints(ep.id)
            active_sp = next((s for s in sprints if s.status == "active"), None)
            if active_sp:
                current_sprint = {
                    "id": active_sp.id,
                    "name": active_sp.name,
                    "epic": ep.name,
                }
                for ep_d in epics_tree:
                    for f in ep_d["features"]:
                        for s in f["stories"]:
                            bucket = (
                                s["status"]
                                if s["status"] in sprint_stories_by_status
                                else "backlog"
                            )
                            sprint_stories_by_status[bucket].append(
                                {**s, "feature": f["name"], "epic": ep_d["name"]}
                            )
                break
    except Exception:
        pass

    # ── Docs (memory_project grouped by category) ────────────────────────────
    memory_docs: dict[str, list] = {}
    quality_scores: list = []
    try:
        from ...db import get_db as _get_db

        _db = _get_db()
        try:
            rows = _db.execute(
                "SELECT id, category, key, value, substr(value,1,300) as excerpt, agent_role, created_at "
                "FROM memory_project WHERE project_id=? ORDER BY category, created_at DESC",
                (project_id,),
            ).fetchall()
            for r in rows:
                cat = r["category"] or "general"
                if cat not in memory_docs:
                    memory_docs[cat] = []
                memory_docs[cat].append(
                    {
                        "id": r["id"],
                        "category": cat,
                        "key": r["key"],
                        "excerpt": r["excerpt"],
                        "value": r["value"] or "",
                        "agent_role": r["agent_role"] or "",
                        "created_at": r["created_at"] or "",
                    }
                )
            qrows = _db.execute(
                "SELECT dimension, AVG(score) as avg_score, COUNT(*) as cnt "
                "FROM quality_reports WHERE project_id=? GROUP BY dimension ORDER BY avg_score DESC",
                (project_id,),
            ).fetchall()
            for qr in qrows:
                quality_scores.append(
                    {
                        "dimension": qr["dimension"],
                        "avg_score": round(float(qr["avg_score"] or 0), 1),
                        "count": qr["cnt"],
                    }
                )
        finally:
            _db.close()
    except Exception as _e:
        logger.debug("[hub] memory/quality query failed: %s", _e)

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

    # Build agents for personas tab
    _av_dir = Path(__file__).parent.parent / "static" / "avatars"
    lead_agents_for_personas = []
    for agent_id in project.agents or []:
        a = agent_store.get(agent_id)
        if not a:
            continue
        av_url = ""
        for ext in ("jpg", "svg"):
            if (_av_dir / f"{a.id}.{ext}").exists():
                av_url = f"/static/avatars/{a.id}.{ext}"
                break
        lead_agents_for_personas.append(
            {
                "name": a.name,
                "role": getattr(a, "role", ""),
                "color": getattr(a, "color", "#333"),
                "avatar_url": av_url,
            }
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
            "epics_kanban": epics_kanban,
            "epic_runs_active": epic_runs_active,
            "epic_runs_history": epic_runs_history,
            "current_sprint": current_sprint,
            "sprint_stories_by_status": sprint_stories_by_status,
            "memory_docs": memory_docs,
            "quality_scores": quality_scores,
            "backlog_stories": all_stories_backlog,
            "health": health,
            "sessions": sessions[:10],
            "active_session": active_session,
            "messages": messages,
            "lead_agent": lead,
            "lead_avatar_url": lead_avatar_url,
            "lead_agents_for_personas": lead_agents_for_personas,
            "stats": {
                "total": len(proj_epics),
                "active": active_count,
                "completed": completed_count,
                "blocked": blocked_count,
                "features": sum(len(e["features"]) for e in epics_tree),
                "stories": len(all_stories_backlog),
                "story_points": sum(
                    s.get("story_points") or 0
                    for ep_d in epics_tree
                    for f in ep_d["features"]
                    for s in f["stories"]
                ),
            },
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    """Redirect to hub — the default project view."""
    from fastapi.responses import RedirectResponse as _Redir

    return _Redir(url=f"/projects/{project_id}/hub", status_code=302)


@router.post("/api/projects/{project_id}/chat/stream")
async def project_hub_chat_stream(request: Request, project_id: str):
    """Stream a conversation with the project lead agent in project hub context."""
    import json as _json
    import re as _re

    import markdown as _md
    from fastapi.responses import StreamingResponse

    from ...agents.executor import get_executor
    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store
    from ...sessions.runner import _build_context
    from ...sessions.store import MessageDef, get_session_store

    data = {}
    try:
        body = await request.body()
        data = _json.loads(body) if body else {}
    except Exception:
        pass

    message = str(data.get("message", "")).strip()
    if not message:
        return HTMLResponse("")

    ps = get_project_store()
    project = ps.get(project_id)
    if not project:
        return HTMLResponse("Project not found", status_code=404)

    # Use project lead agent, fallback to strat-cto
    agent_store = get_agent_store()
    agent_id = project.lead_agent_id or "strat-cto"
    agent = agent_store.get(agent_id) or agent_store.get("strat-cto")
    if not agent:
        agents = agent_store.list_all()
        agent = agents[0] if agents else None
    if not agent:
        return HTMLResponse("No agent available", status_code=500)

    # Get or create a project session for this chat
    sess_store = get_session_store()
    session_id = str(data.get("session_id", "")).strip()
    session = sess_store.get(session_id) if session_id else None

    if not session:
        # Find most recent active project session
        all_sessions = [s for s in sess_store.list_all() if s.project_id == project_id]
        active = [s for s in all_sessions if s.status == "active"]
        if active:
            session = sorted(active, key=lambda s: s.created_at or "", reverse=True)[0]

    if not session:
        # Create a new session for this project chat
        from ...sessions.store import SessionDef
        import uuid as _uuid

        session = sess_store.create(
            SessionDef(
                id=_uuid.uuid4().hex,
                name=f"Hub Chat — {project.name}",
                project_id=project_id,
                status="active",
                config={"type": "hub_chat", "project_id": project_id},
            )
        )

    # Store user message
    sess_store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="user",
            to_agent=agent.id,
            message_type="text",
            content=message,
        )
    )

    # Build rich project context for the agent
    epic_store = get_epic_store()
    proj_epics = epic_store.list_missions(project_id=project_id)
    active_count = sum(1 for e in proj_epics if e.status == "active")
    done_count = sum(1 for e in proj_epics if e.status == "completed")
    blocked_count = sum(1 for e in proj_epics if e.status == "blocked")

    extra_ctx = (
        f"Projet: {project.name} | Stack: {getattr(project, 'tech_stack', '') or ''}\n"
        f"Epics: {len(proj_epics)} total, {active_count} actifs, {done_count} terminés, {blocked_count} bloqués\n"
        f"Path: {getattr(project, 'path', '') or ''}\n"
    )
    if proj_epics:
        top = sorted(proj_epics, key=lambda e: e.wsjf_score or 0, reverse=True)[:3]
        extra_ctx += (
            "Top epics (WSJF): "
            + ", ".join(f"{e.name}({e.wsjf_score})" for e in top)
            + "\n"
        )

    # Add quality context if available
    try:
        from ...db.migrations import get_db as _get_db

        _db = _get_db()
        try:
            qrows = _db.execute(
                "SELECT dimension, AVG(score) as avg_score FROM quality_reports "
                "WHERE project_id=? GROUP BY dimension ORDER BY avg_score DESC LIMIT 5",
                (project_id,),
            ).fetchall()
            if qrows:
                extra_ctx += (
                    "Qualité: "
                    + ", ".join(
                        f"{r['dimension']}={round(float(r['avg_score'] or 0), 1)}"
                        for r in qrows
                    )
                    + "\n"
                )
        finally:
            _db.close()
    except Exception:
        pass

    def sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {_json.dumps(payload, ensure_ascii=False)}\n\n"

    async def event_generator():
        yield sse("status", {"label": "Analyse en cours…"})
        try:
            ctx = await _build_context(agent, session)
            ctx.project_context = extra_ctx + "\n\n" + (ctx.project_context or "")
            if getattr(project, "path", None):
                ctx.project_path = project.path
            ctx.tools_enabled = True
            ctx.allowed_tools = [
                "memory_search",
                "memory_store",
                "code_read",
                "code_search",
                "list_files",
                "git_log",
                "git_status",
                "platform_agents",
                "platform_missions",
                "platform_memory_search",
                "platform_metrics",
                "platform_sessions",
                "platform_workflows",
            ]

            executor = get_executor()
            raw = ""
            sent = 0
            llm_error = ""

            async for evt, payload in executor.run_streaming(ctx, message):
                if evt == "delta":
                    raw += payload
                    clean = _re.sub(r"<think>[\s\S]*?</think>\s*", "", raw).strip()
                    if (
                        "<think>" in clean
                        and "</think>" not in clean.split("<think>")[-1]
                    ):
                        clean = clean[: clean.rfind("<think>")]
                    if len(clean) > sent:
                        yield sse("chunk", {"text": clean[sent:]})
                        sent = len(clean)
                elif evt == "tool":
                    yield sse("tool", {"name": payload, "label": payload})
                elif evt == "result":
                    if hasattr(payload, "error") and payload.error:
                        llm_error = payload.error
                    elif hasattr(payload, "content") and payload.content and not raw:
                        raw = payload.content

            accumulated = _re.sub(r"<think>[\s\S]*?</think>\s*", "", raw).strip()

            if llm_error and not accumulated:
                yield sse("error", {"message": f"LLM indisponible: {llm_error[:150]}"})
                return

            if accumulated:
                sess_store.add_message(
                    MessageDef(
                        session_id=session.id,
                        from_agent=agent.id,
                        to_agent="user",
                        message_type="text",
                        content=accumulated,
                    )
                )

            rendered = (
                _md.markdown(accumulated, extensions=["fenced_code", "tables", "nl2br"])
                if accumulated
                else ""
            )
            yield sse("done", {"html": rendered})

        except Exception as exc:
            logger.exception("Project hub chat stream error")
            yield sse("error", {"message": str(exc)[:200]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Project Board (Kanban) ───────────────────────────────────────
