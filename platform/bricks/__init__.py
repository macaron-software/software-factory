"""Tool Bricks — modular infrastructure integrations.

Each brick is a self-contained module that provides:
- Tool definitions (name, schema, execute function)
- Role mapping (which agent roles get this brick's tools)
- Configuration (enable/disable, credentials, endpoints)
- Health check (is the integration reachable?)

Bricks auto-register via the BrickRegistry on platform startup.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    """A single tool provided by a brick."""
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable  # async (args, ctx) -> str
    category: str = ""


@dataclass
class BrickDef:
    """A brick = modular infrastructure integration."""
    id: str
    name: str
    description: str
    version: str = "1.0"
    tools: list[ToolDef] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)  # agent roles that get these tools
    requires_env: list[str] = field(default_factory=list)  # env vars needed
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        """Brick is available if all required env vars are set."""
        if not self.enabled:
            return False
        return all(os.environ.get(var) for var in self.requires_env)

    def health_check(self) -> tuple[bool, str]:
        """Override in subclass for real health check. Default: check env vars."""
        if not self.enabled:
            return False, "disabled"
        missing = [v for v in self.requires_env if not os.environ.get(v)]
        if missing:
            return False, f"missing env: {', '.join(missing)}"
        return True, "ok"


class BrickRegistry:
    """Registry for all tool bricks. Singleton via get_brick_registry()."""

    def __init__(self):
        self._bricks: dict[str, BrickDef] = {}
        self._discovered = False

    def register(self, brick: BrickDef) -> None:
        """Register a brick and its tools."""
        self._bricks[brick.id] = brick
        logger.info("Brick registered: %s (%d tools)", brick.id, len(brick.tools))

    def get(self, brick_id: str) -> Optional[BrickDef]:
        return self._bricks.get(brick_id)

    def list_all(self) -> list[BrickDef]:
        return list(self._bricks.values())

    def list_available(self) -> list[BrickDef]:
        return [b for b in self._bricks.values() if b.available]

    def list_for_role(self, role: str) -> list[BrickDef]:
        """Get bricks whose tools should be added to agents with this role."""
        return [b for b in self._bricks.values() if b.available and role in b.roles]

    def get_tools_for_role(self, role: str) -> list[ToolDef]:
        """Get all tools from bricks matching a role."""
        tools = []
        for brick in self.list_for_role(role):
            tools.extend(brick.tools)
        return tools

    def health_check_all(self) -> dict[str, tuple[bool, str]]:
        """Run health check on all bricks."""
        return {b.id: b.health_check() for b in self._bricks.values()}

    def discover(self) -> None:
        """Auto-discover and register bricks from platform/bricks/ submodules."""
        if self._discovered:
            return
        self._discovered = True

        package_dir = os.path.dirname(__file__)
        for _importer, modname, _ispkg in pkgutil.iter_modules([package_dir]):
            if modname.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f".{modname}", package=__name__)
                if hasattr(mod, "register"):
                    mod.register(self)
                    logger.info("Brick module loaded: %s", modname)
            except Exception as e:
                logger.warning("Brick module %s failed to load: %s", modname, e)

    def to_dict(self) -> list[dict]:
        """Serialize all bricks for API/UI."""
        return [
            {
                "id": b.id,
                "name": b.name,
                "description": b.description,
                "version": b.version,
                "tools": [t.name for t in b.tools],
                "roles": b.roles,
                "enabled": b.enabled,
                "available": b.available,
                "health": b.health_check(),
            }
            for b in self._bricks.values()
        ]


_registry: Optional[BrickRegistry] = None


def get_brick_registry() -> BrickRegistry:
    """Get or create the singleton BrickRegistry."""
    global _registry
    if _registry is None:
        _registry = BrickRegistry()
        _registry.discover()
    return _registry
