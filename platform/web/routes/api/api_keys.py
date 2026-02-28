"""API Keys management — generate, list, revoke platform API keys."""

from __future__ import annotations
import hashlib
import secrets
from fastapi import APIRouter

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("")
async def list_api_keys():
    from ...db.migrations import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, key_prefix, workspace, permissions, rate_limit, is_active, created_at, last_used_at, expires_at FROM platform_api_keys ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return {"keys": [dict(r) for r in rows]}


@router.post("")
async def create_api_key(
    name: str,
    workspace: str = "default",
    rate_limit: int = 1000,
    permissions: str = '["read","write"]',
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
    conn.commit()
    conn.close()
    return {"id": key_id, "name": name, "key": raw_key, "key_prefix": raw_key[:8]}


@router.delete("/{key_id}")
async def revoke_api_key(key_id: str):
    from ...db.migrations import get_db

    conn = get_db()
    conn.execute("UPDATE platform_api_keys SET is_active=0 WHERE id=?", (key_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
