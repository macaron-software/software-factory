#!/usr/bin/env python3
"""
TMC - Tests de Montée en Charge (Load Testing)
==============================================

Trois niveaux de tests:
1. smoke  - Perf smoke rapide (1-3 min), budgets simples
2. load   - Load test complet (10-30 min), capacité
3. stress - Stress test + chaos combo

Usage:
    ppz tmc smoke                    # Smoke test sur staging
    ppz tmc smoke --env=prod         # Smoke sur prod (read-only)
    ppz tmc load --duration=15m      # Load test 15 minutes
    ppz tmc stress --chaos=network   # Stress + injection réseau

Requirements:
    - k6 (pour HTTP load): brew install k6
    - Playwright (pour UI perf)
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import tempfile
import os

RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")
TESTS_DIR = POPINZ_ROOT / "popinz-tests"
K6_SCRIPTS_DIR = RLM_DIR / "k6_scripts"

# Ensure k6 scripts dir exists
K6_SCRIPTS_DIR.mkdir(exist_ok=True)

# Environment configs
ENVIRONMENTS = {
    "dev": {
        "base_url": "http://test.popinz-saas.fr:8090",
        "api_url": "http://test.popinz-saas.fr:8090/api",
        "grpc_url": "http://test.popinz-saas.fr:8090",
        "db_host": "localhost",
        "db_port": 5433,
    },
    "staging": {
        "base_url": "https://test-staging.popi.nz",
        "api_url": "https://test-staging.popi.nz/api",
        "grpc_url": "https://test-staging.popi.nz",
        "db_host": "51.38.224.228",
        "db_port": 5432,
    },
    "prod": {
        "base_url": "https://test.popi.nz",
        "api_url": "https://test.popi.nz/api",
        "grpc_url": "https://test.popi.nz",
        "read_only": True,  # Prod = smoke only
    }
}

# Performance budgets (seuils)
PERF_BUDGETS = {
    "smoke": {
        "p95_ms": 500,      # p95 latency < 500ms
        "p99_ms": 1000,     # p99 latency < 1s
        "error_rate": 0.01,  # < 1% errors
        "min_rps": 10,      # Au moins 10 req/s
    },
    "load": {
        "p95_ms": 800,
        "p99_ms": 2000,
        "error_rate": 0.02,  # < 2% errors under load
        "min_rps": 50,
        "max_cpu_pct": 80,
        "max_mem_pct": 85,
    },
    "stress": {
        "p99_ms": 5000,     # Stress = dégradation acceptable
        "error_rate": 0.10,  # < 10% errors under stress
        "recovery_time_ms": 30000,  # Recovery < 30s
    }
}

# Critical endpoints to test
CRITICAL_ENDPOINTS = [
    {"method": "GET", "path": "/fr/login", "name": "login_page"},
    {"method": "GET", "path": "/fr/dashboard", "name": "dashboard", "auth": True},
    {"method": "GET", "path": "/api/v1/persons", "name": "api_persons", "auth": True},
    {"method": "GET", "path": "/api/v1/groups", "name": "api_groups", "auth": True},
    {"method": "GET", "path": "/api/v1/planning/events", "name": "api_planning", "auth": True},
    {"method": "POST", "path": "/search/ajax", "name": "search", "auth": True,
     "body": {"query": "test", "types": ["persons", "groups"]}},
]


@dataclass
class PerfResult:
    """Result of a performance test"""
    test_type: str  # smoke, load, stress
    env: str
    passed: bool
    duration_ms: int
    started_at: str
    completed_at: str

    # Latencies
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0

    # Throughput
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rps: float = 0.0
    error_rate: float = 0.0

    # Resources
    cpu_max_pct: float = 0.0
    mem_max_pct: float = 0.0

    # Details
    endpoints: List[Dict] = None
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.endpoints is None:
            self.endpoints = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    emoji = {"INFO": "📊", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "PERF": "⏱️"}.get(level, "")
    print(f"[{ts}] [TMC] [{level}] {emoji} {msg}", flush=True)


def check_k6_installed() -> bool:
    """Check if k6 is installed"""
    try:
        subprocess.run(["k6", "version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def generate_k6_script(endpoints: List[Dict], env_config: Dict,
                       vus: int = 10, duration: str = "1m") -> str:
    """Generate k6 script for load testing"""
    base_url = env_config["base_url"]

    script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Rate, Trend }} from 'k6/metrics';

export const options = {{
    vus: {vus},
    duration: '{duration}',
    thresholds: {{
        http_req_duration: ['p(95)<500', 'p(99)<1000'],
        http_req_failed: ['rate<0.01'],
    }},
}};

const BASE_URL = '{base_url}';

// Custom metrics
const errorRate = new Rate('errors');
const latencyTrend = new Trend('latency');

export default function() {{
"""

    for ep in endpoints:
        method = ep.get("method", "GET")
        path = ep.get("path", "/")
        name = ep.get("name", path)
        body = ep.get("body")

        if method == "GET":
            script += f"""
    // {name}
    let res_{name} = http.get(BASE_URL + '{path}');
    check(res_{name}, {{ '{name} status 2xx': (r) => r.status >= 200 && r.status < 300 }});
    errorRate.add(res_{name}.status >= 400);
    latencyTrend.add(res_{name}.timings.duration);
"""
        elif method == "POST":
            body_str = json.dumps(body) if body else "{}"
            script += f"""
    // {name}
    let res_{name} = http.post(BASE_URL + '{path}', JSON.stringify({body_str}), {{
        headers: {{ 'Content-Type': 'application/json' }}
    }});
    check(res_{name}, {{ '{name} status 2xx': (r) => r.status >= 200 && r.status < 300 }});
    errorRate.add(res_{name}.status >= 400);
    latencyTrend.add(res_{name}.timings.duration);
"""

    script += """
    sleep(0.5);  // Pause between iterations
}
"""
    return script


