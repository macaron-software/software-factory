"""
A2A Veto System - Hierarchical veto with escalation.
======================================================
Extends the Team of Rivals pattern from core/adversarial.py.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from ..models import (
    A2AMessage, MessageType, AgentRole, VetoLevel,
)

logger = logging.getLogger(__name__)


class VetoRecord:
    """Record of a veto action."""

    def __init__(
        self,
        agent_id: str,
        role_id: str,
        reason: str,
        level: VetoLevel,
        message_id: str,
        session_id: str,
    ):
        self.agent_id = agent_id
        self.role_id = role_id
        self.reason = reason
        self.level = level
        self.message_id = message_id
        self.session_id = session_id
        self.timestamp = datetime.utcnow()
        self.overridden = False
        self.overridden_by: Optional[str] = None


class VetoManager:
    """
    Manages the veto system with hierarchical authority.

    Veto hierarchy:
    - ABSOLUTE: Cannot be overridden (security agent on vulnerabilities)
    - STRONG: Requires human escalation to override
    - ADVISORY: Can be overridden with justification by higher-authority agent
    """

    def __init__(self, cooldown_sec: int = 60):
        self.cooldown_sec = cooldown_sec
        self._vetoes: list[VetoRecord] = []
        self._last_veto_time: dict[str, float] = {}  # agent_id → timestamp

    async def submit_veto(
        self,
        agent_id: str,
        role: AgentRole,
        message_id: str,
        session_id: str,
        reason: str,
        bus: Any = None,
    ) -> tuple[bool, str]:
        """
        Submit a veto. Returns (accepted, explanation).
        """
        # Check permission
        if not role.permissions.can_veto:
            return False, f"Role {role.id} does not have veto permission"

        # Check cooldown
        last = self._last_veto_time.get(agent_id, 0)
        if time.time() - last < self.cooldown_sec:
            remaining = int(self.cooldown_sec - (time.time() - last))
            return False, f"Veto cooldown active ({remaining}s remaining)"

        record = VetoRecord(
            agent_id=agent_id,
            role_id=role.id,
            reason=reason,
            level=role.permissions.veto_level,
            message_id=message_id,
            session_id=session_id,
        )
        self._vetoes.append(record)
        self._last_veto_time[agent_id] = time.time()

        # Broadcast veto via bus
        if bus:
            veto_msg = A2AMessage(
                session_id=session_id,
                from_agent=agent_id,
                message_type=MessageType.VETO,
                content=f"[{role.permissions.veto_level.value.upper()} VETO] {reason}",
                parent_id=message_id,
                priority=10,
                metadata={
                    "veto_level": role.permissions.veto_level.value,
                    "role": role.id,
                },
            )
            await bus.publish(veto_msg)

        logger.info(f"Veto by {role.id}: {reason[:100]}")
        return True, "Veto accepted"

    def can_override(
        self,
        veto_record: VetoRecord,
        overrider_role: AgentRole,
    ) -> tuple[bool, str]:
        """Check if a veto can be overridden by another role."""
        if veto_record.level == VetoLevel.ABSOLUTE:
            return False, "ABSOLUTE vetoes cannot be overridden"

        if veto_record.level == VetoLevel.STRONG:
            return False, "STRONG vetoes require human escalation"

        # ADVISORY can be overridden by roles with higher authority
        if overrider_role.permissions.can_approve:
            return True, "Advisory veto can be overridden"

        return False, "Insufficient authority to override"

    async def override_veto(
        self,
        veto_index: int,
        overrider_id: str,
        overrider_role: AgentRole,
        justification: str,
        bus: Any = None,
    ) -> tuple[bool, str]:
        """Attempt to override a veto."""
        if veto_index >= len(self._vetoes):
            return False, "Invalid veto index"

        record = self._vetoes[veto_index]
        can, reason = self.can_override(record, overrider_role)

        if not can:
            return False, reason

        record.overridden = True
        record.overridden_by = overrider_id

        if bus:
            override_msg = A2AMessage(
                session_id=record.session_id,
                from_agent=overrider_id,
                message_type=MessageType.APPROVE,
                content=f"Veto override: {justification}",
                parent_id=record.message_id,
                priority=8,
                metadata={"veto_override": True, "original_veto_role": record.role_id},
            )
            await bus.publish(override_msg)

        logger.info(f"Veto by {record.role_id} overridden by {overrider_role.id}")
        return True, "Veto overridden"

    def get_active_vetoes(self, session_id: str) -> list[VetoRecord]:
        """Get non-overridden vetoes for a session."""
        return [
            v for v in self._vetoes
            if v.session_id == session_id and not v.overridden
        ]

    def has_blocking_veto(self, session_id: str) -> bool:
        """Check if there's any non-overridden veto blocking progress."""
        return any(
            not v.overridden
            for v in self._vetoes
            if v.session_id == session_id
        )

    def get_stats(self) -> dict:
        return {
            "total_vetoes": len(self._vetoes),
            "active_vetoes": sum(1 for v in self._vetoes if not v.overridden),
            "overridden": sum(1 for v in self._vetoes if v.overridden),
            "by_level": {
                "absolute": sum(1 for v in self._vetoes if v.level == VetoLevel.ABSOLUTE),
                "strong": sum(1 for v in self._vetoes if v.level == VetoLevel.STRONG),
                "advisory": sum(1 for v in self._vetoes if v.level == VetoLevel.ADVISORY),
            },
        }
