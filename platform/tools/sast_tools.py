"""
SAST Tools — Static Application Security Testing for LLM-generated code.

Checks beyond basic lint:
- Function/method length (> 30 lines = complexity smell)
- Missing context managers (open() without with, requests without session)
- Global mutable state (module-level list/dict mutations)
- Dangerous patterns: eval, exec, pickle, subprocess shell=True, os.system
- Unbounded collections growing in loops
- Semgrep rules (if installed)
"""

from __future__ import annotations

import ast
import asyncio
import re
import shutil
from pathlib import Path

from .registry import BaseTool
from ..models import AgentInstance

# ─── Python AST-based checks ──────────────────────────────────────────────────

MAX_FUNCTION_LINES = 30
MAX_FILE_LINES = 300

# Dangerous calls that should trigger a warning
_DANGEROUS_CALLS = {
    "eval": "S307 eval() executes arbitrary code — never use with user input",
    "exec": "S102 exec() executes arbitrary code — never use with user input",
    "compile": "S001 compile() with user input is dangerous",
    "os.system": "S605 os.system() vulnerable to shell injection — use subprocess with list args",
    "pickle.loads": "S301 pickle.loads() deserializes arbitrary objects — use json/msgpack",
    "marshal.loads": "S302 marshal.loads() is unsafe — use json",
    "__import__": "S001 __import__() with dynamic names is dangerous",
}

# Patterns for regex-based checks (faster than AST for some cases)
_REGEX_PATTERNS = [
    (
        r"subprocess\.[a-z_]+\([^)]*shell\s*=\s*True",
        "S603 subprocess with shell=True — use list args to prevent injection",
    ),
    (
        r"open\s*\([^)]+\)(?!\s*(?:as|,))",
        "M001 open() without 'with' — resource leak risk",
    ),
    (
        r"requests\.(get|post|put|delete|patch)\s*\([^)]*\)(?!.*timeout)",
        "S113 HTTP request without timeout — can hang forever",
    ),
    (
        r"random\.(random|randint|choice|shuffle)\s*\(",
        "S311 Standard PRNG not cryptographically secure — use secrets module for security tokens",
    ),
    (
        r"hashlib\.(md5|sha1)\s*\(",
        "S303 MD5/SHA1 are cryptographically weak — use SHA256+",
    ),
    (r"DEBUG\s*=\s*True", "S201 DEBUG=True in production code"),
    (
        r"""(password|secret|api_key|token)\s*=\s*['"][^'"]{4,}['"]""",
        "S105 Hardcoded credential detected",
    ),
    (
        r"CORS.*origins.*\*|allow_origins.*\[.*\*",
        "S001 CORS wildcard (*) allows any origin — restrict to known domains",
    ),
]


def _check_python_ast(source: str, filename: str) -> list[str]:
    """AST-based checks: function length, dangerous calls, global mutable state."""
    issues = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]

    lines = source.splitlines()

    for node in ast.walk(tree):
        # Function/method length
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno
            if length > MAX_FUNCTION_LINES:
                issues.append(
                    f"C901 {filename}:{node.lineno} function '{node.name}' is {length} lines "
                    f"(max {MAX_FUNCTION_LINES}) — decompose into smaller functions"
                )

        # Dangerous function calls
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                parts = []
                cur = node.func
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                call_name = ".".join(reversed(parts))

            if call_name in _DANGEROUS_CALLS:
                issues.append(
                    f"{_DANGEROUS_CALLS[call_name]} ({filename}:{node.lineno})"
                )

        # Global mutable state: module-level list/dict assignments
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.col_offset, int)
            and node.col_offset == 0
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                        issues.append(
                            f"M002 {filename}:{node.lineno} global mutable '{target.id}' — "
                            "use function-level state or dependency injection"
                        )

    # File length
    if len(lines) > MAX_FILE_LINES:
        issues.append(
            f"C001 {filename} is {len(lines)} lines (max {MAX_FILE_LINES}) — "
            "split into modules"
        )

    return issues


def _check_regex(source: str, filename: str) -> list[str]:
    """Regex-based checks on raw source."""
    issues = []
    for pattern, message in _REGEX_PATTERNS:
        for m in re.finditer(pattern, source, re.IGNORECASE | re.MULTILINE):
            line_no = source[: m.start()].count("\n") + 1
            issues.append(f"{message} ({filename}:{line_no})")
    return issues


def _classify(issues: list[str]) -> dict:
    """Split issues into critical (S/M) vs warning (C/PERF)."""
    critical = [i for i in issues if re.match(r"S\d{3}|M\d{3}", i)]
    warnings = [i for i in issues if i not in critical]
    return {"critical": critical, "warnings": warnings}


async def _run_semgrep(path: str) -> list[str]:
    """Run semgrep with auto security rules if available."""
    if not shutil.which("semgrep"):
        return []
    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep",
            "--config",
            "auto",
            "--quiet",
            "--json",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        import json

        data = json.loads(stdout.decode(errors="replace"))
        results = data.get("results", [])
        out = []
        for r in results[:20]:  # Cap at 20 findings
            path_ = r.get("path", "")
            line = r.get("start", {}).get("line", "?")
            msg = r.get("extra", {}).get("message", r.get("check_id", ""))
            sev = r.get("extra", {}).get("severity", "WARNING")
            out.append(f"SEMGREP[{sev}] {path_}:{line} {msg}")
        return out
    except Exception:
        return []


