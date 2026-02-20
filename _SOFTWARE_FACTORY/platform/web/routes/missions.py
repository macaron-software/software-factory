"""Web routes — Mission lifecycle and execution."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse

from .helpers import _templates, _avatar_url, _agent_map_for_template, _active_mission_tasks, serve_workspace_file

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Missions ─────────────────────────────────────────────────────

@router.get("/missions", response_class=HTMLResponse)
async def missions_page(request: Request):
    """List all missions with filters."""
    from ...missions.store import get_mission_store
    from ...projects.manager import get_project_store

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

    from ...workflows.store import get_workflow_store
    all_workflows = get_workflow_store().list_all()

    return _templates(request).TemplateResponse("missions.html", {
        "request": request, "page_title": "PI Board",
        "missions": mission_cards,
        "project_ids": project_ids,
        "filter_status": filter_status,
        "filter_project": filter_project,
        "show_new_form": show_new,
        "workflows": all_workflows,
    })


@router.get("/missions/{mission_id}", response_class=HTMLResponse)
async def mission_detail_page(request: Request, mission_id: str):
    """Mission cockpit — sprints, board, team."""
    from ...missions.store import get_mission_store
    from ...projects.manager import get_project_store
    from ...agents.store import get_agent_store

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
    from ...missions.store import get_mission_store, MissionDef
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
    from ...missions.store import get_mission_store
    get_mission_store().update_mission_status(mission_id, "active")
    return JSONResponse({"ok": True})


@router.post("/api/missions/{mission_id}/sprints")
async def create_sprint(mission_id: str):
    """Add a sprint to a mission."""
    from ...missions.store import get_mission_store, SprintDef
    store = get_mission_store()
    existing = store.list_sprints(mission_id)
    num = len(existing) + 1
    s = SprintDef(mission_id=mission_id, number=num, name=f"Sprint {num}")
    store.create_sprint(s)
    return JSONResponse({"ok": True})


@router.post("/api/missions/{mission_id}/tasks")
async def create_task(request: Request, mission_id: str):
    """Create a task in a mission sprint (inline kanban creation)."""
    from ...missions.store import get_mission_store, TaskDef
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
    from ...missions.store import get_mission_store
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...workflows.store import get_workflow_store

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
    from .workflows import _run_workflow_background
    import asyncio
    task_desc = mission.goal or mission.description or mission.name
    asyncio.create_task(_run_workflow_background(wf, session.id, task_desc, mission.project_id or ""))

    return JSONResponse({"session_id": session.id, "workflow_id": wf_id})


@router.post("/api/missions/{mission_id}/wsjf")
async def compute_wsjf(mission_id: str, request: Request):
    """Compute and store WSJF score from components."""
    from ...missions.store import get_mission_store
    from ...db.migrations import get_db as _gdb
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
    from ...missions.store import get_mission_store
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


# ══════════════════════════════════════════════════════════════════════════════
#  MISSION CONTROL — CDP orchestrator dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/mission-control", response_class=HTMLResponse)
async def missions_list_page(request: Request):
    """List all mission runs."""
    from ...missions.store import get_mission_run_store
    from ...projects.manager import get_project_store
    from ...workflows.store import get_workflow_store
    store = get_mission_run_store()
    runs = store.list_runs(limit=50)
    projects = get_project_store().list_all()
    workflows = get_workflow_store().list_all()
    return _templates(request).TemplateResponse("mission_control_list.html", {
        "request": request, "page_title": "Epic Control",
        "runs": runs,
        "projects": projects,
        "workflows": workflows,
    })


@router.get("/api/missions/list-partial", response_class=HTMLResponse)
async def missions_list_partial(request: Request):
    """HTMX partial: refreshes mission list every 15s."""
    from ...missions.store import get_mission_run_store
    runs = get_mission_run_store().list_runs(limit=50)
    # Detect stuck missions: status=running but no active asyncio task
    active_ids = {mid for mid, t in _active_mission_tasks.items() if not t.done()}
    return _templates(request).TemplateResponse("partials/mission_list.html", {
        "request": request, "runs": runs, "active_ids": active_ids,
    })


@router.delete("/api/mission-runs/{run_id}")
async def delete_mission_run(run_id: str):
    """Delete a mission run and its associated session/messages."""
    from ...missions.store import get_mission_run_store
    from ...db.migrations import get_db
    store = get_mission_run_store()
    run = store.get(run_id)
    if not run:
        return JSONResponse({"error": "Not found"}, status_code=404)
    conn = get_db()
    if run.session_id:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (run.session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (run.session_id,))
    conn.execute("DELETE FROM mission_runs WHERE id = ?", (run_id,))
    conn.execute("DELETE FROM confluence_pages WHERE mission_id = ?", (run_id,))
    conn.commit()
    return JSONResponse({"status": "deleted"})


@router.get("/missions/start/{workflow_id}", response_class=HTMLResponse)
async def mission_start_page(request: Request, workflow_id: str):
    """Start a new mission — show brief form."""
    from ...workflows.store import get_workflow_store
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
    from ...missions.store import get_mission_run_store
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...agents.loop import get_loop_manager
    from ...agents.store import get_agent_store
    from ...models import PhaseRun, PhaseStatus, MissionRun, MissionStatus
    import uuid
    from datetime import datetime

    form = await request.form()
    workflow_id = str(form.get("workflow_id", ""))
    brief = str(form.get("brief", "")).strip()
    # Fix double-encoded UTF-8 (curl sends UTF-8 bytes interpreted as latin-1)
    try:
        brief = brief.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
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
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent / "data" / "workspaces" / mission_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    # Init git repo + README with brief
    subprocess.run(["git", "init"], cwd=str(workspace_root), capture_output=True)
    readme = workspace_root / "README.md"
    readme.write_text(f"# {wf.name}\n\n{brief}\n\nMission ID: {mission_id}\n")
    subprocess.run(["git", "add", "."], cwd=str(workspace_root), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit — mission workspace"], cwd=str(workspace_root), capture_output=True)
    workspace_path = str(workspace_root)

    # Determine orchestrator agent (workflow config or default CDP)
    orchestrator_id = (wf.config or {}).get("orchestrator", "chef_de_programme")

    mission = MissionRun(
        id=mission_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief,
        status=MissionStatus.RUNNING,
        phases=phases,
        project_id=project_id or mission_id,
        workspace_path=workspace_path,
        cdp_agent_id=orchestrator_id,
    )

    run_store = get_mission_run_store()
    run_store.create(mission)

    # Create a session for the orchestrator agent
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
        to_agent=orchestrator_id,
        message_type="instruction",
        content=brief,
    ))

    # Start the orchestrator agent loop with workspace path
    mgr = get_loop_manager()
    try:
        await mgr.start_agent(orchestrator_id, session_id, mission.project_id, workspace_path)
    except Exception as e:
        logger.error("Failed to start CDP agent: %s", e)

    return JSONResponse({"mission_id": mission_id, "session_id": session_id,
                         "redirect": f"/missions/{mission_id}/control"})


@router.post("/api/missions/{mission_id}/chat/stream")
async def mission_chat_stream(request: Request, mission_id: str):
    """Stream a conversation with the CDP agent in mission context."""
    from ...missions.store import get_mission_run_store
    from ...sessions.store import get_session_store, MessageDef
    from ...agents.store import get_agent_store
    from ...agents.executor import get_executor, ExecutionContext
    from ...sessions.runner import _build_context
    from ...memory.manager import get_memory_manager

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
    agent_id = str(form.get("agent_id", "")).strip() or "chef_de_programme"
    agent = agent_store.get(agent_id)
    if not agent:
        agent = agent_store.get("chef_de_programme")
    if not agent:
        agents = agent_store.list_all()
        agent = agents[0] if agents else None
    if not agent:
        return HTMLResponse("No agent", status_code=500)

    # Store user message
    sess_store.add_message(MessageDef(
        session_id=session_id, from_agent="user",
        to_agent=agent_id, message_type="text", content=content,
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

    # Role-specific tool instructions per agent type
    _role_instructions = {
        "lead_dev": "\n\nTu es le Lead Dev. Tu peux LIRE et MODIFIER le code du projet. Utilise code_read pour examiner les fichiers, code_write/code_edit pour les modifier, et git_commit pour committer tes changements. Quand l'utilisateur te demande de modifier quelque chose, fais-le directement avec les outils.",
        "dev_backend": "\n\nTu es développeur backend. Tu peux LIRE et MODIFIER le code. Utilise code_read, code_write, code_edit, git_commit.",
        "dev_frontend": "\n\nTu es développeur frontend. Tu peux LIRE et MODIFIER le code. Utilise code_read, code_write, code_edit, git_commit.",
        "architecte": "\n\nTu es l'Architecte Solution. Tu peux LIRE et MODIFIER l'architecture du projet. Utilise code_read pour examiner les fichiers, code_write/code_edit pour modifier Architecture.md ou d'autres docs d'architecture, et git_commit pour committer. Quand l'utilisateur te demande de mettre à jour l'architecture, fais-le directement.",
        "qa_lead": "\n\nTu es le QA Lead. Tu peux LIRE et MODIFIER les tests du projet. Utilise code_read pour examiner les tests, code_write/code_edit pour créer ou modifier des fichiers de test, et git_commit pour committer.",
        "test_manager": "\n\nTu es le Test Manager. Tu peux LIRE et MODIFIER les tests. Utilise code_read, code_write, code_edit, git_commit.",
        "test_automation": "\n\nTu es l'ingénieur test automation. Tu peux LIRE et ÉCRIRE des tests automatisés. Utilise code_read, code_write, code_edit, git_commit.",
        "tech_writer": "\n\nTu es le Technical Writer. Tu peux LIRE et MODIFIER la documentation du projet (README.md, docs/, wiki). Utilise code_read pour examiner les docs, code_write/code_edit pour les mettre à jour, memory_store pour sauvegarder des connaissances, et git_commit pour committer.",
        "product_owner": "\n\nTu es le Product Owner. Tu peux consulter le code, les features et la mémoire projet. Utilise memory_store pour sauvegarder des décisions produit.",
        "product_manager": "\n\nTu es le Product Manager. Tu peux consulter le backlog, les features et la mémoire. Utilise memory_store pour les décisions.",
        "chef_de_programme": """

Tu es le Chef de Programme (CDP). Tu ORCHESTRE activement le projet.

RÈGLE FONDAMENTALE: Quand l'utilisateur te demande d'agir (lancer, relancer, fixer, itérer), tu DOIS utiliser tes outils. Ne te contente JAMAIS de décrire ce que tu ferais — FAIS-LE.

