"""Git worktree workspace manager for agent isolation.

Each agent session gets its own git worktree — isolated branch, no file conflicts.
Inspired by agent-orchestrator's workspace plugin.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..interfaces import SessionStatus, WorkspaceInfo, WorkspaceProtocol, WorkspaceType

logger = logging.getLogger(__name__)

WORKSPACES_ROOT = Path.home() / ".macaron" / "workspaces"


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


class WorktreeManager:
    """Creates isolated git worktrees per agent session.

    Layout:
        ~/.macaron/workspaces/{project_id}/
            {session_short}/          ← git worktree
            ...
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or WORKSPACES_ROOT
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._workspaces: dict[str, WorkspaceInfo] = {}

    async def create(self, project_id: str, session_id: str,
                     branch: str, source_repo: str = "") -> WorkspaceInfo:
        """Create an isolated git worktree for an agent session."""
        session_short = _short_hash(session_id)[:8]
        project_dir = self.base_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = project_dir / session_short

        if worktree_path.exists():
            logger.warning("Worktree already exists: %s", worktree_path)
            if session_id in self._workspaces:
                return self._workspaces[session_id]

        if not source_repo:
            logger.error("No source_repo for project %s", project_id)
            raise ValueError(f"source_repo required for project {project_id}")

        branch_name = f"agent/{session_short}/{branch}"

        # Create worktree from source repo
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", source_repo, "worktree", "add",
            "-b", branch_name, str(worktree_path), "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode().strip()
            # If branch already exists, try without -b
            if "already exists" in err:
                proc2 = await asyncio.create_subprocess_exec(
                    "git", "-C", source_repo, "worktree", "add",
                    str(worktree_path), branch_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr2 = await proc2.communicate()
                if proc2.returncode != 0:
                    raise RuntimeError(f"git worktree add failed: {stderr2.decode()}")
            else:
                raise RuntimeError(f"git worktree add failed: {err}")

        info = WorkspaceInfo(
            session_id=session_id,
            project_id=project_id,
            branch=branch_name,
            path=str(worktree_path),
            workspace_type=WorkspaceType.WORKTREE,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.WORKING,
        )
        self._workspaces[session_id] = info
        logger.info("Created worktree: %s → %s", session_id[:8], worktree_path)
        return info

    async def cleanup(self, session_id: str) -> None:
        """Remove worktree after session ends."""
        info = self._workspaces.pop(session_id, None)
        if not info:
            logger.debug("No worktree found for session %s", session_id[:8])
            return

        worktree_path = Path(info.path)

        # Find source repo to run git worktree remove
        source_repo = await self._find_source_repo(info.project_id)
        if source_repo:
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", source_repo, "worktree", "remove",
                str(worktree_path), "--force",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        # Fallback: remove directory if still exists
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

        logger.info("Cleaned up worktree: %s", session_id[:8])

    async def get(self, session_id: str) -> Optional[WorkspaceInfo]:
        """Get workspace info for a session."""
        return self._workspaces.get(session_id)

    async def list_active(self) -> list[WorkspaceInfo]:
        """List all active workspaces."""
        return [w for w in self._workspaces.values()
                if w.status in (SessionStatus.WORKING, SessionStatus.IDLE)]

    async def cleanup_all(self) -> int:
        """Cleanup all workspaces. Returns count removed."""
        sessions = list(self._workspaces.keys())
        for sid in sessions:
            await self.cleanup(sid)
        return len(sessions)

    async def _find_source_repo(self, project_id: str) -> Optional[str]:
        """Find the source repo path for a project."""
        try:
            from ..projects.manager import ProjectManager
            pm = ProjectManager()
            project = pm.get_project(project_id)
            if project and project.path:
                return project.path
        except Exception:
            pass
        return None


# Singleton
_manager: Optional[WorktreeManager] = None


def get_workspace_manager() -> WorktreeManager:
    global _manager
    if _manager is None:
        _manager = WorktreeManager()
    return _manager
