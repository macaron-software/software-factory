#!/usr/bin/env python3
"""
gates.py - Quality Gates pour Wiggum Pipeline

Implémente les gates critiques pour éviter le code partiel:
1. Completeness Gate: Vérifie que l'inventaire routes/endpoints est couvert
2. Fail-on-stubs Gate: Détecte TODO, NotImplemented, stubs
3. Perf Budget Gate: Vérifie les budgets de performance

Usage:
    from gates import GateRunner
    runner = GateRunner(project_root)
    result = runner.run_all_gates(task_id)
"""

import os
import re
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Seuils
PERF_P95_BUDGET_MS = 500  # 500ms max p95
PERF_ERROR_RATE_MAX = 0.01  # 1% max
MAX_UNWRAP_CALLS = 10

# Patterns interdits (code partiel)
STUB_PATTERNS = [
    r'unimplemented!\s*\(',
    r'todo!\s*\(',
    r'panic!\s*\(["\']not implemented',
    r'return\s+None\s*#\s*TODO',
    r'pass\s*#\s*TODO',
    r'NotImplementedError',
    r'raise\s+NotImplementedError',
    r'// TODO:?\s*(implement|fix|add)',
    r'# TODO:?\s*(implement|fix|add)',
    r'FIXME:?\s*(implement|fix|add)',
]

# Patterns de sécurité
SECURITY_PATTERNS = [
    r'password\s*=\s*["\'][^"\']+["\']',
    r'api_key\s*=\s*["\'][^"\']+["\']',
    r'secret\s*=\s*["\'][^"\']+["\']',
    r'token\s*=\s*["\'][a-zA-Z0-9]{20,}["\']',
    r'\.env\s+in\s+git',
]

# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class GateResult:
    """Résultat d'un gate."""
    name: str
    passed: bool
    message: str
    details: List[str] = field(default_factory=list)
    severity: str = "blocker"  # blocker, warning, info

@dataclass
class GateReport:
    """Rapport complet de tous les gates."""
    task_id: str
    timestamp: str
    gates: List[GateResult] = field(default_factory=list)
    passed: bool = True

    def add_gate(self, result: GateResult):
        self.gates.append(result)
        if not result.passed and result.severity == "blocker":
            self.passed = False

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "gates": [
                {
                    "name": g.name,
                    "passed": g.passed,
                    "message": g.message,
                    "details": g.details,
                    "severity": g.severity
                }
                for g in self.gates
            ]
        }

    def summary(self) -> str:
        lines = [f"=== Gate Report: {self.task_id} ==="]
        for g in self.gates:
            icon = "✓" if g.passed else ("⚠" if g.severity == "warning" else "✗")
            lines.append(f"  {icon} {g.name}: {g.message}")
            for detail in g.details[:3]:
                lines.append(f"      - {detail}")
        lines.append(f"  {'PASSED' if self.passed else 'FAILED'}")
        return "\n".join(lines)


