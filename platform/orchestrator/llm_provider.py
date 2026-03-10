"""Azure AI Foundry LLM provider.

Multi-model routing with fallback chain:
  Azure (GPT-4o / Claude Sonnet 4 / GPT-4.1) → local fallback
"""
from __future__ import annotations

import logging
import os
from typing import AsyncIterator

from ..config import get_config

logger = logging.getLogger(__name__)


class LLMProvider:
    """Unified LLM provider that routes to Azure AI Foundry models."""

    def __init__(self):
        self._cfg = get_config().azure
        self._client = None

    async def _get_client(self):
        """Lazy-init Azure AI Foundry client."""
        if self._client is not None:
            return self._client
        try:
            from azure.ai.projects.aio import AIProjectClient
            from azure.identity.aio import DefaultAzureCredential

            endpoint = self._cfg.project_endpoint or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
            if not endpoint:
                logger.warning("No Azure Foundry endpoint configured — LLM calls will fail")
                return None

            self._client = AIProjectClient(
                endpoint=endpoint,
                credential=DefaultAzureCredential(),
            )
            return self._client
        except ImportError:
            logger.warning("azure-ai-projects not installed — using stub mode")
            return None

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request. Returns the assistant content."""
        model = model or self._cfg.model_deployment or "gpt-5.1"
        client = await self._get_client()

        if client is None:
            return await self._fallback_chat(messages, model, temperature, max_tokens)

        try:
            response = await client.inference.get_chat_completions(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Azure LLM call failed (%s), trying fallback: %s", model, exc)
            return await self._fallback_chat(messages, model, temperature, max_tokens)

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion — yields content chunks."""
        model = model or self._cfg.model_deployment or "gpt-5.1"
        client = await self._get_client()

        if client is None:
            yield await self._fallback_chat(messages, model, temperature, max_tokens)
            return

        try:
            response = await client.inference.get_streaming_chat_completions(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.warning("Azure streaming failed: %s", exc)
            yield await self._fallback_chat(messages, model, temperature, max_tokens)

    async def embed(self, text: str, model: str = "text-embedding-3-large") -> list[float]:
        """Get embeddings for text."""
        client = await self._get_client()
        if client is None:
            return []
        try:
            response = await client.inference.get_embeddings(
                model=model,
                input=[text],
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("Embedding call failed: %s", exc)
            return []

    async def _fallback_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Fallback to local LLM (MiniMax or subprocess-based)."""
        try:
            import sys
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2]))
            from core.llm_client import LLMClient
            client = LLMClient()
            prompt = "\n".join(
                f"[{m.get('role', 'user')}]: {m.get('content', '')}" for m in messages
            )
            return await client.generate(prompt, max_tokens=max_tokens)
        except Exception as exc:
            logger.error("All LLM fallbacks failed: %s", exc)
            return f"[LLM Error] Could not generate response: {exc}"

    async def close(self):
        """Cleanup."""
        if self._client:
            await self._client.close()
            self._client = None


# Singleton
_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider
