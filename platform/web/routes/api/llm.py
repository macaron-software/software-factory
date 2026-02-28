"""LLM observability endpoints."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...schemas import LlmStatsResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Default routing config
_DEFAULT_ROUTING = {
    "reasoning_heavy": {"provider": "azure-ai", "model": "gpt-5.2"},
    "reasoning_light": {"provider": "azure-openai", "model": "gpt-5-mini"},
    "production_heavy": {"provider": "azure-ai", "model": "gpt-5.1-codex"},
    "production_light": {"provider": "azure-openai", "model": "gpt-5-mini"},
    "tasks_heavy": {"provider": "azure-openai", "model": "gpt-5-mini"},
    "tasks_light": {"provider": "azure-openai", "model": "gpt-5-mini"},
    "redaction_heavy": {"provider": "azure-ai", "model": "gpt-5.1-codex"},
    "redaction_light": {"provider": "azure-openai", "model": "gpt-5-mini"},
}


def _get_db():
    from ....db.migrations import get_db

    return get_db()


def _load_routing() -> dict:
    try:
        db = _get_db()
        row = db.execute(
            "SELECT value FROM session_state WHERE key='llm_routing'"
        ).fetchone()
        db.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return dict(_DEFAULT_ROUTING)


def _save_routing(routing: dict) -> None:
    db = _get_db()
    db.execute(
        "INSERT OR REPLACE INTO session_state (key, value) VALUES ('llm_routing', ?)",
        (json.dumps(routing),),
    )
    db.commit()
    db.close()


def _load_disabled_providers() -> set:
    """Load the set of manually disabled provider IDs from DB."""
    try:
        db = _get_db()
        row = db.execute(
            "SELECT value FROM session_state WHERE key='llm_disabled_providers'"
        ).fetchone()
        db.close()
        if row:
            return set(json.loads(row[0]))
    except Exception:
        pass
    return set()


def _save_disabled_providers(disabled: set) -> None:
    db = _get_db()
    db.execute(
        "INSERT OR REPLACE INTO session_state (key, value) VALUES ('llm_disabled_providers', ?)",
        (json.dumps(list(disabled)),),
    )
    db.commit()
    db.close()


def _builtin_providers() -> list[dict]:
    """Return status of all builtin LLM providers."""
    from ....llm.client import _PROVIDERS

    disabled = _load_disabled_providers()
    result = []
    for pid, pcfg in _PROVIDERS.items():
        key_env = pcfg.get("key_env", "")
        has_key = bool(os.environ.get(key_env, ""))
        result.append(
            {
                "id": pid,
                "name": pcfg.get("name", pid),
                "models": pcfg.get("models", []),
                "default_model": pcfg.get("default", pcfg.get("models", ["?"])[0]),
                "has_key": has_key,
                "manually_disabled": pid in disabled,
                "enabled": has_key and pid not in disabled,
            }
        )
    return result


@router.get("/api/llm/stats", responses={200: {"model": LlmStatsResponse}})
async def llm_stats(hours: int = 24, session_id: str = ""):
    """LLM usage statistics: calls, tokens, cost, by provider/agent."""
    from ....llm.observability import get_tracer

    return JSONResponse(get_tracer().stats(session_id=session_id, hours=hours))


@router.get("/api/llm/traces")
async def llm_traces(limit: int = 50, session_id: str = ""):
    """Recent LLM call traces."""
    from ....llm.observability import get_tracer

    return JSONResponse(get_tracer().recent(limit=limit, session_id=session_id))


@router.get("/api/llm/usage")
async def llm_usage_stats():
    """Get LLM usage aggregate (cost by day/phase/agent)."""
    try:
        from ....llm.client import get_llm_client

        client = get_llm_client()
        data = await client.aggregate_usage(days=7)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/llm/routing")
async def get_llm_routing():
    """Get current LLM routing config + provider status."""
    providers = _builtin_providers()
    # Build flat model list across enabled providers
    all_models = []
    for p in providers:
        for m in p["models"]:
            all_models.append(
                {
                    "value": f"{p['id']}::{m}",
                    "label": f"{p['name']} / {m}",
                    "provider": p["id"],
                    "model": m,
                    "enabled": p["enabled"],
                }
            )
    routing = _load_routing()
    return JSONResponse(
        {"ok": True, "providers": providers, "models": all_models, "routing": routing}
    )


@router.post("/api/llm/routing")
async def save_llm_routing(payload: dict):
    """Save LLM routing config."""
    try:
        routing = payload.get("routing", {})
        # Validate keys
        valid_keys = set(_DEFAULT_ROUTING.keys())
        routing = {k: v for k, v in routing.items() if k in valid_keys}
        _save_routing(routing)
        # Invalidate executor cache
        try:
            from ....agents.executor import _invalidate_routing_cache

            _invalidate_routing_cache()
        except Exception:
            pass
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/llm/providers/{provider_id}/toggle")
async def toggle_provider(provider_id: str):
    """Enable or disable a provider (independent of API key presence)."""
    try:
        providers = _builtin_providers()
        ids = {p["id"] for p in providers}
        if provider_id not in ids:
            return JSONResponse(
                {"ok": False, "error": "Unknown provider"}, status_code=404
            )
        disabled = _load_disabled_providers()
        if provider_id in disabled:
            disabled.discard(provider_id)
            now_enabled = True
        else:
            disabled.add(provider_id)
            now_enabled = False
        _save_disabled_providers(disabled)
        return JSONResponse(
            {"ok": True, "provider_id": provider_id, "enabled": now_enabled}
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
