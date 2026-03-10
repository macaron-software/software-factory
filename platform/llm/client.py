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
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..db.adapter import get_connection

import httpx

logger = logging.getLogger(__name__)

# Provider configs — OpenAI-compatible endpoints
_PROVIDERS = {
    "azure-ai": {
        "name": "Azure AI Foundry (GPT-5.2)",
        "base_url": os.environ.get(
            "AZURE_AI_ENDPOINT", "https://swedencentral.api.cognitive.microsoft.com"
        ).rstrip("/"),
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
        "name": "Azure OpenAI",
        "base_url": os.environ.get(
            "AZURE_OPENAI_ENDPOINT", "https://ascii-ui-openai.openai.azure.com"
        ).rstrip("/"),
        "key_env": "AZURE_OPENAI_API_KEY",
        # Deployed on inno-aks-openai: gpt-5-mini, gpt-5.2, gpt-5.2-codex ONLY (no gpt-5.1)
        "models": [
            "gpt-5-mini",
            "gpt-5",
            "gpt-5.1",
            "gpt-5.2",
            "gpt-5.1-codex",
            "gpt-4.1",
        ],
        "default": "gpt-5-mini",
        "auth_header": "api-key",
        "auth_prefix": "",
        "azure_api_version": "2025-01-01-preview",
        "azure_deployment_map": {
            "gpt-5-mini": os.environ.get("AZURE_DEPLOY_GPT5_MINI", "gpt-5-mini"),
            "gpt-5": os.environ.get("AZURE_DEPLOY_GPT5", "gpt-5"),
            "gpt-5.1": os.environ.get("AZURE_DEPLOY_GPT51", "gpt-5.2"),
            "gpt-5.2": os.environ.get("AZURE_DEPLOY_GPT52", "gpt-5.2"),
            "gpt-5.1-codex": os.environ.get("AZURE_DEPLOY_CODEX", "gpt-5.2-codex"),
            "gpt-4.1": os.environ.get("AZURE_DEPLOY_GPT41", "gpt-4.1"),
        },
        "max_tokens_param": {
            "gpt-5-mini": "max_completion_tokens",
            "gpt-5": "max_completion_tokens",
            "gpt-5.1": "max_completion_tokens",
            "gpt-5.2": "max_completion_tokens",
            "gpt-4.1": "max_completion_tokens",
            # gpt-5.1-codex uses Responses API (max_output_tokens handled separately)
        },
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
    "local-mlx": {
        "name": "Local MLX (mlx_lm.server)",
        "base_url": os.environ.get("LOCAL_MLX_URL", "http://localhost:8080/v1"),
        "key_env": None,  # no API key needed
        "models": [
            os.environ.get("LOCAL_MLX_MODEL", "mlx-community/Qwen3.5-35B-A3B-4bit")
        ],
        "default": os.environ.get(
            "LOCAL_MLX_MODEL", "mlx-community/Qwen3.5-35B-A3B-4bit"
        ),
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "no_auth": True,  # skip auth header entirely
    },
    "ollama": {
        "name": "Ollama (local)",
        "base_url": os.environ.get("OLLAMA_URL", "http://localhost:11434/v1"),
        "key_env": None,
        "models": [os.environ.get("OLLAMA_MODEL", "qwen3:14b")],
        "default": os.environ.get("OLLAMA_MODEL", "qwen3:14b"),
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "no_auth": True,
    },
    # WHY: OpenCode Go subscription — OpenAI-compatible API at opencode.ai/zen/go/v1.
    # Source of truth: https://models.dev/api.json (opencode-go provider).
    # Base URL confirmed via models.dev registry: https://opencode.ai/zen/go/v1
    # API key env var: OPENCODE_API_KEY (sk-... format from opencode.ai/auth)
    # Full model catalog: https://opencode.ai/docs/zen
    "opencode": {
        "name": "OpenCode (Go)",
        "base_url": os.environ.get(
            "OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1"
        ),
        "key_env": "OPENCODE_API_KEY",
        "models": [
            os.environ.get("OPENCODE_DEFAULT_MODEL", "kimi-k2.5"),
            "kimi-k2.5",  # Kimi K2.5 — Moonshot AI via opencode-go subscription
            "glm-5",  # GLM-5 — Zhipu AI via opencode-go subscription
            "minimax-m2.5",  # MiniMax M2.5 via opencode-go subscription
        ],
        "default": os.environ.get("OPENCODE_DEFAULT_MODEL", "kimi-k2.5"),
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
    },
}

# Fallback order driven by PLATFORM_LLM_PROVIDER (local=minimax first, azure=azure-openai first)
# Auto-detect Azure when AZURE_DEPLOY=1 (not just from key presence)
# LOCAL_MLX_ENABLED=1 takes priority over MINIMAX_API_KEY for primary detection
_local_mlx_enabled = os.environ.get("LOCAL_MLX_ENABLED", "").strip().lower() not in (
    "",
    "0",
    "false",
    "no",
)
_primary = os.environ.get("PLATFORM_LLM_PROVIDER") or (
    "local-mlx"
    if _local_mlx_enabled
    else "azure-openai"
    if os.environ.get("AZURE_OPENAI_API_KEY")
    else "minimax"
)
_is_azure = bool(os.environ.get("AZURE_DEPLOY", ""))

# ── Per-model profiles (reasoning, token budget, API wire format) ──────────────
# Each GPT-5.x model is a reasoning model: it consumes part of max_completion_tokens
# budget on internal reasoning BEFORE producing visible output.  A budget of 8000
# can leave 0 visible tokens on complex prompts.  We use 16000 as floor.
# MiniMax-M2.5 uses <think> blocks (different mechanism) — also needs high budget.
MODEL_PROFILES: dict[str, dict] = {
    "gpt-5-mini": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_completion_tokens",
        "api": "chat",
    },
    "gpt-5": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_completion_tokens",
        "api": "chat",
    },
    "gpt-5.1": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_completion_tokens",
        "api": "chat",
    },
    "gpt-5.2": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_completion_tokens",
        "api": "chat",
    },
    "gpt-5.1-codex": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_output_tokens",
        "api": "responses",
    },
    "gpt-5.2-codex": {
        "reasoning": True,
        "supports_temperature": False,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_output_tokens",
        "api": "responses",
    },
    "gpt-4.1": {
        "reasoning": False,
        "supports_temperature": True,
        "min_completion_tokens": 4096,
        "max_tokens_param": "max_completion_tokens",
        "api": "chat",
    },
    "MiniMax-M2.5": {
        "reasoning": False,
        "supports_temperature": True,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_tokens",
        "api": "chat",
        "think_blocks": True,
    },
    "MiniMax-M2.1": {
        "reasoning": False,
        "supports_temperature": True,
        "min_completion_tokens": 16000,
        "max_tokens_param": "max_tokens",
        "api": "chat",
        "think_blocks": True,
    },
}

_DEFAULT_PROFILE: dict = {
    "reasoning": False,
    "supports_temperature": True,
    "min_completion_tokens": 4096,
    "max_tokens_param": "max_tokens",
    "api": "chat",
}


def _get_profile(model: str) -> dict:
    """Return model profile with prefix-matching fallback."""
    if model in MODEL_PROFILES:
        return MODEL_PROFILES[model]
    # Prefix match (e.g. "gpt-5-mini-2025-02-01" → "gpt-5-mini")
    for key in sorted(MODEL_PROFILES.keys(), key=len, reverse=True):
        if model.startswith(key):
            return MODEL_PROFILES[key]
    return _DEFAULT_PROFILE


