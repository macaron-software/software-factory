"""Auto-resume missions and background agents after container restart.

Called from server.py lifespan. Resumes:
- All paused mission_runs whose parent mission is "active" and auto-resumable
- Priority given to continuous background missions: TMA, security, self-healing, debt
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Mission types/name patterns that are always-on background missions
_CONTINUOUS_KEYWORDS = (
    "tma", "sécurité", "securite", "security",
    "dette technique", "tech debt", "self-heal", "self_heal",
    "tmc", "load test", "chaos", "endurance",
    "monitoring", "audit",
)

# Max runs to auto-resume at startup (avoid thundering herd)
_MAX_AUTO_RESUME = 20
# Stagger delay between each resume (seconds)
_RESUME_STAGGER = 3.0


def _is_continuous(mission_name: str, mission_type: str) -> bool:
    name_lower = (mission_name or "").lower()
    type_lower = (mission_type or "").lower()
    return any(kw in name_lower or kw in type_lower for kw in _CONTINUOUS_KEYWORDS)


async def auto_resume_missions() -> int:
    """
    Resume paused mission_runs at startup. Returns number of runs resumed.
    Runs as a background asyncio task — staggered to avoid semaphore contention.
    """
    # Import here to avoid circular imports at module load time
    from ..db.migrations import get_db
    from ..missions.store import get_mission_run_store, get_mission_store

    await asyncio.sleep(5)  # Let the platform fully initialize first

    try:
        run_store = get_mission_run_store()
        mission_store = get_mission_store()
        db = get_db()

        # Get all paused runs with their parent mission info
        # mission_runs.session_id links to missions.id
        rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'paused' AND mr.workflow_id IS NOT NULL
            ORDER BY mr.created_at DESC
            LIMIT 200
        """).fetchall()
        db.close()

        if not rows:
            return 0

        # Separate continuous missions from others
        continuous = []
        others = []
        for run_id, wf_id, mname, mtype, mstatus in rows:
            if mstatus not in ("active", None):
                continue  # Skip missions that are completed/failed
            if not wf_id:
                continue  # No workflow → can't resume
            if _is_continuous(mname or "", mtype or ""):
                continuous.append(run_id)
            else:
                others.append(run_id)

        # Resume continuous first, then others, up to _MAX_AUTO_RESUME
        to_resume = (continuous + others)[:_MAX_AUTO_RESUME]

        if not to_resume:
            logger.info("auto_resume: no eligible paused runs found")
            return 0

        logger.warning(
            "auto_resume: resuming %d paused runs (%d continuous + %d others)",
            len(to_resume), len(continuous[:_MAX_AUTO_RESUME]), len(others[:max(0, _MAX_AUTO_RESUME - len(continuous))])
        )

        resumed = 0
        for run_id in to_resume:
            try:
                await _launch_run(run_id)
                resumed += 1
                logger.warning("auto_resume: launched run %s", run_id)
            except Exception as e:
                logger.warning("auto_resume: failed to resume %s: %s", run_id, e)
            await asyncio.sleep(_RESUME_STAGGER)

        logger.warning("auto_resume: %d/%d runs resumed", resumed, len(to_resume))
        return resumed

    except Exception as e:
        logger.error("auto_resume failed: %s", e)
        return 0


async def _launch_run(run_id: str) -> None:
    """Launch a single mission_run via the orchestrator (mirrors _launch_orchestrator in missions.py)."""
    from ..agents.store import get_agent_store
    from ..missions.store import get_mission_run_store
    from ..models import MissionStatus
    from ..services.mission_orchestrator import MissionOrchestrator
    from ..sessions.runner import _push_sse
    from ..web.routes.helpers import _active_mission_tasks, _mission_semaphore
    from ..workflows.store import get_workflow_store

    run_store = get_mission_run_store()
    mission = run_store.get(run_id)
    if not mission:
        raise ValueError(f"Run {run_id} not found")

    # Skip if already running
    existing = _active_mission_tasks.get(run_id)
    if existing and not existing.done():
        return

    wf = get_workflow_store().get(mission.workflow_id)
    if not wf:
        raise ValueError(f"Workflow {mission.workflow_id} not found for run {run_id}")

    agent_store = get_agent_store()
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    orch_agent = agent_store.get(orch_id)
    orch_name = orch_agent.name if orch_agent else "Orchestrateur"
    orch_role = orch_agent.role if orch_agent else "cdp"
    orch_avatar = f"/static/avatars/{orch_id}.svg"

    orchestrator = MissionOrchestrator(
        mission=mission,
        workflow=wf,
        run_store=run_store,
        agent_store=agent_store,
        session_id=mission.session_id or "",
        orch_id=orch_id,
        orch_name=orch_name,
        orch_role=orch_role,
        orch_avatar=orch_avatar,
        push_sse=_push_sse,
    )

    async def _safe_run():
        try:
            async with _mission_semaphore:
                logger.warning("auto_resume: mission_run=%s acquired semaphore", run_id)
                await orchestrator.run_phases()
        except Exception as exc:
            import traceback
            logger.error("auto_resume: run=%s CRASHED: %s\n%s", run_id, exc, traceback.format_exc())
            try:
                mission.status = MissionStatus.FAILED
                run_store.update(mission)
            except Exception:
                pass

    mission.status = MissionStatus.RUNNING
    run_store.update(mission)

    task = asyncio.create_task(_safe_run())
    _active_mission_tasks[run_id] = task
    task.add_done_callback(lambda t: _active_mission_tasks.pop(run_id, None))