Tes outils d'orchestration:
- run_phase(phase_id, brief): Lance une phase du pipeline (idéation, dev-sprint, qa-campaign, etc.)
- get_phase_status(phase_id): Vérifie le statut d'une phase
- list_phases(): Liste toutes les phases et leur statut
- request_validation(phase_id, decision): Demande GO/NOGO

Tes outils d'investigation:
- code_read(path): Lire un fichier du projet
- code_search(query, path): Chercher dans le code
- git_log(cwd): Voir l'historique git
- git_diff(cwd): Voir les changements
- memory_search(query): Chercher dans la mémoire projet
- platform_missions(): État des missions
- platform_agents(): Liste des agents

WORKFLOW: Quand on te dit "go" ou "lance":
1. D'abord list_phases() pour voir l'état
2. Identifie la prochaine phase à lancer
3. Appelle run_phase(phase_id="...", brief="...") pour la lancer
4. Rapporte le résultat

N'écris JAMAIS [TOOL_CALL] en texte — utilise le vrai mécanisme de function calling.""",
    }
    role_instruction = _role_instructions.get(agent_id, "\n\nTu peux LIRE et MODIFIER les fichiers du projet avec code_read, code_write, code_edit, git_commit, et sauvegarder des connaissances avec memory_store.")
    mission_context += role_instruction

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
            ctx.tools_enabled = True
            # Base tools for all agents
            _platform_tools = [
                "platform_agents", "platform_missions", "platform_memory_search",
                "platform_metrics", "platform_sessions", "platform_workflows",
            ]
            base_tools = [
                "memory_search", "memory_store",
                "code_read", "code_search", "list_files",
                "git_log", "git_status", "git_diff",
                "get_project_context",
            ] + _platform_tools
            # CDP gets orchestration tools
            if agent_id in ("chef_de_programme", "chef_projet"):
                ctx.allowed_tools = base_tools + [
                    "get_phase_status", "list_phases",
                    "run_phase", "request_validation",
                ]
            else:
                # Dev/Archi/QA/Wiki agents get write tools
                ctx.allowed_tools = base_tools + [
                    "code_write", "code_edit",
                    "git_commit",
                ]

            executor = get_executor()
            raw_accumulated = ""
            llm_error = ""
            _sent_count = 0

            async for evt, data_s in executor.run_streaming(ctx, content):
                if evt == "delta":
                    raw_accumulated += data_s
                    # Strip all <think>...</think> blocks from accumulated so far
                    import re as _re
                    clean = _re.sub(r'<think>[\s\S]*?</think>\s*', '', raw_accumulated)
                    # If still inside an unclosed <think>, don't send yet
                    if '<think>' in clean and '</think>' not in clean.split('<think>')[-1]:
                        clean = clean[:clean.rfind('<think>')]
                    clean = clean.strip()
                    # Send only newly revealed characters
                    if len(clean) > _sent_count:
                        new_text = clean[_sent_count:]
                        _sent_count = len(clean)
                        yield sse("chunk", {"text": new_text})
                elif evt == "tool":
                    # Tool being called — show in UI
                    tool_labels = {
                        "memory_search": "Recherche mémoire",
                        "memory_store": "Sauvegarde mémoire",
                        "get_phase_status": "Statut des phases",
                        "list_phases": "Liste des phases",
                        "run_phase": "Lancement de phase",
                        "request_validation": "Demande de validation",
                        "code_read": "Lecture de code",
                        "code_write": "Écriture de code",
                        "code_edit": "Modification de code",
                        "code_search": "Recherche dans le code",
                        "list_files": "Liste des fichiers",
                        "git_log": "Historique Git",
                        "git_status": "Statut Git",
                        "git_diff": "Diff Git",
                        "git_commit": "Commit Git",
                        "get_project_context": "Contexte projet",
                        "platform_agents": "Agents plateforme",
                        "platform_missions": "Missions/Epics",
                        "platform_memory_search": "Mémoire plateforme",
                        "platform_metrics": "Métriques",
                        "platform_sessions": "Cérémonies",
                        "platform_workflows": "Templates workflow",
                    }
                    label = tool_labels.get(data_s, f"🔧 {data_s}")
                    yield sse("tool", {"name": data_s, "label": label})
                elif evt == "result":
                    if hasattr(data_s, "error") and data_s.error:
                        llm_error = data_s.error
                    elif hasattr(data_s, "content") and data_s.content and not raw_accumulated:
                        raw_accumulated = data_s.content

            import re as _re
            accumulated = _re.sub(r'<think>[\s\S]*?</think>\s*', '', raw_accumulated).strip()

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
    from ...missions.store import get_mission_run_store
    from ...agents.store import get_agent_store
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store
    from ...memory.manager import get_memory_manager

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
        msgs = session_store.get_messages(mission.session_id, limit=500)
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

    # Also scan workspace screenshots/ directory for QA/test phases
    if mission.workspace_path:
        _ws_shots_dir = Path(mission.workspace_path) / "screenshots"
        if _ws_shots_dir.exists():
            _ws_shots = sorted(
                [f"screenshots/{f.name}" for f in _ws_shots_dir.glob("*.png")
                 if f.stat().st_size > 1000],
            )
            if _ws_shots:
                # Assign to QA phases that don't already have screenshots
                for pid in ("qa-campaign", "qa-execution", "test"):
                    if pid not in phase_screenshots:
                        phase_screenshots[pid] = _ws_shots[:6]
                        break

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
        bp_path = Path(__file__).resolve().parents[3] / "data" / "si_blueprints" / f"{mission.project_id}.yaml"
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

            # Auto-detect project platform from workspace files + mission brief
            detected = _detect_project_platform(ws_path)
            # Override with brief-based detection if files say one thing but brief says another
            brief_lower = (mission.brief or "").lower()
            brief_web_keywords = ("site web", "e-commerce", "webapp", "web app", "api rest",
                                  "saas", "dashboard", "portail", "backoffice", "back-office",
                                  "react", "vue", "angular", "svelte", "next.js", "django",
                                  "flask", "fastapi", "express", "node.js", "docker")
            if any(kw in brief_lower for kw in brief_web_keywords):
                if detected in ("macos-native", "ios-native", "unknown"):
                    # Brief says web but files say native/unknown → trust the brief
                    detected = "web-docker" if "docker" in brief_lower else "web-node"
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
                    result_launch_cmd = f"xcodegen generate && xcodebuild -scheme {scheme} -configuration Debug build && open build/Debug/{scheme}.app"
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
                # Skip hidden dirs and dependency dirs
                _ws_exclude = {"node_modules", ".git", ".next", "dist", "build", "vendor", "__pycache__", ".tox", "venv"}
                dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d not in _ws_exclude][:20]
                for f in sorted(files)[:30]:
                    if f.endswith(".bak"):
                        continue
                    fpath = os.path.join(rel, f) if rel else f
                    workspace_files.append({"path": fpath, "is_dir": False})
            workspace_files = workspace_files[:100]

    # PO Kanban: features from DB or extracted from tool_features
    po_backlog, po_sprint, po_done = [], [], []
    try:
        from ...db.migrations import get_db
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

    # QA: Agent adversarial scores (moved to Phases tab as collapsible)
    agent_scores = []
    qa_total_accepted = 0
    qa_total_rejected = 0
    qa_total_iterations = 0
    try:
        from ...db.migrations import get_db as _gdb_qa
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

    # QA: Test files in workspace (exclude node_modules, .git, vendor, etc.)
    qa_test_files = []
    _qa_exclude = {"node_modules", ".git", ".next", "dist", "build", "vendor", "__pycache__", ".tox", "venv"}
    if ws_path and Path(ws_path).exists():
        ws = Path(ws_path)
        test_globs = ["**/test_*.py", "**/*_test.py", "**/*.test.ts", "**/*.test.js",
                      "**/*.spec.ts", "**/*.spec.js", "**/Tests/**/*.swift", "**/*Test.swift",
                      "**/*Test.kt", "**/*Test.java", "tests/**/*", "test/**/*", "__tests__/**/*"]
        seen = set()
        for pat in test_globs:
            for tf in ws.glob(pat):
                rel = str(tf.relative_to(ws))
                # Skip dependency/build directories
                if any(part in _qa_exclude for part in tf.relative_to(ws).parts):
                    continue
                if tf.is_file() and tf.suffix in (".py", ".ts", ".js", ".swift", ".kt", ".java") and str(tf) not in seen:
                    seen.add(str(tf))
                    rel = str(tf.relative_to(ws))
                    # Determine test type from path/name
                    ttype = "unit"
                    lower = rel.lower()
                    if "e2e" in lower or "integration" in lower or "journey" in lower:
                        ttype = "e2e"
                    elif "smoke" in lower:
                        ttype = "smoke"
                    elif "ui" in lower or "ihm" in lower or "browser" in lower or "spec" in lower:
                        ttype = "e2e-ihm"
                    qa_test_files.append({"path": rel, "type": ttype})
        qa_test_files = sorted(qa_test_files, key=lambda x: x["type"])[:30]

    # QA: Extract test results from QA/test phase messages
    qa_phase_results = []
    if wf:
        for wp in wf.phases:
            pk = wp.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
            if "qa" in pk or "test" in pk:
                pmsgs = phase_messages.get(wp.id, [])
                for m in pmsgs:
                    content = m.get("content", "")
                    if not content:
                        continue
                    # Extract test-like results from agent messages
                    import re as _re_qa
                    # Look for pass/fail indicators
                    passes = len(_re_qa.findall(r'(?:✅|PASS|passed|réussi|OK)', content, _re_qa.IGNORECASE))
                    fails = len(_re_qa.findall(r'(?:❌|FAIL|failed|échoué|ERROR|KO)', content, _re_qa.IGNORECASE))
                    if passes or fails:
                        agent = m.get("from_agent", "unknown")
                        qa_phase_results.append({
                            "phase": wp.name,
                            "agent": agent,
                            "passes": passes,
                            "fails": fails,
                            "excerpt": content[:300],
                        })

    # ── Architecture tab data ──
    archi_content = ""
    archi_updated = ""
    archi_decisions = []
    archi_stack = []
    if ws_path and Path(ws_path).exists():
        ws = Path(ws_path)
        for archi_name in ("Architecture.md", "ARCHITECTURE.md", "architecture.md", "docs/architecture.md"):
            archi_file = ws / archi_name
            if archi_file.exists():
                try:
                    archi_content = archi_file.read_text()[:8000]
                    import datetime
                    mtime = archi_file.stat().st_mtime
                    archi_updated = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
                except Exception:
                    pass
                break

    # Extract architecture decisions from architect agent messages
    if wf:
        for wp in wf.phases:
            pmsgs = phase_messages.get(wp.id, [])
            for m in pmsgs:
                agent = m.get("from_agent", "")
                content = m.get("content", "")
                if not content:
                    continue
                is_archi_agent = any(k in agent for k in ("architecte", "archi", "lead_dev", "sre"))
                if is_archi_agent and len(content) > 50:
                    import re as _re_stack
                    for tech in _re_stack.findall(r'(?:Swift(?:UI)?|Kotlin|React|Vue|Svelte|FastAPI|Django|Node\.js|PostgreSQL|Redis|Docker|Nginx|Playwright|TypeScript|Python|Rust|Go|GraphQL|gRPC|REST|WebSocket|SSE)', content):
                        if tech not in archi_stack:
                            archi_stack.append(tech)
                    if any(kw in content.lower() for kw in ("architecture", "pattern", "design", "stack", "layer", "module", "service", "composant", "structure", "choix")):
                        archi_decisions.append({"phase": wp.name, "text": content[:400]})
    archi_decisions = archi_decisions[:10]
    archi_stack = archi_stack[:15]

    # ── Wiki tab data ──
    wiki_pages = []
    wiki_memories = []
    if ws_path and Path(ws_path).exists():
        ws = Path(ws_path)
        doc_patterns = [
            ("README.md", "README"), ("SPECS.md", "Specifications"),
            ("DesignSystem.md", "Design System"), ("API.md", "API"),
            ("CHANGELOG.md", "Changelog"), ("docs/README.md", "Documentation"),
        ]
        for fname, title in doc_patterns:
            fpath = ws / fname
            if fpath.exists():
                try:
                    content = fpath.read_text()[:5000]
                    if len(content.strip()) > 20:
                        import datetime as _dt_wiki
                        mtime = fpath.stat().st_mtime
                        updated = _dt_wiki.datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
                        wiki_pages.append({"title": title, "content": content, "updated": updated})
                except Exception:
                    pass

    # Project memory entries
    try:
        from ...memory.manager import get_memory_manager
        mem = get_memory_manager()
        if mission.project_id:
            entries = mem.project_search(mission.project_id, "", limit=20)
            for e in entries:
                if hasattr(e, "value") and e.value:
                    wiki_memories.append({"category": getattr(e, "category", "") or "general", "value": e.value[:200]})
    except Exception:
        pass
    for lesson in lessons[:5]:
        wiki_memories.append({"category": "lesson", "value": lesson[:200] if isinstance(lesson, str) else str(lesson)[:200]})
    wiki_memories = wiki_memories[:20]

    # ── Tab profiles by workflow type ──
    wf_id = mission.workflow_id or ""
    support_tickets = []
    try:
        from ...db.migrations import get_db
        _tdb = get_db()
        _ticket_rows = _tdb.execute(
            "SELECT * FROM support_tickets WHERE mission_id=? ORDER BY "
            "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
            (mission_id,)).fetchall()
        support_tickets = [dict(r) for r in _ticket_rows]
        _tdb.close()
    except Exception:
        pass
    if wf_id == "security-hacking":
        tab_profile = [
            {"id": "phases", "label": "Phases", "icon": "list"},
            {"id": "vulns", "label": "Vulnerabilites", "icon": "alert-triangle",
             "agent_id": "threat-analyst", "fallback": "pentester-lead"},
            {"id": "remediation", "label": "Remediation", "icon": "tool",
             "agent_id": "security-dev-lead", "fallback": "lead_dev"},
            {"id": "compliance", "label": "Compliance", "icon": "clipboard",
             "agent_id": "compliance_officer", "fallback": "ciso"},
            {"id": "ciso", "label": "CISO Dashboard", "icon": "shield",
             "agent_id": "ciso", "fallback": "pentester-lead"},
            {"id": "wiki", "label": "Rapport", "icon": "book-open",
             "agent_id": "tech_writer", "fallback": "pentester-lead"},
        ]
    elif wf_id == "rse-compliance":
        tab_profile = [
            {"id": "phases", "label": "Phases", "icon": "list"},
            {"id": "rgpd", "label": "RGPD", "icon": "lock",
             "agent_id": "rse-dpo", "fallback": "rse-manager"},
            {"id": "green-it", "label": "Green IT", "icon": "cpu",
             "agent_id": "rse-nr", "fallback": "rse-manager"},
            {"id": "a11y", "label": "Accessibilite", "icon": "eye",
             "agent_id": "rse-a11y", "fallback": "rse-manager"},
            {"id": "ethique", "label": "Ethique IA", "icon": "zap",
             "agent_id": "rse-ethique-ia", "fallback": "rse-manager"},
            {"id": "wiki", "label": "Synthese", "icon": "book-open",
             "agent_id": "rse-manager", "fallback": "tech_writer"},
        ]
    elif wf_id in ("tma-maintenance", "dsi-platform-tma"):
        tab_profile = [
            {"id": "phases", "label": "Phases", "icon": "list"},
            {"id": "tickets", "label": "Tickets", "icon": "inbox",
             "agent_id": "responsable_tma", "fallback": "plat-tma-lead"},
            {"id": "diagnostic", "label": "Diagnostic", "icon": "search",
             "agent_id": "dev_tma", "fallback": "plat-tma-dev-back"},
            {"id": "correctifs", "label": "Correctifs", "icon": "git-commit",
             "agent_id": "lead_dev", "fallback": "dev_tma"},
            {"id": "sla", "label": "SLA", "icon": "clock",
             "agent_id": "chef_projet", "fallback": "responsable_tma"},
            {"id": "historique", "label": "Historique", "icon": "archive",
             "agent_id": "responsable_tma", "fallback": "plat-tma-lead"},
        ]
    else:
        tab_profile = [
            {"id": "phases", "label": "Phases", "icon": "list"},
            {"id": "dev", "label": "Dev", "icon": "git-branch",
             "agent_id": "lead_dev", "fallback": "dev_backend"},
            {"id": "po", "label": "PO", "icon": "clipboard",
             "agent_id": "product_owner", "fallback": "chef_projet"},
            {"id": "qa", "label": "QA", "icon": "check",
             "agent_id": "qa_lead", "fallback": "test_manager"},
            {"id": "archi", "label": "Archi", "icon": "layers",
             "agent_id": "architecte", "fallback": "lead_dev"},
            {"id": "wiki", "label": "Wiki", "icon": "book-open",
             "agent_id": "tech_writer", "fallback": "lead_dev"},
            {"id": "projet", "label": "Projet", "icon": "code"},
        ]

    # Resolve agent for each tab
    for tp in tab_profile:
        aid = tp.get("agent_id", "")
        ag = agent_map.get(aid) or agent_map.get(tp.get("fallback", "")) or {}
        tp["agent"] = ag

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
        "qa_test_files": qa_test_files,
        "qa_phase_results": qa_phase_results,
        "archi_content": archi_content,
        "archi_updated": archi_updated,
        "archi_decisions": archi_decisions,
        "archi_stack": archi_stack,
        "wiki_pages": wiki_pages,
        "wiki_memories": wiki_memories,
        "orchestrator_id": mission.cdp_agent_id or "chef_de_programme",
        "tab_profile": tab_profile,
        "workflow_type": wf_id,
        "support_tickets": support_tickets,
    })


