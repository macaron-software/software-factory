"""
Azure A2A Bridge - Connect local agents to Azure AI Foundry Agent Service.
============================================================================
Maps internal A2AMessage format to Azure's Agent-to-Agent protocol.
Falls back to local-only mode if Azure is unavailable.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ..config import get_config
from ..models import A2AMessage, MessageType

logger = logging.getLogger(__name__)


class AzureBridge:
    """
    Bridge between local agent platform and Azure AI Foundry Agent Service.
    Handles A2A connections, authentication, and message translation.
    """

    def __init__(self):
        self._config = get_config().azure
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        """Initialize connection to Azure AI Foundry."""
        if not self._config.project_endpoint:
            logger.warning("No Azure endpoint configured, running in local-only mode")
            return False

        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential

            if self._config.use_entra_id:
                credential = DefaultAzureCredential()
            else:
                credential = None  # API key auth handled differently

            self._client = AIProjectClient(
                endpoint=self._config.project_endpoint,
                credential=credential,
            )
            self._connected = True
            logger.info("Connected to Azure AI Foundry")
            return True

        except ImportError:
            logger.warning("azure-ai-projects not installed, local-only mode")
            return False
        except Exception as e:
            logger.error(f"Azure connection failed: {e}")
            return False

    async def disconnect(self):
        """Close Azure connection."""
        self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── LLM Queries via Azure ─────────────────────────────────────────

    async def query(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system: str = None,
    ) -> str:
        """Query an LLM through Azure AI Foundry."""
        if not self._connected:
            raise ConnectionError("Not connected to Azure AI Foundry")

        model = model or self._config.model_deployment

        try:
            # Use the agents SDK for structured queries
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self._client.agents.create_and_run(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Azure LLM query failed: {e}")
            raise

    # ── A2A Cross-Agent Communication ─────────────────────────────────

    async def send_a2a(
        self,
        message: A2AMessage,
        target_connection: str = None,
    ) -> Optional[str]:
        """Send a message to a remote agent via Azure A2A."""
        if not self._connected:
            return None

        conn_name = target_connection or self._config.a2a_connection_name
        if not conn_name:
            return None

        try:
            result = await self._client.agents.call_tool(
                tool_name="a2a",
                params={
                    "message": message.content,
                    "message_type": message.message_type.value,
                    "from_agent": message.from_agent,
                    "metadata": message.metadata,
                },
                connection_name=conn_name,
            )
            return str(result)
        except Exception as e:
            logger.error(f"A2A send failed: {e}")
            return None

    # ── Embeddings ────────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings via Azure."""
        if not self._connected:
            raise ConnectionError("Not connected to Azure")

        try:
            response = await self._client.embeddings.create(
                model=self._config.embedding_deployment,
                input=[text],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "endpoint": self._config.project_endpoint[:30] + "..." if self._config.project_endpoint else "none",
            "model": self._config.model_deployment,
            "a2a_connection": self._config.a2a_connection_name or "none",
        }
