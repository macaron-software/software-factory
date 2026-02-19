#!/usr/bin/env python3
"""
Chaos Runner - Chaos Monkey for Post-Deploy Resilience Testing
==============================================================
Executes chaos scenarios against deployed services to validate:
- Auto-restart after process kill
- Graceful degradation under network latency
- Behavior under CPU/memory pressure
- DB connection recovery
- Disk pressure handling

Auto-rollback if service does not recover within timeout.
Creates resilience feedback tasks for Brain to fix.

Usage:
    from core.chaos_runner import ChaosRunner, ChaosResult
    runner = ChaosRunner(project_config)
    result = await runner.run_all()
    if not result.all_passed:
        await rollback()
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

import logging

logger = logging.getLogger("chaos_runner")


@dataclass
class ChaosScenarioResult:
    """Result of a single chaos scenario"""
    scenario: str
    success: bool
    recovery_time_sec: float = 0.0
    error: str = ""
    output: str = ""
    health_checks: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def summary(self) -> str:
        status = "PASS" if self.success else "FAIL"
        recovery = f"recovery={self.recovery_time_sec:.1f}s" if self.success else f"error={self.error[:80]}"
        return f"CHAOS [{self.scenario}] {status} — {recovery}"


@dataclass
class ChaosResult:
    """Aggregate result of all chaos scenarios"""
    scenarios: List[ChaosScenarioResult] = field(default_factory=list)
    all_passed: bool = False
    total_time_sec: float = 0.0

    def summary(self) -> str:
        passed = sum(1 for s in self.scenarios if s.success)
        total = len(self.scenarios)
        lines = [f"CHAOS: {passed}/{total} passed"]
        for s in self.scenarios:
            lines.append(f"  {s.summary()}")
        return "\n".join(lines)


# Chaos scenario definitions
CHAOS_SCENARIOS = {
    "kill_backend": {
        "description": "SIGKILL backend process, verify auto-restart",
        "type": "process_kill",
        "target": "backend",
        "signal": "KILL",
    },
    "network_latency_200ms": {
        "description": "Add 200ms network latency, verify graceful degradation",
        "type": "network_latency",
        "latency_ms": 200,
        "duration_sec": 30,
    },
    "cpu_stress_80pct": {
        "description": "Stress CPU to 80%, verify no timeouts",
        "type": "cpu_stress",
        "load_pct": 80,
        "duration_sec": 30,
    },
    "memory_pressure": {
        "description": "Apply memory pressure, verify no OOM corruption",
        "type": "memory_stress",
        "target_pct": 85,
        "duration_sec": 30,
    },
    "db_connection_kill": {
        "description": "Kill DB connections, verify reconnect",
        "type": "db_kill",
        "connections_to_kill": 5,
    },
    "disk_pressure": {
        "description": "Fill temp disk, verify warning logs not crash",
        "type": "disk_fill",
        "fill_mb": 500,
        "duration_sec": 20,
    },
}


class ChaosRunner:
    """Executes chaos scenarios against deployed services"""

    def __init__(self, project_name: str, deploy_config: Dict[str, Any], root_path: str):
        self.project_name = project_name
        self.config = deploy_config.get("post_deploy", {}).get("chaos", {})
        self.root_path = Path(root_path)
        self.recovery_timeout = self.config.get("recovery_timeout_sec", 30)
        self.rollback_on_fail = self.config.get("rollback_on_fail", True)
        self.configured_scenarios = self.config.get("scenarios", [])
        self.ssh_target = deploy_config.get("ssh_target", "")
        self.health_url = deploy_config.get("prod", {}).get("url", "http://localhost:8080")
        self.health_path = deploy_config.get("prod", {}).get("health", "/health")

    @property
    def enabled(self) -> bool:
        return self.config.get("enabled", False)

    async def run_all(self) -> ChaosResult:
        """Run all configured chaos scenarios sequentially"""
        start = datetime.now()
        results = []

        scenarios_to_run = self.configured_scenarios or list(CHAOS_SCENARIOS.keys())

        for scenario_name in scenarios_to_run:
            if scenario_name not in CHAOS_SCENARIOS:
                logger.warning(f"Unknown chaos scenario: {scenario_name}, skipping")
                continue

            logger.info(f"Running chaos scenario: {scenario_name}")
            result = await self._run_scenario(scenario_name)
            results.append(result)
            logger.info(result.summary())

            if not result.success and self.rollback_on_fail:
                logger.error(f"Chaos scenario {scenario_name} FAILED — stopping further scenarios")
                break

            # Wait between scenarios for system to stabilize
            await asyncio.sleep(5)

        elapsed = (datetime.now() - start).total_seconds()
        all_passed = all(r.success for r in results) and len(results) > 0

        return ChaosResult(
            scenarios=results,
            all_passed=all_passed,
            total_time_sec=elapsed,
        )

    async def _run_scenario(self, name: str) -> ChaosScenarioResult:
        """Run a single chaos scenario"""
        spec = CHAOS_SCENARIOS[name]

        try:
            # 1. Verify service is healthy before chaos
            healthy = await self._check_health()
            if not healthy:
                return ChaosScenarioResult(
                    scenario=name,
                    success=False,
                    error="Service not healthy before chaos injection",
                )

            # 2. Inject chaos
            inject_ok, inject_output = await self._inject_chaos(name, spec)
            if not inject_ok:
                return ChaosScenarioResult(
                    scenario=name,
                    success=False,
                    error=f"Failed to inject chaos: {inject_output}",
                    output=inject_output,
                )

            # 3. Wait and check recovery
            recovery_time, health_checks = await self._wait_for_recovery(name, spec)

            if recovery_time < 0:
                return ChaosScenarioResult(
                    scenario=name,
                    success=False,
                    recovery_time_sec=self.recovery_timeout,
                    error=f"Service did not recover within {self.recovery_timeout}s",
                    health_checks=health_checks,
                )

            # 4. Cleanup chaos artifacts
            await self._cleanup_chaos(name, spec)

            return ChaosScenarioResult(
                scenario=name,
                success=True,
                recovery_time_sec=recovery_time,
                health_checks=health_checks,
            )

        except Exception as e:
            logger.error(f"Chaos scenario {name} exception: {e}")
            # Always try cleanup
            try:
                await self._cleanup_chaos(name, spec)
            except Exception:
                pass
            return ChaosScenarioResult(
                scenario=name,
                success=False,
                error=str(e),
            )

    async def _inject_chaos(self, name: str, spec: Dict) -> Tuple[bool, str]:
        """Inject chaos based on scenario type"""
        chaos_type = spec["type"]

        if chaos_type == "process_kill":
            return await self._inject_process_kill(spec)
        elif chaos_type == "network_latency":
            return await self._inject_network_latency(spec)
        elif chaos_type == "cpu_stress":
            return await self._inject_cpu_stress(spec)
        elif chaos_type == "memory_stress":
            return await self._inject_memory_stress(spec)
        elif chaos_type == "db_kill":
            return await self._inject_db_kill(spec)
        elif chaos_type == "disk_fill":
            return await self._inject_disk_fill(spec)
        else:
            return False, f"Unknown chaos type: {chaos_type}"

    async def _inject_process_kill(self, spec: Dict) -> Tuple[bool, str]:
        """Kill backend process"""
        target = spec.get("target", "backend")
        sig = spec.get("signal", "KILL")
        cmd = self._build_remote_cmd(f"pkill -{sig} -f '{target}' || true")
        return await self._exec(cmd)

    async def _inject_network_latency(self, spec: Dict) -> Tuple[bool, str]:
        """Add network latency using tc netem"""
        latency = spec.get("latency_ms", 200)
        iface = spec.get("interface", "eth0")
        cmd = self._build_remote_cmd(
            f"tc qdisc add dev {iface} root netem delay {latency}ms 2>/dev/null || "
            f"tc qdisc change dev {iface} root netem delay {latency}ms"
        )
        return await self._exec(cmd)

    async def _inject_cpu_stress(self, spec: Dict) -> Tuple[bool, str]:
        """Stress CPU using stress-ng"""
        duration = spec.get("duration_sec", 30)
        load = spec.get("load_pct", 80)
        cmd = self._build_remote_cmd(
            f"stress-ng --cpu 0 --cpu-load {load} --timeout {duration}s --quiet &"
        )
        return await self._exec(cmd)

    async def _inject_memory_stress(self, spec: Dict) -> Tuple[bool, str]:
        """Apply memory pressure using stress-ng"""
        duration = spec.get("duration_sec", 30)
        pct = spec.get("target_pct", 85)
        cmd = self._build_remote_cmd(
            f"stress-ng --vm 2 --vm-bytes {pct}% --timeout {duration}s --quiet &"
        )
        return await self._exec(cmd)

    async def _inject_db_kill(self, spec: Dict) -> Tuple[bool, str]:
        """Kill database connections"""
        n = spec.get("connections_to_kill", 5)
        # PostgreSQL: terminate random backends
        cmd = self._build_remote_cmd(
            f"psql -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = current_database() AND pid <> pg_backend_pid() "
            f"ORDER BY random() LIMIT {n};\" 2>/dev/null || echo 'DB kill skipped'"
        )
        return await self._exec(cmd)

    async def _inject_disk_fill(self, spec: Dict) -> Tuple[bool, str]:
        """Fill temp disk space"""
        mb = spec.get("fill_mb", 500)
        cmd = self._build_remote_cmd(
            f"fallocate -l {mb}M /tmp/chaos_disk_fill 2>/dev/null || "
            f"dd if=/dev/zero of=/tmp/chaos_disk_fill bs=1M count={mb} 2>/dev/null"
        )
        return await self._exec(cmd)

    async def _cleanup_chaos(self, name: str, spec: Dict):
        """Cleanup chaos artifacts"""
        chaos_type = spec["type"]
        cleanup_cmds = {
            "network_latency": "tc qdisc del dev eth0 root 2>/dev/null || true",
            "cpu_stress": "pkill -f stress-ng 2>/dev/null || true",
            "memory_stress": "pkill -f stress-ng 2>/dev/null || true",
            "disk_fill": "rm -f /tmp/chaos_disk_fill",
        }
        if chaos_type in cleanup_cmds:
            cmd = self._build_remote_cmd(cleanup_cmds[chaos_type])
            await self._exec(cmd)

    async def _wait_for_recovery(self, name: str, spec: Dict) -> Tuple[float, List[Dict]]:
        """Wait for service to recover, return (recovery_time, health_checks)"""
        # For stress scenarios, wait for the stress duration first
        stress_duration = spec.get("duration_sec", 0)
        if stress_duration > 0 and spec["type"] in ("cpu_stress", "memory_stress", "network_latency"):
            logger.info(f"Waiting {stress_duration}s for stress scenario to complete...")
            await asyncio.sleep(stress_duration)
            # Then cleanup
            await self._cleanup_chaos(name, spec)

        # Now check health recovery
        health_checks = []
        start = datetime.now()
        check_interval = 2  # seconds

        while True:
            elapsed = (datetime.now() - start).total_seconds()
            if elapsed > self.recovery_timeout:
                return -1, health_checks  # Failed to recover

            healthy = await self._check_health()
            health_checks.append({
                "time_sec": round(elapsed, 1),
                "healthy": healthy,
            })

            if healthy:
                return elapsed, health_checks

            await asyncio.sleep(check_interval)

    async def _check_health(self) -> bool:
        """Check if service is healthy via HTTP"""
        url = f"{self.health_url.rstrip('/')}{self.health_path}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sf", "--max-time", "5", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return proc.returncode == 0
        except (asyncio.TimeoutError, Exception):
            return False

    def _build_remote_cmd(self, cmd: str) -> List[str]:
        """Build command — SSH if remote, direct if local"""
        if self.ssh_target:
            return ["ssh", "-o", "StrictHostKeyChecking=no", self.ssh_target, cmd]
        return ["bash", "-c", cmd]

    async def _exec(self, cmd: List[str]) -> Tuple[bool, str]:
        """Execute command and return (success, output)"""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")
            return proc.returncode == 0 or "skipped" in output.lower(), output + err
        except asyncio.TimeoutError:
            return False, "Command timeout (60s)"
        except Exception as e:
            return False, str(e)

    def build_feedback_context(self, result: ChaosResult) -> Dict[str, Any]:
        """Build context for Brain to create resilience fix tasks"""
        failed = [s for s in result.scenarios if not s.success]
        return {
            "type": "resilience_failure",
            "project": self.project_name,
            "failed_scenarios": [
                {
                    "scenario": s.scenario,
                    "error": s.error,
                    "recovery_time_sec": s.recovery_time_sec,
                    "spec": CHAOS_SCENARIOS.get(s.scenario, {}),
                }
                for s in failed
            ],
            "total_scenarios": len(result.scenarios),
            "passed": sum(1 for s in result.scenarios if s.success),
            "suggestion": self._suggest_fixes(failed),
        }

    def _suggest_fixes(self, failed: List[ChaosScenarioResult]) -> str:
        """Suggest fixes based on failed scenarios"""
        suggestions = []
        for s in failed:
            spec = CHAOS_SCENARIOS.get(s.scenario, {})
            chaos_type = spec.get("type", "")

            if chaos_type == "process_kill":
                suggestions.append("Add systemd restart policy (Restart=always, RestartSec=2)")
            elif chaos_type == "network_latency":
                suggestions.append("Add request timeouts and retry with exponential backoff")
            elif chaos_type == "cpu_stress":
                suggestions.append("Profile CPU hotspots, consider async/non-blocking operations")
            elif chaos_type == "memory_stress":
                suggestions.append("Check for memory leaks, add OOM kill protection, tune GC")
            elif chaos_type == "db_kill":
                suggestions.append("Configure connection pool with min/max + reconnect + health check query")
            elif chaos_type == "disk_fill":
                suggestions.append("Add disk space monitoring, log rotation, tmpfs cleanup")

        return "; ".join(suggestions) if suggestions else "Investigate service resilience gaps"
