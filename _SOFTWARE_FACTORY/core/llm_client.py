#!/usr/bin/env python3
"""
LLM Client - Unified LLM access for Software Factory
=====================================================
Supports multiple providers with automatic fallback chain.
Config loaded from ~/.config/factory/llm.yaml

Providers:
- anthropic: Claude via `claude` CLI (Opus 4.5 for Brain)
- minimax: MiniMax M2.5 via API (Wiggums)
- local: GLM-4.7-Flash via mlx_lm.server (fallback, Apple Silicon)

Usage:
    from core.llm_client import LLMClient, get_client

    client = get_client()
    response = await client.query("prompt", role="brain")
    response = await client.query("prompt", role="wiggum")
"""

import asyncio
import aiohttp
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

from core.subprocess_util import run_subprocess_exec, run_subprocess_streaming
from core.log import get_logger

# Directories
CONFIG_DIR = Path.home() / ".config" / "factory"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "llm.yaml"

_llm_logger = get_logger("llm")


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    _llm_logger.log(msg, level)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ProviderConfig:
    """Single provider configuration"""
    name: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    models: Dict[str, str] = field(default_factory=dict)
    timeout: int = 180

    def get_api_key(self) -> Optional[str]:
        """Get API key from environment variable"""
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        # Default env var names (only used providers)
        defaults = {
            "anthropic": "ANTHROPIC_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "local": None,  # Local mlx_lm doesn't need API key
        }
        env_var = defaults.get(self.name)
        return os.environ.get(env_var) if env_var else None


@dataclass
class LLMConfig:
    """Full LLM configuration"""
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    brain_provider: str = "anthropic/opus"
    wiggum_provider: str = "minimax/m2.5"
    fallback_chain: List[str] = field(default_factory=lambda: ["minimax/m2.5", "minimax/m2.1", "local/qwen"])


def _load_config(path: Path = None) -> LLMConfig:
    """Load LLM configuration from YAML file"""
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        log(f"Config not found at {config_path}, using defaults", "WARN")
        return _default_config()

    if not YAML_AVAILABLE:
        log("PyYAML not installed, using defaults", "WARN")
        return _default_config()

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)

        providers = {}
        for name, pconfig in raw.get("providers", {}).items():
            providers[name] = ProviderConfig(
                name=name,
                base_url=pconfig.get("base_url"),
                api_key_env=pconfig.get("api_key_env"),
                models=pconfig.get("models", {}),
                timeout=pconfig.get("timeout", 180),
            )

        defaults = raw.get("defaults", {})
        return LLMConfig(
            providers=providers,
            brain_provider=defaults.get("brain", "anthropic/opus"),
            wiggum_provider=defaults.get("wiggum", "minimax/m2.5"),
            fallback_chain=defaults.get("fallback_chain", ["minimax/m2.5", "minimax/m2.1", "local/qwen"]),
        )
    except Exception as e:
        log(f"Error loading config: {e}", "ERROR")
        return _default_config()


def _default_config() -> LLMConfig:
    """Return sensible defaults"""
    return LLMConfig(
        providers={
            "anthropic": ProviderConfig(
                name="anthropic",
                models={"opus": "claude-opus-4-5-20251101", "sonnet": "claude-sonnet-4-20250514"},
            ),
            "minimax": ProviderConfig(
                name="minimax",
                base_url="https://api.minimax.io/anthropic/v1",
                models={"m2.5": "MiniMax-M2.5", "m2.1": "MiniMax-M2.1"},
                timeout=180,
            ),
            "local": ProviderConfig(
                name="local",
                base_url="http://localhost:8002/v1",
                models={"glm": "mlx-community/GLM-4.7-Flash-4bit"},
                timeout=300,
            ),
        },
        brain_provider="anthropic/opus",
        wiggum_provider="minimax/m2.5",
        fallback_chain=["minimax/m2.5", "minimax/m2.1", "local/glm"],
    )


# ============================================================================
# LLM CLIENT
# ============================================================================

