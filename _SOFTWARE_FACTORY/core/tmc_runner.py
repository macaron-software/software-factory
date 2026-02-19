#!/usr/bin/env python3
"""
TMC Runner - Tests de Montee en Charge (Load Testing)
=====================================================
Post-deploy load testing using k6.

Measures baseline performance, runs stress scenarios, and compares results.
Integrates with the deploy pipeline to:
- Capture baseline metrics (p50/p95/p99, throughput, error rate)
- Run ramp-up, spike, soak scenarios
- Compare post-chaos metrics against baseline
- Create perf tasks via Brain feedback loop if bottlenecks found

Usage:
    from core.tmc_runner import TMCRunner, TMCResult
    runner = TMCRunner(project_config)
    baseline = await runner.run_baseline()
    if not baseline.meets_thresholds():
        # create perf feedback task
    post = await runner.run_verify(baseline)
    if post.degraded_vs(baseline, tolerance_pct=15):
        # rollback
"""

import asyncio
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

import logging

logger = logging.getLogger("tmc_runner")


@dataclass
class TMCMetrics:
    """Parsed k6 metrics from JSON output"""
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    throughput_rps: float = 0.0
    error_rate_pct: float = 0.0
    total_requests: int = 0
    total_errors: int = 0
    duration_sec: float = 0.0
    vus_max: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TMCResult:
    """Result of a TMC scenario run"""
    scenario: str
    success: bool
    metrics: TMCMetrics
    threshold_violations: List[str] = field(default_factory=list)
    error: str = ""
    output: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def meets_thresholds(self, thresholds: Dict[str, float] = None) -> bool:
        """Check if metrics meet configured thresholds"""
        if not thresholds:
            return self.success and not self.threshold_violations

        violations = []
        m = self.metrics

        if "p95_latency_ms" in thresholds and m.p95_ms > thresholds["p95_latency_ms"]:
            violations.append(f"p95={m.p95_ms:.0f}ms > {thresholds['p95_latency_ms']}ms")

        if "error_rate_pct" in thresholds and m.error_rate_pct > thresholds["error_rate_pct"]:
            violations.append(f"error_rate={m.error_rate_pct:.1f}% > {thresholds['error_rate_pct']}%")

        if "min_throughput_rps" in thresholds and m.throughput_rps < thresholds["min_throughput_rps"]:
            violations.append(f"throughput={m.throughput_rps:.0f}rps < {thresholds['min_throughput_rps']}rps")

        self.threshold_violations = violations
        return len(violations) == 0

    def degraded_vs(self, baseline: "TMCResult", tolerance_pct: float = 15.0) -> bool:
        """Check if metrics degraded compared to baseline beyond tolerance"""
        if not baseline or not baseline.metrics:
            return False

        b = baseline.metrics
        m = self.metrics

        # p95 degradation
        if b.p95_ms > 0:
            p95_change = ((m.p95_ms - b.p95_ms) / b.p95_ms) * 100
            if p95_change > tolerance_pct:
                logger.warning(f"p95 degraded: {b.p95_ms:.0f}ms → {m.p95_ms:.0f}ms (+{p95_change:.0f}%)")
                return True

        # error rate increase
        if m.error_rate_pct > b.error_rate_pct + 1.0:  # absolute 1% tolerance
            logger.warning(f"Error rate increased: {b.error_rate_pct:.1f}% → {m.error_rate_pct:.1f}%")
            return True

        # throughput drop
        if b.throughput_rps > 0:
            rps_change = ((b.throughput_rps - m.throughput_rps) / b.throughput_rps) * 100
            if rps_change > tolerance_pct:
                logger.warning(f"Throughput dropped: {b.throughput_rps:.0f}rps → {m.throughput_rps:.0f}rps (-{rps_change:.0f}%)")
                return True

        return False

    def summary(self) -> str:
        """Human-readable summary"""
        m = self.metrics
        status = "PASS" if self.success else "FAIL"
        lines = [
            f"TMC [{self.scenario}] {status}",
            f"  p50={m.p50_ms:.0f}ms  p95={m.p95_ms:.0f}ms  p99={m.p99_ms:.0f}ms",
            f"  throughput={m.throughput_rps:.0f}rps  errors={m.error_rate_pct:.1f}%  reqs={m.total_requests}",
        ]
        if self.threshold_violations:
            lines.append(f"  VIOLATIONS: {', '.join(self.threshold_violations)}")
        return "\n".join(lines)


