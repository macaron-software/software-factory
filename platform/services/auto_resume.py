"""Auto-resume missions and background agents after container restart.

Called from server.py lifespan. Runs as a periodic watchdog every 5 minutes:
- Resumes paused epic_runs (all of them, batched with stagger)
- Retries failed continuous background missions (TMA, security, self-healing, debt…)
- Launches unstarted continuous missions (first run ever)
- Hourly: cleans up orphaned workspaces + old llm_traces + cancelled run records
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from ..db.migrations import get_db  # noqa: E402 — placed after logger for readability


def _run_lock_key(run_id: str) -> int:
    """Convert run_id to a stable positive int64 for PG advisory lock."""
    return int(hashlib.md5(run_id.encode()).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF


@asynccontextmanager
async def pg_run_lock(run_id: str) -> AsyncGenerator[bool, None]:
    """Try to acquire a PG session-advisory lock for this run.

    Yields True if the lock was acquired (safe to proceed), False if another
    node already holds it (caller should skip).  No-op (yields True) when not
    using PostgreSQL so existing SQLite/test setups are unaffected.
    """
    from ..db.adapter import is_postgresql

    if not is_postgresql():
        yield True
        return

    lock_key = _run_lock_key(run_id)
    loop = asyncio.get_event_loop()

    from ..db.adapter import get_connection

    conn = await loop.run_in_executor(None, get_connection)
    acquired = False
    try:
        row = await loop.run_in_executor(
            None,
            lambda: conn.execute(
                "SELECT pg_try_advisory_lock(?)", (lock_key,)
            ).fetchone(),
        )
        acquired = bool(row and row[0])
        if acquired:
            logger.info("dist-lock: acquired run=%s key=%d", run_id, lock_key)
        else:
            logger.info("dist-lock: run=%s locked by another node — skip", run_id)
        yield acquired
    finally:
        if acquired:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: conn.execute("SELECT pg_advisory_unlock(?)", (lock_key,)),
                )
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


# Mission name/type patterns that should always be running
_CONTINUOUS_KEYWORDS = (
    "tma",
    "sécurité",
    "securite",
    "security",
    "dette technique",
    "tech debt",
    "self-heal",
    "self_heal",
    "tmc",
    "load test",
    "chaos",
    "endurance",
    "monitoring",
    "audit",
)

# Watchdog loop interval (seconds)
_WATCHDOG_INTERVAL = 300
# Stagger between each resume — defaults, overridden by config at runtime
_STAGGER_STARTUP = 60.0  # 60s between each launch on first pass
_STAGGER_WATCHDOG = 15.0
_MAX_STARTUP_BATCH = 1  # only 1 mission at startup (safe default)
# Disk cleanup: run every N watchdog cycles (300s × 12 = 1h)
_CLEANUP_EVERY_N_CYCLES = 12
# GA health: P1 if all proposals pending > 1h with no approved
_GA_STALL_THRESHOLD_SECS = 3600  # 1h

# Auto-launch new runs
_LAUNCH_PER_CYCLE = 2  # max new launches per watchdog cycle
_LAUNCH_STAGGER = 5.0  # seconds between each new launch

# CPU/RAM backpressure thresholds
_CPU_GREEN = 40.0  # below → launch freely
_CPU_YELLOW = 65.0  # 40-65 → slow down (2× stagger)
_CPU_RED = 80.0  # above → skip launch this cycle
_RAM_RED = 75.0  # RAM % above → skip launch (was 85 — too permissive)


def _get_system_load() -> tuple[float, float]:
    """Return (cpu_percent_1s, ram_percent). Falls back to (0, 0) if psutil unavailable."""
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        return cpu, ram
    except Exception:
        return 0.0, 0.0


def _get_backpressure_config() -> tuple[float, float, float, float]:
    """Return (cpu_green, cpu_yellow, cpu_red, ram_red) from config or defaults."""
    try:
        from ..config import get_config

        oc = get_config().orchestrator
        return oc.cpu_green, oc.cpu_yellow, oc.cpu_red, oc.ram_red
    except Exception:
        return _CPU_GREEN, _CPU_YELLOW, _CPU_RED, _RAM_RED


def _get_resume_config():
    """Read concurrency settings from platform config (live, allows runtime changes)."""
    try:
        from ..config import get_config

        oc = get_config().orchestrator
        return (
            oc.resume_stagger_startup,
            oc.resume_stagger_watchdog,
            oc.resume_batch_startup,
        )
    except Exception:
        return _STAGGER_STARTUP, _STAGGER_WATCHDOG, _MAX_STARTUP_BATCH


def _is_continuous(mission_name: str, mission_type: str) -> bool:
    name_lower = (mission_name or "").lower()
    type_lower = (mission_type or "").lower()
    return any(kw in name_lower or kw in type_lower for kw in _CONTINUOUS_KEYWORDS)


async def auto_resume_epics() -> None:
    """
    Watchdog loop: resumes paused/failed epic_runs and launches unstarted continuous missions.
    First pass is aggressive (all paused, 1.5s stagger), then gentle (5-min checks).
    """
    if os.environ.get("PLATFORM_AUTO_RESUME_ENABLED", "1") == "0":
        logger.warning("auto_resume: disabled via PLATFORM_AUTO_RESUME_ENABLED=0")
        return

    # Let platform fully initialize + allow operator intervention window
    _startup_delay = int(os.environ.get("PLATFORM_AUTO_RESUME_DELAY", "60"))
    await asyncio.sleep(_startup_delay)

    # Semaphore is set to 2 in helpers.py — no hot-patch needed

    # Cleanup stale workspace containers before launching missions
    try:
        await _cleanup_workspace_containers()
    except Exception as e:
        logger.warning("auto_resume: workspace container cleanup error: %s", e)

    # First: repair all failed runs (reset to paused + create TMA incidents)
    try:
        await handle_failed_runs()
    except Exception as e:
        logger.error("auto_resume: handle_failed_runs error: %s", e)

    first_pass = True
    cycle_count = 0
    while True:
        # Read concurrency settings live from config (allows runtime changes via UI)
        stagger_startup, stagger_watchdog, _ = _get_resume_config()
        try:
            stagger = stagger_startup if first_pass else stagger_watchdog
            resumed = await _resume_batch(stagger=stagger)
            if resumed > 0:
                logger.warning(
                    "auto_resume: %d runs resumed (first_pass=%s)", resumed, first_pass
                )
            # Launch unstarted continuous missions (new in v2)
            try:
                launched = await auto_launch_continuous_missions()
                if launched > 0:
                    logger.warning(
                        "auto_resume: %d new continuous missions launched", launched
                    )
            except Exception as e_launch:
                logger.error("auto_resume: auto_launch error: %s", e_launch)
            # Hourly disk cleanup
            cycle_count += 1
            if cycle_count % _CLEANUP_EVERY_N_CYCLES == 0:
                try:
                    await _cleanup_disk()
                except Exception as e_clean:
                    logger.error("auto_resume: disk cleanup error: %s", e_clean)
            # Every cycle: enforce container TTL + project slots
            try:
                await _enforce_container_ttl_and_slots()
            except Exception as e_ttl:
                logger.warning("auto_resume: container TTL error: %s", e_ttl)
            # Every cycle: GA health P1 check (stall > 1h → auto-approve bootstrap)
            try:
                await check_ga_health()
            except Exception as e_ga:
                logger.warning("auto_resume: GA health check error: %s", e_ga)
            first_pass = False
        except Exception as e:
            logger.error("auto_resume watchdog error: %s", e)
            first_pass = False

        await asyncio.sleep(_WATCHDOG_INTERVAL)


async def _resume_batch(stagger: float = 3.0) -> int:
    """Resume all paused runs + retry failed continuous missions. Returns count resumed."""
    import os as _os

    if _os.environ.get("PLATFORM_AUTO_RESUME_ENABLED", "1") == "0":
        return 0

    db = get_db()
    try:
        # All paused runs with workflow — exclude human_input_required and > 48h old
        paused_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active'),
                   COALESCE(mr.resume_attempts, 0)
            FROM epic_runs mr
            LEFT JOIN epics m ON m.id = mr.session_id
            WHERE mr.status = 'paused' AND mr.workflow_id IS NOT NULL
              AND COALESCE(mr.human_input_required, 0) = 0
              AND mr.updated_at >= datetime('now', '-7 days')
            ORDER BY mr.created_at DESC
            LIMIT 500
        """).fetchall()

        # Pending runs stuck > 10 min (not picked up by scheduler)
        pending_rows = db.execute("""
            SELECT mr.id, mr.workflow_id,
                   COALESCE(m.name, ''), COALESCE(m.type, ''), COALESCE(m.status, 'active')
            FROM epic_runs mr
            LEFT JOIN epics m ON m.id = mr.session_id
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
            FROM epic_runs mr
            LEFT JOIN epics m ON m.id = mr.session_id
            WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
              AND (m.status IS NULL OR m.status = 'active')
              AND mr.created_at >= datetime('now', '-7 days')
              AND mr.id = (
                SELECT mr2.id FROM epic_runs mr2
                WHERE mr2.session_id = mr.session_id
                ORDER BY mr2.created_at DESC LIMIT 1
              )
              AND NOT EXISTS (
                SELECT 1 FROM epic_runs mr3
                WHERE mr3.session_id = mr.session_id
                  AND mr3.status IN ('pending', 'running')
              )
            ORDER BY mr.created_at DESC
            LIMIT 20
        """).fetchall()
    finally:
        db.close()

    continuous_paused, others_paused, continuous_failed, stuck_pending = [], [], [], []
    # Map run_id → resume_attempts for backoff filtering
    _attempts: dict[str, int] = {}
    for run_id, wf_id, mname, mtype, mstatus, attempts in paused_rows:
        if mstatus not in ("active", None, ""):
            continue
        _attempts[run_id] = attempts
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

    # Apply exponential backoff: skip missions with too many recent attempts
    # Attempt 0-2: always retry; attempt 3: skip 50% chance (use mod); attempt 4+: skip unless low load
    import time as _time

    _now_minute = int(_time.time() // 60)

    def _backoff_ok(run_id: str) -> bool:
        attempts = _attempts.get(run_id, 0)
        if attempts <= 2:
            return True
        if attempts <= 10:
            # Retry every (2^attempts) minutes — skip if not on the right minute
            interval = 2 ** (attempts - 2)  # 2, 4, 8, 16, 32, 64, 128, 256 min
            if attempts >= 8:
                logger.warning(
                    "ESCALATION: run %s at attempt %d — needs attention",
                    run_id,
                    attempts,
                )
            return (_now_minute % interval) == 0
        return False  # > 10 attempts → wait for manual review or human_input_required

    candidates = [
        r
        for r in (continuous_paused + others_paused + stuck_pending + continuous_failed)
        if _backoff_ok(r)
    ]
    to_resume = candidates

    # On startup (large stagger), cap batch to avoid CPU saturation
    stagger_startup, _, batch_max = _get_resume_config()
    if stagger >= stagger_startup:
        to_resume = to_resume[:batch_max]

    if not to_resume:
        return 0

    logger.warning(
        "auto_resume: %d candidates (paused-continuous=%d, paused-other=%d, stuck-pending=%d, failed-continuous=%d)",
        len(to_resume),
        len(continuous_paused),
        len(others_paused),
        len(stuck_pending),
        len(continuous_failed),
    )

    # Read max_active_projects once per batch (checked per-launch below)
    try:
        from ..config import get_config as _get_cfg_slots

        _max_slots = _get_cfg_slots().orchestrator.max_active_projects
    except Exception:
        _max_slots = 0

    def _count_active_containers() -> int:
        """Count currently running macaron-app-* and proj-* containers."""
        try:
            import subprocess as _sp

            r = _sp.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return sum(
                1
                for ln in r.stdout.splitlines()
                if ln.startswith("macaron-app-") or ln.startswith("proj-")
            )
        except Exception:
            return 0

    resumed = 0
    skipped_load = 0
    for run_id in to_resume:
        # Slot gate: don't exceed max_active_projects deployed containers
        if _max_slots > 0 and _count_active_containers() >= _max_slots:
            logger.warning(
                "auto_resume: slot gate — %d active containers >= max_active_projects=%d — stopping batch",
                _count_active_containers(),
                _max_slots,
            )
            break
        # Backpressure: check CPU/RAM before each launch
        cpu, ram = _get_system_load()
        cpu_green, cpu_yellow, cpu_red, ram_red = _get_backpressure_config()
        if cpu >= cpu_red or ram >= ram_red:
            logger.warning(
                "auto_resume: backpressure RED — cpu=%.0f%% ram=%.0f%% — stopping batch (%d/%d launched)",
                cpu,
                ram,
                resumed,
                len(to_resume),
            )
            break  # Stop this cycle entirely, retry next watchdog pass
        effective_stagger = stagger
        if cpu >= cpu_yellow:
            effective_stagger = stagger * 2  # slow down in yellow zone
            skipped_load += 1
            logger.info(
                "auto_resume: backpressure YELLOW cpu=%.0f%% — doubling stagger to %.0fs",
                cpu,
                effective_stagger,
            )
        try:
            # Try to dispatch to a less-loaded worker node first
            dispatched = await _try_dispatch_to_worker(run_id)
            if not dispatched:
                await _launch_run(run_id)
            resumed += 1
            logger.warning(
                "auto_resume: launched run %s (cpu=%.0f%% ram=%.0f%% dispatched=%s)",
                run_id,
                cpu,
                ram,
                dispatched,
            )
        except Exception as e:
            logger.warning("auto_resume: skipped %s: %s", run_id, e)
        await asyncio.sleep(effective_stagger)

    if skipped_load:
        logger.info("auto_resume: %d launches slowed due to CPU pressure", skipped_load)
    return resumed


async def _try_dispatch_to_worker(run_id: str) -> bool:
    """Try to dispatch a mission run to a less-loaded worker node.
    Returns True if dispatched remotely, False if should run locally.
    Worker nodes are configured in OrchestratorConfig.worker_nodes (list of URLs).
    """
    try:
        from ..config import get_config

        workers = getattr(get_config().orchestrator, "worker_nodes", [])
        if not workers:
            return False

        import urllib.request

        local_cpu, local_ram = _get_system_load()
        local_score = local_cpu * 0.6 + local_ram * 0.4

        best_url = None
        best_score = local_score  # only dispatch if worker is lighter than us

        for worker_url in workers:
            try:
                req = urllib.request.Request(
                    f"{worker_url.rstrip('/')}/api/metrics/load",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    score = data.get("load_score", 100)
                    if score < best_score:
                        best_score = score
                        best_url = worker_url
            except Exception as e:
                logger.debug("auto_resume: worker %s unreachable: %s", worker_url, e)

        if not best_url:
            return False  # run locally

        # Dispatch: POST /api/missions/runs/{run_id}/resume to the worker
        payload = json.dumps({"run_id": run_id}).encode()
        req = urllib.request.Request(
            f"{best_url.rstrip('/')}/api/missions/runs/{run_id}/resume",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 202):
                logger.warning(
                    "auto_resume: dispatched run %s to worker %s (score=%.0f vs local=%.0f)",
                    run_id,
                    best_url,
                    best_score,
                    local_score,
                )
                return True
    except Exception as e:
        logger.debug("auto_resume: dispatch failed for %s: %s", run_id, e)
    return False


async def _launch_run(run_id: str) -> None:
    """Launch a single epic_run via the orchestrator."""
    from ..agents.store import get_agent_store
    from ..epics.store import get_epic_run_store
    from ..models import EpicStatus
    from ..services.epic_orchestrator import EpicOrchestrator
    from ..sessions.runner import _push_sse
    from ..web.routes.helpers import _active_mission_tasks, get_mission_semaphore
    from ..workflows.store import get_workflow_store

    run_store = get_epic_run_store()
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

    # Ensure a session row exists for this epic_run (needed for messages FK)
    if mission.session_id:
        _db = get_db()
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
                        _json.dumps(
                            {
                                "workflow_id": mission.workflow_id,
                                "project_id": mission.project_id,
                            }
                        ),
                        _dt.utcnow().isoformat(),
                    ),
                )
                _db.commit()
        finally:
            _db.close()

    # Sync workflow_checkpoint → phases_json so the orchestrator skips completed phases.
    # Missions launched via the workflow engine store progress in sessions.config_json
    # ("workflow_checkpoint" = last completed phase index) but never update phases_json.
    # Without this sync the orchestrator would restart from phase 0 on every resume.
    if mission.session_id:
        try:
            import json as _json

            from ..models import PhaseStatus as _PhaseStatus

            _db2 = get_db()
            try:
                _scfg_row = _db2.execute(
                    "SELECT config_json FROM sessions WHERE id=?", (mission.session_id,)
                ).fetchone()
                if _scfg_row:
                    _scfg = _json.loads(_scfg_row[0] or "{}")
                    _ckpt = _scfg.get("workflow_checkpoint")
                    if (
                        _ckpt
                        and isinstance(_ckpt, int)
                        and _ckpt > 0
                        and mission.phases
                    ):
                        _updated = False
                        for _i, _ph in enumerate(mission.phases):
                            if _i < _ckpt and _ph.status not in (
                                _PhaseStatus.DONE,
                                _PhaseStatus.DONE_WITH_ISSUES,
                                _PhaseStatus.SKIPPED,
                            ):
                                _ph.status = _PhaseStatus.DONE
                                _ph.summary = (
                                    _ph.summary or ""
                                ) + " [resumed from checkpoint]"
                                _updated = True
                        if _updated:
                            run_store.update(mission)
                            logger.warning(
                                "auto_resume: synced workflow_checkpoint=%d → phases_json for run=%s",
                                _ckpt,
                                run_id,
                            )
            finally:
                _db2.close()
        except Exception as _sync_err:
            logger.debug(
                "auto_resume: checkpoint sync failed for %s: %s", run_id, _sync_err
            )

    agent_store = get_agent_store()
    orch_id = mission.cdp_agent_id or "chef_de_programme"
    orch_agent = agent_store.get(orch_id)
    orch_name = orch_agent.name if orch_agent else "Orchestrateur"
    orch_role = orch_agent.role if orch_agent else "cdp"
    orch_avatar = f"/static/avatars/{orch_id}.svg"

    orchestrator = EpicOrchestrator(
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
        async with pg_run_lock(run_id) as acquired:
            if not acquired:
                # Another node is running this — revert status to paused so it
                # doesn't linger as RUNNING if the other node crashes first.
                try:
                    mission.status = EpicStatus.PAUSED
                    run_store.update(mission)
                except Exception:
                    pass
                return
            try:
                async with get_mission_semaphore():
                    logger.warning(
                        "auto_resume: epic_run=%s acquired semaphore", run_id
                    )
                    await orchestrator.run_phases()
            except Exception as exc:
                import traceback

                logger.error(
                    "auto_resume: run=%s CRASHED: %s\n%s",
                    run_id,
                    exc,
                    traceback.format_exc(),
                )
                try:
                    mission.status = EpicStatus.FAILED
                    run_store.update(mission)
                except Exception:
                    pass

    mission.status = EpicStatus.RUNNING
    run_store.update(mission)

    task = asyncio.create_task(_safe_run())
    _active_mission_tasks[run_id] = task
    task.add_done_callback(lambda t: _active_mission_tasks.pop(run_id, None))


# ─── Failed run repair ──────────────────────────────────────────────────────

_TMA_WORKFLOW_ID = "tma-maintenance"
_MAX_RETRIES = 3  # after that, don't auto-retry


async def handle_failed_runs() -> int:
    """
    Repair failed epic_runs so the watchdog can retry them.
    - Init failures (no progress) → reset to paused, reset pending phases
    - Phase failures (had progress) → reset to paused + create TMA incident run
    - Phantom running runs (stale > 30min) → reset to paused immediately
    Called once at startup (before the watchdog loop starts retrying paused runs).
    Returns number of runs repaired.
    """

    db = get_db()
    try:
        # First: reset phantom running runs (stale > 30min) → paused so watchdog picks them up
        phantom = db.execute("""
            UPDATE epic_runs SET status='paused', updated_at=datetime('now')
            WHERE status = 'running'
            AND workflow_id IS NOT NULL
            AND (updated_at IS NULL OR updated_at < datetime('now', '-30 minutes'))
        """)
        phantom_count = phantom.rowcount
        if phantom_count:
            db.commit()
            logger.warning(
                "handle_failed_runs: reset %d phantom running runs → paused",
                phantom_count,
            )

        rows = db.execute("""
            SELECT mr.id, mr.workflow_id, mr.workflow_name, mr.current_phase,
                   mr.phases_json, mr.project_id, mr.brief,
                   COALESCE(m.name, ''), COALESCE(m.type, '')
            FROM epic_runs mr
            LEFT JOIN epics m ON m.id = mr.session_id
            WHERE mr.status = 'failed' AND mr.workflow_id IS NOT NULL
            ORDER BY mr.created_at DESC
            LIMIT 200
        """).fetchall()
    finally:
        db.close()

    if not rows:
        return phantom_count

    repaired = 0
    tma_created = 0
    for (
        run_id,
        wf_id,
        wf_name,
        cur_phase,
        phases_raw,
        project_id,
        brief,
        mname,
        mtype,
    ) in rows:
        try:
            phases = json.loads(phases_raw) if phases_raw else []
            done_phases = [
                p
                for p in phases
                if p.get("status") in ("done", "done_with_issues", "skipped")
            ]

            # Reset failed/running phases back to pending so orchestrator retries them
            repaired_phases = _reset_failed_phases(phases)
            new_phases_json = json.dumps(repaired_phases, ensure_ascii=False)

            db2 = get_db()
            try:
                db2.execute(
                    "UPDATE epic_runs SET status='paused', phases_json=? WHERE id=?",
                    (new_phases_json, run_id),
                )
                db2.commit()
            finally:
                db2.close()

            repaired += 1

            # Phase-specific failure with prior progress → also create TMA incident
            if done_phases and cur_phase and project_id:
                # Guard: skip if TMA incident already exists for this run
                db3 = get_db()
                try:
                    existing = db3.execute(
                        "SELECT id FROM epic_runs WHERE parent_epic_id=? AND workflow_id=?",
                        (run_id, _TMA_WORKFLOW_ID),
                    ).fetchone()
                finally:
                    db3.close()
                if not existing:
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
        repaired,
        tma_created,
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
    """Create a TMA incident epic_run for a failed execution phase."""
    import uuid

    incident_id = str(uuid.uuid4())[:8] + "-tma-incident"
    brief = (
        f"[AUTO-INCIDENT] Mission «{workflow_name}» a échoué en phase «{failed_phase}» "
        f"après avoir complété {len(done_phases)} phases ({', '.join(done_phases[:3])}…). "
        f"Analyser la cause, corriger l'environnement/code et valider que la mission peut reprendre. "
        f"Mission d'origine: {failed_run_id}. Contexte original: {original_brief[:200]}"
    )

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO epic_runs
              (id, workflow_id, workflow_name, project_id, status, current_phase,
               phases_json, brief, parent_epic_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', '',
                    '[]', ?, ?, datetime('now'), datetime('now'))
        """,
            (
                incident_id,
                _TMA_WORKFLOW_ID,
                "TMA — Incident Auto-Détecté",
                project_id,
                brief,
                failed_run_id,
            ),
        )
        db.commit()
        logger.warning(
            "handle_failed_runs: TMA incident %s created for failed run %s (phase=%s)",
            incident_id,
            failed_run_id,
            failed_phase,
        )
    finally:
        db.close()


# ─── Auto-launch continuous missions with no runs ───────────────────────────


async def auto_launch_continuous_missions() -> int:
    """
    Find active continuous missions (security, debt, TMA…) that have NO epic_run yet
    and launch them. Called by the watchdog loop after handling paused/failed.
    Returns count of missions launched.
    """

    db = get_db()
    try:
        # Active missions with a workflow but no run ever
        rows = db.execute("""
            SELECT m.id, m.name, m.type, m.workflow_id,
                   COALESCE(m.project_id, ''), COALESCE(m.description, ''),
                   COALESCE(m.goal, m.description, m.name)
            FROM epics m
            WHERE m.status = 'active'
              AND m.workflow_id IS NOT NULL AND m.workflow_id != ''
              AND NOT EXISTS (
                SELECT 1 FROM epic_runs mr
                WHERE mr.session_id = m.id
                   OR mr.parent_epic_id = m.id
              )
            ORDER BY m.created_at DESC
            LIMIT 200
        """).fetchall()
    finally:
        db.close()

    if not rows:
        return 0

    # Filter: only continuous missions
    candidates = [r for r in rows if _is_continuous(r[1], r[2])]

    if not candidates:
        logger.warning(
            "auto_launch: %d unstarted active missions, 0 continuous", len(rows)
        )
        return 0

    to_launch = candidates[:_LAUNCH_PER_CYCLE]
    logger.warning(
        "auto_launch: %d continuous missions unstarted, launching %d this cycle",
        len(candidates),
        len(to_launch),
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
            logger.warning(
                "auto_launch: started run for mission %s (%s)",
                mission_id[:8],
                name[:50],
            )
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
    """Create a new EpicRun for a backlog mission and launch it."""
    import os
    import subprocess
    import uuid

    from ..models import EpicRun, EpicStatus, PhaseRun, PhaseStatus
    from ..epics.store import get_epic_run_store
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
        "data",
        "workspaces",
        run_id,
    )
    os.makedirs(ws_base, exist_ok=True)
    # Ensure workspace has a git repo so git tools work
    if not os.path.isdir(os.path.join(ws_base, ".git")):
        subprocess.run(["git", "init"], cwd=ws_base, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init workspace"],
            cwd=ws_base,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "agent",
                "GIT_AUTHOR_EMAIL": "agent@sf",
                "GIT_COMMITTER_NAME": "agent",
                "GIT_COMMITTER_EMAIL": "agent@sf",
            },
        )

    run = EpicRun(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=wf.name,
        brief=brief[:500],
        status=EpicStatus.PENDING,
        phases=phases,
        project_id=project_id,
        workspace_path=ws_base,
        cdp_agent_id=orchestrator_id,
        session_id=mission_id,  # links run → mission in missions table
    )

    get_epic_run_store().create(run)
    await _launch_run(run_id)
    return run_id


async def check_ga_health() -> None:
    """P1 watchdog: if all GA proposals are pending for > 1h with none approved,
    auto-approve the best per workflow (bootstrap) and log a P1 warning.
    Runs every watchdog cycle (~5 min) but only acts once per stall episode."""

    db = get_db()
    try:
        # Count pending proposals older than threshold
        stall_row = db.execute(
            """SELECT COUNT(*) FROM evolution_proposals
               WHERE status = 'pending'
               AND EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at)) > ?""",
            (_GA_STALL_THRESHOLD_SECS,),
        ).fetchone()
        stalled_count = stall_row[0] if stall_row else 0
        if stalled_count == 0:
            return

        # Check if any approved exist (would mean GA is healthy)
        approved_row = db.execute(
            "SELECT COUNT(*) FROM evolution_proposals WHERE status = 'approved'"
        ).fetchone()
        approved_count = approved_row[0] if approved_row else 0

        if approved_count > 0:
            return  # GA has approved proposals — not stalled

        # P1: GA fully stalled — auto-approve best per workflow to bootstrap
        logger.warning(
            "P1 GA STALL: %d proposals pending >1h, 0 approved — auto-approving best per workflow",
            stalled_count,
        )
        db.execute(
            """UPDATE evolution_proposals
               SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
               WHERE id IN (
                   SELECT id FROM evolution_proposals ep1
                   WHERE status = 'pending' AND fitness > 0
                   AND NOT EXISTS (
                       SELECT 1 FROM evolution_proposals ep2
                       WHERE ep2.base_wf_id = ep1.base_wf_id
                         AND ep2.fitness > ep1.fitness
                         AND ep2.status = 'pending'
                   )
               )"""
        )
        db.commit()
        approved_now = db.execute(
            "SELECT COUNT(*) FROM evolution_proposals WHERE status = 'approved'"
        ).fetchone()[0]
        logger.warning("P1 GA STALL resolved: %d proposals auto-approved", approved_now)
    except Exception as e:
        logger.error("check_ga_health error: %s", e)
    finally:
        db.close()


async def _cleanup_disk() -> None:
    """Hourly cleanup: orphaned workspaces + old LLM traces + stale cancelled runs."""

    db = None
    try:
        db = get_db()

        # 1. Remove workspaces for non-active sessions
        ws_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "workspaces"
        )
        ws_dir = os.path.normpath(ws_dir)
        if not os.path.isdir(ws_dir):
            # Try absolute path used in container
            ws_dir = "/app/data/workspaces"
        if os.path.isdir(ws_dir):
            active_sessions = {
                r[0]
                for r in db.execute(
                    "SELECT session_id FROM epic_runs WHERE status IN ('running','pending','paused') AND session_id IS NOT NULL"
                ).fetchall()
            }
            removed_ws = 0
            for ws_name in os.listdir(ws_dir):
                if ws_name not in active_sessions:
                    try:
                        shutil.rmtree(os.path.join(ws_dir, ws_name))
                        removed_ws += 1
                    except Exception:
                        pass
            if removed_ws:
                logger.warning(
                    "cleanup_disk: removed %d orphaned workspaces", removed_ws
                )

        # 2. Purge LLM traces older than 14 days (keep recent for observability)
        deleted_traces = db.execute(
            "DELETE FROM llm_traces WHERE created_at < datetime('now', '-14 days')"
        ).rowcount
        if deleted_traces:
            db.commit()
            logger.warning("cleanup_disk: purged %d LLM traces >14d", deleted_traces)

        # 3. Purge cancelled run records older than 7 days
        deleted_runs = db.execute(
            "DELETE FROM epic_runs WHERE status = 'cancelled' AND updated_at < datetime('now', '-7 days')"
        ).rowcount
        if deleted_runs:
            db.commit()
            logger.warning("cleanup_disk: purged %d cancelled runs >7d", deleted_runs)

        if deleted_traces + deleted_runs > 100:
            db.execute("VACUUM")
            logger.warning(
                "cleanup_disk: VACUUM done after %d deletes",
                deleted_traces + deleted_runs,
            )
    except Exception:
        pass
    finally:
        if db:
            db.close()


async def _cleanup_workspace_containers() -> None:
    """Kill stale proj-* and macaron-app-* containers that accumulate from past missions."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return

    killed = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        name, status = parts
        # Kill stopped/exited workspace containers (proj-* and macaron-app-*)
        if (name.startswith("proj-") or name.startswith("macaron-app-")) and (
            "Exited" in status or "Created" in status
        ):
            try:
                subprocess.run(
                    ["docker", "rm", "-f", name], capture_output=True, timeout=10
                )
                killed.append(name)
            except Exception:
                pass

    if killed:
        logger.warning(
            "auto_resume: cleaned up %d stale workspace containers: %s",
            len(killed),
            killed[:5],
        )


