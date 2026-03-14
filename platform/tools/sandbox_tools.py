"""
Sandbox Tools — exposes CommandRunner / SandboxExecutor to agents.
===================================================================
WHY: Agents need a safe way to execute shell commands without importing
sandbox internals directly. These tools wrap platform/tools/sandbox.py
and surface the result as JSON, including sandbox mode and Landlock status.
"""
# Ref: feat-tool-builder

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from .registry import BaseTool

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)


class SandboxRunTool(BaseTool):
    name = "sandbox_run"
    description = (
        "Run a shell command inside the platform sandbox. "
        "Returns JSON: {stdout, stderr, returncode, sandboxed}. "
        "params: command (str), workspace (str, default '.')"
    )
    category = "sandbox"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        command = params.get("command", "")
        workspace = params.get("workspace", ".")
        if not command:
            return json.dumps({"error": "command is required"})
        try:
            from .sandbox import get_sandbox

            result = get_sandbox(workspace).run(command)
            return json.dumps(
                {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "sandboxed": result.sandboxed,
                }
            )
        except Exception as exc:
            logger.error("sandbox_run failed: %s", exc)
            return json.dumps({"error": str(exc)})


class SandboxCheckTool(BaseTool):
    name = "sandbox_check"
    description = (
        "Check sandbox capabilities: Landlock availability, Docker sandbox mode, runner path. "
        "No params required. Returns JSON: {landlock_available, landlock_enabled, docker_sandbox, runner_path}."
    )
    category = "sandbox"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        try:
            from .sandbox import LANDLOCK_ENABLED, _LANDLOCK_PATH

            runner_path = _LANDLOCK_PATH or ""
            landlock_available = bool(runner_path and os.path.isfile(runner_path))

            try:
                from .sandbox import DOCKER_ENABLED

                docker_sandbox = bool(DOCKER_ENABLED)
            except ImportError:
                docker_sandbox = False

            return json.dumps(
                {
                    "landlock_available": landlock_available,
                    "landlock_enabled": bool(LANDLOCK_ENABLED),
                    "docker_sandbox": docker_sandbox,
                    "runner_path": runner_path,
                }
            )
        except Exception as exc:
            logger.error("sandbox_check failed: %s", exc)
            return json.dumps({"error": str(exc)})


def register_sandbox_tools(registry) -> None:
    registry.register(SandboxRunTool())
    registry.register(SandboxCheckTool())
    logger.debug("Sandbox tools registered (2 tools)")
