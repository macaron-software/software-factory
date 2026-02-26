"""Auto-resume missions and background agents after container restart.

Called from server.py lifespan. Runs as a periodic watchdog every 5 minutes:
- Resumes paused mission_runs (all of them, batched with stagger)
- Retries failed continuous background missions (TMA, security, self-healing, debt…)
- Launches unstarted continuous missions (first run ever)
"""
from __future__ import annotations

import asyncio
import json
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

# Auto-launch new runs
_LAUNCH_PER_CYCLE = 5   # max new launches per watchdog cycle (avoid thundering herd)
_LAUNCH_STAGGER = 2.0   # seconds between each new launch


def _is_continuous(mission_name: str, mission_type: str) -> bool:
    name_lower = (mission_name or "").lower()
    type_lower = (mission_type or "").lower()
    return any(kw in name_lower or kw in type_lower for kw in _CONTINUOUS_KEYWORDS)


async def auto_resume_missions() -> None:
    """
    Watchdog loop: resumes paused/failed mission_runs and launches unstarted continuous missions.
    First pass is aggressive (all paused, 1.5s stagger), then gentle (5-min checks).
    """
    await asyncio.sleep(5)  # Let platform fully initialize first

    # Hot-patch startup: use release() to both add slots AND wake up waiting coroutines
    try:
        from ..web.routes.helpers import _mission_semaphore
        target = 10
        added = max(0, target - _mission_semaphore._value)
        for _ in range(added):
            _mission_semaphore.release()
        if added:
            logger.warning("auto_resume: released %d semaphore slots → value=%d (wakes waiters)", added, _mission_semaphore._value)
    except Exception as _e_sem:
        logger.warning("auto_resume: semaphore patch failed: %s", _e_sem)

    # First: repair all failed runs (reset to paused + create TMA incidents)
    try:
        await handle_failed_runs()
    except Exception as e:
        logger.error("auto_resume: handle_failed_runs error: %s", e)

    first_pass = True
    while True:
        # Hot-patch per cycle: use release() to add slots and wake up waiting coroutines
        try:
            from ..web.routes.helpers import _mission_semaphore
            target = 10
            added = max(0, target - _mission_semaphore._value)
            for _ in range(added):
                _mission_semaphore.release()
            if added:
                logger.warning("auto_resume: released %d semaphore slots → value=%d", added, _mission_semaphore._value)
        except Exception as _e_sem:
            logger.warning("auto_resume: semaphore patch failed: %s", _e_sem)
        try:
            stagger = _STAGGER_STARTUP if first_pass else _STAGGER_WATCHDOG
            resumed = await _resume_batch(stagger=stagger)
            if resumed > 0:
                logger.warning("auto_resume: %d runs resumed (first_pass=%s)", resumed, first_pass)
            # Launch unstarted continuous missions (new in v2)
            try:
                launched = await auto_launch_continuous_missions()
                if launched > 0:
                    logger.warning("auto_resume: %d new continuous missions launched", launched)
            except Exception as e_launch:
                logger.error("auto_resume: auto_launch error: %s", e_launch)
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

        # Pending runs stuck > 10 min (not picked up by scheduler)
        pending_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'pending' AND mr.workflow_id IS NOT NULL
              AND mr.created_at <= datetime('now', '-10 minutes')
              AND (m.status IS NULL OR m.status = 'active')
            ORDER BY mr.created_at ASC
            LIMIT 20
        """).fetchall()

        # Failed continuous missions: only LATEST run per mission, only if no pending/running run exists
        failed_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
              AND (m.status IS NULL OR m.status = 'active')
              AND mr.created_at >= datetime('now', '-7 days')
              AND mr.id = (
                SELECT mr2.id FROM mission_runs mr2
                WHERE mr2.session_id = mr.session_id
                ORDER BY mr2.created_at DESC LIMIT 1
              )
              AND NOT EXISTS (
                SELECT 1 FROM mission_runs mr3
                WHERE mr3.session_id = mr.session_id
                  AND mr3.status IN ('pending', 'running')
              )
            ORDER BY mr.created_at DESC
            LIMIT 20
        """).fetchall()
    finally:
        db.close()

    continuous_paused, others_paused, continuous_failed, stuck_pending = [], [], [], []
    for run_id, wf_id, mname, mtype, mstatus in paused_rows:
        if mstatus not in ("active", None, ""):
            continue
        if _is_continuous(mname, mtype):
            continuous_paused.append(run_id)
        else:
            others_paused.append(run_id)

    for run_id, wf_id, mname, mtype, mstatus in pending_rows:
        if mstatus in ("active", None, ""):
            stuck_pending.append(run_id)

    for run_id, wf_id, mname, mtype, mstatus in failed_rows:
        if _is_continuous(mname, mtype):
            continuous_failed.append(run_id)

    to_resume = continuous_paused + others_paused + stuck_pending + continuous_failed

    if not to_resume:
        return 0

    logger.warning(
        "auto_resume: %d candidates (paused-continuous=%d, paused-other=%d, stuck-pending=%d, failed-continuous=%d)",
        len(to_resume), len(continuous_paused), len(others_paused), len(stuck_pending), len(continuous_failed),
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

    # Ensure a session row exists for this mission_run (needed for messages FK)
    if mission.session_id:
        from ..db.migrations import get_db as _get_db
        _db = _get_db()
        try:
            exists = _db.execute(
                "SELECT id FROM sessions WHERE id=?", (mission.session_id,)
            ).fetchone()
            if not exists:
                from datetime import datetime as _dt
                import json as _json
                _db.execute(
                    "INSERT OR IGNORE INTO sessions "
                    "(id, name, status, config_json, created_at) "
                    "VALUES (?, ?, 'active', ?, ?)",
                    (
                        mission.session_id,
                        f"mission-{mission.session_id[:8]}",
                        _json.dumps({"workflow_id": mission.workflow_id,
                                     "project_id": mission.project_id}),
                        _dt.utcnow().isoformat(),
                    ),
                )
                _db.commit()
        finally:
            _db.close()

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


# ─── Failed run repair ──────────────────────────────────────────────────────

_TMA_WORKFLOW_ID = "tma-maintenance"
_MAX_RETRIES = 3  # after that, don't auto-retry


async def handle_failed_runs() -> int:
    """
    Repair failed mission_runs so the watchdog can retry them.
    - Init failures (no progress) → reset to paused, reset pending phases
    - Phase failures (had progress) → reset to paused + create TMA incident run
    Called once at startup (before the watchdog loop starts retrying paused runs).
    Returns number of runs repaired.
    """
    from ..db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute("""
            SELECT mr.id, mr.workflow_id, mr.workflow_name, mr.current_phase,
                   mr.phases_json, mr.project_id, mr.brief,
                   COALESCE(m.name, ''), COALESCE(m.type, '')
            FROM mission_runs mr
            LEFT JOIN missions m ON m.id = mr.session_id
            WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
            ORDER BY mr.created_at DESC
            LIMIT 200
        """).fetchall()
    finally:
        db.close()

    if not rows:
        return 0

    repaired = 0
    tma_created = 0
    for run_id, wf_id, wf_name, cur_phase, phases_raw, project_id, brief, mname, mtype in rows:
        try:
            phases = json.loads(phases_raw) if phases_raw else []
            done_phases = [p for p in phases if p.get("status") in ("done", "done_with_issues", "skipped")]

            # Reset failed/running phases back to pending so orchestrator retries them
            repaired_phases = _reset_failed_phases(phases)
            new_phases_json = json.dumps(repaired_phases, ensure_ascii=False)

            db2 = get_db()
            try:
                db2.execute(
                    "UPDATE mission_runs SET status='paused', phases_json=? WHERE id=?",
                    (new_phases_json, run_id),
                )
                db2.commit()
            finally:
                db2.close()

            repaired += 1

            # Phase-specific failure with prior progress → also create TMA incident
            if done_phases and cur_phase and project_id:
                await _create_tma_incident(
                    failed_run_id=run_id,
                    workflow_name=wf_name,
                    failed_phase=cur_phase,
                    done_phases=[p["phase_id"] for p in done_phases],
                    project_id=project_id,
                    original_brief=brief or "",
                )
                tma_created += 1

        except Exception as e:
            logger.warning("handle_failed_runs: error on %s: %s", run_id, e)

    logger.warning(
        "handle_failed_runs: %d repaired → paused (%d TMA incidents created)",
        repaired, tma_created,
    )
    return repaired


def _reset_failed_phases(phases: list) -> list:
    """Reset failed/stuck-running phases to pending so orchestrator retries them."""
    import copy
    result = []
    for p in phases:
        phase = copy.deepcopy(p)
        if phase.get("status") in ("failed", "running"):
            phase["status"] = "pending"
            phase["started_at"] = None
            phase["completed_at"] = None
            # Preserve summary as context but mark it as a retry
            if phase.get("summary"):
                phase["summary"] = f"[retry] {phase['summary']}"
        result.append(phase)
    return result


async def _create_tma_incident(
    failed_run_id: str,
    workflow_name: str,
    failed_phase: str,
    done_phases: list,
    project_id: str,
    original_brief: str,
) -> None:
    """Create a TMA incident mission_run for a failed execution phase."""
    import uuid
    from ..db.migrations import get_db

    incident_id = str(uuid.uuid4())[:8] + "-tma-incident"
    brief = (
        f"[AUTO-INCIDENT] Mission «{workflow_name}» a échoué en phase «{failed_phase}» "
        f"après avoir complété {len(done_phases)} phases ({', '.join(done_phases[:3])}…). "
        f"Analyser la cause, corriger l'environnement/code et valider que la mission peut reprendre. "
        f"Mission d'origine: {failed_run_id}. Contexte original: {original_brief[:200]}"
    )

    db = get_db()
    try:
        db.execute("""
            INSERT INTO mission_runs
              (id, workflow_id, workflow_name, project_id, status, current_phase,
               phases_json, brief, parent_mission_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', '',
                    '[]', ?, ?, datetime('now'), datetime('now'))
        """, (
            incident_id,
            _TMA_WORKFLOW_ID,
            "TMA — Incident Auto-Détecté",
            project_id,
            brief,
            failed_run_id,
        ))
        db.commit()
        logger.warning(
            "handle_failed_runs: TMA incident %s created for failed run %s (phase=%s)",
            incident_id, failed_run_id, failed_phase,
        )
    finally:
        db.close()


# ─── Auto-launch continuous missions with no runs ───────────────────────────

async def auto_launch_continuous_missions() -> int:
    """
    Find active continuous missions (security, debt, TMA…) that have NO mission_run yet
    and launch them. Called by the watchdog loop after handling paused/failed.
    Returns count of missions launched.
    """
    from ..db.migrations import get_db

    db = get_db()
    try:
        # Active missions with a workflow but no run ever
        rows = db.execute("""
            SELECT m.id, m.name, m.type, m.workflow_id,
                   COALESCE(m.project_id, ''), COALESCE(m.description, ''),
                   COALESCE(m.goal, m.description, m.name)
            FROM missions m
            WHERE m.status = 'active'
              AND m.workflow_id IS NOT NULL AND m.workflow_id != ''
              AND NOT EXISTS (
                SELECT 1 FROM mission_runs mr
                WHERE mr.session_id = m.id
                   OR mr.parent_mission_id = m.id
              )
            ORDER BY m.created_at DESC
            LIMIT 200
        """).fetchall()
    finally:
        db.close()

    if not rows:
        return 0

    # Filter: only continuous missions
    candidates = [
        r for r in rows
        if _is_continuous(r[1], r[2])
    ]

    if not candidates:
        logger.warning("auto_launch: %d unstarted active missions, 0 continuous", len(rows))
        return 0

    to_launch = candidates[:_LAUNCH_PER_CYCLE]
    logger.warning(
        "auto_launch: %d continuous missions unstarted, launching %d this cycle",
        len(candidates), len(to_launch),
    )

    launched = 0
    for row in to_launch:
        mission_id, name, mtype, wf_id, project_id, desc, goal = row
        try:
            await _launch_new_run(
                mission_id=mission_id,
                workflow_id=wf_id,
                project_id=project_id,
                brief=goal or desc or name,
                mission_name=name,
            )
            launched += 1
            logger.warning("auto_launch: started run for mission %s (%s)", mission_id[:8], name[:50])
        except Exception as e:
            logger.warning("auto_launch: failed to start %s: %s", mission_id[:8], e)
        await asyncio.sleep(_LAUNCH_STAGGER)

    return launched


async def _launch_new_run(
    mission_id: str,
    workflow_id: str,
    project_id: str,
    brief: str,
    mission_name: str,
) -> str:
    """Create a new MissionRun for a backlog mission and launch it."""
    import os
    import subprocess
    import uuid

    from ..models import MissionRun, MissionStatus, PhaseRun, PhaseStatus
    from ..missions.store import get_mission_run_store
    from ..workflows.store import get_workflow_store

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        raise ValueError(f"Workflow {workflow_id} not found")

    phases = [
        PhaseRun(
            phase_id=wp.id,
            phase_name=wp.name,
            pattern_id=wp.pattern_id,
            status=PhaseStatus.PENDING,
        )
        for wp in wf.phases
    ]

    orchestrator_id = (wf.config or {}).get("orchestrator", "chef_de_programme")

    run_id = uuid.uuid4().hex[:8]
    # Workspace under data/workspaces/
    ws_base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "workspaces", run_id,
    )
    os.makedirs(ws_base, exist_ok=True)
    # Ensure workspace has a git repo so git tools work
    if not os.path.isdir(os.path.join(ws_base, ".git")):
        subprocess.run(["git", "init"], cwd=ws_base, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init workspace"],
                       cwd=ws_base, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "agent", "GIT_AUTHOR_EMAIL": "agent@sf",
                            "GIT_COMMITTER_NAME": "agent", "GIT_COMMITTER_EMAIL": "agent@sf"})

    run = MissionRun(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief[:500],
        status=MissionStatus.PENDING,
        phases=phases,
        project_id=project_id,
        workspace_path=ws_base,
        cdp_agent_id=orchestrator_id,
        session_id=mission_id,  # links run → mission in missions table
    )

    get_mission_run_store().create(run)
    await _launch_run(run_id)
    return run_id