# Local inference servers require explicit opt-in
def _env_flag(name: str) -> bool:
    """Return True only for non-empty values that are not '0', 'false', 'no'."""
    v = os.environ.get(name, "").strip().lower()
    return v not in ("", "0", "false", "no")


_ollama_enabled = _env_flag("OLLAMA_ENABLED")
_opencode_enabled = bool(
    os.environ.get("OPENCODE_API_KEY", "")
    or _env_flag("OPENCODE_ENABLED")
    or os.path.isfile(os.path.expanduser("~/.config/factory/opencode.key"))
)
# ── LLM timeout settings (override via env vars) ──────────────────────────────
# LLM_TIMEOUT_HTTP     : httpx total timeout per request (seconds). Default: 600.
# LLM_TIMEOUT_CONNECT  : httpx connect timeout (seconds). Default: 30.
# LLM_TIMEOUT_MLX_WAIT : max seconds to wait for local-mlx server to become ready. Default: 120.
_LLM_TIMEOUT_HTTP = float(os.environ.get("LLM_TIMEOUT_HTTP", "180"))
_LLM_TIMEOUT_CONNECT = float(os.environ.get("LLM_TIMEOUT_CONNECT", "10"))
_LLM_TIMEOUT_MLX_WAIT = int(os.environ.get("LLM_TIMEOUT_MLX_WAIT", "120"))
# Hard wall-clock cap per LLM call — httpx read timeout resets on each chunk,
# so chunked/streaming APIs (MiniMax <think>) can hang forever without this.
_LLM_TIMEOUT_TOTAL = float(os.environ.get("LLM_TIMEOUT_TOTAL", "180"))

_fallback_env = os.environ.get("PLATFORM_LLM_FALLBACK", None)
# NO FALLBACK — ever. Fail fast, surface real LLM errors.
# Silent fallback masks broken providers (opencode HTTP 500, minimax conn issues).
# If primary fails → RuntimeError → visible in logs → fix the root cause.
_FALLBACK_CHAIN = [_primary]

_rtk_cache: dict = {}

_mlx_proc: "subprocess.Popen | None" = None  # noqa: F821
_mlx_lock = asyncio.Lock() if False else __import__("threading").Lock()


def _ensure_mlx_server() -> None:
    """Start mlx_lm.server if LOCAL_MLX_ENABLED and not already responding."""
    import subprocess

    global _mlx_proc

    mlx_url = os.environ.get("LOCAL_MLX_URL", "http://localhost:8080/v1")
    mlx_model = os.environ.get("LOCAL_MLX_MODEL", "mlx-community/Qwen3.5-35B-A3B-4bit")

    # Health check with generous timeout — avoids false negatives on loaded servers
    def _is_up(t: float = 5.0) -> bool:
        try:
            import urllib.request

            urllib.request.urlopen(f"{mlx_url}/models", timeout=t)
            return True
        except Exception:
            return False

    if _is_up():
        return  # already running

    with _mlx_lock:
        if _is_up():
            return

        # Already launched by us and still running?
        if _mlx_proc is not None and _mlx_proc.poll() is None:
            return

        logger.warning(
            "local-mlx: server not found on %s — auto-launching mlx_lm.server", mlx_url
        )
        try:
            port = int(mlx_url.rstrip("/").rsplit(":", 1)[-1].split("/")[0])
        except Exception:
            port = 8080
        _mlx_proc = subprocess.Popen(
            [
                "python3",
                "-m",
                "mlx_lm.server",
                "--model",
                mlx_model,
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.warning("local-mlx: launched PID %d, model=%s", _mlx_proc.pid, mlx_model)

        # Wait up to _LLM_TIMEOUT_MLX_WAIT seconds for it to come up
        import time as _time

        for _ in range(_LLM_TIMEOUT_MLX_WAIT):
            _time.sleep(1)
            if _is_up():
                logger.warning("local-mlx: server ready on %s", mlx_url)
                return
        logger.warning(
            "local-mlx: server did not become ready after %ds", _LLM_TIMEOUT_MLX_WAIT
        )


class _RateLimiter:
    """Sliding window rate limiter with async queuing.

    Azure OpenAI gpt-5-mini: 100 req/60s, 100K tokens/60s.
    With ~12K tokens per agent call, we hit the token limit at ~8 req/min.
    Target: 6 req/60s to stay safely under token limit.
    """

    def __init__(self, max_requests: int = 6, window_seconds: float = 60.0):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self, timeout: float = 120.0):
        """Wait until a request slot is available. Raises TimeoutError after timeout."""
        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._window
                self._timestamps = [t for t in self._timestamps if t > cutoff]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                # Calculate wait time until oldest request exits the window
                wait = self._timestamps[0] - cutoff
            if time.monotonic() + wait > deadline:
                raise TimeoutError(
                    f"Rate limiter: waited {timeout}s, still at capacity ({self._max} req/{self._window}s)"
                )
            await asyncio.sleep(min(wait + 0.1, 5.0))

    @property
    def usage(self) -> str:
        now = time.monotonic()
        cutoff = now - self._window
        active = sum(1 for t in self._timestamps if t > cutoff)
        return f"{active}/{self._max}"


# Global rate limiter (shared across all agents in this process)
_rate_limiter = _RateLimiter(
    max_requests=int(os.environ.get("LLM_RATE_LIMIT_RPM", "15")),
    window_seconds=60.0,
)


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None  # for role=tool responses
    tool_calls: list[dict] | None = None  # for assistant tool_calls


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
    tokens_in: int = 0
    tokens_out: int = 0


# Cost estimation: $/1M tokens (input, output) per model
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.2": (2.50, 10.00),
    "gpt-5-mini": (0.40, 1.60),
    "kimi-k2": (0.60, 2.40),
    "m1": (0.50, 2.00),
    "m2.5": (0.50, 2.00),
}
_DEFAULT_PRICING = (1.00, 4.00)  # fallback for unknown models