@router.get("/api/missions/{mission_id}")
async def api_mission_status(request: Request, mission_id: str):
    """Get mission status as JSON."""
    from ...missions.store import get_mission_run_store
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
    from ...missions.store import get_mission_run_store
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

    # Adaptive timeout: build commands need more time
    timeout = 60
    build_keywords = ("xcodebuild", "xcodegen", "gradle", "cargo build", "npm run build", "docker build", "swift build")
    if any(bk in cmd for bk in build_keywords):
        timeout = 300  # 5 minutes for builds

    try:
        result = _sp.run(
            cmd, shell=True, cwd=ws,
            capture_output=True, text=True, timeout=timeout,
            env={**_os.environ, "TERM": "dumb"},
        )
        return JSONResponse({
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-2000:],
            "returncode": result.returncode,
            "command": cmd,
        })
    except _sp.TimeoutExpired:
        return JSONResponse({"error": f"Timeout ({timeout}s)", "command": cmd}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e), "command": cmd}, status_code=500)


@router.post("/api/missions/{mission_id}/validate")
async def api_mission_validate(request: Request, mission_id: str):
    """Human validates a checkpoint (GO/NOGO/PIVOT)."""
    from ...missions.store import get_mission_run_store
    from ...sessions.store import get_session_store, MessageDef
    from ...a2a.bus import get_bus
    from ...models import A2AMessage, MessageType, PhaseStatus

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

    # Send decision to orchestrator agent via bus
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    if mission.session_id:
        session_store = get_session_store()
        session_store.add_message(MessageDef(
            session_id=mission.session_id,
            from_agent="user",
            to_agent=orch_id,
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
            to_agent=orch_id,
            message_type=MessageType.RESPONSE,
            content=f"DECISION: {decision}",
            timestamp=datetime.utcnow(),
        ))

    return JSONResponse({"decision": decision, "phase": mission.current_phase})


@router.post("/api/missions/{mission_id}/reset")
async def api_mission_reset(request: Request, mission_id: str):
    """Reset a mission: all phases back to pending, clear messages, ready to re-run."""
    from ...missions.store import get_mission_run_store
    from ...sessions.store import get_session_store, MessageDef
    from ...models import PhaseStatus, MissionStatus
    from ...sessions.runner import _push_sse

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
        from ...db.migrations import get_db
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


# ── Confluence Sync ──────────────────────────────────────────

@router.post("/api/missions/{mission_id}/confluence/sync")
async def api_confluence_sync_all(mission_id: str):
    """Sync all mission tabs to Confluence."""
    try:
        from ...confluence.sync import get_sync_engine
        engine = get_sync_engine()
        results = engine.sync_mission(mission_id)
        return JSONResponse(results)
    except FileNotFoundError:
        return JSONResponse({"error": "Confluence PAT not configured"}, status_code=503)
    except Exception as e:
        logger.error("Confluence sync failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/missions/{mission_id}/confluence/sync/{tab}")
async def api_confluence_sync_tab(mission_id: str, tab: str):
    """Sync a single tab to Confluence."""
    try:
        from ...confluence.sync import get_sync_engine
        engine = get_sync_engine()
        result = engine.sync_tab(mission_id, tab)
        return JSONResponse(result)
    except FileNotFoundError:
        return JSONResponse({"error": "Confluence PAT not configured"}, status_code=503)
    except Exception as e:
        logger.error("Confluence sync tab %s failed: %s", tab, e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/missions/{mission_id}/confluence/status")
async def api_confluence_status(mission_id: str):
    """Get Confluence sync status for a mission."""
    try:
        from ...confluence.sync import get_sync_engine
        engine = get_sync_engine()
        status = engine.get_sync_status(mission_id)
        healthy = engine.client.health_check()
        return JSONResponse({"status": status, "connected": healthy})
    except FileNotFoundError:
        return JSONResponse({"connected": False, "status": {}})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Support Tickets API (TMA) ──

@router.get("/api/missions/{mission_id}/tickets")
async def api_list_tickets(mission_id: str, status: str = ""):
    from ...db.migrations import get_db
    db = get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM support_tickets WHERE mission_id=? AND status=? ORDER BY "
            "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
            (mission_id, status)).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM support_tickets WHERE mission_id=? ORDER BY "
            "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
            (mission_id,)).fetchall()
    db.close()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/missions/{mission_id}/tickets")
