"""Workspace routes — CRUD + UI for multi-tenant workspaces."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_db():
    from ...db.migrations import get_db

    return get_db()


def _row_to_dict(row) -> dict:
    return dict(row) if row else {}


def _list_workspaces(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT w.*, COUNT(wm.user_id) as member_count "
        "FROM workspaces w "
        "LEFT JOIN workspace_members wm ON w.id = wm.workspace_id "
        "GROUP BY w.id ORDER BY w.created_at"
    ).fetchall()
    return [dict(r) for r in rows]


# ── UI ───────────────────────────────────────────────────────────────────────


@router.get("/workspaces", response_class=HTMLResponse)
async def workspaces_page(request: Request):
    from .helpers import get_workspace_context

    conn = _get_db()
    try:
        workspaces = _list_workspaces(conn)
    finally:
        conn.close()
    ctx = get_workspace_context(request)
    return _templates(request).TemplateResponse(
        "workspaces.html",
        {
            "request": request,
            "page_title": "Workspaces",
            "workspaces": workspaces,
            **ctx,
        },
    )


# ── API ──────────────────────────────────────────────────────────────────────


@router.get("/api/workspaces/current")
async def api_workspace_current(request: Request):
    ws_id = getattr(request.state, "workspace_id", "default")
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = 'default'"
            ).fetchone()
    finally:
        conn.close()
    return JSONResponse(
        _row_to_dict(row)
        if row
        else {"id": "default", "name": "Default", "color": "#6366f1"}
    )


@router.get("/api/workspaces")
async def api_workspaces_list(request: Request):
    conn = _get_db()
    try:
        workspaces = _list_workspaces(conn)
    finally:
        conn.close()
    return JSONResponse(workspaces)


@router.post("/api/workspaces")
async def api_workspace_create(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or name.lower().replace(" ", "-")).strip()
    description = data.get("description", "")
    color = data.get("color", "#6366f1")
    if not name or not slug:
        return JSONResponse({"error": "name and slug required"}, status_code=400)
    ws_id = str(uuid.uuid4())
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO workspaces (id, name, slug, description, color) VALUES (?, ?, ?, ?, ?)",
            (ws_id, name, slug, description, color),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
    finally:
        conn.close()
    return JSONResponse(_row_to_dict(row), status_code=201)


@router.get("/api/workspaces/{ws_id}")
async def api_workspace_get(ws_id: str):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_row_to_dict(row))


@router.put("/api/workspaces/{ws_id}")
async def api_workspace_update(ws_id: str, request: Request):
    data = await request.json()
    fields = {
        k: v
        for k, v in data.items()
        if k in ("name", "slug", "description", "color", "settings")
    }
    if not fields:
        return JSONResponse({"error": "nothing to update"}, status_code=400)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [ws_id]
    conn = _get_db()
    try:
        conn.execute(f"UPDATE workspaces SET {set_clause} WHERE id = ?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_row_to_dict(row))


@router.delete("/api/workspaces/{ws_id}")
async def api_workspace_delete(ws_id: str):
    if ws_id == "default":
        return JSONResponse(
            {"error": "cannot delete default workspace"}, status_code=400
        )
    conn = _get_db()
    try:
        conn.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.post("/api/workspaces/{ws_id}/switch")
async def api_workspace_switch(ws_id: str):
    from fastapi.responses import Response

    response = Response(
        content=f'{{"ok": true, "workspace_id": "{ws_id}"}}',
        media_type="application/json",
    )
    response.set_cookie(
        "workspace_id", ws_id, max_age=60 * 60 * 24 * 30, samesite="lax"
    )
    return response
