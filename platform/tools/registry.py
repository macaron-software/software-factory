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


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return the global tool registry singleton, loading custom tools from DB."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _load_custom_tools(_registry)
    return _registry


def _load_custom_tools(registry: ToolRegistry) -> None:
    """Load enabled custom tools from the database into the registry."""
    try:
        from ..db.migrations import get_db
        db = get_db()
        rows = db.execute("SELECT * FROM custom_tools WHERE enabled = 1").fetchall()
        for row in rows:
            _register_custom_tool(registry, dict(row))
    except Exception as e:
        logger.debug("Custom tools not loaded (DB may not be ready): %s", e)


def _register_custom_tool(registry: ToolRegistry, tool_data: dict) -> None:
    """Register a single custom tool from DB data into the registry."""
    import json as _json

    try:
        config = _json.loads(tool_data["config"]) if isinstance(tool_data["config"], str) else tool_data["config"]
    except Exception:
        config = {}

    tool_name = f"custom.{tool_data['name']}"
    tool_desc = tool_data.get("description", "")
    tool_type = tool_data["type"]
    _cfg = config
    _tt = tool_type

    class _CustomTool(BaseTool):
        name = tool_name
        description = tool_desc
        category = "custom"

        async def execute(self, params: dict, agent: AgentInstance = None) -> str:
            return _json.dumps({"type": _tt, "config": _cfg, "params": params})

    try:
        registry.register(_CustomTool())
    except Exception as e:
        logger.warning("Failed to register custom tool %s: %s", tool_name, e)
