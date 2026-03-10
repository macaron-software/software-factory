"""Git Service — read-only git operations for local repositories."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitStatus:
    branch: str = "unknown"
    commit_hash: str = ""
    commit_message: str = ""
    commit_date: str = ""
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    modified: int = 0
    untracked: int = 0
    clean: bool = True


@dataclass
class GitCommit:
    hash: str
    short_hash: str
    message: str
    author: str
    date: str


@dataclass
class GitFileChange:
    status: str  # M, A, D, R, ?
    path: str


def _run(repo_path: str, *args: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-pager", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def get_status(repo_path: str) -> GitStatus:
    p = Path(repo_path)
    if not p.is_dir():
        return GitStatus()

    # Check if inside any git repo
    git_dir = _run(repo_path, "rev-parse", "--git-dir")
    if not git_dir:
        return GitStatus()

    status = GitStatus()

    status.branch = _run(repo_path, "branch", "--show-current") or _run(
        repo_path, "rev-parse", "--short", "HEAD"
    )

    log_line = _run(repo_path, "log", "-1", "--format=%H|%h|%s|%an|%ar")
    if log_line and "|" in log_line:
        parts = log_line.split("|", 4)
        if len(parts) >= 5:
            status.commit_hash = parts[0]
            status.commit_message = parts[2]
            status.commit_date = parts[4]

    porcelain = _run(repo_path, "status", "--porcelain")
    if porcelain:
        status.clean = False
        for line in porcelain.splitlines():
            if len(line) < 2:
                continue
            idx, wt = line[0], line[1]
            if idx in "MADRC" and wt == " ":
                status.staged += 1
            elif wt in "MD":
                status.modified += 1
            elif line.startswith("??"):
                status.untracked += 1
    else:
        status.clean = True

    ab = _run(repo_path, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if ab and "\t" in ab:
        parts = ab.split("\t")
        try:
            status.behind = int(parts[0])
            status.ahead = int(parts[1])
        except (ValueError, IndexError):
            pass

    return status


def get_log(repo_path: str, count: int = 20) -> list[GitCommit]:
    raw = _run(repo_path, "log", f"-{count}", "--format=%H|%h|%s|%an|%ar")
    if not raw:
        return []

    commits = []
    for line in raw.splitlines():
        parts = line.split("|", 4)
        if len(parts) >= 5:
            commits.append(GitCommit(
                hash=parts[0], short_hash=parts[1],
                message=parts[2], author=parts[3], date=parts[4],
            ))
    return commits


def get_changes(repo_path: str) -> list[GitFileChange]:
    raw = _run(repo_path, "status", "--porcelain")
    if not raw:
        return []

    changes = []
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        status_code = line[:2].strip() or "?"
        filepath = line[3:]
        changes.append(GitFileChange(status=status_code, path=filepath))
    return changes


def get_branches(repo_path: str) -> list[str]:
    raw = _run(repo_path, "branch", "--format=%(refname:short)")
    if not raw:
        return []
    return [b.strip() for b in raw.splitlines() if b.strip()]


def get_diff_stat(repo_path: str) -> str:
    return _run(repo_path, "diff", "--stat")
