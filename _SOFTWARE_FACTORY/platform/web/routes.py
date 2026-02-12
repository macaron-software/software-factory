"""Web routes — HTMX-driven pages and API endpoints."""
from __future__ import annotations

import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


# ── Pages ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
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
    # Get agents
    agent_store = get_agent_store()
    agents = agent_store.list_all()
    lead = agent_store.get(project.lead_agent_id) if project.lead_agent_id else None
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
        "agents": agents,
        "lead_agent": lead,
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
    """Skill library — SF skills + role definitions."""
    from ..skills.library import get_skill_library
    library = get_skill_library()
    skills = library.scan_all()
    return _templates(request).TemplateResponse("skills.html", {
        "request": request,
        "page_title": "Skills",
        "skills": skills,
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
    agents = get_agent_store().list_all()
    patterns = []
    try:
        from ..db.migrations import get_db as _gdb
        conn = _gdb()
        patterns = [dict(r) for r in conn.execute("SELECT id, name FROM patterns").fetchall()]
        conn.close()
    except Exception:
        pass
    projects = []
    try:
        from ..projects.manager import get_project_store
        projects = get_project_store().list_all()
    except Exception:
        pass
    return _templates(request).TemplateResponse("new_session.html", {
        "request": request,
        "page_title": "New Session",
        "agents": agents,
        "patterns": patterns,
        "projects": projects,
    })


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_page(request: Request, session_id: str):
    """Active session conversation view."""
    from ..sessions.store import get_session_store
    from ..agents.store import get_agent_store
    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("<h2>Session not found</h2>", status_code=404)
    messages = store.get_messages(session_id)
    agents = get_agent_store().list_all()
    agent_map = {a.id: {"name": a.name, "icon": a.icon, "color": a.color, "role": a.role} for a in agents}
    return _templates(request).TemplateResponse("conversation.html", {
        "request": request,
        "page_title": session.name,
        "session": session,
        "messages": messages,
        "agents": agents,
        "agent_map": agent_map,
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
        config={"lead_agent": str(form.get("lead_agent", ""))} if form.get("lead_agent") else {},
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


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    from ..sessions.store import get_session_store
    get_session_store().delete(session_id)
    return HTMLResponse("")


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

    # For HTMX: return inline response with link to full conversation
    if agent_msg:
        agent_content = agent_msg.get("content", "") if isinstance(agent_msg, dict) else getattr(agent_msg, "content", str(agent_msg))
        return HTMLResponse(
            f'<div class="quick-chat-response">'
            f'<div class="msg-content" style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.5rem">{agent_content[:500]}</div>'
            f'<a href="/sessions/{session.id}" class="btn btn-sm">Open full conversation →</a>'
            f'</div>'
        )
    return HTMLResponse(f'<a href="/sessions/{session.id}" class="btn btn-sm">Open conversation →</a>')


# ── SSE Live Stream ─────────────────────────────────────────────

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