async def api_create_ticket(request: Request, mission_id: str):
    import uuid
    from ...db.migrations import get_db
    body = await request.json()
    tid = str(uuid.uuid4())[:8]
    db = get_db()
    db.execute(
        "INSERT INTO support_tickets (id, mission_id, title, description, severity, category, reporter, assignee) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tid, mission_id, body.get("title", ""), body.get("description", ""),
         body.get("severity", "P3"), body.get("category", "incident"),
         body.get("reporter", ""), body.get("assignee", "")))
    db.commit()
    row = db.execute("SELECT * FROM support_tickets WHERE id=?", (tid,)).fetchone()
    db.close()
    return JSONResponse(dict(row), status_code=201)


@router.patch("/api/missions/{mission_id}/tickets/{ticket_id}")
async def api_update_ticket(request: Request, mission_id: str, ticket_id: str):
    from ...db.migrations import get_db
    body = await request.json()
    db = get_db()
    sets, vals = [], []
    for field in ("status", "severity", "assignee", "resolution", "title", "description", "category"):
        if field in body:
            sets.append(f"{field}=?")
            vals.append(body[field])
    if not sets:
        db.close()
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    sets.append("updated_at=CURRENT_TIMESTAMP")
    if body.get("status") in ("resolved", "closed"):
        sets.append("resolved_at=CURRENT_TIMESTAMP")
    vals.extend([ticket_id, mission_id])
    db.execute(f"UPDATE support_tickets SET {','.join(sets)} WHERE id=? AND mission_id=?", vals)
    db.commit()
    row = db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(dict(row))

@router.post("/api/missions/{mission_id}/run")
async def api_mission_run(request: Request, mission_id: str):
    """Drive mission execution: CDP orchestrates phases sequentially.

    Uses the REAL pattern engine (run_pattern) for each phase — agents
    think with LLM, stream their responses, and interact per pattern type.
    """
    import asyncio
    from ...missions.store import get_mission_run_store
    from ...workflows.store import get_workflow_store
    from ...agents.store import get_agent_store
    from ...models import PhaseStatus, MissionStatus
    from ...sessions.runner import _push_sse
    from ...patterns.engine import run_pattern, NodeStatus
    from ...patterns.store import PatternDef
    from datetime import datetime

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Prevent double-launch: check if an asyncio task is already running
    existing_task = _active_mission_tasks.get(mission_id)
    if existing_task and not existing_task.done():
        return JSONResponse({"status": "running", "mission_id": mission_id, "info": "already running"})

    wf = get_workflow_store().get(mission.workflow_id)
    if not wf:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)

    session_id = mission.session_id or ""
    agent_store = get_agent_store()
    # Resolve orchestrator (CISO for security, CDP for product lifecycle, etc.)
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    orch_agent = agent_store.get(orch_id)
    orch_name = orch_agent.name if orch_agent else "Orchestrateur"
    orch_role = orch_agent.role if orch_agent else "Orchestrateur"
    orch_avatar = f"/static/avatars/{orch_id}.svg"

    async def _run_phases():
        """Execute phases sequentially using the real pattern engine.
        
        Error reloop: when QA or deploy fails, re-run dev→CI/CD→QA with
        error feedback injected (max 2 reloops to avoid infinite loops).
        """
        workspace = mission.workspace_path or ""
        phases_done = 0
        phases_failed = 0
        phase_summaries = []  # accumulated phase results for cross-phase context
        reloop_count = 0
        MAX_RELOOPS = 2
        reloop_errors = []  # accumulated error context across reloops

        # Use index-based iteration to allow backtracking
        i = 0
        while i < len(mission.phases):
            phase = mission.phases[i]
            wf_phase = wf.phases[i] if i < len(wf.phases) else None
            if not wf_phase:
                i += 1
                continue

            # Skip already-completed phases (for resume/fast-forward)
            if phase.status in (PhaseStatus.DONE, PhaseStatus.DONE_WITH_ISSUES, PhaseStatus.SKIPPED):
                if phase.summary:
                    phase_summaries.append(f"## {wf_phase.name}\n{phase.summary}")
                i += 1
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
                "from_agent": orch_id,
                "from_name": orch_name,
                "from_role": orch_role,
                "from_avatar": orch_avatar,
                "content": cdp_announce,
                "phase_id": phase.phase_id,
                "msg_type": "text",
            })
            await asyncio.sleep(0.5)

            # Snapshot message count before phase starts (for summary extraction)
            from ...sessions.store import get_session_store as _get_ss
            _ss_pre = _get_ss()
            _pre_phase_msg_count = len(_ss_pre.get_messages(session_id, limit=1000))

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
            is_dev_phase = "sprint" in phase_key_check or "dev" in phase_key_check
            is_retryable = is_dev_phase or "cicd" in phase_key_check or "qa" in phase_key_check or "architecture" in phase_key_check or "setup" in phase_key_check
            max_sprints = wf_phase.config.get("max_iterations", 3) if is_dev_phase else (2 if is_retryable else 1)

            # Run the real pattern engine — NO fake success on error
            phase_success = False
            phase_error = ""

            for sprint_num in range(1, max_sprints + 1):
                sprint_label = f"Sprint {sprint_num}/{max_sprints}" if max_sprints > 1 else ""

                if max_sprints > 1:
                    # Announce sprint start
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
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
                            from ...memory.manager import get_memory_manager
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
                # - Failure/VETO → remediation: retry with feedback (all retryable phases)
                # - Failure in non-retryable phases → break immediately
                if not phase_success:
                    if sprint_num < max_sprints:
                        # Retry with veto/error feedback
                        retry_label = f"Itération {sprint_num}/{max_sprints}" if not is_dev_phase else sprint_label
                        remediation_msg = f"{retry_label} terminé avec des problèmes. Relance avec feedback correctif…"
                        await _push_sse(session_id, {
                            "type": "message",
                            "from_agent": orch_id,
                            "from_name": orch_name,
                            "from_role": orch_role,
                            "from_avatar": orch_avatar,
                            "content": remediation_msg,
                            "phase_id": phase.phase_id,
                            "msg_type": "text",
                        })
                        await asyncio.sleep(0.8)
                        # Inject rejection feedback into next iteration context
                        prev_context += f"\n- REJET itération {sprint_num}: {phase_error[:500]}"
                        phase_error = ""  # reset for next attempt
                        continue
                    else:
                        break  # Last iteration: stop

                # Announce sprint completion (only for multi-sprint phases)
                if max_sprints > 1 and sprint_num < max_sprints:
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
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
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
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
                # Build LLM summary from agent messages (with timeout)
                try:
                    from ...sessions.store import get_session_store
                    from ...llm.client import get_llm_client, LLMMessage
                    ss = get_session_store()
                    phase_msgs = ss.get_messages(session_id, limit=1000)
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
                        transcript = "\n\n".join(convo[-15:])
                        llm = get_llm_client()
                        resp = await asyncio.wait_for(llm.chat([
                            LLMMessage(role="user", content=f"Summarize this team discussion in 2-3 sentences. Focus on decisions made, key proposals, and conclusions. Be factual and specific. Answer in the same language as the discussion.\n\n{transcript[:4000]}")
                        ], max_tokens=200, temperature=0.3), timeout=45)
                        phase.summary = (resp.content or "").strip()[:500]
                    if not getattr(phase, 'summary', None):
                        phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                except Exception:
                    phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                phases_done += 1

                summary_text = f"[{wf_phase.name}] terminée"
                if mission.workspace_path:
                    try:
                        import subprocess as _sp
                        diff_stat = _sp.run(
                            ["git", "diff", "--stat", "HEAD~1"],
                            cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                        )
                        if diff_stat.stdout.strip():
                            summary_text += f" | Fichiers: {diff_stat.stdout.strip().split(chr(10))[-1]}"
                    except Exception:
                        pass
                try:
                    from ...memory.manager import get_memory_manager
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
            else:
                phase.summary = f"Phase échouée — {phase_error[:200]}"
                phases_failed += 1
            run_store.update(mission)

            # Send phase_completed SSE IMMEDIATELY (before slow hooks)
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
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
                        "content": cdp_msg,
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    await asyncio.sleep(0.8)
                else:
                    # Phase failed — check if it's a blocking phase
                    # Strategic gates (HITL) + dev/CI phases are blocking
                    # Only discussion/ideation/TMA phases are non-blocking
                    phase_key = phase.phase_id.lower() if phase.phase_id else ""
                    is_execution_phase = any(k in phase_key for k in ("sprint", "dev", "cicd", "ci-cd", "pipeline", "deploy"))
                    blocking = (
                        (pattern_type in ("human-in-the-loop",) and "deploy" not in phase.phase_id)
                        or is_execution_phase  # dev/CI/CD failures are blocking
                    )
                    # Phase failed — determine response
                    phase_key = phase.phase_id.lower() if phase.phase_id else ""
                    is_execution_phase = any(k in phase_key for k in ("sprint", "dev", "cicd", "ci-cd", "pipeline"))
                    is_hitl_gate = pattern_type in ("human-in-the-loop",) and "deploy" not in phase.phase_id
                    short_err = phase_error[:200] if phase_error else "erreur inconnue"
                    if is_hitl_gate:
                        # Strategic gate NOGO — stop mission
                        cdp_msg = f"Phase «{wf_phase.name}» échouée ({short_err}). Epic arrêtée — corrigez puis relancez via le bouton Réinitialiser."
                    elif is_execution_phase:
                        # Dev/CI/CD failure — keep as FAILED (reloop will handle if applicable)
                        cdp_msg = f"Phase «{wf_phase.name}» échouée ({short_err}). Phase bloquante — correction nécessaire avant de continuer."
                        # DON'T downgrade to DONE_WITH_ISSUES — this is a real failure
                    else:
                        cdp_msg = f"Phase «{wf_phase.name}» terminée avec des problèmes ({short_err}). Passage à la phase suivante malgré tout…"
                        phase.status = PhaseStatus.DONE_WITH_ISSUES  # clearly mark issues
                        phases_done += 1
                        phases_failed -= 1  # undo the +1 from above
                        # Rebuild summary from agent messages (not "Phase échouée")
                        try:
                            from ...sessions.store import get_session_store
                            ss = get_session_store()
                            phase_msgs = ss.get_messages(session_id, limit=1000)
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
                                from ...llm.client import get_llm_client, LLMMessage
                                llm = get_llm_client()
                                transcript = "\n\n".join(convo[-10:])
                                resp = await asyncio.wait_for(llm.chat([
                                    LLMMessage(role="user", content=f"Résume cette discussion d'équipe en 2-3 phrases. Focus sur les décisions et conclusions. Même langue que la discussion.\n\n{transcript[:3000]}")
                                ], max_tokens=200, temperature=0.3), timeout=45)
                                new_summary = (resp.content or "").strip()[:500]
                                if new_summary and len(new_summary) > 20:
                                    phase.summary = new_summary
                                else:
                                    phase.summary = f"{len(aids)} agents ont travaillé ({pattern_type}) — terminée avec avertissements"
                            else:
                                phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                        except Exception:
                            phase.summary = f"{len(aids)} agents ont travaillé ({pattern_type}) — terminée avec avertissements"
                    await _push_sse(session_id, {
                        "type": "message",
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
                        "content": cdp_msg,
                        "phase_id": phase.phase_id,
                        "msg_type": "text",
                    })
                    if is_hitl_gate:
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

            # Post-phase hooks (non-blocking — don't block pipeline)
            if phase_success:
                async def _safe_hooks():
                    try:
                        await asyncio.wait_for(
                            _run_post_phase_hooks(
                                phase.phase_id, wf_phase.name, mission, session_id, _push_sse
                            ), timeout=90
                        )
                    except Exception as hook_err:
                        logger.warning("Post-phase hooks timeout/error for %s: %s", phase.phase_id, hook_err)
                asyncio.create_task(_safe_hooks())

            # ── Error Reloop: execution phase failure → retry or loop back ──
            # When dev/CI/QA/deploy fails, loop back to dev-sprint with error feedback.
            if not phase_success and reloop_count < MAX_RELOOPS:
                phase_key_rl = phase.phase_id.lower() if phase.phase_id else ""
                is_reloopable = any(k in phase_key_rl for k in ("qa", "deploy", "tma", "sprint", "dev", "cicd", "ci-cd", "pipeline"))
                if is_reloopable:
                    reloop_count += 1
                    reloop_errors.append(f"[Reloop {reloop_count}] Phase «{wf_phase.name}» failed: {phase_error[:300]}")
                    # Find dev-sprint phase index
                    dev_idx = None
                    for j, wp_j in enumerate(wf.phases):
                        pk_j = wp_j.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
                        if "sprint" in pk_j or "dev" in pk_j:
                            dev_idx = j
                            break
                    if dev_idx is not None and dev_idx <= i:
                        # CDP announces reloop
                        reloop_msg = (
                            f"Reloop {reloop_count}/{MAX_RELOOPS} — Phase «{wf_phase.name}» échouée. "
                            f"Erreur: {phase_error[:200]}. "
                            f"Retour au sprint de développement pour correction…"
                        )
                        await _push_sse(session_id, {
                            "type": "message",
                            "from_agent": orch_id,
                            "from_name": orch_name,
                            "from_role": orch_role,
                            "from_avatar": orch_avatar,
                            "content": reloop_msg,
                            "phase_id": phase.phase_id,
                            "msg_type": "text",
                        })
                        await asyncio.sleep(1)
                        # Reset dev-sprint and subsequent phases for re-execution
                        reset_pids = []
                        for k in range(dev_idx, len(mission.phases)):
                            mission.phases[k].status = PhaseStatus.PENDING
                            mission.phases[k].summary = None
                            mission.phases[k].started_at = None
                            mission.phases[k].completed_at = None
                            reset_pids.append(mission.phases[k].phase_id)
                        run_store.update(mission)
                        # Send reloop SSE event to reset frontend
                        await _push_sse(session_id, {
                            "type": "reloop",
                            "mission_id": mission.id,
                            "reloop_count": reloop_count,
                            "max_reloops": MAX_RELOOPS,
                            "failed_phase": phase.phase_id,
                            "target_phase": mission.phases[dev_idx].phase_id,
                            "reset_phases": reset_pids,
                            "error": phase_error[:200],
                        })
                        # Inject error context for dev agents
                        error_feedback = "\n".join(reloop_errors)
                        prev_context += f"\n\n--- RELOOP FEEDBACK (erreurs à corriger) ---\n{error_feedback}\n"
                        # Jump back to dev-sprint
                        i = dev_idx
                        continue

            i += 1

        # Mission complete — count from actual phase statuses
        phases_done = sum(1 for p in mission.phases if p.status == PhaseStatus.DONE)
        phases_with_issues = sum(1 for p in mission.phases if p.status == PhaseStatus.DONE_WITH_ISSUES)
        phases_failed = sum(1 for p in mission.phases if p.status == PhaseStatus.FAILED)
        total = phases_done + phases_with_issues + phases_failed
        if phases_failed == 0 and phases_with_issues == 0:
            mission.status = MissionStatus.COMPLETED
            reloop_info = f" ({reloop_count} reloop{'s' if reloop_count > 1 else ''})" if reloop_count > 0 else ""
            final_msg = f"Epic terminée avec succès — {phases_done}/{total} phases réussies{reloop_info}."
        else:
            mission.status = MissionStatus.COMPLETED if phases_done > 0 else MissionStatus.FAILED
            reloop_info = f" ({reloop_count} reloop{'s' if reloop_count > 1 else ''})" if reloop_count > 0 else ""
            issues_info = f", {phases_with_issues} avec avertissements" if phases_with_issues > 0 else ""
            final_msg = f"Epic terminée — {phases_done} réussies{issues_info}, {phases_failed} échouées sur {total} phases{reloop_info}."
        run_store.update(mission)
        await _push_sse(session_id, {
            "type": "message",
            "from_agent": orch_id,
            "from_name": orch_name,
            "from_role": orch_role,
            "from_avatar": orch_avatar,
            "content": final_msg,
            "msg_type": "text",
        })

        # Auto-trigger retrospective on epic completion
        try:
            await _auto_retrospective(mission, session_id, phase_summaries, _push_sse)
        except Exception as retro_err:
            logger.warning(f"Auto-retrospective failed: {retro_err}")

    async def _safe_run():
        try:
            await _run_phases()
        except Exception as exc:
            import traceback
            logger.error("Mission %s _run_phases crashed: %s\n%s", mission_id, exc, traceback.format_exc())
            try:
                mission.status = MissionStatus.FAILED
                run_store.update(mission)
                await _push_sse(session_id, {
                    "type": "message",
                    "from_agent": orch_id,
                    "from_name": orch_name,
                    "from_role": orch_role,
                    "from_avatar": orch_avatar,
                    "content": f"Erreur interne: {exc}",
                    "msg_type": "text",
                })
            except Exception:
                pass

    mission.status = MissionStatus.RUNNING
    run_store.update(mission)

    # Track the task so we can detect stuck missions after restart
    task = asyncio.create_task(_safe_run())
    _active_mission_tasks[mission_id] = task
    task.add_done_callback(lambda t: _active_mission_tasks.pop(mission_id, None))

    return JSONResponse({"status": "running", "mission_id": mission_id})


