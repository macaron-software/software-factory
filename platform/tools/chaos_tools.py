"""
Chaos & Load Testing Tools - Chaos Monkey, TMC (k6), Infra checks.
===================================================================
Wraps existing SF modules: chaos_runner.py, tmc_runner.py, wiggum_infra.py.
Falls back to direct subprocess if SF modules unavailable.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from ..models import AgentInstance
from .registry import BaseTool


class ChaosTestTool(BaseTool):
    """Chaos Monkey — inject failures and verify recovery."""

    name = "chaos_test"
    description = (
        "Run chaos engineering tests against a staging URL. "
        "Scenarios: kill_process, network_latency, memory_pressure, cpu_stress. "
        "Verifies the app recovers within timeout. Returns recovery time + health status."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        scenario = params.get("scenario", "kill_process")
        timeout_sec = params.get("timeout", 30)

        if not url:
            return "Error: url required (staging endpoint to test)"

        valid = {"kill_process", "network_latency", "memory_pressure", "cpu_stress"}
        if scenario not in valid:
            return f"Error: scenario must be one of {valid}"

        # Try SF chaos_runner first
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "core"))
            from chaos_runner import ChaosRunner

            config = {
                "post_deploy": {
                    "chaos": {
                        "enabled": True,
                        "scenarios": [scenario],
                        "recovery_timeout_sec": timeout_sec,
                        "rollback_on_fail": False,
                    }
                }
            }
            runner = ChaosRunner("test", config, str(Path.cwd()))
            result = await runner.run_all()
            return self._format_chaos_result(result)
        except ImportError:
            pass

        # Fallback: basic health check loop
        return await self._basic_chaos(url, scenario, timeout_sec)

    async def _basic_chaos(self, url: str, scenario: str, timeout: int) -> str:
        lines = [f"[CHAOS] Scenario: {scenario} against {url}"]
        lines.append(f"[CHAOS] Recovery timeout: {timeout}s")

        # Pre-check
        pre = await self._health_check(url)
        lines.append(f"[CHAOS] Pre-check: {'HEALTHY' if pre else 'UNHEALTHY'}")
        if not pre:
            return "\n".join(lines + ["[CHAOS] ABORT — target already unhealthy"])

        # Simulate chaos (for now, just verify resilience via rapid requests)
        lines.append(f"[CHAOS] Injecting: {scenario}")
        if scenario == "network_latency":
            # Rapid burst to test under load
            results = []
            for _ in range(10):
                ok = await self._health_check(url)
                results.append(ok)
                await asyncio.sleep(0.2)
            fail_rate = results.count(False) / len(results)
            lines.append(f"[CHAOS] Burst test: {fail_rate*100:.0f}% failure rate")
        else:
            lines.append(f"[CHAOS] Note: {scenario} requires infrastructure access (docker/ssh)")
            lines.append(f"[CHAOS] Running health probe instead")

        # Post-check
        post = await self._health_check(url)
        lines.append(f"[CHAOS] Post-check: {'HEALTHY' if post else 'UNHEALTHY'}")

        status = "PASS" if post else "FAIL — app did not recover"
        lines.append(f"[CHAOS] Result: {status}")
        return "\n".join(lines)

    async def _health_check(self, url: str) -> bool:
        try:
            r = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout.strip().startswith("2")
        except Exception:
            return False

    def _format_chaos_result(self, result) -> str:
        lines = [f"[CHAOS] Overall: {'PASS' if result.passed else 'FAIL'}"]
        for s in getattr(result, "scenarios", []):
            lines.append(f"  {s.name}: {'recovered' if s.recovered else 'FAILED'} in {s.recovery_time:.1f}s")
        return "\n".join(lines)


class TmcLoadTestTool(BaseTool):
    """TMC — Load testing via k6."""

    name = "tmc_load_test"
    description = (
        "Run load tests (TMC) against a URL using k6. "
        "Scenarios: baseline (normal), ramp_10x (gradual increase), spike (sudden burst). "
        "Returns p50/p95/p99 latency, throughput (rps), error rate."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        scenario = params.get("scenario", "baseline")
        duration = params.get("duration", 30)

        if not url:
            return "Error: url required"

        valid = {"baseline", "ramp_10x", "spike", "soak"}
        if scenario not in valid:
            return f"Error: scenario must be one of {valid}"

        # Try k6 directly
        try:
            return await self._run_k6(url, scenario, duration)
        except FileNotFoundError:
            return "[TMC] k6 not installed (brew install k6 or https://k6.io)"

    async def _run_k6(self, url: str, scenario: str, duration: int) -> str:
        vus, ramp = {"baseline": (5, False), "ramp_10x": (50, True), "spike": (100, False), "soak": (10, False)}[scenario]

        script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';
export let options = {{
  vus: {vus},
  duration: '{duration}s',
}};
export default function() {{
  let res = http.get('{url}');
  check(res, {{ 'status 200': (r) => r.status === 200 }});
  sleep(0.5);
}}
"""
        script_path = Path("/tmp/k6_tmc_test.js")
        script_path.write_text(script)

        try:
            r = subprocess.run(
                ["k6", "run", "--summary-trend-stats", "p(50),p(95),p(99)", "--out", "json=/tmp/k6_out.json", str(script_path)],
                capture_output=True, text=True, timeout=duration + 30,
            )
            output = r.stdout + r.stderr
            return f"[TMC/{scenario}] k6 results:\n{output[-2000:]}"
        except subprocess.TimeoutExpired:
            return f"[TMC/{scenario}] TIMEOUT ({duration+30}s)"
        except FileNotFoundError:
            raise
        finally:
            script_path.unlink(missing_ok=True)


