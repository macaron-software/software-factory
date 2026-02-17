"""
Git Tools - Version control operations for agents.
====================================================
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show git status"
    category = "git"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        try:
            r = subprocess.run(
                ["git", "--no-pager", "status", "--short"],
                capture_output=True, text=True, cwd=cwd, timeout=10,
            )
            return r.stdout or "Clean working tree"
        except Exception as e:
            return f"Error: {e}"


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Show git diff"
    category = "git"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        path = params.get("path", "")
        cmd = ["git", "--no-pager", "diff"]
        if path:
            cmd.extend(["--", path])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
            return r.stdout[:10000] or "No changes"
        except Exception as e:
            return f"Error: {e}"


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Show recent git commits"
    category = "git"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        limit = params.get("limit", 10)
        try:
            r = subprocess.run(
                ["git", "--no-pager", "log", f"--max-count={limit}",
                 "--oneline", "--decorate"],
                capture_output=True, text=True, cwd=cwd, timeout=10,
            )
            return r.stdout or "No commits"
        except Exception as e:
            return f"Error: {e}"


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage files and commit"
    category = "git"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        files = params.get("files", [])
        message = params.get("message", "")
        if not message:
            return "Error: commit message required"
        try:
            if files:
                subprocess.run(["git", "add"] + files, cwd=cwd, timeout=10, check=True)
            else:
                subprocess.run(["git", "add", "-A"], cwd=cwd, timeout=10, check=True)
            r = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True, cwd=cwd, timeout=30,
            )
            return r.stdout or r.stderr
        except Exception as e:
            return f"Error: {e}"


def register_git_tools(registry):
    """Register all git tools."""
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitCommitTool())
