"""Quality Scanner — deterministic code quality metrics using CLI tools.

Computes 10 quality dimensions (each scored 0-100) and produces a QualityScorecard.
All measurements are deterministic (no LLM) — they run real tools and parse output.

Usage:
    scanner = QualityScanner()
    scorecard = await scanner.full_scan("/workspace/myproject", project_id="abc")
    print(scorecard.global_score)  # 72.5
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# Dimension weights (must sum to 1.0)
WEIGHTS = {
    "complexity": 0.15,
    "coverage_ut": 0.15,
    "coverage_e2e": 0.10,
    "security": 0.15,
    "accessibility": 0.10,
    "performance": 0.05,
    "documentation": 0.10,
    "architecture": 0.10,
    "maintainability": 0.05,
    "adversarial": 0.05,
}

_TIMEOUT = 120  # seconds per tool run


@dataclass
class DimensionResult:
    """Result of scanning a single quality dimension."""

    dimension: str
    score: float  # 0-100
    details: dict = field(default_factory=dict)
    tool_used: str = ""
    error: str = ""


@dataclass
class QualityScorecard:
    """Full quality scan result."""

    global_score: float = 0.0
    dimensions: dict[str, DimensionResult] = field(default_factory=dict)
    project_id: str = ""
    workspace: str = ""

    def to_dict(self) -> dict:
        return {
            "global_score": round(self.global_score, 1),
            "dimensions": {
                k: {
                    "score": round(v.score, 1),
                    "tool": v.tool_used,
                    "details": v.details,
                    "error": v.error,
                }
                for k, v in self.dimensions.items()
            },
        }


def _run_cmd(cmd: list[str], cwd: str, timeout: int = _TIMEOUT) -> tuple[str, str, int]:
    """Run a subprocess, return (stdout, stderr, returncode). Sync fallback."""
    import subprocess

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return r.stdout, r.stderr, r.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except subprocess.TimeoutExpired:
        return "", f"Timeout after {timeout}s", -2
    except Exception as e:
        return "", str(e), -3


async def _arun_cmd(
    cmd: list[str], cwd: str, timeout: int = _TIMEOUT
) -> tuple[str, str, int]:
    """Run a subprocess asynchronously (non-blocking)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
            proc.returncode or 0,
        )
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except asyncio.TimeoutError:
        proc.kill()  # type: ignore[possibly-undefined]
        return "", f"Timeout after {timeout}s", -2
    except Exception as e:
        return "", str(e), -3


def _validate_workspace(workspace: str) -> str:
    """Validate workspace path to prevent directory traversal."""
    p = Path(workspace).resolve()
    # Must be an existing directory
    if not p.is_dir():
        raise ValueError(f"Workspace not found: {workspace}")
    # Block system-critical paths
    blocked = (
        "/etc",
        "/var",
        "/usr",
        "/bin",
        "/sbin",
        "/boot",
        "/root",
        "/proc",
        "/sys",
    )
    for b in blocked:
        if str(p) == b or str(p).startswith(b + "/"):
            raise ValueError(f"Workspace in blocked path: {p}")
    return str(p)


def _detect_stack(workspace: str) -> dict:
    """Detect project language stack from files."""
    p = Path(workspace)
    has = {
        "python": bool(list(p.rglob("*.py"))[:1]),
        "javascript": bool(list(p.rglob("*.js"))[:1])
        or bool(list(p.rglob("*.ts"))[:1]),
        "typescript": bool(list(p.rglob("*.ts"))[:1]),
        "rust": (p / "Cargo.toml").exists(),
        "go": (p / "go.mod").exists(),
        "java": bool(list(p.rglob("*.java"))[:1]),
    }
    # Dependency manifests
    has["requirements_txt"] = (p / "requirements.txt").exists()
    has["package_json"] = (p / "package.json").exists()
    has["cargo_toml"] = (p / "Cargo.toml").exists()
    has["go_mod"] = (p / "go.mod").exists()
    return has


