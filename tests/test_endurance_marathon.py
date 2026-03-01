"""
Marathon Endurance Test — 12h / 24h / 36h multi-environment.

Monitors platform health, mission progression, memory, and LLM metrics
continuously across Local, Azure Prod, and OVH Demo.

Usage:
    MARATHON_HOURS=12 pytest tests/test_endurance_marathon.py --live -v -s
    MARATHON_HOURS=24 pytest tests/test_endurance_marathon.py --live -v -s
    MARATHON_HOURS=36 pytest tests/test_endurance_marathon.py --live -v -s

    # Single env:
    MARATHON_ENV=local MARATHON_HOURS=1 pytest tests/test_endurance_marathon.py --live -v -s

    # Run directly (no pytest):
    python3 tests/test_endurance_marathon.py --hours 12
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import pytest

pytestmark = [pytest.mark.endurance, pytest.mark.live]

# ── Configuration ──────────────────────────────────────────────────────────

MARATHON_HOURS = float(os.environ.get("MARATHON_HOURS", "12"))
MARATHON_ENV = os.environ.get("MARATHON_ENV", "all")  # local | azure | ovh | all

ENVS = {
    "local": {
        "url": os.environ.get("LOCAL_URL", "http://localhost:8099"),
        "auth": None,
        "ssh_host": None,
        "container": None,
    },
    "azure": {
        "url": os.environ.get("AZURE_URL", "https://sf.macaron-software.com"),
        "auth": ("admin", os.environ.get("AZURE_PASS", "MacaronAz2026!")),
        "ssh_host": "macaron@4.233.64.30",
        "container": None,  # auto-detected
    },
    "ovh": {
        "url": os.environ.get("OVH_URL", "http://54.36.183.124:8090"),
        "auth": None,
        "ssh_host": "debian@54.36.183.124",
        "container": None,  # auto-detected
    },
}

INTERVALS = {
    "health": 60,       # every 60s
    "missions": 300,    # every 5min
    "memory": 900,      # every 15min
    "snapshot": 1800,   # every 30min
}

RESULTS_DIR = Path(__file__).parent
REPORT_PATH = RESULTS_DIR / "marathon_results_{env}_{hours}h_{date}.json"


# ── Data structures ────────────────────────────────────────────────────────

@dataclass
class HealthResult:
    ts: str
    env: str
    status: str  # ok | error | timeout
    latency_ms: float
    error: str = ""


@dataclass
class MissionSnapshot:
    ts: str
    env: str
    total: int
    running: int
    completed: int
    failed: int
    paused: int
    zombie_count: int  # running > 2h without phase change
    stall_count: int   # running > 15min without progress


@dataclass
class MemorySnapshot:
    ts: str
    env: str
    container: str
    mem_usage_mb: float
    mem_limit_mb: float
    mem_pct: float
    cpu_pct: float
    disk_used_pct: float


@dataclass
class LLMSnapshot:
    ts: str
    env: str
    total_calls: int
    total_tokens: int
    errors: int


@dataclass
class MarathonReport:
    env: str
    hours: float
    start_ts: str
    end_ts: str
    uptime_pct: float
    total_health_checks: int
    failed_health_checks: int
    avg_latency_ms: float
    p99_latency_ms: float
    missions_completed: int
    missions_failed: int
    zombie_incidents: int
    stall_incidents: int
    max_mem_pct: float
    alerts: list = field(default_factory=list)
    health_history: list = field(default_factory=list)
    mission_history: list = field(default_factory=list)
    memory_history: list = field(default_factory=list)
    llm_history: list = field(default_factory=list)


# ── HTTP helpers ───────────────────────────────────────────────────────────

def _http_get(url: str, auth=None, timeout: int = 10) -> tuple[int, float, str]:
    """Returns (status_code, latency_ms, body). 0 status = timeout/error."""
    import urllib.request, urllib.error, ssl, base64
    t0 = time.time()
    try:
        req = urllib.request.Request(url)
        if auth:
            creds = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(500).decode("utf-8", errors="replace")
            latency = (time.time() - t0) * 1000
            return r.status, latency, body
    except Exception as e:
        latency = (time.time() - t0) * 1000
        return 0, latency, str(e)


def _http_get_json(url: str, auth=None, timeout: int = 15) -> tuple[int, float, dict]:
    status, latency, body = _http_get(url, auth=auth, timeout=timeout)
    try:
        return status, latency, json.loads(body)
    except Exception:
        return status, latency, {}


def _ssh_run(host: str, cmd: str, timeout: int = 20) -> str:
    """Run command on remote host via SSH."""
    full = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {host} '{cmd}'"
    try:
        r = subprocess.run(
            ["/bin/bash", "-c", full],
            capture_output=True, text=True, timeout=timeout,
        )
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return str(e)


# ── Collectors ──────────────────────────────────────────────────────────────

def collect_health(env_name: str, env_cfg: dict) -> HealthResult:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    url = env_cfg["url"] + "/api/health"
    status, latency, body = _http_get(url, auth=env_cfg.get("auth"), timeout=10)
    if status == 200:
        return HealthResult(ts, env_name, "ok", latency)
    elif status == 0:
        return HealthResult(ts, env_name, "error", latency, error=body[:200])
    else:
        return HealthResult(ts, env_name, f"http_{status}", latency)


def collect_missions(env_name: str, env_cfg: dict) -> MissionSnapshot:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    url = env_cfg["url"] + "/api/missions"
    _, _, data = _http_get_json(url, auth=env_cfg.get("auth"), timeout=15)

    missions = data if isinstance(data, list) else data.get("missions", [])
    total = len(missions)
    running = sum(1 for m in missions if m.get("status") == "running")
    completed = sum(1 for m in missions if m.get("status") == "completed")
    failed = sum(1 for m in missions if m.get("status") == "failed")
    paused = sum(1 for m in missions if m.get("status") == "paused")

    # Zombie detection: running missions with updated_at > 2h ago
    now = time.time()
    zombies = 0
    stalls = 0
    for m in missions:
        if m.get("status") != "running":
            continue
        ua = m.get("updated_at", "")
        if ua:
            try:
                import dateutil.parser as dp
                age_s = now - dp.parse(ua).timestamp()
            except Exception:
                age_s = 0
            if age_s > 7200:   # > 2h
                zombies += 1
            elif age_s > 900:  # > 15min
                stalls += 1

    return MissionSnapshot(ts, env_name, total, running, completed, failed, paused, zombies, stalls)


def collect_memory(env_name: str, env_cfg: dict) -> Optional[MemorySnapshot]:
    ssh_host = env_cfg.get("ssh_host")
    if not ssh_host:
        return None
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Auto-detect container
    container = env_cfg.get("container")
    if not container:
        out = _ssh_run(ssh_host, "docker ps --format '{{.Names}}' | grep 'platform' | grep -v factory | head -1")
        container = out.strip()
        env_cfg["container"] = container

    if not container or "TIMEOUT" in container:
        return None

    # docker stats
    stats_out = _ssh_run(ssh_host, f"docker stats --no-stream --format '{{{{.MemUsage}}}},{{{{.MemPerc}}}},{{{{.CPUPerc}}}}' {container}")
    disk_out = _ssh_run(ssh_host, "df -h / | tail -1 | awk '{print $5}'")

    mem_mb = 0.0
    mem_limit = 0.0
    mem_pct = 0.0
    cpu_pct = 0.0
    disk_pct = 0.0

    try:
        parts = stats_out.split(",")
        if len(parts) >= 3:
            mem_parts = parts[0].split("/")
            mem_mb = _parse_mem(mem_parts[0].strip())
            mem_limit = _parse_mem(mem_parts[1].strip()) if len(mem_parts) > 1 else 0
            mem_pct = float(parts[1].strip().replace("%", ""))
            cpu_pct = float(parts[2].strip().replace("%", ""))
    except Exception:
        pass

    try:
        disk_pct = float(disk_out.strip().replace("%", ""))
    except Exception:
        pass

    return MemorySnapshot(ts, env_name, container, mem_mb, mem_limit, mem_pct, cpu_pct, disk_pct)


def _parse_mem(s: str) -> float:
    """Parse '256MiB' or '1.2GiB' to MB."""
    s = s.strip()
    if "GiB" in s or "GB" in s:
        return float(s.replace("GiB", "").replace("GB", "").strip()) * 1024
    if "MiB" in s or "MB" in s:
        return float(s.replace("MiB", "").replace("MB", "").strip())
    if "KiB" in s or "KB" in s:
        return float(s.replace("KiB", "").replace("KB", "").strip()) / 1024
    try:
        return float(s)
    except Exception:
        return 0.0


def collect_llm(env_name: str, env_cfg: dict) -> LLMSnapshot:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    url = env_cfg["url"] + "/api/llm/stats"
    _, _, data = _http_get_json(url, auth=env_cfg.get("auth"), timeout=10)
    total_calls = data.get("total_calls", 0) or 0
    total_tokens = data.get("total_tokens", 0) or 0
    errors = data.get("errors", 0) or 0
    return LLMSnapshot(ts, env_name, total_calls, total_tokens, errors)


# ── Marathon runner ────────────────────────────────────────────────────────

def run_marathon(env_name: str, env_cfg: dict, duration_h: float) -> MarathonReport:
    """Run the endurance marathon for one environment."""
    duration_s = duration_h * 3600
    start = time.time()
    start_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    report = MarathonReport(
        env=env_name,
        hours=duration_h,
        start_ts=start_ts,
        end_ts="",
        uptime_pct=0.0,
        total_health_checks=0,
        failed_health_checks=0,
        avg_latency_ms=0.0,
        p99_latency_ms=0.0,
        missions_completed=0,
        missions_failed=0,
        zombie_incidents=0,
        stall_incidents=0,
        max_mem_pct=0.0,
    )

    last_health = 0.0
    last_missions = 0.0
    last_memory = 0.0
    last_snapshot = 0.0
    latencies: list[float] = []

    prev_completed = 0
    prev_failed = 0

    print(f"\n[marathon:{env_name}] Starting {duration_h}h marathon → {env_cfg['url']}")

    while (time.time() - start) < duration_s:
        now = time.time()
        elapsed_min = (now - start) / 60

        # ── Health check (60s) ──
        if now - last_health >= INTERVALS["health"]:
            h = collect_health(env_name, env_cfg)
            report.health_history.append(asdict(h))
            report.total_health_checks += 1
            latencies.append(h.latency_ms)
            if h.status != "ok":
                report.failed_health_checks += 1
                report.alerts.append(f"[{elapsed_min:.0f}min] Health {h.status}: {h.error[:100]}")
                print(f"  ⚠️  [{elapsed_min:.0f}min] health={h.status} latency={h.latency_ms:.0f}ms")
            else:
                print(f"  ✅ [{elapsed_min:.0f}min] health=ok latency={h.latency_ms:.0f}ms")
            last_health = now

        # ── Missions check (5min) ──
        if now - last_missions >= INTERVALS["missions"]:
            ms = collect_missions(env_name, env_cfg)
            report.mission_history.append(asdict(ms))
            delta_completed = ms.completed - prev_completed
            delta_failed = ms.failed - prev_failed
            report.missions_completed += max(0, delta_completed)
            report.missions_failed += max(0, delta_failed)
            prev_completed = ms.completed
            prev_failed = ms.failed
            if ms.zombie_count > 0:
                report.zombie_incidents += ms.zombie_count
                report.alerts.append(f"[{elapsed_min:.0f}min] {ms.zombie_count} zombie missions detected")
                print(f"  🧟 [{elapsed_min:.0f}min] zombies={ms.zombie_count} stalls={ms.stall_count}")
            if ms.stall_count > 0:
                report.stall_incidents += ms.stall_count
            print(f"  📋 [{elapsed_min:.0f}min] missions: total={ms.total} running={ms.running} completed={ms.completed} failed={ms.failed}")
            last_missions = now

        # ── Memory check (15min) ──
        if now - last_memory >= INTERVALS["memory"]:
            mem = collect_memory(env_name, env_cfg)
            if mem:
                report.memory_history.append(asdict(mem))
                report.max_mem_pct = max(report.max_mem_pct, mem.mem_pct)
                if mem.mem_pct > 80:
                    report.alerts.append(f"[{elapsed_min:.0f}min] HIGH MEMORY {mem.mem_pct:.1f}% on {mem.container}")
                    print(f"  🔴 [{elapsed_min:.0f}min] MEM={mem.mem_pct:.1f}% ({mem.mem_usage_mb:.0f}MB) CPU={mem.cpu_pct:.1f}%")
                elif mem.mem_pct > 60:
                    print(f"  🟡 [{elapsed_min:.0f}min] MEM={mem.mem_pct:.1f}% ({mem.mem_usage_mb:.0f}MB) CPU={mem.cpu_pct:.1f}%")
                else:
                    print(f"  💚 [{elapsed_min:.0f}min] MEM={mem.mem_pct:.1f}% ({mem.mem_usage_mb:.0f}MB) CPU={mem.cpu_pct:.1f}%")
                if mem.disk_used_pct > 85:
                    report.alerts.append(f"[{elapsed_min:.0f}min] HIGH DISK {mem.disk_used_pct:.1f}%")
            last_memory = now

        # ── LLM snapshot (30min) ──
        if now - last_snapshot >= INTERVALS["snapshot"]:
            llm = collect_llm(env_name, env_cfg)
            report.llm_history.append(asdict(llm))
            print(f"  🤖 [{elapsed_min:.0f}min] LLM: calls={llm.total_calls} tokens={llm.total_tokens} errors={llm.errors}")
            last_snapshot = now

        time.sleep(10)  # check every 10s to not miss intervals

    # ── Final report ──
    report.end_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if latencies:
        report.avg_latency_ms = sum(latencies) / len(latencies)
        sorted_lat = sorted(latencies)
        p99_idx = int(len(sorted_lat) * 0.99)
        report.p99_latency_ms = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]
    if report.total_health_checks > 0:
        report.uptime_pct = (1 - report.failed_health_checks / report.total_health_checks) * 100

    return report


def save_report(report: MarathonReport) -> Path:
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    path = RESULTS_DIR / f"marathon_results_{report.env}_{report.hours:.0f}h_{date_str}.json"
    path.write_text(json.dumps(asdict(report), indent=2, default=str))
    return path


def print_summary(report: MarathonReport) -> None:
    print(f"\n{'='*60}")
    print(f"MARATHON REPORT — {report.env} — {report.hours}h")
    print(f"{'='*60}")
    print(f"  Uptime:        {report.uptime_pct:.2f}%")
    print(f"  Avg latency:   {report.avg_latency_ms:.1f}ms")
    print(f"  P99 latency:   {report.p99_latency_ms:.1f}ms")
    print(f"  Health checks: {report.total_health_checks} total, {report.failed_health_checks} failed")
    print(f"  Missions:      +{report.missions_completed} completed, +{report.missions_failed} failed")
    print(f"  Zombies:       {report.zombie_incidents} incidents")
    print(f"  Stalls:        {report.stall_incidents} incidents")
    print(f"  Max memory:    {report.max_mem_pct:.1f}%")
    if report.alerts:
        print(f"  Alerts ({len(report.alerts)}):")
        for a in report.alerts[:10]:
            print(f"    ⚠️  {a}")
    overall = "✅ PASS" if report.uptime_pct >= 99.0 and report.zombie_incidents == 0 else "⚠️  ISSUES" if report.uptime_pct >= 95.0 else "❌ FAIL"
    print(f"  Overall:       {overall}")


# ── pytest fixtures & tests ────────────────────────────────────────────────

def _active_envs() -> list[tuple[str, dict]]:
    if MARATHON_ENV == "all":
        return list(ENVS.items())
    if MARATHON_ENV in ENVS:
        return [(MARATHON_ENV, ENVS[MARATHON_ENV])]
    return list(ENVS.items())


@pytest.fixture(scope="module")
def marathon_envs():
    return _active_envs()


class TestMarathonPreCheck:
    """Quick pre-flight checks before the long marathon."""

    def test_all_envs_reachable(self):
        """All environments must respond to health check before marathon."""
        failures = []
        for env_name, env_cfg in _active_envs():
            status, latency, _ = _http_get(
                env_cfg["url"] + "/api/health",
                auth=env_cfg.get("auth"),
                timeout=15,
            )
            if status != 200:
                failures.append(f"{env_name}: HTTP {status} ({latency:.0f}ms)")
            else:
                print(f"  ✅ {env_name}: HTTP {status} ({latency:.0f}ms)")
        assert not failures, f"Envs not reachable: {failures}"

    def test_missions_api_responds(self):
        """Missions API must respond on all envs."""
        failures = []
        for env_name, env_cfg in _active_envs():
            status, _, data = _http_get_json(
                env_cfg["url"] + "/api/missions",
                auth=env_cfg.get("auth"),
            )
            if status != 200:
                failures.append(f"{env_name}: HTTP {status}")
        assert not failures, f"Missions API failing: {failures}"

    def test_agents_api_responds(self):
        """Agents API must respond on all envs."""
        failures = []
        for env_name, env_cfg in _active_envs():
            status, _, _ = _http_get_json(
                env_cfg["url"] + "/api/agents",
                auth=env_cfg.get("auth"),
            )
            if status != 200:
                failures.append(f"{env_name}: HTTP {status}")
        assert not failures, f"Agents API failing: {failures}"


class TestMarathonEndurance:
    """Long-running endurance marathon (MARATHON_HOURS env var)."""

    def test_marathon_local(self):
        """Run marathon against local env."""
        if MARATHON_ENV not in ("all", "local"):
            pytest.skip("Not targeting local env")
        env_cfg = ENVS["local"]
        status, _, _ = _http_get(env_cfg["url"] + "/api/health", timeout=5)
        if status != 200:
            pytest.skip("Local server not running")
        report = run_marathon("local", env_cfg, MARATHON_HOURS)
        path = save_report(report)
        print_summary(report)
        print(f"\n  Report saved: {path}")
        assert report.uptime_pct >= 95.0, f"Local uptime {report.uptime_pct:.1f}% < 95%"
        assert report.zombie_incidents == 0, f"Zombie missions detected: {report.zombie_incidents}"

    def test_marathon_azure(self):
        """Run marathon against Azure prod."""
        if MARATHON_ENV not in ("all", "azure"):
            pytest.skip("Not targeting azure env")
        env_cfg = ENVS["azure"]
        status, _, _ = _http_get(env_cfg["url"] + "/api/health", auth=env_cfg["auth"], timeout=10)
        if status != 200:
            pytest.skip(f"Azure not reachable (HTTP {status})")
        report = run_marathon("azure", env_cfg, MARATHON_HOURS)
        path = save_report(report)
        print_summary(report)
        print(f"\n  Report saved: {path}")
        assert report.uptime_pct >= 99.0, f"Azure uptime {report.uptime_pct:.1f}% < 99%"
        assert report.p99_latency_ms < 5000, f"Azure p99 latency {report.p99_latency_ms:.0f}ms too high"

    def test_marathon_ovh(self):
        """Run marathon against OVH demo."""
        if MARATHON_ENV not in ("all", "ovh"):
            pytest.skip("Not targeting ovh env")
        env_cfg = ENVS["ovh"]
        status, _, _ = _http_get(env_cfg["url"] + "/api/health", timeout=10)
        if status != 200:
            pytest.skip(f"OVH not reachable (HTTP {status})")
        report = run_marathon("ovh", env_cfg, MARATHON_HOURS)
        path = save_report(report)
        print_summary(report)
        print(f"\n  Report saved: {path}")
        assert report.uptime_pct >= 95.0, f"OVH uptime {report.uptime_pct:.1f}% < 95%"


# ── Standalone entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SF Marathon Endurance Test")
    parser.add_argument("--hours", type=float, default=12.0, help="Duration in hours")
    parser.add_argument("--env", choices=["local", "azure", "ovh", "all"], default="all")
    args = parser.parse_args()

    targets = [(args.env, ENVS[args.env])] if args.env != "all" else list(ENVS.items())

    reports = []
    threads = []

    def _run(env_name, env_cfg):
        r = run_marathon(env_name, env_cfg, args.hours)
        path = save_report(r)
        print_summary(r)
        print(f"Report: {path}")
        reports.append(r)

    for env_name, env_cfg in targets:
        t = threading.Thread(target=_run, args=(env_name, env_cfg), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"\n{'='*60}")
    print("ALL ENVIRONMENTS SUMMARY")
    for r in reports:
        status = "✅" if r.uptime_pct >= 99.0 else "⚠️" if r.uptime_pct >= 95.0 else "❌"
        print(f"  {status} {r.env}: uptime={r.uptime_pct:.1f}% p99={r.p99_latency_ms:.0f}ms missions=+{r.missions_completed}")
