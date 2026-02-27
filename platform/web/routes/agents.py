"""Web routes — Agent, pattern, skill, MCP CRUD."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse

from .helpers import _templates, _avatar_url, _agent_map_for_template, _active_mission_tasks, serve_workspace_file
from ..schemas import AgentOut, AgentDetail, LlmProvider, OkResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Agents ───────────────────────────────────────────────────────

@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    """Agent builder — list all agents."""
    from ...agents.store import get_agent_store
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
    from ...agents.store import AgentDef
    from ...llm.providers import list_providers, get_all_models
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
    from ...agents.store import get_agent_store
    from ...llm.providers import list_providers, get_all_models
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
    from ...agents.store import get_agent_store, AgentDef
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
    from ...agents.store import get_agent_store
    get_agent_store().delete(agent_id)
    return HTMLResponse("")


@router.get("/api/agents/{agent_id}/details", responses={200: {"model": AgentDetail}})
async def agent_details_json(agent_id: str):
    """Full agent details as JSON for modals."""
    from ...agents.store import get_agent_store
    a = get_agent_store().get(agent_id)
    if not a:
        return JSONResponse({"error": "Not found"}, status_code=404)
    avatars_dir = Path(__file__).resolve().parent.parent / "static" / "avatars"
    avatar_url = f"/static/avatars/{a.id}.jpg" if (avatars_dir / f"{a.id}.jpg").exists() else ""
    return JSONResponse({
        "id": a.id, "name": a.name, "role": a.role, "description": a.description,
        "tagline": a.tagline or "", "persona": a.persona or "", "motivation": a.motivation or "",
        "avatar_url": avatar_url, "color": a.color or "#7c3aed", "icon": a.icon or "bot",
        "skills": a.skills or [], "tools": a.tools or [], "tags": a.tags or [],
        "permissions": a.permissions or {}, "hierarchy_rank": a.hierarchy_rank or 30,
        "provider": a.provider or "", "model": a.model or "",
    })


# ── Patterns ─────────────────────────────────────────────────────

@router.get("/patterns", response_class=HTMLResponse)
async def patterns_page(request: Request):
    """Pattern builder — list workflows."""
    from ...patterns.store import get_pattern_store
    patterns = get_pattern_store().list_all()
    return _templates(request).TemplateResponse("patterns.html", {
        "request": request,
        "page_title": "Patterns",
        "patterns": patterns,
    })


@router.get("/patterns/list", response_class=HTMLResponse)
async def patterns_list(request: Request):
    """Partial: patterns list (no tabs wrapper)."""
    from ...patterns.store import get_pattern_store
    patterns = get_pattern_store().list_all()
    return _templates(request).TemplateResponse("partials/patterns_list.html", {
        "request": request,
        "patterns": patterns,
    })


@router.get("/patterns/new", response_class=HTMLResponse)
async def pattern_new(request: Request):
    """Create new pattern form."""
    from ...patterns.store import PatternDef
    from ...agents.store import get_agent_store
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
    from ...patterns.store import get_pattern_store
    from ...agents.store import get_agent_store
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
    from ...patterns.store import get_pattern_store, PatternDef
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
    from ...patterns.store import get_pattern_store
    get_pattern_store().delete(pattern_id)
    return HTMLResponse("")


# ── Skills ───────────────────────────────────────────────────────

@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    """Skill library — local + GitHub skills with pagination & filtering."""
    from ...skills.library import get_skill_library
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
    from ...skills.library import get_skill_library
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
    from ...mcps.store import get_mcp_store
    from ...mcps.manager import get_mcp_manager
    store = get_mcp_store()
    manager = get_mcp_manager()
    mcps = store.list()
    # Enrich with live status
    for mcp in mcps:
        proc = manager._processes.get(mcp.id)
        if proc and proc.is_running:
            mcp.status = "running"
    return _templates(request).TemplateResponse("mcps.html", {
        "request": request,
        "page_title": "MCPs",
        "mcps": mcps,
    })


@router.post("/api/mcps/{mcp_id}/start")
async def api_mcp_start(mcp_id: str):
    """Start an MCP server."""
    from ...mcps.manager import get_mcp_manager
    manager = get_mcp_manager()
    ok, msg = await manager.start(mcp_id)
    return {"ok": ok, "message": msg}


@router.post("/api/mcps/{mcp_id}/stop")
async def api_mcp_stop(mcp_id: str):
    """Stop an MCP server."""
    from ...mcps.manager import get_mcp_manager
    manager = get_mcp_manager()
    ok, msg = await manager.stop(mcp_id)
    return {"ok": ok, "message": msg}


@router.post("/api/mcps/{mcp_id}/test")
async def api_mcp_test(mcp_id: str):
    """Test an MCP server — start, discover tools, test call."""
    from ...mcps.manager import get_mcp_manager
    manager = get_mcp_manager()
    result = await manager.test(mcp_id)
    return result


@router.post("/api/mcps/{mcp_id}/call")
async def api_mcp_call(mcp_id: str, request: Request):
    """Call a tool on a running MCP server."""
    from ...mcps.manager import get_mcp_manager
    body = await request.json()
    tool_name = body.get("tool", "")
    arguments = body.get("arguments", {})
    manager = get_mcp_manager()
    result = await manager.call_tool(mcp_id, tool_name, arguments)
    return {"result": result}


@router.get("/api/mcps/status")
async def api_mcps_status():
    """Get status of all MCP servers."""
    from ...mcps.manager import get_mcp_manager
    manager = get_mcp_manager()
    return {"mcps": manager.status()}


# ── Org Tree ─────────────────────────────────────────────────────

@router.get("/org", response_class=HTMLResponse)
async def org_page(request: Request):
    """SAFe Org Tree — Portfolio → ART → Team."""
    from ...agents.org import get_org_store
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
    from ...agents.org import get_org_store
    return JSONResponse(get_org_store().get_org_tree())


# ── API: Agents ──────────────────────────────────────────────────

@router.get("/api/agents", responses={200: {"model": list[AgentOut]}})
async def api_agents():
    """List all agents (JSON)."""
    from ...agents.store import get_agent_store
    from ...agents.tool_schemas import _get_capability_grade
    agents = get_agent_store().list_all()
    return JSONResponse([{
        "id": a.id, "name": a.name, "role": a.role,
        "provider": a.provider, "model": a.model,
        "description": a.description, "icon": a.icon,
        "color": a.color, "tags": a.tags, "is_builtin": a.is_builtin,
        "capability_grade": _get_capability_grade(a),
    } for a in agents])


@router.get("/api/llm/providers", responses={200: {"model": list[LlmProvider]}})
async def api_providers():
    """List LLM providers with availability (JSON)."""
    from ...llm.client import get_llm_client
    client = get_llm_client()
    providers = client.available_providers()
    return JSONResponse(providers)


@router.post("/api/skills/reload")
async def reload_skills():
    """Hot-reload skill definitions."""
    from ...skills.loader import get_skill_loader
    count = get_skill_loader().reload()
    return {"reloaded": count}


@router.post("/api/skills/github/add")
async def add_github_skill_source(request: Request):
    """Add a GitHub repo as skill source."""
    from ...skills.library import get_skill_library
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
    from ...skills.library import get_skill_library
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
    from ...skills.library import get_skill_library
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
    from ...generators.team import TeamGenerator

    form = await request.form()
    prompt = str(form.get("prompt", "")).strip()
    if not prompt:
        return HTMLResponse('<div class="msg-system-text">Prompt requis</div>', status_code=400)

    try:
        gen = TeamGenerator()
        result = await gen.generate(prompt)

        # Launch workflow in background
        from ...workflows.store import get_workflow_store, run_workflow
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


# ── 3D Agent World ────────────────────────────────────────────────

@router.get("/world", response_class=HTMLResponse)
async def agent_world_page(request: Request):
    """3D Sims-like agent visualization with live data."""
    import json as _json
    from ...agents.store import AgentStore
    from ...missions.store import MissionRunStore
    from ...sessions.store import SessionStore

    agent_store = AgentStore()
    mission_store = MissionRunStore()
    session_store = SessionStore()
    all_agents = agent_store.list_all()

    # Active missions
    all_runs = mission_store.list_runs(limit=50)
    _s = lambda v: v.value if hasattr(v, 'value') else str(v) if v else 'pending'
    active_missions = []
    active_session_ids = set()
    for mr in all_runs:
        st = _s(mr.status)
        if st in ('running', 'pending', 'paused'):
            phases_done = sum(1 for p in (mr.phases or []) if _s(p.status) in ('completed', 'done'))
            phases_total = len(mr.phases or [])
            active_missions.append({
                "id": mr.id, "name": mr.workflow_name or mr.workflow_id,
                "brief": (mr.brief or '')[:100], "status": st,
                "session_id": mr.session_id,
                "phases_done": phases_done, "phases_total": phases_total,
                "phases": [{"name": p.phase_name or f"Phase {i+1}", "status": _s(p.status)}
                           for i, p in enumerate(mr.phases or [])],
            })
            if mr.session_id:
                active_session_ids.add(mr.session_id)

    # Recent messages from active sessions (last 30 messages across all)
    recent_messages = []
    agent_sessions = {}  # agent_id → session_id mapping
    for sid in list(active_session_ids)[:10]:
        try:
            msgs = session_store.get_messages(sid, limit=20)
            for m in msgs:
                if m.from_agent and m.from_agent != 'user' and m.from_agent != 'system':
                    agent_sessions[m.from_agent] = sid
                    content = (m.content or '')[:120]
                    if content and m.message_type not in ('system',):
                        recent_messages.append({
                            "from": m.from_agent, "to": m.to_agent or '',
                            "content": content, "type": m.message_type or 'text',
                            "session_id": sid, "ts": m.timestamp or '',
                        })
        except Exception:
            pass
    # Sort by timestamp desc, keep last 50
    recent_messages.sort(key=lambda x: x['ts'], reverse=True)
    recent_messages = recent_messages[:50]

    agents_json = _json.dumps([
        {
            "id": a.id, "name": a.name, "role": a.role,
            "color": a.color, "avatar": a.avatar, "tagline": a.tagline,
            "hierarchy_rank": a.hierarchy_rank,
            "skills": a.skills[:8], "tools": a.tools[:6],
        }
        for a in all_agents
    ])
    live_json = _json.dumps({
        "missions": active_missions,
        "messages": recent_messages,
        "agent_sessions": agent_sessions,
    })
    return _templates(request).TemplateResponse("agent_world.html", {
        "request": request, "page_title": "World",
        "agents": all_agents, "agents_json": agents_json,
        "live_json": live_json,
    })

