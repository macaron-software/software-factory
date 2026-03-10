"""
A2A Protocol - Message format, routing rules, and priority handling.
=====================================================================
Defines the structured communication protocol between agents.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..models import (
    A2AMessage, MessageType, AgentRole, AgentCommunication,
)


# Message priority mapping
PRIORITY_MAP: dict[MessageType, int] = {
    MessageType.VETO: 10,
    MessageType.ESCALATE: 9,
    MessageType.HUMAN_REQUEST: 8,
    MessageType.DELEGATE: 7,
    MessageType.REQUEST: 6,
    MessageType.NEGOTIATE: 5,
    MessageType.RESPONSE: 4,
    MessageType.APPROVE: 4,
    MessageType.HUMAN_RESPONSE: 4,
    MessageType.INFORM: 3,
    MessageType.SYSTEM: 2,
}


class ProtocolValidator:
    """Validates A2A messages against communication rules."""

    def __init__(self, roles: dict[str, AgentRole] = None):
        self._roles = roles or {}

    def update_roles(self, roles: dict[str, AgentRole]):
        self._roles = roles

    def validate_message(
        self,
        message: A2AMessage,
        from_role_id: str,
        to_role_id: str = None,
    ) -> tuple[bool, str]:
        """
        Validate that a message is allowed by the protocol.
        Returns (is_valid, reason).
        """
        from_role = self._roles.get(from_role_id)
        if not from_role:
            return True, "ok"  # No role constraint

        # Check veto permission
        if message.message_type == MessageType.VETO:
            if not from_role.permissions.can_veto:
                return False, f"Role {from_role_id} cannot veto"

        # Check delegation permission
        if message.message_type == MessageType.DELEGATE:
            if not from_role.permissions.can_delegate:
                return False, f"Role {from_role_id} cannot delegate"

        # Check approval permission
        if message.message_type == MessageType.APPROVE:
            if not from_role.permissions.can_approve:
                return False, f"Role {from_role_id} cannot approve"

        # Check communication rules (who can talk to whom)
        if to_role_id and from_role.communication.can_contact:
            if to_role_id not in from_role.communication.can_contact:
                return False, f"Role {from_role_id} cannot contact {to_role_id}"

        return True, "ok"

    def auto_set_priority(self, message: A2AMessage) -> A2AMessage:
        """Set message priority based on type if not explicitly set."""
        if message.priority == 5:  # default
            message.priority = PRIORITY_MAP.get(message.message_type, 5)
        return message

    def is_expired(self, message: A2AMessage, ttl_sec: int = 3600) -> bool:
        """Check if a message has expired."""
        return datetime.utcnow() - message.timestamp > timedelta(seconds=ttl_sec)


# ── Message builders ──────────────────────────────────────────────────

def make_request(
    from_agent: str,
    to_agent: str,
    session_id: str,
    content: str,
    **kwargs,
) -> A2AMessage:
    """Build a REQUEST message."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=MessageType.REQUEST,
        content=content,
        requires_response=True,
        priority=PRIORITY_MAP[MessageType.REQUEST],
        **kwargs,
    )


def make_delegate(
    from_agent: str,
    to_agent: str,
    session_id: str,
    task: str,
    **kwargs,
) -> A2AMessage:
    """Build a DELEGATE message."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=MessageType.DELEGATE,
        content=task,
        requires_response=True,
        priority=PRIORITY_MAP[MessageType.DELEGATE],
        **kwargs,
    )


def make_veto(
    from_agent: str,
    session_id: str,
    reason: str,
    parent_id: str = None,
    **kwargs,
) -> A2AMessage:
    """Build a VETO message."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        message_type=MessageType.VETO,
        content=reason,
        parent_id=parent_id,
        priority=PRIORITY_MAP[MessageType.VETO],
        **kwargs,
    )


def make_approve(
    from_agent: str,
    session_id: str,
    parent_id: str = None,
    comment: str = "Approved",
    **kwargs,
) -> A2AMessage:
    """Build an APPROVE message."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        message_type=MessageType.APPROVE,
        content=comment,
        parent_id=parent_id,
        priority=PRIORITY_MAP[MessageType.APPROVE],
        **kwargs,
    )


def make_inform(
    from_agent: str,
    session_id: str,
    content: str,
    channel: str = None,
    **kwargs,
) -> A2AMessage:
    """Build an INFORM broadcast message."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        to_agent=None,
        message_type=MessageType.INFORM,
        content=content,
        metadata={"channel": channel} if channel else {},
        priority=PRIORITY_MAP[MessageType.INFORM],
        **kwargs,
    )


def make_human_request(
    from_agent: str,
    session_id: str,
    question: str,
    choices: list[str] = None,
    **kwargs,
) -> A2AMessage:
    """Build a HUMAN_REQUEST message (agent asks user for input)."""
    return A2AMessage(
        session_id=session_id,
        from_agent=from_agent,
        to_agent="user",
        message_type=MessageType.HUMAN_REQUEST,
        content=question,
        metadata={"choices": choices} if choices else {},
        requires_response=True,
        priority=PRIORITY_MAP[MessageType.HUMAN_REQUEST],
        **kwargs,
    )
