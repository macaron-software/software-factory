"""Hook registry API — list, register, toggle, delete hooks and view execution log."""
# Ref: feat-monitoring

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/hooks")
async def list_hooks(request: Request):
    """List all registered hooks. Supports ?agent_id= filter."""
    from ....hooks import registry as _reg

    agent_id = request.query_params.get("agent_id")
    return JSONResponse({"hooks": _reg.list_all(agent_id=agent_id or None)})


@router.get("/api/hooks/types")
async def hook_types():
    """List available hook types with descriptions."""
    return JSONResponse(
        {
            "types": [
                {
                    "id": "pre_tool",
                    "label": "PRE_TOOL",
                    "description": "Fires before each tool execution. Can block (requires security/arch scope).",
                    "can_block": True,
                },
                {
                    "id": "post_tool",
                    "label": "POST_TOOL",
                    "description": "Fires after each tool execution.",
                    "can_block": False,
                },
                {
                    "id": "session_start",
                    "label": "SESSION_START",
                    "description": "Fires at the beginning of an agent session.",
                    "can_block": False,
                },
                {
                    "id": "session_end",
                    "label": "SESSION_END",
                    "description": "Fires at the end of an agent session.",
                    "can_block": False,
                },
                {
                    "id": "pre_compact",
                    "label": "PRE_COMPACT",
                    "description": "Fires before context summarization.",
                    "can_block": False,
                },
            ]
        }
    )


@router.get("/api/hooks/log")
async def hook_log(request: Request):
    """Return recent hook execution log. Supports ?limit=50&agent_id=&hook_type="""
    limit = min(int(request.query_params.get("limit", 50)), 200)
    agent_filter = request.query_params.get("agent_id", "")
    type_filter = request.query_params.get("hook_type", "")

    try:
        from ....db.migrations import get_db

        with get_db() as db:
            params: list = []
            where = []
            if agent_filter:
                where.append("agent_id = ?")
                params.append(agent_filter)
            if type_filter:
                where.append("hook_type = ?")
                params.append(type_filter)
            clause = ("WHERE " + " AND ".join(where)) if where else ""
            rows = db.execute(
                f"SELECT * FROM hook_log {clause} ORDER BY ts DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            cols = [
                "id",
                "hook_type",
                "handler_name",
                "agent_id",
                "session_id",
                "tool_name",
                "blocked",
                "message",
                "duration_ms",
                "ts",
            ]
            return JSONResponse(
                {"log": [dict(zip(cols, r)) for r in rows], "total": len(rows)}
            )
    except Exception as exc:
        logger.warning("hook_log error: %s", exc)
        return JSONResponse({"log": [], "error": str(exc)})


@router.post("/api/hooks")
async def register_hook(request: Request):
    """Register a new hook handler (built-in handler name or custom).

    Body: {hook_type, handler_name, agent_id?, priority?, can_block?, required_role?, config?}
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    hook_type = body.get("hook_type", "")
    handler_name = body.get("handler_name", "")
    agent_id = body.get("agent_id")
    priority = int(body.get("priority", 0))
    can_block = bool(body.get("can_block", False))
    required_role = body.get("required_role")

    if not hook_type or not handler_name:
        return JSONResponse(
            {"error": "hook_type and handler_name are required"}, status_code=400
        )

    # RBAC check — caller agent
    caller_agent_id = body.get("caller_agent_id", "")
    if caller_agent_id:
        try:
            from ....hooks.rbac import can_register_hook
            from ....agents.store import get_agent_store

            store = get_agent_store()
            caller = store.get(caller_agent_id)
            if caller:
                agent_dict = {
                    "id": caller.id,
                    "scope": getattr(caller, "scope", "project"),
                    "category": getattr(caller, "category", ""),
                    "permissions": getattr(caller, "permissions", {}),
                }
                allowed, reason = can_register_hook(agent_dict, hook_type, can_block)
                if not allowed:
                    return JSONResponse({"error": reason}, status_code=403)
        except Exception as exc:
            logger.warning("hook rbac check failed: %s", exc)

    # Register (custom hooks use a pass-through no-op handler — real logic injected via external call)
    from ....hooks import HookType, HookContext, HookResult, registry as _reg

    try:
        ht = HookType(hook_type)
    except ValueError:
        return JSONResponse(
            {"error": f"Unknown hook_type: {hook_type}"}, status_code=400
        )

    async def _noop(ctx: HookContext) -> HookResult:
        return HookResult()

    rid = str(uuid.uuid4())
    try:
        _reg.register(
            ht,
            handler_name,
            _noop,
            agent_id=agent_id,
            priority=priority,
            can_block=can_block,
            required_role=required_role,
            reg_id=rid,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # Persist to DB
    try:
        from ....db.migrations import get_db
        import json

        with get_db() as db:
            db.execute(
                """INSERT OR REPLACE INTO hook_registrations
                   (id, hook_type, handler_name, agent_id, priority, enabled, can_block, required_role, config_json)
                   VALUES (?,?,?,?,?,1,?,?,?)""",
                (
                    rid,
                    hook_type,
                    handler_name,
                    agent_id,
                    priority,
                    1 if can_block else 0,
                    required_role,
                    json.dumps(body.get("config", {})),
                ),
            )
    except Exception as exc:
        logger.warning("hook persist error: %s", exc)

    return JSONResponse(
        {"id": rid, "hook_type": hook_type, "handler_name": handler_name}
    )


@router.patch("/api/hooks/{hook_id}/toggle")
async def toggle_hook(hook_id: str, request: Request):
    """Enable or disable a registered hook. Body: {enabled: bool}"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    enabled = bool(body.get("enabled", True))

    from ....hooks import registry as _reg

    ok = _reg.toggle(hook_id, enabled)
    if not ok:
        return JSONResponse({"error": "Hook not found"}, status_code=404)

    try:
        from ....db.migrations import get_db

        with get_db() as db:
            db.execute(
                "UPDATE hook_registrations SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, hook_id),
            )
    except Exception:
        pass

    return JSONResponse({"id": hook_id, "enabled": enabled})


@router.delete("/api/hooks/{hook_id}")
async def delete_hook(hook_id: str):
    """Unregister a hook by ID."""
    from ....hooks import registry as _reg

    ok = _reg.unregister(hook_id)
    if not ok:
        return JSONResponse({"error": "Hook not found"}, status_code=404)

    try:
        from ....db.migrations import get_db

        with get_db() as db:
            db.execute("DELETE FROM hook_registrations WHERE id = ?", (hook_id,))
    except Exception:
        pass

    return JSONResponse({"deleted": hook_id})
