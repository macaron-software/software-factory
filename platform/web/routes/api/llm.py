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


# Default routing derived from the active primary provider + fallback chain.
# WHY: hardcoding Azure defaults breaks local-mlx and opencode environments where
# azure-ai/azure-openai are not enabled — the selects would have no matching option.
# We pick defaults that actually match what's available in each deployment.
def _build_default_routing() -> dict:
    from ....llm.client import _PROVIDERS, _primary, _FALLBACK_CHAIN

    def _slot(provider_id: str, model: str) -> dict:
        return {"provider": provider_id, "model": model}

    p = _PROVIDERS.get(_primary, {})
    default_model = p.get("default") or (p.get("models") or [""])[0]

    # Azure prod: differentiate codex (heavy) vs gpt-5-mini (light)
    if _primary in ("azure-openai", "azure-ai"):
        az_openai = _PROVIDERS.get("azure-openai", {})
        az_ai = _PROVIDERS.get("azure-ai", {})
        codex = next(
            (
                m
                for m in az_ai.get("models", []) + az_openai.get("models", [])
                if "codex" in m
            ),
            az_openai.get("default", "gpt-5-mini"),
        )
        light = az_openai.get("default", "gpt-5-mini")
        heavy_prov = "azure-ai" if "azure-ai" in _FALLBACK_CHAIN else "azure-openai"
        heavy_model = (
            az_ai.get("default", "gpt-5.2") if heavy_prov == "azure-ai" else codex
        )
        return {
            "reasoning_heavy": _slot(heavy_prov, heavy_model),
            "reasoning_light": _slot("azure-openai", light),
            "production_heavy": _slot("azure-openai", codex),
            "production_light": _slot("azure-openai", light),
            "tasks_heavy": _slot("azure-openai", light),
            "tasks_light": _slot("azure-openai", light),
            "redaction_heavy": _slot("azure-openai", codex),
            "redaction_light": _slot("azure-openai", light),
        }

    # All other envs (local-mlx, opencode, minimax, …): same model everywhere as starting point
    return {
        key: _slot(_primary, default_model)
        for key in (
            "reasoning_heavy",
            "reasoning_light",
            "production_heavy",
            "production_light",
            "tasks_heavy",
            "tasks_light",
            "redaction_heavy",
            "redaction_light",
        )
    }


_DEFAULT_ROUTING = _build_default_routing()


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
        key_env = pcfg.get("key_env") or ""
        no_auth = pcfg.get("no_auth", False)
        has_key = no_auth or bool(os.environ.get(key_env, "") if key_env else False)
        result.append(
            {
                "id": pid,
                "name": pcfg.get("name", pid),
                "models": pcfg.get("models", []),
                "default_model": pcfg.get("default") or (pcfg.get("models") or [""])[0],
                "has_key": has_key,
                "no_auth": no_auth,
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
        {"ok": True, "providers": providers, "models": all_models, "routing": routing},
        headers={"Cache-Control": "no-store"},
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


@router.post("/api/llm/routing/reset")
async def reset_llm_routing():
    """Reset routing to current auto-detected defaults (primary provider)."""
    try:
        db = _get_db()
        db.execute("DELETE FROM session_state WHERE key='llm_routing'")
        db.commit()
        db.close()
        try:
            from ....agents.executor import _invalidate_routing_cache

            _invalidate_routing_cache()
        except Exception:
            pass
        return JSONResponse({"ok": True, "routing": _DEFAULT_ROUTING})
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


@router.get("/api/llm/providers/{provider_id}/models")
async def get_provider_models_live(provider_id: str):
    """Fetch available models for a provider live from its API.

    WHY: Azure Foundry, ollama, opencode go and local-mlx all expose a model
    discovery endpoint. Polling it lets Settings show the real available models
    instead of the static list in _PROVIDERS. This is especially useful when
    new deployments are added to Azure without updating the code.
    Supported: azure-ai (GET /openai/models), azure-openai (GET /openai/deployments),
    ollama (GET /api/tags), local-mlx / opencode (GET /v1/models OpenAI-compat).
    """
    import asyncio
    import json as _json
    import urllib.request
    import urllib.error

    from ....llm.client import _PROVIDERS

    pcfg = _PROVIDERS.get(provider_id)
    if not pcfg:
        return JSONResponse({"ok": False, "error": "Unknown provider"}, status_code=404)

    loop = asyncio.get_event_loop()

    def _fetch():
        base = pcfg.get("base_url", "").rstrip("/")
        key_env = pcfg.get("key_env") or ""
        api_key = os.environ.get(key_env, "") if key_env else ""
        if not api_key:
            # Try ~/.config/factory/<name>.key
            name = key_env.replace("_API_KEY", "").replace("_", "-").lower()
            try:
                api_key = (
                    open(os.path.expanduser(f"~/.config/factory/{name}.key"))
                    .read()
                    .strip()
                )
            except OSError:
                pass

        headers = {"Content-Type": "application/json"}
        if api_key and not pcfg.get("no_auth"):
            prefix = pcfg.get("auth_prefix", "Bearer ")
            headers[pcfg.get("auth_header", "Authorization")] = f"{prefix}{api_key}"

        if provider_id == "azure-ai":
            # Azure AI Foundry: list models from the inference service
            api_ver = pcfg.get("azure_api_version", "2024-10-21")
            url = f"{base}/openai/models?api-version={api_ver}"
            if api_key:
                headers = {"api-key": api_key, "Content-Type": "application/json"}
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = _json.loads(resp.read())
                return sorted({m["id"] for m in data.get("data", [])})
            except Exception as e:
                logger.warning("azure-ai model fetch: %s", e)
                return pcfg.get("models", [])

        if provider_id == "azure-openai":
            # Azure OpenAI: list deployed models (deployments endpoint)
            api_ver = pcfg.get("azure_api_version", "2024-10-21")
            url = f"{base}/openai/deployments?api-version={api_ver}"
            if api_key:
                headers = {"api-key": api_key, "Content-Type": "application/json"}
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = _json.loads(resp.read())
                # deployment.properties.model.name → model id
                models = []
                for d in data.get("value", []):
                    mid = (
                        d.get("properties", {}).get("model", {}).get("name")
                        or d.get("model", {}).get("name")
                        or d.get("id", "")
                    )
                    if mid:
                        models.append(mid)
                return sorted(set(models)) or pcfg.get("models", [])
            except Exception as e:
                logger.warning("azure-openai deployments fetch: %s", e)
                return pcfg.get("models", [])

        if provider_id == "ollama":
            # Ollama native tags API (GET /api/tags on the non-/v1 base)
            ollama_base = base.rstrip("/v1").rstrip("/")
            url = f"{ollama_base}/api/tags"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url), timeout=4
                ) as resp:
                    data = _json.loads(resp.read())
                return [m["name"] for m in data.get("models", [])]
            except Exception as e:
                logger.warning("ollama tags fetch: %s", e)
                return pcfg.get("models", [])

        # Generic OpenAI-compatible /v1/models (local-mlx, opencode, etc.)
        url = f"{base}/models"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read())
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning("%s model fetch: %s", provider_id, e)
            return pcfg.get("models", [])

    try:
        models = await loop.run_in_executor(None, _fetch)
        return JSONResponse({"ok": True, "provider_id": provider_id, "models": models})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/llm/local/ensure")
