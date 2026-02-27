"""
Git Tools - Version control operations for agents.
====================================================
Git branch isolation: agents commit to agent/{agent_id}/ branches, never main/master.
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool
from . import rtk_run

# Protected branches — agents cannot commit directly
_PROTECTED_BRANCHES = {"main", "master", "develop", "release", "production", "staging"}


def _current_branch(cwd: str) -> str:
    """Get current git branch name."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
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
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=5,
    )
    if check.returncode == 0:
        # Branch exists, checkout
        subprocess.run(
            ["git", "checkout", branch_name], capture_output=True, cwd=cwd, timeout=10
        )
    else:
        # Create new branch from current
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            cwd=cwd,
            timeout=10,
        )
    return ""


class GitInitTool(BaseTool):
    name = "git_init"
    description = "Initialize a git repository in the given directory (git init + initial commit if files exist)"
    category = "git"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        initial_message = params.get("message", "chore: initial commit")
        try:
            # Check if already a git repo
            check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=5,
            )
            if check.returncode == 0:
                return f"Already a git repository at {cwd} (branch: {_current_branch(cwd)})"

            subprocess.run(["git", "init"], cwd=cwd, timeout=10, check=True)
            subprocess.run(
                ["git", "config", "user.email", "agent@software-factory"],
                cwd=cwd,
                timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.name", "Software Factory Agent"],
                cwd=cwd,
                timeout=5,
            )

            # Stage and commit if there are files
            status = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=5,
            )
            if status.stdout.strip():
                subprocess.run(["git", "add", "-A"], cwd=cwd, timeout=10, check=True)
                r = subprocess.run(
                    ["git", "commit", "-m", initial_message],
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30,
                )
                return f"Git initialized at {cwd}\n{r.stdout or r.stderr}".strip()
            return f"Git initialized at {cwd} (empty repo, no files to commit)"
        except Exception as e:
            return f"Error: {e}"


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show git status"
    category = "git"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        try:
            r = rtk_run(
                ["git", "--no-pager", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=10,
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
            r = rtk_run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
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
            r = rtk_run(
                [
                    "git",
                    "--no-pager",
                    "log",
                    f"--max-count={limit}",
                    "--oneline",
                    "--decorate",
                ],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=10,
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
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30,
            )
            return (r.stdout or r.stderr) + branch_msg
        except Exception as e:
            return f"Error: {e}"


class GitPushTool(BaseTool):
    name = "git_push"
    description = "Push current agent branch to remote origin"
    category = "git"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        remote = params.get("remote", "origin")
        try:
            branch = _current_branch(cwd)
            if not branch:
                return "Error: could not determine current branch"
            r = subprocess.run(
                ["git", "push", "--set-upstream", remote, branch],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60,
            )
            if r.returncode == 0:
                return f"Pushed branch '{branch}' to {remote}.\n{r.stdout.strip()}"
            return f"Push failed:\n{r.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"


class GitCreatePRTool(BaseTool):
    name = "git_create_pr"
    description = "Create a GitHub Pull Request from current branch to base branch (default: main)"
    category = "git"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        title = params.get("title", "")
        body = params.get("body", "")
        base = params.get("base", "main")
        if not title:
            return "Error: PR title required"
        try:
            branch = _current_branch(cwd)
            if not branch:
                return "Error: could not determine current branch"
            # Push first if not already pushed
            subprocess.run(
                ["git", "push", "--set-upstream", "origin", branch],
                capture_output=True,
                cwd=cwd,
                timeout=60,
            )
            cmd = [
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body or f"Automated fix by agent on branch `{branch}`",
                "--base",
                base,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)
            if r.returncode == 0:
                pr_url = r.stdout.strip()
                # Fire PR notification
                try:
                    from ..services.notifications import emit_notification
                    from ..services.notification_service import (
                        get_notification_service,
                        NotificationPayload,
                    )

                    agent_name = getattr(agent, "id", "agent") if agent else "agent"
                    emit_notification(
                        f"PR Created: {title}",
                        type="pr",
                        message=f"Agent {agent_name} created a PR: {pr_url}",
                        url=pr_url,
                        severity="info",
                        source="git",
                    )
                    svc = get_notification_service()
                    if svc.is_configured:
                        import asyncio

                        payload = NotificationPayload(
                            event="pr_created",
                            title=f"PR Created: {title}",
                            message=f"{pr_url}\n\nAgent: {agent_name}",
                            severity="info",
                        )
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(svc.notify(payload))
                        except RuntimeError:
                            pass
                except Exception:
                    pass
                # Auto-launch code review mission
                try:
                    import asyncio
                    from ..missions.store import MissionDef, get_mission_store

                    pr_number = pr_url.rstrip("/").split("/")[-1]
                    ms = get_mission_store()
                    review_mission = MissionDef(
                        name=f"PR Review: {title[:80]}",
                        description=f"Automated code review for PR #{pr_number}",
                        goal=f"Review PR #{pr_number} ({pr_url}) and post structured feedback",
                        type="program",
                        workflow_id="pr-auto-review",
                        created_by="code-reviewer",
                        config={
                            "pr_ref": pr_number,
                            "pr_url": pr_url,
                            "pr_title": title,
                            "cwd": cwd,
                            "auto_provisioned": True,
                        },
                    )
                    ms.create_mission(review_mission)
                except Exception:
                    pass  # Non-blocking
                return f"PR created: {pr_url}"
            # gh not available — output branch URL hint
            return (
                f"gh CLI not available ({r.stderr.strip()[:200]}). "
                f"Branch '{branch}' is ready — create PR manually at GitHub."
            )
        except Exception as e:
            return f"Error: {e}"


class GitGetPRDiffTool(BaseTool):
    name = "git_get_pr_diff"
    description = (
        "Fetch the diff of a GitHub Pull Request for code review (by PR number or URL)"
    )
    category = "git"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        pr = params.get("pr", "")
        cwd = params.get("cwd", ".")
        if not pr:
            return "Error: pr (number or URL) required"
        try:
            # Extract PR number from URL if needed
            pr_ref = str(pr).split("/")[-1] if "github.com" in str(pr) else str(pr)
            # Get PR metadata
            meta_r = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    pr_ref,
                    "--json",
                    "title,number,author,baseRefName,headRefName,body",
                ],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30,
            )
            # Get diff
            diff_r = subprocess.run(
                ["gh", "pr", "diff", pr_ref],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60,
            )
            if diff_r.returncode != 0:
                return f"Error fetching PR diff: {diff_r.stderr.strip()[:300]}"
            diff = diff_r.stdout
            # Truncate large diffs
            MAX = 12000
            if len(diff) > MAX:
                diff = (
                    diff[:MAX]
                    + f"\n\n... [diff truncated at {MAX} chars — {len(diff_r.stdout)} total] ..."
                )
            meta = meta_r.stdout if meta_r.returncode == 0 else ""
            return f"PR #{pr_ref} metadata:\n{meta}\n\nDiff:\n{diff}"
        except FileNotFoundError:
            return "Error: gh CLI not installed"
        except Exception as e:
            return f"Error: {e}"


