"""API Keys management — generate, list, revoke platform API keys."""

from __future__ import annotations
import hashlib
import json
import secrets
from typing import List
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def check_scope(key_id: str, required_scope: str) -> bool:
    """Return True if the given key has the required scope."""
    try:
        from ...db.migrations import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM api_key_scopes WHERE key_id=? AND scope=?",
            (key_id, required_scope),
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def _get_key_id_from_request(request: Request) -> str | None:
    """Extract key_id from X-API-Key header (match by prefix)."""
    raw = request.headers.get("X-API-Key", "")
    if not raw:
        return None
    try:
        from ...db.migrations import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT id FROM platform_api_keys WHERE key_prefix=? AND is_active=1",
            (raw[:8],),
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except Exception:
        return None


@router.get("")
async def list_api_keys():
    from ...db.migrations import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, key_prefix, workspace, permissions, rate_limit, is_active, created_at, last_used_at, expires_at FROM platform_api_keys ORDER BY created_at DESC"
    ).fetchall()
    keys = []
    for r in rows:
        k = dict(r)
        scopes = conn.execute(
            "SELECT scope FROM api_key_scopes WHERE key_id=?", (k["id"],)
        ).fetchall()
        k["scopes"] = [s["scope"] for s in scopes]
        k["usage_count"] = (
            conn.execute(
                "SELECT COUNT(*) FROM api_key_usage WHERE key_id=?", (k["id"],)
            ).fetchone()[0]
            if _table_exists(conn, "api_key_usage")
            else 0
        )
        keys.append(k)
    conn.close()
    return {"keys": keys}


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


@router.post("")
async def create_api_key(
    request: Request,
    name: str,
    workspace: str = "default",
    rate_limit: int = 1000,
    permissions: str = '["read","write"]',
    scopes: str = '["read","write"]',
):
    import uuid
    from ...db.migrations import get_db

    raw_key = "sf_" + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)
    key_id = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO platform_api_keys (id, name, key_prefix, key_hash, workspace, permissions, rate_limit) VALUES (?,?,?,?,?,?,?)",
        (key_id, name, raw_key[:8], key_hash, workspace, permissions, rate_limit),
    )
    # Insert scopes
    try:
        scope_list: List[str] = (
            json.loads(scopes) if isinstance(scopes, str) else scopes
        )
    except Exception:
        scope_list = ["read", "write"]
    for s in scope_list:
        conn.execute(
            "INSERT OR IGNORE INTO api_key_scopes (key_id, scope) VALUES (?,?)",
            (key_id, s),
        )
    conn.commit()
    conn.close()
    return {
        "id": key_id,
        "name": name,
        "key": raw_key,
        "key_prefix": raw_key[:8],
        "scopes": scope_list,
    }


@router.delete("/{key_id}")
async def revoke_api_key(key_id: str, request: Request):
    """Revoke an API key. Requires admin scope."""
    caller_key_id = _get_key_id_from_request(request)
    if caller_key_id and not check_scope(caller_key_id, "admin"):
        raise HTTPException(status_code=403, detail="admin scope required")

    from ...db.migrations import get_db

    conn = get_db()
    conn.execute("UPDATE platform_api_keys SET is_active=0 WHERE id=?", (key_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
