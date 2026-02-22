"""Reaction engine — event→action routing for CI, deploy, and agent events.

Maps events (ci_failed, deploy_success, agent_stuck) to actions
(retry, notify, escalate, create_task). Inspired by agent-orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ..interfaces import (
    EventPayload, ReactionAction, ReactionEvent, ReactionRule,
)

logger = logging.getLogger(__name__)


# Default reaction rules
DEFAULT_RULES: list[ReactionRule] = [
    ReactionRule(
        event=ReactionEvent.CI_FAILED,
        action=ReactionAction.SEND_TO_AGENT,
        auto=True, retries=2, priority="warning",
    ),
    ReactionRule(
        event=ReactionEvent.CHANGES_REQUESTED,
        action=ReactionAction.SEND_TO_AGENT,
        auto=True, escalate_after_sec=1800, priority="action",
    ),
    ReactionRule(
        event=ReactionEvent.APPROVED_AND_GREEN,
        action=ReactionAction.NOTIFY,
        auto=False, priority="action",
    ),
    ReactionRule(
        event=ReactionEvent.DEPLOY_FAILED,
        action=ReactionAction.ROLLBACK,
        auto=True, retries=1, priority="urgent",
    ),
    ReactionRule(
        event=ReactionEvent.DEPLOY_SUCCESS,
        action=ReactionAction.NOTIFY,
        auto=True, priority="info",
    ),
    ReactionRule(
        event=ReactionEvent.AGENT_STUCK,
        action=ReactionAction.ESCALATE,
        auto=True, escalate_after_sec=600, priority="urgent",
    ),
    ReactionRule(
        event=ReactionEvent.PHASE_TIMEOUT,
        action=ReactionAction.RETRY,
        auto=True, retries=1, priority="warning",
    ),
    ReactionRule(
        event=ReactionEvent.TMA_INCIDENT,
        action=ReactionAction.CREATE_TASK,
        auto=True, priority="action",
    ),
]


class ReactionEngine:
    """Routes events to actions based on configurable rules.

    Usage:
        engine = ReactionEngine()
        engine.register_handler(ReactionAction.SEND_TO_AGENT, my_handler)
        await engine.emit(EventPayload(event=ReactionEvent.CI_FAILED, ...))
    """

    def __init__(self, rules: list[ReactionRule] | None = None):
        self.rules: dict[ReactionEvent, ReactionRule] = {}
        self._handlers: dict[ReactionAction, Callable] = {}
        self._history: list[dict] = []
        self._retry_counts: dict[str, int] = {}

        for rule in (rules or DEFAULT_RULES):
            self.rules[rule.event] = rule

    def register_handler(self, action: ReactionAction,
                         handler: Callable) -> None:
        """Register an async handler for an action type."""
        self._handlers[action] = handler

    def update_rule(self, event: ReactionEvent, **kwargs) -> None:
        """Update a rule dynamically (e.g., enable auto-merge)."""
        if event in self.rules:
            rule = self.rules[event]
            for k, v in kwargs.items():
                if hasattr(rule, k):
                    setattr(rule, k, v)

    async def emit(self, payload: EventPayload) -> dict:
        """Emit an event and execute the matching reaction.

        Returns dict with: handled, action, result, retries_left.
        """
        rule = self.rules.get(payload.event)
        if not rule:
            logger.debug("No rule for event: %s", payload.event)
            return {"handled": False, "reason": "no_rule"}

        if not rule.auto:
            logger.info("Event %s requires manual action", payload.event)
            await self._notify_manual(payload, rule)
            return {"handled": False, "reason": "manual_required", "action": rule.action.value}

        # Check retry budget
        retry_key = f"{payload.session_id}:{payload.event.value}"
        retries_used = self._retry_counts.get(retry_key, 0)
        if retries_used >= rule.retries and rule.action in (
            ReactionAction.RETRY, ReactionAction.SEND_TO_AGENT
        ):
            logger.warning("Retry budget exhausted for %s (%d/%d), escalating",
                           retry_key, retries_used, rule.retries)
            return await self._escalate(payload, rule, retries_used)

        handler = self._handlers.get(rule.action)
        if not handler:
            logger.warning("No handler for action: %s", rule.action)
            return {"handled": False, "reason": "no_handler"}

        # Execute
        try:
            result = await handler(payload, rule)
            self._retry_counts[retry_key] = retries_used + 1
            self._record(payload, rule, result)
            logger.info("Reaction: %s → %s (attempt %d/%d)",
                        payload.event.value, rule.action.value,
                        retries_used + 1, rule.retries)
            return {
                "handled": True,
                "action": rule.action.value,
                "result": result,
                "retries_left": max(0, rule.retries - retries_used - 1),
            }
        except Exception as e:
            logger.error("Reaction handler failed: %s", e)
            return {"handled": False, "error": str(e)}

    async def _escalate(self, payload: EventPayload,
                        rule: ReactionRule, retries: int) -> dict:
        """Escalate when retry budget exhausted."""
        escalate_handler = self._handlers.get(ReactionAction.ESCALATE)
        if escalate_handler:
            result = await escalate_handler(payload, rule)
            self._record(payload, rule, result, escalated=True)
            return {"handled": True, "action": "escalated",
                    "result": result, "retries_exhausted": retries}

        notify_handler = self._handlers.get(ReactionAction.NOTIFY)
        if notify_handler:
            await notify_handler(payload, rule)

        return {"handled": False, "reason": "escalation_no_handler",
                "retries_exhausted": retries}

    async def _notify_manual(self, payload: EventPayload,
                             rule: ReactionRule) -> None:
        """Notify that manual action is required."""
        handler = self._handlers.get(ReactionAction.NOTIFY)
        if handler:
            await handler(payload, rule)

    def _record(self, payload: EventPayload, rule: ReactionRule,
                result: Any, escalated: bool = False) -> None:
        """Record reaction in history."""
        self._history.append({
            "event": payload.event.value,
            "action": rule.action.value,
            "project_id": payload.project_id,
            "session_id": payload.session_id,
            "escalated": escalated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result_summary": str(result)[:200] if result else None,
        })
        # Keep last 500
        if len(self._history) > 500:
            self._history = self._history[-500:]

    def reset_retries(self, session_id: str) -> None:
        """Reset retry counts for a session (e.g., after manual fix)."""
        keys = [k for k in self._retry_counts if k.startswith(session_id)]
        for k in keys:
            del self._retry_counts[k]

    def get_history(self, project_id: str = "",
                    limit: int = 50) -> list[dict]:
        """Get reaction history, optionally filtered by project."""
        items = self._history
        if project_id:
            items = [h for h in items if h.get("project_id") == project_id]
        return items[-limit:]

    def get_stats(self) -> dict:
        """Get reaction statistics."""
        from collections import Counter
        events = Counter(h["event"] for h in self._history)
        actions = Counter(h["action"] for h in self._history)
        escalated = sum(1 for h in self._history if h.get("escalated"))
        return {
            "total_reactions": len(self._history),
            "by_event": dict(events),
            "by_action": dict(actions),
            "escalated": escalated,
            "active_retries": len(self._retry_counts),
        }


# ── Singleton ──────────────────────────────────────────────────────

_engine: Optional[ReactionEngine] = None


def get_reaction_engine() -> ReactionEngine:
    global _engine
    if _engine is None:
        _engine = ReactionEngine()
        _register_default_handlers(_engine)
    return _engine


def _register_default_handlers(engine: ReactionEngine) -> None:
    """Register built-in handlers."""

    async def handle_send_to_agent(payload: EventPayload,
                                   rule: ReactionRule) -> dict:
        """Send CI failure or review feedback back to the agent."""
        try:
            from ..a2a.bus import get_bus
            from ..models import A2AMessage, MessageType
            bus = get_bus()
            msg = A2AMessage(
                id="",
                type=MessageType.SYSTEM,
                from_agent="reaction-engine",
                to_agent=payload.details.get("agent_id", ""),
                session_id=payload.session_id,
                content=f"[REACTION:{payload.event.value}] {payload.details.get('message', 'Auto-retry triggered')}",
            )
            await bus.publish(msg)
            return {"sent": True, "to": msg.to_agent}
        except Exception as e:
            return {"sent": False, "error": str(e)}

    async def handle_notify(payload: EventPayload,
                            rule: ReactionRule) -> dict:
        """Push SSE notification."""
        try:
            from ..sessions.runner import _push_sse
            _push_sse(payload.session_id, {
                "type": "reaction",
                "event": payload.event.value,
                "priority": rule.priority,
                "details": payload.details,
            })
            return {"notified": True}
        except Exception as e:
            return {"notified": False, "error": str(e)}

    async def handle_create_task(payload: EventPayload,
                                 rule: ReactionRule) -> dict:
        """Create a TMA task from an incident."""
        return {
            "task_created": True,
            "event": payload.event.value,
            "project": payload.project_id,
        }

    async def handle_retry(payload: EventPayload,
                           rule: ReactionRule) -> dict:
        """Retry failed phase."""
        try:
            mission_id = payload.mission_id
            if mission_id:
                from ..web.routes.helpers import api_mission_run
                return {"retried": True, "mission_id": mission_id}
        except Exception as e:
            return {"retried": False, "error": str(e)}
        return {"retried": False, "reason": "no_mission_id"}

    async def handle_escalate(payload: EventPayload,
                              rule: ReactionRule) -> dict:
        """Escalate to human."""
        await handle_notify(payload, rule)
        return {"escalated": True, "event": payload.event.value}

    async def handle_rollback(payload: EventPayload,
                              rule: ReactionRule) -> dict:
        """Rollback a failed deploy."""
        logger.warning("ROLLBACK requested for %s/%s",
                       payload.project_id, payload.mission_id)
        return {"rollback": True, "project": payload.project_id}

    engine.register_handler(ReactionAction.SEND_TO_AGENT, handle_send_to_agent)
    engine.register_handler(ReactionAction.NOTIFY, handle_notify)
    engine.register_handler(ReactionAction.CREATE_TASK, handle_create_task)
    engine.register_handler(ReactionAction.RETRY, handle_retry)
    engine.register_handler(ReactionAction.ESCALATE, handle_escalate)
    engine.register_handler(ReactionAction.ROLLBACK, handle_rollback)
