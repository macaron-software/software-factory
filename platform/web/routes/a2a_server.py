"""A2A (Agent2Agent) Protocol Server — Jarvis endpoint.

Exposes Jarvis (strat-cto) as a standard A2A-compliant agent:
  GET  /.well-known/agent.json        Agent Card (discovery)
  POST /a2a/tasks                     Submit a task to Jarvis
  GET  /a2a/tasks/{task_id}           Get task status / result
  GET  /a2a/events?task_id={id}       SSE streaming progress
  POST /a2a/tasks/{task_id}/cancel    Cancel a pending task

A2A spec: https://a2a-protocol.org/latest/specification/
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue as _queue_module
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Depends,  APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import Request
from ...auth.middleware import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

_CTO_AGENT_ID = "strat-cto"

# In-memory task store: task_id → task dict
# (For production: use DB / Redis)
_tasks: dict[str, dict] = {}
# SSE queues per task_id — use thread-safe queue.Queue so _run_jarvis thread can write
_task_queues: dict[str, _queue_module.Queue] = {}

# ── Agent Card ────────────────────────────────────────────────────────────────


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/.well-known/agent.json")
async def agent_card(request: Request):
    """A2A Agent Card — describes Jarvis capabilities for external discovery."""
    base = _base_url(request)
    return JSONResponse(
        {
            "a2a_version": "1.0",
            "id": "urn:agent:software-factory:jarvis",
            "name": "Jarvis — Software Factory CTO",
            "description": (
                "Jarvis is the executive AI agent of the Software Factory. "
                "He creates and orchestrates projects, epics, missions, sprints and teams. "
                "Delegate any software delivery task to Jarvis."
            ),
            "version": "1.0.0",
            "provider": {
                "name": "Macaron Software",
                "url": base,
            },
            "endpoints": {
                "task_submit": f"{base}/a2a/tasks",
                "task_get": f"{base}/a2a/tasks/{{task_id}}",
                "task_cancel": f"{base}/a2a/tasks/{{task_id}}/cancel",
                "events": f"{base}/a2a/events",
            },
            "capabilities": [
                "create_project",
                "create_mission",
                "create_epic",
                "launch_epic_run",
                "check_run_status",
                "delegate_to_rte",
                "delegate_to_po",
                "delegate_to_scrum_master",
                "web_search",
                "platform_metrics",
            ],
            "modalities": ["text/plain", "application/json"],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": [
                {
                    "id": "project-creation",
                    "name": "Project Creation",
                    "description": "Create a new software project with team, workflow and first epic.",
                    "tags": ["project", "epic", "mission"],
                },
                {
                    "id": "delivery-orchestration",
                    "name": "Delivery Orchestration",
                    "description": "Launch and monitor epic runs, delegate to RTE, PO, Scrum Master.",
                    "tags": ["orchestration", "sprint", "agile"],
                },
                {
                    "id": "platform-status",
                    "name": "Platform Status",
                    "description": "Report on running missions, agent activity, and metrics.",
                    "tags": ["monitoring", "metrics"],
                },
            ],
            "auth": {
                "type": "cookie",
                "description": "Requires active SF session cookie (POST /api/auth/demo for demo auth).",
            },
        }
    )


# ── Task helpers ───────────────────────────────────────────────────────────────


def _make_task(message: str, context_id: str = "") -> dict:
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task = {
        "id": task_id,
        "kind": "task",
        "contextId": context_id or str(uuid.uuid4()),
        "status": {"state": "submitted", "timestamp": now},
        "input": {"role": "user", "parts": [{"kind": "text", "text": message}]},
        "output": None,
        "metadata": {},
        "createdAt": now,
        "updatedAt": now,
    }
    _tasks[task_id] = task
    _task_queues[task_id] = _queue_module.Queue(maxsize=200)
    return task


def _update_task(
    task_id: str, state: str, output: str | None = None, metadata: dict | None = None
):
    task = _tasks.get(task_id)
    if not task:
        return
    now = datetime.now(timezone.utc).isoformat()
    task["status"] = {"state": state, "timestamp": now}
    task["updatedAt"] = now
    if output is not None:
        task["output"] = {"role": "agent", "parts": [{"kind": "text", "text": output}]}
    if metadata:
        task["metadata"].update(metadata)
    # Notify SSE listeners
    q = _task_queues.get(task_id)
    if q:
        try:
            q.put_nowait({"event": "task.status", "task": task})
        except _queue_module.Full:
            pass


# ── Submit task ────────────────────────────────────────────────────────────────


@router.post("/a2a/tasks", dependencies=[Depends(require_auth())])
async def submit_task(request: Request):
    """Submit a task to Jarvis. Returns task object with id + submitted status."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    # Extract message from A2A task input
    parts = (body.get("input") or {}).get("parts") or []
    message = next((p.get("text", "") for p in parts if p.get("kind") == "text"), "")
    if not message:
        # Fallback: accept plain {"message": "..."}
        message = str(body.get("message") or body.get("text") or "").strip()
    if not message:
        return JSONResponse(
            {"error": "No text message provided in input.parts"}, status_code=422
        )

    context_id = str(body.get("contextId") or "")
    task = _make_task(message, context_id)

    # Schedule Jarvis execution as an async task on the current event loop.
    # The executor pattern with asyncio.run() fails in thread context.
    asyncio.ensure_future(_run_jarvis(task["id"], message))

    return JSONResponse(task, status_code=202)


