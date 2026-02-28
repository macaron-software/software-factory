"""Webhook Triggers — event-driven mission launches.

Supported sources: github, jira, monitoring (Grafana/PagerDuty), generic.
Each webhook config maps source+event to workflow_id + project_id.
"""

from __future__ import annotations
import hashlib
import hmac
import json
import os
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _get_configs(source: str):
    from ...db.migrations import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM webhook_configs WHERE source=? AND is_active=1", (source,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def _launch_mission(
    workflow_id: str, project_id: str, name: str, goal: str
) -> str | None:
    """Launch a workflow mission and return run_id."""
    try:
        from ...missions.store import MissionStore, MissionRunStore
        from ...orchestrator.engine import get_engine
        import asyncio

        ms = MissionStore()
        mission = ms.create(
            name=name,
            workflow_id=workflow_id,
            project_id=project_id or "default",
            goal=goal,
            tags=["webhook", "auto"],
        )
        mrs = MissionRunStore()
        run = mrs.create(mission_id=mission.id)
        engine = get_engine()
        asyncio.create_task(engine.run(run.id))
        return run.id
    except Exception as e:
        import logging

        logging.getLogger(__name__).error("webhook launch failed: %s", e)
        return None


@router.post("/github")
async def github_webhook(request: Request):
    """GitHub webhook: push, pull_request, issues — launch configured workflow."""
    body = await request.body()
    event = request.headers.get("X-GitHub-Event", "ping")

    if event == "ping":
        return JSONResponse({"ok": True, "event": "ping"})

    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = (
            "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(sig, expected):
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    repo = payload.get("repository", {}).get("full_name", "unknown")
    configs = _get_configs("github")

    launched = []
    for cfg in configs:
        if cfg["event_filter"] not in ("*", event):
            continue
        name = f"GitHub {event}: {repo}"
        goal = (
            f"Handle GitHub {event} from {repo}. Payload summary: {str(payload)[:300]}"
        )
        run_id = await _launch_mission(
            cfg["workflow_id"], cfg["project_id"] or "", name, goal
        )
        if run_id:
            launched.append(run_id)

    return JSONResponse({"ok": True, "event": event, "launched": launched})


@router.post("/jira")
async def jira_webhook(request: Request):
    """Jira webhook: issue_created, issue_updated — launch configured workflow."""
    body = await request.body()

    secret = os.environ.get("JIRA_WEBHOOK_SECRET", "")
    if secret:
        sig = request.headers.get("X-Hub-Signature", "")
        expected = (
            "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(sig, expected):
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    event = payload.get("webhookEvent", "unknown")
    issue = payload.get("issue", {})
    issue_key = issue.get("key", "?")
    summary = issue.get("fields", {}).get("summary", "")

    configs = _get_configs("jira")
    launched = []
    for cfg in configs:
        if cfg["event_filter"] not in ("*", event):
            continue
        name = f"Jira {event}: {issue_key}"
        goal = f"Handle Jira event {event} for issue {issue_key}: {summary}"
        run_id = await _launch_mission(
            cfg["workflow_id"], cfg["project_id"] or "", name, goal
        )
        if run_id:
            launched.append(run_id)

    return JSONResponse(
        {"ok": True, "event": event, "issue": issue_key, "launched": launched}
    )


@router.post("/monitoring")
async def monitoring_webhook(request: Request):
    """Monitoring webhook: Grafana alerts, PagerDuty incidents — launch tma-autoheal."""
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    alert_name = (
        payload.get("title")
        or payload.get("incident", {}).get("title")
        or payload.get("alert", "unknown")
    )
    severity = payload.get("severity", payload.get("state", "warning"))

    configs = _get_configs("monitoring")
    launched = []
    for cfg in configs:
        name = f"Alert: {alert_name}"
        goal = f"Auto-heal triggered by monitoring alert: {alert_name} (severity: {severity}). Payload: {str(payload)[:300]}"
        run_id = await _launch_mission(
            cfg["workflow_id"], cfg["project_id"] or "", name, goal
        )
        if run_id:
            launched.append(run_id)

    return JSONResponse({"ok": True, "alert": alert_name, "launched": launched})


@router.post("/generic")
async def generic_webhook(request: Request, workflow_id: str, project_id: str = ""):
    """Generic webhook: launch any workflow with payload as context.
    Usage: POST /api/webhooks/generic?workflow_id=tma-maintenance&project_id=my-project
    """
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    name = f"Webhook: {workflow_id}"
    goal = f"Webhook-triggered {workflow_id}. Context: {str(payload)[:400]}"
    run_id = await _launch_mission(workflow_id, project_id, name, goal)
    return JSONResponse(
        {"ok": True if run_id else False, "run_id": run_id, "workflow_id": workflow_id}
    )


# Config management


@router.get("/configs")
async def list_webhook_configs():
    from ...db.migrations import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM webhook_configs ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return {"configs": [dict(r) for r in rows]}


@router.post("/configs")
async def create_webhook_config(
    source: str,
    event_filter: str = "*",
    workflow_id: str = "",
    project_id: str = "",
    description: str = "",
    secret_env: str = "",
):
    from ...db.migrations import get_db

    if not workflow_id:
        from fastapi import HTTPException

        raise HTTPException(400, "workflow_id required")
    cid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO webhook_configs (id, source, event_filter, workflow_id, project_id, description, secret_env) VALUES (?,?,?,?,?,?,?)",
        (cid, source, event_filter, workflow_id, project_id, description, secret_env),
    )
    conn.commit()
    conn.close()
    return {"id": cid, "ok": True}


@router.delete("/configs/{config_id}")
async def delete_webhook_config(config_id: str):
    from ...db.migrations import get_db

    conn = get_db()
    conn.execute("DELETE FROM webhook_configs WHERE id=?", (config_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
