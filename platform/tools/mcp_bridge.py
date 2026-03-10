"""
MCP Bridge - Connect platform tools to the existing MCP LRM server.
=====================================================================
"""

from __future__ import annotations

import aiohttp
import logging
from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

MCP_URL = "http://localhost:9501"


class MCPTool(BaseTool):
    """Generic MCP tool that proxies to the LRM server."""

    def __init__(self, tool_name: str, description: str):
        self.name = f"mcp_{tool_name}"
        self.description = description
        self.category = "mcp"
        self._tool_name = tool_name

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{MCP_URL}/tool",
                    json={"name": self._tool_name, "arguments": params},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return str(data.get("result", data))
                    else:
                        return f"MCP error {resp.status}: {await resp.text()}"
        except aiohttp.ClientError:
            return f"MCP server not available at {MCP_URL}"
        except Exception as e:
            return f"MCP error: {e}"


def register_mcp_tools(registry):
    """Register MCP bridge tools."""
    tools = [
        ("locate", "Find files matching a pattern in the project"),
        ("summarize", "Summarize file or directory content"),
        ("conventions", "Get coding conventions for a domain"),
        ("build", "Run build/test/lint via MCP"),
    ]
    for name, desc in tools:
        registry.register(MCPTool(name, desc))


# ---------------------------------------------------------------------------
# Solaris Design System MCP
# ---------------------------------------------------------------------------

SOLARIS_MCP_URL = "http://localhost:9502"


class SolarisMCPTool(BaseTool):
    """MCP tool for Solaris Design System — queries Figma components, WCAG patterns, and validation."""

    def __init__(self, tool_name: str, description: str):
        self.name = f"solaris_{tool_name}"
        self.description = description
        self.category = "design_system"
        self._tool_name = tool_name

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{SOLARIS_MCP_URL}/tool",
                    json={"name": self._tool_name, "arguments": params},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return str(data.get("result", data))
                    else:
                        return f"Solaris MCP error {resp.status}: {await resp.text()}"
        except aiohttp.ClientError:
            return f"Solaris MCP server not available at {SOLARIS_MCP_URL}"
        except Exception as e:
            return f"Solaris MCP error: {e}"


def register_solaris_tools(registry):
    """Register Solaris Design System MCP tools."""
    tools = [
        ("component", "Get Figma component details: all variants, properties, and component sets"),
        ("variant", "Get specific variant with exact Figma styles (borderRadius, padding, dimensions, colors)"),
        ("wcag", "Get WCAG accessibility pattern for a component type (accordion, button, tabs, etc.)"),
        ("knowledge", "Query design system knowledge base: semantic HTML, WCAG patterns, best practices"),
        ("validation", "Get validation status for a component from the latest validation report"),
        ("grep", "Search in generated CSS, HTML, or SCSS files"),
        ("list_components", "List all available Figma components/families"),
        ("stats", "Get overall Solaris statistics: components count, validation rates"),
    ]
    for name, desc in tools:
        registry.register(SolarisMCPTool(name, desc))
