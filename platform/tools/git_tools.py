"""
Git Tools - Version control operations for agents.
====================================================
Git branch isolation: agents commit to agent/{agent_id}/ branches, never main/master.
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool

# Protected branches — agents cannot commit directly
_PROTECTED_BRANCHES = {"main", "master", "develop", "release", "production", "staging"}


def _current_branch(cwd: str) -> str:
    """Get current git branch name."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=cwd, timeout=5,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _ensure_agent_branch(cwd: str, agent_id: str, session_id: str = "") -> str:
    """Create/checkout an agent-specific branch. Returns branch name or error."""
    branch_suffix = session_id[:8] if session_id else "work"
    branch_name = f"agent/{agent_id}/{branch_suffix}"

    current = _current_branch(cwd)
    if current == branch_name:
        return ""  # already on correct branch

    # Check if branch exists
    check = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True, cwd=cwd, timeout=5,
    )
    if check.returncode == 0:
        # Branch exists, checkout
        subprocess.run(["git", "checkout", branch_name],
                        capture_output=True, cwd=cwd, timeout=10)
    else:
        # Create new branch from current
        subprocess.run(["git", "checkout", "-b", branch_name],
                        capture_output=True, cwd=cwd, timeout=10)
    return ""


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
            branch = _current_branch(cwd)
            status = r.stdout or "Clean working tree"
            return f"[branch: {branch}]\n{status}"
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
    description = "Stage files and commit (auto-creates agent branch)"
    category = "git"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        files = params.get("files", [])
        message = params.get("message", "")
        if not message:
            return "Error: commit message required"

        agent_id = params.get("_agent_id", "unknown")
        session_id = params.get("_session_id", "")

        try:
            # Git branch isolation: ensure we're on an agent branch
            current = _current_branch(cwd)
            if current in _PROTECTED_BRANCHES:
                err = _ensure_agent_branch(cwd, agent_id, session_id)
                if err:
                    return f"Error: could not create agent branch: {err}"
                new_branch = _current_branch(cwd)
                branch_msg = f" (auto-switched to branch: {new_branch})"
            else:
                branch_msg = f" (on branch: {current})"

            if files:
                subprocess.run(["git", "add"] + files, cwd=cwd, timeout=10, check=True)
            else:
                subprocess.run(["git", "add", "-A"], cwd=cwd, timeout=10, check=True)
            r = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True, cwd=cwd, timeout=30,
            )
            return (r.stdout or r.stderr) + branch_msg
        except Exception as e:
            return f"Error: {e}"


def register_git_tools(registry):
    """Register all git tools."""
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitCommitTool())