async def _enforce_container_ttl_and_slots() -> None:
    """Stop deployed app containers (macaron-app-*) that are too old or exceed the active-project slot limit.

    Reads config.orchestrator.max_active_projects and deployed_container_ttl_hours.
    Called every watchdog cycle.
    """
    import subprocess
    import re
    from datetime import datetime, timezone

    try:
        from ..config import get_config

        oc = get_config().orchestrator
        max_slots = oc.max_active_projects  # 0 = unlimited
        ttl_hours = oc.deployed_container_ttl_hours  # 0 = no TTL
    except Exception:
        max_slots = 3
        ttl_hours = 4.0

    if max_slots == 0 and ttl_hours == 0:
        return

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.CreatedAt}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return

    now = datetime.now(timezone.utc)
    app_containers: list[tuple[str, datetime]] = []

    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        name, created_str = parts
        if not (name.startswith("macaron-app-") or name.startswith("proj-")):
            continue
        try:
            # Docker format: "2026-01-15 10:23:45 +0000 UTC" or "2026-01-15T10:23:45Z"
            created_str = re.sub(r"\s+UTC$", "", created_str.strip())
            dt = datetime.fromisoformat(
                created_str.replace(" ", "T").replace(" +0000", "+00:00")
            )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            app_containers.append((name, dt))
        except Exception:
            app_containers.append((name, now))  # unknown age → treat as fresh

    if not app_containers:
        return

    # Sort oldest first
    app_containers.sort(key=lambda x: x[1])

    to_stop = []
    for name, created in app_containers:
        age_hours = (now - created).total_seconds() / 3600
        if ttl_hours > 0 and age_hours > ttl_hours:
            to_stop.append((name, f"age={age_hours:.1f}h > ttl={ttl_hours}h"))

    # Enforce slot limit: stop oldest beyond max_slots
    if max_slots > 0 and len(app_containers) > max_slots:
        over = app_containers[: len(app_containers) - max_slots]
        for name, created in over:
            if name not in [n for n, _ in to_stop]:
                to_stop.append((name, f"slots={len(app_containers)} > max={max_slots}"))

    for name, reason in to_stop:
        try:
            subprocess.run(["docker", "stop", name], capture_output=True, timeout=15)
            subprocess.run(["docker", "rm", name], capture_output=True, timeout=10)
            logger.warning(
                "auto_resume: stopped deployed container %s (%s)", name, reason
            )
            # Pause any still-running SF run whose mission maps to this container
            try:
                prefix = name.removeprefix("macaron-app-").removeprefix("proj-")

                _db2 = get_db()
                try:
                    _db2.execute(
                        """UPDATE epic_runs SET status='paused', updated_at=datetime('now')
                           WHERE status='running'
                             AND session_id LIKE ? || '%'""",
                        (prefix,),
                    )
                    _db2.commit()
                finally:
                    _db2.close()
            except Exception as _e2:
                logger.debug("auto_resume: could not pause run for %s: %s", name, _e2)
        except Exception as e:
            logger.warning("auto_resume: failed to stop %s: %s", name, e)
