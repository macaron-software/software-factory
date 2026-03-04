"""
Evolution Scheduler — nightly GA run at 02:00 UTC + RL retraining.

Call start_evolution_scheduler() once at app startup (server.py).

Leader election: only one node runs the nightly cycle.  The first node to set
the Redis key ``leader:evolution`` (NX EX 3600) becomes the leader for that
night.  If Redis is unavailable, every node runs (safe — idempotent GA writes).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

_NODE_ID = os.environ.get("SF_NODE_ID") or socket.gethostname()


async def _try_become_leader(task_name: str, ttl_secs: int = 3600) -> bool:
    """Try to claim leadership for *task_name* via Redis SETNX.

    Returns True if this node is the leader (or Redis is unavailable).
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return True  # single-node: always leader
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=3
        )
        key = f"leader:{task_name}"
        result = await r.set(key, _NODE_ID, nx=True, ex=ttl_secs)
        await r.aclose()
        if result:
            log.info("leader-election: %s → leader is %s", task_name, _NODE_ID)
        else:
            current = None
            try:
                r2 = aioredis.from_url(
                    redis_url, decode_responses=True, socket_connect_timeout=3
                )
                current = await r2.get(key)
                await r2.aclose()
            except Exception:
                pass
            log.info(
                "leader-election: %s → leader is %s, skipping on %s",
                task_name,
                current,
                _NODE_ID,
            )
        return bool(result)
    except Exception as e:
        log.warning(
            "leader-election: Redis error (%s) — assuming leader on %s", e, _NODE_ID
        )
        return True  # fallback: run anyway


async def _wait_until_next_run(hour: int = 2) -> None:
    """Wait until the next occurrence of `hour`:00 UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_secs = (target - now).total_seconds()
    log.info(
        f"Evolution scheduler: next run at {target.isoformat()} (in {wait_secs / 3600:.1f}h)"
    )
    await asyncio.sleep(wait_secs)


async def _run_evolution_cycle() -> None:
    """Run GA evolution on all workflows + RL retraining (leader only)."""
    if not await _try_become_leader("evolution", ttl_secs=3600):
        return
    log.info("Evolution scheduler: starting nightly cycle on %s", _NODE_ID)
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
        log.info(
            f"GA: evolved {len(ga_results)} workflows, best={max(ga_results.values(), default=0):.4f}"
        )
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