class QualityScanner:
    """Orchestrates deterministic quality scans across 10 dimensions."""

    async def full_scan(
        self,
        workspace: str,
        project_id: str = "",
        mission_id: str = "",
        url: str = "",
    ) -> QualityScorecard:
        """Run all dimension scans and compute global score."""
        workspace = _validate_workspace(workspace)
        stack = _detect_stack(workspace)
        scorecard = QualityScorecard(project_id=project_id, workspace=workspace)

        # Run each dimension
        scanners = [
            ("complexity", self.scan_complexity),
            ("coverage_ut", self.scan_coverage_ut),
            ("coverage_e2e", self.scan_coverage_e2e),
            ("security", self.scan_security),
            ("accessibility", lambda w, **kw: self.scan_accessibility(w, url=url)),
            ("performance", lambda w, **kw: self.scan_performance(w, url=url)),
            ("documentation", self.scan_documentation),
            ("architecture", self.scan_architecture),
            ("maintainability", self.scan_maintainability),
            (
                "adversarial",
                lambda w, **kw: self.scan_adversarial(project_id=project_id),
            ),
        ]

        for dim_name, scanner_fn in scanners:
            try:
                result = await scanner_fn(workspace, stack=stack)
            except Exception as e:
                result = DimensionResult(dimension=dim_name, score=0, error=str(e))
            result.dimension = dim_name
            scorecard.dimensions[dim_name] = result

        # Compute weighted global score — exclude skipped dimensions
        total = 0.0
        active_weight = 0.0
        for dim, weight in WEIGHTS.items():
            if dim in scorecard.dimensions:
                r = scorecard.dimensions[dim]
                if r.details.get("skipped"):
                    continue  # don't inflate score with skipped=100
                total += r.score * weight
                active_weight += weight
        # Weighted score normalized to active dimensions only
        scorecard.global_score = (
            round(total / active_weight, 1) if active_weight > 0 else 0.0
        )

        # Persist
        if project_id:
            self._store(scorecard, project_id, mission_id)
            # Store in agent memory for retrieval during workflows
            QualityScanner.store_in_memory(
                project_id,
                {
                    "global_score": scorecard.global_score,
                    "dimensions": {
                        k: {"score": v.score, "details": v.details}
                        for k, v in scorecard.dimensions.items()
                    },
                },
            )

            # Emit event: quality scanned
            try:
                from ..events.store import QUALITY_SCANNED, get_event_store

                get_event_store().emit(
                    QUALITY_SCANNED,
                    {"global_score": scorecard.global_score, "dimensions": len(scorecard.dimensions)},
                    entity_type="project",
                    entity_id=project_id,
                    project_id=project_id,
                    mission_id=mission_id,
                )
            except Exception:
                pass

        return scorecard

    # ── Dimension Scanners ──

    async def scan_complexity(self, workspace: str, **kw) -> DimensionResult:
        """Cyclomatic complexity via radon (Python) or lizard (multi-lang)."""
        stack = kw.get("stack") or _detect_stack(workspace)
        details: dict = {}
        score = 100.0

        if stack.get("python"):
            stdout, stderr, rc = await _arun_cmd(
                ["python3", "-m", "radon", "cc", "-j", "-a", "."],
                cwd=workspace,
            )
            if rc == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    total_cc = 0
                    func_count = 0
                    high_count = 0
                    for filename, funcs in data.items():
                        for f in funcs:
                            cc = f.get("complexity", 0)
                            total_cc += cc
                            func_count += 1
                            if cc > 10:
                                high_count += 1
                    avg_cc = total_cc / max(func_count, 1)
                    details = {
                        "avg_cc": round(avg_cc, 1),
                        "functions": func_count,
                        "high_complexity": high_count,
                        "tool": "radon",
                    }
                    # Score: A(1-5)=100, B(6-10)=80, C(11-15)=60, D(16-25)=40, F(26+)=20
                    if avg_cc <= 5:
                        score = 100
                    elif avg_cc <= 10:
                        score = 80
                    elif avg_cc <= 15:
                        score = 60
                    elif avg_cc <= 25:
                        score = 40
                    else:
                        score = 20
                    # Penalize high-complexity functions
                    if func_count > 0:
                        pct_high = high_count / func_count
                        score = max(0, score - pct_high * 30)
                except json.JSONDecodeError:
                    details["parse_error"] = "radon output not valid JSON"
            return DimensionResult(
                dimension="complexity", score=score, details=details, tool_used="radon"
            )

        # Fallback: lizard (multi-language)
        stdout, stderr, rc = await _arun_cmd(
            ["lizard", "--csv", "."],
            cwd=workspace,
        )
        if rc == 0 and stdout.strip():
            lines = stdout.strip().split("\n")
            total_cc = 0
            func_count = 0
            high_count = 0
            for line in lines[1:]:  # skip header
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        cc = int(parts[1])
                        total_cc += cc
                        func_count += 1
                        if cc > 10:
                            high_count += 1
                    except (ValueError, IndexError):
                        pass
            avg_cc = total_cc / max(func_count, 1)
            details = {
                "avg_cc": round(avg_cc, 1),
                "functions": func_count,
                "high_complexity": high_count,
                "tool": "lizard",
            }
            if avg_cc <= 5:
                score = 100
            elif avg_cc <= 10:
                score = 80
            elif avg_cc <= 15:
                score = 60
            elif avg_cc <= 25:
                score = 40
            else:
                score = 20
        else:
            details["error"] = "No complexity tool available (install radon or lizard)"

        return DimensionResult(
            dimension="complexity", score=score, details=details, tool_used="lizard"
        )

    async def scan_coverage_ut(self, workspace: str, **kw) -> DimensionResult:
        """Unit test coverage via coverage.py (Python) or nyc (JS)."""
        stack = kw.get("stack") or _detect_stack(workspace)
        details: dict = {}
        tmpdir = tempfile.mkdtemp(prefix="macaron_cov_")

        try:
            if stack.get("python"):
                cov_json = str(Path(tmpdir) / "cov.json")
                await _arun_cmd(
                    [
                        "python3",
                        "-m",
                        "coverage",
                        "run",
                        "--source=.",
                        "-m",
                        "pytest",
                        "-q",
                        "--tb=no",
                    ],
                    cwd=workspace,
                    timeout=180,
                )
                await _arun_cmd(
                    ["python3", "-m", "coverage", "json", "-o", cov_json],
                    cwd=workspace,
                )
                try:
                    with open(cov_json) as f:
                        data = json.load(f)
                    pct = data.get("totals", {}).get("percent_covered", 0)
                    details = {
                        "percent_covered": round(pct, 1),
                        "lines_covered": data.get("totals", {}).get("covered_lines", 0),
                        "lines_total": data.get("totals", {}).get("num_statements", 0),
                        "tool": "coverage.py",
                    }
                    return DimensionResult(
                        dimension="coverage_ut",
                        score=round(pct, 1),
                        details=details,
                        tool_used="coverage.py",
                    )
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

            if stack.get("javascript") or stack.get("typescript"):
                nyc_dir = str(Path(tmpdir) / "nyc-report")
                stdout, stderr, rc = await _arun_cmd(
                    [
                        "npx",
                        "nyc",
                        "report",
                        "--reporter=json",
                        f"--report-dir={nyc_dir}",
                    ],
                    cwd=workspace,
                )
                try:
                    with open(Path(nyc_dir) / "coverage-final.json") as f:
                        data = json.load(f)
                    total_stmts = 0
                    covered_stmts = 0
                    for filepath, info in data.items():
                        s = info.get("s", {})
                        total_stmts += len(s)
                        covered_stmts += sum(1 for v in s.values() if v > 0)
                    pct = (covered_stmts / max(total_stmts, 1)) * 100
                    details = {"percent_covered": round(pct, 1), "tool": "nyc"}
                    return DimensionResult(
                        dimension="coverage_ut",
                        score=round(pct, 1),
                        details=details,
                        tool_used="nyc",
                    )
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

            if stack.get("go"):
                cover_out = str(Path(tmpdir) / "cover.out")
                stdout, stderr, rc = await _arun_cmd(
                    ["go", "test", f"-coverprofile={cover_out}", "./..."],
                    cwd=workspace,
                    timeout=180,
                )
                if rc == 0:
                    m = re.search(r"coverage:\s*([\d.]+)%", stdout + stderr)
                    if m:
                        pct = float(m.group(1))
                        details = {"percent_covered": pct, "tool": "go test"}
                        return DimensionResult(
                            dimension="coverage_ut",
                            score=pct,
                            details=details,
                            tool_used="go test",
                        )

            # No coverage data
            details["error"] = "No test coverage data found"
            return DimensionResult(dimension="coverage_ut", score=0, details=details)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    async def scan_coverage_e2e(self, workspace: str, **kw) -> DimensionResult:
        """E2E test coverage from Playwright/Cypress reports or journey manifest."""
        details: dict = {}
        p = Path(workspace)

        # Check for Playwright report
        report_paths = [
            p / "playwright-report" / "report.json",
            p / "test-results" / "results.json",
            p / "e2e-results.json",
        ]
        for rp in report_paths:
            if rp.exists():
                try:
                    data = json.loads(rp.read_text())
                    total = data.get("stats", {}).get("expected", 0) or len(
                        data.get("suites", [])
                    )
                    passed = data.get("stats", {}).get("expected", 0)
                    details = {
                        "total_tests": total,
                        "passed": passed,
                        "tool": "playwright",
                    }
                    score = (passed / max(total, 1)) * 100
                    return DimensionResult(
                        dimension="coverage_e2e",
                        score=score,
                        details=details,
                        tool_used="playwright",
                    )
                except Exception:
                    pass

        # Check for journey manifest (custom)
        manifest = p / "journeys.json"
        if manifest.exists():
            try:
                journeys = json.loads(manifest.read_text())
                total = len(journeys)
                covered = sum(1 for j in journeys if j.get("tested"))
                pct = (covered / max(total, 1)) * 100
                details = {"total_journeys": total, "covered": covered}
                return DimensionResult(
                    dimension="coverage_e2e",
                    score=pct,
                    details=details,
                    tool_used="journey-manifest",
                )
            except Exception:
                pass

        # Count E2E-specific test files as proxy (exclude *_test.py — those are unit tests)
        e2e_files = list(p.rglob("*.spec.*")) + list(p.rglob("*.e2e.*"))
        if e2e_files:
            details = {"test_files": len(e2e_files), "estimated": True}
            score = min(100, len(e2e_files) * 10)  # 10 points per test file, cap at 100
            return DimensionResult(
                dimension="coverage_e2e",
                score=score,
                details=details,
                tool_used="file-count",
            )

        return DimensionResult(
            dimension="coverage_e2e", score=0, details={"error": "No E2E tests found"}
        )

    async def scan_security(self, workspace: str, **kw) -> DimensionResult:
        """Security scan via bandit (Python) + semgrep + dependency audit."""
        stack = kw.get("stack") or _detect_stack(workspace)
        findings: dict = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        tools_used = []

        if stack.get("python"):
            stdout, stderr, rc = await _arun_cmd(
                ["python3", "-m", "bandit", "-r", ".", "-f", "json", "-ll"],
                cwd=workspace,
            )
            if stdout.strip():
                try:
                    data = json.loads(stdout)
                    for r in data.get("results", []):
                        sev = r.get("issue_severity", "").upper()
                        if sev == "HIGH":
                            findings["high"] += 1
                        elif sev == "MEDIUM":
                            findings["medium"] += 1
                        elif sev == "LOW":
                            findings["low"] += 1
                    tools_used.append("bandit")
                except json.JSONDecodeError:
                    pass

            # pip-audit
            stdout, stderr, rc = await _arun_cmd(
                ["pip-audit", "-f", "json", "-r", "requirements.txt"],
                cwd=workspace,
            )
            if stdout.strip():
                try:
                    data = json.loads(stdout)
                    for vuln in (
                        data if isinstance(data, list) else data.get("dependencies", [])
                    ):
                        vulns = vuln.get("vulns", [])
                        for v in vulns:
                            fix = v.get("fix_versions", [])
                            if not fix:
                                findings["critical"] += 1
                            else:
                                findings["high"] += 1
                    tools_used.append("pip-audit")
                except json.JSONDecodeError:
                    pass

        if stack.get("javascript") or stack.get("typescript"):
            stdout, stderr, rc = await _arun_cmd(
                ["npm", "audit", "--json"], cwd=workspace
            )
            if stdout.strip():
                try:
                    data = json.loads(stdout)
                    vulns = data.get("metadata", {}).get("vulnerabilities", {})
                    findings["critical"] += vulns.get("critical", 0)
                    findings["high"] += vulns.get("high", 0)
                    findings["medium"] += vulns.get("moderate", 0)
                    findings["low"] += vulns.get("low", 0)
                    tools_used.append("npm-audit")
                except json.JSONDecodeError:
                    pass

        # Score: 100 - (critical*20 + high*10 + medium*2 + low*0.5)
        penalty = (
            findings["critical"] * 20
            + findings["high"] * 10
            + findings["medium"] * 2
            + findings["low"] * 0.5
        )
        score = max(0, min(100, 100 - penalty))

        details = {**findings, "tools": tools_used}
        return DimensionResult(
            dimension="security",
            score=score,
            details=details,
            tool_used=",".join(tools_used) or "none",
        )

    async def scan_accessibility(
        self, workspace: str, url: str = "", **kw
    ) -> DimensionResult:
        """Accessibility scan via pa11y or axe-core."""
        if not url:
            return DimensionResult(
                dimension="accessibility",
                score=100,
                details={"skipped": True, "reason": "No URL provided"},
                tool_used="none",
            )

        stdout, stderr, rc = await _arun_cmd(
            ["pa11y", "--reporter", "json", url],
            cwd=workspace,
        )
        if rc >= 0 and stdout.strip():
            try:
                issues = json.loads(stdout)
                if isinstance(issues, list):
                    critical = sum(1 for i in issues if i.get("type") == "error")
                    serious = sum(1 for i in issues if i.get("type") == "warning")
                    score = max(0, 100 - critical * 15 - serious * 5)
                    return DimensionResult(
                        dimension="accessibility",
                        score=score,
                        details={
                            "errors": critical,
                            "warnings": serious,
                            "total": len(issues),
                        },
                        tool_used="pa11y",
                    )
            except json.JSONDecodeError:
                pass

        return DimensionResult(
            dimension="accessibility",
            score=100,
            details={
                "skipped": True,
                "reason": "pa11y not available or URL unreachable",
            },
        )

    async def scan_performance(
        self, workspace: str, url: str = "", **kw
    ) -> DimensionResult:
        """Performance score via Lighthouse CLI."""
        if not url:
            return DimensionResult(
                dimension="performance",
                score=100,
                details={"skipped": True, "reason": "No URL provided"},
            )

        stdout, stderr, rc = await _arun_cmd(
            [
                "lighthouse",
                url,
                "--output=json",
                "--chrome-flags=--headless --no-sandbox",
                "--quiet",
            ],
            cwd=workspace,
            timeout=180,
        )
        if rc == 0 and stdout.strip():
            try:
                data = json.loads(stdout)
                cats = data.get("categories", {})
                perf = cats.get("performance", {}).get("score", 0) * 100
                a11y = cats.get("accessibility", {}).get("score", 0) * 100
                bp = cats.get("best-practices", {}).get("score", 0) * 100
                seo = cats.get("seo", {}).get("score", 0) * 100
                return DimensionResult(
                    dimension="performance",
                    score=perf,
                    details={
                        "performance": perf,
                        "accessibility": a11y,
                        "best_practices": bp,
                        "seo": seo,
                    },
                    tool_used="lighthouse",
                )
            except json.JSONDecodeError:
                pass

        return DimensionResult(
            dimension="performance",
            score=100,
            details={"skipped": True, "reason": "lighthouse not available"},
        )

    async def scan_documentation(self, workspace: str, **kw) -> DimensionResult:
        """Documentation coverage via interrogate (Python) or custom checker."""
        stack = kw.get("stack") or _detect_stack(workspace)
        details: dict = {}

        if stack.get("python"):
            stdout, stderr, rc = await _arun_cmd(
                ["python3", "-m", "interrogate", "-v", "--fail-under=0", "."],
                cwd=workspace,
            )
            combined = stdout + stderr
            m = re.search(r"([\d.]+)%", combined)
            if m:
                pct = float(m.group(1))
                details = {"docstring_coverage": pct, "tool": "interrogate"}
                return DimensionResult(
                    dimension="documentation",
                    score=pct,
                    details=details,
                    tool_used="interrogate",
                )

        # Fallback: check for README, API docs, CHANGELOG
        p = Path(workspace)
        checks = {
            "readme": any(p.glob("README*")),
            "changelog": any(p.glob("CHANGELOG*")),
            "api_docs": any(p.rglob("docs/*")) or any(p.rglob("api-docs/*")),
            "contributing": any(p.glob("CONTRIBUTING*")),
            "license": any(p.glob("LICENSE*")),
        }
        present = sum(1 for v in checks.values() if v)
        score = (present / len(checks)) * 100
        details = {"checks": checks, "tool": "file-check"}
        return DimensionResult(
            dimension="documentation",
            score=score,
            details=details,
            tool_used="file-check",
        )

    async def scan_architecture(self, workspace: str, **kw) -> DimensionResult:
        """Architecture quality: circular deps, code duplication, type safety."""
        stack = kw.get("stack") or _detect_stack(workspace)
        issues = {"circular_deps": 0, "duplicates": 0, "type_errors": 0}
        tools_used = []
        tmpdir = tempfile.mkdtemp(prefix="macaron_arch_")

        try:
            if stack.get("javascript") or stack.get("typescript"):
                # madge --circular
                stdout, stderr, rc = await _arun_cmd(
                    ["madge", "--circular", "--json", "."],
                    cwd=workspace,
                )
                if rc >= 0 and stdout.strip():
                    try:
                        data = json.loads(stdout)
                        issues["circular_deps"] = (
                            len(data) if isinstance(data, list) else 0
                        )
                        tools_used.append("madge")
                    except json.JSONDecodeError:
                        pass

            # jscpd — copy-paste detection (any language)
            jscpd_dir = str(Path(tmpdir) / "jscpd-report")
            stdout, stderr, rc = await _arun_cmd(
                ["jscpd", "--reporters", "json", "--output", jscpd_dir, "."],
                cwd=workspace,
            )
            if rc >= 0:
                try:
                    report = Path(jscpd_dir) / "jscpd-report.json"
                    if report.exists():
                        data = json.loads(report.read_text())
                        stats = data.get("statistics", {}).get("total", {})
                        issues["duplicates"] = stats.get("clones", 0)
                        issues["duplication_pct"] = stats.get("percentage", 0)
                        tools_used.append("jscpd")
                except (json.JSONDecodeError, Exception):
                    pass

            if stack.get("python"):
                # mypy type checking
                stdout, stderr, rc = await _arun_cmd(
                    ["python3", "-m", "mypy", "--no-error-summary", "--no-color", "."],
                    cwd=workspace,
                )
                if rc >= 0:
                    error_lines = [
                        ln for ln in (stdout + stderr).split("\n") if ": error:" in ln
                    ]
                    issues["type_errors"] = len(error_lines)
                    tools_used.append("mypy")

            # Score: 100 - (circular*10 + duplicates*5 + type_errors*2), capped at 0
            penalty = (
                issues["circular_deps"] * 10
                + issues["duplicates"] * 5
                + issues["type_errors"] * 2
            )
            score = max(0, min(100, 100 - penalty))

            details = {**issues, "tools": tools_used}
            return DimensionResult(
                dimension="architecture",
                score=score,
                details=details,
                tool_used=",".join(tools_used) or "none",
            )
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    async def scan_maintainability(self, workspace: str, **kw) -> DimensionResult:
        """Maintainability Index via radon mi (Python) or file-based heuristic."""
        stack = kw.get("stack") or _detect_stack(workspace)

        if stack.get("python"):
            stdout, stderr, rc = await _arun_cmd(
                ["python3", "-m", "radon", "mi", "-j", "."],
                cwd=workspace,
            )
            if rc == 0 and stdout.strip():
                try:
                    data = json.loads(stdout)
                    mi_values = []
                    for filename, info in data.items():
                        if isinstance(info, dict):
                            mi_values.append(info.get("mi", 0))
                        elif isinstance(info, (int, float)):
                            mi_values.append(info)
                    if mi_values:
                        avg_mi = sum(mi_values) / len(mi_values)
                        return DimensionResult(
                            dimension="maintainability",
                            score=min(100, avg_mi),
                            details={
                                "avg_mi": round(avg_mi, 1),
                                "files": len(mi_values),
                            },
                            tool_used="radon-mi",
                        )
                except json.JSONDecodeError:
                    pass

        # Heuristic fallback: file size distribution, comment ratio
        p = Path(workspace)
        src_files = (
            list(p.rglob("*.py"))
            + list(p.rglob("*.js"))
            + list(p.rglob("*.ts"))
            + list(p.rglob("*.go"))
            + list(p.rglob("*.rs"))
        )
        if not src_files:
            return DimensionResult(
                dimension="maintainability", score=50, details={"no_source_files": True}
            )

        large_files = sum(1 for f in src_files if f.stat().st_size > 10_000)
        pct_large = large_files / len(src_files)
        score = max(0, 100 - pct_large * 50)
        return DimensionResult(
            dimension="maintainability",
            score=score,
            details={"total_files": len(src_files), "large_files": large_files},
            tool_used="heuristic",
        )

    async def scan_adversarial(self, project_id: str = "", **kw) -> DimensionResult:
        """Adversarial rejection rate from platform DB."""
        if not project_id:
            return DimensionResult(
                dimension="adversarial",
                score=100,
                details={"skipped": True, "reason": "No project_id"},
            )

        try:
            db = get_db()
            # Count quality-related incidents (no project_id on platform_incidents,
            # so we count all quality_rejection incidents linked via mission)
            total = db.execute(
                "SELECT COUNT(*) FROM platform_incidents WHERE error_type IS NOT NULL",
            ).fetchone()[0]
            rejections = db.execute(
                "SELECT COUNT(*) FROM platform_incidents WHERE error_type = 'quality_rejection'",
            ).fetchone()[0]

            if total == 0:
                return DimensionResult(
                    dimension="adversarial",
                    score=100,
                    details={"total_incidents": 0, "rejections": 0, "skipped": True},
                    tool_used="platform-db",
                )

            rejection_rate = rejections / total
            score = max(0, 100 - rejection_rate * 100)
            return DimensionResult(
                dimension="adversarial",
                score=score,
                details={
                    "total_incidents": total,
                    "rejections": rejections,
                    "rejection_rate": round(rejection_rate, 3),
                },
                tool_used="platform-db",
            )
        except Exception as e:
            return DimensionResult(
                dimension="adversarial",
                score=50,
                details={"error": str(e)},
            )

    # ── Persistence ──

    def _store(
        self, scorecard: QualityScorecard, project_id: str, mission_id: str = ""
    ):
        """Persist quality reports and snapshot to DB."""
        try:
            db = get_db()
            # Store individual dimension reports
            for dim_name, result in scorecard.dimensions.items():
                db.execute(
                    """INSERT INTO quality_reports
                       (project_id, mission_id, dimension, score, details_json, tool_used)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        mission_id,
                        dim_name,
                        result.score,
                        json.dumps(result.details),
                        result.tool_used,
                    ),
                )

            # Store snapshot
            db.execute(
                """INSERT INTO quality_snapshots
                   (project_id, mission_id, global_score, breakdown_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    project_id,
                    mission_id,
                    scorecard.global_score,
                    json.dumps(scorecard.to_dict()),
                ),
            )
            db.commit()
        except Exception as e:
            logger.error("Failed to store quality report: %s", e)

    # ── Query helpers ──

    @staticmethod
    def get_latest_snapshot(project_id: str) -> Optional[dict]:
        """Get latest quality snapshot for a project."""
        try:
            db = get_db()
            row = db.execute(
                "SELECT global_score, breakdown_json, created_at FROM quality_snapshots WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if row:
                return {
                    "global_score": row[0],
                    "breakdown": json.loads(row[1]),
                    "timestamp": row[2],
                }
        except Exception:
            pass
        return None

    @staticmethod
    def get_trend(project_id: str, limit: int = 20) -> list[dict]:
        """Get quality trend (last N snapshots)."""
        try:
            db = get_db()
            rows = db.execute(
                "SELECT global_score, breakdown_json, created_at FROM quality_snapshots WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            return [
                {"global_score": r[0], "breakdown": json.loads(r[1]), "timestamp": r[2]}
                for r in reversed(rows)
            ]
        except Exception:
            return []

    @staticmethod
    def get_all_projects_scores() -> list[dict]:
        """Get latest score per project (for portfolio heatmap)."""
        try:
            db = get_db()
            rows = db.execute("""
                SELECT qs.project_id, qs.global_score, qs.breakdown_json, qs.created_at
                FROM quality_snapshots qs
                INNER JOIN (
                    SELECT project_id, MAX(created_at) as max_ts
                    FROM quality_snapshots GROUP BY project_id
                ) latest ON qs.project_id = latest.project_id AND qs.created_at = latest.max_ts
                ORDER BY qs.global_score ASC
            """).fetchall()
            return [
                {
                    "project_id": r[0],
                    "global_score": r[1],
                    "breakdown": json.loads(r[2]),
                    "timestamp": r[3],
                }
                for r in rows
            ]
        except Exception:
            return []

    @staticmethod
    def store_in_memory(project_id: str, scorecard: dict) -> None:
        """Persist quality results in project + global memory for agent retrieval."""
        try:
            from ..memory.manager import get_memory_manager

            mm = get_memory_manager()
            global_score = scorecard.get("global_score", 0)
            dims = scorecard.get("dimensions", {})
            summary = f"Quality score: {global_score}/100. " + ", ".join(
                f"{k}={v.get('score', 0)}" for k, v in dims.items()
            )
            mm.project_store(
                project_id,
                "quality_latest",
                summary,
                category="quality",
                source="quality_scanner",
                confidence=0.9,
            )
            worst = sorted(dims.items(), key=lambda x: x[1].get("score", 100))[:3]
            if worst:
                mm.project_store(
                    project_id,
                    "quality_worst_dims",
                    ", ".join(f"{k}({v.get('score', 0)})" for k, v in worst),
                    category="quality",
                    source="quality_scanner",
                    confidence=0.9,
                )
            mm.global_store(
                f"quality_{project_id}",
                summary,
                category="quality_trend",
                project_id=project_id,
                confidence=0.8,
            )
        except Exception:
            pass
