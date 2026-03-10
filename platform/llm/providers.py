"""LLM Provider registry — unified interface for Anthropic, MiniMax, GLM, Azure."""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
import logging
from dataclasses import dataclass
from typing import Optional

from ..config import get_config

logger = logging.getLogger(__name__)

# Azure model cache
_azure_cache: dict = {"models": [], "ts": 0.0}
_AZURE_CACHE_TTL = 300  # 5 minutes

_AZURE_FALLBACK_MODELS = [
    "gpt-5.1", "gpt-5.1-codex", "gpt-5.1-codex-mini",
    "DeepSeek-R1", "Phi-4", "Llama-3.3-70B", "Mistral-Large",
]


def _fetch_azure_models() -> list[str]:
    """Fetch available models from Azure Foundry, with 5-min cache."""
    now = time.time()
    if _azure_cache["models"] and (now - _azure_cache["ts"]) < _AZURE_CACHE_TTL:
        return _azure_cache["models"]

    cfg = get_config()
    endpoint = cfg.llm.providers["azure"].base_url.rstrip("/")
    api_key = os.environ.get(cfg.llm.providers["azure"].api_key_env, "")

    if not endpoint or not api_key:
        return _AZURE_FALLBACK_MODELS

    url = f"{endpoint}/openai/models?api-version=2024-10-21"
    req = urllib.request.Request(url, headers={
        "api-key": api_key,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        models = sorted({m["id"] for m in data.get("data", [])})
        if models:
            _azure_cache["models"] = models
            _azure_cache["ts"] = now
            return models
    except Exception as exc:
        logger.debug("Azure model fetch failed: %s", exc)

    return _AZURE_FALLBACK_MODELS


@dataclass
class ProviderInfo:
    """Info about an LLM provider."""
    id: str
    name: str
    models: list[str]
    default_model: str
    enabled: bool
    has_key: bool


def list_providers() -> list[ProviderInfo]:
    """List all configured LLM providers with availability status."""
    cfg = get_config()
    result = []
    for pid, pcfg in cfg.llm.providers.items():
        has_key = bool(os.environ.get(pcfg.api_key_env, ""))
        models = pcfg.models
        if pid == "azure" and has_key:
            models = _fetch_azure_models()
        result.append(ProviderInfo(
            id=pcfg.id,
            name=pcfg.name,
            models=models,
            default_model=pcfg.default_model,
            enabled=pcfg.enabled and has_key,
            has_key=has_key,
        ))
    return result


def get_provider(provider_id: str) -> Optional[ProviderInfo]:
    """Get a specific provider info."""
    for p in list_providers():
        if p.id == provider_id:
            return p
    return None


def get_all_models() -> list[dict]:
    """Get flat list of all available models across providers."""
    result = []
    for p in list_providers():
        for m in p.models:
            result.append({
                "provider": p.id,
                "provider_name": p.name,
                "model": m,
                "label": f"{p.name} — {m}",
                "enabled": p.enabled,
                "is_default": m == p.default_model,
            })
    return result
