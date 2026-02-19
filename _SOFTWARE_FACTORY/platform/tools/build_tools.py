"""
Build Tools - Build, test, lint operations (bridges to Factory core).
======================================================================
Uses Docker sandbox for isolation when SANDBOX_ENABLED=true.
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool
from .sandbox import get_sandbox, SANDBOX_ENABLED


class BuildTool(BaseTool):
    name = "build"
    description = "Build a project"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: build command required"
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        output = result.stdout[-3000:] if result.returncode == 0 else result.stderr[-3000:]
        status = "[OK] SUCCESS" if result.returncode == 0 else f"[FAIL] FAILED (exit {result.returncode})"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


class TestTool(BaseTool):
    name = "test"
    description = "Run tests"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: test command required"
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        output = result.stdout[-3000:] + result.stderr[-1000:]
        status = "[OK] PASS" if result.returncode == 0 else f"[FAIL] FAIL (exit {result.returncode})"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


class LintTool(BaseTool):
    name = "lint"
    description = "Run linter"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: lint command required"
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=120)
        output = result.stdout[-3000:] + result.stderr[-1000:]
        status = "[OK] CLEAN" if result.returncode == 0 else "[WARN] ISSUES"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


def register_build_tools(registry):
    """Register all build tools."""
    registry.register(BuildTool())
    registry.register(TestTool())
    registry.register(LintTool())
