"""
Security Tools - SAST scanning, dependency audit, secrets detection.
====================================================================
Real security tools (subprocess-based), not LLM guessing.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..models import AgentInstance
from .registry import BaseTool


class SastScanTool(BaseTool):
    """Static Application Security Testing via semgrep or bandit."""

    name = "sast_scan"
    description = (
        "Run static security analysis on workspace code. "
        "Auto-detects language (Python→bandit, JS/TS→semgrep, Rust→cargo-audit). "
        "Returns findings with severity, file, line, and description."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        path = params.get("path", ".")
        target = Path(cwd) / path

        if not target.exists():
            return f"Error: path {target} does not exist"

        # Detect stack
        has_python = any(target.rglob("*.py")) if target.is_dir() else str(target).endswith(".py")
        has_js = any(target.rglob("*.ts")) or any(target.rglob("*.js")) if target.is_dir() else False

        results = []

        if has_python:
            results.append(await self._run_bandit(str(target)))

        if has_js or has_python:
            results.append(await self._run_semgrep(str(target)))

        if not results:
            results.append(await self._run_semgrep(str(target)))

        return "\n\n".join(r for r in results if r)

    async def _run_bandit(self, target: str) -> str:
        try:
            r = subprocess.run(
                ["python3", "-m", "bandit", "-r", target, "-f", "json", "-ll"],
                capture_output=True, text=True, timeout=120,
            )
            if "results" in r.stdout:
                import json
                data = json.loads(r.stdout)
                findings = data.get("results", [])
                if not findings:
                    return "[SAST/bandit] No issues found"
                lines = [f"[SAST/bandit] {len(findings)} finding(s):"]
                for f in findings[:20]:
                    lines.append(
                        f"  {f.get('issue_severity','?')}: {f.get('issue_text','')} "
                        f"({f.get('filename','')}:{f.get('line_number','')})"
                    )
                return "\n".join(lines)
            return f"[SAST/bandit] {r.stdout[:500]}{r.stderr[:500]}"
        except FileNotFoundError:
            return "[SAST/bandit] bandit not installed (pip install bandit)"
        except subprocess.TimeoutExpired:
            return "[SAST/bandit] TIMEOUT (120s)"

    async def _run_semgrep(self, target: str) -> str:
        try:
            r = subprocess.run(
                ["semgrep", "scan", "--config", "auto", "--json", "--quiet", target],
                capture_output=True, text=True, timeout=180,
            )
            if r.stdout:
                import json
                data = json.loads(r.stdout)
                findings = data.get("results", [])
                if not findings:
                    return "[SAST/semgrep] No issues found"
                lines = [f"[SAST/semgrep] {len(findings)} finding(s):"]
                for f in findings[:20]:
                    sev = f.get("extra", {}).get("severity", "?")
                    msg = f.get("extra", {}).get("message", "")[:120]
                    path = f.get("path", "")
                    line = f.get("start", {}).get("line", "")
                    lines.append(f"  {sev}: {msg} ({path}:{line})")
                return "\n".join(lines)
            return f"[SAST/semgrep] {r.stderr[:500]}"
        except FileNotFoundError:
            return "[SAST/semgrep] semgrep not installed (pip install semgrep)"
        except subprocess.TimeoutExpired:
            return "[SAST/semgrep] TIMEOUT (180s)"


class DependencyAuditTool(BaseTool):
    """Scan dependencies for known CVEs."""

    name = "dependency_audit"
    description = (
        "Audit project dependencies for known vulnerabilities (CVEs). "
        "Auto-detects: package.json→npm audit, requirements.txt→pip-audit, "
        "Cargo.toml→cargo audit. Returns CVE list with severity."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        workspace = Path(cwd)
        results = []

        if (workspace / "package.json").exists():
            results.append(await self._npm_audit(str(workspace)))
        if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
            results.append(await self._pip_audit(str(workspace)))
        if (workspace / "Cargo.toml").exists():
            results.append(await self._cargo_audit(str(workspace)))

        if not results:
            return "[AUDIT] No dependency files found (package.json, requirements.txt, Cargo.toml)"

        return "\n\n".join(r for r in results if r)

    async def _npm_audit(self, cwd: str) -> str:
        try:
            r = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True, text=True, cwd=cwd, timeout=60,
            )
            import json
            data = json.loads(r.stdout) if r.stdout else {}
            vulns = data.get("vulnerabilities", {})
            if not vulns:
                return "[AUDIT/npm] No vulnerabilities found"
            lines = [f"[AUDIT/npm] {len(vulns)} vulnerable package(s):"]
            for name, info in list(vulns.items())[:15]:
                sev = info.get("severity", "?")
                via = ", ".join(v if isinstance(v, str) else v.get("title", "") for v in info.get("via", [])[:3])
                lines.append(f"  {sev}: {name} — {via}")
            return "\n".join(lines)
        except FileNotFoundError:
            return "[AUDIT/npm] npm not found"
        except Exception as e:
            return f"[AUDIT/npm] Error: {e}"

    async def _pip_audit(self, cwd: str) -> str:
        try:
            r = subprocess.run(
                ["python3", "-m", "pip_audit", "--format", "json", "--desc"],
                capture_output=True, text=True, cwd=cwd, timeout=120,
            )
            if r.stdout:
                import json
                findings = json.loads(r.stdout)
                if not findings:
                    return "[AUDIT/pip] No vulnerabilities found"
                lines = [f"[AUDIT/pip] {len(findings)} finding(s):"]
                for f in findings[:15]:
                    lines.append(f"  {f.get('name','')} {f.get('version','')}: {f.get('id','')} — {f.get('description','')[:80]}")
                return "\n".join(lines)
            return f"[AUDIT/pip] {r.stderr[:300]}"
        except FileNotFoundError:
            return "[AUDIT/pip] pip-audit not installed (pip install pip-audit)"
        except Exception as e:
            return f"[AUDIT/pip] Error: {e}"

    async def _cargo_audit(self, cwd: str) -> str:
        try:
            r = subprocess.run(
                ["cargo", "audit", "--json"],
                capture_output=True, text=True, cwd=cwd, timeout=120,
            )
            if r.stdout:
                import json
                data = json.loads(r.stdout)
                vulns = data.get("vulnerabilities", {}).get("list", [])
                if not vulns:
                    return "[AUDIT/cargo] No vulnerabilities found"
                lines = [f"[AUDIT/cargo] {len(vulns)} finding(s):"]
                for v in vulns[:15]:
                    adv = v.get("advisory", {})
                    lines.append(f"  {adv.get('id','')}: {adv.get('title','')[:80]} ({adv.get('package','')})")
                return "\n".join(lines)
            return f"[AUDIT/cargo] {r.stderr[:300]}"
        except FileNotFoundError:
            return "[AUDIT/cargo] cargo-audit not installed (cargo install cargo-audit)"
        except Exception as e:
            return f"[AUDIT/cargo] Error: {e}"


class SecretsScanTool(BaseTool):
    """Deterministic secrets detection — grep-based, no LLM."""

    name = "secrets_scan"
    description = (
        "Scan workspace for hardcoded secrets (API keys, tokens, passwords). "
        "Deterministic grep-based detection. Returns file:line for each finding. "
        "Ignores test fixtures, .env.example, and node_modules."
    )
    category = "security"

    PATTERNS = [
        (r'(?:api[_-]?key|apikey)\s*[:=]\s*["\'][a-zA-Z0-9]{16,}', "API_KEY"),
        (r'(?:secret|password|passwd|pwd)\s*[:=]\s*["\'][^"\']{8,}', "SECRET/PASSWORD"),
        (r'(?:token|bearer)\s*[:=]\s*["\'][a-zA-Z0-9._\-]{20,}', "TOKEN"),
        (r'(?:aws_access_key_id|aws_secret)\s*[:=]\s*["\']?[A-Z0-9]{16,}', "AWS_KEY"),
        (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', "PRIVATE_KEY"),
        (r'ghp_[a-zA-Z0-9]{36}', "GITHUB_TOKEN"),
        (r'sk-[a-zA-Z0-9]{32,}', "OPENAI_KEY"),
        (r'xox[bposa]-[a-zA-Z0-9\-]{10,}', "SLACK_TOKEN"),
    ]

    IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "target"}
    IGNORE_FILES = {".env.example", ".env.template", ".env.sample"}

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        workspace = Path(cwd)
        findings = []

        for fpath in workspace.rglob("*"):
            if not fpath.is_file():
                continue
            if any(d in fpath.parts for d in self.IGNORE_DIRS):
                continue
            if fpath.name in self.IGNORE_FILES:
                continue
            if fpath.suffix in {".png", ".jpg", ".ico", ".woff", ".ttf", ".lock", ".pyc"}:
                continue
            # Skip test fixture files
            if "fixture" in str(fpath).lower() or "mock" in str(fpath).lower():
                continue

            try:
                content = fpath.read_text(errors="ignore")
            except Exception:
                continue

            for pattern, label in self.PATTERNS:
                for m in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[:m.start()].count("\n") + 1
                    match_text = m.group()[:60] + "..." if len(m.group()) > 60 else m.group()
                    rel = fpath.relative_to(workspace)
                    findings.append(f"  {label}: {rel}:{line_num} — {match_text}")

        if not findings:
            return "[SECRETS] No hardcoded secrets detected"

        return f"[SECRETS] {len(findings)} potential secret(s) found:\n" + "\n".join(findings[:30])


def register_security_tools(registry):
    """Register security scanning tools."""
    registry.register(SastScanTool())
    registry.register(DependencyAuditTool())
    registry.register(SecretsScanTool())
