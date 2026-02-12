"""LLM Client — unified async interface for all providers.

All providers use OpenAI-compatible chat/completions API:
- MiniMax (api.minimaxi.chat)
- NVIDIA/Kimi (integrate.api.nvidia.com)
- Local GLM (mlx_lm.server)
- Azure OpenAI (castudioia*.openai.azure.com) — when VPN available

Streaming supported via SSE (text/event-stream).
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)

# Provider configs — OpenAI-compatible endpoints
_PROVIDERS = {
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.chat/v1",
        "key_env": "MINIMAX_API_KEY",
        "models": ["MiniMax-M2.1", "MiniMax-M2", "MiniMax-M1-80k"],
        "default": "MiniMax-M2.1",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
    "nvidia": {
        "name": "NVIDIA (Kimi)",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "models": ["moonshotai/kimi-k2-instruct", "moonshotai/kimi-k2.5-instruct"],
        "default": "moonshotai/kimi-k2-instruct",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
    "local": {
        "name": "Local (MLX)",
        "base_url": "http://127.0.0.1:8081/v1",
        "key_env": "",
        "models": ["mlx-community/GLM-4.7-Flash-4bit"],
        "default": "mlx-community/GLM-4.7-Flash-4bit",
        "auth_header": "",
        "auth_prefix": "",
    },
    "azure": {
        "name": "Azure OpenAI",
        "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
        "key_env": "AZURE_OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "default": "gpt-4o",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2024-10-21",
    },
}

# Fallback chain: try providers in order
_FALLBACK_CHAIN = ["minimax", "nvidia", "local"]


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str
    name: Optional[str] = None


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"


@dataclass
class LLMStreamChunk:
    delta: str
    done: bool = False
    model: str = ""
    finish_reason: str = ""


class LLMClient:
    """Async LLM client with multi-provider support and fallback."""

    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None
        self._stats = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "errors": 0}

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _get_provider_config(self, provider: str) -> dict:
        return _PROVIDERS.get(provider, _PROVIDERS["minimax"])

    def _get_api_key(self, pcfg: dict) -> str:
        env = pcfg.get("key_env", "")
        return os.environ.get(env, "") if env else "no-key"

    def _build_url(self, pcfg: dict, model: str) -> str:
        base = pcfg["base_url"].rstrip("/")
        if pcfg.get("azure_api_version") and base:
            # Azure uses deployment-based URLs
            return f"{base}/openai/deployments/{model}/chat/completions?api-version={pcfg['azure_api_version']}"
        return f"{base}/chat/completions"

    def _build_headers(self, pcfg: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        key = self._get_api_key(pcfg)
        if pcfg.get("auth_header") and key:
            headers[pcfg["auth_header"]] = f"{pcfg.get('auth_prefix', '')}{key}"
        return headers

    async def chat(
        self,
        messages: list[LLMMessage],
        provider: str = "minimax",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> LLMResponse:
        """Send a chat completion request. Falls back to next provider on failure."""
        providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

        for prov in providers_to_try:
            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not key or key == "no-key" and pcfg.get("key_env"):
                continue

            use_model = model if (prov == provider and model) else pcfg["default"]
            try:
                result = await self._do_chat(pcfg, prov, use_model, messages, temperature, max_tokens, system_prompt)
                self._stats["calls"] += 1
                self._stats["tokens_in"] += result.tokens_in
                self._stats["tokens_out"] += result.tokens_out
                return result
            except Exception as exc:
                logger.warning("LLM %s/%s failed: %s — trying next", prov, use_model, exc)
                self._stats["errors"] += 1
                continue

        raise RuntimeError(f"All LLM providers failed for {provider}/{model}")

    async def _do_chat(
        self, pcfg: dict, provider: str, model: str,
        messages: list[LLMMessage], temperature: float, max_tokens: int,
        system_prompt: str,
    ) -> LLMResponse:
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)

        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            d = {"role": m.role, "content": m.content}
            if m.name:
                d["name"] = m.name
            msgs.append(d)

        body = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        t0 = time.monotonic()
        resp = await http.post(url, json=body, headers=headers)
        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "")
        # Strip <think> blocks from MiniMax
        if "<think>" in content and "</think>" in content:
            idx = content.index("</think>") + len("</think>")
            content = content[idx:].strip()

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=provider,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            duration_ms=elapsed,
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        provider: str = "minimax",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream chat completion response."""
        pcfg = self._get_provider_config(provider)
        use_model = model or pcfg["default"]
        http = await self._get_http()
        url = self._build_url(pcfg, use_model)
        headers = self._build_headers(pcfg)

        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            d = {"role": m.role, "content": m.content}
            if m.name:
                d["name"] = m.name
            msgs.append(d)

        body = {
            "model": use_model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with http.stream("POST", url, json=body, headers=headers) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                raise RuntimeError(f"HTTP {resp.status_code}: {text[:200]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    yield LLMStreamChunk(delta="", done=True, model=use_model)
                    break
                try:
                    data = json.loads(payload)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    finish = data.get("choices", [{}])[0].get("finish_reason")
                    if content:
                        yield LLMStreamChunk(delta=content, model=use_model)
                    if finish:
                        yield LLMStreamChunk(delta="", done=True, model=use_model, finish_reason=finish)
                except json.JSONDecodeError:
                    continue

    def available_providers(self) -> list[dict]:
        """List providers with availability status."""
        result = []
        for pid, pcfg in _PROVIDERS.items():
            key = self._get_api_key(pcfg)
            has_key = bool(key and key != "no-key") or not pcfg.get("key_env")
            result.append({
                "id": pid,
                "name": pcfg["name"],
                "models": pcfg["models"],
                "default": pcfg["default"],
                "enabled": has_key,
                "has_key": has_key,
            })
        return result

    @property
    def stats(self) -> dict:
        return dict(self._stats)


# Singleton
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
