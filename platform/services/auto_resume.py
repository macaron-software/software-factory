"""Auto-resume missions and background agents after container restart.

Called from server.py lifespan. Runs as a periodic watchdog every 5 minutes:
- Resumes paused mission_runs (all of them, batched with stagger)
- Retries failed continuous background missions (TMA, security, self-healing, debt…)
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Mission name/type patterns that should always be running
_CONTINUOUS_KEYWORDS = (
    "tma", "sécurité", "securite", "security",
    "dette technique", "tech debt", "self-heal", "self_heal",
    "tmc", "load test", "chaos", "endurance",
    "monitoring", "audit",
)

# Watchdog loop interval (seconds)
_WATCHDOG_INTERVAL = 300
# Stagger between each resume
_STAGGER_STARTUP = 1.5
_STAGGER_WATCHDOG = 3.0


def _is_continuous(mission_name: str, mission_type: str) -> bool:
    name_lower = (mission_name or "").lower()
    type_lower = (mission_type or "").lower()
    return any(kw in name_lower or kw in type_lower for kw in _CONTINUOUS_KEYWORDS)


async def auto_resume_missions() -> None:
    """
    Watchdog loop: resumes paused/failed mission_runs.
    First pass is aggressive (all paused, 1.5s stagger), then gentle (5-min checks).
    """
    await asyncio.sleep(5)  # Let platform fully initialize first

    first_pass = True
    while True:
        try:
            stagger = _STAGGER_STARTUP if first_pass else _STAGGER_WATCHDOG
            resumed = await _resume_batch(stagger=stagger)
            if resumed > 0:
                logger.warning("auto_resume: %d runs resumed (first_pass=%s)", resumed, first_pass)
            first_pass = False
        except Exception as e:
            logger.error("auto_resume watchdog error: %s", e)
            first_pass = False

        await asyncio.sleep(_WATCHDOG_INTERVAL)


async def _resume_batch(stagger: float = 3.0) -> int:
    """Resume all paused runs + retry failed continuous missions. Returns count resumed."""
    from ..db.migrations import get_db

    db = get_db()
    try:
        # All paused runs with workflow
        paused_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'paused' AND mr.workflow_id IS NOT NULL
            ORDER BY mr.created_at DESC
            LIMIT 500
        """).fetchall()

        # Failed continuous missions (retry within 7 days)
        failed_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
              AND (m.status IS NULL OR m.status = 'active')
              AND mr.created_at >= datetime('now', '-7 days')
            ORDER BY mr.created_at DESC
            LIMIT 100
        """).fetchall()
    finally:
        db.close()

    continuous_paused, others_paused, continuous_failed = [], [], []
    for run_id, wf_id, mname, mtype, mstatus in paused_rows:
        if mstatus not in ("active", None, ""):
            continue
        if _is_continuous(mname, mtype):
            continuous_paused.append(run_id)
        else:
            others_paused.append(run_id)

    for run_id, wf_id, mname, mtype, mstatus in failed_rows:
        if _is_continuous(mname, mtype):
            continuous_failed.append(run_id)

    to_resume = continuous_paused + others_paused + continuous_failed

    if not to_resume:
        return 0

    logger.warning(
        "auto_resume: %d candidates (paused-continuous=%d, paused-other=%d, failed-continuous=%d)",
        len(to_resume), len(continuous_paused), len(others_paused), len(continuous_failed),
    )

    resumed = 0
    for run_id in to_resume:
        try:
            await _launch_run(run_id)
            resumed += 1
            logger.warning("auto_resume: launched run %s", run_id)
        except Exception as e:
            logger.warning("auto_resume: skipped %s: %s", run_id, e)
        await asyncio.sleep(stagger)

    return resumed


async def _launch_run(run_id: str) -> None:
    """Launch a single mission_run via the orchestrator."""
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
