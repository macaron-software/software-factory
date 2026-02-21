"""Agent Permission Enforcement — tool ACL + file path sandboxing + rate limits + audit.

Five enforcement layers:
  1. Tool ACL: agent can only call tools in its allowed_tools list
  2. Path sandbox: file tools restricted to project workspace + allowed_paths
  3. Rate limits: max tool calls and writes per agent per session
  4. Git path guard: git tools restricted to project_path
  5. Audit log: every denial is logged to SQLite for debugging

Usage in executor._execute_tool():
    denied = check_permission(ctx, tool_name, args)
    if denied:
        return denied  # "Permission denied: ..."
"""
from __future__ import annotations

import fnmatch
import logging
import os
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Tools that access the filesystem ──
_FILE_READ_TOOLS = {"code_read", "code_search", "list_files"}
_FILE_WRITE_TOOLS = {"code_write", "code_edit"}
_EXEC_TOOLS = {"build", "test", "lint", "docker_build", "deploy_azure",
               "playwright_test", "chaos_test", "tmc_load_test",
               "sast_scan", "dependency_audit", "secrets_scan"}
_GIT_WRITE_TOOLS = {"git_commit"}
_GIT_READ_TOOLS = {"git_status", "git_log", "git_diff"}
_ALL_WRITE_TOOLS = _FILE_WRITE_TOOLS | _GIT_WRITE_TOOLS

# Rate limit defaults
MAX_TOOL_CALLS_PER_SESSION = 200
MAX_WRITES_PER_SESSION = 80

# Default denied path patterns (always blocked regardless of config)
_ALWAYS_DENIED_BASENAMES = {".env", "id_rsa", "id_ed25519"}
_ALWAYS_DENIED_EXTENSIONS = {".pem"}
_ALWAYS_DENIED_DIR_SEGMENTS = {"secrets"}
_ALWAYS_DENIED_BASENAME_PATTERNS = [".env.*", "*secret*key*"]


def _is_path_denied(abs_path: str) -> Optional[str]:
    """Check if path matches always-denied rules. Returns matched rule or None."""
    basename = os.path.basename(abs_path)
    # Exact basename match
    if basename in _ALWAYS_DENIED_BASENAMES:
        return f"denied file: {basename}"
    # Extension match
    _, ext = os.path.splitext(basename)
    if ext in _ALWAYS_DENIED_EXTENSIONS:
        return f"denied extension: {ext}"
    # Directory segment match (e.g. /foo/secrets/bar)
    parts = abs_path.replace("\\", "/").split("/")
    for seg in parts:
        if seg in _ALWAYS_DENIED_DIR_SEGMENTS:
            return f"denied directory: {seg}/"
    # Basename glob patterns
    for pat in _ALWAYS_DENIED_BASENAME_PATTERNS:
        if fnmatch.fnmatch(basename, pat):
            return f"denied pattern: {pat}"
    return None


@dataclass
class PermissionDenial:
    agent_id: str
    tool_name: str
    reason: str
    path: str = ""
    timestamp: float = 0.0


