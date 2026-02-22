"""
MCP LRM - Model Context Protocol for Software Factory
=====================================================
Provides project context access to LLM agents.
"""

from mcp_lrm.server import MCPLRMServer
from mcp_lrm.exclusions import should_exclude_path, filter_paths

__all__ = [
    "MCPLRMServer",
    "should_exclude_path",
    "filter_paths",
]
