"""
Software Factory - Configuration
=======================================
100% local platform. LLM providers: Anthropic, MiniMax, GLM, Azure Foundry.
Loads from ~/.config/factory/platform.yaml with env var overrides.

Secret management (priority order):
  1. Infisical vault  — if INFISICAL_TOKEN + INFISICAL_SITE_URL are set
  2. .env file        — fallback / local dev bootstrap
  3. os.environ       — always wins (shell overrides)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# Load .env first (provides bootstrap vars like INFISICAL_TOKEN for local dev)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _load_infisical() -> bool:
    """Inject secrets from Infisical vault into os.environ via REST API.

    Uses httpx (already a platform dependency) — no infisical SDK needed.

    Requires in environment (or minimal .env bootstrap):
      INFISICAL_TOKEN       — service token st.xxxx (mandatory)
      INFISICAL_SITE_URL    — self-hosted URL or https://app.infisical.com (default)
      INFISICAL_ENVIRONMENT — dev / staging / prod (default: prod)
      INFISICAL_PROJECT_ID  — Infisical project UUID (mandatory for REST API)
      INFISICAL_PATH        — secret path (default: /)

    Secrets are injected with setdefault → explicit env vars always win.
    Returns True if secrets were loaded, False if skipped/failed.
    """
    token = os.environ.get("INFISICAL_TOKEN")
    if not token:
        return False  # not configured — skip silently

    site_url = os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com").rstrip(
        "/"
    )
    environment = os.environ.get("INFISICAL_ENVIRONMENT", "prod")
    path = os.environ.get("INFISICAL_PATH", "/")
    project_id = os.environ.get("INFISICAL_PROJECT_ID", "")

    try:
        import httpx

        headers = {"Authorization": f"Bearer {token}"}
        params: dict = {"environment": environment, "secretPath": path}
        if project_id:
            params["workspaceId"] = project_id

        resp = httpx.get(
            f"{site_url}/api/v3/secrets/raw",
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        secrets = data.get("secrets", [])
        injected = 0
        for s in secrets:
            key = s.get("secretKey") or s.get("key", "")
            val = s.get("secretValue") or s.get("value", "")
            if key and key not in os.environ:
                os.environ[key] = val
                injected += 1
        log.info(
            "Infisical: loaded %d secrets (env=%s, path=%s)",
            injected,
            environment,
            path,
        )
        return True
    except Exception as e:
        log.warning("Infisical: failed to load secrets — %s (falling back to .env)", e)
    return False


# Inject vault secrets after .env bootstrap
_infisical_active = _load_infisical()

# Paths
PLATFORM_ROOT = Path(__file__).parent
FACTORY_ROOT = PLATFORM_ROOT.parent
DATA_DIR = FACTORY_ROOT / "data"
SKILLS_DIR = PLATFORM_ROOT / "skills" / "definitions"
LEGACY_SKILLS_DIR = FACTORY_ROOT / "skills"
CONFIG_PATH = Path.home() / ".config" / "factory" / "platform.yaml"

# Database
DB_PATH = DATA_DIR / "platform.db"


@dataclass
class LLMProviderConfig:
    """A single LLM provider."""

    id: str = ""
    name: str = ""
    base_url: str = ""
    api_key_env: str = ""  # env var name holding the key
    models: list = field(default_factory=list)
    default_model: str = ""
    enabled: bool = True


@dataclass
class LLMConfig:
    """All LLM providers."""

    providers: dict = field(
        default_factory=lambda: {
            "anthropic": LLMProviderConfig(
                id="anthropic",
                name="Anthropic",
                base_url="https://api.anthropic.com",
                api_key_env="ANTHROPIC_API_KEY",
                models=[
                    "claude-opus-4-5-20250520",
                    "claude-sonnet-4-20250514",
                    "claude-haiku-4-5-20250520",
                ],
                default_model="claude-sonnet-4-20250514",
            ),
            "minimax": LLMProviderConfig(
                id="minimax",
                name="MiniMax",
                base_url="https://api.minimax.chat/v1",
                api_key_env="MINIMAX_API_KEY",
                models=["MiniMax-M1-80k"],
                default_model="MiniMax-M1-80k",
            ),
            "glm": LLMProviderConfig(
                id="glm",
                name="Zhipu AI (GLM)",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key_env="GLM_API_KEY",
                models=["glm-4-plus", "glm-4-flash"],
                default_model="glm-4-flash",
            ),
            "azure": LLMProviderConfig(
                id="azure",
                name="Azure Foundry",
                base_url=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                api_key_env="AZURE_OPENAI_API_KEY",
                models=["gpt-5.2", "gpt-5.2-codex", "gpt-5.2-codex"],
                default_model="gpt-5.2",
                enabled=True,
            ),
        }
    )
    # Role → provider:model mapping
    role_defaults: dict = field(
        default_factory=lambda: {
            "brain": "anthropic:claude-opus-4-5-20250520",
            "worker": "azure:gpt-5.2-codex",
            "code_critic": "azure:gpt-5.2-codex",
            "security_critic": "glm:glm-4-flash",
            "arch_critic": "anthropic:claude-sonnet-4-20250514",
            "code_gen": "azure:gpt-5.2-codex",
        }
    )


@dataclass
class ServerConfig:
    """Web server configuration."""

    host: str = "127.0.0.1"
    port: int = 8090
    reload: bool = False
    workers: int = 1


@dataclass
class AgentConfig:
    """Agent runtime defaults."""

    max_concurrent_agents: int = 20
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    agent_timeout_sec: int = 300
    memory_window_size: int = 50


@dataclass
class A2AConfig:
    """Agent-to-Agent protocol configuration."""

    max_message_size: int = 100_000
    message_ttl_sec: int = 3600
    max_negotiation_rounds: int = 10
    consensus_type: str = "majority"
    veto_cooldown_sec: int = 60


@dataclass
class OrchestratorConfig:
    """Orchestration engine defaults."""

    default_pattern: str = "hierarchical"
    max_parallel_agents: int = 10
    max_loop_iterations: int = 20
    wip_limit: int = 15
    # Mission concurrency (auto-resume throttle)
    mission_semaphore: int = 2  # max concurrent missions
    resume_stagger_startup: float = 30.0  # seconds between launches on boot
    resume_stagger_watchdog: float = 10.0  # seconds between launches on watchdog
    resume_batch_startup: int = 3  # max missions launched per startup pass
    # CPU/RAM backpressure thresholds (%)
    cpu_green: float = 40.0  # below → launch freely
    cpu_yellow: float = 70.0  # 40-70 → slow down (2× stagger)
    cpu_red: float = 85.0  # above → skip this cycle
    ram_red: float = 85.0  # RAM % above → skip this cycle
    # Deployed-app container lifecycle
    max_active_projects: int = (
        3  # max projects with live deploy containers; 0 = unlimited
    )
    deployed_container_ttl_hours: float = (
        4.0  # stop macaron-app-* containers after N hours idle
    )
    # Worker nodes for multi-server dispatch (list of base URLs)
    worker_nodes: list = field(default_factory=list)
    # YOLO mode: auto-approve all human-in-the-loop checkpoints (no pause)
    yolo_mode: bool = False


@dataclass
class SecurityConfig:
    """Security & sandbox configuration."""

    # Landlock filesystem sandbox — restricts agent shell commands to workspace only
    landlock_enabled: bool = (
        True  # auto (enabled if binary found); set False to disable
    )


@dataclass
class PlatformConfig:
    """Root configuration object."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    a2a: A2AConfig = field(default_factory=A2AConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


