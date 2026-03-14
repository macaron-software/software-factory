"""Deploy Targets CRUD API."""
# Ref: feat-ops

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from ....auth.middleware import require_auth
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


@router.post("/api/deploy-targets", dependencies=[Depends(require_auth("admin"))])
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


@router.put("/api/deploy-targets/{target_id}", dependencies=[Depends(require_auth("admin"))])
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


@router.delete("/api/deploy-targets/{target_id}", dependencies=[Depends(require_auth("admin"))])
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


@router.post("/api/deploy-targets/{target_id}/test", dependencies=[Depends(require_auth("admin"))])
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


@router.post("/api/deploy-targets/{target_id}/provision", dependencies=[Depends(require_auth("admin"))])
async def provision_deploy_target(target_id: str, request: Request):
    """
    Provision a new Azure VM for a deploy target.
    Body: {tenant_id, client_id, client_secret, subscription_id, resource_group?, location?, vm_name?}
    Returns SSE stream of provisioning steps.
    """
    from fastapi.responses import StreamingResponse
    from ....db.migrations import get_db
    from ....tools.deploy.azure_provision import provision_azure_vm

    body = await request.json()
    required = ["tenant_id", "client_id", "client_secret", "subscription_id"]
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JSONResponse({"error": f"Missing fields: {', '.join(missing)}"}, status_code=400)

    db = get_db()
    row = db.execute("SELECT name FROM deploy_targets WHERE id=?", (target_id,)).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "Target not found"}, status_code=404)
    target_name = row[0]

    async def stream():
        steps_out = []

        async def progress(step):
            import json as _json
            steps_out.append(step)
            yield f"data: {_json.dumps({'step': step.step, 'message': step.message, 'done': step.done, 'error': step.error})}\n\n"

        # Collect and stream
        events = []

        async def cb(step):
            events.append(step)

        result = await provision_azure_vm(
            subscription_id=body["subscription_id"],
            tenant_id=body["tenant_id"],
            client_id=body["client_id"],
            client_secret=body["client_secret"],
            resource_group=body.get("resource_group", "macaron-sandbox-rg"),
            location=body.get("location", "francecentral"),
            vm_name=body.get("vm_name", "macaron-sandbox"),
            progress_cb=cb,
        )

        import json as _json
        for s in events:
            yield f"data: {_json.dumps({'step': s.step, 'message': s.message, 'done': s.done, 'error': s.error})}\n\n"

        if result.ok:
            # Update target with real IP + private key
            import os as _os
            key_path = _os.path.expanduser(f"~/.ssh/macaron-sandbox.pem")
            with open(key_path, "w") as kf:
                kf.write(result.private_key)
            _os.chmod(key_path, 0o600)

            new_config = json.dumps({
                "host": result.host,
                "port": 22,
                "user": result.user,
                "key_path": key_path,
                "remote_dir": "/opt/macaron-apps",
                "host_port": 0,
            })
            db2 = get_db()
            db2.execute(
                "UPDATE deploy_targets SET config_json=?, status='ok', last_check=CURRENT_TIMESTAMP WHERE id=?",
                (new_config, target_id),
            )
            db2.commit()
            db2.close()
            yield f"data: {_json.dumps({'step': 'complete', 'message': f'VM ready at {result.host} — target updated', 'done': True, 'error': False, 'host': result.host})}\n\n"
        else:
            yield f"data: {_json.dumps({'step': 'error', 'message': result.message, 'done': False, 'error': True})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
