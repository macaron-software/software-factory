#!/usr/bin/env python3
"""
LLM Client - Unified LLM access for Software Factory
=====================================================
Supports multiple providers with automatic fallback chain.
Config loaded from ~/.config/factory/llm.yaml

Providers:
- anthropic: Claude via `claude` CLI (Opus 4.5 for Brain)
- minimax: MiniMax M2.1 via API (Wiggums)
- local: Qwen local via llama-cpp API (fallback)

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


# Directories
CONFIG_DIR = Path.home() / ".config" / "factory"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "llm.yaml"


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [LLM] [{level}] {msg}", flush=True)


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
            "local": None,  # Local llama.cpp doesn't need API key
        }
        env_var = defaults.get(self.name)
        return os.environ.get(env_var) if env_var else None


@dataclass
class LLMConfig:
    """Full LLM configuration"""
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    brain_provider: str = "anthropic/opus"
    wiggum_provider: str = "minimax/m2.1"
    fallback_chain: List[str] = field(default_factory=lambda: ["minimax/m2.1", "local/qwen"])


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
            wiggum_provider=defaults.get("wiggum", "minimax/m2.1"),
            fallback_chain=defaults.get("fallback_chain", ["minimax/m2.1", "local/qwen"]),
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
                models={"m2.1": "MiniMax-M2.1"},
                timeout=180,
            ),
            "local": ProviderConfig(
                name="local",
                base_url="http://localhost:8002/v1",
                models={"qwen": "qwen3-30b-a3b"},
                timeout=300,
            ),
        },
        brain_provider="anthropic/opus",
        wiggum_provider="minimax/m2.1",
        fallback_chain=["minimax/m2.1", "local/qwen"],
    )


# ============================================================================
# LLM CLIENT
# ============================================================================

class LLMClient:
    """
    Unified LLM client with fallback chain support.

    Roles:
    - "brain": Claude Opus 4.5 via claude CLI (heavy analysis, vision)
    - "wiggum": MiniMax M2.1 via API (code generation, TDD)
    - "sub": Local Qwen via llama-cpp (fast iteration, fallback)

    Direct provider access:
    - "anthropic/opus", "minimax/m2.1", "local/qwen"
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
            "sub": "local/qwen",
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
        max_tokens: int = 4096,
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
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",  # Print mode (headless)
                "--model", model,
                "--max-turns", "3",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                start_new_session=True,  # Process group for cleanup
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode()),
                    timeout=600,  # 10 min timeout for heavy analysis
                )
            except asyncio.TimeoutError:
                import os
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
                log("Claude CLI timeout (10min) - killed process group", "ERROR")
                return None

            if proc.returncode == 0:
                response = stdout.decode().strip()
                log(f"Claude CLI response: {len(response)} chars")
                return response
            else:
                error = stderr.decode()[:500]
                log(f"Claude CLI error: {error}", "ERROR")
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
        Call OpenAI-compatible local API (llama.cpp, vLLM with Qwen).
        Used for: Fallback when MiniMax unavailable.
        NOT OpenAI cloud - just compatible API format.
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
    "minimax/MiniMax-M2.1",          # Primary (paid, fast)
    "opencode/glm-4.7-free",         # Fallback1 (free, capable)
    "minimax/MiniMax-M2",            # Fallback2 (free tier M2)
]


async def run_opencode(
    prompt: str,
    model: str = "minimax/MiniMax-M2.1",
    cwd: str = None,
    timeout: int = None,  # IGNORED - no timeout. Model runs until complete. Fallback only on RATE LIMIT.
    project: str = None,
    fallback: bool = True,
) -> Tuple[int, str]:
    """
    Run opencode CLI with fallback chain for rate limits.

    Fallback chain:
    1. MiniMax M2.1 (primary)
    2. MiniMax M2 (free, on rate limit)
    3. GLM-4.7 free (fallback)
    4. GPT-5 nano (fallback)

    Args:
        prompt: Task description
        model: Model in format "provider/model"
        cwd: Working directory
        timeout: IGNORED - no timeout, model runs until complete
        project: Project name for MCP LRM tools
        fallback: Enable fallback chain on error

    Returns:
        Tuple of (returncode, output)
    """
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

    last_error = ""
    for i, current_model in enumerate(models_to_try):
        is_fallback = i > 0
        if is_fallback:
            log(f"Fallback to {current_model}...", "WARN")

        log(f"Running opencode ({current_model})...")

        try:
            proc = await asyncio.create_subprocess_exec(
                "opencode",
                "run",
                "-m", current_model,
                prompt,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,  # Create process group for cleanup
            )

            # Max 30 min safety timeout - prevents infinite hangs
            # But don't fallback on timeout (model was working, just stuck)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
            except asyncio.TimeoutError:
                # Kill entire process group (opencode + all child processes)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Already dead
                await proc.wait()
                log(f"opencode MAX TIMEOUT 30min ({current_model}) - killed process group", "ERROR")
                return 1, "Error: max timeout 30min (process stuck, not rate limited)"
            output = stdout.decode() + stderr.decode()

            # Check for rate limit in output → fallback
            if proc.returncode != 0:
                if "rate" in output.lower() or "limit" in output.lower() or "429" in output:
                    last_error = output
                    log(f"Rate limit detected ({current_model}), trying fallback...", "WARN")
                    if i < len(models_to_try) - 1:
                        continue  # Try fallback
                return proc.returncode, output

            # Check for rate limit message in success output
            if "rate limit" in output.lower() or "too many requests" in output.lower():
                last_error = output
                log(f"Rate limit in output ({current_model}), trying fallback...", "WARN")
                if i < len(models_to_try) - 1:
                    continue  # Try fallback

            return proc.returncode, output

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
) -> Tuple[int, str]:
    """
    Run claude CLI in agent mode for complex tasks.

    Args:
        prompt: Task description
        cwd: Working directory
        max_turns: Max agent iterations
        timeout: Timeout in seconds

    Returns:
        Tuple of (returncode, output)
    """
    log(f"Running Claude agent (max {max_turns} turns)...")

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "--model", "claude-opus-4-5-20251101",
            "--max-turns", str(max_turns),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=timeout,
        )

        output = stdout.decode() + stderr.decode()
        return proc.returncode, output
    except FileNotFoundError:
        log("claude CLI not found", "ERROR")
        return 1, "Error: claude not installed"
    except asyncio.TimeoutError:
        log(f"Claude agent timeout ({timeout}s)", "ERROR")
        return 1, f"Error: timeout after {timeout}s"
    except Exception as e:
        log(f"Claude agent exception: {e}", "ERROR")
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
      m2.1: MiniMax-M2.1
    timeout: 180

  local:
    base_url: http://localhost:8002/v1
    models:
      qwen: qwen3-30b-a3b
    timeout: 300

defaults:
  brain: anthropic/opus      # Vision LEAN, orchestration
  wiggum: minimax/m2.1       # TDD workers
  fallback_chain:
    - minimax/m2.1
    - local/qwen
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
