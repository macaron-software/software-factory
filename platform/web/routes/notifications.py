"""Web routes — In-app notifications (bell icon, list, mark-read)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...services.notification_service import get_notification_service
from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/notifications")
async def api_notifications(request: Request, limit: int = 30, unread_only: bool = False):
    """Return recent notifications + unread count."""
    store = get_notification_service()
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
    count = get_notification_service().count_unread()
    if count > 0:
        return HTMLResponse(f'<span class="notif-badge">{count if count < 100 else "99+"}</span>')
    return HTMLResponse("")


@router.post("/api/notifications/{nid}/read")
async def api_notification_mark_read(nid: str, request: Request):
    get_notification_service().mark_read(nid)
    return JSONResponse({"ok": True})


@router.post("/api/notifications/read-all")
async def api_notification_mark_all_read(request: Request):
    count = get_notification_service().mark_all_read()
    return JSONResponse({"ok": True, "marked": count})


@router.get("/api/notifications/dropdown")
async def api_notifications_dropdown(request: Request):
    """Return HTML partial for the notification dropdown."""
    store = get_notification_service()
    notifs = store.list_recent(limit=15)
    unread = store.count_unread()
    return _templates(request).TemplateResponse(
        "partials/notifications_dropdown.html",
        {"request": request, "notifications": notifs, "unread": unread},
    )


@router.get("/notifications")
async def notifications_page(request: Request):
    """Full notifications history page."""
    store = get_notification_service()
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