class LLMClient:
    """
    Unified LLM client with fallback chain support.

    Roles:
    - "brain": Claude Opus 4.5 via claude CLI (heavy analysis, vision)
    - "wiggum": MiniMax M2.5 via API (code generation, TDD)
    - "sub": Local GLM-4.7-Flash via mlx_lm (fast iteration, fallback)

    Direct provider access:
    - "anthropic/opus", "minimax/m2.5", "minimax/m2.1", "local/glm"
    """

    def __init__(self, config: LLMConfig = None):
        self.config = config or _load_config()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _resolve_provider(self, role_or_provider: str) -> Tuple[str, str]:
        """
        Resolve role or provider string to (provider_name, model_id).

        Args:
            role_or_provider: "brain", "wiggum", "sub", or "provider/model"

        Returns:
            Tuple of (provider_name, model_id)
        """
        # Role aliases
        role_map = {
            "brain": self.config.brain_provider,
            "wiggum": self.config.wiggum_provider,
            "sub": "local/glm",
        }

        provider_str = role_map.get(role_or_provider, role_or_provider)

        if "/" in provider_str:
            parts = provider_str.split("/", 1)
            return parts[0], parts[1]
        else:
            # Just provider name, use first model
            provider = self.config.providers.get(provider_str)
            if provider and provider.models:
                first_model = list(provider.models.keys())[0]
                return provider_str, first_model
            return provider_str, "default"

    async def query(
        self,
        prompt: str,
        role: str = "wiggum",
        max_tokens: int = 32000,  # No artificial limit - let model produce full response
        temperature: float = 0.3,
        use_fallback: bool = True,
    ) -> str:
        """
        Query LLM with automatic provider routing and fallback.

        Args:
            prompt: The prompt to send
            role: "brain", "wiggum", "sub", or "provider/model"
            max_tokens: Max tokens for response
            temperature: Sampling temperature
            use_fallback: Whether to use fallback chain on failure

        Returns:
            LLM response text
        """
        provider_name, model_alias = self._resolve_provider(role)

        # Try primary provider
        result = await self._call_provider(
            provider_name, model_alias, prompt, max_tokens, temperature
        )

        if result is not None:
            return result

        # Fallback chain
        if use_fallback:
            for fallback in self.config.fallback_chain:
                if fallback != f"{provider_name}/{model_alias}":
                    fb_provider, fb_model = self._resolve_provider(fallback)
                    log(f"Fallback to {fb_provider}/{fb_model}", "WARN")
                    result = await self._call_provider(
                        fb_provider, fb_model, prompt, max_tokens, temperature
                    )
                    if result is not None:
                        return result

        return "Error: All LLM providers failed"

    async def _call_provider(
        self,
        provider_name: str,
        model_alias: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[str]:
        """Call a specific provider"""
        provider = self.config.providers.get(provider_name)
        if not provider:
            log(f"Unknown provider: {provider_name}", "ERROR")
            return None

        # Get actual model ID
        model_id = provider.models.get(model_alias, model_alias)

        # Route to appropriate backend
        if provider_name == "anthropic":
            return await self._call_claude_cli(model_id, prompt, max_tokens)
        elif provider.base_url:
            if "anthropic" in provider.base_url:
                return await self._call_anthropic_api(provider, model_id, prompt, max_tokens)
            else:
                return await self._call_local_api(provider, model_id, prompt, max_tokens, temperature)
        else:
            log(f"No base_url for provider {provider_name}", "ERROR")
            return None

    async def _call_claude_cli(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> Optional[str]:
        """
        Call Claude via `claude` CLI.
        Used for: Brain analysis, vision, LEAN reasoning.
        """
        log(f"Calling Claude CLI ({model})...")

        try:
            rc, stdout, stderr = await run_subprocess_exec(
                ["claude", "-p", "--model", model, "--max-turns", "3"],
                timeout=600,
                stdin_data=prompt.encode(),
                log_fn=log,
                register_pgroup=True,
            )

            if rc == -1:  # timeout
                log("Claude CLI timeout (10min) - killed process group", "ERROR")
                return None
            if rc == 0:
                response = stdout.strip()
                log(f"Claude CLI response: {len(response)} chars")
                return response
            else:
                log(f"Claude CLI error: {stderr[:500]}", "ERROR")
                return None
        except FileNotFoundError:
            log("claude CLI not found - install with: npm i -g @anthropic-ai/claude-code", "ERROR")
            return None
        except Exception as e:
            log(f"Claude CLI exception: {e}", "ERROR")
            return None

    async def _call_anthropic_api(
        self,
        provider: ProviderConfig,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> Optional[str]:
        """
        Call Anthropic-compatible API (MiniMax, etc.).
        Used for: Wiggum code generation, TDD iterations.
        """
        api_key = provider.get_api_key()
        if not api_key:
            log(f"No API key for {provider.name} (set {provider.api_key_env or provider.name.upper() + '_API_KEY'})", "ERROR")
            return None

        log(f"Calling {provider.name} API ({model})...")

        try:
            session = await self._get_session()
            async with session.post(
                f"{provider.base_url}/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=aiohttp.ClientTimeout(total=provider.timeout),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Anthropic format: content[0] may be thinking, content[1] is text
                    content = data.get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            if text:
                                log(f"{provider.name} response: {len(text)} chars")
                                return text
                    log(f"{provider.name}: no text in response", "WARN")
                    return None
                else:
                    error_text = await resp.text()
                    log(f"{provider.name} HTTP {resp.status}: {error_text[:200]}", "WARN")
                    return None
        except asyncio.TimeoutError:
            log(f"{provider.name} timeout ({provider.timeout}s)", "WARN")
            return None
        except Exception as e:
            log(f"{provider.name} exception: {e}", "WARN")
            return None

    async def _call_local_api(
        self,
        provider: ProviderConfig,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[str]:
        """
        Call OpenAI-compatible local API (mlx_lm.server with GLM-4.7-Flash).
        Used for: Fallback when MiniMax unavailable.
        NOT OpenAI cloud - just compatible API format.
        Start server: python -m mlx_lm.server --model mlx-community/GLM-4.7-Flash-4bit --port 8002
        """
        log(f"Calling {provider.name} API ({model})...")

        api_key = provider.get_api_key() or "not-needed"

        try:
            session = await self._get_session()
            async with session.post(
                f"{provider.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=aiohttp.ClientTimeout(total=provider.timeout),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if content:
                        log(f"{provider.name} response: {len(content)} chars")
                        return content
                    log(f"{provider.name}: empty response", "WARN")
                    return None
                else:
                    log(f"{provider.name} HTTP {resp.status}", "WARN")
                    return None
        except Exception as e:
            log(f"{provider.name} exception: {e}", "WARN")
            return None


# ============================================================================
# SINGLETON & CONVENIENCE
# ============================================================================

_client: Optional[LLMClient] = None


def get_client(config: LLMConfig = None) -> LLMClient:
    """Get or create singleton LLM client"""
    global _client
    if _client is None or config is not None:
        _client = LLMClient(config)
    return _client


async def query(prompt: str, role: str = "wiggum", **kwargs) -> str:
    """Convenience function for quick queries"""
    return await get_client().query(prompt, role, **kwargs)


def query_sync(prompt: str, role: str = "wiggum", **kwargs) -> str:
    """Synchronous query wrapper"""
    return asyncio.run(query(prompt, role, **kwargs))


# ============================================================================
# CLI TOOLS SUPPORT
# ============================================================================

# Fallback model chain for rate limits
FALLBACK_MODELS = [
    "minimax/MiniMax-M2.5",          # Primary (paid, fast, reasoning)
    "minimax/MiniMax-M2.1",          # Fallback1 (M2.1, cheaper)
    # Note: local/glm requires mlx_lm.server running (Apple Silicon only)
]


def ensure_mcp_server_running():
    """Check MCP server health and auto-restart if down."""
    import urllib.request
    import subprocess

    MCP_URL = "http://127.0.0.1:9500/health"

    try:
        req = urllib.request.Request(MCP_URL, method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return True  # Server is running
    except Exception:
        pass  # Server is down

    # Auto-restart MCP server
    log("MCP server down - auto-restarting...", "WARN")
    try:
        # Start daemon in background
        subprocess.Popen(
            ["python3", "-c",
             "from mcp_lrm.server_sse import start_daemon; start_daemon()"],
            cwd=str(Path(__file__).parent.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        import time
        time.sleep(2)  # Wait for startup

        # Verify it started
        try:
            req = urllib.request.Request(MCP_URL, method='GET')
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    log("MCP server auto-restarted successfully", "INFO")
                    return True
        except Exception:
            log("MCP server failed to restart", "ERROR")
            return False
    except Exception as e:
        log(f"Failed to auto-restart MCP server: {e}", "ERROR")
        return False


# ============================================================================
# GLOBAL CONCURRENCY LIMITER - Prevents memory explosion from too many opencode
# ============================================================================
_opencode_semaphore: Optional[asyncio.Semaphore] = None
_MAX_CONCURRENT_OPENCODE = 20  # Max 20 concurrent opencode processes system-wide

def _get_opencode_semaphore() -> asyncio.Semaphore:
    """Get or create global semaphore for opencode concurrency"""
    global _opencode_semaphore
    if _opencode_semaphore is None:
        _opencode_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_OPENCODE)
    return _opencode_semaphore


async def run_opencode(
    prompt: str,
    model: str = "minimax/MiniMax-M2.5",
    cwd: str = None,
    timeout: int = None,  # IGNORED - no timeout. Model runs until complete. Fallback only on RATE LIMIT.
    project: str = None,
    fallback: bool = True,
    project_env: Dict[str, str] = None,  # Project-specific env vars to set
    agent: str = None,  # Custom agent name (e.g., "tdd-scoped")
) -> Tuple[int, str]:
    """
    Run opencode CLI with fallback chain for rate limits.

    Fallback chain:
    1. MiniMax M2.5 (primary)
    2. MiniMax M2.1 (fallback)
    3. GLM-4.7 free (fallback)
    4. GPT-5 nano (fallback)

    Args:
        prompt: Task description
        model: Model in format "provider/model"
        cwd: Working directory
        timeout: IGNORED - no timeout, model runs until complete
        project: Project name for MCP LRM tools
        fallback: Enable fallback chain on error
        agent: Custom opencode agent name (from .opencode/agents/)

    Returns:
        Tuple of (returncode, output)
    """
    # CONCURRENCY LIMITER - Acquire semaphore to limit parallel opencode processes
    semaphore = _get_opencode_semaphore()
    async with semaphore:
        return await _run_opencode_impl(prompt, model, cwd, timeout, project, fallback, project_env, agent)


async def _run_opencode_impl(
    prompt: str,
    model: str = "minimax/MiniMax-M2.5",
    cwd: str = None,
    timeout: int = None,
    project: str = None,
    fallback: bool = True,
    project_env: Dict[str, str] = None,
    agent: str = None,
) -> Tuple[int, str]:
    """Internal implementation - runs under semaphore"""
    # Ensure MCP server is running before starting
    ensure_mcp_server_running()

    # Build model chain
    import os
    import signal

    if fallback:
        models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]
    else:
        models_to_try = [model]

    # Set environment with project for MCP LRM
    env = os.environ.copy()
    if project:
        env["FACTORY_PROJECT"] = project

    # Add project-specific environment variables
    if project_env:
        env.update(project_env)
        log(f"Added {len(project_env)} project env vars: {list(project_env.keys())}")

    last_error = ""
    for i, current_model in enumerate(models_to_try):
        is_fallback = i > 0
        if is_fallback:
            log(f"Fallback to {current_model}...", "WARN")

        log(f"Running opencode ({current_model})...")

        try:
            # Build command with variant for extended thinking
            cmd = [
                "opencode",
                "run",
                "-m", current_model,
                "--variant", "high",  # Enable extended thinking/reasoning
            ]
            # Add agent if specified (restricts tools)
            if agent:
                cmd.extend(["--agent", agent])
            cmd.append(prompt)

            # Use unified streaming subprocess with stuck/stale detection
            rc, output = await run_subprocess_streaming(
                cmd,
                timeout=900,  # 15 min max
                cwd=cwd,
                env=env,
                progress_interval=60,
                stuck_timeout=600,   # 10 min with 0 chars = rate limited
                stale_timeout=180,   # 3 min no new output = stuck
                log_fn=log,
            )

            # Handle stuck/stale → try fallback
            if rc == -2:  # stuck (0 chars)
                last_error = f"Stuck (0 output = rate limited)"
                log(f"STUCK ({current_model}) - triggering fallback", "WARN")
                # CRITICAL: Wait for process cleanup to complete before spawning fallback
                # This prevents race condition where new process spawns before old one is dead,
                # causing old process to be reparented to init (parent=1) as orphan.
                await asyncio.sleep(0.5)  # 500ms grace period for killpg() verification
                if i < len(models_to_try) - 1:
                    continue
                return 1, last_error
            if rc == -3:  # stale
                last_error = f"Stale (no new output after producing chars)"
                log(f"STALE ({current_model}) - triggering fallback", "WARN")
                # Same grace period for stale processes
                await asyncio.sleep(0.5)
                if i < len(models_to_try) - 1:
                    continue
                return 1, last_error
            if rc == -1:  # max timeout
                log(f"opencode MAX TIMEOUT ({current_model}) - killed process group", "ERROR")
                return 1, f"Error: max timeout (process stuck, not rate limited)"

            # Check for rate limit in output → fallback
            # Be STRICT: only trigger on actual API rate limit errors, not code containing "rate" or "limit"
            RATE_LIMIT_PATTERNS = [
                "rate_limit",           # API error type
                "rate limit exceeded",  # Common error message
                "too many requests",    # HTTP 429 message
                "requests per minute",  # Quota message
                "quota exceeded",       # Quota message
                '"type": "rate_limit"', # JSON error response
                "error code: 429",      # HTTP status in message
            ]

            def is_rate_limited(text: str) -> bool:
                """Strict rate limit detection - only API errors, not code mentioning 'rate'"""
                text_lower = text.lower()
                return any(pattern in text_lower for pattern in RATE_LIMIT_PATTERNS)

            if rc != 0:
                if is_rate_limited(output):
                    last_error = output
                    log(f"Rate limit detected ({current_model}), trying fallback...", "WARN")
                    if i < len(models_to_try) - 1:
                        continue  # Try fallback
                return rc, output

            # SUCCESS (rc == 0): never fallback on success output.
            # The generated code may contain "rate_limit" in variable names,
            # error handlers, or middleware code — not actual API rate limits.
            return rc, output

        except FileNotFoundError:
            log("opencode CLI not found", "ERROR")
            return 1, "Error: opencode not installed"
        except Exception as e:
            last_error = str(e)
            log(f"opencode exception: {e}", "ERROR")
            if i < len(models_to_try) - 1:
                continue  # Try fallback
            return 1, f"Error: {e}"

    return 1, f"Error: all models failed - {last_error}"


async def run_claude_agent(
    prompt: str,
    cwd: str = None,
    max_turns: int = 10,
    timeout: int = 1800,
    model: str = "claude-opus-4-5-20251101",
) -> Tuple[int, str]:
    """
    Run claude CLI in agent mode for complex tasks.

    Args:
        prompt: Task description
        cwd: Working directory
        max_turns: Max agent iterations
        timeout: Timeout in seconds
        model: Claude model (opus, sonnet, haiku)

    Returns:
        Tuple of (returncode, output)
    """
    log(f"Running Claude agent ({model}, max {max_turns} turns)...")

    try:
        rc, stdout, stderr = await run_subprocess_exec(
            ["claude", "-p", "--model", model, "--max-turns", str(max_turns),
             "--permission-mode", "acceptEdits"],
            timeout=timeout,
            cwd=cwd,
            stdin_data=prompt.encode(),
            log_fn=log,
            register_pgroup=True,
        )

        if rc == -1:  # timeout
            log(f"Claude agent timeout ({timeout}s)", "ERROR")
            return 1, f"Error: timeout after {timeout}s"

        return rc, stdout + stderr
    except FileNotFoundError:
        log("claude CLI not found", "ERROR")
        return 1, "Error: claude not installed"
    except Exception as e:
        log(f"Claude agent exception: {e}", "ERROR")
        return 1, f"Error: {e}"


async def run_claude_haiku(
    prompt: str,
    cwd: str = None,
    max_turns: int = 15,
    timeout: int = 900,
) -> Tuple[int, str]:
    """
    Run claude CLI with Haiku model for fast, cost-effective TDD tasks.
    """
    return await run_claude_agent(
        prompt=prompt,
        cwd=cwd,
        max_turns=max_turns,
        timeout=timeout,
        model="haiku",  # Claude Code accepts "haiku" as shorthand
    )


async def run_copilot_agent(
    prompt: str,
    cwd: str = None,
    model: str = "claude-sonnet-4.5",
    timeout: int = 1800,
) -> Tuple[int, str]:
    """
    Run GitHub Copilot CLI in agent mode for complex tasks.

    Args:
        prompt: Task description
        cwd: Working directory
        model: Model to use (claude-sonnet-4.5, claude-opus-4.5, etc.)
        timeout: Timeout in seconds

    Returns:
        Tuple of (returncode, output)
    """
    log(f"Running Copilot agent with {model}...")

    try:
        rc, stdout, stderr = await run_subprocess_exec(
            ["copilot", "--model", model, "-p", prompt,
             "--allow-all-tools", "--allow-all-paths"],
            timeout=timeout,
            cwd=cwd,
            log_fn=log,
            register_pgroup=True,
        )

        if rc == -1:  # timeout
            log(f"Copilot agent timeout ({timeout}s)", "ERROR")
            return 1, f"Error: timeout after {timeout}s"

        return rc, stdout + stderr
    except FileNotFoundError:
        log("copilot CLI not found", "ERROR")
        return 1, "Error: copilot not installed"
    except Exception as e:
        log(f"Copilot agent exception: {e}", "ERROR")
        return 1, f"Error: {e}"


# ============================================================================
# CONFIG TEMPLATE
# ============================================================================

CONFIG_TEMPLATE = """# Software Factory LLM Configuration
# ===================================
# Location: ~/.config/factory/llm.yaml

providers:
  anthropic:
    # API key via ANTHROPIC_API_KEY env var
    models:
      opus: claude-opus-4-5-20251101
      sonnet: claude-sonnet-4-20250514

  minimax:
    base_url: https://api.minimax.io/anthropic/v1
    # API key via MINIMAX_API_KEY env var
    models:
      m2.5: MiniMax-M2.5
    timeout: 180

  local:
    # Start: python -m mlx_lm.server --model mlx-community/GLM-4.7-Flash-4bit --port 8002
    base_url: http://localhost:8002/v1
    models:
      glm: mlx-community/GLM-4.7-Flash-4bit
    timeout: 300

defaults:
  brain: anthropic/opus      # Vision LEAN, orchestration
  wiggum: minimax/m2.5       # TDD workers
  fallback_chain:
    - minimax/m2.5
    - minimax/m2.1
    - local/glm
"""


def create_config_template(path: Path = None):
    """Create config template file"""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        print(f"Config already exists at {config_path}")
        return

    config_path.write_text(CONFIG_TEMPLATE)
    print(f"Created config template at {config_path}")
    print("Edit the file and set your API keys as environment variables.")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Software Factory LLM Client")
    parser.add_argument("--init", action="store_true", help="Create config template")
    parser.add_argument("--test", action="store_true", help="Test LLM providers")
    parser.add_argument("--role", type=str, default="wiggum", help="Role: brain, wiggum, sub")
    parser.add_argument("prompt", nargs="?", help="Prompt to send")

    args = parser.parse_args()

    if args.init:
        create_config_template()
    elif args.test:
        async def test():
            client = LLMClient()

            print("\n=== Testing LLM Providers ===")
            print(f"Brain: {client.config.brain_provider}")
            print(f"Wiggum: {client.config.wiggum_provider}")
            print(f"Fallback: {client.config.fallback_chain}")

            # Test local first (fast)
            print("\n--- Test local/qwen ---")
            response = await client.query("Say 'hello' in one word", role="sub", use_fallback=False)
            print(f"Response: {response[:200]}")

            # Test wiggum
            print("\n--- Test wiggum (MiniMax) ---")
            response = await client.query("Say 'hello' in one word", role="wiggum", use_fallback=False)
            print(f"Response: {response[:200]}")

            await client.close()
            print("\n✅ LLM Client ready")

        asyncio.run(test())
    elif args.prompt:
        async def run():
            response = await query(args.prompt, role=args.role)
            print(response)
        asyncio.run(run())
    else:
        parser.print_help()
