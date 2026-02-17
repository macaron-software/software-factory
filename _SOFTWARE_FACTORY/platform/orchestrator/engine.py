"""
Orchestration Engine - Coordinates agents using patterns.
===========================================================
Central coordinator that selects patterns, assigns agents, and manages workflows.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from ..models import (
    OrchestrationPattern, Session, SessionStatus, A2AMessage, MessageType,
)
from ..agents.base import BaseAgent
from ..agents.runtime import AgentRuntime
from ..a2a.bus import MessageBus
from ..a2a.veto import VetoManager
from .patterns import (
    parallel, sequential, loop, router, aggregator,
    hierarchical, network, human_in_loop, PatternResult,
)

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    """
    Main orchestration engine. Takes a session goal, selects pattern,
    spawns agents, and coordinates execution.
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        bus: MessageBus,
        veto_manager: VetoManager = None,
        db_conn: Any = None,
    ):
        self.runtime = runtime
        self.bus = bus
        self.veto_manager = veto_manager or VetoManager()
        self.db = db_conn
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self,
        name: str,
        goal: str,
        pattern: OrchestrationPattern = OrchestrationPattern.HIERARCHICAL,
        agent_roles: list[str] = None,
        project_id: str = None,
        description: str = "",
    ) -> Session:
        """Create a new work session and spawn agents."""
        session = Session(
            name=name,
            description=description,
            pattern=pattern,
            goal=goal,
            project_id=project_id,
        )

        # Spawn agents for requested roles
        if agent_roles:
            for role_id in agent_roles:
                try:
                    agent = await self.runtime.spawn(role_id, session.id)
                    session.agents.append(agent.id)
                    self.bus.register_agent(agent.id, agent.receive)
                except ValueError as e:
                    logger.warning(f"Could not spawn {role_id}: {e}")

        session.status = SessionStatus.ACTIVE
        self._sessions[session.id] = session

        # Persist
        if self.db:
            self._persist_session(session)

        logger.info(f"Session {session.id[:8]} created: {name} ({pattern.value}, {len(session.agents)} agents)")
        return session

    async def run_session(self, session_id: str) -> PatternResult:
        """Execute a session using its configured pattern."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Unknown session: {session_id}")

        agents = [self.runtime.get(aid) for aid in session.agents]
        agents = [a for a in agents if a is not None]

        if not agents:
            return PatternResult(session.pattern.value, False, error="No agents available")

        # Dispatch to pattern
        pattern = session.pattern
        task = session.goal

        try:
            if pattern == OrchestrationPattern.PARALLEL:
                result = await parallel(agents, task, session_id)

            elif pattern == OrchestrationPattern.SEQUENTIAL:
                result = await sequential(agents, task, session_id)

            elif pattern == OrchestrationPattern.LOOP:
                result = await loop(agents, task, session_id)

            elif pattern == OrchestrationPattern.ROUTER:
                if len(agents) < 2:
                    return PatternResult("router", False, error="Need at least 2 agents")
                router_agent = agents[0]
                specialists = {a.role_id: a for a in agents[1:]}
                result = await router(router_agent, specialists, task, session_id)

            elif pattern == OrchestrationPattern.AGGREGATOR:
                if len(agents) < 2:
                    return PatternResult("aggregator", False, error="Need at least 2 agents")
                workers = agents[:-1]
                synthesizer = agents[-1]
                result = await aggregator(workers, synthesizer, task, session_id)

            elif pattern == OrchestrationPattern.HIERARCHICAL:
                if len(agents) < 2:
                    return PatternResult("hierarchical", False, error="Need at least 2 agents")
                manager = agents[0]
                workers = agents[1:]
                result = await hierarchical(manager, workers, task, session_id)

            elif pattern == OrchestrationPattern.NETWORK:
                result = await network(agents, task, session_id)

            elif pattern == OrchestrationPattern.HUMAN_IN_LOOP:
                result = await human_in_loop(agents[0], task, session_id)

            else:
                result = PatternResult(pattern.value, False, error=f"Unknown pattern: {pattern}")

            # Check for vetoes
            if self.veto_manager.has_blocking_veto(session_id):
                result.success = False
                result.error = "Blocked by veto"

            # Update session status
            session.status = SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
            if session.status == SessionStatus.COMPLETED:
                session.completed_at = datetime.utcnow()

            return result

        except Exception as e:
            session.status = SessionStatus.FAILED
            logger.error(f"Session {session_id[:8]} failed: {e}")
            return PatternResult(session.pattern.value, False, error=str(e))

    async def stop_session(self, session_id: str):
        """Stop a session and its agents."""
        session = self._sessions.get(session_id)
        if session:
            await self.runtime.stop_session_agents(session_id)
            session.status = SessionStatus.CANCELLED

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def list_sessions(self, status: SessionStatus = None) -> list[Session]:
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sessions

    def _persist_session(self, session: Session):
        """Save session to DB."""
        if not self.db:
            return
        try:
            self.db.execute(
                """INSERT OR REPLACE INTO sessions
                   (id, name, description, pattern, status, goal, context_json, project_id, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id, session.name, session.description,
                    session.pattern.value, session.status.value,
                    session.goal, json.dumps(session.context),
                    session.project_id,
                    session.created_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                ),
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist session: {e}")


# Singleton
_engine: OrchestrationEngine | None = None


def get_engine() -> OrchestrationEngine:
    global _engine
    if _engine is None:
        _engine = OrchestrationEngine()
    return _engine