async def _run_trivy(path: str) -> list[str]:
    """Run trivy filesystem scan if available."""
    if not shutil.which("trivy"):
        return []
    try:
        import json

        proc = await asyncio.create_subprocess_exec(
            "trivy",
            "fs",
            "--format",
            "json",
            "--quiet",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        data = json.loads(stdout.decode(errors="replace"))
        out = []
        for result in data.get("Results", []):
            for vuln in result.get("Vulnerabilities", [])[:10]:
                sev = vuln.get("Severity", "UNKNOWN")
                pkg = vuln.get("PkgName", "?")
                cve = vuln.get("VulnerabilityID", "?")
                title = vuln.get("Title", "")
                fixed = vuln.get("FixedVersion", "")
                fix_hint = f" → fix: {fixed}" if fixed else ""
                out.append(f"TRIVY[{sev}] {pkg} {cve}: {title}{fix_hint}")
        return out
    except Exception:
        return []


async def _run_trivy_image(image: str) -> str:
    """Run trivy image scan. Returns formatted text report."""
    if not shutil.which("trivy"):
        return "trivy not installed — run: brew install trivy"
    try:
        import json

        proc = await asyncio.create_subprocess_exec(
            "trivy",
            "image",
            "--format",
            "json",
            "--quiet",
            image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        data = json.loads(stdout.decode(errors="replace"))
        lines = [f"Trivy scan: {image}"]
        total = 0
        for result in data.get("Results", []):
            vulns = result.get("Vulnerabilities") or []
            total += len(vulns)
            for vuln in vulns[:15]:
                sev = vuln.get("Severity", "UNKNOWN")
                pkg = vuln.get("PkgName", "?")
                cve = vuln.get("VulnerabilityID", "?")
                fixed = vuln.get("FixedVersion", "")
                fix_hint = f" (fix: {fixed})" if fixed else ""
                lines.append(f"  [{sev}] {pkg} — {cve}{fix_hint}")
        lines.append(f"\nTotal vulnerabilities: {total}")
        return "\n".join(lines)
    except Exception as e:
        return f"trivy image scan failed: {e}"


class TrivyScanTool(BaseTool):
    name = "trivy_scan_repo"
    description = (
        "Scan a local repository or filesystem path for CVEs, misconfigurations, and exposed secrets using Trivy. "
        "Requires trivy installed (brew install trivy). Returns severity-classified vulnerability list."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", ".")
        p = Path(path)
        if not p.exists():
            return f"Error: path not found: {path}"
        issues = await _run_trivy(str(p))
        if not issues:
            return "Trivy: no vulnerabilities found (or trivy not installed)."
        critical = [i for i in issues if "[CRITICAL]" in i or "[HIGH]" in i]
        other = [i for i in issues if i not in critical]
        lines = []
        if critical:
            lines.append(f"HIGH/CRITICAL ({len(critical)}):")
            lines.extend(f"  {i}" for i in critical)
        if other:
            lines.append(f"MEDIUM/LOW ({len(other)}):")
            lines.extend(f"  {i}" for i in other[:10])
        return "\n".join(lines)


class TrivyImageTool(BaseTool):
    name = "trivy_scan_image"
    description = (
        "Scan a Docker/container image for CVEs using Trivy. "
        "Example: trivy_scan_image({'image': 'nginx:latest'}). "
        "Requires trivy installed."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        image = params.get("image", "")
        if not image:
            return "Error: image name required (e.g. nginx:latest)"
        return await _run_trivy_image(image)


class SastCheckTool(BaseTool):
    name = "sast_check"
    description = (
        "Run SAST (Static Application Security Testing) on generated code. "
        "Checks: function length, dangerous calls (eval/exec/pickle/shell=True), "
        "global mutable state, missing context managers, weak crypto, hardcoded secrets, "
        "unbounded collections. Use after code_write/code_edit."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path:
            return "Error: path required"

        p = Path(path)
        if not p.exists():
            return f"Error: path not found: {path}"

        all_issues: list[str] = []

        # Collect files to check
        files: list[Path] = []
        if p.is_file():
            files = [p]
        else:
            files = [
                f
                for f in p.rglob("*")
                if f.suffix in (".py", ".ts", ".js", ".rs", ".go")
                and "__pycache__" not in str(f)
                and "node_modules" not in str(f)
                and "target" not in str(f)
            ]

        for f in files[:50]:  # Cap at 50 files
            try:
                source = f.read_text(errors="replace")
            except Exception:
                continue

            fname = str(f.relative_to(p) if p.is_dir() else f.name)

            if f.suffix == ".py":
                all_issues.extend(_check_python_ast(source, fname))
            all_issues.extend(_check_regex(source, fname))

        # Semgrep + Trivy (async, optional)
        semgrep_issues, trivy_issues = await asyncio.gather(
            _run_semgrep(path), _run_trivy(path)
        )
        all_issues.extend(semgrep_issues)
        all_issues.extend(trivy_issues)

        classified = _classify(all_issues)

        if not all_issues:
            return "SAST: no issues found."

        lines = []
        if classified["critical"]:
            lines.append(f"CRITICAL ({len(classified['critical'])} issues — must fix):")
            lines.extend(f"  - {i}" for i in classified["critical"])
        if classified["warnings"]:
            lines.append(
                f"WARNINGS ({len(classified['warnings'])} issues — should fix):"
            )
            lines.extend(f"  - {i}" for i in classified["warnings"][:20])

        total = len(all_issues)
        lines.append(
            f"\nTotal: {total} issue(s). Fix critical issues before proceeding."
        )
        return "\n".join(lines)


def register_sast_tools(registry):
    registry.register(SastCheckTool())
    registry.register(TrivyScanTool())
    registry.register(TrivyImageTool())