async def _auto_retrospective(mission, session_id: str, phase_summaries: list, push_sse):
    """Auto-generate retrospective when epic completes, store lessons in global memory."""
    from ...memory.manager import get_memory_manager
    from ...sessions.store import get_session_store
    from ...llm.client import get_llm_client, LLMMessage
    import json as _json

    ss = get_session_store()
    msgs = ss.get_messages(session_id, limit=500)
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

    # Auto-commit after EVERY phase — agents never call git_commit reliably
    try:
        result = subprocess.run(
            ["git", "add", "-A"], cwd=workspace, capture_output=True, text=True, timeout=10
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True, timeout=10
        )
        if status.stdout.strip():
            file_count = status.stdout.strip().count("\n") + 1
            commit_msg = f"chore({phase_key}): {phase_name} — {file_count} files"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=workspace, capture_output=True, text=True, timeout=10
            )
            await push_sse(session_id, {
                "type": "message",
                "from_agent": "system",
                "from_name": "CI/CD",
                "from_role": "Pipeline",
                "content": f"Auto-commit: {file_count} fichiers ({phase_name})",
                "phase_id": phase_id,
                "msg_type": "text",
            })
    except Exception as e:
        logger.warning("Auto-commit failed for phase %s: %s", phase_id, e)

    # After EVERY phase: update Architecture.md + docs via LLM (architect + tech writer)
    await _update_docs_post_phase(phase_id, phase_name, mission, session_id, push_sse)

    # After ideation/architecture/dev: extract features for PO kanban
    if any(k in phase_key for k in ("ideation", "architecture", "sprint", "dev", "setup")):
        await _extract_features_from_phase(phase_id, mission, session_id)

    # After dev sprint: auto screenshots for HTML files
    if "dev" in phase_key or "sprint" in phase_key:
        ws = Path(workspace)
        html_files = list(ws.glob("*.html")) + list(ws.glob("public/*.html")) + list(ws.glob("src/*.html"))
        if html_files:
            screenshots_dir = ws / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            shot_paths = []
            for hf in html_files[:3]:
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
                try:
                    r = subprocess.run(
                        ["node", "-e", shot_script],
                        capture_output=True, text=True, cwd=workspace, timeout=30
                    )
                    if r.returncode == 0 and (screenshots_dir / fname).exists():
                        shot_paths.append(f"screenshots/{fname}")
                except Exception:
                    pass

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

    # After QA phases: auto-build + screenshot pipeline (deterministic, no LLM)
    if "qa" in phase_key or "test" in phase_key:
        ws = Path(workspace)
        try:
            platform_type = _detect_project_platform(str(ws))
            screenshots = await _auto_qa_screenshots(ws, platform_type)
            if screenshots:
                shot_content = f"📸 QA Screenshots ({platform_type}) — {len(screenshots)} captures :\n"
                shot_content += "\n".join(f"[SCREENSHOT:{s}]" for s in screenshots)
                await push_sse(session_id, {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "QA Pipeline",
                    "from_role": "Automated QA",
                    "content": shot_content,
                    "phase_id": phase_id,
                    "msg_type": "text",
                })
        except Exception as e:
            logger.error("Post-phase QA screenshots failed: %s", e)

    # Confluence sync — auto-sync after every phase
    try:
        from ...confluence.sync import get_sync_engine
        engine = get_sync_engine()
        if engine.client.health_check():
            results = engine.sync_mission(mission.id if hasattr(mission, 'id') else str(mission))
            synced = [t for t, r in results.items() if r.get("status") == "ok"]
            if synced:
                await push_sse(session_id, {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "Confluence",
                    "from_role": "Sync",
                    "content": f"Sync Confluence: {', '.join(synced)} ({len(synced)} pages)",
                    "phase_id": phase_id,
                    "msg_type": "text",
                })
    except FileNotFoundError:
        pass  # No PAT configured — skip
    except Exception as e:
        logger.warning("Confluence sync failed: %s", e)


