"""Tool schemas and role-based tool mapping for the agent executor.

WHY: tool_schemas.py grew to 3313L with 6 large schema functions + ROLE_TOOL_MAP.
Split into category sub-modules. This __init__.py re-exports all public symbols
so all existing imports (from .tool_schemas import ...) continue to work unchanged.

Sub-modules:
  _core.py     — core tools + phase + web schemas
  _mcp.py      — MCP bridge tool schemas
  _build.py    — build/CI/test tool schemas
  _platform.py — platform-introspection + org + project tool schemas
  _mapping.py  — ROLE_TOOL_MAP, _classify_agent_role, _filter_schemas
"""

from __future__ import annotations

from ._core import _core_schemas, _phase_schemas, _web_schemas
from ._mcp import _mcp_schemas
from ._build import _build_schemas
from ._platform import _platform_schemas
from ._mapping import (
    ROLE_TOOL_MAP,
    _classify_agent_role,
    _filter_schemas,
    _get_capability_grade,
    _get_tools_for_agent,
)

__all__ = [
    "_core_schemas",
    "_phase_schemas",
    "_web_schemas",
    "_mcp_schemas",
    "_build_schemas",
    "_platform_schemas",
    "_get_tool_schemas",
    "_filter_schemas",
    "_classify_agent_role",
    "_get_tools_for_agent",
    "_get_capability_grade",
    "ROLE_TOOL_MAP",
]

# Tool schemas cache — built once on first call
_TOOL_SCHEMAS: list[dict] | None = None


def _get_tool_schemas() -> list[dict]:
    """Build OpenAI-compatible tool definitions from the registry."""
    global _TOOL_SCHEMAS
    if _TOOL_SCHEMAS is not None:
        return _TOOL_SCHEMAS
    _TOOL_SCHEMAS = (
        _core_schemas()
        + _phase_schemas()
        + _web_schemas()
        + _mcp_schemas()
        + _build_schemas()
        + _platform_schemas()
    )
    return _TOOL_SCHEMAS
