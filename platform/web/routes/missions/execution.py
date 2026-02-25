"""Mission execution routes."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ....i18n import t
from ...schemas import ErrorResponse, OkResponse
from ..helpers import _active_mission_tasks, _mission_semaphore, _parse_body, _templates

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/missions/{mission_id}/start", responses={200: {"model": OkResponse}})
async def start_mission(mission_id: str):
    """Activate a mission."""
    from ....missions.store import get_mission_store

    get_mission_store().update_mission_status(mission_id, "active")
    return JSONResponse({"ok": True})




@router.post(
    "/api/missions/{mission_id}/launch",
    responses={200: {"model": OkResponse}, 404: {"model": ErrorResponse}},
)
async def launch_mission_workflow(request: Request, mission_id: str):
    """Create a session from mission's workflow and redirect to live view."""
    from ....missions.store import get_mission_run_store, get_mission_store
    from ....models import MissionRun, MissionStatus, PhaseRun, PhaseStatus
    from ....sessions.store import MessageDef, SessionDef, get_session_store
    from ....workflows.store import get_workflow_store

    mission_store = get_mission_store()
    mission = mission_store.get_mission(mission_id)
    if not mission:
        return JSONResponse({"error": "Mission not found"}, status_code=404)

    wf_id = mission.workflow_id
    if not wf_id:
        # Pick a default workflow based on project type
        wf_id = "product-lifecycle"

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
    session_store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content=f'Workflow "{wf_id}" lancé pour la mission "{mission.name}". Goal: {mission.goal or "not specified"}',
        )
    )

    # Create workspace directory for agent tools (code, git, docker)
    import subprocess
    from pathlib import Path

    workspace_root = (
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "workspaces" / session.id
    )
    workspace_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(workspace_root), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "agents@macaron.ai"],
        cwd=str(workspace_root), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Macaron Agents"],
        cwd=str(workspace_root), capture_output=True,
    )
    readme = workspace_root / "README.md"
    task_desc = mission.goal or mission.description or mission.name
    readme.write_text(f"# {wf.name}\n\n{task_desc}\n\nMission ID: {mission_id}\n")
    gitignore = workspace_root / ".gitignore"
    gitignore.write_text("node_modules/\ndist/\nbuild/\n.env\n*.bak\n__pycache__/\n.DS_Store\n")
    subprocess.run(["git", "add", "."], cwd=str(workspace_root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit — mission workspace"],
        cwd=str(workspace_root), capture_output=True,
    )

    # Auto-start workflow execution — agents will dialogue via patterns
    import asyncio

    from ..workflows import _run_workflow_background

    # Auto-extract AO requirements from mission description for traceability
    if mission.description:
        try:
            from ....patterns.engine import _auto_extract_requirements

            _auto_extract_requirements(mission.description, mission_id)
        except Exception:
            pass

    # Create MissionRun with phases from workflow (for pipeline UI)
    phases = [
        PhaseRun(
            phase_id=wp.id,
            phase_name=wp.name,
            pattern_id=wp.pattern_id,
            status=PhaseStatus.PENDING,
        )
        for wp in wf.phases
    ]
    run = MissionRun(
        id=session.id,
        workflow_id=wf_id,
        workflow_name=wf.name,
        brief=task_desc,
        status=MissionStatus.RUNNING,
        phases=phases,
        project_id=mission.project_id or mission_id,
        session_id=session.id,
        parent_mission_id=mission_id,
        workspace_path=str(workspace_root),
    )
    try:
        get_mission_run_store().create(run)
    except Exception:
        pass

    asyncio.create_task(
        _run_workflow_background(wf, session.id, task_desc, mission.project_id or "")
    )

    return JSONResponse({"session_id": session.id, "workflow_id": wf_id})




@router.post("/api/missions/start")
async def api_mission_start(request: Request):
    """Create a mission run and start the CDP agent."""
    import uuid

    from ....agents.loop import get_loop_manager
    from ....missions.store import get_mission_run_store
    from ....models import MissionRun, MissionStatus, PhaseRun, PhaseStatus
    from ....sessions.store import MessageDef, SessionDef, get_session_store
    from ....workflows.store import get_workflow_store

    data = await _parse_body(request)
    workflow_id = str(data.get("workflow_id", ""))
    brief = str(data.get("brief", "")).strip()
    # Fix double-encoded UTF-8 (curl sends UTF-8 bytes interpreted as latin-1)
    try:
        brief = brief.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    project_id = str(data.get("project_id", ""))

    # WSJF components from form (SAFe prioritization)
    bv = float(data.get("business_value", 5))
    tc = float(data.get("time_criticality", 5))
    rr = float(data.get("risk_reduction", 3))
    jd = max(float(data.get("job_duration", 3)), 0.1)
    wsjf_score = round((bv + tc + rr) / jd, 1)

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    if not brief:
        return JSONResponse({"error": "Brief is required"}, status_code=400)

    # Build phase runs from workflow
    phases = []
    for wp in wf.phases:
        phases.append(
            PhaseRun(
                phase_id=wp.id,
                phase_name=wp.name,
                pattern_id=wp.pattern_id,
                status=PhaseStatus.PENDING,
            )
        )

    mission_id = uuid.uuid4().hex[:8]

    # Create workspace directory for agent tools (code, git, docker)
    import subprocess
    from pathlib import Path

    workspace_root = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "data"
        / "workspaces"
        / mission_id
    )
    workspace_root.mkdir(parents=True, exist_ok=True)
    # Init git repo + README with brief
    subprocess.run(["git", "init"], cwd=str(workspace_root), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "agents@macaron.ai"],
        cwd=str(workspace_root),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Macaron Agents"],
        cwd=str(workspace_root),
        capture_output=True,
    )
    readme = workspace_root / "README.md"
    readme.write_text(f"# {wf.name}\n\n{brief}\n\nMission ID: {mission_id}\n")
    # Add .gitignore to prevent node_modules/dist/build from being committed
    gitignore = workspace_root / ".gitignore"
    gitignore.write_text(
        "node_modules/\ndist/\nbuild/\n.env\n*.bak\n__pycache__/\n.DS_Store\n"
    )
    subprocess.run(["git", "add", "."], cwd=str(workspace_root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit — mission workspace"],
        cwd=str(workspace_root),
        capture_output=True,
    )
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

    # Create Epic record in missions table (SAFe backlog item) with WSJF
    try:
        from ....missions.store import MissionDef, get_mission_store

        epic = MissionDef(
            id=mission_id,
            project_id=project_id or mission_id,
            name=brief[:80] if brief else wf.name,
            description=brief,
            goal=brief,
            status="active",
            type="epic",
            workflow_id=workflow_id,
            wsjf_score=wsjf_score,
            created_by="user",
        )
        ms = get_mission_store()
        ms.create_mission(epic)
        # Store WSJF components
        from ....db.migrations import get_db as _gdb

        db = _gdb()
        try:
            db.execute(
                "UPDATE missions SET business_value=?, time_criticality=?, risk_reduction=?, job_duration=? WHERE id=?",
                (bv, tc, rr, jd, mission_id),
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not create epic record: %s", e)

    # Auto-provision TMA, Security, Debt missions for the project
    try:
        from ....projects.manager import Project, get_project_store

        _ps = get_project_store()
        if project_id and not _ps.get(project_id):
            _ps.create(
                Project(
                    id=project_id,
                    name=brief[:60] or wf.name,
                    path=workspace_path,
                    description=brief[:200],
                )
            )
        if project_id:
            _ps.auto_provision(project_id, brief[:60] or wf.name)
    except Exception as _prov_err:
        logger.warning("auto_provision failed for %s: %s", project_id, _prov_err)

    # Create a session for the orchestrator agent
    session_store = get_session_store()
    session_id = uuid.uuid4().hex[:8]
    session_store.create(
        SessionDef(
            id=session_id,
            name=f"Epic: {wf.name}",
            project_id=mission.project_id or None,
            status="active",
        )
    )
    # Update mission with session_id
    mission.session_id = session_id
    run_store.update(mission)

    # Send the brief as initial message
    session_store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            to_agent=orchestrator_id,
            message_type="instruction",
            content=brief,
        )
    )

    # Start the orchestrator agent loop with workspace path
    mgr = get_loop_manager()
    try:
        await mgr.start_agent(
            orchestrator_id, session_id, mission.project_id, workspace_path
        )
    except Exception as e:
        logger.error("Failed to start CDP agent: %s", e)

    # Auto-trigger orchestrator pipeline (no second API call needed)
    try:
        await _launch_orchestrator(mission_id)
        logger.warning("ORCH auto-launched for mission=%s", mission_id)
    except Exception as e:
        logger.error("Failed to auto-launch orchestrator: %s", e)

    return JSONResponse(
        {
            "mission_id": mission_id,
            "session_id": session_id,
            "redirect": f"/missions/{mission_id}/control",
        }
    )