async def ensure_local_server():
    """Ensure the local LLM server (local-mlx) is running, starting it if needed.

    Runs _ensure_mlx_server() in a thread (it blocks during startup wait).
    Returns: {ok, status: 'running'|'started'|'failed'|'disabled', url, models}
    """
    import asyncio
    import urllib.request

    from ....llm.client import _env_flag

    # Re-read from env in case it was changed at runtime
    enabled = _env_flag("LOCAL_MLX_ENABLED")
    if not enabled:
        return JSONResponse(
            {
                "ok": True,
                "status": "disabled",
                "message": "LOCAL_MLX_ENABLED is not set",
            }
        )

    mlx_url = os.environ.get("LOCAL_MLX_URL", "http://localhost:8080/v1")

    def _check_up() -> bool:
        try:
            urllib.request.urlopen(f"{mlx_url}/models", timeout=5)
            return True
        except Exception:
            return False

    def _get_models() -> list:
        import json as _json

        try:
            with urllib.request.urlopen(f"{mlx_url}/models", timeout=5) as r:
                return [m["id"] for m in _json.loads(r.read()).get("data", [])]
        except Exception:
            return []

    loop = asyncio.get_event_loop()

    # Already up?
    already_up = await loop.run_in_executor(None, _check_up)
    if already_up:
        models = await loop.run_in_executor(None, _get_models)
        return JSONResponse(
            {"ok": True, "status": "running", "url": mlx_url, "models": models}
        )

    # Start it
    from ....llm.client import _ensure_mlx_server

    await loop.run_in_executor(None, _ensure_mlx_server)

    # Check again
    now_up = await loop.run_in_executor(None, _check_up)
    if now_up:
        models = await loop.run_in_executor(None, _get_models)
        return JSONResponse(
            {"ok": True, "status": "started", "url": mlx_url, "models": models}
        )

    return JSONResponse(
        {
            "ok": False,
            "status": "failed",
            "url": mlx_url,
            "message": f"Server did not respond on {mlx_url} after startup attempt",
        },
        status_code=503,
    )


@router.get("/api/tools/thompson")
async def tool_thompson_stats_endpoint():
    """Thompson Sampling stats for search tool selection (code_search vs mcp_cocoindex_search)."""
    try:
        from ....llm.tool_thompson import tool_thompson_stats
        stats = tool_thompson_stats()
        # Group by context_type
        grouped: dict[str, list] = {}
        for arm in stats:
            ct = arm["context_type"]
            grouped.setdefault(ct, []).append(arm)
        return JSONResponse({
            "ok": True,
            "arms": stats,
            "by_context": grouped,
            "total_arms": len(stats),
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
