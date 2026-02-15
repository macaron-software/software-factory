"""Web routes — HTMX-driven pages and API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _templates(request: Request):
    return request.app.state.templates


# ── Pages ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
@router.get("/projects", response_class=HTMLResponse)
async def index(request: Request):
    """Projects dashboard — main page."""
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
    })


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


# ── Memory ───────────────────────────────────────────────────────

@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    """Memory dashboard."""
    from ..memory.manager import get_memory_manager
    mem = get_memory_manager()
    stats = mem.stats()
    recent_global = mem.global_get(limit=20)
    return _templates(request).TemplateResponse("memory.html", {
        "request": request,
        "page_title": "Memory",
        "stats": stats,
        "recent_global": recent_global,
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

    # Build agent list with status
    agents = []
    for a in all_agents:
        loop = mgr.get_loop(a.id, session_id)
        agents.append({
            "id": a.id, "name": a.name, "role": a.role,
            "icon": a.icon, "color": a.color,
            "avatar": getattr(a, "avatar", "") or "🤖",
            "status": loop.status.value if loop else "idle",
            "description": a.description,
            "skills": getattr(a, "skills", []) or [],
            "tools": getattr(a, "tools", []) or [],
            "mcps": getattr(a, "mcps", []) or [],
            "model": getattr(a, "model", "") or "",
            "provider": getattr(a, "provider", "") or "",
            "tagline": getattr(a, "tagline", "") or "",
        })

    # Build graph from workflow config if available
    graph = {"nodes": [], "edges": []}
    wf_id = (session.config or {}).get("workflow_id", "")
    if wf_id:
        from ..workflows.store import get_workflow_store
        wf = get_workflow_store().get(wf_id)
        if wf and wf.config and wf.config.get("graph"):
            graph = wf.config["graph"]

    # Serialize messages for template
    msg_list = []
    for m in messages:
        a = agent_map.get(m.from_agent)
        msg_list.append({
            "id": m.id, "from_agent": m.from_agent, "to_agent": getattr(m, "to_agent", ""),
            "type": m.message_type, "content": m.content,
            "timestamp": m.timestamp if isinstance(m.timestamp, str) else m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            "from_name": a.name if a else m.from_agent,
            "from_color": a.color if a else "#6b7280",
            "from_avatar": getattr(a, "avatar", "🤖") if a else "💬",
        })

    # Load memory for this session
    memory_data = {"session": [], "project": [], "shared": []}
    try:
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        memory_data["session"] = mem.pattern_get(session_id, limit=20)
        if session.project_id:
            memory_data["project"] = mem.project_get(session.project_id, limit=20)
        memory_data["shared"] = mem.global_get(limit=10)
    except Exception:
        pass

    return _templates(request).TemplateResponse("session_live.html", {
        "request": request,
        "page_title": f"Live: {session.name}",
        "session": {"id": session.id, "name": session.name, "goal": session.goal,
                     "status": session.status, "pattern": getattr(session, "pattern_id", ""),
                     "project_id": session.project_id},
        "agents": agents,
        "messages": msg_list,
        "graph": graph,
        "memory": memory_data,
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
    agent_map = {a.id: {"name": a.name, "icon": a.icon, "color": a.color, "role": a.role} for a in agents}
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
    agent_map = {a.id: {"name": a.name, "icon": a.icon, "color": a.color, "role": a.role} for a in agents}

    # Render user bubble
    user_html = _templates(request).TemplateResponse("partials/message_bubble.html", {
        "request": request, "msg": user_msg, "agent_map": agent_map,
    }).body.decode()

    # Call agent (async LLM)
    agent_msg = await handle_user_message(session_id, content, to_agent or "")

    if agent_msg:
        agent_html = _templates(request).TemplateResponse("partials/message_bubble.html", {
            "request": request, "msg": agent_msg, "agent_map": agent_map,
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
    agent_map = {a.id: {"name": a.name, "icon": a.icon, "color": a.color, "role": a.role} for a in agents}
    html_parts = []
    for msg in messages:
        html_parts.append(_templates(request).TemplateResponse("partials/message_bubble.html", {
            "request": request,
            "msg": msg,
            "agent_map": agent_map,
        }).body.decode())
    return HTMLResponse("".join(html_parts))


@router.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active session."""
    from ..sessions.store import get_session_store, MessageDef
    store = get_session_store()
    store.update_status(session_id, "completed")
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        message_type="system",
        content="Session stopped by user.",
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
        content=f"🚀 Run pattern **{pattern.name}**: {task}",
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

    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        message_type="text",
        content=f"🔄 Run workflow **{wf.name}**: {task}",
    ))

    asyncio.create_task(_run_workflow_background(wf, session_id, task, session.project_id or ""))
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
            pills = "".join(f'<span class="chat-tool-pill">🔧 {html_mod.escape(str(tc.get("name", tc) if isinstance(tc, dict) else tc))}</span>' for tc in tool_calls)
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
                    "deep_search": "🔬 Deep search…",
                    "code_read": "📄 Reading files…",
                    "code_search": "🔍 Searching code…",
                    "git_log": "📋 Checking git…",
                    "git_diff": "📋 Checking diff…",
                    "memory_search": "Searching memory…",
                    "memory_store": "Storing to memory…",
                }
                label = labels.get(name, f"🔧 {name}…")
                await progress_queue.put(("tool", name, label))

            ctx.on_tool_call = on_tool_call

            # Run executor in background task
            result_holder = {}
            async def run_agent():
                executor = get_executor()
                result_holder["result"] = await executor.run(ctx, content)

            task = asyncio.create_task(run_agent())

            # Yield progress events while agent is working
            while not task.done():
                try:
                    kind, name, label = await asyncio.wait_for(
                        progress_queue.get(), timeout=0.5
                    )
                    event_type = "status" if kind == "status" else "tool"
                    yield sse(event_type, {"name": name, "label": label})
                except asyncio.TimeoutError:
                    pass

            # Drain any remaining events
            while not progress_queue.empty():
                kind, name, label = progress_queue.get_nowait()
                event_type = "status" if kind == "status" else "tool"
                yield sse(event_type, {"name": name, "label": label})

            # Wait for result
            await task
            result = result_holder.get("result")
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
            f'<div class="gh-sync-result error">⚠️ {repo}: {errs}</div>'
        )
    return HTMLResponse(
        f'<div class="gh-sync-result success">✅ {repo}: {result["fetched"]} skills fetched</div>'
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
            f'<div class="gh-sync-result">🔄 Synced {total} skills, {len(errors)} errors</div>'
        )
    return HTMLResponse(
        f'<div class="gh-sync-result success">✅ Synced {total} skills from {len(results)} repos</div>'
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