# ============================================================================
# COMPLETENESS GATE
# ============================================================================
class CompletenessGate:
    """
    Vérifie que l'inventaire des routes/endpoints est entièrement implémenté.

    Compare:
    - Routes définies dans proto/*.proto
    - Routes implémentées dans src/grpc/services/*.rs
    - Routes frontend dans routes/*/+page.svelte
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backend_root = project_root / "veligo-platform" / "backend"
        self.frontend_root = project_root / "veligo-platform" / "frontend"
        self.proto_root = project_root / "veligo-platform" / "proto"

    def _get_proto_rpcs(self) -> Dict[str, List[str]]:
        """Extract RPC definitions from proto files."""
        rpcs = {}
        for proto_file in self.proto_root.rglob("*.proto"):
            if "node_modules" in str(proto_file):
                continue
            try:
                content = proto_file.read_text()
                service_match = re.findall(r'service\s+(\w+)\s*\{([^}]+)\}', content, re.DOTALL)
                for service_name, service_body in service_match:
                    rpc_matches = re.findall(r'rpc\s+(\w+)\s*\(', service_body)
                    rpcs[service_name] = rpc_matches
            except Exception:
                continue
        return rpcs

    def _get_implemented_rpcs(self) -> Dict[str, List[str]]:
        """Find implemented RPCs in Rust services."""
        implemented = {}
        services_dir = self.backend_root / "src" / "grpc" / "services"

        if not services_dir.exists():
            return implemented

        for rs_file in services_dir.glob("*.rs"):
            try:
                content = rs_file.read_text()
                # Find impl blocks and their methods
                impl_matches = re.findall(
                    r'impl\s+\w+\s+for\s+(\w+Service)',
                    content
                )
                for service in impl_matches:
                    # Find async fn (RPC implementations)
                    fn_matches = re.findall(
                        r'async\s+fn\s+(\w+)\s*\(',
                        content
                    )
                    # Exclude unimplemented ones
                    real_impl = []
                    for fn_name in fn_matches:
                        # Check if it's not just returning unimplemented
                        fn_body_match = re.search(
                            rf'async\s+fn\s+{fn_name}\s*\([^)]*\)[^{{]*\{{([^}}]{{0,500}})',
                            content
                        )
                        if fn_body_match:
                            body = fn_body_match.group(1)
                            if 'unimplemented!' not in body:
                                real_impl.append(fn_name)
                    implemented[service] = real_impl
            except Exception:
                continue
        return implemented

    def _get_frontend_routes(self) -> List[str]:
        """Get frontend route paths."""
        routes = []
        routes_dir = self.frontend_root / "src" / "routes"

        if not routes_dir.exists():
            return routes

        for page in routes_dir.rglob("+page.svelte"):
            # Convert path to route
            rel_path = page.parent.relative_to(routes_dir)
            route = "/" + str(rel_path).replace("(", "").replace(")", "").replace("\\", "/")
            route = re.sub(r'/\[.*?\]', '/:param', route)
            routes.append(route)

        return routes

    def run(self) -> GateResult:
        """Run completeness check."""
        proto_rpcs = self._get_proto_rpcs()
        impl_rpcs = self._get_implemented_rpcs()

        missing = []

        # Check each proto service
        for service, rpcs in proto_rpcs.items():
            # Find matching implementation
            impl_key = None
            for key in impl_rpcs:
                if service.lower() in key.lower():
                    impl_key = key
                    break

            if impl_key:
                impl_set = set(fn.lower() for fn in impl_rpcs[impl_key])
                for rpc in rpcs:
                    if rpc.lower() not in impl_set:
                        missing.append(f"{service}.{rpc}")
            else:
                for rpc in rpcs:
                    missing.append(f"{service}.{rpc} (service not found)")

        if missing:
            return GateResult(
                name="Completeness",
                passed=False,
                message=f"{len(missing)} RPCs not implemented",
                details=missing[:10],
                severity="blocker"
            )

        return GateResult(
            name="Completeness",
            passed=True,
            message=f"All {sum(len(v) for v in proto_rpcs.values())} RPCs implemented",
            severity="info"
        )


# ============================================================================
# FAIL-ON-STUBS GATE
# ============================================================================
class FailOnStubsGate:
    """
    Détecte les stubs, TODO, NotImplemented dans le code.
    Empêche le code partiel de passer en production.
    """

    def __init__(self, project_root: Path, changed_files: Optional[List[str]] = None):
        self.project_root = project_root
        self.changed_files = changed_files

    def _scan_file(self, filepath: Path) -> List[Tuple[int, str, str]]:
        """Scan a file for stub patterns. Returns (line_num, pattern, line)."""
        findings = []
        try:
            content = filepath.read_text()
            lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                for pattern in STUB_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append((i, pattern, line.strip()[:80]))
                        break  # One finding per line
        except Exception:
            pass
        return findings

    def run(self) -> GateResult:
        """Run stub detection."""
        all_findings = []

        # Determine files to scan
        if self.changed_files:
            files_to_scan = [
                self.project_root / f for f in self.changed_files
                if f.endswith(('.rs', '.ts', '.py', '.svelte'))
            ]
        else:
            # Scan key directories
            files_to_scan = []
            for ext in ['.rs', '.ts', '.svelte']:
                files_to_scan.extend(
                    self.project_root.rglob(f"veligo-platform/**/*{ext}")
                )

        for filepath in files_to_scan:
            if "node_modules" in str(filepath) or "target" in str(filepath):
                continue
            findings = self._scan_file(filepath)
            for line_num, pattern, line in findings:
                rel_path = filepath.relative_to(self.project_root)
                all_findings.append(f"{rel_path}:{line_num}: {line}")

        if all_findings:
            return GateResult(
                name="Fail-on-Stubs",
                passed=False,
                message=f"{len(all_findings)} stubs/TODOs found",
                details=all_findings[:10],
                severity="blocker"
            )

        return GateResult(
            name="Fail-on-Stubs",
            passed=True,
            message="No stubs or TODOs found",
            severity="info"
        )


# ============================================================================
# SECURITY GATE
# ============================================================================
class SecurityGate:
    """Détecte les secrets hardcodés et patterns de sécurité."""

    def __init__(self, project_root: Path, changed_files: Optional[List[str]] = None):
        self.project_root = project_root
        self.changed_files = changed_files

    def run(self) -> GateResult:
        """Run security scan."""
        findings = []

        files_to_scan = self.changed_files or []
        if not files_to_scan:
            # Get changed files from git
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD"],
                    capture_output=True, text=True, cwd=self.project_root
                )
                files_to_scan = result.stdout.strip().split('\n')
            except Exception:
                pass

        for filepath in files_to_scan:
            if not filepath:
                continue
            full_path = self.project_root / filepath
            if not full_path.exists():
                continue

            try:
                content = full_path.read_text()
                for pattern in SECURITY_PATTERNS:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        findings.append(f"{filepath}: {pattern[:30]}...")
            except Exception:
                continue

        if findings:
            return GateResult(
                name="Security",
                passed=False,
                message=f"{len(findings)} security issues found",
                details=findings[:5],
                severity="blocker"
            )

        return GateResult(
            name="Security",
            passed=True,
            message="No security issues detected",
            severity="info"
        )


# ============================================================================
# PERF BUDGET GATE
# ============================================================================
class PerfBudgetGate:
    """
    Vérifie les budgets de performance via tests de charge.
    Utilise k6 ou des métriques collectées.
    """

    def __init__(self, project_root: Path, metrics_file: Optional[Path] = None):
        self.project_root = project_root
        self.metrics_file = metrics_file or project_root / "perf-results.json"

    def _run_perf_smoke(self) -> Optional[Dict]:
        """Run quick perf smoke test with k6 if available."""
        k6_script = self.project_root / "veligo-platform" / "tests" / "perf" / "smoke.js"

        if not k6_script.exists():
            return None

        try:
            result = subprocess.run(
                ["k6", "run", "--quiet", "--out", "json=perf-results.json", str(k6_script)],
                capture_output=True, text=True, timeout=120, cwd=self.project_root
            )
            if result.returncode == 0 and self.metrics_file.exists():
                return json.loads(self.metrics_file.read_text())
        except Exception:
            pass
        return None

    def run(self) -> GateResult:
        """Run perf budget check."""
        # Try to load existing metrics
        metrics = None
        if self.metrics_file.exists():
            try:
                metrics = json.loads(self.metrics_file.read_text())
            except Exception:
                pass

        # If no metrics, try running smoke test
        if not metrics:
            metrics = self._run_perf_smoke()

        if not metrics:
            return GateResult(
                name="Perf-Budget",
                passed=True,
                message="No perf metrics available (skipped)",
                severity="warning"
            )

        violations = []

        # Check p95 latency
        p95 = metrics.get("http_req_duration", {}).get("p95", 0)
        if p95 > PERF_P95_BUDGET_MS:
            violations.append(f"p95 latency {p95}ms > budget {PERF_P95_BUDGET_MS}ms")

        # Check error rate
        error_rate = metrics.get("http_req_failed", {}).get("rate", 0)
        if error_rate > PERF_ERROR_RATE_MAX:
            violations.append(f"Error rate {error_rate*100:.2f}% > budget {PERF_ERROR_RATE_MAX*100}%")

        if violations:
            return GateResult(
                name="Perf-Budget",
                passed=False,
                message=f"{len(violations)} budget violations",
                details=violations,
                severity="blocker"
            )

        return GateResult(
            name="Perf-Budget",
            passed=True,
            message=f"p95={p95}ms, errors={error_rate*100:.2f}%",
            severity="info"
        )


# ============================================================================
# TEST SKIP GATE
# ============================================================================
class TestSkipGate:
    """Détecte les tests skippés (.skip, .todo)."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "veligo-platform" / "tests"

    def run(self) -> GateResult:
        """Check for skipped tests."""
        findings = []

        patterns = [
            r'test\.skip\s*\(',
            r'it\.skip\s*\(',
            r'describe\.skip\s*\(',
            r'test\.todo\s*\(',
            r'#\[ignore\]',
        ]

        for test_file in self.tests_dir.rglob("*.spec.ts"):
            try:
                content = test_file.read_text()
                for pattern in patterns:
                    if re.search(pattern, content):
                        rel_path = test_file.relative_to(self.project_root)
                        findings.append(str(rel_path))
                        break
            except Exception:
                continue

        if findings:
            return GateResult(
                name="Test-Skip",
                passed=False,
                message=f"{len(findings)} files with skipped tests",
                details=findings[:5],
                severity="blocker"
            )

        return GateResult(
            name="Test-Skip",
            passed=True,
            message="No skipped tests found",
            severity="info"
        )


