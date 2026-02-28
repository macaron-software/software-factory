"""Tool Builder — no-code custom tool creation (HTTP, SQL, shell)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ...db.migrations import get_db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ── Pages ────────────────────────────────────────────────────────────────────


@router.get("/tool-builder", response_class=HTMLResponse)
async def tool_builder_page(request: Request):
    return templates.TemplateResponse(
        request, "tool_builder.html", {"page_title": "Tool Builder"}
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.get("/api/tools/custom")
async def list_custom_tools():
    db = get_db()
    rows = db.execute("SELECT * FROM custom_tools ORDER BY created_at DESC").fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/tools/custom")
async def create_custom_tool(request: Request):
    body = await request.json()
    tool_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO custom_tools (id, name, description, type, config, enabled) VALUES (?,?,?,?,?,1)",
        (
            tool_id,
            body.get("name", "Untitled"),
            body.get("description", ""),
            body.get("type", "http"),
            json.dumps(body.get("config", {})),
        ),
    )
    db.commit()
    return JSONResponse({"id": tool_id})


@router.put("/api/tools/custom/{tool_id}")
async def update_custom_tool(tool_id: str, request: Request):
    body = await request.json()
    db = get_db()
    db.execute(
        "UPDATE custom_tools SET name=?, description=?, type=?, config=?, enabled=?, "
        "updated_at=datetime('now') WHERE id=?",
        (
            body.get("name"),
            body.get("description", ""),
            body.get("type", "http"),
            json.dumps(body.get("config", {})),
            1 if body.get("enabled", True) else 0,
            tool_id,
        ),
    )
    db.commit()
    return JSONResponse({"ok": True})


@router.delete("/api/tools/custom/{tool_id}")
async def delete_custom_tool(tool_id: str):
    db = get_db()
    db.execute("DELETE FROM custom_tools WHERE id=?", (tool_id,))
    db.commit()
    return JSONResponse({"ok": True})


@router.post("/api/tools/custom/{tool_id}/toggle")
async def toggle_custom_tool(tool_id: str):
    db = get_db()
    db.execute("UPDATE custom_tools SET enabled = 1 - enabled WHERE id=?", (tool_id,))
    db.commit()
    row = db.execute(
        "SELECT enabled FROM custom_tools WHERE id=?", (tool_id,)
    ).fetchone()
    return JSONResponse({"enabled": bool(row["enabled"]) if row else False})


# ── Test execution ────────────────────────────────────────────────────────────


@router.post("/api/tools/custom/{tool_id}/test")
async def test_custom_tool(tool_id: str, request: Request):
    db = get_db()
    row = db.execute("SELECT * FROM custom_tools WHERE id=?", (tool_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "Tool not found"}, status_code=404)

    config = json.loads(row["config"]) if row["config"] else {}
    tool_type = row["type"]
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    try:
        if tool_type == "http":
            result = _test_http(config, body)
        elif tool_type == "sql":
            result = _test_sql(config)
        elif tool_type == "shell":
            result = _test_shell(config)
        else:
            result = {"error": f"Unknown tool type: {tool_type}"}
    except Exception as e:
        result = {"error": str(e)}

    return JSONResponse(result)


def _test_http(config: dict, body: dict) -> dict:
    url = config.get("url", "")
    if not url:
        return {"error": "No URL configured"}
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    payload = config.get("body_template", None)
    if payload and isinstance(payload, str):
        payload = json.loads(payload)

    with httpx.Client(timeout=10) as client:
        resp = client.request(method, url, headers=headers, json=payload or None)
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:2000],
        }


def _test_sql(config: dict) -> dict:
    query = config.get("query", "").strip()
    if not query:
        return {"error": "No query configured"}
    # Read-only guard
    if not query.lower().lstrip().startswith("select"):
        return {"error": "Only SELECT queries are allowed"}
    from ...db.migrations import DB_PATH

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchmany(50)
        return {"rows": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


def _test_shell(config: dict) -> dict:
    allow_list = config.get("allow_list", [])
    if not allow_list:
        return {"error": "Shell tools require an allow_list of permitted commands"}
    command = config.get("command", "").strip()
    if not command:
        return {"error": "No command configured"}
    # Validate command starts with an allowed prefix
    if not any(command.startswith(allowed) for allowed in allow_list):
        return {"error": f"Command not in allow_list: {allow_list}"}
    timeout = min(int(config.get("timeout_s", 5)), 30)
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:500],
        "returncode": result.returncode,
    }