def _apply_section(obj, raw: dict):
    """Apply dict values to a dataclass."""
    for k, v in raw.items():
        if hasattr(obj, k):
            setattr(obj, k, v)


def load_config() -> PlatformConfig:
    """Load platform config from YAML + env vars."""
    cfg = PlatformConfig()

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            raw = yaml.safe_load(f) or {}
        for section in ("server", "agents", "a2a", "orchestrator"):
            if section in raw:
                _apply_section(getattr(cfg, section), raw[section])
        if "llm" in raw:
            if "role_defaults" in raw["llm"]:
                cfg.llm.role_defaults.update(raw["llm"]["role_defaults"])

    # Env overrides
    if p := os.environ.get("PLATFORM_PORT"):
        cfg.server.port = int(p)
    if h := os.environ.get("PLATFORM_HOST"):
        cfg.server.host = h
    if y := os.environ.get("PLATFORM_YOLO_MODE"):
        cfg.orchestrator.yolo_mode = y.lower() in ("1", "true", "yes", "on")

    return cfg


_config: Optional[PlatformConfig] = None


def get_config() -> PlatformConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def save_config(cfg: "PlatformConfig") -> None:
    """Persist config to YAML and reload the singleton."""
    global _config
    import dataclasses

    def _to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        return obj

    raw = _to_dict(cfg)
    # Only persist the sections that make sense to save
    to_save = {
        k: raw[k] for k in ("server", "agents", "a2a", "orchestrator") if k in raw
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(to_save, f, default_flow_style=False, allow_unicode=True)
    _config = cfg
