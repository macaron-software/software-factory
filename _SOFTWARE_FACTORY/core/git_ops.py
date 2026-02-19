"""
Git Operations - Unified git command wrappers
=============================================
Centralizes git diff, commit, reset, status, add operations.
Uses subprocess_util for proper process group cleanup and timeouts.

Usage:
    from core.git_ops import git_diff, git_commit, git_reset, git_status, git_add

    diff = await git_diff(cwd, staged=True)
    sha = await git_commit(cwd, "fix: message", files=["src/main.rs"])
    await git_reset(cwd)
"""

import subprocess
from typing import Callable, List, Optional

from core.subprocess_util import run_subprocess


async def git_diff(
    cwd: str,
    staged: bool = False,
    context_lines: int = 20,
    files: List[str] = None,
    log_fn: Callable = None,
) -> str:
    """
    Get git diff output.

    Args:
        cwd: Repository root
        staged: If True, show staged changes (--cached)
        context_lines: Context lines around changes (-U)
        files: Specific files to diff
        log_fn: Optional log function

    Returns:
        Diff output string (empty if no changes)
    """
    cmd = f"git diff -U{context_lines}"
    if staged:
        cmd += " --cached"
    if files:
        cmd += " -- " + " ".join(f'"{f}"' for f in files)

    rc, stdout, _ = await run_subprocess(cmd, timeout=30, cwd=cwd, log_fn=log_fn)
    return stdout if rc == 0 else ""


async def git_add(
    cwd: str,
    files: List[str] = None,
    all: bool = False,
    log_fn: Callable = None,
) -> bool:
    """
    Stage files for commit.

    Args:
        cwd: Repository root
        files: Specific files to add (mutually exclusive with all)
        all: Add all changes (-A)
        log_fn: Optional log function

    Returns:
        True on success
    """
    if all:
        cmd = "git add -A"
    elif files:
        safe_files = " ".join(f'"{f}"' for f in files)
        cmd = f"git add {safe_files}"
    else:
        return True  # Nothing to add

    rc, _, _ = await run_subprocess(cmd, timeout=60, cwd=cwd, log_fn=log_fn)
    return rc == 0


async def git_commit(
    cwd: str,
    message: str,
    files: List[str] = None,
    no_verify: bool = False,
    log_fn: Callable = None,
) -> Optional[str]:
    """
    Create a git commit.

    Args:
        cwd: Repository root
        message: Commit message
        files: Files to stage before commit (None = commit staged)
        no_verify: Skip pre-commit hooks
        log_fn: Optional log function

    Returns:
        Commit SHA on success, None on failure
    """
    # Stage files if specified
    if files:
        if not await git_add(cwd, files=files, log_fn=log_fn):
            return None

    # Escape message for shell safety
    safe_msg = message.replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    cmd = f'git commit -m "{safe_msg}"'
    if no_verify:
        cmd = f'git commit --no-verify -m "{safe_msg}"'

    rc, _, stderr = await run_subprocess(cmd, timeout=60, cwd=cwd, log_fn=log_fn)
    if rc != 0:
        if log_fn:
            log_fn(f"Commit failed: {stderr[:200]}", "ERROR")
        return None

    # Get commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd, capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


async def git_reset(
    cwd: str,
    files: List[str] = None,
    log_fn: Callable = None,
) -> bool:
    """
    Reset uncommitted changes.

    Args:
        cwd: Repository root
        files: Specific files to reset (None = reset all)
        log_fn: Optional log function

    Returns:
        True on success
    """
    if files:
        safe_files = " ".join(f'"{f}"' for f in files)
        cmd = f"git checkout -- {safe_files}"
    else:
        cmd = "git checkout -- . && git clean -fd"

    rc, _, _ = await run_subprocess(cmd, timeout=60, cwd=cwd, log_fn=log_fn)
    return rc == 0


async def git_status(
    cwd: str,
    log_fn: Callable = None,
) -> dict:
    """
    Get git status summary.

    Args:
        cwd: Repository root
        log_fn: Optional log function

    Returns:
        Dict with 'changed' (bool), 'files' (list of changed file paths),
        'branch' (str), 'head' (str commit sha)
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd, capture_output=True, text=True, timeout=10,
    )

    files = []
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            if len(line) > 3:
                files.append(line[3:].strip())

    branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=cwd, capture_output=True, text=True, timeout=10,
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd, capture_output=True, text=True, timeout=10,
    )
    head = head_result.stdout.strip() if head_result.returncode == 0 else "unknown"

    return {
        "changed": len(files) > 0,
        "files": files,
        "branch": branch,
        "head": head,
    }


async def git_push(
    cwd: str,
    remote: str = None,
    branch: str = None,
    log_fn: Callable = None,
) -> bool:
    """
    Push to remote.

    Args:
        cwd: Repository root
        remote: Remote name (auto-detected if None)
        branch: Branch name (auto-detected if None)
        log_fn: Optional log function

    Returns:
        True on success
    """
    if not remote:
        result = subprocess.run(
            ["git", "remote"], cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        remotes = result.stdout.strip().split("\n") if result.returncode == 0 else []
        remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")

    if not branch:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "dev"

    cmd = f"git push {remote} {branch}"
    rc, _, stderr = await run_subprocess(cmd, timeout=120, cwd=cwd, log_fn=log_fn)

    if rc != 0 and log_fn:
        log_fn(f"Push failed: {stderr[:200]}", "ERROR")

    return rc == 0