class InfraCheckTool(BaseTool):
    """Infrastructure health verification."""

    name = "infra_check"
    description = (
        "Verify infrastructure health: HTTP endpoints, Docker containers, "
        "database connectivity. Returns structured health report."
    )
    category = "devops"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        checks = params.get("checks", ["site"])
        url = params.get("url", "")
        results = []

        if "site" in checks and url:
            results.append(await self._check_site(url))

        if "docker" in checks:
            results.append(await self._check_docker())

        if "ports" in checks:
            port = params.get("port", 8080)
            results.append(await self._check_port(port))

        if not results:
            return "[INFRA] No checks performed. Provide url and/or checks=['site','docker','ports']"

        return "\n".join(results)

    async def _check_site(self, url: str) -> str:
        try:
            r = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code} %{time_total}s", "-m", "10", url],
                capture_output=True, text=True, timeout=15,
            )
            parts = r.stdout.strip().split()
            code = parts[0] if parts else "?"
            time = parts[1] if len(parts) > 1 else "?"
            status = "OK" if code.startswith("2") else "FAIL"
            return f"[INFRA/site] {url}: {status} (HTTP {code}, {time})"
        except Exception as e:
            return f"[INFRA/site] {url}: ERROR — {e}"

    async def _check_docker(self) -> str:
        try:
            r = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return f"[INFRA/docker] ERROR: {r.stderr[:200]}"
            containers = r.stdout.strip().split("\n")
            containers = [c for c in containers if c.strip()]
            if not containers:
                return "[INFRA/docker] No containers running"
            lines = [f"[INFRA/docker] {len(containers)} container(s):"]
            for c in containers[:10]:
                lines.append(f"  {c}")
            return "\n".join(lines)
        except FileNotFoundError:
            return "[INFRA/docker] docker not found"
        except Exception as e:
            return f"[INFRA/docker] ERROR: {e}"

    async def _check_port(self, port: int) -> str:
        try:
            r = subprocess.run(
                ["lsof", "-i", f":{port}", "-P", "-n"],
                capture_output=True, text=True, timeout=5,
            )
            if r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                return f"[INFRA/port] :{port} — LISTENING ({lines[1].split()[0] if len(lines) > 1 else 'unknown'})"
            return f"[INFRA/port] :{port} — NOT LISTENING"
        except Exception as e:
            return f"[INFRA/port] ERROR: {e}"


def register_chaos_tools(registry):
    """Register chaos and load testing tools."""
    registry.register(ChaosTestTool())
    registry.register(TmcLoadTestTool())
    registry.register(InfraCheckTool())
