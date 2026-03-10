"""
State Machine - FSM for workflow state management.
====================================================
Persisted states with validated transitions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    DECOMPOSING = "decomposing"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    NEGOTIATING = "negotiating"
    WAITING_HUMAN = "waiting_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid transitions: from_state → [to_states]
TRANSITIONS: dict[WorkflowState, list[WorkflowState]] = {
    WorkflowState.INIT: [WorkflowState.PLANNING],
    WorkflowState.PLANNING: [WorkflowState.DECOMPOSING, WorkflowState.EXECUTING, WorkflowState.CANCELLED],
    WorkflowState.DECOMPOSING: [WorkflowState.EXECUTING, WorkflowState.FAILED],
    WorkflowState.EXECUTING: [
        WorkflowState.REVIEWING, WorkflowState.NEGOTIATING,
        WorkflowState.WAITING_HUMAN, WorkflowState.FAILED,
    ],
    WorkflowState.REVIEWING: [
        WorkflowState.APPROVED, WorkflowState.REJECTED,
        WorkflowState.NEGOTIATING, WorkflowState.WAITING_HUMAN,
    ],
    WorkflowState.NEGOTIATING: [
        WorkflowState.EXECUTING, WorkflowState.REVIEWING,
        WorkflowState.WAITING_HUMAN, WorkflowState.FAILED,
    ],
    WorkflowState.WAITING_HUMAN: [
        WorkflowState.EXECUTING, WorkflowState.REVIEWING,
        WorkflowState.APPROVED, WorkflowState.REJECTED,
        WorkflowState.CANCELLED,
    ],
    WorkflowState.APPROVED: [WorkflowState.COMPLETED, WorkflowState.EXECUTING],
    WorkflowState.REJECTED: [WorkflowState.PLANNING, WorkflowState.CANCELLED],
    WorkflowState.COMPLETED: [],
    WorkflowState.FAILED: [WorkflowState.PLANNING],
    WorkflowState.CANCELLED: [],
}


class StateTransition:
    """Record of a state transition."""

    def __init__(self, from_state: WorkflowState, to_state: WorkflowState, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.timestamp = datetime.utcnow()


class WorkflowStateMachine:
    """
    Finite State Machine for workflow management.
    Validates transitions, runs hooks, and persists state.
    """

    def __init__(self, session_id: str, initial_state: WorkflowState = WorkflowState.INIT):
        self.session_id = session_id
        self.state = initial_state
        self.history: list[StateTransition] = []
        self._hooks_pre: dict[str, list[Callable]] = {}
        self._hooks_post: dict[str, list[Callable]] = {}
        self._timeouts: dict[WorkflowState, float] = {}
        self._entered_at = datetime.utcnow()

    def transition(self, to_state: WorkflowState, reason: str = "") -> bool:
        """
        Attempt a state transition.
        Returns True if successful, False if invalid.
        """
        if to_state not in TRANSITIONS.get(self.state, []):
            logger.warning(
                f"Invalid transition {self.state.value} → {to_state.value} "
                f"for session {self.session_id[:8]}"
            )
            return False

        # Run pre-transition hooks
        hook_key = f"{self.state.value}→{to_state.value}"
        for hook in self._hooks_pre.get(hook_key, []):
            try:
                hook(self.state, to_state)
            except Exception as e:
                logger.error(f"Pre-hook failed: {e}")
                return False

        # Transition
        transition = StateTransition(self.state, to_state, reason)
        self.history.append(transition)
        old_state = self.state
        self.state = to_state
        self._entered_at = datetime.utcnow()

        logger.info(f"Session {self.session_id[:8]}: {old_state.value} → {to_state.value} ({reason})")

        # Run post-transition hooks
        for hook in self._hooks_post.get(hook_key, []):
            try:
                hook(old_state, to_state)
            except Exception as e:
                logger.error(f"Post-hook failed: {e}")

        return True

    def can_transition(self, to_state: WorkflowState) -> bool:
        """Check if a transition is valid."""
        return to_state in TRANSITIONS.get(self.state, [])

    def available_transitions(self) -> list[WorkflowState]:
        """List valid next states."""
        return TRANSITIONS.get(self.state, [])

    def on_pre(self, from_state: str, to_state: str, hook: Callable):
        """Register a pre-transition hook."""
        key = f"{from_state}→{to_state}"
        self._hooks_pre.setdefault(key, []).append(hook)

    def on_post(self, from_state: str, to_state: str, hook: Callable):
        """Register a post-transition hook."""
        key = f"{from_state}→{to_state}"
        self._hooks_post.setdefault(key, []).append(hook)

    def set_timeout(self, state: WorkflowState, timeout_sec: float):
        """Set max duration for a state (auto-escalation on timeout)."""
        self._timeouts[state] = timeout_sec

    def is_timed_out(self) -> bool:
        """Check if current state has exceeded its timeout."""
        timeout = self._timeouts.get(self.state)
        if timeout is None:
            return False
        elapsed = (datetime.utcnow() - self._entered_at).total_seconds()
        return elapsed > timeout

    @property
    def is_terminal(self) -> bool:
        return self.state in (WorkflowState.COMPLETED, WorkflowState.CANCELLED)

    @property
    def duration_in_state_sec(self) -> float:
        return (datetime.utcnow() - self._entered_at).total_seconds()

    def get_history(self) -> list[dict]:
        return [
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "reason": t.reason,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self.history
        ]
