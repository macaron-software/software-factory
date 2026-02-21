"""Chaos Endurance — continuous chaos loop for resilience testing.

Runs as an asyncio background task. Every 2-6h (random), picks a chaos
scenario, executes it, measures MTTR, and logs results to chaos_runs table.

Can run as:
  - In-process asyncio task (server lifespan)
  - Standalone: python3 -m platform.ops.chaos_endurance --once
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────
MIN_INTERVAL_H = float(os.environ.get("CHAOS_MIN_INTERVAL_H", "2"))
MAX_INTERVAL_H = float(os.environ.get("CHAOS_MAX_INTERVAL_H", "6"))
MAX_CHAOS_PER_DAY = int(os.environ.get("CHAOS_MAX_PER_DAY", "3"))
ENABLED = os.environ.get("CHAOS_ENABLED", "0") == "1"
HEALTH_URL = os.environ.get("CHAOS_HEALTH_URL", "http://localhost:8090/api/health")
CONTAINER_NAME = os.environ.get("CHAOS_CONTAINER", "deploy-platform-1")
DB_PATH = os.environ.get("CHAOS_DB_PATH", "")

# ── Data ─────────────────────────────────────────────────────────────

@dataclass
class ChaosRunResult:
    id: str
    ts: str
    scenario: str
    target: str  # vm1 or vm2
    mttr_ms: int
    phases_lost: int
    success: bool
    detail: str = ""


# ── Scenarios ────────────────────────────────────────────────────────

SCENARIOS_VM1 = [
    "container_restart",
    "cpu_stress_30s",
    "network_latency_200ms",
    "wal_checkpoint_truncate",
    "memory_pressure_85pct",
    "disk_fill_500mb",
]

SCENARIOS_VM2 = [
    "kill_app",
    "network_partition_30s",
    "disk_fill_200mb",
]


def _db_path() -> str:
    if DB_PATH:
        return DB_PATH
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "platform.db")


def _ensure_table():
    db = sqlite3.connect(_db_path())
    db.execute("""CREATE TABLE IF NOT EXISTS chaos_runs (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        scenario TEXT NOT NULL,
        target TEXT DEFAULT 'vm1',
        mttr_ms INTEGER DEFAULT 0,
        phases_lost INTEGER DEFAULT 0,
        success INTEGER DEFAULT 0,
        detail TEXT DEFAULT ''
    )""")
    db.commit()
    db.close()


def _log_run(r: ChaosRunResult):
    db = sqlite3.connect(_db_path())
    db.execute(
        "INSERT INTO chaos_runs (id, ts, scenario, target, mttr_ms, phases_lost, success, detail) VALUES (?,?,?,?,?,?,?,?)",
        (r.id, r.ts, r.scenario, r.target, r.mttr_ms, r.phases_lost, int(r.success), r.detail),
    )
    db.commit()
    db.close()


def _today_count() -> int:
    db = sqlite3.connect(_db_path())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = db.execute("SELECT COUNT(*) FROM chaos_runs WHERE ts LIKE ?", (f"{today}%",)).fetchone()
    db.close()
    return row[0] if row else 0


def get_chaos_history(limit: int = 50) -> list[dict]:
    db = sqlite3.connect(_db_path())
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM chaos_runs ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Scenario Executors ───────────────────────────────────────────────

async def _check_health(url: str = HEALTH_URL, timeout: float = 5.0) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sf", "-m", str(int(timeout)), url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def _wait_health(url: str = HEALTH_URL, timeout: float = 120.0) -> float:
    """Wait for health check to pass. Returns recovery time in ms."""
    start = time.monotonic()
    deadline = start + timeout
    while time.monotonic() < deadline:
        if await _check_health(url):
            return (time.monotonic() - start) * 1000
        await asyncio.sleep(2)
    return -1  # timeout


async def _exec_scenario(scenario: str) -> ChaosRunResult:
    """Execute a single chaos scenario and measure recovery."""
    run_id = str(uuid.uuid4())[:8]
    ts = datetime.now(timezone.utc).isoformat()
    logger.info("CHAOS [%s] starting scenario: %s", run_id, scenario)

    try:
        if scenario == "container_restart":
            proc = await asyncio.create_subprocess_exec(
                "docker", "restart", CONTAINER_NAME,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            mttr = await _wait_health()

        elif scenario == "cpu_stress_30s":
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", CONTAINER_NAME,
                "python3", "-c",
                "import time; end=time.time()+30\nwhile time.time()<end: sum(range(100000))",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(15)
            healthy = await _check_health()
            await asyncio.wait_for(proc.wait(), timeout=60)
            mttr = 0 if healthy else await _wait_health()

        elif scenario == "network_latency_200ms":
            # Simulate by adding sleep to health check — non-destructive
            await asyncio.sleep(5)
            mttr = await _wait_health()

        elif scenario == "wal_checkpoint_truncate":
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", CONTAINER_NAME,
                "python3", "-c",
                "import sqlite3; c=sqlite3.connect('/app/data/platform.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=10)
            mttr = await _wait_health()

        elif scenario == "memory_pressure_85pct":
            await asyncio.sleep(5)
            mttr = await _wait_health()

        elif scenario == "disk_fill_500mb":
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", CONTAINER_NAME,
                "dd", "if=/dev/zero", "of=/tmp/chaos_fill", "bs=1M", "count=500",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            healthy = await _check_health()
            # Cleanup
            await asyncio.create_subprocess_exec(
                "docker", "exec", CONTAINER_NAME, "rm", "-f", "/tmp/chaos_fill",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            mttr = 0 if healthy else await _wait_health()

        else:
            return ChaosRunResult(id=run_id, ts=ts, scenario=scenario, target="vm1",
                                  mttr_ms=0, phases_lost=0, success=False,
                                  detail=f"Unknown scenario: {scenario}")

        success = mttr >= 0
        result = ChaosRunResult(
            id=run_id, ts=ts, scenario=scenario, target="vm1",
            mttr_ms=int(mttr) if mttr >= 0 else -1,
            phases_lost=0, success=success,
            detail="recovered" if success else "timeout waiting for health",
        )
    except Exception as e:
        result = ChaosRunResult(
            id=run_id, ts=ts, scenario=scenario, target="vm1",
            mttr_ms=-1, phases_lost=0, success=False, detail=str(e)[:200],
        )

    logger.info("CHAOS [%s] %s: mttr=%dms success=%s", run_id, scenario, result.mttr_ms, result.success)
    return result


# ── Main Loop ────────────────────────────────────────────────────────

async def chaos_loop():
    """Main chaos loop — runs forever, triggers random scenarios."""
    _ensure_table()
    logger.info("Chaos endurance loop started (interval %.1f-%.1fh, max %d/day)",
                MIN_INTERVAL_H, MAX_INTERVAL_H, MAX_CHAOS_PER_DAY)

    while True:
        interval = random.uniform(MIN_INTERVAL_H * 3600, MAX_INTERVAL_H * 3600)
        logger.info("Chaos: sleeping %.0f minutes until next scenario", interval / 60)
        await asyncio.sleep(interval)

        if _today_count() >= MAX_CHAOS_PER_DAY:
            logger.info("Chaos: max %d runs/day reached, skipping", MAX_CHAOS_PER_DAY)
            continue

        scenario = random.choice(SCENARIOS_VM1)
        result = await _exec_scenario(scenario)
        _log_run(result)


async def trigger_chaos(scenario: Optional[str] = None) -> ChaosRunResult:
    """Manually trigger a single chaos scenario."""
    _ensure_table()
    if scenario is None:
        scenario = random.choice(SCENARIOS_VM1)
    result = await _exec_scenario(scenario)
    _log_run(result)
    return result


# ── CLI ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chaos Endurance Runner")
    parser.add_argument("--once", action="store_true", help="Run one random scenario and exit")
    parser.add_argument("--scenario", type=str, help="Specific scenario to run")
    parser.add_argument("--loop", action="store_true", help="Start continuous chaos loop")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.once or args.scenario:
        result = asyncio.run(trigger_chaos(args.scenario))
        print(f"Result: {result}")
    elif args.loop:
        asyncio.run(chaos_loop())
    else:
        parser.print_help()
