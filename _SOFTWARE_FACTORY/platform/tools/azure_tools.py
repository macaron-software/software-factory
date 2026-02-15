"""
Azure Tools - Azure AI services integration.
==============================================
"""

from __future__ import annotations

import logging
from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


class AzureSearchTool(BaseTool):
    name = "azure_search"
    description = "Search using Azure AI Search"
    category = "azure"

    def __init__(self, bridge=None):
        self._bridge = bridge

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        query = params.get("query", "")
        if not query:
            return "Error: query required"
        if not self._bridge or not self._bridge.is_connected:
            return "Azure not connected"
        try:
            result = await self._bridge.query(
                prompt=query, model="gpt-5.1", max_tokens=2000,
            )
            return result
        except Exception as e:
            return f"Azure search error: {e}"


class AzureEmbedTool(BaseTool):
    name = "azure_embed"
    description = "Generate text embeddings via Azure"
    category = "azure"

    def __init__(self, bridge=None):
        self._bridge = bridge

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        text = params.get("text", "")
        if not text:
            return "Error: text required"
        if not self._bridge or not self._bridge.is_connected:
            return "Azure not connected"
        try:
            embedding = await self._bridge.embed(text)
            return f"Embedding generated ({len(embedding)} dimensions)"
        except Exception as e:
            return f"Embedding error: {e}"


def register_azure_tools(registry, bridge=None):
    """Register Azure tools."""
    registry.register(AzureSearchTool(bridge))
    registry.register(AzureEmbedTool(bridge))