class GitPostPRReviewTool(BaseTool):
    name = "git_post_pr_review"
    description = "Post a code review comment on a GitHub Pull Request (approve, request-changes, or comment)"
    category = "git"
    requires_approval = False  # Agent-initiated review is safe

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        pr = params.get("pr", "")
        body = params.get("body", "")
        event = params.get("event", "COMMENT")  # APPROVE | REQUEST_CHANGES | COMMENT
        cwd = params.get("cwd", ".")
        if not pr or not body:
            return "Error: pr and body required"
        # Map to gh review event flags
        event_map = {
            "APPROVE": "--approve",
            "REQUEST_CHANGES": "--request-changes",
            "COMMENT": "--comment",
        }
        event_flag = event_map.get(event.upper(), "--comment")
        try:
            pr_ref = str(pr).split("/")[-1] if "github.com" in str(pr) else str(pr)
            r = subprocess.run(
                ["gh", "pr", "review", pr_ref, event_flag, "--body", body],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60,
            )
            if r.returncode == 0:
                return f"Review posted on PR #{pr_ref} ({event})"
            return f"Error posting review: {r.stderr.strip()[:300]}"
        except FileNotFoundError:
            return "Error: gh CLI not installed"
        except Exception as e:
            return f"Error: {e}"


def register_git_tools(registry):
    """Register all git tools."""
    registry.register(GitInitTool())
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitCommitTool())
    registry.register(GitPushTool())
    registry.register(GitCreatePRTool())
    registry.register(GitGetPRDiffTool())
    registry.register(GitPostPRReviewTool())
