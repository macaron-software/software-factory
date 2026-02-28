"""LLM routing — model/provider selection for agents.

Extracted from executor.py. Handles Darwin LLM Thompson Sampling + DB routing config
+ hardcoded role/tag fallbacks.

Public API:
  _route_provider(agent, tools, ...) → (provider, model)
  _invalidate_routing_cache()
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.store import AgentDef

logger = logging.getLogger(__name__)

# Provider for tool-calling agents (OpenAI models handle tools reliably)
TOOL_PROVIDER = "azure-openai"
TOOL_MODEL = "gpt-5-mini"
# Providers that support native function calling
TOOL_CAPABLE_PROVIDERS = {"azure-openai", "azure-ai", "openai"}

# Backward-compat aliases (executor.py used underscore-prefixed names)
_TOOL_PROVIDER = TOOL_PROVIDER
_TOOL_MODEL = TOOL_MODEL
_TOOL_CAPABLE_PROVIDERS = TOOL_CAPABLE_PROVIDERS

# Cheap-mode: tools that don't require strong reasoning — can use MiniMax to save cost
CHEAP_TOOLS = frozenset(
    {
        "memory_search",
        "memory_store",
        "memory_list",
        "list_files",
        "read_file",
        "grep",
        "find_files",
        "git_log",
        "git_status",
        "git_diff",
        "search_confluence",
        "lrm_search",
        "get_ticket",
        "list_tickets",
    }
)
# Provider/model to use for cheap (non-code) tasks
CHEAP_PROVIDER = "minimax"
CHEAP_MODEL = "MiniMax-M2.5"

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
    """Select (provider, model) using routing config + Darwin LLM Thompson Sampling.

    Priority:
    1. Darwin LLM Thompson Sampling (if multiple models tested for this agent×context)
    2. DB routing config (Settings → LLM tab)
    3. Hardcoded role/tag defaults
    Falls back to minimax on local dev (AZURE_DEPLOY unset).
    """
    import os

    if not os.environ.get("AZURE_DEPLOY", ""):
        return agent.provider, agent.model

    azure_ai_key = os.environ.get("AZURE_AI_API_KEY", "")
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
    light_cfg = routing.get(category_light, {})

    candidates: list[tuple[str, str]] = []
    if azure_ai_key:
        h_provider = heavy_cfg.get("provider", "azure-ai")
        h_model = heavy_cfg.get(
            "model",
            "gpt-5.2" if category_heavy == "reasoning_heavy" else "gpt-5.1-codex",
        )
        l_provider = light_cfg.get("provider", "azure-openai")
        l_model = light_cfg.get("model", "gpt-5-mini")
        candidates = [(h_model, h_provider), (l_model, l_provider)]
    else:
        candidates = [("gpt-5-mini", "azure-openai")]

    if pattern_id and azure_ai_key and len(candidates) > 1:
        try:
            from ..patterns.team_selector import LLMTeamSelector

            model, provider = LLMTeamSelector.select_model(
                agent_id=agent.id,
                pattern_id=pattern_id,
                technology=technology,
                phase_type=phase_type,
                candidate_models=candidates,
                mission_id=mission_id,
            )
            if model and model != "default":
                return provider, model
        except Exception as exc:
            logger.debug("LLMTeamSelector.select_model error: %s", exc)

    if heavy_cfg.get("provider") and azure_ai_key:
        return heavy_cfg["provider"], heavy_cfg.get("model", "gpt-5-mini")

    if role in _REASONING_ROLES or tags & _REASONING_TAGS:
        return (
            ("azure-ai", "gpt-5.2") if azure_ai_key else ("azure-openai", "gpt-5-mini")
        )
    if role in _CODE_ROLES or tags & _CODE_TAGS:
        return (
            ("azure-ai", "gpt-5.1-codex")
            if azure_ai_key
            else ("azure-openai", "gpt-5-mini")
        )
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
    """Route to the best provider+model using Darwin LLM Thompson Sampling + routing config.

    Priority:
    1. Cheap-mode: if last round only used cheap tools (memory_search, read_file…) → MiniMax
    2. Darwin LLM Thompson Sampling (same team, competing models)
    3. DB routing config (Settings → LLM tab)
    4. Hardcoded role/tag defaults (gpt-5.2 / gpt-5.1-codex / gpt-5-mini)
    Overrides: tool-calling → must use _TOOL_CAPABLE_PROVIDERS; high rejection → escalate
    """
    import os

    # Cheap-mode: route simple info-retrieval rounds to MiniMax to save cost
    if cheap_mode and os.environ.get("AZURE_DEPLOY", ""):
        return CHEAP_PROVIDER, CHEAP_MODEL

    best_provider, best_model = _select_model_for_agent(
        agent,
        technology=technology,
        phase_type=phase_type,
        pattern_id=pattern_id,
        mission_id=mission_id,
    )

    if tools and best_provider not in _TOOL_CAPABLE_PROVIDERS:
        return _TOOL_PROVIDER, _TOOL_MODEL

    if best_provider not in _TOOL_CAPABLE_PROVIDERS:
        try:
            from .selection import rejection_rate

            if rejection_rate(agent.id) > 0.40:
                logger.debug(
                    "Escalating %s to azure-openai (high rejection rate)", agent.id
                )
                return _TOOL_PROVIDER, _TOOL_MODEL
        except Exception:
            pass

    return best_provider, best_model


def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if "<|" not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub("", text)
    cleaned = re.sub(r"^functions\.\w+:\d+$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()
