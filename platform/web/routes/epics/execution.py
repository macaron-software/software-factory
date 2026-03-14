"""Mission execution routes."""
# Ref: feat-mission-control, feat-workflows

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
from ..sse_utils import sse
from .execution_helpers import build_epic_context, get_role_instruction

router = APIRouter()
logger = logging.getLogger(__name__)


def _auto_create_planning_run(epic_id: str):
    """Auto-create a lightweight EpicRun when chatting with an epic that has no run.

    This allows API clients to chat with an epic immediately after creating it,
    without needing to launch a full workflow first.
    """
    from ....epics.store import get_epic_run_store, get_epic_store
    from ....models import EpicRun, EpicStatus
    from ....sessions.store import SessionDef, get_session_store

    epic_store = get_epic_store()
    epic_def = epic_store.get(epic_id)
    if not epic_def:
        return None

    # Create a session for this planning run
    sess_store = get_session_store()
    session = SessionDef(
        name=f"Epic planning: {epic_def.name}",
        epic_id=epic_id,
    )
    sess_store.create(session)

    # Create a lightweight run (no workflow, just for chat)
    run = EpicRun(
        id=epic_id,
        workflow_id="",
        workflow_name="planning",
        session_id=session.id,
        project_id=epic_def.project_id,
        status=EpicStatus.RUNNING,
        brief=epic_def.description or epic_def.goal or epic_def.name,
    )
    run_store = get_epic_run_store()
    run_store.save(run)
    logger.info("Auto-created planning run for epic %s", epic_id)
    return run


@router.post("/api/epics/{epic_id}/start", responses={200: {"model": OkResponse}})
@router.post("/api/missions/{epic_id}/start", responses={200: {"model": OkResponse}})
async def start_mission(epic_id: str):
    """Activate a mission."""
    from ....epics.store import get_epic_store

    get_epic_store().update_mission_status(epic_id, "active")
    return JSONResponse({"ok": True})


@router.post(
    "/api/missions/{epic_id}/launch",
    responses={200: {"model": OkResponse}, 404: {"model": ErrorResponse}},
)
async def launch_mission_workflow(request: Request, epic_id: str):
    """Create a session from mission's workflow and redirect to live view."""
    from ....epics.store import get_epic_run_store, get_epic_store
    from ....models import EpicRun, EpicStatus, PhaseRun, PhaseStatus
    from ....sessions.store import MessageDef, SessionDef, get_session_store
    from ....workflows.store import get_workflow_store

    epic_store = get_epic_store()
    mission = epic_store.get_mission(epic_id)
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
            "mission_id": epic_id,
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

    from ....config import DATA_DIR

    workspace_root = DATA_DIR / "workspaces" / session.id
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
    readme.write_text(f"# {wf.name}\n\n{task_desc}\n\nMission ID: {epic_id}\n")
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

            _auto_extract_requirements(mission.description, epic_id)
        except Exception:
            pass

    # Create EpicRun with phases from workflow (for pipeline UI)
    phases = [
        PhaseRun(
            phase_id=wp.id,
            phase_name=wp.name,
            pattern_id=wp.pattern_id,
            status=PhaseStatus.PENDING,
        )
        for wp in wf.phases
    ]
    run = EpicRun(
        id=session.id,
        workflow_id=wf_id,
        workflow_name=wf.name,
        brief=task_desc,
        status=EpicStatus.PENDING,
        phases=phases,
        project_id=mission.project_id or epic_id,
        session_id=session.id,
        parent_epic_id=epic_id,
        workspace_path=str(workspace_root),
    )
    try:
        get_epic_run_store().create(run)
    except Exception:
        pass

    # Register project in project store with workspace path so tools_enabled works
    _proj_id = mission.project_id or epic_id
    try:
        from ....projects.manager import Project, get_project_store

        _p_store = get_project_store()
        _existing = _p_store.get(_proj_id)
        if _existing:
            _existing.path = str(workspace_root)
            _p_store.update(_existing)
        else:
            _p_store.create(
                Project(id=_proj_id, name=mission.name, path=str(workspace_root))
            )
    except Exception as _e:
        logger.warning("Could not register project workspace for %s: %s", _proj_id, _e)

    async def _guarded_workflow():
        async with get_mission_semaphore():
            await _run_workflow_background(wf, session.id, task_desc, _proj_id)

    _wf_task = asyncio.create_task(_guarded_workflow())
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


