"""Platform settings — configurable rate limits and budget caps."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()

_RATE_LIMIT_DEFAULTS: dict[str, tuple[str, str]] = {
    "rate_limit_usd_per_session": ("2.00", "Max USD spend per agent session"),
    "rate_limit_usd_per_hour": ("10.00", "Max USD spend per hour platform-wide"),
    "rate_limit_calls_per_min": ("60", "Max LLM calls per minute"),
    "rate_limit_enabled": ("true", "Whether rate limiting is active"),
}


def _ensure_defaults(db) -> None:
    """Seed missing default settings into platform_settings."""
    for key, (value, description) in _RATE_LIMIT_DEFAULTS.items():
        db.execute(
            "INSERT OR IGNORE INTO platform_settings (key, value, description) VALUES (?,?,?)",
            (key, value, description),
        )
    db.commit()


@router.get("/api/settings/rate-limits")
async def get_rate_limits(request: Request):
    from ....db.migrations import get_db

    db = get_db()
    try:
        _ensure_defaults(db)
        rows = db.execute(
            "SELECT key, value, description, updated_at FROM platform_settings"
            " WHERE key LIKE 'rate_limit_%' ORDER BY key"
        ).fetchall()
        return {"settings": [dict(r) for r in rows]}
    finally:
        db.close()


@router.put("/api/settings/rate-limits")
async def update_rate_limits(request: Request):
    from ....db.migrations import get_db

    body = await request.json()
    allowed_keys = set(_RATE_LIMIT_DEFAULTS.keys())
    updates = {k: str(v) for k, v in body.items() if k in allowed_keys}
    if not updates:
        return {"ok": False, "error": "No valid keys provided"}

    db = get_db()
    try:
        _ensure_defaults(db)
        for key, value in updates.items():
            db.execute(
                "UPDATE platform_settings SET value=?,"
                " updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE key=?",
                (value, key),
            )
        db.commit()
        logger.info("Rate-limit settings updated: %s", list(updates.keys()))
        return {"ok": True, "updated": list(updates.keys())}
    finally:
        db.close()
