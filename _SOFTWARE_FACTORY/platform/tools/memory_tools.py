"""Memory Tools — search and store in project memory."""
from __future__ import annotations

from ..models import AgentInstance
from .registry import BaseTool


class MemorySearchTool(BaseTool):
    name = "memory_search"
    description = "Search project memory for stored knowledge"
    category = "memory"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        # Actual execution is handled directly in executor (needs ctx)
        return "Error: memory_search must be called via executor"


class MemoryStoreTool(BaseTool):
    name = "memory_store"
    description = "Store a fact in project memory"
    category = "memory"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: memory_store must be called via executor"


def register_memory_tools(registry):
    registry.register(MemorySearchTool())
    registry.register(MemoryStoreTool())