@router.post("/api/epics/start")
@router.post("/api/missions/start")
async def api_mission_start(request: Request):
    """Create a mission run and start the CDP agent."""
    import uuid

    from ....agents.loop import get_loop_manager
    from ....epics.store import get_epic_run_store
    from ....models import EpicRun, EpicStatus, PhaseRun, PhaseStatus
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

    # Stack detection: Rust/game projects → rust-game-sprint
    _brief_lower = (brief or "").lower()
    _rust_keywords = {"rust", "macroquad", "cargo", "game", "arcade", "platformer", "shooter"}
    if len(_rust_keywords & set(_brief_lower.split())) >= 2:
        workflow_id = workflow_id or "rust-game-sprint"

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    if not brief:
        return JSONResponse({"error": "Brief is required"}, status_code=400)

    # Auto-inject domain default_pattern + default_agents into workflow phases when applicable
    try:
        from ....projects.registry import get_project_registry
        from ....projects.domains import load_domain

        _proj = get_project_registry().get(project_id) if project_id else None
        if _proj and getattr(_proj, "arch_domain", ""):
            _dom = load_domain(_proj.arch_domain)
            if _dom and _dom.default_pattern:
                # Override pattern_id on all phases that use a generic pattern
                for wp in wf.phases:
                    if not wp.pattern_id or wp.pattern_id in (
                        "solo-chat",
                        "sequential",
                    ):
                        wp.pattern_id = _dom.default_pattern
                logger.info(
                    "MissionCreate: domain '%s' default_pattern='%s' applied to workflow '%s'",
                    _proj.arch_domain,
                    _dom.default_pattern,
                    workflow_id,
                )
            if _dom and _dom.default_agents:
                # Inject domain default agents into phase agent_ids if not already set
                for wp in wf.phases:
                    if not getattr(wp, "agent_ids", None):
                        wp.agent_ids = list(_dom.default_agents)
                logger.info(
                    "MissionCreate: domain '%s' default_agents=%s applied to workflow '%s'",
                    _proj.arch_domain,
                    _dom.default_agents,
                    workflow_id,
                )
    except Exception as _de:
        logger.debug("MissionCreate: could not apply domain defaults: %s", _de)

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

    epic_id = uuid.uuid4().hex[:8]

    # Create workspace directory for agent tools (code, git, docker)
    import subprocess

    from ....config import DATA_DIR

    workspace_root = DATA_DIR / "workspaces" / epic_id
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
    readme.write_text(f"# {wf.name}\n\n{brief}\n\nMission ID: {epic_id}\n")
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

    mission = EpicRun(
        id=epic_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief,
        status=EpicStatus.RUNNING,
        phases=phases,
        project_id=project_id or epic_id,
        workspace_path=workspace_path,
        cdp_agent_id=orchestrator_id,
    )

    run_store = get_epic_run_store()
    run_store.create(mission)

    # Create Epic record in missions table (SAFe backlog item) with WSJF
    try:
        from ....epics.store import MissionDef, get_epic_store

        epic = MissionDef(
            id=epic_id,
            project_id=project_id or epic_id,
            name=brief[:80] if brief else wf.name,
            description=brief,
            goal=brief,
            status="active",
            type="epic",
            workflow_id=workflow_id,
            wsjf_score=wsjf_score,
            created_by="user",
        )
        ms = get_epic_store()
        ms.create_mission(epic)
        # Store WSJF components
        from ....db.migrations import get_db as _gdb

        db = _gdb()
        try:
            db.execute(
                "UPDATE epics SET business_value=?, time_criticality=?, risk_reduction=?, job_duration=? WHERE id=?",
                (bv, tc, rr, jd, epic_id),
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
        if project_id and not project_id.startswith("marathon-"):
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

        dispatched = await maybe_dispatch(epic_id, brief, project_id, workflow_id)
    except Exception as _de:
        logger.debug("Dispatch check failed (running locally): %s", _de)

    if dispatched:
        # Worker node took over — return coordinator response with remote info
        return JSONResponse(
            {
                "mission_id": epic_id,
                "session_id": session_id,
                "redirect": f"/missions/{epic_id}/control",
                "_dispatched_to": dispatched.get("_dispatched_to", ""),
            }
        )

    try:
        await _launch_orchestrator(epic_id)
        logger.warning("ORCH auto-launched for mission=%s", epic_id)
    except Exception as e:
        logger.error("Failed to auto-launch orchestrator: %s", e)

    return JSONResponse(
        {
            "mission_id": epic_id,
            "session_id": session_id,
            "redirect": f"/missions/{epic_id}/control",
        }
    )


@router.post("/api/epics/{epic_id}/chat/stream")
@router.post("/api/missions/{epic_id}/chat/stream")
async def mission_chat_stream(request: Request, epic_id: str):
    """Stream a conversation with the CDP agent in mission context."""
    from ....agents.executor import get_executor
    from ....agents.store import get_agent_store
    from ....epics.store import get_epic_run_store
    from ....sessions.runner import _build_context
    from ....sessions.store import MessageDef, get_session_store

    data = await _parse_body(request)
    content = str(data.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    run_store = get_epic_run_store()
    mission = run_store.get(epic_id)
    if not mission:
        # Auto-create a planning run from epic definition
        mission = _auto_create_planning_run(epic_id)
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
    epic_context = build_epic_context(mission, session_id, sess_store)
    epic_context += get_role_instruction(agent_id)

    async def event_generator():
        import markdown as md_lib

        yield sse("status", {"label": "Analyse en cours..."})

        try:
            ctx = await _build_context(agent, session)
            # Inject mission context into project_context
            ctx.project_context = epic_context + "\n\n" + (ctx.project_context or "")
            if mission.workspace_path:
                ctx.project_path = mission.workspace_path
            ctx.epic_run_id = epic_id
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


@router.post("/api/epics/{epic_id}/exec")
@router.post("/api/missions/{epic_id}/exec")
async def api_mission_exec(request: Request, epic_id: str):
    """Execute a command in the mission workspace. Returns JSON {stdout, stderr, returncode}."""
    import os as _os
    import subprocess as _sp

    from ....auth.middleware import get_current_user as _get_current_user

    user = await _get_current_user(request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    from ....epics.store import get_epic_run_store

    store = get_epic_run_store()
    mission = store.get(epic_id)
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


@router.post("/api/epics/{epic_id}/validate")
@router.post("/api/missions/{epic_id}/validate")
async def api_mission_validate(request: Request, epic_id: str):
    """Human validates a checkpoint (GO/NOGO/PIVOT)."""
    from ....a2a.bus import get_bus
    from ....epics.store import get_epic_run_store
    from ....models import A2AMessage, MessageType, PhaseStatus
    from ....sessions.store import MessageDef, get_session_store

    data = await _parse_body(request)
    decision = str(data.get("decision", "GO")).upper()

    run_store = get_epic_run_store()
    mission = run_store.get(epic_id)
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


@router.post("/api/epics/{epic_id}/reset")
@router.post("/api/missions/{epic_id}/reset")
async def api_mission_reset(request: Request, epic_id: str):
    """Reset a mission: all phases back to pending, clear messages, ready to re-run."""
    from ....epics.store import get_epic_run_store
    from ....models import EpicStatus, PhaseStatus
    from ....sessions.runner import _push_sse
    from ....sessions.store import MessageDef, get_session_store

    run_store = get_epic_run_store()
    mission = run_store.get(epic_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Cancel any running asyncio task for this mission
    existing_task = _active_mission_tasks.pop(epic_id, None)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        logger.info("Cancelled running task for mission %s", epic_id)

    # Reset all phases to pending
    for p in mission.phases:
        p.status = PhaseStatus.PENDING
        p.started_at = None
        p.completed_at = None
        p.summary = ""
        p.agent_count = 0

    mission.status = EpicStatus.RUNNING
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
                "mission_id": epic_id,
            },
        )

    return JSONResponse({"status": "reset", "mission_id": epic_id})


# ── Confluence Sync ──────────────────────────────────────────


async def _launch_orchestrator(epic_id: str):
    """Shared helper: launch the EpicOrchestrator as an asyncio task."""

    from ....agents.store import get_agent_store
    from ....epics.store import get_epic_run_store
    from ....models import EpicStatus
    from ....services.epic_orchestrator import EpicOrchestrator
    from ....sessions.runner import _push_sse
    from ....workflows.store import get_workflow_store

    run_store = get_epic_run_store()
    mission = run_store.get(epic_id)
    if not mission:
        raise ValueError(f"Mission {epic_id} not found")

    existing_task = _active_mission_tasks.get(epic_id)
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

    orchestrator = EpicOrchestrator(
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
                logger.warning("ORCH mission=%s acquired semaphore, starting", epic_id)
                await orchestrator.run_phases()
                logger.warning("ORCH mission=%s completed normally", epic_id)
                project_path = getattr(mission, "workspace_path", None)
                if project_path:
                    asyncio.create_task(
                        _run_quality_scan_background(
                            epic_id,
                            getattr(mission, "project_id", "") or "",
                            project_path,
                            session_id,
                        )
                    )
                # Push browser notification on completion
                try:
                    from ....services.push import send_push_to_project

                    _pid = getattr(mission, "project_id", "") or ""
                    _mname = getattr(mission, "name", epic_id) or epic_id
                    _wname = getattr(wf, "name", "") or ""
                    asyncio.create_task(
                        send_push_to_project(
                            _pid,
                            f"✅ Mission completed: {_mname}",
                            f"Workflow: {_wname}"
                            if _wname
                            else "Mission finished successfully",
                            url=f"/projects/{_pid}/workspace" if _pid else "/",
                        )
                    )
                except Exception:
                    pass
        except Exception as exc:
            import traceback

            logger.error(
                "ORCH mission=%s CRASHED: %s\n%s",
                epic_id,
                exc,
                traceback.format_exc(),
            )
            try:
                mission.status = EpicStatus.FAILED
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
                # Push browser notification on failure
                try:
                    from ....services.push import send_push_to_project

                    _pid = getattr(mission, "project_id", "") or ""
                    _mname = getattr(mission, "name", epic_id) or epic_id
                    _wname = getattr(wf, "name", "") or ""
                    asyncio.create_task(
                        send_push_to_project(
                            _pid,
                            f"❌ Mission failed: {_mname}",
                            f"Workflow: {_wname}"
                            if _wname
                            else "Mission encountered an error",
                            url=f"/projects/{_pid}/workspace" if _pid else "/",
                        )
                    )
                except Exception:
                    pass
            except Exception:
                pass

    mission.status = EpicStatus.RUNNING
    run_store.update(mission)

    task = asyncio.create_task(_safe_run())
    _active_mission_tasks[epic_id] = task
    task.add_done_callback(lambda t: _active_mission_tasks.pop(epic_id, None))


@router.post("/api/epics/{epic_id}/run")
@router.post("/api/missions/{epic_id}/run")
async def api_epic_run(request: Request, epic_id: str):
    """Drive mission execution: CDP orchestrates phases sequentially.

    Uses the REAL pattern engine (run_pattern) for each phase — agents
    think with LLM, stream their responses, and interact per pattern type.

    Smart resume: phases already DONE are skipped; only FAILED/PENDING phases
    are re-executed. This allows re-running a completed/failed run without
    restarting from ideation.
    """
    from ....epics.store import get_epic_run_store
    from ....models import PhaseStatus

    run_store = get_epic_run_store()
    mission = run_store.get(epic_id)
    if not mission:
        return JSONResponse({"error": "Not found"}, status_code=404)

    existing_task = _active_mission_tasks.get(epic_id)
    if existing_task and not existing_task.done():
        return JSONResponse(
            {"status": "running", "mission_id": epic_id, "info": "already running"}
        )

    # Reset FAILED phases → PENDING so they are re-executed.
    # DONE/DONE_WITH_ISSUES phases stay as-is and will be skipped by the orchestrator.
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    from_phase: int = int(body.get("from_phase", -1))

    reset_count = 0
    for idx, phase in enumerate(mission.phases):
        if from_phase >= 0 and idx >= from_phase:
            # Hard reset from a specific phase index
            phase.status = PhaseStatus.PENDING
            reset_count += 1
        elif phase.status == PhaseStatus.FAILED:
            phase.status = PhaseStatus.PENDING
            reset_count += 1

    # Also reset the run status itself so the orchestrator picks it up
    if mission.status in ("completed", "failed", "paused"):
        mission.status = "running"
        run_store.update(mission)
    elif reset_count:
        run_store.update(mission)

    await _launch_orchestrator(epic_id)
    return JSONResponse(
        {"status": "running", "mission_id": epic_id, "phases_reset": reset_count}
    )


@router.post("/api/epics/{epic_id}/resume")
@router.post("/api/missions/{epic_id}/resume")
async def api_mission_resume(request: Request, epic_id: str):
    """Resume a mission from a specific phase. Reuses existing workspace and session.

    Body params:
        phase: str | int — phase_id (e.g. "dev-sprint") or phase index (0-based)
        reset_only: bool — if true, only reset the phase without launching (default: false)

    Behavior:
        - Finds the latest epic_run for this mission
        - Resets the target phase + all subsequent phases to PENDING
        - Marks completed phases before the target as DONE
        - Resumes orchestration from the target phase
    """
    from ....epics.store import get_epic_run_store, get_epic_store
    from ....models import EpicStatus, PhaseStatus

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    phase_target = body.get("phase", body.get("from_phase"))
    reset_only = body.get("reset_only", False)

    # Find the latest epic_run for this mission (by parent_epic_id)
    run_store = get_epic_run_store()

    # Try direct lookup first (epic_id might be the run_id)
    run = run_store.get(epic_id)
    if not run:
        # Search by parent_epic_id (mission_id → run)
        try:
            from ....db.migrations import get_db
            db = get_db()
            rows = db.execute(
                "SELECT id FROM epic_runs WHERE parent_epic_id = ? ORDER BY created_at DESC LIMIT 1",
                (epic_id,),
            ).fetchall()
            if rows:
                run = run_store.get(rows[0][0] if isinstance(rows[0], (tuple, list)) else rows[0]["id"])
            db.close()
        except Exception:
            pass

    if not run:
        return JSONResponse({"error": "No run found for this mission"}, status_code=404)

    # Resolve phase target to index
    target_idx = -1
    if phase_target is not None:
        if isinstance(phase_target, int) or (isinstance(phase_target, str) and phase_target.isdigit()):
            target_idx = int(phase_target)
        else:
            # Match by phase_id
            for idx, p in enumerate(run.phases):
                if p.phase_id == phase_target:
                    target_idx = idx
                    break

    if target_idx < 0 or target_idx >= len(run.phases):
        phase_list = [f"  {i}: {p.phase_id} ({p.status})" for i, p in enumerate(run.phases)]
        return JSONResponse({
            "error": f"Phase '{phase_target}' not found",
            "available_phases": phase_list,
        }, status_code=400)

    # Reset target + subsequent phases → PENDING, mark prior as done
    reset_count = 0
    for idx, p in enumerate(run.phases):
        if idx < target_idx:
            _st = p.status.value if hasattr(p.status, 'value') else str(p.status)
            if _st in ("pending", "running"):
                p.status = PhaseStatus.DONE
        elif idx >= target_idx:
            p.status = PhaseStatus.PENDING
            reset_count += 1

    # Update run status
    if run.status in ("completed", "failed", "paused", "gated", "escalated"):
        run.status = EpicStatus.RUNNING
    run_store.update(run)

    # Update session checkpoint
    try:
        from ....sessions.store import get_session_store
        sess_store = get_session_store()
        sess = sess_store.get(run.session_id)
        if sess:
            config = sess.config or {}
            config["workflow_checkpoint"] = target_idx
            sess_store.update_config(run.session_id, config)
    except Exception:
        pass

    result = {
        "status": "reset" if reset_only else "running",
        "run_id": run.id,
        "session_id": run.session_id,
        "from_phase": target_idx,
        "phase_id": run.phases[target_idx].phase_id,
        "phase_name": run.phases[target_idx].phase_name,
        "phases_reset": reset_count,
    }

    if not reset_only:
        await _launch_orchestrator(run.id)

    return JSONResponse(result)


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
        compliance_blocking: bool = False
        try:
            proj = get_project_registry().get(project_id)
            if proj and proj.arch_domain:
                domain = load_domain(proj.arch_domain)
                if domain and domain.compliance_agents:
                    compliance_agents = domain.compliance_agents
                    compliance_blocking = domain.compliance_blocking
                    logger.info(
                        "MilestonePipeline: domain '%s' compliance_agents=%s blocking=%s session=%s",
                        proj.arch_domain,
                        compliance_agents,
                        compliance_blocking,
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
            compliance_blocking=compliance_blocking,
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


# ── Quality Scan ─────────────────────────────────────────────────


async def _run_quality_scan_background(
    epic_id: str,
    project_id: str,
    project_path: str,
    session_id: str,
) -> None:
    """Run code-critic quality scan after mission completion (non-blocking)."""
    import re
    from ....agents.executor import AgentExecutor, ExecutionContext
    from ....agents.store import get_agent_store
    from ....db.migrations import get_db

    try:
        agent_store = get_agent_store()
        critic = agent_store.get("code-critic") or agent_store.get("code_critic")
        if critic is None:
            logger.info(
                "QualityScan: no code-critic agent found, skipping mission=%s",
                epic_id,
            )
            return

        executor = AgentExecutor()
        ctx = ExecutionContext(
            agent=critic,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
            tools_enabled=True,
        )
        prompt = (
            "Review the code produced in the recent mission. "
            "Check for: SLOP, dead code, missing tests, security issues. "
            "Provide a quality score 0-100 and list of findings."
        )
        result = await executor.run(ctx, prompt)

        # Parse quality score from result
        score: int | None = None
        if result and result.content:
            m = re.search(r"\b(\d{1,3})\s*/\s*100\b", result.content)
            if not m:
                m = re.search(r"[Ss]core[:\s]+(\d{1,3})", result.content)
            if m:
                score = int(m.group(1))

        # Write to quality_reports table
        try:
            conn = get_db()
            conn.execute(
                """INSERT INTO quality_reports
                   (project_id, mission_id, session_id, phase_name, dimension, score, details_json, tool_used, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    project_id,
                    epic_id,
                    session_id,
                    "mission_completion",
                    "overall",
                    score,
                    json.dumps({"content": result.content if result else ""})
                    if result
                    else "{}",
                    "code-critic",
                ),
            )
            conn.commit()
        except Exception as db_err:
            logger.warning(
                "QualityScan: DB write failed mission=%s: %s", epic_id, db_err
            )

        logger.info(
            "QualityScan: mission=%s score=%s",
            epic_id,
            score if score is not None else "n/a",
        )
    except Exception as exc:
        logger.warning("QualityScan: failed mission=%s: %s", epic_id, exc)


# ── Mission Debug & Replay ────────────────────────────────────────


@router.get("/api/missions/{run_id}/skills-audit")
@router.get("/api/epics/{run_id}/skills-audit")
async def mission_skills_audit(run_id: str):
    """Return per-phase skill injection audit for a mission run.

    Shows which skills were injected at each phase, useful for verifying
    that design-system-components, ux-laws, etc. are active during UX phases.

    Returns:
        {
          "run_id": "...",
          "phases": [
            {
              "phase_id": "ux-design-review",
              "phase_name": "UX Design Review",
              "status": "done",
              "injected_skills": ["ux-laws", "design-system-components", "ux-best-practices"]
            }, ...
          ],
          "skill_coverage": {           # which skills appeared at least once
            "ux-laws": ["ux-design-review"],
            "design-system-components": ["ux-design-review", "tdd-sprint"]
          },
          "phases_without_skills": ["env-setup"]   # phases where nothing was injected
        }
    """
    from ....epics.store import get_epic_run_store

    run = get_epic_run_store().get(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    phases_out = []
    skill_coverage: dict[str, list[str]] = {}
    phases_without_skills: list[str] = []

    for p in run.phases:
        entry = {
            "phase_id": p.phase_id,
            "phase_name": p.phase_name or p.phase_id,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "injected_skills": p.injected_skills or [],
        }
        phases_out.append(entry)

        if p.injected_skills:
            for sk in p.injected_skills:
                skill_coverage.setdefault(sk, []).append(p.phase_id)
        else:
            phases_without_skills.append(p.phase_id)

    return JSONResponse({
        "run_id": run_id,
        "phases": phases_out,
        "skill_coverage": skill_coverage,
        "phases_without_skills": phases_without_skills,
        "total_phases": len(run.phases),
        "phases_with_skills": len(run.phases) - len(phases_without_skills),
    })



    """Return debug info for a mission run: phases, llm_traces, cost breakdown."""
    from ....db.migrations import get_db

    conn = get_db()
    try:
        run = conn.execute("SELECT * FROM epic_runs WHERE id=?", (run_id,)).fetchone()
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
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
        (table,),
    ).fetchone()
    return bool(row)


@router.post("/api/epics/{run_id}/replay")
@router.post("/api/missions/{run_id}/replay")
async def mission_replay(run_id: str, from_phase: int = 0):
    """Create a new mission run as replay of an existing one."""
    from ....db.migrations import get_db
    from ....epics.store import get_epic_run_store
    from ....models import EpicRun

    conn = get_db()
    try:
        run = conn.execute("SELECT * FROM epic_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            return JSONResponse({"error": "Run not found"}, status_code=404)
        run_dict = dict(run)
    finally:
        conn.close()

    # Build a new EpicRun from the original
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

    new_run = EpicRun(
        workflow_id=run_dict.get("workflow_id", ""),
        workflow_name=run_dict.get("workflow_name", ""),
        session_id=run_dict.get("session_id", ""),
        cdp_agent_id=run_dict.get("cdp_agent_id", ""),
        project_id=run_dict.get("project_id", ""),
        workspace_path=run_dict.get("workspace_path", ""),
        parent_epic_id=run_id,
        brief=run_dict.get("brief", ""),
        phases=new_phases,
    )

    mrs = get_epic_run_store()
    mrs.create(new_run)

    return JSONResponse(
        {"ok": True, "new_run_id": new_run.id, "from_phase": from_phase}
    )


# ── Worker node: resume endpoint (used by multi-node dispatch) ────────────


@router.post("/api/missions/runs/{run_id}/resume")
async def worker_resume_run(run_id: str):
    """Trigger local execution of a run dispatched from another node.

    Called by auto_resume._try_dispatch_to_worker when this node is the
    least-loaded worker. Equivalent to /api/missions/{id}/run but targeted
    by run_id rather than epic_id and always resumes (no body required).
    """
    from ....epics.store import get_epic_run_store
    from ....services.auto_resume import _launch_run

    run_store = get_epic_run_store()
    if not run_store.get(run_id):
        return JSONResponse({"error": "Run not found"}, status_code=404)

    existing = _active_mission_tasks.get(run_id)
    if existing and not existing.done():
        return JSONResponse({"status": "already_running", "run_id": run_id})

    try:
        await _launch_run(run_id)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"status": "launched", "run_id": run_id}, status_code=202)


# ── Resume at specific phase ──────────────────────────────────────────


@router.post("/api/missions/runs/{run_id}/resume-at-phase")
async def resume_run_at_phase(run_id: str, request: Request):
    """Reset a phase (or all phases from it) and resume from there.

    Body JSON:
      phase_id   (str)  – target phase to reset and resume from
      reset_from (bool) – if true, also reset all phases AFTER phase_id (default: false)

    Behaviour:
      - target phase → status=pending, cleared timestamps/summary/error
      - if reset_from=true: same for every phase after the target
      - run.current_phase = phase_id
      - run.status = paused  (auto_resume picks it up next cycle)
    """
    from ....epics.store import get_epic_run_store
    from ....models import EpicStatus, PhaseStatus

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    phase_id: str = body.get("phase_id", "")
    reset_from: bool = bool(body.get("reset_from", False))

    if not phase_id:
        return JSONResponse({"error": "phase_id required"}, status_code=400)

    store = get_epic_run_store()
    run = store.get(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    # Safety: refuse to mutate an actively running run
    if run.status == EpicStatus.RUNNING:
        # Check if it's actually in-flight (task exists and is alive)
        existing = _active_mission_tasks.get(run_id)
        if existing and not existing.done():
            return JSONResponse(
                {"error": "Run is currently executing — cancel it first"},
                status_code=409,
            )

    # Find target phase index
    target_idx = next(
        (i for i, p in enumerate(run.phases) if p.phase_id == phase_id), None
    )
    if target_idx is None:
        available = [p.phase_id for p in run.phases]
        return JSONResponse(
            {"error": f"Phase '{phase_id}' not found. Available: {available}"},
            status_code=404,
        )

    # Reset phases
    phases_to_reset = (
        run.phases[target_idx:]          # target + everything after
        if reset_from
        else [run.phases[target_idx]]    # target only
    )
    for p in phases_to_reset:
        p.status = PhaseStatus.PENDING
        p.started_at = None
        p.completed_at = None
        p.summary = ""
        p.error = ""
        p.iteration = 0
        p.sprint_count = 0

    run.current_phase = phase_id
    run.status = EpicStatus.PAUSED
    run.completed_at = None

    store.update(run)

    reset_ids = [p.phase_id for p in phases_to_reset]
    return JSONResponse(
        {
            "status": "ok",
            "run_id": run_id,
            "resume_from": phase_id,
            "reset_phases": reset_ids,
            "reset_from": reset_from,
            "message": f"Run paused at phase '{phase_id}' — will resume on next auto_resume cycle",
        }
    )


# ── Compliance Reports ────────────────────────────────────────────────


@router.get("/api/epics/{run_id}/compliance-reports")
@router.get("/api/missions/{run_id}/compliance-reports")
async def get_compliance_reports(run_id: str):
    """Get all compliance verdicts for a mission run."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        # Ensure table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS compliance_verdicts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                milestone_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                goal TEXT,
                verdict TEXT NOT NULL,
                is_blocking INTEGER DEFAULT 0,
                content TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Get session_id for this run
        run = db.execute(
            "SELECT session_id FROM epic_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run:
            return JSONResponse({"error": "Run not found"}, status_code=404)

        verdicts = db.execute(
            """SELECT * FROM compliance_verdicts WHERE session_id=?
               ORDER BY created_at ASC""",
            (run["session_id"],),
        ).fetchall()

        total = len(verdicts)
        passed = sum(1 for v in verdicts if v["verdict"] == "PASS")
        failed = sum(1 for v in verdicts if v["verdict"] == "FAIL")

        return JSONResponse(
            {
                "run_id": run_id,
                "summary": {"total": total, "passed": passed, "failed": failed},
                "verdicts": [
                    {
                        "id": v["id"],
                        "milestone_id": v["milestone_id"],
                        "agent_id": v["agent_id"],
                        "goal": v["goal"],
                        "verdict": v["verdict"],
                        "is_blocking": bool(v["is_blocking"]),
                        "preview": (v["content"] or "")[:500],
                        "created_at": v["created_at"],
                    }
                    for v in verdicts
                ],
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/compliance/project/{project_id}")
async def get_project_compliance_summary(project_id: str):
    """Get compliance history for a project across all missions."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS compliance_verdicts (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                milestone_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                goal TEXT, verdict TEXT NOT NULL, is_blocking INTEGER DEFAULT 0,
                content TEXT, created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        rows = db.execute(
            """SELECT cv.agent_id, cv.verdict, cv.milestone_id, cv.goal,
                      cv.is_blocking, cv.created_at
               FROM compliance_verdicts cv
               JOIN epic_runs mr ON cv.session_id = mr.session_id
               WHERE mr.project_id = ?
               ORDER BY cv.created_at DESC
               LIMIT 100""",
            (project_id,),
        ).fetchall()

        by_agent: dict = {}
        for r in rows:
            aid = r["agent_id"]
            if aid not in by_agent:
                by_agent[aid] = {
                    "agent_id": aid,
                    "pass": 0,
                    "fail": 0,
                    "last_verdict": None,
                }
            if r["verdict"] == "PASS":
                by_agent[aid]["pass"] += 1
            elif r["verdict"] == "FAIL":
                by_agent[aid]["fail"] += 1
            if not by_agent[aid]["last_verdict"]:
                by_agent[aid]["last_verdict"] = r["verdict"]

        return JSONResponse(
            {
                "project_id": project_id,
                "by_agent": list(by_agent.values()),
                "recent": [
                    {
                        "agent_id": r["agent_id"],
                        "verdict": r["verdict"],
                        "milestone_id": r["milestone_id"],
                        "goal": r["goal"],
                        "is_blocking": bool(r["is_blocking"]),
                        "created_at": r["created_at"],
                    }
                    for r in rows[:20]
                ],
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()