# ============================================================================
# GATE RUNNER
# ============================================================================
class GateRunner:
    """Execute all gates and produce report."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or PROJECT_ROOT

    def run_all_gates(self, task_id: str, changed_files: Optional[List[str]] = None) -> GateReport:
        """Run all gates and return report."""
        report = GateReport(
            task_id=task_id,
            timestamp=datetime.now().isoformat()
        )

        # 1. Completeness Gate
        completeness = CompletenessGate(self.project_root)
        report.add_gate(completeness.run())

        # 2. Fail-on-Stubs Gate
        stubs = FailOnStubsGate(self.project_root, changed_files)
        report.add_gate(stubs.run())

        # 3. Security Gate
        security = SecurityGate(self.project_root, changed_files)
        report.add_gate(security.run())

        # 4. Test Skip Gate
        test_skip = TestSkipGate(self.project_root)
        report.add_gate(test_skip.run())

        # 5. Perf Budget Gate (optional)
        perf = PerfBudgetGate(self.project_root)
        report.add_gate(perf.run())

        return report

    def run_quick_gates(self, task_id: str, changed_files: Optional[List[str]] = None) -> GateReport:
        """Run only quick gates (no perf)."""
        report = GateReport(
            task_id=task_id,
            timestamp=datetime.now().isoformat()
        )

        # Quick gates only
        stubs = FailOnStubsGate(self.project_root, changed_files)
        report.add_gate(stubs.run())

        security = SecurityGate(self.project_root, changed_files)
        report.add_gate(security.run())

        return report


# ============================================================================
# CLI
# ============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run quality gates")
    parser.add_argument("--task", "-t", default="GATE-CHECK", help="Task ID")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick gates only")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")

    args = parser.parse_args()

    runner = GateRunner()

    if args.quick:
        report = runner.run_quick_gates(args.task)
    else:
        report = runner.run_all_gates(args.task)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary())

    return 0 if report.passed else 1


if __name__ == "__main__":
    exit(main())
