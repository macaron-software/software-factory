"""
A2A Negotiation - Multi-agent consensus and compromise protocol.
=================================================================
Supports proposal → counter-proposal → vote → accept/reject cycle.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from ..models import (
    A2AMessage, MessageType, NegotiationState,
)

logger = logging.getLogger(__name__)


class NegotiationManager:
    """Manages multi-agent negotiations with configurable consensus."""

    def __init__(
        self,
        bus: Any = None,
        max_rounds: int = 10,
        consensus_type: str = "majority",  # "majority" | "unanimous"
    ):
        self.bus = bus
        self.max_rounds = max_rounds
        self.consensus_type = consensus_type
        self._negotiations: dict[str, NegotiationState] = {}

    async def start_negotiation(
        self,
        session_id: str,
        topic: str,
        initiator: str,
        participants: list[str],
        initial_proposal: str,
    ) -> NegotiationState:
        """Start a new negotiation."""
        neg = NegotiationState(
            session_id=session_id,
            topic=topic,
            initiator=initiator,
            participants=participants,
            max_rounds=self.max_rounds,
        )

        # Record initial proposal
        proposal_msg = A2AMessage(
            session_id=session_id,
            from_agent=initiator,
            message_type=MessageType.NEGOTIATE,
            content=initial_proposal,
            metadata={"negotiation_id": neg.id, "round": 0, "action": "propose"},
        )
        neg.proposals.append(proposal_msg)
        self._negotiations[neg.id] = neg

        # Notify participants
        if self.bus:
            for participant in participants:
                notify = A2AMessage(
                    session_id=session_id,
                    from_agent="system",
                    to_agent=participant,
                    message_type=MessageType.SYSTEM,
                    content=f"Negotiation started on: {topic}\nProposal: {initial_proposal}",
                    metadata={"negotiation_id": neg.id},
                )
                await self.bus.publish(notify)

        logger.info(f"Negotiation {neg.id[:8]} started: {topic}")
        return neg

    async def submit_vote(
        self,
        negotiation_id: str,
        agent_id: str,
        vote: str,  # "accept" | "reject" | "counter"
        counter_proposal: str = None,
    ) -> Optional[str]:
        """
        Submit a vote. Returns negotiation status:
        "accepted", "rejected", "counter", "pending", or None if invalid.
        """
        neg = self._negotiations.get(negotiation_id)
        if not neg or neg.status != "open":
            return None

        if agent_id not in neg.participants:
            return None

        neg.votes[agent_id] = vote

        if vote == "counter" and counter_proposal:
            neg.round += 1
            counter_msg = A2AMessage(
                session_id=neg.session_id,
                from_agent=agent_id,
                message_type=MessageType.NEGOTIATE,
                content=counter_proposal,
                metadata={"negotiation_id": neg.id, "round": neg.round, "action": "counter"},
            )
            neg.proposals.append(counter_msg)

            # Reset votes for new round (keep counter-proposer's implicit accept)
            neg.votes = {agent_id: "accept"}

            # Notify others of counter-proposal
            if self.bus:
                for p in neg.participants:
                    if p != agent_id:
                        await self.bus.publish(A2AMessage(
                            session_id=neg.session_id,
                            from_agent=agent_id,
                            to_agent=p,
                            message_type=MessageType.NEGOTIATE,
                            content=f"Counter-proposal (round {neg.round}): {counter_proposal}",
                            metadata={"negotiation_id": neg.id, "round": neg.round},
                        ))
            return "counter"

        # Check if all votes are in
        result = self._check_consensus(neg)
        if result:
            neg.status = result
            return result

        # Check max rounds
        if neg.round >= neg.max_rounds:
            neg.status = "escalated"
            return "escalated"

        return "pending"

    def _check_consensus(self, neg: NegotiationState) -> Optional[str]:
        """Check if consensus has been reached."""
        total = len(neg.participants)
        voted = len(neg.votes)

        if voted < total:
            return None  # Not all votes in

        accepts = sum(1 for v in neg.votes.values() if v == "accept")
        rejects = sum(1 for v in neg.votes.values() if v == "reject")

        if self.consensus_type == "unanimous":
            if accepts == total:
                return "accepted"
            if rejects > 0:
                return "rejected"
        else:  # majority
            if accepts > total / 2:
                return "accepted"
            if rejects > total / 2:
                return "rejected"

        return None

    def get_negotiation(self, negotiation_id: str) -> Optional[NegotiationState]:
        return self._negotiations.get(negotiation_id)

    def get_session_negotiations(self, session_id: str) -> list[NegotiationState]:
        return [n for n in self._negotiations.values() if n.session_id == session_id]

    def get_active(self) -> list[NegotiationState]:
        return [n for n in self._negotiations.values() if n.status == "open"]
