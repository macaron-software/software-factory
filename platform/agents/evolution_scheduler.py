"""
Evolution Scheduler — nightly GA run at 02:00 UTC + RL retraining.

Call start_evolution_scheduler() once at app startup (server.py).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


async def _wait_until_next_run(hour: int = 2) -> None:
    """Wait until the next occurrence of `hour`:00 UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_secs = (target - now).total_seconds()
    log.info(f"Evolution scheduler: next run at {target.isoformat()} (in {wait_secs/3600:.1f}h)")
    await asyncio.sleep(wait_secs)


async def _run_evolution_cycle() -> None:
    """Run GA evolution on all workflows + RL retraining."""
    log.info("Evolution scheduler: starting nightly cycle")
    try:
        # 1. Seed simulator data for cold-start workflows
        from ..agents.simulator import MissionSimulator
        sim = MissionSimulator()
        sim_results = sim.run_all(n_runs_per_workflow=100)
        log.info(f"Simulator: seeded {sum(sim_results.values())} rows")
    except Exception as e:
        log.warning(f"Simulator seed failed: {e}")

    try:
        # 2. Run GA on all workflows
        from ..agents.evolution import GAEngine
        engine = GAEngine()
        ga_results = engine.evolve_all(generations=30)
        log.info(f"GA: evolved {len(ga_results)} workflows, best={max(ga_results.values(), default=0):.4f}")
    except Exception as e:
        log.warning(f"GA evolution failed: {e}")

    try:
        # 3. Retrain RL policy
        from ..agents.rl_policy import get_rl_policy
        policy = get_rl_policy()
        rl_stats = policy.train(max_rows=100_000)
        log.info(f"RL retrain: {rl_stats}")
    except Exception as e:
        log.warning(f"RL retrain failed: {e}")


async def start_evolution_scheduler() -> None:
    """Long-running coroutine — runs evolution every night at 02:00 UTC."""
    log.info("Evolution scheduler: started")
    while True:
        await _wait_until_next_run(hour=2)
        await _run_evolution_cycle()


def launch_evolution_scheduler(app=None) -> None:
    """
    Hook to start the scheduler as a background task on app startup.
    Call from server.py lifespan or startup event.
    """
    async def _bg():
        await start_evolution_scheduler()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_bg())
        else:
            loop.create_task(_bg())
    except Exception as e:
        log.warning(f"Could not start evolution scheduler: {e}")