class PermissionGuard:
    """Enforces tool ACL, path sandboxing, rate limits, and git path guard."""

    def __init__(self, db_path: str = ""):
        if not db_path:
            from ..config import DB_PATH
            db_path = str(DB_PATH).replace("platform.db", "permissions_audit.db")
        self._db_path = db_path
        # Rate limit counters: key = "{agent_id}:{session_id}"
        self._call_counts: dict[str, int] = defaultdict(int)
        self._write_counts: dict[str, int] = defaultdict(int)
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_denials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    session_id TEXT DEFAULT '',
                    tool_name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    path TEXT DEFAULT '',
                    args_preview TEXT DEFAULT '',
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_denials_agent
                ON permission_denials(agent_id)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Permission audit DB init failed: %s", e)

    def _log_denial(self, denial: PermissionDenial, session_id: str = "",
                    args_preview: str = ""):
        """Record denial to audit log."""
        logger.warning("PERMISSION DENIED: agent=%s tool=%s reason=%s path=%s",
                       denial.agent_id, denial.tool_name, denial.reason, denial.path)
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT INTO permission_denials
                   (agent_id, session_id, tool_name, reason, path, args_preview, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (denial.agent_id, session_id, denial.tool_name,
                 denial.reason, denial.path, args_preview[:500], time.time())
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def check_tool_acl(self, agent_id: str, tool_name: str,
                       allowed_tools: Optional[list[str]],
                       session_id: str = "") -> Optional[str]:
        """Check if agent is allowed to use this tool. Returns error string or None."""
        if allowed_tools is None:
            return None  # no restrictions
        if tool_name in allowed_tools:
            return None  # explicitly allowed

        denial = PermissionDenial(
            agent_id=agent_id,
            tool_name=tool_name,
            reason=f"Tool '{tool_name}' not in agent's allowed tools",
            timestamp=time.time(),
        )
        self._log_denial(denial, session_id=session_id)
        return f"Permission denied: tool '{tool_name}' is not available to this agent."

    def check_path_access(self, agent_id: str, tool_name: str,
                          path: str, project_path: str,
                          permissions: Optional[dict] = None,
                          session_id: str = "") -> Optional[str]:
        """Check if agent can access this path. Returns error string or None."""
        if not path:
            return None

        # Normalize path (resolve symlinks to prevent traversal)
        abs_path = os.path.realpath(path)
        abs_project = os.path.realpath(project_path) if project_path else ""

        # 1. Check always-denied patterns (secrets, keys, etc.)
        denied_rule = _is_path_denied(abs_path)
        if denied_rule:
            denial = PermissionDenial(
                agent_id=agent_id,
                tool_name=tool_name,
                reason=f"Path matches {denied_rule}",
                path=abs_path,
                timestamp=time.time(),
            )
            self._log_denial(denial, session_id=session_id)
            return f"Permission denied: access to '{os.path.basename(abs_path)}' is restricted."

        # 2. Check custom denied_paths from agent permissions
        if permissions:
            for pattern in (permissions.get("denied_paths") or []):
                if fnmatch.fnmatch(abs_path, pattern) or fnmatch.fnmatch(os.path.basename(abs_path), pattern):
                    denial = PermissionDenial(
                        agent_id=agent_id,
                        tool_name=tool_name,
                        reason=f"Path matches agent denied_paths: {pattern}",
                        path=abs_path,
                        timestamp=time.time(),
                    )
                    self._log_denial(denial, session_id=session_id)
                    return f"Permission denied: access to this path is restricted for this agent."

        # 3. Check path is within project workspace
        if abs_project:
            allowed_roots = [abs_project]
            # Add custom allowed_paths
            if permissions:
                for ap in (permissions.get("allowed_paths") or []):
                    allowed_roots.append(os.path.abspath(ap))

            in_allowed = any(
                abs_path == root or abs_path.startswith(root + os.sep)
                for root in allowed_roots
            )
            if not in_allowed:
                denial = PermissionDenial(
                    agent_id=agent_id,
                    tool_name=tool_name,
                    reason=f"Path outside workspace boundary",
                    path=abs_path,
                    timestamp=time.time(),
                )
                self._log_denial(denial, session_id=session_id)
                return f"Permission denied: path is outside the project workspace."

        return None

    def check_write_permission(self, agent_id: str, tool_name: str,
                               permissions: Optional[dict] = None,
                               session_id: str = "") -> Optional[str]:
        """Check if agent has write permission for write tools."""
        if permissions and permissions.get("can_write") is False:
            if tool_name in _FILE_WRITE_TOOLS | _GIT_WRITE_TOOLS:
                denial = PermissionDenial(
                    agent_id=agent_id,
                    tool_name=tool_name,
                    reason="Agent is read-only (can_write=false)",
                    timestamp=time.time(),
                )
                self._log_denial(denial, session_id=session_id)
                return "Permission denied: this agent has read-only access."
        return None

    def check_exec_permission(self, agent_id: str, tool_name: str,
                              permissions: Optional[dict] = None,
                              session_id: str = "") -> Optional[str]:
        """Check if agent can execute commands."""
        if permissions and permissions.get("can_execute") is False:
            if tool_name in _EXEC_TOOLS:
                denial = PermissionDenial(
                    agent_id=agent_id,
                    tool_name=tool_name,
                    reason="Agent cannot execute commands (can_execute=false)",
                    timestamp=time.time(),
                )
                self._log_denial(denial, session_id=session_id)
                return "Permission denied: this agent cannot execute commands."
        return None

    def check_rate_limit(self, agent_id: str, tool_name: str,
                         session_id: str = "") -> Optional[str]:
        """Check if agent has exceeded rate limits for this session."""
        key = f"{agent_id}:{session_id}" if session_id else agent_id

        # Increment call count
        self._call_counts[key] += 1
        if tool_name in _ALL_WRITE_TOOLS:
            self._write_counts[key] += 1

        if self._call_counts[key] > MAX_TOOL_CALLS_PER_SESSION:
            denial = PermissionDenial(
                agent_id=agent_id,
                tool_name=tool_name,
                reason=f"Rate limit: {self._call_counts[key]}/{MAX_TOOL_CALLS_PER_SESSION} tool calls exceeded",
                timestamp=time.time(),
            )
            self._log_denial(denial, session_id=session_id)
            return f"Rate limit exceeded: max {MAX_TOOL_CALLS_PER_SESSION} tool calls per session."

        if tool_name in _ALL_WRITE_TOOLS and self._write_counts[key] > MAX_WRITES_PER_SESSION:
            denial = PermissionDenial(
                agent_id=agent_id,
                tool_name=tool_name,
                reason=f"Write limit: {self._write_counts[key]}/{MAX_WRITES_PER_SESSION} writes exceeded",
                timestamp=time.time(),
            )
            self._log_denial(denial, session_id=session_id)
            return f"Rate limit exceeded: max {MAX_WRITES_PER_SESSION} write operations per session."

        return None

    def check_git_path_guard(self, agent_id: str, tool_name: str,
                             args: dict, project_path: str,
                             session_id: str = "") -> Optional[str]:
        """Restrict git tools to operate only within project_path."""
        if tool_name not in (_GIT_READ_TOOLS | _GIT_WRITE_TOOLS):
            return None
        if not project_path:
            return None

        cwd = args.get("cwd", "")
        if not cwd:
            return None

        abs_cwd = os.path.realpath(cwd)
        abs_project = os.path.realpath(project_path)
        if not (abs_cwd == abs_project or abs_cwd.startswith(abs_project + os.sep)):
            denial = PermissionDenial(
                agent_id=agent_id,
                tool_name=tool_name,
                reason=f"Git tool cwd outside project: {abs_cwd}",
                path=abs_cwd,
                timestamp=time.time(),
            )
            self._log_denial(denial, session_id=session_id)
            return f"Permission denied: git operations must be within the project workspace."

        # Also check path argument for git_diff
        if tool_name == "git_diff":
            diff_path = args.get("path", "")
            if diff_path and os.path.isabs(diff_path):
                if not os.path.realpath(diff_path).startswith(abs_project + os.sep):
                    denial = PermissionDenial(
                        agent_id=agent_id,
                        tool_name=tool_name,
                        reason=f"git_diff path outside project: {diff_path}",
                        path=diff_path,
                        timestamp=time.time(),
                    )
                    self._log_denial(denial, session_id=session_id)
                    return f"Permission denied: git diff path is outside the project workspace."

        return None

    def get_rate_stats(self, agent_id: str, session_id: str = "") -> dict:
        """Get current rate limit usage for an agent."""
        key = f"{agent_id}:{session_id}" if session_id else agent_id
        return {
            "tool_calls": self._call_counts.get(key, 0),
            "max_tool_calls": MAX_TOOL_CALLS_PER_SESSION,
            "writes": self._write_counts.get(key, 0),
            "max_writes": MAX_WRITES_PER_SESSION,
        }

    def check(self, agent_id: str, tool_name: str, args: dict,
              allowed_tools: Optional[list[str]] = None,
              project_path: str = "",
              permissions: Optional[dict] = None,
              session_id: str = "") -> Optional[str]:
        """Run all permission checks. Returns error string or None if allowed."""
        # 1. Tool ACL
        denied = self.check_tool_acl(agent_id, tool_name, allowed_tools, session_id)
        if denied:
            return denied

        # 2. Write permission
        denied = self.check_write_permission(agent_id, tool_name, permissions, session_id)
        if denied:
            return denied

        # 3. Execute permission
        denied = self.check_exec_permission(agent_id, tool_name, permissions, session_id)
        if denied:
            return denied

        # 4. Rate limits
        denied = self.check_rate_limit(agent_id, tool_name, session_id)
        if denied:
            return denied

        # 5. Path sandboxing (for file/code tools)
        if tool_name in _FILE_READ_TOOLS | _FILE_WRITE_TOOLS:
            path = args.get("path", "")
            denied = self.check_path_access(
                agent_id, tool_name, path, project_path, permissions, session_id
            )
            if denied:
                return denied

        # 6. Git path guard
        denied = self.check_git_path_guard(agent_id, tool_name, args, project_path, session_id)
        if denied:
            return denied

        return None

    # ── Audit queries ──

    def recent_denials(self, limit: int = 50, agent_id: str = "") -> list[dict]:
        """Get recent permission denials."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            if agent_id:
                rows = conn.execute(
                    "SELECT * FROM permission_denials WHERE agent_id=? ORDER BY created_at DESC LIMIT ?",
                    (agent_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM permission_denials ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def denial_stats(self) -> dict:
        """Get denial statistics."""
        try:
            conn = sqlite3.connect(self._db_path)
            total = conn.execute("SELECT COUNT(*) FROM permission_denials").fetchone()[0]
            by_tool = conn.execute(
                "SELECT tool_name, COUNT(*) as cnt FROM permission_denials GROUP BY tool_name ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            by_agent = conn.execute(
                "SELECT agent_id, COUNT(*) as cnt FROM permission_denials GROUP BY agent_id ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            by_reason = conn.execute(
                "SELECT reason, COUNT(*) as cnt FROM permission_denials GROUP BY reason ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            conn.close()
            return {
                "total_denials": total,
                "by_tool": [{"tool": r[0], "count": r[1]} for r in by_tool],
                "by_agent": [{"agent": r[0], "count": r[1]} for r in by_agent],
                "by_reason": [{"reason": r[0], "count": r[1]} for r in by_reason],
            }
        except Exception:
            return {"total_denials": 0, "by_tool": [], "by_agent": [], "by_reason": []}


# Singleton
_guard: Optional[PermissionGuard] = None

def get_permission_guard() -> PermissionGuard:
    global _guard
    if _guard is None:
        _guard = PermissionGuard()
    return _guard