async def _extract_features_from_phase(phase_id: str, mission, session_id: str):
    """Extract features/stories from agent messages and store in features table."""
    from ...sessions.store import get_session_store
    from ...llm.client import get_llm_client, LLMMessage
    from ...db.migrations import get_db
    import json, uuid

    try:
        ss = get_session_store()
        msgs = ss.get_messages(session_id, limit=500)
        # Collect agent messages from this phase
        texts = []
        for m in msgs:
            meta = m.metadata if isinstance(m.metadata, dict) else {}
            if meta.get("phase_id") != phase_id:
                continue
            agent = getattr(m, "from_agent", "") or ""
            if agent in ("system", "user", "chef_de_programme"):
                continue
            content = (getattr(m, "content", "") or "").strip()
            if len(content) > 50:
                texts.append(content[:500])
        if not texts:
            return

        transcript = "\n---\n".join(texts[-10:])
        llm = get_llm_client()
        resp = await asyncio.wait_for(llm.chat([
            LLMMessage(role="user", content=(
                "Extract product features/stories from this team discussion. "
                "Return a JSON array of objects with keys: name (short title), "
                "description (1-2 sentences), priority (1-5, 1=highest), status (backlog/in_progress/done). "
                "Only extract real product features, not meta-discussion. Max 8 items. "
                "Return ONLY valid JSON array, no markdown.\n\n"
                f"{transcript[:4000]}"
            ))
        ], max_tokens=500, temperature=0.2), timeout=30)

        raw = (resp.content or "").strip()
        # Extract JSON array from response
        if raw.startswith("```"):
            raw = raw.split("```")[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        features = json.loads(raw)
        if not isinstance(features, list):
            return

        db = get_db()
        for f in features[:8]:
            name = f.get("name", "").strip()
            if not name or len(name) < 3:
                continue
            fid = str(uuid.uuid4())[:8]
            try:
                db.execute(
                    "INSERT OR IGNORE INTO features (id, epic_id, name, description, priority, status) VALUES (?,?,?,?,?,?)",
                    (fid, mission.id, name, f.get("description", "")[:500],
                     f.get("priority", 5), f.get("status", "backlog"))
                )
            except Exception:
                pass
        db.commit()
        db.close()
    except Exception as e:
        logger.warning("Feature extraction failed for phase %s: %s", phase_id, e)


async def _update_docs_post_phase(
    phase_id: str, phase_name: str, mission, session_id: str, push_sse
):
    """Call LLM to update Architecture.md and README.md after each phase."""
    from pathlib import Path
    import subprocess

    workspace = mission.workspace_path
    if not workspace or not Path(workspace).is_dir():
        return

    ws = Path(workspace)

    # Gather context: list of files + phase summary from messages
    try:
        file_list = subprocess.run(
            ["find", ".", "-type", "f", "-not", "-path", "./.git/*", "-not", "-name", "*.bak"],
            cwd=workspace, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        file_list = ""

    # Read existing docs for incremental update
    existing_archi = ""
    archi_path = ws / "Architecture.md"
    if archi_path.exists():
        try:
            existing_archi = archi_path.read_text()[:3000]
        except Exception:
            pass

    existing_readme = ""
    readme_path = ws / "README.md"
    if readme_path.exists():
        try:
            existing_readme = readme_path.read_text()[:2000]
        except Exception:
            pass

    # Read key source files for context (first 200 lines of main files)
    code_context = ""
    code_files = list(ws.glob("**/*.swift"))[:3] + list(ws.glob("**/*.ts"))[:3] + list(ws.glob("**/*.py"))[:3] + list(ws.glob("**/*.svelte"))[:3]
    for cf in code_files[:4]:
        try:
            content = cf.read_text()[:1500]
            code_context += f"\n--- {cf.relative_to(ws)} ---\n{content}\n"
        except Exception:
            pass

    if not file_list and not code_context:
        return

    from ...llm.client import get_llm_client, LLMMessage

    client = get_llm_client()

    # 1. Architecture update (architect agent)
    try:
        archi_prompt = f"""Tu es l'architecte logiciel. Apres la phase "{phase_name}", mets a jour Architecture.md.

Fichiers du projet:
{file_list[:2000]}

Code source principal:
{code_context[:3000]}

Architecture existante:
{existing_archi[:2000] if existing_archi else "(aucune)"}

Genere un Architecture.md complet et a jour avec:
- Vue d'ensemble du projet
- Stack technique (langages, frameworks, outils)
- Structure des dossiers/modules
- Patterns utilises (MVC, MVVM, etc.)
- Diagramme ASCII des composants principaux
- Decisions architecturales prises

Reponds UNIQUEMENT avec le contenu Markdown du fichier."""

        resp = await asyncio.wait_for(client.chat(
            messages=[LLMMessage(role="user", content=archi_prompt)],
            system_prompt="Architecte logiciel senior. Documentation technique concise et precise.",
            temperature=0.3, max_tokens=2000,
        ), timeout=60)
        archi_text = resp.content.strip()
        # Strip markdown fences if present
        if archi_text.startswith("```"):
            archi_text = archi_text.split("\n", 1)[1] if "\n" in archi_text else archi_text
        if archi_text.endswith("```"):
            archi_text = archi_text.rsplit("```", 1)[0]

        if len(archi_text) > 100:
            archi_path.write_text(archi_text)
            await push_sse(session_id, {
                "type": "message",
                "from_agent": "architecte",
                "from_name": "Architecte",
                "from_role": "Architecture",
                "content": f"Architecture.md mis a jour ({len(archi_text)} chars)",
                "phase_id": phase_id,
                "msg_type": "text",
            })
    except Exception as e:
        logger.warning("Architecture update failed: %s", e)

    # 2. README update (tech writer agent)
    try:
        readme_prompt = f"""Tu es le tech writer. Apres la phase "{phase_name}", mets a jour README.md.

Fichiers du projet:
{file_list[:1500]}

README existant:
{existing_readme[:1500] if existing_readme else "(aucun)"}

Genere un README.md a jour avec:
- Titre et description du projet
- Prerequis / Installation
- Lancement (commande build et run)
- Structure du projet
- Technologies utilisees
- Statut actuel

Reponds UNIQUEMENT avec le contenu Markdown du fichier."""

        resp = await asyncio.wait_for(client.chat(
            messages=[LLMMessage(role="user", content=readme_prompt)],
            system_prompt="Technical writer. Documentation claire et actionnable.",
            temperature=0.3, max_tokens=1500,
        ), timeout=60)
        readme_text = resp.content.strip()
        if readme_text.startswith("```"):
            readme_text = readme_text.split("\n", 1)[1] if "\n" in readme_text else readme_text
        if readme_text.endswith("```"):
            readme_text = readme_text.rsplit("```", 1)[0]

        if len(readme_text) > 80:
            readme_path.write_text(readme_text)
            await push_sse(session_id, {
                "type": "message",
                "from_agent": "tech_writer",
                "from_name": "Tech Writer",
                "from_role": "Documentation",
                "content": f"README.md mis a jour ({len(readme_text)} chars)",
                "phase_id": phase_id,
                "msg_type": "text",
            })
    except Exception as e:
        logger.warning("README update failed: %s", e)

    # Auto-commit docs update
    try:
        subprocess.run(["git", "add", "Architecture.md", "README.md"], cwd=workspace, capture_output=True, text=True, timeout=5)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True, timeout=5)
        if status.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", f"docs({phase_name.lower().replace(' ', '-')}): update Architecture.md + README.md"],
                cwd=workspace, capture_output=True, text=True, timeout=10
            )
    except Exception:
        pass


async def _auto_qa_screenshots(ws: "Path", platform_type: str) -> list[str]:
    """Deterministic screenshot pipeline — build, run, capture. No LLM."""
    screenshots_dir = ws / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    if platform_type == "macos-native":
        results = await _qa_screenshots_macos(ws, screenshots_dir)
    elif platform_type == "ios-native":
        results = await _qa_screenshots_ios(ws, screenshots_dir)
    elif platform_type in ("web-docker", "web-node", "web-static"):
        results = await _qa_screenshots_web(ws, screenshots_dir, platform_type)
    else:
        return []

    # Filter out tiny/empty screenshots
    return [r for r in results if (ws / r).exists() and (ws / r).stat().st_size > 1000]


