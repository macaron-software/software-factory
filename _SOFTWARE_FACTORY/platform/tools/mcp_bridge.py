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

MCP_URL = "http://localhost:9500"


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
                    f"{MCP_URL}/call",
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