class LLMClient:
    """Async LLM client with multi-provider support, fallback, and circuit breaker."""

    # Circuit breaker: opens after FAIL_THRESHOLD errors in WINDOW seconds
    CB_FAIL_THRESHOLD = 5
    CB_WINDOW = 60  # seconds
    CB_OPEN_DURATION = 120  # seconds — how long circuit stays open

    def __init__(self):
        self._http: httpx.AsyncClient | None = None
        self._stats = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "errors": 0}
        self._usage_table_ready = False
        # Cooldown: provider → timestamp when it becomes available again
        self._provider_cooldown: dict[str, float] = {}
        # Circuit breaker: provider → list of failure timestamps
        self._cb_failures: dict[str, list[float]] = {}
        self._cb_open_until: dict[str, float] = {}
        # Context for observability tracing (set by caller before chat())
        self._trace_context: dict = {}  # agent_id, session_id, mission_id

    def _cb_record_failure(self, provider: str):
        """Record a failure for circuit breaker evaluation."""
        now = time.monotonic()
        fails = self._cb_failures.setdefault(provider, [])
        fails.append(now)
        # Trim old failures outside window
        cutoff = now - self.CB_WINDOW
        self._cb_failures[provider] = [t for t in fails if t > cutoff]
        if len(self._cb_failures[provider]) >= self.CB_FAIL_THRESHOLD:
            self._cb_open_until[provider] = now + self.CB_OPEN_DURATION
            self._cb_failures[provider] = []
            logger.error(
                "Circuit breaker OPEN for %s (%d failures in %ds) — blocked for %ds",
                provider,
                self.CB_FAIL_THRESHOLD,
                self.CB_WINDOW,
                self.CB_OPEN_DURATION,
            )

    def _cb_record_success(self, provider: str):
        """Reset failures on success (half-open → closed)."""
        self._cb_failures.pop(provider, None)
        self._cb_open_until.pop(provider, None)

    def _cb_is_open(self, provider: str) -> bool:
        """Check if circuit breaker is open for provider."""
        until = self._cb_open_until.get(provider, 0)
        if until > time.monotonic():
            return True
        if until > 0:
            # Half-open: allow one probe request
            self._cb_open_until.pop(provider, None)
        return False

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=_LLM_TIMEOUT_HTTP)
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

    @staticmethod
    def _is_codex_model(model: str) -> bool:
        return "codex" in model

    def _build_url(self, pcfg: dict, model: str) -> str:
        base = pcfg["base_url"].rstrip("/")
        if pcfg.get("azure_api_version") and base:
            if self._is_codex_model(model):
                # Codex models use Responses API (no deployment in URL, model in body)
                return f"{base}/openai/responses?api-version=2025-03-01-preview"
            # Standard Azure: deployment-based URL
            dep_map = pcfg.get("azure_deployment_map", {})
            deployment = dep_map.get(model, model)
            return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={pcfg['azure_api_version']}"
        return f"{base}/chat/completions"

    def _build_headers(self, pcfg: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if pcfg.get("no_auth"):
            return headers
        key = self._get_api_key(pcfg)
        if pcfg.get("auth_header") and key and key != "no-key":
            headers[pcfg["auth_header"]] = f"{pcfg.get('auth_prefix', '')}{key}"
        return headers

    async def chat(
        self,
        messages: list[LLMMessage],
        provider: str = _primary,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Send a chat completion request. Falls back to next provider on failure."""
        # ── Cache lookup (deterministic dedup) ──
        from .cache import get_cache

        _llm_cache = get_cache()
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        cache_model = model or provider
        cached = _llm_cache.get(cache_model, msg_dicts, temperature, tools)
        if cached:
            logger.info(
                "LLM cache HIT (%s, saved %d tokens)",
                cache_model,
                cached["tokens_in"] + cached["tokens_out"],
            )
            return LLMResponse(
                content=cached["content"],
                tokens_in=cached["tokens_in"],
                tokens_out=cached["tokens_out"],
                model=cache_model,
                provider="cache",
            )

        if _is_azure:
            provider = "azure-openai"
        # NO FALLBACK — single provider, fail fast
        providers_to_try = [provider]
        if "local-mlx" in providers_to_try and _local_mlx_enabled:
            _ensure_mlx_server()

        # Thompson Sampling: reorder by Beta-sampled quality (skip on Azure — forced)
        if not _is_azure and len(providers_to_try) > 1:
            try:
                from .llm_thompson import llm_thompson_select

                _best = llm_thompson_select(
                    [p for p in providers_to_try if p in _PROVIDERS]
                )
                if _best and _best != providers_to_try[0]:
                    providers_to_try = [_best] + [
                        p for p in providers_to_try if p != _best
                    ]
            except Exception:
                pass

        for prov in providers_to_try:
            cooldown_until = self._provider_cooldown.get(prov, 0)
            now = time.monotonic()
            if cooldown_until > now:
                remaining = int(cooldown_until - now)
                logger.warning(
                    "LLM %s in cooldown (%ds left), SKIPPING — NO FALLBACK",
                    prov,
                    remaining,
                )
                continue

            # Skip providers with open circuit breaker
            if self._cb_is_open(prov):
                logger.warning(
                    "LLM %s circuit breaker OPEN, SKIPPING — NO FALLBACK", prov
                )
                continue

            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not pcfg.get("no_auth") and (not key or key == "no-key"):
                logger.warning("LLM %s skipped (no API key)", prov)
                continue

            use_model = (
                model
                if (prov == provider and model and model in pcfg.get("models", []))
                else pcfg["default"]
            )

            # Rate limiter: queue until a slot is available (120s max to fail fast)
            try:
                await _rate_limiter.acquire(timeout=120.0)
            except TimeoutError:
                logger.warning(
                    "LLM rate limiter timeout (120s) — retrying (%s)",
                    _rate_limiter.usage,
                )
                await asyncio.sleep(10)
                continue

            logger.warning(
                "LLM trying %s/%s ... [rate: %s]", prov, use_model, _rate_limiter.usage
            )
            max_attempts = 3  # Retry within provider, then fall back to next
            for attempt in range(max_attempts):
                try:
                    # RTK-inspired prompt compression — on by default for all providers
                    # Toggle via integrations table (cached 60s), fallback to env
                    _send_messages = messages
                    _send_system = system_prompt
                    _rtk_now = time.monotonic()
                    if _rtk_now - _rtk_cache.get("ts", 0) > 60.0:
                        try:
                            from ..db.migrations import get_db as _get_db

                            _db = _get_db()
                            _row = _db.execute(
                                "SELECT enabled FROM integrations WHERE id='rtk-compression'"
                            ).fetchone()
                            _db.close()
                            _rtk_cache["enabled"] = (
                                bool(_row["enabled"]) if _row else True
                            )
                        except Exception:
                            _rtk_cache["enabled"] = not bool(
                                os.environ.get("LLM_COMPRESS_DISABLED", "")
                            )
                        _rtk_cache["ts"] = _rtk_now
                    if _rtk_cache.get("enabled", True):
                        try:
                            from .prompt_compressor import (
                                compress_messages as _rtk_compress,
                            )

                            _send_messages, _send_system, _rtk_stats = _rtk_compress(
                                messages, system_prompt, provider=prov
                            )
                            if _rtk_stats["savings_pct"] > 0:
                                logger.warning(
                                    "RTK compress %s: %d→%d tokens (-%s%%)",
                                    prov,
                                    _rtk_stats["original_tokens"],
                                    _rtk_stats["compressed_tokens"],
                                    _rtk_stats["savings_pct"],
                                )
                                try:
                                    from .prompt_compressor import (
                                        record_compression_stats as _rtk_record,
                                    )

                                    _rtk_record(
                                        prov,
                                        _rtk_stats["original_tokens"],
                                        _rtk_stats["compressed_tokens"],
                                        _rtk_stats["savings_pct"],
                                    )
                                except Exception:
                                    pass
                        except Exception as _ce:
                            logger.debug("RTK compressor error (skipped): %s", _ce)
                    result = await asyncio.wait_for(
                        self._do_chat(
                            pcfg,
                            prov,
                            use_model,
                            _send_messages,
                            temperature,
                            max_tokens,
                            _send_system,
                            tools,
                            response_format,
                        ),
                        timeout=_LLM_TIMEOUT_TOTAL,
                    )
                    self._stats["calls"] += 1
                    self._stats["tokens_in"] += result.tokens_in
                    self._stats["tokens_out"] += result.tokens_out
                    logger.warning(
                        "LLM %s/%s OK (%d in, %d out tokens)",
                        prov,
                        use_model,
                        result.tokens_in,
                        result.tokens_out,
                    )
                    self._cb_record_success(prov)
                    # Trace for observability
                    self._trace(result, messages)
                    await self._persist_usage(
                        prov, use_model, result.tokens_in, result.tokens_out
                    )
                    # Thompson Sampling: record success
                    try:
                        from .llm_thompson import llm_thompson_record

                        _quality = min(
                            1.0,
                            result.tokens_out
                            / max(1, result.tokens_in + result.tokens_out),
                        )
                        llm_thompson_record(prov, success=True, quality=_quality)
                    except Exception:
                        pass
                    # Cache the response for future dedup
                    try:
                        _llm_cache.put(
                            cache_model,
                            msg_dicts,
                            temperature,
                            result.content,
                            result.tokens_in,
                            result.tokens_out,
                            tools,
                        )
                    except Exception:
                        pass
                    # Content policy fallback: retry with gpt-5.2 then gpt-5-mini
                    if (
                        result.finish_reason == "content_filter"
                        and prov == "azure-openai"
                    ):
                        for _fb in ["gpt-5.2", "gpt-5-mini"]:
                            if _fb != use_model and _fb in pcfg.get("models", []):
                                logger.warning(
                                    "LLM %s/%s content policy — retrying with %s",
                                    prov,
                                    use_model,
                                    _fb,
                                )
                                try:
                                    _fb_result = await self._do_chat(
                                        pcfg,
                                        prov,
                                        _fb,
                                        _send_messages,
                                        temperature,
                                        max_tokens,
                                        _send_system,
                                        tools,
                                        response_format,
                                    )
                                    if _fb_result.finish_reason != "content_filter":
                                        result = _fb_result
                                        break
                                except Exception:
                                    pass
                    return result
                except Exception as exc:
                    err_str = repr(exc)
                    is_rate_limit = "429" in err_str or "RateLimitReached" in err_str
                    is_transient = (
                        "ReadError" in err_str
                        or "ConnectError" in err_str
                        or "RemoteProtocolError" in err_str
                        or "TimeoutError" in err_str
                    )
                    is_quota_exhausted = (
                        is_rate_limit and "usage limit exceeded" in err_str.lower()
                    )
                    if (
                        attempt < max_attempts - 1
                        and not is_quota_exhausted
                        and (is_transient or (is_rate_limit and not _is_azure))
                    ):
                        import random

                        # Exponential backoff with jitter: 10s, 20s, 40s, 80s
                        base = (2**attempt) * (10 if is_rate_limit else 3)
                        jitter = random.uniform(0, base * 0.3)
                        delay = min(base + jitter, 90)
                        logger.warning(
                            "LLM %s/%s %s (attempt %d/%d): %s — retrying in %ds",
                            prov,
                            use_model,
                            "rate-limited" if is_rate_limit else "transient",
                            attempt + 1,
                            max_attempts,
                            err_str[:120],
                            int(delay),
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "LLM %s/%s failed after %d attempts: %s",
                        prov,
                        use_model,
                        attempt + 1,
                        err_str[:200],
                    )
                    self._stats["errors"] += 1
                    # HTTP 4xx client errors shouldn't open the circuit breaker
                    _is_client_err = any(
                        f"HTTP {c}" in err_str for c in ("400", "401", "403", "404")
                    )
                    if not _is_client_err:
                        self._cb_record_failure(prov)
                    await self._persist_usage(prov, use_model, 0, 0, error=True)
                    # Thompson Sampling: record failure
                    try:
                        from .llm_thompson import llm_thompson_record

                        llm_thompson_record(prov, success=False, quality=0.0)
                    except Exception:
                        pass
                    if is_rate_limit:
                        # quota exhausted → long cooldown (4h windows); generic 429 → 30s
                        is_quota_exhausted = "usage limit exceeded" in err_str.lower()
                        cd = 3600 if is_quota_exhausted else 30
                        self._provider_cooldown[prov] = time.monotonic() + cd
                        logger.warning(
                            "LLM %s → cooldown %ds (%s), falling back to next provider",
                            prov,
                            cd,
                            "quota exhausted" if is_quota_exhausted else "rate limited",
                        )
                        if is_quota_exhausted:
                            break  # skip remaining retries — quota won't recover in seconds
                continue

        raise RuntimeError(f"All LLM providers failed for {provider}/{model}")

    async def _do_chat(
        self,
        pcfg: dict,
        provider: str,
        model: str,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        # gpt-5.1-codex uses Responses API (completely different wire format)
        if self._is_codex_model(model) and pcfg.get("azure_api_version"):
            return await self._do_chat_responses(
                pcfg, provider, model, messages, max_tokens, system_prompt, tools
            )
        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)

        msgs = []
        if system_prompt:
            # For Ollama/Qwen3: prepend /no_think to disable thinking mode (saves tokens)
            sp = (
                f"/no_think\n{system_prompt}" if provider == "ollama" else system_prompt
            )
            msgs.append({"role": "system", "content": sp})
        elif provider == "ollama":
            msgs.append({"role": "system", "content": "/no_think"})
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
            # MiniMax M2.5 supports standard tool_calls/tool format natively.
            # Only mangle for M2.1 (which doesn't support tool role messages).
            _is_minimax_legacy = provider == "minimax" and model == "MiniMax-M2.1"
            if _is_minimax_legacy and d["role"] == "tool":
                d["role"] = "user"
                d["content"] = f"[Résultat de {name or 'tool'}]:\n{content}"
                msgs.append(d)
                continue
            if _is_minimax_legacy and role == "assistant" and tool_calls:
                tc_names = [
                    tc.get("function", {}).get("name", "?")
                    if isinstance(tc, dict)
                    else "?"
                    for tc in (tool_calls or [])
                ]
                d["content"] = f"[Appel outils: {', '.join(tc_names)}]"
                msgs.append(d)
                continue
            # MiniMax requires consistent name across all messages (error 2013 if mixed).
            # Strip name for MiniMax to avoid inconsistency between messages.
            if name and provider != "minimax":
                d["name"] = name
            if tool_call_id:
                d["tool_call_id"] = tool_call_id
            if tool_calls:
                d["tool_calls"] = tool_calls
                d.pop("content", None)  # assistant tool_call msgs may have no content
            msgs.append(d)

        # Strip orphaned tool result messages: if tool_call_id has no matching
        # assistant tool_calls entry, the API will reject with HTTP 400.
        # This can happen on session resume when history is partially restored.
        _known_call_ids: set[str] = set()
        for _m in msgs:
            if _m.get("role") == "assistant":
                for _tc in _m.get("tool_calls") or []:
                    _cid = _tc.get("id") if isinstance(_tc, dict) else None
                    if _cid:
                        _known_call_ids.add(_cid)
        msgs = [
            _m
            for _m in msgs
            if not (
                _m.get("role") == "tool"
                and _m.get("tool_call_id")
                and _m.get("tool_call_id") not in _known_call_ids
            )
        ]

        # local-mlx requires system message strictly at position 0 — merge all system msgs
        if provider == "local-mlx":
            embedded_sys = [m for m in msgs if m["role"] == "system"]
            msgs = [m for m in msgs if m["role"] != "system"]
            if embedded_sys:
                merged = "\n\n".join(m["content"] for m in embedded_sys)
                msgs.insert(0, {"role": "system", "content": merged})

        body = {
            "model": model,
            "messages": msgs,
        }
        # Per-model profile: reasoning, temperature, token budget, param name
        _profile = _get_profile(model)
        if _profile["supports_temperature"]:
            body["temperature"] = temperature
        effective_max = max(max_tokens, _profile["min_completion_tokens"])
        mt_param = _profile["max_tokens_param"]
        body[mt_param] = effective_max

        if tools:
            body["tools"] = tools
            if provider == "minimax":
                # M2.5 supports standard tool_choice including "required".
                # Use forced single-tool mode when only 1 tool (most reliable),
                # otherwise "required" to force at least one tool call.
                if len(tools) == 1:
                    tool_name = tools[0].get("function", {}).get("name", "")
                    body["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_name},
                    }
                else:
                    body["tool_choice"] = "required"
                # Disable parallel tool calls — M2.5 is more reliable with sequential calls
                body["parallel_tool_calls"] = False
            else:
                body["tool_choice"] = "auto"
            # GPT models sometimes output tool calls as text "[Calling tools: ...]"
            # instead of using the structured tool_calls format. Add explicit instruction.
            _tool_instruction = (
                "\n\n<tool_format_rule>NEVER write tool calls as text like "
                "'[Calling tools: ...]' or '[Tool: ...]'. ALWAYS use the native "
                "function_call/tool_calls API format. Text-formatted tool calls "
                "will be rejected.</tool_format_rule>"
            )
            # Append to last system message or first message
            for m in reversed(msgs):
                if m.get("role") == "system":
                    m["content"] = m.get("content", "") + _tool_instruction
                    break
            else:
                if msgs and msgs[0].get("role") == "system":
                    msgs[0]["content"] = msgs[0].get("content", "") + _tool_instruction
        if response_format:
            body["response_format"] = response_format

        t0 = time.monotonic()

        # Retry loop for 429 rate limits (3 attempts with exponential backoff)
        import random

        for attempt in range(3):
            resp = await http.post(url, json=body, headers=headers)
            if resp.status_code != 429:
                break
            retry_after = int(resp.headers.get("Retry-After", (2**attempt) * 10))
            retry_after = max(retry_after, 10)
            retry_after = min(retry_after + random.randint(0, 5), 90)
            logger.warning(
                "LLM %s/%s rate-limited (429), retry in %ds (attempt %d/3) [rate: %s]",
                provider,
                model,
                retry_after,
                attempt + 1,
                _rate_limiter.usage,
            )
            await asyncio.sleep(retry_after)

        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 400 and "content management policy" in resp.text.lower():
            # Azure content filter blocked the prompt — not a transient error, don't
            # count in circuit breaker, return a neutral synthetic completion instead.
            logger.warning(
                "LLM %s/%s HTTP 400 content policy — returning synthetic neutral response",
                provider,
                model,
            )
            return LLMResponse(
                content="[CONTENT_POLICY_BLOCKED] Azure content management policy prevented this analysis. Treating as neutral/pass.",
                model=model,
                provider=provider,
                tool_calls=[],
                finish_reason="content_filter",
                tokens_in=0,
                tokens_out=0,
                duration_ms=elapsed,
            )

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or [{}]
        choice = choices[0] if choices else {}
        msg = choice.get("message", {})
        content = msg.get("content", "") or ""
        # Ollama/Qwen3: thinking models put response in reasoning field when content is empty
        # GLM-5/kimi: use reasoning_content field
        if not content:
            for _rf in ("reasoning", "reasoning_content"):
                _rtext = msg.get(_rf)
                if _rtext:
                    content = _rtext.strip()
                    break
        # Strip <think> blocks from MiniMax / Qwen3
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
            parsed_tool_calls.append(
                LLMToolCall(
                    id=tc.get("id", ""),
                    function_name=fn.get("name", ""),
                    arguments=args,
                )
            )

        usage = data.get("usage", {})
        _finish = choice.get("finish_reason", "stop")

        # Reasoning model budget exhaustion: reasoning consumed all tokens → empty content.
        # Retry once with doubled budget instead of returning empty/blocked.
        if (
            not content
            and not parsed_tool_calls
            and _finish == "length"
            and _profile.get("reasoning")
            and not getattr(self, "_reasoning_retry", False)
        ):
            doubled = effective_max * 2
            logger.warning(
                "LLM %s/%s reasoning budget exhausted (%d tokens, content empty) — retrying with %d",
                provider,
                model,
                effective_max,
                doubled,
            )
            self._reasoning_retry = True
            try:
                body[mt_param] = doubled
                t0_retry = time.monotonic()
                resp2 = await http.post(url, json=body, headers=headers)
                elapsed2 = int((time.monotonic() - t0_retry) * 1000)
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    choices2 = data2.get("choices") or [{}]
                    choice2 = choices2[0] if choices2 else {}
                    msg2 = choice2.get("message", {})
                    content2 = msg2.get("content", "") or ""
                    if "<think>" in content2 and "</think>" in content2:
                        idx2 = content2.index("</think>") + len("</think>")
                        after2 = content2[idx2:].strip()
                        if after2:
                            content2 = after2
                    tc2 = []
                    for tc in msg2.get("tool_calls") or []:
                        fn = tc.get("function", {})
                        try:
                            args = json.loads(fn.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        tc2.append(
                            LLMToolCall(
                                id=tc.get("id", ""),
                                function_name=fn.get("name", ""),
                                arguments=args,
                            )
                        )
                    usage2 = data2.get("usage", {})
                    return LLMResponse(
                        content=content2,
                        model=data2.get("model", model),
                        provider=provider,
                        tokens_in=usage2.get("prompt_tokens", 0),
                        tokens_out=usage2.get("completion_tokens", 0),
                        duration_ms=elapsed + elapsed2,
                        finish_reason=choice2.get("finish_reason", "stop"),
                        tool_calls=tc2,
                    )
            except Exception as e:
                logger.warning("LLM reasoning retry failed: %s", e)
            finally:
                self._reasoning_retry = False

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=provider,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            duration_ms=elapsed,
            finish_reason=_finish,
            tool_calls=parsed_tool_calls,
        )

    async def _do_chat_responses(
        self,
        pcfg: dict,
        provider: str,
        model: str,
        messages: list[LLMMessage],
        max_tokens: int,
        system_prompt: str,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Handle Azure Responses API for codex models (gpt-5.1-codex etc.)."""
        import random

        http = await self._get_http()
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)

        # Build input array — Responses API uses mixed item types
        input_msgs: list[dict] = []
        if system_prompt:
            input_msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "") or ""
                tool_call_id = m.get("tool_call_id")
                tool_calls = m.get("tool_calls")
            else:
                role = m.role
                content = m.content or ""
                tool_call_id = m.tool_call_id
                tool_calls = m.tool_calls

            if role == "tool" and tool_call_id:
                # Tool result → function_call_output item
                input_msgs.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call_id,
                        "output": content,
                    }
                )
            elif role == "assistant" and tool_calls:
                # Previous assistant tool calls → function_call items
                for tc in tool_calls or []:
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        input_msgs.append(
                            {
                                "type": "function_call",
                                "call_id": tc.get("id", ""),
                                "name": fn.get("name", ""),
                                "arguments": fn.get("arguments", "{}"),
                            }
                        )
            else:
                input_msgs.append({"role": role, "content": content})

        # Convert tools from chat/completions format → Responses API format
        resp_tools = None
        if tools:
            resp_tools = []
            for t in tools:
                fn = t.get("function", t)  # handle both wrapped and flat
                resp_tools.append(
                    {
                        "type": "function",
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    }
                )

        _profile_r = _get_profile(model)
        body: dict = {
            "model": model,
            "input": input_msgs,
            "max_output_tokens": max(max_tokens, _profile_r["min_completion_tokens"]),
        }
        if resp_tools:
            body["tools"] = resp_tools

        t0 = time.monotonic()
        for attempt in range(3):
            resp = await http.post(url, json=body, headers=headers)
            if resp.status_code != 429:
                break
            retry_after = int(resp.headers.get("Retry-After", (2**attempt) * 10))
            retry_after = max(retry_after, 10)
            retry_after = min(retry_after + random.randint(0, 5), 90)
            logger.warning(
                "LLM %s/%s rate-limited (429), retry in %ds (attempt %d/3)",
                provider,
                model,
                retry_after,
                attempt + 1,
            )
            await asyncio.sleep(retry_after)

        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 400 and "content management policy" in resp.text.lower():
            logger.warning(
                "LLM %s/%s HTTP 400 content policy (Responses API) — returning synthetic neutral response",
                provider,
                model,
            )
            return LLMResponse(
                content="[CONTENT_POLICY_BLOCKED] Azure content management policy prevented this analysis. Treating as neutral/pass.",
                model=model,
                provider=provider,
                tool_calls=[],
                finish_reason="content_filter",
                tokens_in=0,
                tokens_out=0,
                duration_ms=elapsed,
            )

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = ""
        parsed_tool_calls: list[LLMToolCall] = []
        for item in data.get("output", []):
            itype = item.get("type", "")
            if itype == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        content += c.get("text", "")
            elif itype == "function_call":
                try:
                    args = json.loads(item.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                parsed_tool_calls.append(
                    LLMToolCall(
                        id=item.get("call_id", item.get("id", "")),
                        function_name=item.get("name", ""),
                        arguments=args,
                    )
                )

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=provider,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            duration_ms=elapsed,
            finish_reason=data.get("status", "completed"),
            tool_calls=parsed_tool_calls,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        provider: str = _primary,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream chat completion response — NO FALLBACK, single provider."""
        if _is_azure:
            provider = "azure-openai"
        # NO FALLBACK — single provider, fail fast
        providers_to_try = [provider]

        for prov in providers_to_try:
            if prov not in _PROVIDERS:
                continue
            now = time.monotonic()
            cooldown_until = self._provider_cooldown.get(prov, 0)
            if cooldown_until > now:
                continue
            if self._cb_is_open(prov):
                continue
            pcfg = self._get_provider_config(prov)
            key = self._get_api_key(pcfg)
            if not pcfg.get("no_auth") and (not key or key == "no-key"):
                continue
            use_model = (
                model
                if (prov == provider and model and model in pcfg.get("models", []))
                else pcfg["default"]
            )
            try:
                await _rate_limiter.acquire(timeout=120.0)
            except TimeoutError:
                logger.warning(
                    "LLM stream rate limiter timeout (120s) — retrying (%s)",
                    _rate_limiter.usage,
                )
                await asyncio.sleep(10)
                continue

            max_attempts = 4
            for attempt in range(max_attempts):
                try:
                    # RTK prompt compression — same as chat() path
                    _stream_messages = messages
                    _stream_system = system_prompt
                    _rtk_now = time.monotonic()
                    if _rtk_now - _rtk_cache.get("ts", 0) > 60.0:
                        try:
                            from ..db.migrations import get_db as _get_db

                            _db = _get_db()
                            _row = _db.execute(
                                "SELECT enabled FROM integrations WHERE id='rtk-compression'"
                            ).fetchone()
                            _db.close()
                            _rtk_cache["enabled"] = (
                                bool(_row["enabled"]) if _row else True
                            )
                        except Exception:
                            _rtk_cache["enabled"] = not bool(
                                os.environ.get("LLM_COMPRESS_DISABLED", "")
                            )
                        _rtk_cache["ts"] = _rtk_now
                    if _rtk_cache.get("enabled", True):
                        try:
                            from .prompt_compressor import (
                                compress_messages as _rtk_compress,
                            )

                            _stream_messages, _stream_system, _rtk_stats = (
                                _rtk_compress(messages, system_prompt, provider=prov)
                            )
                            if _rtk_stats["savings_pct"] > 0:
                                logger.warning(
                                    "RTK stream compress %s: %d→%d tokens (-%s%%)",
                                    prov,
                                    _rtk_stats["original_tokens"],
                                    _rtk_stats["compressed_tokens"],
                                    _rtk_stats["savings_pct"],
                                )
                        except Exception as _ce:
                            logger.debug(
                                "RTK stream compressor error (skipped): %s", _ce
                            )
                    _stream_tokens_in = 0
                    _stream_tokens_out = 0
                    _stream_accumulated = ""
                    _stream_t0 = time.monotonic()
                    async with asyncio.timeout(_LLM_TIMEOUT_TOTAL):
                        async for chunk in self._do_stream(
                            pcfg,
                            prov,
                            use_model,
                            _stream_messages,
                            temperature,
                            max_tokens,
                            _stream_system,
                        ):
                            if chunk.delta:
                                _stream_accumulated += chunk.delta
                            if chunk.tokens_in:
                                _stream_tokens_in = chunk.tokens_in
                            if chunk.tokens_out:
                                _stream_tokens_out = chunk.tokens_out
                            yield chunk
                    # Estimate tokens if API didn't report them
                    if not _stream_tokens_in:
                        _stream_tokens_in = (
                            sum(len(m.content or "") for m in _stream_messages) // 4
                        )
                    if not _stream_tokens_out:
                        _stream_tokens_out = len(_stream_accumulated) // 4
                    self._cb_record_success(prov)
                    self._stats["calls"] += 1
                    self._stats["tokens_in"] += _stream_tokens_in
                    self._stats["tokens_out"] += _stream_tokens_out
                    # Trace streaming call for observability
                    _stream_result = LLMResponse(
                        content=_stream_accumulated,
                        model=use_model,
                        provider=prov,
                        tokens_in=_stream_tokens_in,
                        tokens_out=_stream_tokens_out,
                        duration_ms=int((time.monotonic() - _stream_t0) * 1000),
                    )
                    self._trace(_stream_result, _stream_messages)
                    await self._persist_usage(
                        prov, use_model, _stream_tokens_in, _stream_tokens_out
                    )
                    return
                except Exception as exc:
                    err_str = repr(exc)
                    is_rate_limit = "429" in err_str or "RateLimitReached" in err_str
                    is_transient = (
                        "ReadError" in err_str
                        or "ConnectError" in err_str
                        or "RemoteProtocolError" in err_str
                        or "ServerDisconnected" in err_str
                        or "TimeoutError" in err_str
                    )
                    is_quota_exhausted_stream = (
                        is_rate_limit and "usage limit exceeded" in err_str.lower()
                    )
                    if (
                        attempt < max_attempts - 1
                        and not is_quota_exhausted_stream
                        and ((is_rate_limit and not _is_azure) or is_transient)
                    ):
                        import random

                        delay = min((2**attempt) * 10 + random.uniform(0, 5), 90)
                        logger.warning(
                            "LLM stream %s/%s %s (attempt %d/%d) — retrying in %ds",
                            prov,
                            use_model,
                            "rate-limited" if is_rate_limit else "transient error",
                            attempt + 1,
                            max_attempts,
                            int(delay),
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "LLM stream %s/%s failed: %s — trying next",
                        prov,
                        use_model,
                        err_str[:200],
                    )
                    # HTTP 4xx client errors shouldn't open the circuit breaker
                    _is_client_err_s = any(
                        f"HTTP {c}" in err_str for c in ("400", "401", "403", "404")
                    )
                    if not _is_client_err_s:
                        self._cb_record_failure(prov)
                    if is_rate_limit:
                        is_quota_exhausted = "usage limit exceeded" in err_str.lower()
                        cd = 3600 if is_quota_exhausted else 30
                        self._provider_cooldown[prov] = time.monotonic() + cd
                        logger.warning(
                            "LLM %s stream → cooldown %ds (%s)",
                            prov,
                            cd,
                            "quota exhausted" if is_quota_exhausted else "rate limited",
                        )
                    break

        raise RuntimeError(f"All LLM providers failed for streaming {provider}/{model}")

    async def _do_stream(
        self,
        pcfg: dict,
        provider: str,
        model: str,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        system_prompt: str,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Single-provider streaming attempt."""
        url = self._build_url(pcfg, model)
        headers = self._build_headers(pcfg)
        logger.warning("LLM stream trying %s/%s ...", provider, model)

        msgs = []
        sys_content = system_prompt or ""
        for m in messages:
            d = {"role": m.role, "content": m.content or ""}
            # MiniMax requires consistent name across all messages (error 2013).
            # Strip name for MiniMax to avoid inconsistency between messages.
            if m.name and provider != "minimax":
                d["name"] = m.name
            # MiniMax M2.5 supports native tool_calls/tool format.
            # Only mangle for MiniMax M2.1 (legacy).
            _is_minimax_legacy = provider == "minimax" and model == "MiniMax-M2.1"
            if provider == "minimax":
                # MiniMax rejects system role in streaming
                if d["role"] == "system":
                    if not msgs:
                        sys_content = (
                            (sys_content + "\n\n" + d["content"]).strip()
                            if sys_content
                            else d["content"]
                        )
                    else:
                        d["role"] = "user"
                        d["content"] = f"[System instruction]: {d['content']}"
                        msgs.append(d)
                    continue
                if _is_minimax_legacy:
                    # M2.1 doesn't support tool role — convert to user messages
                    if d["role"] == "tool":
                        tool_name = m.name or "tool"
                        d["role"] = "user"
                        d["content"] = f"[Résultat de {tool_name}]:\n{d['content']}"
                        msgs.append(d)
                        continue
                    if d["role"] == "assistant" and getattr(m, "tool_calls", None):
                        tc_names = [
                            tc.get("function", {}).get("name", "?")
                            for tc in (m.tool_calls or [])
                            if isinstance(tc, dict)
                        ]
                        d["content"] = f"[Appel outils: {', '.join(tc_names)}]"
                        d.pop("tool_calls", None)
                        msgs.append(d)
                        continue
                # M2.5: pass tool_calls/tool_call_id natively (same as OpenAI)
                if m.tool_call_id:
                    d["tool_call_id"] = m.tool_call_id
                if m.tool_calls:
                    d["tool_calls"] = m.tool_calls
                    d.pop("content", None)
            else:
                if m.tool_call_id:
                    d["tool_call_id"] = m.tool_call_id
                if m.tool_calls:
                    d["tool_calls"] = m.tool_calls
                    d.pop("content", None)
            msgs.append(d)
        # Inject system prompt
        # local-mlx (mlx_lm.server) requires system message strictly at position 0 —
        # collect any embedded system msgs from history, merge, put first.
        if provider == "local-mlx":
            embedded_sys = [m for m in msgs if m["role"] == "system"]
            msgs = [m for m in msgs if m["role"] != "system"]
            all_sys = ([sys_content] if sys_content else []) + [
                m["content"] for m in embedded_sys
            ]
            if all_sys:
                msgs.insert(0, {"role": "system", "content": "\n\n".join(all_sys)})
        elif sys_content:
            if provider == "minimax":
                for i, m in enumerate(msgs):
                    if m["role"] == "user":
                        msgs[i]["content"] = (
                            f"[System instructions]:\n{sys_content}\n\n[User message]:\n{m['content']}"
                        )
                        break
                else:
                    msgs.insert(0, {"role": "user", "content": sys_content})
            else:
                msgs.insert(0, {"role": "system", "content": sys_content})

        # Strip orphaned tool result messages (no matching assistant tool_calls).
        # This can happen on resume when conversation history is partially restored.
        _stream_known_ids: set[str] = set()
        for _m in msgs:
            if _m.get("role") == "assistant":
                for _tc in _m.get("tool_calls") or []:
                    _cid = _tc.get("id") if isinstance(_tc, dict) else None
                    if _cid:
                        _stream_known_ids.add(_cid)
        msgs = [
            _m
            for _m in msgs
            if not (
                _m.get("role") == "tool"
                and _m.get("tool_call_id")
                and _m.get("tool_call_id") not in _stream_known_ids
            )
        ]

        _profile_s = _get_profile(model)
        effective_max = max(max_tokens, _profile_s["min_completion_tokens"])
        mt_param = _profile_s["max_tokens_param"]
        body = {
            "model": model,
            "messages": msgs,
            mt_param: effective_max,
            "stream": True,
        }
        if _profile_s["supports_temperature"]:
            body["temperature"] = temperature

        # Use a separate client for streaming to avoid blocking the shared client
        stream_http = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=_LLM_TIMEOUT_CONNECT,
                read=_LLM_TIMEOUT_HTTP,
                write=_LLM_TIMEOUT_CONNECT,
                pool=_LLM_TIMEOUT_CONNECT,
            )
        )
        try:
            async with stream_http.stream(
                "POST", url, json=body, headers=headers
            ) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    if (
                        resp.status_code == 400
                        and b"content management policy" in text.lower()
                    ):
                        logger.warning(
                            "LLM stream %s/%s HTTP 400 content policy — yielding synthetic neutral response",
                            provider,
                            model,
                        )
                        yield LLMStreamChunk(
                            delta="[CONTENT_POLICY_BLOCKED] Azure content management policy prevented this analysis. Treating as neutral/pass.",
                            done=True,
                            model=model,
                            tokens_in=0,
                            tokens_out=0,
                        )
                        return
                    raise RuntimeError(f"HTTP {resp.status_code}: {text[:200]}")
                logger.warning("LLM stream %s/%s connected", provider, model)
                _stream_usage: dict = {}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        yield LLMStreamChunk(
                            delta="",
                            done=True,
                            model=model,
                            tokens_in=_stream_usage.get("prompt_tokens", 0),
                            tokens_out=_stream_usage.get("completion_tokens", 0),
                        )
                        return
                    try:
                        data = json.loads(payload)
                        if data.get("usage"):
                            _stream_usage = data["usage"]
                        choices = data.get("choices") or [{}]
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        finish = choices[0].get("finish_reason")
                        if content:
                            yield LLMStreamChunk(delta=content, model=model)
                        if finish:
                            yield LLMStreamChunk(
                                delta="",
                                done=True,
                                model=model,
                                finish_reason=finish,
                                tokens_in=_stream_usage.get("prompt_tokens", 0),
                                tokens_out=_stream_usage.get("completion_tokens", 0),
                            )
                            return  # MiniMax doesn't send [DONE], exit on finish_reason
                    except json.JSONDecodeError:
                        continue
        finally:
            await stream_http.aclose()

    def set_trace_context(
        self, agent_id: str = "", session_id: str = "", mission_id: str = ""
    ):
        """Set context for observability tracing on subsequent calls."""
        self._trace_context = {
            "agent_id": agent_id,
            "session_id": session_id,
            "mission_id": mission_id,
        }

    def _trace(self, result: LLMResponse, messages: list[LLMMessage]):
        """Record LLM call in observability store."""
        try:
            from .observability import get_tracer

            ctx = self._trace_context
            input_preview = ""
            if messages:
                last = messages[-1]
                input_preview = (
                    last.content
                    if isinstance(last, LLMMessage)
                    else last.get("content", "")
                )[:200]
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
        """List providers with availability status.

        WHY: local-mlx and ollama have no_auth=True which previously caused them
        to always appear as has_key=True in the cockpit — showing '✓ OK' even when
        the local servers weren't running. They now require their explicit enable flag
        (LOCAL_MLX_ENABLED / OLLAMA_ENABLED) to be considered available.
        """
        result = []
        for pid, pcfg in _PROVIDERS.items():
            # Local servers: only available if explicitly enabled
            if pid == "local-mlx":
                has_key = bool(os.environ.get("LOCAL_MLX_ENABLED"))
            elif pid == "ollama":
                has_key = bool(os.environ.get("OLLAMA_ENABLED"))
            elif pcfg.get("no_auth"):
                has_key = True  # other no-auth providers (none currently)
            else:
                key = self._get_api_key(pcfg)
                has_key = bool(key and key != "no-key")
            result.append(
                {
                    "id": pid,
                    "name": pcfg["name"],
                    "models": pcfg["models"],
                    "default": pcfg["default"],
                    "enabled": has_key,
                    "has_key": has_key,
                }
            )
        return result

    # ── LLM usage persistence ──────────────────────────────────────

    def _ensure_usage_table(self):
        """Create llm_usage table if it doesn't exist (called once lazily)."""
        if self._usage_table_ready:
            return
        conn = get_connection()
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS llm_usage (
                id TEXT PRIMARY KEY,
                ts TEXT,
                provider TEXT,
                model TEXT,
                tokens_in INT,
                tokens_out INT,
                cost_estimate REAL,
                agent_id TEXT,
                mission_id TEXT,
                phase TEXT,
                error INT DEFAULT 0
            )""")
            conn.commit()
        finally:
            conn.close()
        self._usage_table_ready = True

    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost in USD based on per-model pricing."""
        price_in, price_out = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
        return (tokens_in * price_in + tokens_out * price_out) / 1_000_000

    async def _persist_usage(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        error: bool = False,
    ):
        """Insert a usage row into the llm_usage SQLite table (non-blocking)."""
        try:
            ctx = self._trace_context
            row = (
                uuid.uuid4().hex,
                datetime.now(timezone.utc).isoformat(),
                provider,
                model,
                tokens_in,
                tokens_out,
                self._estimate_cost(model, tokens_in, tokens_out),
                ctx.get("agent_id", ""),
                ctx.get("mission_id", ""),
                ctx.get("phase", ""),
                1 if error else 0,
            )

            def _insert():
                self._ensure_usage_table()
                conn = get_connection()
                try:
                    conn.execute(
                        "INSERT INTO llm_usage (id,ts,provider,model,tokens_in,tokens_out,"
                        "cost_estimate,agent_id,mission_id,phase,error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        row,
                    )
                    conn.commit()
                finally:
                    conn.close()

            await asyncio.to_thread(_insert)
        except Exception as exc:
            logger.debug("Usage persistence failed: %s", exc)

    async def aggregate_usage(self, days: int = 7) -> dict:
        """Return cost/day, cost/phase, cost/agent breakdowns for the last N days."""

        def _query():
            self._ensure_usage_table()
            conn = get_connection()
            try:
                cutoff = f"datetime('now', '-{days} days')"
                by_day = conn.execute(
                    f"SELECT date(ts) AS day, SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY day ORDER BY day"
                ).fetchall()
                by_phase = conn.execute(
                    f"SELECT phase, SUM(cost_estimate), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY phase ORDER BY SUM(cost_estimate) DESC"
                ).fetchall()
                by_agent = conn.execute(
                    f"SELECT agent_id, SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*)"
                    f" FROM llm_usage WHERE ts >= {cutoff} GROUP BY agent_id ORDER BY SUM(cost_estimate) DESC"
                ).fetchall()
                totals = conn.execute(
                    f"SELECT SUM(cost_estimate), SUM(tokens_in), SUM(tokens_out), COUNT(*), SUM(error)"
                    f" FROM llm_usage WHERE ts >= {cutoff}"
                ).fetchone()
                return {
                    "days": days,
                    "total": {
                        "cost": totals[0] or 0,
                        "tokens_in": totals[1] or 0,
                        "tokens_out": totals[2] or 0,
                        "calls": totals[3] or 0,
                        "errors": totals[4] or 0,
                    },
                    "by_day": [
                        {
                            "day": r[0],
                            "cost": r[1],
                            "tokens_in": r[2],
                            "tokens_out": r[3],
                            "calls": r[4],
                        }
                        for r in by_day
                    ],
                    "by_phase": [
                        {"phase": r[0] or "(none)", "cost": r[1], "calls": r[2]}
                        for r in by_phase
                    ],
                    "by_agent": [
                        {
                            "agent_id": r[0] or "(none)",
                            "cost": r[1],
                            "tokens_in": r[2],
                            "tokens_out": r[3],
                            "calls": r[4],
                        }
                        for r in by_agent
                    ],
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    def _demo_response(self, messages: list["LLMMessage"]) -> "LLMResponse":
        """Return a deterministic mock response for demo/test mode."""
        last = messages[-1].content.lower() if messages else ""
        if any(w in last for w in ("bug", "fix", "error", "crash", "issue", "broken")):
            content = "I've analyzed the issue and identified the root cause. The fix involves correcting the logic in the affected module to handle edge cases properly."
        elif any(
            w in last
            for w in ("deploy", "deployment", "staging", "production", "release")
        ):
            content = "Deployment pipeline initiated. Running pre-deploy checks, building Docker image, and pushing to the target environment."
        elif any(w in last for w in ("test", "spec", "coverage", "unit", "e2e")):
            content = "Test suite analyzed. Writing unit tests with proper assertions and edge case coverage."
        elif any(w in last for w in ("refactor", "clean", "optimize", "improve")):
            content = "Refactoring the code to improve readability and maintainability while preserving existing behavior."
        else:
            content = "I understand the task. Analyzing the requirements and preparing a comprehensive solution."
        return LLMResponse(
            content=content,
            model="demo",
            provider="demo",
            tokens_in=len(last) // 4,
            tokens_out=len(content) // 4,
        )

    @property
    def stats(self) -> dict:
        s = dict(self._stats)
        s["rate_limiter"] = _rate_limiter.usage
        return s


# Singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
