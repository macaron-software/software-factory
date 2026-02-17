"""
Build Tools - Build, test, lint operations (bridges to Factory core).
======================================================================
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool


class BuildTool(BaseTool):
    name = "build"
    description = "Build a project"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: build command required"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=300,
            )
            output = r.stdout[-3000:] if r.returncode == 0 else r.stderr[-3000:]
            status = "[OK] SUCCESS" if r.returncode == 0 else f"[FAIL] FAILED (exit {r.returncode})"
            return f"{status}\n{output}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (300s)"
        except Exception as e:
            return f"Error: {e}"


class TestTool(BaseTool):
    name = "test"
    description = "Run tests"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: test command required"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=300,
            )
            output = r.stdout[-3000:] + r.stderr[-1000:]
            status = "[OK] PASS" if r.returncode == 0 else f"[FAIL] FAIL (exit {r.returncode})"
            return f"{status}\n{output}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (300s)"
        except Exception as e:
            return f"Error: {e}"


class LintTool(BaseTool):
    name = "lint"
    description = "Run linter"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: lint command required"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=120,
            )
            output = r.stdout[-3000:] + r.stderr[-1000:]
            status = "[OK] CLEAN" if r.returncode == 0 else "[WARN] ISSUES"
            return f"{status}\n{output}"
        except Exception as e:
            return f"Error: {e}"


def register_build_tools(registry):
    """Register all build tools."""
    registry.register(BuildTool())
    registry.register(TestTool())
    registry.register(LintTool())
