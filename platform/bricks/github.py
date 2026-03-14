"""GitHub brick — issue, PR, and Actions integration via gh CLI."""
# Ref: feat-tool-builder

from __future__ import annotations

import asyncio
import logging
import os

from . import BrickDef, BrickRegistry, ToolDef

logger = logging.getLogger(__name__)


async def _run_gh(args: str, cwd: str = "") -> str:
    """Run a gh CLI command and return output."""
    cmd = f"gh {args}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return f"Error: {(stderr or b'').decode('utf-8', errors='replace')}"
        return (stdout or b"").decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return "Error: gh command timed out after 30s"
    except Exception as e:
        return f"Error: {e}"


async def create_issue(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    title = args.get("title", "")
    body = args.get("body", "")
    labels = args.get("labels", "")
    cmd = f'issue create --repo {repo} --title "{title}" --body "{body}"'
    if labels:
        cmd += f' --label "{labels}"'
    return await _run_gh(cmd)


async def list_issues(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    state = args.get("state", "open")
    limit = args.get("limit", 10)
    return await _run_gh(f"issue list --repo {repo} --state {state} --limit {limit}")


async def create_pr(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    title = args.get("title", "")
    body = args.get("body", "")
    base = args.get("base", "main")
    head = args.get("head", "")
    cmd = f'pr create --repo {repo} --title "{title}" --body "{body}" --base {base}'
    if head:
        cmd += f" --head {head}"
    return await _run_gh(cmd)


async def list_prs(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    state = args.get("state", "open")
    limit = args.get("limit", 10)
    return await _run_gh(f"pr list --repo {repo} --state {state} --limit {limit}")


async def list_workflows(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    return await _run_gh(f"workflow list --repo {repo}")


async def trigger_workflow(args: dict, ctx=None) -> str:
    repo = args.get("repo", "")
    workflow = args.get("workflow", "")
    ref = args.get("ref", "main")
    return await _run_gh(f"workflow run {workflow} --repo {repo} --ref {ref}")


BRICK = BrickDef(
    id="github",
    name="GitHub",
    description="GitHub integration: issues, PRs, Actions via gh CLI",
    tools=[
        ToolDef(
            name="gh_create_issue",
            description="Create a GitHub issue",
            parameters={"repo": "str (owner/repo)", "title": "str", "body": "str", "labels": "str (optional)"},
            execute=create_issue,
            category="github",
        ),
        ToolDef(
            name="gh_list_issues",
            description="List GitHub issues",
            parameters={"repo": "str (owner/repo)", "state": "open|closed", "limit": "int"},
            execute=list_issues,
            category="github",
        ),
        ToolDef(
            name="gh_create_pr",
            description="Create a GitHub pull request",
            parameters={"repo": "str (owner/repo)", "title": "str", "body": "str", "base": "str", "head": "str"},
            execute=create_pr,
            category="github",
        ),
        ToolDef(
            name="gh_list_prs",
            description="List GitHub pull requests",
            parameters={"repo": "str (owner/repo)", "state": "open|closed", "limit": "int"},
            execute=list_prs,
            category="github",
        ),
        ToolDef(
            name="gh_list_workflows",
            description="List GitHub Actions workflows",
            parameters={"repo": "str (owner/repo)"},
            execute=list_workflows,
            category="github",
        ),
        ToolDef(
            name="gh_trigger_workflow",
            description="Trigger a GitHub Actions workflow",
            parameters={"repo": "str (owner/repo)", "workflow": "str", "ref": "str"},
            execute=trigger_workflow,
            category="github",
        ),
    ],
    roles=["devops", "pm", "cto", "rte"],
    requires_env=["GH_TOKEN"],
)


def register(registry: BrickRegistry) -> None:
    registry.register(BRICK)
