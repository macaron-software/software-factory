"""
Dependency Tools — Manifest parsing and security auditing.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil

from .registry import BaseTool
from ..models import AgentInstance

TIMEOUT = 30

MANIFEST_NAMES = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "package.json": "javascript",
    "Cargo.toml": "rust",
    "go.mod": "go",
}

AUDIT_CONFIG = {
    "python": {"bin": "pip-audit", "cmd": lambda p: ["pip-audit", "-r", p]},
    "javascript": {"bin": "npm", "cmd": lambda p: ["npm", "audit", "--json", "--prefix", os.path.dirname(p) or "."]},
    "rust": {"bin": "cargo", "cmd": lambda _: ["cargo", "audit"]},
    "go": {"bin": "go", "cmd": lambda _: ["go", "vuln", "./..."]},
}


def _find_manifest(path: str) -> tuple[str, str] | None:
    if os.path.isfile(path):
        name = os.path.basename(path)
        lang = MANIFEST_NAMES.get(name)
        if lang:
            return path, lang
        return None
    for name, lang in MANIFEST_NAMES.items():
        candidate = os.path.join(path, name)
        if os.path.isfile(candidate):
            return candidate, lang
    return None


def _parse_requirements_txt(text: str) -> list[str]:
    deps = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            deps.append(line)
    return deps


def _parse_package_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ["Error: invalid JSON"]
    deps = []
    for section in ("dependencies", "devDependencies"):
        for name, version in data.get(section, {}).items():
            deps.append(f"{name}@{version} ({section})")
    return deps


def _parse_cargo_toml(text: str) -> list[str]:
    deps = []
    in_deps = False
    for line in text.splitlines():
        if re.match(r'^\[.*dependencies.*\]', line):
            in_deps = True
            continue
        if line.startswith("["):
            in_deps = False
            continue
        if in_deps:
            m = re.match(r'^(\w[\w-]*)\s*=\s*(.+)', line)
            if m:
                deps.append(f"{m.group(1)} = {m.group(2).strip()}")
    return deps


def _parse_go_mod(text: str) -> list[str]:
    deps = []
    in_require = False
    for line in text.splitlines():
        line = line.strip()
        if line == "require (":
            in_require = True
            continue
        if line == ")":
            in_require = False
            continue
        if in_require and line:
            deps.append(line)
        elif line.startswith("require "):
            deps.append(line.removeprefix("require ").strip())
    return deps


PARSERS = {
    "requirements.txt": _parse_requirements_txt,
    "package.json": _parse_package_json,
    "Cargo.toml": _parse_cargo_toml,
    "go.mod": _parse_go_mod,
}


async def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        return proc.returncode, (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
    except FileNotFoundError:
        return -1, f"{cmd[0]}: command not found"
    except asyncio.TimeoutError:
        proc.kill()
        return -2, f"Timeout ({TIMEOUT}s) exceeded running {cmd[0]}"


class DepCheckTool(BaseTool):
    name = "dep_check"
    description = "Read a manifest file and list dependencies with versions."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("manifest") or params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        result = _find_manifest(path)
        if not result:
            return f"Error: no supported manifest found at {path}"
        manifest_path, lang = result

        name = os.path.basename(manifest_path)
        parser = PARSERS.get(name)
        if not parser:
            return f"Error: no parser for {name}"

        with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        deps = parser(text)
        if not deps:
            return f"No dependencies found in {name}."
        header = f"{name} ({lang}) — {len(deps)} dependencies:"
        return header + "\n" + "\n".join(f"  {d}" for d in deps)


class DepAuditTool(BaseTool):
    name = "dep_audit"
    description = "Audit dependencies for known vulnerabilities."
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("manifest") or params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        result = _find_manifest(path)
        if not result:
            return f"Error: no supported manifest found at {path}"
        manifest_path, lang = result

        cfg = AUDIT_CONFIG.get(lang)
        if not cfg:
            return f"Error: no audit tool configured for {lang}"

        if not shutil.which(cfg["bin"]):
            return f"Error: {cfg['bin']} not installed. Install it to audit {lang} dependencies."

        code, output = await _run(cfg["cmd"](manifest_path), cwd=os.path.dirname(manifest_path) or None)
        if code == 0:
            return "No known vulnerabilities found."

        lines = output.splitlines()
        detail = "\n".join(lines[:50])
        if len(lines) > 50:
            detail += f"\n... ({len(lines) - 50} more lines)"
        return f"Vulnerabilities found:\n{detail}"
