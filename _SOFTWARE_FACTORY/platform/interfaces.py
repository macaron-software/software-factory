"""Plugin interface protocols for extensible architecture.

Inspired by agent-orchestrator's 8-slot plugin system.
All core abstractions are defined as Python Protocols for duck-typing extensibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional, Protocol, runtime_checkable


# ── Enums ──────────────────────────────────────────────────────────

class WorkspaceType(str, Enum):
    WORKTREE = "worktree"
    COPY = "copy"
    SHARED = "shared"


class SessionStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    PR_OPEN = "pr_open"
    MERGED = "merged"
    FAILED = "failed"


class ReactionEvent(str, Enum):
    CI_FAILED = "ci_failed"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED_AND_GREEN = "approved_and_green"
    DEPLOY_FAILED = "deploy_failed"
    DEPLOY_SUCCESS = "deploy_success"
    AGENT_STUCK = "agent_stuck"
    PHASE_TIMEOUT = "phase_timeout"
    TMA_INCIDENT = "tma_incident"


class ReactionAction(str, Enum):
    SEND_TO_AGENT = "send_to_agent"
    RETRY = "retry"
    NOTIFY = "notify"
    ESCALATE = "escalate"
    CREATE_TASK = "create_task"
    ROLLBACK = "rollback"


# ── Data classes ───────────────────────────────────────────────────

@dataclass
class WorkspaceInfo:
    """Metadata for an isolated agent workspace."""
    session_id: str
    project_id: str
    branch: str
    path: str
    workspace_type: WorkspaceType = WorkspaceType.WORKTREE
    created_at: str = ""
    status: SessionStatus = SessionStatus.IDLE


@dataclass
class ReactionRule:
    """A single event→action mapping."""
    event: ReactionEvent
    action: ReactionAction
    auto: bool = True
    retries: int = 2
    escalate_after_sec: int = 1800  # 30 min
    priority: str = "normal"  # urgent | action | warning | info
    config: dict = field(default_factory=dict)


@dataclass
class EventPayload:
    """Payload for a reaction event."""
    event: ReactionEvent
    project_id: str
    session_id: str = ""
    mission_id: str = ""
    phase_id: str = ""
    details: dict = field(default_factory=dict)
    timestamp: str = ""


# ── Protocols (duck-typing interfaces) ─────────────────────────────

@runtime_checkable
class WorkerProtocol(Protocol):
    """Interface for any execution worker (TDD, build, deploy, transform)."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute a task and return result dict with status, output, errors."""
        ...

    async def cancel(self) -> None:
        """Cancel current execution."""
        ...

    @property
    def status(self) -> str:
        """Current worker status: idle | running | failed."""
        ...


@runtime_checkable
class ToolProtocol(Protocol):
    """Interface for agent tools (code_read, code_write, git, deploy, etc.)."""

    name: str
    description: str
    category: str

    async def execute(self, params: dict, agent: Any = None) -> str:
        """Execute tool with params and return string result."""
        ...

    def is_allowed(self, role_id: str) -> bool:
        """Check if agent role is allowed to use this tool."""
        ...


@runtime_checkable
class WorkspaceProtocol(Protocol):
    """Interface for workspace management (worktree, copy, shared)."""

    async def create(self, project_id: str, session_id: str,
                     branch: str) -> WorkspaceInfo:
        """Create an isolated workspace for an agent session."""
        ...

    async def cleanup(self, session_id: str) -> None:
        """Remove workspace after session ends."""
        ...

    async def get(self, session_id: str) -> Optional[WorkspaceInfo]:
        """Get workspace info for a session."""
        ...

    async def list_active(self) -> list[WorkspaceInfo]:
        """List all active workspaces."""
        ...


@runtime_checkable
class RuntimeProtocol(Protocol):
    """Interface for agent runtime environments (process, docker, tmux)."""

    async def start(self, agent_id: str, workspace: WorkspaceInfo,
                    config: dict) -> str:
        """Start a runtime and return runtime_id."""
        ...

    async def stop(self, runtime_id: str) -> None:
        """Stop a runtime."""
        ...

    async def send(self, runtime_id: str, message: str) -> None:
        """Send input to a running agent."""
        ...

    async def is_alive(self, runtime_id: str) -> bool:
        """Check if runtime is still running."""
        ...


@runtime_checkable
class NotifierProtocol(Protocol):
    """Interface for notification channels (SSE, slack, desktop, webhook)."""

    async def notify(self, event: ReactionEvent, payload: dict,
                     priority: str = "info") -> None:
        """Send a notification."""
        ...


@runtime_checkable
class ReactionHandler(Protocol):
    """Interface for handling reaction events."""

    async def handle(self, payload: EventPayload, rule: ReactionRule) -> dict:
        """Handle an event according to its rule. Returns action result."""
        ...


@runtime_checkable
class AnalyzerProtocol(Protocol):
    """Interface for code/project analyzers (rust, typescript, playwright)."""

    supported_extensions: list[str]

    async def analyze(self, file_path: str, context: dict) -> dict:
        """Analyze a file and return findings dict."""
        ...

    async def suggest_fix(self, finding: dict) -> Optional[str]:
        """Suggest a fix for a finding. Returns patch or None."""
        ...