async def _run_jarvis(task_id: str, message: str):
    """Background coroutine: runs Jarvis executor, updates task state + SSE queue."""
    try:
        from ...sessions.store import get_session_store, MessageDef
        from ...agents.store import get_agent_store
        from ...agents.executor import get_executor
        from ...sessions.runner import _build_context
    except Exception as exc:
        logger.exception("A2A task %s — import error", task_id)
        _update_task(task_id, "failed", f"Import error: {exc}")
        return

    task = _tasks.get(task_id)
    if not task:
        return

    _update_task(task_id, "working")

    try:
        store = get_session_store()

        # Reuse or create a CTO session per contextId
        context_id = task.get("contextId", "")
        existing = None
        if context_id:
            # Try to find existing session with matching contextId
            for s in store.list_all(limit=50):
                if (s.config or {}).get("a2a_context_id") == context_id:
                    existing = s
                    break

        if not existing:
            from ...sessions.store import SessionDef

            session = store.create(
                SessionDef(
                    name=f"A2A task {task_id[:8]}",
                    goal="A2A task delegation to Jarvis",
                    status="active",
                    config={
                        "lead_agent": _CTO_AGENT_ID,
                        "type": "cto_chat",
                        "a2a_context_id": context_id or task_id,
                        "a2a_task_id": task_id,
                    },
                )
            )
        else:
            session = existing

        store.add_message(
            MessageDef(
                session_id=session.id,
                from_agent="user",
                message_type="text",
                content=message,
            )
        )

        agent_store = get_agent_store()
        agent = agent_store.get(_CTO_AGENT_ID)
        if not agent:
            _update_task(task_id, "failed", "CTO agent not found")
            return

        ctx = await _build_context(agent, session)
        executor = get_executor()
        result_text = ""

        async for event_type, data in executor.run_streaming(ctx, message):
            if event_type == "delta":
                result_text += data
                # Push incremental SSE event
                q = _task_queues.get(task_id)
                if q:
                    try:
                        q.put_nowait(
                            {"event": "task.delta", "task_id": task_id, "delta": data}
                        )
                    except _queue_module.Full:
                        pass
            elif event_type == "tool":
                q = _task_queues.get(task_id)
                if q:
                    try:
                        q.put_nowait(
                            {"event": "task.tool", "task_id": task_id, "tool": data}
                        )
                    except _queue_module.Full:
                        pass
            elif event_type == "result":
                result_text = data.content if hasattr(data, "content") else str(data)
                _update_task(
                    task_id,
                    "completed",
                    result_text,
                    {
                        "model": getattr(data, "model", ""),
                        "provider": getattr(data, "provider", ""),
                        "tokens_in": getattr(data, "tokens_in", 0),
                        "tokens_out": getattr(data, "tokens_out", 0),
                    },
                )

        store.add_message(
            MessageDef(
                session_id=session.id,
                from_agent=_CTO_AGENT_ID,
                to_agent="user",
                message_type="text",
                content=result_text,
            )
        )

        if _tasks.get(task_id, {}).get("status", {}).get("state") == "working":
            _update_task(task_id, "completed", result_text)

    except Exception as exc:
        logger.exception("A2A task %s failed", task_id)
        _update_task(task_id, "failed", str(exc))
    finally:
        # Signal SSE stream end
        q = _task_queues.get(task_id)
        if q:
            try:
                q.put_nowait({"event": "task.done", "task_id": task_id})
            except _queue_module.Full:
                pass


# ── Get task ───────────────────────────────────────────────────────────────────


@router.get("/a2a/tasks/{task_id}")
async def get_task(task_id: str):
    """Return current task state."""
    task = _tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse(task)


@router.get("/a2a/tasks")
async def list_tasks():
    """List recent tasks (last 50)."""
    tasks = list(_tasks.values())[-50:]
    return JSONResponse({"tasks": tasks, "total": len(_tasks)})


# ── Cancel task ────────────────────────────────────────────────────────────────


@router.post("/a2a/tasks/{task_id}/cancel", dependencies=[Depends(require_auth())])
async def cancel_task(task_id: str):
    """Cancel a submitted or working task."""
    task = _tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    state = task.get("status", {}).get("state", "")
    if state in ("completed", "failed", "canceled"):
        return JSONResponse(
            {"ok": False, "error": f"Task already in terminal state: {state}"}
        )
    _update_task(task_id, "canceled")
    return JSONResponse({"ok": True, "task_id": task_id, "status": "canceled"})


# ── SSE events ─────────────────────────────────────────────────────────────────


@router.get("/a2a/events")
async def task_events(task_id: str = ""):
    """SSE stream for a task. Set task_id query param."""
    if not task_id or task_id not in _tasks:
        return JSONResponse(
            {"error": "task_id required and must exist"}, status_code=400
        )

    async def generate() -> AsyncIterator[str]:
        q = _task_queues.get(task_id)
        if not q:
            yield f"data: {json.dumps({'event': 'task.done', 'task_id': task_id})}\n\n"
            return

        # If already done, send current state immediately
        state = _tasks.get(task_id, {}).get("status", {}).get("state", "")
        if state in ("completed", "failed", "canceled"):
            yield f"data: {json.dumps({'event': 'task.status', 'task': _tasks[task_id]})}\n\n"
            yield f"data: {json.dumps({'event': 'task.done', 'task_id': task_id})}\n\n"
            return

        while True:
            try:
                # Read from thread-safe queue; run_in_executor avoids blocking event loop
                event = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: q.get(timeout=30)
                )
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("event") == "task.done":
                    break
            except _queue_module.Empty:
                # Keepalive ping
                yield ": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
