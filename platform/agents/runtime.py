"""
Agent Runtime - Lifecycle management for agent instances.
==========================================================
Manages spawning, running, and stopping of agent instances.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from ..models import AgentInstance, AgentRole, AgentStatus
from .base import BaseAgent
from .registry import AgentRegistry, get_registry

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Manages all running agent instances."""

    def __init__(
        self,
        registry: AgentRegistry = None,
        llm_provider: Any = None,
        bus: Any = None,
        memory_store: Any = None,
        tool_registry: Any = None,
    ):
        self.registry = registry or get_registry()
        self.llm = llm_provider
        self.bus = bus
        self.memory = memory_store
        self.tool_registry = tool_registry
        self._agents: dict[str, BaseAgent] = {}
        self._lock = asyncio.Lock()

    async def spawn(
        self,
        role_id: str,
        session_id: str = None,
    ) -> BaseAgent:
        """Spawn a new agent instance from a role definition."""
        role = self.registry.get(role_id)
        if not role:
            raise ValueError(f"Unknown role: {role_id}")

        instance = AgentInstance(
            role_id=role_id,
            session_id=session_id,
        )

        # Resolve tools for this role
        tools = {}
        if self.tool_registry:
            for tool_name in role.tools:
                tool = self.tool_registry.get(tool_name)
                if tool:
                    tools[tool_name] = tool

        agent = BaseAgent(
            role=role,
            instance=instance,
            llm_provider=self.llm,
            tools=tools,
            memory=self.memory,
            bus=self.bus,
        )

        async with self._lock:
            self._agents[agent.id] = agent

        await agent.start()
        logger.info(f"Spawned agent {role_id}:{agent.id[:8]}")
        return agent

    async def stop_agent(self, agent_id: str):
        """Stop and remove an agent."""
        async with self._lock:
            agent = self._agents.pop(agent_id, None)
        if agent:
            await agent.stop()
            logger.info(f"Stopped agent {agent.role_id}:{agent_id[:8]}")

    async def stop_session_agents(self, session_id: str):
        """Stop all agents for a session."""
        to_stop = [
            a for a in self._agents.values()
            if a.instance.session_id == session_id
        ]
        for agent in to_stop:
            await self.stop_agent(agent.id)

    async def stop_all(self):
        """Stop all running agents."""
        agent_ids = list(self._agents.keys())
        for aid in agent_ids:
            await self.stop_agent(aid)

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_by_role(self, role_id: str) -> list[BaseAgent]:
        """Get all agents with a given role."""
        return [a for a in self._agents.values() if a.role_id == role_id]

    def get_by_session(self, session_id: str) -> list[BaseAgent]:
        """Get all agents in a session."""
        return [
            a for a in self._agents.values()
            if a.instance.session_id == session_id
        ]

    def list_agents(self) -> list[BaseAgent]:
        """List all running agents."""
        return list(self._agents.values())

    @property
    def active_count(self) -> int:
        return sum(
            1 for a in self._agents.values()
            if a.status not in (AgentStatus.STOPPED, AgentStatus.ERROR)
        )

    @property
    def total_count(self) -> int:
        return len(self._agents)

    def get_stats(self) -> dict:
        """Get runtime statistics."""
        by_status = {}
        by_role = {}
        total_tokens = 0
        total_messages = 0

        for agent in self._agents.values():
            s = agent.status.value
            by_status[s] = by_status.get(s, 0) + 1
            r = agent.role_id
            by_role[r] = by_role.get(r, 0) + 1
            total_tokens += agent.instance.tokens_used
            total_messages += agent.instance.messages_sent + agent.instance.messages_received

        return {
            "total_agents": self.total_count,
            "active_agents": self.active_count,
            "by_status": by_status,
            "by_role": by_role,
            "total_tokens": total_tokens,
            "total_messages": total_messages,
        }

    async def start(self):
        """Start the runtime (called on app startup)."""
        logger.info("AgentRuntime started")

    async def stop(self):
        """Stop the runtime and all agents."""
        await self.stop_all()
        logger.info("AgentRuntime stopped")

    def stats(self) -> dict:
        """Alias for get_stats."""
        return self.get_stats()


# Singleton
_runtime: AgentRuntime | None = None


def get_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime
