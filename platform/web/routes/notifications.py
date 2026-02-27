"""Web routes — In-app notifications (bell icon, list, mark-read)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...services.notifications import get_notification_store
from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/notifications")
async def api_notifications(request: Request, limit: int = 30, unread_only: bool = False):
    """Return recent notifications + unread count."""
    store = get_notification_store()
    notifs = store.list_recent(limit=limit, unread_only=unread_only)
    return JSONResponse({
        "unread": store.count_unread(),
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "url": n.url,
                "severity": n.severity,
                "source": n.source,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifs
        ],
    })


@router.get("/api/notifications/badge")
async def api_notifications_badge(request: Request):
    """Return just the unread count (for polling)."""
    count = get_notification_store().count_unread()
    if count > 0:
        return HTMLResponse(f'<span class="notif-badge">{count if count < 100 else "99+"}</span>')
    return HTMLResponse("")


@router.post("/api/notifications/{nid}/read")
async def api_notification_mark_read(nid: str, request: Request):
    get_notification_store().mark_read(nid)
    return JSONResponse({"ok": True})


@router.post("/api/notifications/read-all")
async def api_notification_mark_all_read(request: Request):
    count = get_notification_store().mark_all_read()
    return JSONResponse({"ok": True, "marked": count})


@router.get("/api/notifications/dropdown")
async def api_notifications_dropdown(request: Request):
    """Return HTML partial for the notification dropdown."""
    store = get_notification_store()
    notifs = store.list_recent(limit=15)
    unread = store.count_unread()
    return _templates(request).TemplateResponse(
        "partials/notifications_dropdown.html",
        {"request": request, "notifications": notifs, "unread": unread},
    )


@router.get("/notifications")
async def notifications_page(request: Request):
    """Full notifications history page."""
    store = get_notification_store()
    notifs = store.list_recent(limit=100)
    unread = store.count_unread()
    return _templates(request).TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "page_title": "Notifications",
            "notifications": notifs,
            "unread": unread,
        },
    )


@router.post("/api/notifications/test")
async def test_notification_channel(request: Request):
    """Test a notification channel with a sample payload."""
    from ...services.notification_service import get_notification_service, NotificationPayload
    import os

    try:
        body = await request.json()
    except Exception:
        body = {}

    channel = body.get("channel", "all")
    svc = get_notification_service()

    # Override URLs from body if provided (for UI-configured channels not yet in env)
    if body.get("slack_url"):
        svc.slack_webhook = body["slack_url"]
    if body.get("webhook_url"):
        svc.webhook_url = body["webhook_url"]

    payload = NotificationPayload(
        event="test",
        title="🧪 Test — Software Factory",
        message="Ceci est un test de notification. Si vous voyez ce message, le canal fonctionne !",
        project_id="test",
        severity="info",
        url=str(request.base_url),
    )

    try:
        if channel == "slack" and svc.has_slack:
            await svc._send_slack(payload)
        elif channel == "webhook" and svc.has_webhook:
            await svc._send_webhook(payload)
        elif channel == "whatsapp" and svc.has_whatsapp:
            await svc._send_whatsapp(payload)
        elif channel == "push" and svc.has_browser_push:
            await svc._send_browser_push(payload)
        elif channel == "all":
            await svc.notify(payload)
        else:
            return JSONResponse({"ok": False, "error": f"Canal '{channel}' non configuré. Vérifiez les variables d'environnement."})
        return JSONResponse({"ok": True, "message": f"Notification envoyée via {channel}"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