class TMCRunner:
    """Runs k6 load testing scenarios and parses results"""

    def __init__(self, project_name: str, deploy_config: Dict[str, Any], root_path: str):
        self.project_name = project_name
        self.config = deploy_config.get("post_deploy", {}).get("tmc", {})
        self.root_path = Path(root_path)
        self.tool = self.config.get("tool", "k6")
        self.thresholds = self.config.get("thresholds", {})
        self.scenarios = self.config.get("scenarios", ["baseline"])
        self.duration_sec = self.config.get("duration_sec", 120)

    @property
    def enabled(self) -> bool:
        return self.config.get("enabled", False)

    async def run_baseline(self) -> TMCResult:
        """Run baseline scenario to capture reference metrics"""
        return await self._run_scenario("baseline")

    async def run_ramp(self) -> TMCResult:
        """Run ramp-up scenario (10x normal load)"""
        return await self._run_scenario("ramp_10x")

    async def run_spike(self) -> TMCResult:
        """Run spike scenario (sudden burst)"""
        return await self._run_scenario("spike")

    async def run_soak(self) -> TMCResult:
        """Run soak scenario (sustained load, detect memory leaks)"""
        return await self._run_scenario("soak")

    async def run_verify(self, baseline: TMCResult) -> TMCResult:
        """Run verification after chaos — compare against baseline"""
        result = await self._run_scenario("baseline")
        if baseline:
            result.degraded_vs(baseline, tolerance_pct=15.0)
        return result

    async def run_all_scenarios(self) -> List[TMCResult]:
        """Run all configured scenarios"""
        results = []
        for scenario in self.scenarios:
            result = await self._run_scenario(scenario)
            results.append(result)
            if not result.success:
                logger.warning(f"Scenario {scenario} failed, stopping")
                break
        return results

    async def _run_scenario(self, scenario: str) -> TMCResult:
        """Run a single k6 scenario"""
        script_path = self._get_script_path(scenario)

        if not script_path.exists():
            # Generate default k6 script if none exists
            script_path = await self._generate_default_script(scenario)

        logger.info(f"Running TMC scenario: {scenario} (tool={self.tool}, duration={self.duration_sec}s)")

        try:
            result = await self._run_k6(script_path, scenario)
            result.meets_thresholds(self.thresholds)
            logger.info(f"TMC result:\n{result.summary()}")
            return result
        except Exception as e:
            logger.error(f"TMC scenario {scenario} error: {e}")
            return TMCResult(
                scenario=scenario,
                success=False,
                metrics=TMCMetrics(),
                error=str(e),
            )

    async def _run_k6(self, script_path: Path, scenario: str) -> TMCResult:
        """Execute k6 and parse JSON output"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json_output = f.name

        cmd = [
            "k6", "run",
            "--out", f"json={json_output}",
            "--summary-export", json_output,
            "--duration", f"{self.duration_sec}s",
            str(script_path),
        ]

        # Add scenario-specific env vars
        env_vars = self._scenario_env(scenario)
        env_str = " ".join(f"{k}={v}" for k, v in env_vars.items())
        if env_str:
            cmd = ["env"] + [f"{k}={v}" for k, v in env_vars.items()] + cmd

        timeout = self.duration_sec + 60  # buffer

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.root_path),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            # Parse k6 JSON summary
            metrics = self._parse_k6_summary(json_output)

            success = proc.returncode == 0
            return TMCResult(
                scenario=scenario,
                success=success,
                metrics=metrics,
                output=output[:5000],
                error=err[:2000] if not success else "",
            )
        except asyncio.TimeoutError:
            return TMCResult(
                scenario=scenario,
                success=False,
                metrics=TMCMetrics(),
                error=f"Timeout after {timeout}s",
            )
        finally:
            Path(json_output).unlink(missing_ok=True)

    def _parse_k6_summary(self, json_path: str) -> TMCMetrics:
        """Parse k6 --summary-export JSON"""
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return TMCMetrics()

        metrics = data.get("metrics", {})

        # http_req_duration contains percentile data
        duration = metrics.get("http_req_duration", {}).get("values", {})
        reqs = metrics.get("http_reqs", {}).get("values", {})
        failures = metrics.get("http_req_failed", {}).get("values", {})

        total_reqs = int(reqs.get("count", 0))
        fail_rate = failures.get("rate", 0.0)
        test_duration = data.get("state", {}).get("testRunDurationMs", 0) / 1000.0

        return TMCMetrics(
            p50_ms=duration.get("med", 0.0),
            p95_ms=duration.get("p(95)", 0.0),
            p99_ms=duration.get("p(99)", 0.0),
            avg_ms=duration.get("avg", 0.0),
            min_ms=duration.get("min", 0.0),
            max_ms=duration.get("max", 0.0),
            throughput_rps=total_reqs / test_duration if test_duration > 0 else 0,
            error_rate_pct=fail_rate * 100,
            total_requests=total_reqs,
            total_errors=int(total_reqs * fail_rate),
            duration_sec=test_duration,
            vus_max=data.get("state", {}).get("vusMax", 0),
            raw=data,
        )

    def _get_script_path(self, scenario: str) -> Path:
        """Get k6 script path for scenario"""
        custom = self.config.get("script")
        if custom:
            return self.root_path / custom

        # Convention: tests/load/<scenario>.js
        return self.root_path / "tests" / "load" / f"{scenario}.js"

    async def _generate_default_script(self, scenario: str) -> Path:
        """Generate a default k6 script for the scenario"""
        scripts_dir = self.root_path / "tests" / "load"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"{scenario}.js"

        # Determine target URL from deploy config
        prod_url = "http://localhost:8080"
        # Try to get from project config
        deploy = self.config
        if hasattr(self, '_deploy_config_full'):
            prod_url = self._deploy_config_full.get("prod", {}).get("url", prod_url)

        vus, duration = self._scenario_params(scenario)

        script = f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  stages: {self._scenario_stages_js(scenario, vus, duration)},
  thresholds: {{
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  }},
}};

const BASE_URL = __ENV.TMC_TARGET_URL || '{prod_url}';

export default function () {{
  const res = http.get(`${{BASE_URL}}/health`);
  check(res, {{
    'status 200': (r) => r.status === 200,
    'duration < 500ms': (r) => r.timings.duration < 500,
  }});
  sleep(0.5);
}}
"""
        script_path.write_text(script)
        logger.info(f"Generated default k6 script: {script_path}")
        return script_path

    def _scenario_params(self, scenario: str) -> tuple:
        """Return (vus, duration_sec) for scenario"""
        params = {
            "baseline": (10, self.duration_sec),
            "ramp_10x": (100, self.duration_sec),
            "spike": (200, 60),
            "soak": (20, 300),
        }
        return params.get(scenario, (10, self.duration_sec))

    def _scenario_stages_js(self, scenario: str, vus: int, duration: int) -> str:
        """Generate k6 stages array for scenario"""
        if scenario == "baseline":
            return f"[{{ duration: '{duration}s', target: {vus} }}]"
        elif scenario == "ramp_10x":
            ramp = duration // 3
            return (
                f"[{{ duration: '{ramp}s', target: {vus // 10} }}, "
                f"{{ duration: '{ramp}s', target: {vus} }}, "
                f"{{ duration: '{ramp}s', target: 0 }}]"
            )
        elif scenario == "spike":
            return (
                f"[{{ duration: '10s', target: 10 }}, "
                f"{{ duration: '5s', target: {vus} }}, "
                f"{{ duration: '30s', target: {vus} }}, "
                f"{{ duration: '15s', target: 0 }}]"
            )
        elif scenario == "soak":
            return f"[{{ duration: '{duration}s', target: {vus} }}]"
        return f"[{{ duration: '{duration}s', target: {vus} }}]"

    def _scenario_env(self, scenario: str) -> Dict[str, str]:
        """Environment variables for k6 scenario"""
        env = {"K6_SCENARIO": scenario}
        return env

    def build_feedback_context(self, result: TMCResult) -> Dict[str, Any]:
        """Build context for Brain to create perf optimization tasks"""
        m = result.metrics
        return {
            "type": "perf_bottleneck",
            "project": self.project_name,
            "scenario": result.scenario,
            "metrics": {
                "p50_ms": m.p50_ms,
                "p95_ms": m.p95_ms,
                "p99_ms": m.p99_ms,
                "throughput_rps": m.throughput_rps,
                "error_rate_pct": m.error_rate_pct,
                "total_requests": m.total_requests,
            },
            "violations": result.threshold_violations,
            "thresholds": self.thresholds,
            "suggestion": self._suggest_optimization(result),
        }

    def _suggest_optimization(self, result: TMCResult) -> str:
        """Suggest optimization based on metrics pattern"""
        m = result.metrics
        suggestions = []

        if m.p99_ms > 3 * m.p50_ms:
            suggestions.append("High tail latency (p99 >> p50): likely N+1 queries or lock contention")

        if m.error_rate_pct > 1.0:
            suggestions.append(f"Error rate {m.error_rate_pct:.1f}%: check connection pool limits or timeout configs")

        if m.throughput_rps < 50 and m.p95_ms < 100:
            suggestions.append("Low throughput with low latency: possible single-threaded bottleneck or rate limit")

        if m.max_ms > 10 * m.avg_ms:
            suggestions.append("Extreme outliers: check GC pauses, cold starts, or unindexed queries")

        return "; ".join(suggestions) if suggestions else "Analyze slow endpoints with profiling"
