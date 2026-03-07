"""LLM routing — model/provider selection for agents.

One provider per environment — nothing hardcoded, everything from env/Settings DB.
Zero fallback — fail fast if the provider is unavailable.

  Azure prod   (AZURE_DEPLOY=1):  azure-openai
    reasoning/leadership → gpt-5.2
    code/tests           → gpt-5.2-codex
    small talk/default   → gpt-5-mini

  OVH demo     (PLATFORM_LLM_PROVIDER=minimax):  MiniMax-M2.5
  Local dev    (PLATFORM_LLM_PROVIDER=local-mlx): Qwen3.5-35B

  Settings DB (session_state key='llm_routing') overrides defaults per category.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.store import AgentDef

logger = logging.getLogger(__name__)

# Provider for tool-calling agents (OpenAI-compatible models)
TOOL_PROVIDER = os.environ.get("PLATFORM_LLM_PROVIDER", "azure-openai")
TOOL_MODEL = "gpt-5-mini"
# Providers that support native function calling
TOOL_CAPABLE_PROVIDERS = {"azure-openai", "azure-ai", "openai", "local-mlx", "ollama", "minimax"}

# Backward-compat aliases
_TOOL_PROVIDER = TOOL_PROVIDER
_TOOL_MODEL = TOOL_MODEL
_TOOL_CAPABLE_PROVIDERS = TOOL_CAPABLE_PROVIDERS

# Backward-compat — kept for executor.py import; cheap_mode is now a no-op (no downgrade)
CHEAP_TOOLS: frozenset[str] = frozenset()
CHEAP_PROVIDER = TOOL_PROVIDER
CHEAP_MODEL = TOOL_MODEL

# Multi-model routing — roles/tags → (provider, model)
_REASONING_ROLES = {
    "architect",
    "product_owner",
    "scrum_master",
    "tech_lead",
    "cto",
    "ceo",
}
_REASONING_TAGS = {
    "architecture",
    "reasoning",
    "leadership",
    "planning",
    "strategy",
    "analysis",
}
_CODE_ROLES = {
    "developer",
    "tester",
    "qa",
    "security",
    "devops",
    "data_engineer",
    "ml_engineer",
}
_CODE_TAGS = {
    "code",
    "coding",
    "test",
    "tests",
    "security",
    "refactor",
    "review",
    "ci",
    "cd",
    "devops",
}

# AC improvement-cycle agents — hardcoded routing (Azure only).
# These have generic role names that don't match _REASONING/_CODE_ROLES above.
_AC_AGENT_ROUTING: dict[str, tuple[str, str]] = {
    "ac-architect":   ("azure-openai", "gpt-5.2"),
    "ac-adversarial": ("azure-openai", "gpt-5.2"),
    "ac-coach":       ("azure-openai", "gpt-5.2"),
    "ac-codex":       ("azure-openai", "gpt-5.1-codex"),
    "ac-qa-agent":    ("azure-openai", "gpt-5.1"),
    "ac-cicd-agent":  ("azure-openai", "gpt-5.1"),
}

# Cache for routing config loaded from DB
_routing_cache: dict | None = None
_routing_cache_ts: float = 0.0
_ROUTING_CACHE_TTL = 60.0  # 1 min

# Regex to strip raw MiniMax/internal tool-call tokens from LLM output
_RAW_TOKEN_RE = re.compile(
    r"<\|(?:tool_calls_section_begin|tool_calls_section_end|tool_call_begin|tool_call_end|"
    r"tool_call_argument_begin|tool_call_argument_end|tool_sep|im_end|im_start)\|>"
)


def _invalidate_routing_cache() -> None:
    global _routing_cache, _routing_cache_ts
    _routing_cache = None
    _routing_cache_ts = 0.0


def _load_routing_config() -> dict:
    """Load LLM routing config from DB (cached 60s)."""
    import time

    global _routing_cache, _routing_cache_ts
    now = time.time()
    if _routing_cache is not None and (now - _routing_cache_ts) < _ROUTING_CACHE_TTL:
        return _routing_cache
    try:
        import json

        from ..db.migrations import get_db

        db = get_db()
        row = db.execute(
            "SELECT value FROM session_state WHERE key='llm_routing'"
        ).fetchone()
        db.close()
        if row:
            _routing_cache = json.loads(row[0])
            _routing_cache_ts = now
            return _routing_cache
    except Exception:
        pass
    _routing_cache = {}
    return {}


def _select_model_for_agent(
    agent: "AgentDef",
    technology: str = "generic",
    phase_type: str = "generic",
    pattern_id: str = "",
    mission_id: str | None = None,
) -> tuple[str, str]:
    """Select (provider, model) from Settings DB → role/tag defaults.

    Priority:
    1. DB routing config (Settings → LLM tab)
    2. Role/tag defaults

    Provider always comes from PLATFORM_LLM_PROVIDER env var.
    On Azure (AZURE_DEPLOY=1): model varies by agent role (gpt-5.2 / gpt-5.2-codex / gpt-5-mini).
    On OVH/local: single model from PLATFORM_LLM_MODEL.
    """
    prov = os.environ.get("PLATFORM_LLM_PROVIDER") or (
        "azure-openai" if os.environ.get("AZURE_OPENAI_API_KEY") else "minimax"
    )

    if not os.environ.get("AZURE_DEPLOY", ""):
        # OVH demo or local dev — single model, no per-role dispatch
        model = os.environ.get("PLATFORM_LLM_MODEL", "MiniMax-M2.5")
        return prov, model

    # AC improvement-cycle agents — hardcoded overrides (before role/tag dispatch)
    if agent.id in _AC_AGENT_ROUTING:
        return _AC_AGENT_ROUTING[agent.id]

    # Azure prod — route by agent role/tags, overridable via Settings DB
    role = (agent.role or "").lower().replace("-", "_").replace(" ", "_")
    tags = {t.lower() for t in (agent.tags or [])}

    if role in _REASONING_ROLES or tags & _REASONING_TAGS:
        category_heavy, category_light = "reasoning_heavy", "reasoning_light"
    elif role in _CODE_ROLES or tags & _CODE_TAGS:
        category_heavy, category_light = "production_heavy", "production_light"
    else:
        category_heavy, category_light = "tasks_heavy", "tasks_light"

    routing = _load_routing_config()
    heavy_cfg = routing.get(category_heavy, {})

    if heavy_cfg.get("provider"):
        return heavy_cfg["provider"], heavy_cfg.get("model", "gpt-5-mini")

    codex_model = os.environ.get("AZURE_CODEX_MODEL", "gpt-5.2-codex")
    if role in _REASONING_ROLES or tags & _REASONING_TAGS:
        return "azure-openai", "gpt-5.2"
    if role in _CODE_ROLES or tags & _CODE_TAGS:
        return "azure-openai", codex_model
    return "azure-openai", "gpt-5-mini"


def _route_provider(
    agent: "AgentDef",
    tools: list | None,
    technology: str = "generic",
    phase_type: str = "generic",
    pattern_id: str = "",
    mission_id: str | None = None,
    cheap_mode: bool = False,
) -> tuple[str, str]:
    """Route to provider+model from Settings DB → role/tag defaults.

    Priority:
    1. DB routing config (Settings → LLM tab)
    2. Role/tag defaults (gpt-5.2 / gpt-5.2-codex / gpt-5-mini on Azure)
    cheap_mode is ignored — no downgrade to cheaper provider.
    """

    best_provider, best_model = _select_model_for_agent(
        agent,
        technology=technology,
        phase_type=phase_type,
        pattern_id=pattern_id,
        mission_id=mission_id,
    )
    return best_provider, best_model


def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if "<|" not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub("", text)
    cleaned = re.sub(r"^functions\.\w+:\d+$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()