async def run_k6_test(script_content: str, output_file: Path) -> Dict:
    """Run k6 test and return results"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        cmd = [
            "k6", "run",
            "--out", f"json={output_file}",
            "--summary-export", str(output_file.with_suffix('.summary.json')),
            script_path
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        # Parse summary
        summary_path = output_file.with_suffix('.summary.json')
        if summary_path.exists():
            with open(summary_path) as f:
                return json.load(f)
        return {}

    finally:
        os.unlink(script_path)


async def run_playwright_perf(env: str, scenarios: List[str] = None) -> Dict:
    """Run Playwright performance scenarios"""
    if scenarios is None:
        scenarios = ["smoke"]

    env_config = ENVIRONMENTS.get(env, ENVIRONMENTS["staging"])
    base_url = env_config["base_url"]

    cmd = [
        "npx", "playwright", "test",
        "--project=chromium",
        "--grep", "@perf",
        "--reporter=json",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(TESTS_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={
            **os.environ,
            "TEST_ENV": env,
            "BASE_URL": base_url,
        }
    )

    stdout, stderr = await proc.communicate()

    try:
        return json.loads(stdout.decode())
    except json.JSONDecodeError:
        return {"error": stderr.decode()}


class TMC:
    """Tests de Montée en Charge orchestrator"""

    def __init__(self, env: str = "staging"):
        self.env = env
        self.env_config = ENVIRONMENTS.get(env, ENVIRONMENTS["staging"])
        self.results_dir = RLM_DIR / "tmc_results"
        self.results_dir.mkdir(exist_ok=True)

    async def smoke(self, task_id: str = None) -> PerfResult:
        """
        Perf smoke test (1-3 minutes)
        Quick validation of critical endpoints.
        """
        log(f"Starting SMOKE test on {self.env}")
        start_time = time.time()
        started_at = datetime.now().isoformat()

        budgets = PERF_BUDGETS["smoke"]
        result = PerfResult(
            test_type="smoke",
            env=self.env,
            passed=True,
            duration_ms=0,
            started_at=started_at,
            completed_at=""
        )

        if check_k6_installed():
            # Use k6 for HTTP load
            script = generate_k6_script(
                CRITICAL_ENDPOINTS,
                self.env_config,
                vus=5,
                duration="1m"
            )

            output_file = self.results_dir / f"smoke_{self.env}_{int(time.time())}.json"
            k6_results = await run_k6_test(script, output_file)

            if k6_results:
                metrics = k6_results.get("metrics", {})

                # Extract latencies
                http_req_duration = metrics.get("http_req_duration", {})
                result.p50_ms = http_req_duration.get("values", {}).get("p(50)", 0)
                result.p95_ms = http_req_duration.get("values", {}).get("p(95)", 0)
                result.p99_ms = http_req_duration.get("values", {}).get("p(99)", 0)
                result.max_ms = http_req_duration.get("values", {}).get("max", 0)

                # Extract throughput
                http_reqs = metrics.get("http_reqs", {})
                result.total_requests = int(http_reqs.get("values", {}).get("count", 0))
                result.rps = http_reqs.get("values", {}).get("rate", 0)

                # Extract errors
                http_req_failed = metrics.get("http_req_failed", {})
                result.error_rate = http_req_failed.get("values", {}).get("rate", 0)
                result.failed_requests = int(result.total_requests * result.error_rate)
                result.successful_requests = result.total_requests - result.failed_requests

        else:
            # Fallback: simple curl-based test
            log("k6 not installed, using curl fallback", "WARN")
            result.warnings.append("k6 not installed - using curl fallback")

            latencies = []
            errors = 0
            total = 0

            for ep in CRITICAL_ENDPOINTS[:5]:  # Test first 5 endpoints
                path = ep.get("path", "/")
                url = f"{self.env_config['base_url']}{path}"

                try:
                    start = time.time()
                    proc = await asyncio.create_subprocess_exec(
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code},%{time_total}",
                        "-m", "10", url,
                        stdout=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await proc.communicate()
                    parts = stdout.decode().strip().split(",")
                    status = int(parts[0])
                    latency = float(parts[1]) * 1000  # Convert to ms

                    latencies.append(latency)
                    total += 1
                    if status >= 400:
                        errors += 1

                except Exception as e:
                    errors += 1
                    total += 1
                    result.errors.append(str(e))

            if latencies:
                latencies.sort()
                result.p50_ms = latencies[len(latencies) // 2]
                result.p95_ms = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
                result.p99_ms = latencies[-1]
                result.max_ms = max(latencies)

            result.total_requests = total
            result.failed_requests = errors
            result.successful_requests = total - errors
            result.error_rate = errors / total if total > 0 else 0

        # Calculate duration
        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        # Validate against budgets
        if result.p95_ms > budgets["p95_ms"]:
            result.passed = False
            result.errors.append(f"p95 latency {result.p95_ms:.0f}ms > budget {budgets['p95_ms']}ms")

        if result.error_rate > budgets["error_rate"]:
            result.passed = False
            result.errors.append(f"Error rate {result.error_rate:.2%} > budget {budgets['error_rate']:.2%}")

        if result.rps < budgets["min_rps"] and result.rps > 0:
            result.warnings.append(f"RPS {result.rps:.1f} < expected {budgets['min_rps']}")

        # Log results
        status = "PASS" if result.passed else "FAIL"
        log(f"SMOKE {status}: p95={result.p95_ms:.0f}ms, errors={result.error_rate:.2%}, rps={result.rps:.1f}",
            "OK" if result.passed else "ERROR")

        # Save results
        self._save_result(result, task_id)

        return result

    async def load(self, duration: str = "10m", vus: int = 50,
                   task_id: str = None) -> PerfResult:
        """
        Load test (10-30 minutes)
        Validate capacity and find saturation point.
        """
        log(f"Starting LOAD test on {self.env} ({duration}, {vus} VUs)")
        start_time = time.time()
        started_at = datetime.now().isoformat()

        budgets = PERF_BUDGETS["load"]
        result = PerfResult(
            test_type="load",
            env=self.env,
            passed=True,
            duration_ms=0,
            started_at=started_at,
            completed_at=""
        )

        if not check_k6_installed():
            log("k6 required for load tests", "ERROR")
            result.passed = False
            result.errors.append("k6 not installed - required for load tests")
            return result

        # Generate k6 script with ramp-up
        script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Rate, Trend }} from 'k6/metrics';

export const options = {{
    stages: [
        {{ duration: '1m', target: {vus // 2} }},   // Ramp up to 50%
        {{ duration: '2m', target: {vus} }},        // Ramp up to 100%
        {{ duration: '{duration}', target: {vus} }}, // Stay at peak
        {{ duration: '1m', target: 0 }},            // Ramp down
    ],
    thresholds: {{
        http_req_duration: ['p(95)<{budgets["p95_ms"]}', 'p(99)<{budgets["p99_ms"]}'],
        http_req_failed: ['rate<{budgets["error_rate"]}'],
    }},
}};

const BASE_URL = '{self.env_config["base_url"]}';
const errorRate = new Rate('errors');
const latencyTrend = new Trend('latency');

export default function() {{
"""

        for ep in CRITICAL_ENDPOINTS:
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            name = ep.get("name", path)

            if method == "GET":
                script += f"""
    let res_{name} = http.get(BASE_URL + '{path}');
    check(res_{name}, {{ '{name} ok': (r) => r.status < 400 }});
    errorRate.add(res_{name}.status >= 400);
    latencyTrend.add(res_{name}.timings.duration);
"""

        script += """
    sleep(0.3);
}
"""

        output_file = self.results_dir / f"load_{self.env}_{int(time.time())}.json"
        k6_results = await run_k6_test(script, output_file)

        if k6_results:
            metrics = k6_results.get("metrics", {})

            http_req_duration = metrics.get("http_req_duration", {})
            result.p50_ms = http_req_duration.get("values", {}).get("p(50)", 0)
            result.p95_ms = http_req_duration.get("values", {}).get("p(95)", 0)
            result.p99_ms = http_req_duration.get("values", {}).get("p(99)", 0)
            result.max_ms = http_req_duration.get("values", {}).get("max", 0)

            http_reqs = metrics.get("http_reqs", {})
            result.total_requests = int(http_reqs.get("values", {}).get("count", 0))
            result.rps = http_reqs.get("values", {}).get("rate", 0)

            http_req_failed = metrics.get("http_req_failed", {})
            result.error_rate = http_req_failed.get("values", {}).get("rate", 0)

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        # Validate
        if result.p95_ms > budgets["p95_ms"]:
            result.passed = False
            result.errors.append(f"p95 {result.p95_ms:.0f}ms > {budgets['p95_ms']}ms")

        if result.error_rate > budgets["error_rate"]:
            result.passed = False
            result.errors.append(f"Error rate {result.error_rate:.2%} > {budgets['error_rate']:.2%}")

        status = "PASS" if result.passed else "FAIL"
        log(f"LOAD {status}: p95={result.p95_ms:.0f}ms, errors={result.error_rate:.2%}, rps={result.rps:.1f}",
            "OK" if result.passed else "ERROR")

        self._save_result(result, task_id)
        return result

    async def stress(self, duration: str = "5m", vus: int = 100,
                     chaos_type: str = None, task_id: str = None) -> PerfResult:
        """
        Stress test with optional chaos injection.
        Find breaking point and validate recovery.
        """
        log(f"Starting STRESS test on {self.env} ({duration}, {vus} VUs, chaos={chaos_type})")
        start_time = time.time()
        started_at = datetime.now().isoformat()

        budgets = PERF_BUDGETS["stress"]
        result = PerfResult(
            test_type="stress",
            env=self.env,
            passed=True,
            duration_ms=0,
            started_at=started_at,
            completed_at=""
        )

        # If chaos requested, import and start chaos
        if chaos_type:
            try:
                from chaos_monkey import ChaosMonkey
                chaos = ChaosMonkey(env=self.env)
                log(f"Starting chaos injection: {chaos_type}")
                chaos_task = asyncio.create_task(
                    getattr(chaos, chaos_type)(duration_seconds=300)
                )
            except ImportError:
                result.warnings.append("ChaosMonkey not available")
                chaos_task = None
        else:
            chaos_task = None

        if not check_k6_installed():
            result.passed = False
            result.errors.append("k6 required for stress tests")
            return result

        # Aggressive ramp-up script
        script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Rate }} from 'k6/metrics';

