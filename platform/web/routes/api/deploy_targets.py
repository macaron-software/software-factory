"""Deploy Targets CRUD API."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/deploy-targets")
async def list_deploy_targets():
    """Return all deploy targets (DB + builtin docker-local)."""
    from ....tools.deploy.registry import list_targets
    return JSONResponse(list_targets())


@router.get("/api/deploy-targets/drivers")
async def list_drivers():
    """Return available driver types with their config schemas."""
    from ....tools.deploy.registry import available_drivers
    return JSONResponse(available_drivers())


@router.post("/api/deploy-targets")
async def create_deploy_target(request: Request):
    """Create a new deploy target."""
    from ....db.migrations import get_db
    body = await request.json()
    name = (body.get("name") or "").strip()
    driver = (body.get("driver") or "").strip()
    if not name or not driver:
        return JSONResponse({"error": "name and driver are required"}, status_code=400)

    config = body.get("config") or {}
    if isinstance(config, str):
        config = json.loads(config)

    tid = str(uuid.uuid4())
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO deploy_targets (id, name, driver, config_json, status)
            VALUES (?, ?, ?, ?, 'unknown')
            """,
            (tid, name, driver, json.dumps(config)),
        )
        db.commit()
        return JSONResponse({"id": tid, "name": name, "driver": driver, "status": "unknown"}, status_code=201)
    except Exception as e:
        if "UNIQUE" in str(e) or "unique" in str(e):
            return JSONResponse({"error": f"Name '{name}' already exists"}, status_code=409)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.put("/api/deploy-targets/{target_id}")
async def update_deploy_target(target_id: str, request: Request):
    """Update an existing deploy target."""
    from ....db.migrations import get_db
    body = await request.json()
    config = body.get("config") or {}
    if isinstance(config, str):
        config = json.loads(config)

    db = get_db()
    try:
        db.execute(
            """
            UPDATE deploy_targets SET
                name = COALESCE(?, name),
                driver = COALESCE(?, driver),
                config_json = ?,
                status = 'unknown',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (body.get("name"), body.get("driver"), json.dumps(config), target_id),
        )
        db.commit()
        if db.execute("SELECT id FROM deploy_targets WHERE id=?", (target_id,)).fetchone():
            return JSONResponse({"ok": True})
        return JSONResponse({"error": "Not found"}, status_code=404)
    finally:
        db.close()


@router.delete("/api/deploy-targets/{target_id}")
async def delete_deploy_target(target_id: str):
    """Delete a deploy target."""
    from ....db.migrations import get_db
    db = get_db()
    try:
        db.execute("DELETE FROM deploy_targets WHERE id = ?", (target_id,))
        db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


@router.post("/api/deploy-targets/{target_id}/test")
async def test_deploy_target(target_id: str):
    """
    Test connectivity for a deploy target.
    For docker-local, checks docker daemon.
    For ssh_docker, tests SSH + docker.
    """
    from ....db.migrations import get_db
    from ....tools.deploy.registry import get_target

    if target_id == "docker-local":
        target = get_target("docker-local")
        ok, msg = await target.test_connection()
        return JSONResponse({"ok": ok, "message": msg})

    db = get_db()
    try:
        row = db.execute("SELECT name FROM deploy_targets WHERE id=?", (target_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "Not found"}, status_code=404)
        target = get_target(row[0])
        ok, msg = await target.test_connection()
        # Update status in DB
        status = "ok" if ok else "error"
        db.execute(
            "UPDATE deploy_targets SET status=?, last_check=CURRENT_TIMESTAMP WHERE id=?",
            (status, target_id),
        )
        db.commit()
        return JSONResponse({"ok": ok, "message": msg})
    finally:
        db.close()