@router.post("/api/missions/{mission_id}/chat/stream")
async def mission_chat_stream(request: Request, mission_id: str):
    """Stream a conversation with the CDP agent in mission context."""
    from ....agents.executor import get_executor
    from ....agents.store import get_agent_store
    from ....memory.manager import get_memory_manager
    from ....missions.store import get_mission_run_store
    from ....sessions.runner import _build_context
    from ....sessions.store import MessageDef, get_session_store

    data = await _parse_body(request)
    content = str(data.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return HTMLResponse("Mission not found", status_code=404)

    session_id = str(data.get("session_id", "")).strip() or mission.session_id
    sess_store = get_session_store()
    session = sess_store.get(session_id) if session_id else None
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    agent_store = get_agent_store()
    agent_id = str(data.get("agent_id", "")).strip() or "chef_de_programme"
    agent = agent_store.get(agent_id)
    if not agent:
        agent = agent_store.get("chef_de_programme")
    if not agent:
        agents = agent_store.list_all()
        agent = agents[0] if agents else None
    if not agent:
        return HTMLResponse("No agent", status_code=500)

    # Store user message
    sess_store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            to_agent=agent_id,
            message_type="text",
            content=content,
        )
    )

    # Build mission-specific context summary
    phase_summary = []
    if mission.phases:
        for p in mission.phases:
            phase_summary.append(
                f"- {p.phase_id}: {p.status.value if hasattr(p.status, 'value') else p.status}"
            )
    phases_str = "\n".join(phase_summary) if phase_summary else "No phases yet"

    # Gather memory
    mem_ctx = ""
    try:
        mem = get_memory_manager()
        entries = mem.project_get(mission_id, limit=20)
        if entries:
            mem_ctx = "\n".join(
                f"[{e['category']}] {e['key']}: {e['value'][:200]}" for e in entries
            )
    except Exception:
        pass

    # Gather recent agent messages from this session
    recent = sess_store.get_messages(session_id, limit=30)
    agent_msgs = []
    for m in recent:
        if m.from_agent not in ("user", "system") and m.content:
            agent_msgs.append(f"[{m.from_agent}] {m.content[:300]}")
    agent_conv = (
        "\n".join(agent_msgs[-10:]) if agent_msgs else "No agent conversations yet"
    )

    mission_context = f"""MISSION BRIEF: {mission.brief or "N/A"}
MISSION STATUS: {mission.status.value if hasattr(mission.status, "value") else mission.status}
WORKSPACE: {mission.workspace_path or "N/A"}

PHASES STATUS:
{phases_str}

PROJECT MEMORY (knowledge from agents):
{mem_ctx or "No memory entries yet"}

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
- git_log(cwd): View git history
- git_diff(cwd): View changes
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
    role_instruction = _role_instructions.get(
        agent_id,
        "\n\nTu peux LIRE et MODIFIER les fichiers du projet avec code_read, code_write, code_edit, git_commit, et sauvegarder des connaissances avec memory_store.",
    )
    mission_context += role_instruction

    async def event_generator():
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
                "platform_agents",
                "platform_missions",
                "platform_memory_search",
                "platform_metrics",
                "platform_sessions",
                "platform_workflows",
            ]
            base_tools = [
                "memory_search",
                "memory_store",
                "code_read",
                "code_search",
                "list_files",
                "git_log",
                "git_status",
                "git_diff",
                "get_project_context",
            ] + _platform_tools
            # CDP gets orchestration tools
            if agent_id in ("chef_de_programme", "chef_projet"):
                ctx.allowed_tools = base_tools + [
                    "get_phase_status",
                    "list_phases",
                    "run_phase",
                    "request_validation",
                ]
            else:
                # Dev/Archi/QA/Wiki agents get write tools
                ctx.allowed_tools = base_tools + [
                    "code_write",
                    "code_edit",
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

                    clean = _re.sub(r"<think>[\s\S]*?</think>\s*", "", raw_accumulated)
                    # If still inside an unclosed <think>, don't send yet
                    if (
                        "<think>" in clean
                        and "</think>" not in clean.split("<think>")[-1]
                    ):
                        clean = clean[: clean.rfind("<think>")]
                    clean = clean.strip()
                    # Send only newly revealed characters
                    if len(clean) > _sent_count:
                        new_text = clean[_sent_count:]
                        _sent_count = len(clean)
                        yield sse("chunk", {"text": new_text})
                elif evt == "tool":
                    # Tool being called — show in UI
                    tool_labels = {
                        "memory_search": t(
                            "tool_memory_search",
                            lang=getattr(request.state, "lang", "en"),
                        ),
                        "memory_store": "Sauvegarde mémoire",
                        "get_phase_status": "Statut des phases",
                        "list_phases": "Liste des phases",
                        "run_phase": "Lancement de phase",
                        "request_validation": "Demande de validation",
                        "code_read": "Lecture de code",
                        "code_write": "Écriture de code",
                        "code_edit": "Modification de code",
                        "code_search": t(
                            "tool_code_search",
                            lang=getattr(request.state, "lang", "en"),
                        ),
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
                    label = tool_labels.get(data_s, f'<svg class="icon icon-sm" style="vertical-align:middle"><use href="#icon-wrench"/></svg> {data_s}')
                    yield sse("tool", {"name": data_s, "label": label})
                elif evt == "result":
                    if hasattr(data_s, "error") and data_s.error:
                        llm_error = data_s.error
                    elif (
                        hasattr(data_s, "content")
                        and data_s.content
                        and not raw_accumulated
                    ):
                        raw_accumulated = data_s.content

            import re as _re

            accumulated = _re.sub(
                r"<think>[\s\S]*?</think>\s*", "", raw_accumulated
            ).strip()

            # If LLM failed and no real content, send error
            if llm_error and not accumulated:
                yield sse("error", {"message": f"LLM indisponible: {llm_error[:150]}"})
                return

            # Store agent response
            if accumulated:
                sess_store.add_message(
                    MessageDef(
                        session_id=session_id,
                        from_agent="chef_de_programme",
                        to_agent="user",
                        message_type="text",
                        content=accumulated,
                    )
                )

            rendered = (
                md_lib.markdown(
                    accumulated, extensions=["fenced_code", "tables", "nl2br"]
                )
                if accumulated
                else ""
            )
            yield sse("done", {"html": rendered})

        except Exception as exc:
            logger.exception("Mission chat stream error")
            yield sse("error", {"message": str(exc)[:200]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )




@router.post("/api/missions/{mission_id}/exec")
async def api_mission_exec(request: Request, mission_id: str):
    """Execute a command in the mission workspace. Returns JSON {stdout, stderr, returncode}."""
    import os as _os
    import subprocess as _sp

    from ....missions.store import get_mission_run_store

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
    build_keywords = (
        "xcodebuild",
        "xcodegen",
        "gradle",
        "cargo build",
        "npm run build",
        "docker build",
        "swift build",
    )
    if any(bk in cmd for bk in build_keywords):
        timeout = 300  # 5 minutes for builds

    try:
        result = _sp.run(
            cmd,
            shell=True,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**_os.environ, "TERM": "dumb"},
        )
        return JSONResponse(
            {
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
                "returncode": result.returncode,
                "command": cmd,
            }
        )
    except _sp.TimeoutExpired:
        return JSONResponse(
            {"error": f"Timeout ({timeout}s)", "command": cmd}, status_code=408
        )
    except Exception as e:
        return JSONResponse({"error": str(e), "command": cmd}, status_code=500)




@router.post("/api/missions/{mission_id}/validate")
async def api_mission_validate(request: Request, mission_id: str):
    """Human validates a checkpoint (GO/NOGO/PIVOT)."""
    from ....a2a.bus import get_bus
    from ....missions.store import get_mission_run_store
    from ....models import A2AMessage, MessageType, PhaseStatus
    from ....sessions.store import MessageDef, get_session_store

    data = await _parse_body(request)
    decision = str(data.get("decision", "GO")).upper()

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Update phase status
    updated_phase = False
    if mission.current_phase:
        for p in mission.phases:
            if p.phase_id == mission.current_phase and p.status in (
                PhaseStatus.WAITING_VALIDATION,
                "waiting_validation",
            ):
                p.status = PhaseStatus.DONE if decision == "GO" else PhaseStatus.FAILED
                updated_phase = True
        run_store.update(mission)
        # Belt-and-suspenders: also update via update_phase to ensure DB write
        if updated_phase:
            new_status = "done" if decision == "GO" else "failed"
            run_store.update_phase(mission.id, mission.current_phase, status=new_status)

    # Send decision to orchestrator agent via bus
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    if mission.session_id:
        session_store = get_session_store()
        session_store.add_message(
            MessageDef(
                session_id=mission.session_id,
                from_agent="user",
                to_agent=orch_id,
                message_type="response",
                content=f"DECISION: {decision}",
            )
        )
        # Also publish to bus for agent loop
        bus = get_bus()
        import uuid
        from datetime import datetime

        await bus.publish(
            A2AMessage(
                id=uuid.uuid4().hex[:8],
                session_id=mission.session_id,
                from_agent="user",
                to_agent=orch_id,
                message_type=MessageType.RESPONSE,
                content=f"DECISION: {decision}",
                timestamp=datetime.utcnow(),
            )
        )

    return JSONResponse({"decision": decision, "phase": mission.current_phase})




@router.post("/api/missions/{mission_id}/reset")
async def api_mission_reset(request: Request, mission_id: str):
    """Reset a mission: all phases back to pending, clear messages, ready to re-run."""
    from ....missions.store import get_mission_run_store
    from ....models import MissionStatus, PhaseStatus
    from ....sessions.runner import _push_sse
    from ....sessions.store import MessageDef, get_session_store

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Cancel any running asyncio task for this mission
    existing_task = _active_mission_tasks.pop(mission_id, None)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        logger.info("Cancelled running task for mission %s", mission_id)

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
        from ....db.migrations import get_db

        conn = get_db()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (mission.session_id,))
        conn.commit()
        conn.close()

        # Add reset marker
        store = get_session_store()
        store.add_message(
            MessageDef(
                session_id=mission.session_id,
                from_agent="system",
                to_agent="all",
                message_type="system",
                content="Epic réinitialisée — prête pour une nouvelle exécution.",
            )
        )

        # Notify frontend
        await _push_sse(
            mission.session_id,
            {
                "type": "mission_reset",
                "mission_id": mission_id,
            },
        )

    return JSONResponse({"status": "reset", "mission_id": mission_id})


# ── Confluence Sync ──────────────────────────────────────────




async def _launch_orchestrator(mission_id: str):
    """Shared helper: launch the MissionOrchestrator as an asyncio task."""
    import asyncio

    from ....agents.store import get_agent_store
    from ....missions.store import get_mission_run_store
    from ....models import MissionStatus
    from ....services.mission_orchestrator import MissionOrchestrator
    from ....sessions.runner import _push_sse
    from ....workflows.store import get_workflow_store

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        raise ValueError(f"Mission {mission_id} not found")

    existing_task = _active_mission_tasks.get(mission_id)
    if existing_task and not existing_task.done():
        return  # Already running

    wf = get_workflow_store().get(mission.workflow_id)
    if not wf:
        raise ValueError(f"Workflow {mission.workflow_id} not found")

    session_id = mission.session_id or ""
    agent_store = get_agent_store()
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    orch_agent = agent_store.get(orch_id)
    orch_name = orch_agent.name if orch_agent else "Orchestrateur"
    orch_role = orch_agent.role if orch_agent else "Orchestrateur"
    orch_avatar = f"/static/avatars/{orch_id}.svg"

    orchestrator = MissionOrchestrator(
        mission=mission,
        workflow=wf,
        run_store=run_store,
        agent_store=agent_store,
        session_id=session_id,
        orch_id=orch_id,
        orch_name=orch_name,
        orch_role=orch_role,
        orch_avatar=orch_avatar,
        push_sse=_push_sse,
    )

    async def _safe_run():
        try:
            async with _mission_semaphore:
                logger.warning(
                    "ORCH mission=%s acquired semaphore, starting", mission_id
                )
                await orchestrator.run_phases()
                logger.warning("ORCH mission=%s completed normally", mission_id)
        except Exception as exc:
            import traceback

            logger.error(
                "ORCH mission=%s CRASHED: %s\n%s",
                mission_id,
                exc,
                traceback.format_exc(),
            )
            try:
                mission.status = MissionStatus.FAILED
                run_store.update(mission)
                await _push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": orch_id,
                        "from_name": orch_name,
                        "from_role": orch_role,
                        "from_avatar": orch_avatar,
                        "content": f"Internal error: {exc}",
                        "msg_type": "text",
                    },
                )
            except Exception:
                pass

    mission.status = MissionStatus.RUNNING
    run_store.update(mission)

    task = asyncio.create_task(_safe_run())
    _active_mission_tasks[mission_id] = task
    task.add_done_callback(lambda t: _active_mission_tasks.pop(mission_id, None))




@router.post("/api/missions/{mission_id}/run")
async def api_mission_run(request: Request, mission_id: str):
    """Drive mission execution: CDP orchestrates phases sequentially.

    Uses the REAL pattern engine (run_pattern) for each phase — agents
    think with LLM, stream their responses, and interact per pattern type.
    """
    from ....missions.store import get_mission_run_store

    run_store = get_mission_run_store()
    mission = run_store.get(mission_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    existing_task = _active_mission_tasks.get(mission_id)
    if existing_task and not existing_task.done():
        return JSONResponse(
            {"status": "running", "mission_id": mission_id, "info": "already running"}
        )

    await _launch_orchestrator(mission_id)
    return JSONResponse({"status": "running", "mission_id": mission_id})



