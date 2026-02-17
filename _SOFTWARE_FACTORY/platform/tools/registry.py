"""
Tool Registry - Discovery, registration, and permission management.
=====================================================================
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models import AgentInstance, ToolResult

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all tools available to agents."""

    name: str = ""
    description: str = ""
    category: str = "general"
    requires_approval: bool = False
    allowed_roles: list[str] = []  # empty = all

    @abstractmethod
    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        """Execute the tool and return string result."""
        ...

    def is_allowed(self, role_id: str) -> bool:
        if not self.allowed_roles:
            return True
        return role_id in self.allowed_roles


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self, category: str = None, role_id: str = None) -> list[BaseTool]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if role_id:
            tools = [t for t in tools if t.is_allowed(role_id)]
        return tools

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_schema(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "requires_approval": t.requires_approval,
            }
            for t in self._tools.values()
        ]
