"""Platform settings — configurable rate limits, budget caps, and AC quality thresholds."""

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

# AC quality thresholds — stored in platform_settings, read live by dashboard + platform
_AC_QUALITY_DEFAULTS: dict[str, tuple[str, str]] = {
    "ac_hardening_threshold": (
        "85",
        "Score min avant déclenchement du Hardening Sprint (0-100)",
    ),
    "ac_adversarial_warn": (
        "60",
        "Score adversarial en-dessous duquel on passe en warn (0-100)",
    ),
    "ac_adversarial_fail": (
        "40",
        "Score adversarial en-dessous duquel on passe en fail (0-100)",
    ),
    "ac_max_hardening_per_cycle": (
        "1",
        "Nombre max de sprints hardening consécutifs avant de forcer la progression",
    ),
    "ac_auto_hardening_enabled": (
        "true",
        "Activer le déclenchement automatique du Hardening Sprint",
    ),
}


def _ensure_defaults(db) -> None:
    """Seed missing default settings into platform_settings."""
    for key, (value, description) in {
        **_RATE_LIMIT_DEFAULTS,
        **_AC_QUALITY_DEFAULTS,
    }.items():
        db.execute(
            "INSERT OR IGNORE INTO platform_settings (key, value, description) VALUES (?,?,?)",
            (key, value, description),
        )
    db.commit()


def get_ac_quality_settings(db) -> dict:
    """Read AC quality thresholds from platform_settings. Returns dict with defaults if missing."""
    _ensure_defaults(db)
    rows = db.execute(
        "SELECT key, value FROM platform_settings WHERE key LIKE 'ac_%'"
    ).fetchall()
    result = {k: v for k, (v, _) in _AC_QUALITY_DEFAULTS.items()}  # defaults
    for r in rows:
        result[r["key"]] = r["value"]
    return result


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


@router.get("/api/settings/quality")
async def get_quality_settings(request: Request):
    """Get AC quality thresholds (live, from DB)."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        settings = get_ac_quality_settings(db)
        return {"ok": True, "settings": settings}
    finally:
        db.close()


@router.put("/api/settings/quality")
async def update_quality_settings(request: Request):
    """Update AC quality thresholds live — no restart needed."""
    from ....db.migrations import get_db

    body = await request.json()
    allowed_keys = set(_AC_QUALITY_DEFAULTS.keys())
    updates = {k: str(v) for k, v in body.items() if k in allowed_keys}
    if not updates:
        return {"ok": False, "error": "No valid keys provided"}

    db = get_db()
    try:
        _ensure_defaults(db)
        for key, value in updates.items():
            db.execute(
                "INSERT INTO platform_settings (key, value, description)"
                " VALUES (?,?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
                " updated_at=CURRENT_TIMESTAMP",
                (key, value, _AC_QUALITY_DEFAULTS[key][1]),
            )
        db.commit()
        logger.info("AC quality settings updated: %s", updates)
        return {"ok": True, "updated": updates}
    finally:
        db.close()