async def _qa_screenshots_macos(ws: "Path", shots_dir: "Path") -> list[str]:
    """Build Swift app → launch → AppleScript navigation → multi-step screenshots."""
    import subprocess
    import asyncio as _aio

    results = []

    # 1. Ensure Package.swift exists
    pkg = ws / "Package.swift"
    if not pkg.exists() and (ws / "Sources").exists():
        app_name = "App"
        for sf in (ws / "Sources").rglob("*App.swift"):
            app_name = sf.stem.replace("App", "") or "App"
            break

        # Detect duplicate filenames and .bak files to exclude
        from collections import Counter
        swift_files = list((ws / "Sources").rglob("*.swift"))
        name_counts = Counter(f.name for f in swift_files)
        excludes = []
        seen_names = set()
        for sf in sorted(swift_files, key=lambda f: len(str(f))):
            rel = str(sf.relative_to(ws / "Sources"))
            if sf.suffix == ".bak" or rel.endswith(".bak"):
                continue
            if sf.name in seen_names and name_counts[sf.name] > 1:
                excludes.append(f'"{rel}"')
            seen_names.add(sf.name)

        # Also exclude .bak files
        for sf in (ws / "Sources").rglob("*.bak"):
            excludes.append(f'"{str(sf.relative_to(ws / "Sources"))}"')

        exclude_clause = ""
        if excludes:
            exclude_clause = f',\n            exclude: [{", ".join(excludes)}]'

        pkg.write_text(
            f'// swift-tools-version:5.9\n'
            f'import PackageDescription\n\n'
            f'let package = Package(\n'
            f'    name: "{app_name}",\n'
            f'    platforms: [.macOS(.v14)],\n'
            f'    targets: [\n'
            f'        .executableTarget(\n'
            f'            name: "{app_name}",\n'
            f'            path: "Sources"{exclude_clause}\n'
            f'        ),\n'
            f'    ]\n'
            f')\n'
        )
        logger.info("Auto-generated Package.swift for %s (excluding %d files)", app_name, len(excludes))

    # 2. Build
    build_result = subprocess.run(
        ["xcrun", "swift", "build"],
        cwd=str(ws), capture_output=True, text=True, timeout=120,
    )
    build_log = (build_result.stdout + "\n" + build_result.stderr)[-3000:]
    (shots_dir / "build_log.txt").write_text(build_log)

    if build_result.returncode != 0:
        _write_status_png(shots_dir / "01_build_failed.png", "BUILD FAILED ❌",
                          build_log[-1200:], bg_color=(40, 10, 10))
        results.append("screenshots/01_build_failed.png")
        return results

    _write_status_png(shots_dir / "01_build_success.png", "BUILD SUCCESS ✅",
                      build_log[-400:], bg_color=(10, 40, 10))
    results.append("screenshots/01_build_success.png")

    # 3. Find the built binary
    binary = None
    for d in [ws / ".build" / "debug", ws / ".build" / "release"]:
        if d.exists():
            for f in d.iterdir():
                if f.is_file() and f.stat().st_mode & 0o111 and not f.suffix and f.name != "ModuleCache":
                    binary = f
                    break
            if binary:
                break

    if not binary:
        _write_status_png(shots_dir / "02_no_binary.png", "NO EXECUTABLE",
                          "Build produced no runnable binary.", bg_color=(40, 30, 10))
        results.append("screenshots/02_no_binary.png")
        return results

    # 4. Discover views/screens from source code for journey steps
    views = _discover_macos_views(ws)

    # 5. Launch app + multi-step screenshots via AppleScript
    proc = None
    try:
        proc = subprocess.Popen(
            [str(binary)], cwd=str(ws),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        await _aio.sleep(3)

        app_name = binary.name

        # Step 1: Initial launch
        _capture_app_screenshot(app_name, shots_dir / "02_launch.png")
        if (shots_dir / "02_launch.png").exists():
            results.append("screenshots/02_launch.png")

        # Step 2: Interact with each discovered view/tab via keyboard/menu
        step = 3
        for view in views[:8]:
            await _aio.sleep(1)
            # Try navigating via menu or keyboard shortcut
            _applescript_navigate(app_name, view)
            await _aio.sleep(1.5)
            fname = f"{step:02d}_{view['id']}.png"
            _capture_app_screenshot(app_name, shots_dir / fname)
            if (shots_dir / fname).exists():
                results.append(f"screenshots/{fname}")
            step += 1

        # Step N: Final state
        await _aio.sleep(1)
        _capture_app_screenshot(app_name, shots_dir / f"{step:02d}_final_state.png")
        if (shots_dir / f"{step:02d}_final_state.png").exists():
            results.append(f"screenshots/{step:02d}_final_state.png")

    except Exception as e:
        _write_status_png(shots_dir / "02_launch_error.png", "LAUNCH FAILED",
                          str(e)[:500], bg_color=(40, 10, 10))
        results.append("screenshots/02_launch_error.png")
    finally:
        if proc:
            try:
                import os
                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    return results


def _discover_macos_views(ws: "Path") -> list[dict]:
    """Scan Swift sources to discover views/screens for screenshot journey."""
    views = []
    seen = set()
    for sf in sorted(ws.rglob("*.swift")):
        try:
            code = sf.read_text(errors="ignore")
        except Exception:
            continue
        name = sf.stem
        # Detect SwiftUI views
        if ": View" in code and "var body" in code and name not in seen:
            view_type = "tab"
            if "TabView" in code:
                view_type = "tabview"
            elif "NavigationView" in code or "NavigationStack" in code:
                view_type = "navigation"
            elif "Sheet" in code or ".sheet" in code:
                view_type = "sheet"
            elif "Menu" in code or "MenuBar" in code:
                view_type = "menu"
            # Extract keyboard shortcut if any
            shortcut = None
            import re
            ks = re.search(r'\.keyboardShortcut\("(\w)"', code)
            if ks:
                shortcut = ks.group(1)
            views.append({"id": name.lower(), "name": name, "type": view_type, "shortcut": shortcut})
            seen.add(name)
    return views


def _capture_app_screenshot(app_name: str, output_path: "Path"):
    """Capture app window screenshot via screencapture -l (window ID)."""
    import subprocess
    try:
        # Get window ID via AppleScript
        script = (
            'tell application "System Events"\n'
            f'  set appProc to first process whose name contains "{app_name}"\n'
            '  set wID to id of first window of appProc\n'
            '  return wID\n'
            'end tell'
        )
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            subprocess.run(["screencapture", "-l", r.stdout.strip(), str(output_path)],
                           timeout=10, capture_output=True)
        else:
            # Fallback: full screen
            subprocess.run(["screencapture", "-x", str(output_path)],
                           timeout=10, capture_output=True)
    except Exception:
        import subprocess as _sp
        _sp.run(["screencapture", "-x", str(output_path)],
                timeout=10, capture_output=True)


def _applescript_navigate(app_name: str, view: dict):
    """Navigate to a view via AppleScript (keyboard shortcuts, menu clicks, tabs)."""
    import subprocess
    try:
        if view.get("shortcut"):
            # Use keyboard shortcut
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  keystroke "{view["shortcut"]}" using command down\n'
                f'end tell'
            )
        elif view["type"] == "menu":
            # Click menu bar icon
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  click menu bar item 1 of menu bar 2 of process "{app_name}"\n'
                f'end tell'
            )
        elif view["type"] == "tab" or view["type"] == "tabview":
            # Try Tab key navigation
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  keystroke tab\n'
                f'end tell'
            )
        elif view["type"] == "sheet":
            # Try Cmd+N for new item (common pattern)
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  keystroke "n" using command down\n'
                f'end tell'
            )
        elif view["type"] == "navigation":
            # Try arrow keys to navigate list
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  key code 125\n'
                f'end tell'
            )
        else:
            return
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass


async def _qa_screenshots_ios(ws: "Path", shots_dir: "Path") -> list[str]:
    """Build iOS app for simulator, boot sim, screenshot."""
    import subprocess
    import asyncio as _aio

    results = []
    has_xcproj = any(ws.glob("*.xcodeproj")) or any(ws.glob("*.xcworkspace"))

    if has_xcproj:
        build_result = subprocess.run(
            ["xcodebuild", "-scheme", "App", "-sdk", "iphonesimulator",
             "-destination", "platform=iOS Simulator,name=iPhone 16",
             "-derivedDataPath", str(ws / ".build"), "build"],
            cwd=str(ws), capture_output=True, text=True, timeout=180,
        )
    else:
        build_result = subprocess.run(
            ["xcrun", "swift", "build"],
            cwd=str(ws), capture_output=True, text=True, timeout=120,
        )

    build_log = (build_result.stdout + "\n" + build_result.stderr)[-2000:]
    if build_result.returncode != 0:
        _write_status_png(shots_dir / "01_ios_build_failed.png", "iOS BUILD FAILED ❌",
                          build_log[-1000:], bg_color=(40, 10, 10))
        results.append("screenshots/01_ios_build_failed.png")
        return results

    _write_status_png(shots_dir / "01_ios_build_success.png", "iOS BUILD ✅",
                      build_log[-400:], bg_color=(10, 40, 10))
    results.append("screenshots/01_ios_build_success.png")

    # Boot simulator + screenshot
    try:
        subprocess.run(["xcrun", "simctl", "boot", "iPhone 16"],
                       capture_output=True, timeout=30)
        await _aio.sleep(3)
        subprocess.run(
            ["xcrun", "simctl", "io", "booted", "screenshot",
             str(shots_dir / "02_simulator.png")],
            capture_output=True, timeout=15,
        )
        if (shots_dir / "02_simulator.png").exists():
            results.append("screenshots/02_simulator.png")
    except Exception as e:
        logger.error("iOS simulator screenshot failed: %s", e)
    return results


