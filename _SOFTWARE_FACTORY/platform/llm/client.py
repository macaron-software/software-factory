"""LLM Client — unified async interface for all providers.

All providers use OpenAI-compatible chat/completions API:
- Azure AI Foundry GPT-5.2 (swedencentral) — leaders, control, architecture
- NVIDIA/Kimi K2 (integrate.api.nvidia.com) — fast production workers
- MiniMax M2.5 (api.minimaxi.chat) — fallback, thinking model
- Claude CLI / Copilot CLI — offline headless (slow, 10-12s)

Streaming supported via SSE (text/event-stream).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)

# Provider configs — OpenAI-compatible endpoints
_PROVIDERS = {
    "azure-ai": {
        "name": "Azure AI Foundry (GPT-5.2)",
        "base_url": os.environ.get("AZURE_AI_ENDPOINT", "https://swedencentral.api.cognitive.microsoft.com").rstrip("/"),
        "key_env": "AZURE_AI_API_KEY",
        "models": ["gpt-5.2"],
        "default": "gpt-5.2",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2024-10-21",
        "azure_deployment_map": {"gpt-5.2": "gpt-52"},
        "max_tokens_param": {"gpt-5.2": "max_completion_tokens"},
    },
    "azure-openai": {
        "name": "Azure OpenAI (GPT-5-mini)",
        "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT", "https://ascii-ui-openai.openai.azure.com").rstrip("/"),
        "key_env": "AZURE_OPENAI_API_KEY",
        "models": ["gpt-5-mini"],
        "default": "gpt-5-mini",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2025-01-01-preview",
        "azure_deployment_map": {"gpt-5-mini": "gpt-5-mini"},
        "max_tokens_param": {"gpt-5-mini": "max_completion_tokens"},
    },
    "nvidia": {
        "name": "NVIDIA (Kimi K2)",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "models": ["moonshotai/kimi-k2-instruct"],
        "default": "moonshotai/kimi-k2-instruct",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.chat/v1",
        "key_env": "MINIMAX_API_KEY",
        "models": ["MiniMax-M2.5", "MiniMax-M2.1"],
        "default": "MiniMax-M2.5",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
}

# Fallback order driven by PLATFORM_LLM_PROVIDER (local=minimax first, azure=azure-openai first)
_primary = os.environ.get("PLATFORM_LLM_PROVIDER", "minimax")
_FALLBACK_CHAIN = [_primary] + [p for p in ["minimax", "azure-openai", "azure-ai"] if p != _primary]


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None  # for role=tool responses
    tool_calls: Optional[list[dict]] = None  # for assistant tool_calls


@dataclass
class LLMToolCall:
    id: str
    function_name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"
    tool_calls: list[LLMToolCall] = field(default_factory=list)


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
        # Cooldown: provider → timestamp when it becomes available again
        self._provider_cooldown: dict[str, float] = {}
        # Context for observability tracing (set by caller before chat())
        self._trace_context: dict = {}  # agent_id, session_id, mission_id

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=300.0)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _get_provider_config(self, provider: str) -> dict:
        return _PROVIDERS.get(provider, _PROVIDERS.get("minimax", {}))

    def _get_api_key(self, pcfg: dict) -> str:
        env = pcfg.get("key_env", "")
        if not env:
            return "no-key"
        key = os.environ.get(env, "")
        if key:
            return key
        # Fallback: read from ~/.config/factory/<name>.key
        key_file = pcfg.get("key_file") or ""
        if not key_file:
            # Derive from env var name: NVIDIA_API_KEY → nvidia.key
            name = env.replace("_API_KEY", "").replace("_", "-").lower()
            key_file = os.path.expanduser(f"~/.config/factory/{name}.key")
        try:
            return Path(key_file).read_text().strip()
        except (OSError, FileNotFoundError):
            return ""

    def _build_url(self, pcfg: dict, model: str) -> str:
        base = pcfg["base_url"].rstrip("/")
        if pcfg.get("azure_api_version") and base:
            # Azure uses deployment-based URLs; map model name → deployment name
            dep_map = pcfg.get("azure_deployment_map", {})
            deployment = dep_map.get(model, model)
            return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={pcfg['azure_api_version']}"
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
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Send a chat completion request. Falls back to next provider on failure."""
        providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

        for prov in providers_to_try:
            # Skip unknown providers
            if prov not in _PROVIDERS:
                logger.warning("LLM %s skipped (unknown provider)", prov)
                continue

            # Skip providers in cooldown (rate-limited recently)
            now = time.monotonic()
            cooldown_until = self._provider_cooldown.get(prov, 0)
            if cooldown_until > now:
                remaining = int(cooldown_until - now)
                logger.warning("LLM %s in cooldown (%ds left), skipping → fallback", prov, remaining)
                continue

            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not key or key == "no-key":
                logger.warning("LLM %s skipped (no API key)", prov)
                continue

            use_model = model if (prov == provider and model and model in pcfg.get("models", [])) else pcfg["default"]
            logger.warning("LLM trying %s/%s ...", prov, use_model)
            last_exc = None
            for attempt in range(3):
                try:
                    result = await self._do_chat(pcfg, prov, use_model, messages, temperature, max_tokens, system_prompt, tools)
                    self._stats["calls"] += 1
                    self._stats["tokens_in"] += result.tokens_in
                    self._stats["tokens_out"] += result.tokens_out
                    logger.warning("LLM %s/%s OK (%d in, %d out tokens)", prov, use_model, result.tokens_in, result.tokens_out)
                    # Trace for observability
                    self._trace(result, messages)
                    return result
                except Exception as exc:
                    last_exc = exc
                    err_str = repr(exc)
                    # Retry on transient network errors
                    if attempt < 2 and ("ReadError" in err_str or "ConnectError" in err_str or "RemoteProtocolError" in err_str):
                        logger.warning("LLM %s/%s transient error (attempt %d): %s — retrying in 3s", prov, use_model, attempt+1, err_str)
                        await asyncio.sleep(3)
                        continue
                    logger.warning("LLM %s/%s failed: %s — trying next", prov, use_model, err_str)
                    self._stats["errors"] += 1
                    # On 429, put provider in cooldown for 90s
                    if "429" in err_str or "RateLimitReached" in err_str:
                        self._provider_cooldown[prov] = time.monotonic() + 90
                    logger.warning("LLM %s → cooldown 90s (rate limited)", prov)
                continue

        raise RuntimeError(f"All LLM providers failed for {provider}/{model}")

    async def _do_chat(
        self, pcfg: dict, provider: str, model: str,
        messages: list[LLMMessage], temperature: float, max_tokens: int,
        system_prompt: str, tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)

        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            # Accept both LLMMessage objects and plain dicts
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                tool_call_id = m.get("tool_call_id")
                tool_calls = m.get("tool_calls")
            else:
                role = m.role
                content = m.content or ""
                name = m.name
                tool_call_id = m.tool_call_id
                tool_calls = m.tool_calls
            d = {"role": role, "content": content}
            # MiniMax rejects system messages after position 0
            if d["role"] == "system" and provider == "minimax" and msgs:
                d["role"] = "user"
                d["content"] = f"[System instruction]: {d['content']}"
            if name:
                d["name"] = name
            if tool_call_id:
                d["tool_call_id"] = tool_call_id
            if tool_calls:
                d["tool_calls"] = tool_calls
                d.pop("content", None)  # assistant tool_call msgs may have no content
            msgs.append(d)

        body = {
            "model": model,
            "messages": msgs,
        }
        # GPT-5-mini only supports temperature=1 (default)
        if not (model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex")):
            body["temperature"] = temperature
        # MiniMax uses <think> blocks that consume tokens — boost limit
        # GPT-5-mini is a reasoning model — needs extra tokens for internal reasoning
        effective_max = max_tokens
        if provider == "minimax":
            effective_max = max(max_tokens, 16000)
        elif model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex"):
            effective_max = max(max_tokens, 8000)
        # Some models (gpt-5.2) use max_completion_tokens instead of max_tokens
        mt_param = pcfg.get("max_tokens_param", {}).get(model, "max_tokens")
        body[mt_param] = effective_max

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        t0 = time.monotonic()

        # Retry loop for 429 rate limits (2 attempts, then fallback to next provider)
        for attempt in range(2):
            resp = await http.post(url, json=body, headers=headers)
            if resp.status_code != 429:
                break
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt * 5))
            retry_after = min(retry_after, 30)
            logger.warning("LLM %s/%s rate-limited (429), retry in %ds (attempt %d/2)",
                           provider, model, retry_after, attempt + 1)
            await asyncio.sleep(retry_after)

        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "") or ""
        # Strip <think> blocks from MiniMax
        if "<think>" in content and "</think>" in content:
            idx = content.index("</think>") + len("</think>")
            after_think = content[idx:].strip()
            if after_think:
                content = after_think
            else:
                # finish_reason=length: think block consumed all tokens
                # Extract useful reasoning from think block as fallback
                think_start = content.index("<think>") + len("<think>")
                think_end = content.index("</think>")
                content = content[think_start:think_end].strip()
        elif "<think>" in content and "</think>" not in content:
            # Incomplete think block (truncated by max_tokens)
            think_start = content.index("<think>") + len("<think>")
            content = content[think_start:].strip()

        # Parse tool calls from response
        parsed_tool_calls = []
        raw_tool_calls = msg.get("tool_calls") or []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            parsed_tool_calls.append(LLMToolCall(
                id=tc.get("id", ""),
                function_name=fn.get("name", ""),
                arguments=args,
            ))

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=provider,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            duration_ms=elapsed,
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=parsed_tool_calls,
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
        """Stream chat completion response with provider fallback."""
        providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

        for prov in providers_to_try:
            if prov not in _PROVIDERS:
                continue
            now = time.monotonic()
            cooldown_until = self._provider_cooldown.get(prov, 0)
            if cooldown_until > now:
                continue
            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not key or key == "no-key":
                continue
            use_model = model if (prov == provider and model and model in pcfg.get("models", [])) else pcfg["default"]
            try:
                async for chunk in self._do_stream(pcfg, prov, use_model, messages, temperature, max_tokens, system_prompt):
                    yield chunk
                return
            except Exception as exc:
                logger.warning("LLM stream %s/%s failed: %s — trying next", prov, use_model, exc)
                if "429" in repr(exc):
                    self._provider_cooldown[prov] = time.monotonic() + 90
                continue

        raise RuntimeError(f"All LLM providers failed for streaming {provider}/{model}")

    async def _do_stream(
        self,
        pcfg: dict, provider: str, model: str,
        messages: list[LLMMessage],
        temperature: float, max_tokens: int,
        system_prompt: str,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Single-provider streaming attempt."""
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)
        logger.warning("LLM stream trying %s/%s ...", provider, model)

        msgs = []
        sys_content = system_prompt or ""
        for m in messages:
            d = {"role": m.role, "content": m.content or ""}
            if m.name:
                d["name"] = m.name
            if provider == "minimax":
                # MiniMax rejects system role in streaming
                if d["role"] == "system":
                    if not msgs:
                        sys_content = (sys_content + "\n\n" + d["content"]).strip() if sys_content else d["content"]
                    else:
                        d["role"] = "user"
                        d["content"] = f"[System instruction]: {d['content']}"
                        msgs.append(d)
                    continue
                # MiniMax rejects tool messages — skip tool results and assistant tool_call messages
                if d["role"] == "tool":
                    continue
                if d["role"] == "assistant" and getattr(m, "tool_calls", None):
                    continue
            else:
                if m.tool_call_id:
                    d["tool_call_id"] = m.tool_call_id
                if m.tool_calls:
                    d["tool_calls"] = m.tool_calls
                    d.pop("content", None)
            msgs.append(d)
        # Inject system prompt
        if sys_content:
            if provider == "minimax":
                for i, m in enumerate(msgs):
                    if m["role"] == "user":
                        msgs[i]["content"] = f"[System instructions]:\n{sys_content}\n\n[User message]:\n{m['content']}"
                        break
                else:
                    msgs.insert(0, {"role": "user", "content": sys_content})
            else:
                msgs.insert(0, {"role": "system", "content": sys_content})

        effective_max = max_tokens
        if provider == "minimax":
            effective_max = max(max_tokens, 16000)
        elif model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex"):
            effective_max = max(max_tokens, 8000)

        mt_param = pcfg.get("max_tokens_param", {}).get(model, "max_tokens")
        body = {
            "model": model,
            "messages": msgs,
            mt_param: effective_max,
            "stream": True,
        }
        # GPT-5-mini only supports temperature=1 (default)
        if not (model.startswith("gpt-5-mini") or model.startswith("gpt-5.1-codex")):
            body["temperature"] = temperature

        # Use a separate client for streaming to avoid blocking the shared client
        stream_http = httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0))
        try:
            async with stream_http.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise RuntimeError(f"HTTP {resp.status_code}: {text[:200]}")
                logger.warning("LLM stream %s/%s connected", provider, model)
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        yield LLMStreamChunk(delta="", done=True, model=model)
                        return
                    try:
                        data = json.loads(payload)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        finish = data.get("choices", [{}])[0].get("finish_reason")
                        if content:
                            yield LLMStreamChunk(delta=content, model=model)
                        if finish:
                            yield LLMStreamChunk(delta="", done=True, model=model, finish_reason=finish)
                            return  # MiniMax doesn't send [DONE], exit on finish_reason
                    except json.JSONDecodeError:
                        continue
        finally:
            await stream_http.aclose()

    def set_trace_context(self, agent_id: str = "", session_id: str = "", mission_id: str = ""):
        """Set context for observability tracing on subsequent calls."""
        self._trace_context = {"agent_id": agent_id, "session_id": session_id, "mission_id": mission_id}

    def _trace(self, result: LLMResponse, messages: list[LLMMessage]):
        """Record LLM call in observability store."""
        try:
            from .observability import get_tracer
            ctx = self._trace_context
            input_preview = ""
            if messages:
                last = messages[-1]
                input_preview = (last.content if isinstance(last, LLMMessage) else last.get("content", ""))[:200]
            get_tracer().trace_call(
                provider=result.provider,
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                duration_ms=result.duration_ms,
                agent_id=ctx.get("agent_id", ""),
                session_id=ctx.get("session_id", ""),
                mission_id=ctx.get("mission_id", ""),
                input_preview=input_preview,
                output_preview=result.content[:200] if result.content else "",
            )
        except Exception as exc:
            logger.debug("Trace recording failed: %s", exc)

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