export const options = {{
    stages: [
        {{ duration: '30s', target: {vus // 2} }},
        {{ duration: '1m', target: {vus} }},
        {{ duration: '{duration}', target: {int(vus * 1.5)} }},  // Overshoot
        {{ duration: '1m', target: {vus} }},  // Recover
        {{ duration: '30s', target: 0 }},
    ],
}};

const BASE_URL = '{self.env_config["base_url"]}';
const errorRate = new Rate('errors');

export default function() {{
    let res = http.get(BASE_URL + '/fr/dashboard');
    errorRate.add(res.status >= 400);
    sleep(0.1);
}}
"""

        output_file = self.results_dir / f"stress_{self.env}_{int(time.time())}.json"
        k6_results = await run_k6_test(script, output_file)

        if k6_results:
            metrics = k6_results.get("metrics", {})

            http_req_duration = metrics.get("http_req_duration", {})
            result.p99_ms = http_req_duration.get("values", {}).get("p(99)", 0)
            result.max_ms = http_req_duration.get("values", {}).get("max", 0)

            http_req_failed = metrics.get("http_req_failed", {})
            result.error_rate = http_req_failed.get("values", {}).get("rate", 0)

        # Stop chaos if running
        if chaos_task:
            chaos_task.cancel()
            try:
                await chaos_task
            except asyncio.CancelledError:
                pass

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        # Validate (stress has relaxed budgets)
        if result.p99_ms > budgets["p99_ms"]:
            result.warnings.append(f"p99 {result.p99_ms:.0f}ms > {budgets['p99_ms']}ms")

        if result.error_rate > budgets["error_rate"]:
            result.passed = False
            result.errors.append(f"Error rate {result.error_rate:.2%} > {budgets['error_rate']:.2%}")

        status = "PASS" if result.passed else "FAIL"
        log(f"STRESS {status}: p99={result.p99_ms:.0f}ms, errors={result.error_rate:.2%}",
            "OK" if result.passed else "ERROR")

        self._save_result(result, task_id)
        return result

    def _save_result(self, result: PerfResult, task_id: str = None):
        """Save result to file and optionally to task store"""
        # Save to file
        filename = f"{result.test_type}_{self.env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.results_dir / filename
        with open(filepath, 'w') as f:
            json.dump(asdict(result), f, indent=2)

        # Save to task store if task_id provided
        if task_id:
            try:
                from task_store import TaskStore
                store = TaskStore()
                store.record_perf_result(
                    task_id=task_id,
                    test_type=result.test_type,
                    passed=result.passed,
                    duration_ms=result.duration_ms,
                    p50_ms=result.p50_ms,
                    p95_ms=result.p95_ms,
                    p99_ms=result.p99_ms,
                    error_rate=result.error_rate,
                    throughput_rps=result.rps,
                    details=asdict(result)
                )
            except ImportError:
                pass


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="TMC - Tests de Montée en Charge")
    parser.add_argument("command", choices=["smoke", "load", "stress"],
                       help="Type of test to run")
    parser.add_argument("--env", default="staging", choices=["dev", "staging", "prod"])
    parser.add_argument("--duration", default="10m", help="Duration for load/stress tests")
    parser.add_argument("--vus", type=int, default=50, help="Virtual users")
    parser.add_argument("--chaos", choices=["network", "db", "service"],
                       help="Chaos injection type for stress test")
    parser.add_argument("--task", type=str, help="Task ID to record results")

    args = parser.parse_args()

    tmc = TMC(env=args.env)

    if args.command == "smoke":
        result = await tmc.smoke(task_id=args.task)
    elif args.command == "load":
        result = await tmc.load(
            duration=args.duration,
            vus=args.vus,
            task_id=args.task
        )
    elif args.command == "stress":
        result = await tmc.stress(
            duration=args.duration,
            vus=args.vus,
            chaos_type=args.chaos,
            task_id=args.task
        )

    # Exit code based on result
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
