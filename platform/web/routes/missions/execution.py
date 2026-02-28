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
from ..helpers import _active_mission_tasks, get_mission_semaphore, _parse_body
from .execution_helpers import build_mission_context, get_role_instruction

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
        Path(__file__).resolve().parent.parent.parent.parent
        / "data"
        / "workspaces"
        / session.id
    )
    workspace_root.mkdir(parents=True, exist_ok=True)
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
    task_desc = mission.goal or mission.description or mission.name
    readme.write_text(f"# {wf.name}\n\n{task_desc}\n\nMission ID: {mission_id}\n")
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

    # Auto-start workflow execution — agents will dialogue via patterns

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

    from ..helpers import _active_mission_tasks

    _wf_task = asyncio.create_task(
        _run_workflow_background(wf, session.id, task_desc, mission.project_id or "")
    )
    _active_mission_tasks[session.id] = _wf_task
    _wf_task.add_done_callback(lambda t: _active_mission_tasks.pop(session.id, None))

    # If mission config has milestones, also launch the milestone pipeline in parallel
    milestones = (mission.config or {}).get("milestones")
    if milestones and isinstance(milestones, list) and len(milestones) > 0:
        asyncio.create_task(
            _run_milestone_pipeline_background(
                milestones=milestones,
                session_id=session.id,
                mission_name=mission.name,
                project_path=str(workspace_root),
                lead_agent_id=mission.created_by or "brain",
                project_id=mission.project_id or "",
            )
        )

    return JSONResponse(
        {
            "session_id": session.id,
            "workflow_id": wf_id,
            "milestones": len(milestones) if milestones else 0,
        }
    )


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
    # Check if we should dispatch to a remote worker node
    dispatched = None
    try:
        from .dispatch import maybe_dispatch

        dispatched = await maybe_dispatch(mission_id, brief, project_id, workflow_id)
    except Exception as _de:
        logger.debug("Dispatch check failed (running locally): %s", _de)

    if dispatched:
        # Worker node took over — return coordinator response with remote info
        return JSONResponse(
            {
                "mission_id": mission_id,
                "session_id": session_id,
                "redirect": f"/missions/{mission_id}/control",
                "_dispatched_to": dispatched.get("_dispatched_to", ""),
            }
        )

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

    # Build mission-specific context summary and role instruction
    mission_context = build_mission_context(mission, session_id, sess_store)
    mission_context += get_role_instruction(agent_id)

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
                    label = tool_labels.get(
                        data_s,
                        f'<svg class="icon icon-sm" style="vertical-align:middle"><use href="#icon-wrench"/></svg> {data_s}',
                    )
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
            async with get_mission_semaphore():
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


async def _run_milestone_pipeline_background(
    *,
    milestones: list[dict],
    session_id: str,
    mission_name: str,
    project_path: str,
    lead_agent_id: str,
    project_id: str,
) -> None:
    """Launch the MilestoneRunner pipeline as a background task."""
    from ....agents.milestone_runner import run_milestone_pipeline
    from ....agents.executor import AgentExecutor, ExecutionContext
    from ....agents.store import get_agent_store
    from ....projects.registry import get_project_registry
    from ....projects.domains import load_domain

    try:
        agent_def = get_agent_store().get(lead_agent_id)
        if agent_def is None:
            agent_def = get_agent_store().get("brain")
        if agent_def is None:
            logger.warning(
                "MilestonePipeline: no agent found, skipping. session=%s", session_id
            )
            return

        # Resolve domain compliance agents
        compliance_agents: list[str] = []
        try:
            proj = get_project_registry().get(project_id)
            if proj and proj.arch_domain:
                domain = load_domain(proj.arch_domain)
                if domain and domain.compliance_agents:
                    compliance_agents = domain.compliance_agents
                    logger.info(
                        "MilestonePipeline: domain '%s' compliance_agents=%s session=%s",
                        proj.arch_domain,
                        compliance_agents,
                        session_id,
                    )
        except Exception as _e:
            logger.debug(
                "MilestonePipeline: could not load domain compliance agents: %s", _e
            )

        executor = AgentExecutor()
        ctx = ExecutionContext(
            agent=agent_def,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
            tools_enabled=True,
        )
        results = await run_milestone_pipeline(
            milestones,
            executor=executor,
            ctx=ctx,
            session_id=session_id,
            mission_name=mission_name,
            project_path=project_path,
            compliance_agents=compliance_agents or None,
        )
        done = sum(1 for r in results if r.success)
        logger.info(
            "MilestonePipeline done: %d/%d milestones passed session=%s",
            done,
            len(milestones),
            session_id,
        )
    except Exception as exc:
        logger.exception("MilestonePipeline error session=%s: %s", session_id, exc)


# ── Mission Debug & Replay ────────────────────────────────────────


@router.get("/api/missions/{run_id}/debug")
async def mission_debug(run_id: str):
    """Return debug info for a mission run: phases, llm_traces, cost breakdown."""
    from ....db.migrations import get_db

    conn = get_db()
    try:
        run = conn.execute(
            "SELECT * FROM mission_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run:
            return JSONResponse({"error": "Run not found"}, status_code=404)

        phases = (
            conn.execute(
                "SELECT * FROM phase_runs WHERE run_id=? ORDER BY started_at ASC",
                (run_id,),
            ).fetchall()
            if _table_exists(conn, "phase_runs")
            else []
        )

        traces = (
            conn.execute(
                "SELECT * FROM llm_traces WHERE mission_id=? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            if _table_exists(conn, "llm_traces")
            else []
        )

        traces_list = [dict(t) for t in traces]
        phases_list = [dict(p) for p in phases]

        return JSONResponse(
            {
                "run": dict(run),
                "phases": phases_list,
                "traces": traces_list,
                "total_traces": len(traces_list),
                "total_cost": sum((t.get("cost_usd") or 0) for t in traces_list),
                "total_tokens": sum((t.get("tokens_total") or 0) for t in traces_list),
            }
        )
    finally:
        conn.close()


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


@router.post("/api/missions/{run_id}/replay")
async def mission_replay(run_id: str, from_phase: int = 0):
    """Create a new mission run as replay of an existing one."""
    from ....db.migrations import get_db
    from ....missions.store import get_mission_run_store
    from ....models import MissionRun

    conn = get_db()
    try:
        run = conn.execute(
            "SELECT * FROM mission_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run:
            return JSONResponse({"error": "Run not found"}, status_code=404)
        run_dict = dict(run)
    finally:
        conn.close()

    # Build a new MissionRun from the original
    import json as _json
    from ....models import PhaseRun

    orig_phases_raw = _json.loads(run_dict.get("phases_json") or "[]")
    new_phases = [
        PhaseRun(
            phase_id=p.get("phase_id", ""),
            phase_name=p.get("phase_name", ""),
            pattern_id=p.get("pattern_id", ""),
        )
        for p in orig_phases_raw
    ]

    new_run = MissionRun(
        workflow_id=run_dict.get("workflow_id", ""),
        workflow_name=run_dict.get("workflow_name", ""),
        session_id=run_dict.get("session_id", ""),
        cdp_agent_id=run_dict.get("cdp_agent_id", ""),
        project_id=run_dict.get("project_id", ""),
        workspace_path=run_dict.get("workspace_path", ""),
        parent_mission_id=run_id,
        brief=run_dict.get("brief", ""),
        phases=new_phases,
    )

    mrs = get_mission_run_store()
    mrs.create(new_run)

    return JSONResponse(
        {"ok": True, "new_run_id": new_run.id, "from_phase": from_phase}
    )
