"""Incident management, auto-heal & chaos endurance endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...schemas import AutoHealStats, IncidentOut, IncidentStats, OkResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/incidents/stats", responses={200: {"model": IncidentStats}})
async def incidents_stats():
    """Incident counts by severity and status."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        by_severity = db.execute(
            "SELECT severity, COUNT(*) as cnt FROM platform_incidents GROUP BY severity"
        ).fetchall()
        by_status = db.execute(
            "SELECT status, COUNT(*) as cnt FROM platform_incidents GROUP BY status"
        ).fetchall()
        recent = db.execute(
            "SELECT id, title, severity, status, source, error_type, created_at "
            "FROM platform_incidents ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        return JSONResponse(
            {
                "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
                "by_status": {r["status"]: r["cnt"] for r in by_status},
                "recent": [dict(r) for r in recent],
            }
        )
    except Exception:
        return JSONResponse({"by_severity": {}, "by_status": {}, "recent": []})
    finally:
        db.close()


@router.get("/api/incidents", responses={200: {"model": list[IncidentOut]}})
async def list_incidents(request: Request):
    """List incidents, optionally filtered by status/severity."""
    from ....db.migrations import get_db

    status = request.query_params.get("status", "")
    severity = request.query_params.get("severity", "")
    limit = int(request.query_params.get("limit", "50"))
    db = get_db()
    try:
        query = "SELECT * FROM platform_incidents WHERE 1=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.post("/api/incidents", responses={200: {"model": OkResponse}})
async def create_incident(request: Request):
    """Create a manual incident."""
    import uuid

    from ....db.migrations import get_db

    data = await request.json()
    title = data.get("title", "")
    if not title:
        return JSONResponse({"error": "title required"}, status_code=400)
    inc_id = str(uuid.uuid4())[:12]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO platform_incidents (id, title, severity, status, source, error_type, error_detail, mission_id, agent_id) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (
                inc_id,
                title,
                data.get("severity", "P3"),
                data.get("source", "manual"),
                data.get("error_type", ""),
                data.get("error_detail", ""),
                data.get("mission_id", ""),
                data.get("agent_id", ""),
            ),
        )
        db.commit()
        return JSONResponse({"id": inc_id, "title": title})
    finally:
        db.close()


@router.patch("/api/incidents/{incident_id}", responses={200: {"model": OkResponse}})
async def update_incident(request: Request, incident_id: str):
    """Update incident status (resolve, close)."""
    from ....db.migrations import get_db

    data = await request.json()
    db = get_db()
    try:
        updates = []
        params = []
        if "status" in data:
            updates.append("status=?")
            params.append(data["status"])
            if data["status"] in ("resolved", "closed"):
                updates.append("resolved_at=CURRENT_TIMESTAMP")
        if "resolution" in data:
            updates.append("resolution=?")
            params.append(data["resolution"])
        if not updates:
            return JSONResponse({"error": "nothing to update"}, status_code=400)
        params.append(incident_id)
        db.execute(
            f"UPDATE platform_incidents SET {', '.join(updates)} WHERE id=?", params
        )
        db.commit()
        return JSONResponse({"ok": True, "id": incident_id})
    finally:
        db.close()


@router.get("/api/autoheal/stats", responses={200: {"model": AutoHealStats}})
async def autoheal_stats():
    """Auto-heal engine statistics."""
    from ....ops.auto_heal import get_autoheal_stats

    return JSONResponse(get_autoheal_stats())


@router.get("/api/autoheal/heartbeat")
async def autoheal_heartbeat():
    """Return animated ECG heartbeat icon with hover detail popover."""
    from ....ops.auto_heal import get_autoheal_stats

    stats = get_autoheal_stats()
    hb = stats.get("heartbeat", "starting")
    inc = stats["incidents"]
    mis = stats["missions"]
    active = stats["active_heals"]

    if not stats["enabled"]:
        css_class, color, status_label = "stale", "var(--text-secondary)", "Disabled"
    elif hb == "alive" and inc["open"] == 0 and active == 0:
        css_class, color, status_label = "alive", "#22c55e", "OK"
    elif hb == "alive":
        css_class, color, status_label = "healing", "#f59e0b", "Active"
    elif hb == "starting":
        css_class, color, status_label = "starting", "#818cf8", "Starting..."
    else:
        css_class, color, status_label = "stale", "#ef4444", "Down"

    last_err = stats.get("last_error", "")
    err_line = (
        f'<div class="tma-tip-row" style="color:#ef4444">Err: {last_err[:60]}</div>'
        if last_err
        else ""
    )

    html = (
        f'<span class="tma-hb {css_class}" style="--tma-color:{color}">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
        f'<div class="tma-tip">'
        f'<div class="tma-tip-title" style="color:{color}">TMA Auto-Heal — {status_label}</div>'
        f'<div class="tma-tip-grid">'
        f'<div class="tma-tip-row"><span>Open</span><span style="color:#f59e0b">{inc["open"]}</span></div>'
        f'<div class="tma-tip-row"><span>Investigating</span><span>{inc["investigating"]}</span></div>'
        f'<div class="tma-tip-row"><span>Resolved</span><span style="color:#22c55e">{inc["resolved"]}</span></div>'
        f'<div class="tma-tip-sep"></div>'
        f'<div class="tma-tip-row"><span>Missions</span><span>{mis["total"]}</span></div>'
        f'<div class="tma-tip-row"><span>Healing</span><span style="color:#f59e0b">{active}</span></div>'
        f'<div class="tma-tip-row"><span>Completed</span><span style="color:#22c55e">{mis["completed"]}</span></div>'
        f'<div class="tma-tip-row"><span>Failed</span><span style="color:#ef4444">{mis["failed"]}</span></div>'
        f"{err_line}"
        f"</div>"
        f'<div class="tma-tip-footer">Scan every {stats["interval_s"]}s — Max {stats["max_concurrent"]} concurrent</div>'
        f"</div></span>"
    )
    return HTMLResponse(html)


@router.post("/api/autoheal/trigger")
async def autoheal_trigger():
    """Manually trigger one auto-heal cycle."""
    from ....ops.auto_heal import heal_cycle

    try:
        await heal_cycle()
        from ....ops.auto_heal import get_autoheal_stats

        return JSONResponse({"ok": True, **get_autoheal_stats()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/chaos/history")
async def chaos_history():
    """Get chaos run history."""
    from ....ops.chaos_endurance import _ensure_table, get_chaos_history

    try:
        _ensure_table()
    except Exception:
        pass
    return JSONResponse(get_chaos_history())


@router.post("/api/chaos/trigger")
async def chaos_trigger(request: Request):
    """Manually trigger a chaos scenario."""
    from ....ops.chaos_endurance import trigger_chaos

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    scenario = body.get("scenario")
    try:
        result = await trigger_chaos(scenario)
        return JSONResponse(
            {
                "ok": result.success,
                "scenario": result.scenario,
                "mttr_ms": result.mttr_ms,
                "detail": result.detail,
            }
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