async def _qa_screenshots_web(ws: "Path", shots_dir: "Path", platform_type: str) -> list[str]:
    """Start web server → Playwright multi-step journey screenshots (routes + interactions + RBAC)."""
    import subprocess
    import asyncio as _aio

    results = []
    proc = None
    port = 18234

    try:
        # Start server
        if platform_type == "web-docker":
            r = subprocess.run(
                ["docker", "build", "-t", "qa-screenshot-app", "."],
                cwd=str(ws), capture_output=True, text=True, timeout=180,
            )
            if r.returncode == 0:
                proc = subprocess.Popen(
                    ["docker", "run", "--rm", "--name", "qa-screenshot-app",
                     "-p", f"{port}:8080", "qa-screenshot-app"],
                    cwd=str(ws), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                build_log = (r.stdout + "\n" + r.stderr)[-1200:]
                _write_status_png(shots_dir / "01_docker_build_failed.png",
                                  "DOCKER BUILD FAILED ❌", build_log, bg_color=(40, 10, 10))
                results.append("screenshots/01_docker_build_failed.png")
                return results
        elif platform_type == "web-node":
            subprocess.run(["npm", "install"], cwd=str(ws), capture_output=True, timeout=60)
            proc = subprocess.Popen(
                ["npm", "start"], cwd=str(ws),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**__import__("os").environ, "PORT": str(port)},
            )
        elif platform_type == "web-static":
            proc = subprocess.Popen(
                ["python3", "-m", "http.server", str(port)],
                cwd=str(ws), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        if proc:
            await _aio.sleep(4)

            # Discover routes from codebase
            routes = _discover_web_routes(ws)
            # Discover auth/RBAC users if any
            users = _discover_web_users(ws)

            # Generate Playwright journey script
            journey_script = _build_playwright_journey(port, routes, users, str(shots_dir))

            r = subprocess.run(["node", "-e", journey_script],
                               capture_output=True, text=True, timeout=90,
                               cwd=str(ws))

            # Collect all generated screenshots
            if shots_dir.exists():
                for png in sorted(shots_dir.glob("*.png")):
                    if png.stat().st_size > 1000:
                        results.append(f"screenshots/{png.name}")

            # If no screenshots, write error
            if not results:
                err = (r.stderr or r.stdout or "No output")[-800:]
                _write_status_png(shots_dir / "01_playwright_error.png",
                                  "PLAYWRIGHT FAILED", err, bg_color=(40, 10, 10))
                results.append("screenshots/01_playwright_error.png")

    except Exception as e:
        logger.error("Web screenshot pipeline failed: %s", e)
        _write_status_png(shots_dir / "01_web_error.png", "WEB PIPELINE FAILED",
                          str(e)[:500], bg_color=(40, 10, 10))
        results.append("screenshots/01_web_error.png")
    finally:
        if proc:
            try:
                import os
                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            if platform_type == "web-docker":
                subprocess.run(["docker", "rm", "-f", "qa-screenshot-app"],
                               capture_output=True, timeout=10)
    return results


def _discover_web_routes(ws: "Path") -> list[dict]:
    """Scan codebase to find web routes for screenshot journey."""
    import re
    routes = [{"path": "/", "label": "homepage", "actions": []}]
    seen = {"/"}

    # SvelteKit / Next.js file-based routes
    for routes_dir in [ws / "src" / "routes", ws / "app", ws / "pages"]:
        if routes_dir.exists():
            for f in sorted(routes_dir.rglob("*.{svelte,tsx,jsx,vue}")):
                rel = str(f.parent.relative_to(routes_dir)).replace("\\", "/")
                if rel == ".":
                    continue
                route = "/" + rel.replace("(", "").replace(")", "").replace("[", ":").replace("]", "")
                if route not in seen and "+page" in f.name or "index" in f.name or "page" in f.name:
                    label = rel.strip("/").replace("/", "_").replace("-", "_")
                    routes.append({"path": route, "label": label, "actions": []})
                    seen.add(route)

    # Express / FastAPI route decorators
    for ext in ("*.py", "*.ts", "*.js"):
        for f in ws.rglob(ext):
            if "node_modules" in str(f) or ".build" in str(f):
                continue
            try:
                code = f.read_text(errors="ignore")[:5000]
            except Exception:
                continue
            # Python: @app.get("/path") or @router.get("/path")
            for m in re.finditer(r'@(?:app|router)\.\w+\(["\'](/[^"\']*)["\']', code):
                path = m.group(1)
                if path not in seen and not re.search(r':\w+|{\w+}', path):
                    routes.append({"path": path, "label": path.strip("/").replace("/", "_") or "root", "actions": []})
                    seen.add(path)
            # Express: app.get('/path', ...)
            for m in re.finditer(r"(?:app|router)\.(?:get|post|use)\(['\"](/[^'\"]*)['\"]", code):
                path = m.group(1)
                if path not in seen and not re.search(r':\w+', path):
                    routes.append({"path": path, "label": path.strip("/").replace("/", "_") or "root", "actions": []})
                    seen.add(path)

    # HTML files as fallback
    for hf in sorted(ws.rglob("*.html"))[:10]:
        if "node_modules" in str(hf) or ".build" in str(hf):
            continue
        rel = str(hf.relative_to(ws))
        path = f"/{rel}"
        if path not in seen:
            routes.append({"path": path, "label": rel.replace("/", "_").replace(".html", ""), "actions": []})
            seen.add(path)

    # Discover forms/buttons for interaction steps
    for route in routes[:10]:
        _enrich_route_actions(ws, route)

    return routes[:15]


def _enrich_route_actions(ws: "Path", route: dict):
    """Detect interactive elements (forms, buttons, modals) in route files."""
    import re
    actions = []
    # Search for form elements, buttons, links in HTML/template files
    for ext in ("*.html", "*.svelte", "*.tsx", "*.jsx", "*.vue"):
        for f in ws.rglob(ext):
            if "node_modules" in str(f):
                continue
            try:
                code = f.read_text(errors="ignore")[:8000]
            except Exception:
                continue
            if route["path"] != "/" and route["label"] not in str(f).lower():
                continue
            # Forms
            if "<form" in code:
                actions.append({"type": "form", "selector": "form"})
            # Login patterns
            if 'type="password"' in code or 'type="email"' in code:
                actions.append({"type": "login", "selector": "form"})
            # Buttons with text
            for m in re.finditer(r'<button[^>]*>([^<]+)</button>', code):
                btn_text = m.group(1).strip()
                if len(btn_text) < 30:
                    actions.append({"type": "click", "selector": f"button:has-text('{btn_text}')"})
            # Navigation links
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', code):
                href, text = m.group(1), m.group(2).strip()
                if href.startswith("/") and len(text) < 30:
                    actions.append({"type": "navigate", "href": href, "text": text})
            break  # Only check first matching file
    route["actions"] = actions[:5]


def _discover_web_users(ws: "Path") -> list[dict]:
    """Scan codebase for auth/RBAC test users (env, fixtures, seed)."""
    import re
    users = []
    # Check for seed/fixture files
    for pattern in ("*seed*", "*fixture*", "*mock*", ".env*", "*test*"):
        for f in ws.glob(pattern):
            try:
                code = f.read_text(errors="ignore")[:3000]
            except Exception:
                continue
            # Look for user/password patterns
            for m in re.finditer(r'(?:email|user(?:name)?)\s*[:=]\s*["\']([^"\']+)["\']', code, re.I):
                email = m.group(1)
                pw_match = re.search(r'(?:password|pass|pwd)\s*[:=]\s*["\']([^"\']+)["\']', code[m.start():m.start()+200], re.I)
                if pw_match:
                    role = "user"
                    if "admin" in email.lower():
                        role = "admin"
                    elif "manager" in email.lower() or "lead" in email.lower():
                        role = "manager"
                    users.append({"email": email, "password": pw_match.group(1), "role": role})
    # Deduplicate
    seen = set()
    unique = []
    for u in users:
        if u["email"] not in seen:
            unique.append(u)
            seen.add(u["email"])
    return unique[:4]


def _build_playwright_journey(port: int, routes: list, users: list, shots_dir: str) -> str:
    """Generate a Playwright script that screenshots each route + interactions + RBAC."""
    base = f"http://localhost:{port}"

    # Build journey steps
    steps_js = ""
    step_num = 1

    # Per-user journeys (RBAC)
    if users:
        for user in users[:3]:
            role = user["role"]
            steps_js += f"""
    // --- RBAC Journey: {role} ({user['email']}) ---
    console.log('Journey: {role}');
    await page.goto('{base}/', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_00_before_login.png', fullPage: true }});
"""
            step_num += 1
            # Try login
            steps_js += f"""
    // Login attempt
    try {{
        const loginForm = await page.$('form');
        if (loginForm) {{
            const emailInput = await page.$('input[type="email"], input[name="email"], input[name="username"]');
            const pwInput = await page.$('input[type="password"]');
            if (emailInput && pwInput) {{
                await emailInput.fill('{user["email"]}');
                await pwInput.fill('{user["password"]}');
                await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_01_login_filled.png', fullPage: true }});
                await loginForm.$('button[type="submit"], button').then(b => b && b.click()).catch(() => {{}});
                await page.waitForTimeout(2000);
                await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_02_after_login.png', fullPage: true }});
            }}
        }}
    }} catch(e) {{ console.log('Login skip:', e.message); }}
"""
            step_num += 2
            # Visit each route as this user
            for route in routes[:5]:
                steps_js += f"""
    await page.goto('{base}{route["path"]}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_{route["label"]}.png', fullPage: true }});
"""
                step_num += 1
            # Clear session
            steps_js += f"""
    await context.clearCookies();
"""
    else:
        # No RBAC — anonymous journey through all routes
        for route in routes[:10]:
            label = route["label"]
            steps_js += f"""
    // Route: {route['path']}
    await page.goto('{base}{route["path"]}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}.png', fullPage: true }});
"""
            step_num += 1

            # Interactions on this page
            for action in route.get("actions", [])[:3]:
                if action["type"] == "click":
                    steps_js += f"""
    try {{
        const btn = await page.$('{action["selector"]}');
        if (btn) {{
            await btn.click();
            await page.waitForTimeout(1000);
            await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}_click.png', fullPage: true }});
        }}
    }} catch(e) {{}}
"""
                    step_num += 1
                elif action["type"] == "navigate":
                    steps_js += f"""
    await page.goto('{base}{action.get("href", "/")}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}_nav_{action.get("text", "link")[:10]}.png', fullPage: true }});
"""
                    step_num += 1

    # Viewport variants (mobile + desktop)
    steps_js += f"""
    // Mobile viewport
    await page.setViewportSize({{ width: 375, height: 812 }});
    await page.goto('{base}/', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_mobile_home.png', fullPage: true }});
"""
    step_num += 1

    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch();
    const context = await browser.newContext({{ viewport: {{ width: 1280, height: 720 }} }});
    const page = await context.newPage();
    const errors = [];
    page.on('console', msg => {{ if (msg.type() === 'error') errors.push(msg.text()); }});

    try {{
{steps_js}
    }} catch(e) {{
        console.error('Journey error:', e.message);
    }}

    // Console errors summary
    if (errors.length > 0) {{
        const fs = require('fs');
        fs.writeFileSync('{shots_dir}/console_errors.txt', errors.join('\\n'));
    }}

    await browser.close();
}})();
"""
    return script



def _write_status_png(path: "Path", title: str, body: str,
                      bg_color: tuple = (26, 17, 40), width: int = 800, height: int = 400):
    """Generate a status PNG with readable text using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        lines = body.split("\n")
        line_h = 16
        pad = 20
        title_h = 36
        img_w = max(width, 600)
        img_h = max(height, len(lines) * line_h + pad * 2 + title_h + 20)

        img = Image.new("RGB", (img_w, img_h), bg_color)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, img_w, title_h], fill=(37, 26, 53))
        draw.line([0, title_h, img_w, title_h], fill=(168, 85, 247), width=2)

        # Use default font (monospace-like)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)
            title_font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
        except Exception:
            font = ImageFont.load_default()
            title_font = font

        # Title text
        draw.text((pad, 8), title, fill=(255, 255, 255), font=title_font)

        # Body text
        y = title_h + pad
        for line in lines:
            # Truncate long lines
            if len(line) > 100:
                line = line[:97] + "..."
            color = (200, 200, 200)
            if "error" in line.lower() or "failed" in line.lower():
                color = (255, 100, 100)
            elif "warning" in line.lower():
                color = (255, 200, 80)
            elif "success" in line.lower() or "✅" in line:
                color = (100, 255, 100)
            draw.text((pad, y), line, fill=color, font=font)
            y += line_h
            if y > img_h - pad:
                draw.text((pad, y), "... (truncated)", fill=(150, 150, 150), font=font)
                break

        img.save(str(path), "PNG")
    except ImportError:
        # Fallback: minimal PNG without text
        import struct, zlib
        img_w, img_h = 400, 100
        raw = b""
        for y in range(img_h):
            raw += b"\x00" + bytes(bg_color) * img_w
        def _ch(ct, d):
            c = ct + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        ihdr = struct.pack(">IIBBBBB", img_w, img_h, 8, 2, 0, 0, 0)
        with open(str(path), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            f.write(_ch(b"IHDR", ihdr))
            f.write(_ch(b"IDAT", zlib.compress(raw)))
            f.write(_ch(b"IEND", b""))

    # Also write readable text
    path.with_suffix(".txt").write_text(f"=== {title} ===\n\n{body}")


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
