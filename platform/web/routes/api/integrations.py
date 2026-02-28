"""Integrations CRUD, AI providers & Jira endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/integrations")
async def list_integrations():
    """List all integrations."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute("SELECT * FROM integrations ORDER BY name").fetchall()
        return JSONResponse([dict(r) for r in rows])
    finally:
        db.close()


@router.patch("/api/integrations/{integ_id}")
async def update_integration(integ_id: str, body: "IntegrationUpdate"):
    """Toggle or update integration config."""
    import json as _json
    from ....db.migrations import get_db
    from .input_models import IntegrationUpdate as _M  # noqa: F401

    db = get_db()
    try:
        if body.enabled is not None:
            db.execute(
                "UPDATE integrations SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (1 if body.enabled else 0, integ_id),
            )
        if body.config is not None:
            existing = db.execute(
                "SELECT config_json FROM integrations WHERE id=?", (integ_id,)
            ).fetchone()
            if existing:
                cfg = _json.loads(existing["config_json"] or "{}")
                cfg.update(body.config)
                db.execute(
                    "UPDATE integrations SET config_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (_json.dumps(cfg), integ_id),
                )
        db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


@router.post("/api/integrations/{integ_id}/test")
async def test_integration(integ_id: str):
    """Test integration connectivity."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM integrations WHERE id=?", (integ_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"ok": False, "error": "not found"}, 404)
        import json as _json

        cfg = _json.loads(row["config_json"] or "{}")
        url = cfg.get("url", "")
        if not url:
            db.execute(
                "UPDATE integrations SET status='error', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": False, "error": "no URL configured"})
        # Basic connectivity test
        try:
            import urllib.request

            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Macaron-Platform/1.0")
            token = cfg.get("api_token", "")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            urllib.request.urlopen(req, timeout=10)
            db.execute(
                "UPDATE integrations SET status='connected', last_sync=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": True})
        except Exception as e:
            db.execute(
                "UPDATE integrations SET status='error', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": False, "error": str(e)[:200]})
    finally:
        db.close()


@router.get("/api/ai-providers")
async def list_ai_providers():
    """List all custom AI providers."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, name, provider_type, base_url, default_model, enabled, created_at "
            "FROM custom_ai_providers ORDER BY name"
        ).fetchall()
        providers = [dict(r) for r in rows]
        return JSONResponse({"ok": True, "providers": providers})
    finally:
        db.close()


@router.post("/api/ai-providers")
async def create_ai_provider(request: Request):
    """Create a new custom AI provider."""
    import uuid

    from cryptography.fernet import Fernet

    from ....db.migrations import get_db

    body = await request.json()
    name = body.get("name", "").strip()
    provider_type = body.get("provider_type", "openai-compatible")
    base_url = body.get("base_url", "").strip()
    api_key = body.get("api_key", "").strip()
    default_model = body.get("default_model", "").strip()

    if not all([name, base_url, api_key, default_model]):
        return JSONResponse(
            {"ok": False, "error": "Missing required fields"}, status_code=400
        )

    # Encrypt API key
    encryption_key = os.environ.get("SF_ENCRYPTION_KEY")
    if not encryption_key:
        # Generate a key if not set (for development)
        encryption_key = Fernet.generate_key().decode()
        logger.warning(
            "SF_ENCRYPTION_KEY not set, using temporary key (not secure for production)"
        )

    fernet = Fernet(
        encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
    )
    encrypted_key = fernet.encrypt(api_key.encode()).decode()

    provider_id = str(uuid.uuid4())[:12]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO custom_ai_providers (id, name, provider_type, base_url, api_key_encrypted, default_model, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (provider_id, name, provider_type, base_url, encrypted_key, default_model),
        )
        db.commit()
        return JSONResponse({"ok": True, "id": provider_id})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        db.close()


@router.patch("/api/ai-providers/{provider_id}")
async def update_ai_provider(provider_id: str, request: Request):
    """Update a custom AI provider."""
    from cryptography.fernet import Fernet

    from ....db.migrations import get_db

    body = await request.json()
    db = get_db()

    try:
        updates = []
        params = []

        if "enabled" in body:
            updates.append("enabled = ?")
            params.append(1 if body["enabled"] else 0)

        if "name" in body:
            updates.append("name = ?")
            params.append(body["name"])

        if "base_url" in body:
            updates.append("base_url = ?")
            params.append(body["base_url"])

        if "default_model" in body:
            updates.append("default_model = ?")
            params.append(body["default_model"])

        if "api_key" in body and body["api_key"]:
            encryption_key = os.environ.get("SF_ENCRYPTION_KEY")
            if not encryption_key:
                encryption_key = Fernet.generate_key().decode()
            fernet = Fernet(
                encryption_key.encode()
                if isinstance(encryption_key, str)
                else encryption_key
            )
            encrypted_key = fernet.encrypt(body["api_key"].encode()).decode()
            updates.append("api_key_encrypted = ?")
            params.append(encrypted_key)

        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(provider_id)
            db.execute(
                f"UPDATE custom_ai_providers SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            db.commit()

        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        db.close()


@router.delete("/api/ai-providers/{provider_id}")
async def delete_ai_provider(provider_id: str):
    """Delete a custom AI provider."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        db.execute("DELETE FROM custom_ai_providers WHERE id = ?", (provider_id,))
        db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


@router.post("/api/ai-providers/{provider_id}/test")
async def test_ai_provider(provider_id: str):
    """Test connection to a custom AI provider."""
    import httpx
    from cryptography.fernet import Fernet

    from ....db.migrations import get_db

    db = get_db()
    try:
        row = db.execute(
            "SELECT base_url, api_key_encrypted, default_model FROM custom_ai_providers WHERE id = ?",
            (provider_id,),
        ).fetchone()

        if not row:
            return JSONResponse(
                {"ok": False, "error": "Provider not found"}, status_code=404
            )

        base_url = row[0]
        encrypted_key = row[1]
        model = row[2]

        # Decrypt API key
        encryption_key = os.environ.get("SF_ENCRYPTION_KEY")
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
        fernet = Fernet(
            encryption_key.encode()
            if isinstance(encryption_key, str)
            else encryption_key
        )
        api_key = fernet.decrypt(encrypted_key.encode()).decode()

        # Test API call
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5,
                },
            )

        if response.status_code == 200:
            return JSONResponse({"ok": True, "status": "connected"})
        return JSONResponse(
            {"ok": False, "error": f"HTTP {response.status_code}"}, status_code=500
        )

    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/jira/board")
async def jira_board(board_id: int = 8680):
    """Get issues from a Jira board."""
    from ....tools.jira_tools import jira_board_issues

    result = await jira_board_issues(board_id)
    return PlainTextResponse(result)


@router.get("/api/jira/search")
async def jira_search_api(jql: str = "project=LPDATA"):
    """Search Jira issues."""
    from ....tools.jira_tools import jira_search

    result = await jira_search(jql)
    return PlainTextResponse(result)


@router.post("/api/jira/sync/{mission_id}")
async def jira_sync_mission(mission_id: str, board_id: int = 8680):
    """Sync a mission's tasks/stories to Jira."""
    from ....tools.jira_tools import jira_sync_from_platform

    result = await jira_sync_from_platform(mission_id, board_id)
    return PlainTextResponse(result)


@router.post("/api/jira/kanban-sync")
async def jira_kanban_sync_api(direction: str = "both"):
    """Bidirectional kanban sync between Platform and Jira board."""
    from ....tools.jira_tools import jira_kanban_sync

    result = await jira_kanban_sync(direction)
    return PlainTextResponse(result)
