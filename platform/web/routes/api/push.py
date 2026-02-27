"""Browser Web Push API — subscribe/unsubscribe and VAPID public key."""
import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ....services.notification_service import get_notification_service
from ....db.migrations import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_db_subscriptions() -> list[dict]:
    """Load all push subscriptions from SQLite."""
    db = get_db()
    try:
        db.execute(
            """CREATE TABLE IF NOT EXISTS push_subscriptions (
                endpoint TEXT PRIMARY KEY,
                subscription_json TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        db.commit()
        rows = db.execute("SELECT subscription_json FROM push_subscriptions").fetchall()
        return [json.loads(r["subscription_json"]) for r in rows]
    except Exception as e:
        logger.warning("push_subscriptions table error: %s", e)
        return []
    finally:
        db.close()


def _save_subscription(sub: dict) -> None:
    db = get_db()
    try:
        db.execute(
            """CREATE TABLE IF NOT EXISTS push_subscriptions (
                endpoint TEXT PRIMARY KEY,
                subscription_json TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        db.execute(
            "INSERT OR REPLACE INTO push_subscriptions (endpoint, subscription_json) VALUES (?,?)",
            (sub["endpoint"], json.dumps(sub)),
        )
        db.commit()
    except Exception as e:
        logger.warning("push save error: %s", e)
    finally:
        db.close()


def _delete_subscription(endpoint: str) -> None:
    db = get_db()
    try:
        db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


@router.get("/api/push/vapid-public-key")
async def get_vapid_public_key():
    """Return VAPID public key for browser push subscription."""
    key = os.environ.get("NOTIFY_VAPID_PUBLIC_KEY", "")
    return {"publicKey": key, "enabled": bool(key)}


@router.post("/api/push/subscribe")
async def subscribe_push(request: Request):
    """Register a browser push subscription."""
    try:
        sub = await request.json()
        if not sub.get("endpoint"):
            return JSONResponse({"error": "missing endpoint"}, status_code=400)
        svc = get_notification_service()
        svc.add_push_subscription(sub)
        _save_subscription(sub)
        return {"ok": True, "subscriptions": len(svc._push_subscriptions)}
    except Exception as e:
        logger.error("push subscribe error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/push/subscribe")
async def unsubscribe_push(request: Request):
    """Unregister a browser push subscription."""
    try:
        body = await request.json()
        endpoint = body.get("endpoint", "")
        svc = get_notification_service()
        svc.remove_push_subscription(endpoint)
        _delete_subscription(endpoint)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/push/status")
async def push_status():
    """Return push notification configuration status."""
    svc = get_notification_service()
    return {
        "browser_push": svc.has_browser_push,
        "whatsapp": svc.has_whatsapp,
        "slack": svc.has_slack,
        "email": svc.has_email,
        "webhook": svc.has_webhook,
        "push_subscriptions": len(svc._push_subscriptions),
        "vapid_public": os.environ.get("NOTIFY_VAPID_PUBLIC_KEY", "")[:20] + "…" if svc.has_browser_push else "",
    }
