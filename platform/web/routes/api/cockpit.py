"""Cockpit — SF global summary endpoint.

Aggregates all SF state into a single JSON payload for the /cockpit dashboard:
pipeline stats, environments, daemons, LLM providers, projects, activity feed,
TMA, incidents, DORA metrics.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


@router.get("/api/cockpit/summary")
async def cockpit_summary() -> JSONResponse:
    """Return full SF state summary for the cockpit page."""
    import json as _json
    from decimal import Decimal

    from ....db.adapter import get_connection

    db = get_connection()
    try:
        result = _build_summary(db)
    finally:
        db.close()

    # Serialize — handle Decimal from PG aggregates
    def _default(o):
        if isinstance(o, Decimal):
            return float(o)
        raise TypeError(
            f"Object of type {o.__class__.__name__} is not JSON serializable"
        )

    return JSONResponse(content=_json.loads(_json.dumps(result, default=_default)))


def _build_summary(db) -> dict[str, Any]:
    # ── Pipeline ────────────────────────────────────────────────────
    pipeline = _safe(lambda: _get_pipeline(db), {})

    # ── Environments ────────────────────────────────────────────────
    environments = _safe(_get_environments, [])

    # ── Daemons ─────────────────────────────────────────────────────
    daemons = _safe(_get_daemons, [])

    # ── LLM providers ───────────────────────────────────────────────
    llm = _safe(_get_llm_status, [])

    # ── Projects ────────────────────────────────────────────────────
    projects = _safe(lambda: _get_projects(db), [])

    # ── Activity feed ───────────────────────────────────────────────
    activity = _safe(lambda: _get_activity(db), [])

    # ── TMA ─────────────────────────────────────────────────────────
    tma = _safe(lambda: _get_tma(db), {})

    # ── Incidents / Auto-Heal ────────────────────────────────────────
    incidents = _safe(lambda: _get_incidents(db), {})

    # ── DORA ────────────────────────────────────────────────────────
    dora = _safe(lambda: _get_dora(db), {})

    return {
        "ts": int(time.time()),
        "pipeline": pipeline,
        "environments": environments,
        "daemons": daemons,
        "llm": llm,
        "projects": projects,
        "activity": activity,
        "tma": tma,
        "incidents": incidents,
        "dora": dora,
    }


# ── Pipeline ────────────────────────────────────────────────────────────────


def _get_pipeline(db) -> dict:
    # Epics (missions table)
    epics = db.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE status IN ('active','running')) AS active,"
        "  COUNT(*) AS total,"
        "  COUNT(*) FILTER (WHERE status='completed') AS completed,"
        "  COUNT(*) FILTER (WHERE status='planning') AS planning"
        " FROM missions"
    ).fetchone()
    # Features
    feats = db.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE status IN ('active','running','in_progress')) AS active,"
        "  COUNT(*) AS total,"
        "  COUNT(*) FILTER (WHERE status='completed') AS completed"
        " FROM features"
    ).fetchone()
    # Tasks
    tsk = _safe(
        lambda: db.execute(
            "SELECT "
            "  COUNT(*) FILTER (WHERE status IN ('active','running','in_progress')) AS active,"
            "  COUNT(*) AS total"
            " FROM tasks"
        ).fetchone(),
        None,
    )
    ideation = db.execute(
        "SELECT COUNT(*) AS n FROM ideation_sessions WHERE status='active'"
    ).fetchone()
    deploys = db.execute(
        "SELECT COUNT(*) AS n FROM missions"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '1 day'"
    ).fetchone()
    return {
        "ideation_active": ideation["n"] if ideation else 0,
        # Epics (formerly missions)
        "epics_total": epics["total"] if epics else 0,
        "epics_active": epics["active"] if epics else 0,
        "epics_planning": epics["planning"] if epics else 0,
        "epics_completed": epics["completed"] if epics else 0,
        # Features
        "features_total": feats["total"] if feats else 0,
        "features_active": feats["active"] if feats else 0,
        "features_completed": feats["completed"] if feats else 0,
        # Tasks
        "tasks_total": tsk["total"] if tsk else 0,
        "tasks_active": tsk["active"] if tsk else 0,
        # Legacy keys for backwards compat
        "missions_total": epics["total"] if epics else 0,
        "missions_active": epics["active"] if epics else 0,
        "missions_planning": epics["planning"] if epics else 0,
        "missions_completed": epics["completed"] if epics else 0,
        "deploys_today": deploys["n"] if deploys else 0,
    }


# ── Environments ────────────────────────────────────────────────────────────


def _get_environments() -> list[dict]:
    import httpx

    # Local env — we're running on this server, mark as online directly
    local_version = None
    try:
        import importlib.metadata

        local_version = importlib.metadata.version("macaron-platform")
    except Exception:
        pass

    envs_remote = [
        {
            "id": "ovh",
            "name": "OVH Demo",
            "url": os.environ.get("OVH_PLATFORM_URL", ""),
        },
        {
            "id": "azure",
            "name": "Azure Prod",
            "url": os.environ.get("AZURE_PLATFORM_URL", ""),
        },
    ]
    results = [
        {
            "id": "local",
            "name": "Local Dev",
            "url": "http://localhost:8099",
            "status": "online",
            "version": local_version,
        },
    ]
    for env in envs_remote:
        url = env["url"]
        if not url:
            results.append({**env, "status": "not_configured", "version": None})
            continue
        try:
            r = httpx.get(f"{url}/api/health", timeout=2.0)
            data = (
                r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            results.append(
                {
                    **env,
                    "status": "online"
                    if r.status_code == 200 and data.get("status") == "ok"
                    else "degraded",
                    "version": data.get("version"),
                }
            )
        except Exception:
            results.append({**env, "status": "offline", "version": None})
    return results


# ── Daemons ─────────────────────────────────────────────────────────────────


def _get_daemons() -> list[dict]:
    """Return known background daemons and their heartbeat status."""
    from ....ops.endurance_watchdog import ENABLED as _wd_enabled

    # Daemons declared at startup. We check "alive" via in-memory flags + DB metrics.
    daemons = [
        {"id": "watchdog", "label": "Endurance Watchdog", "schedule": "continuous"},
        {"id": "autoheal", "label": "Auto-Heal", "schedule": "60s"},
        {
            "id": "evolution",
            "label": "Evolution Scheduler",
            "schedule": "nightly 02:00",
        },
        {
            "id": "knowledge",
            "label": "Knowledge Maintenance",
            "schedule": "nightly 04:00",
        },
        {"id": "compactor", "label": "Memory Compactor", "schedule": "nightly 03:00"},
        {"id": "mcp", "label": "MCP Watchdog", "schedule": "continuous"},
        {"id": "wal", "label": "WAL Checkpoint", "schedule": "continuous"},
    ]

    # Try to get last heartbeat from endurance_metrics table
    last_runs: dict[str, str] = {}
    try:
        from ....db.adapter import get_connection as _gc

        _db = _gc()
        try:
            rows = _db.execute(
                "SELECT metric, MAX(ts) as last_ts FROM endurance_metrics"
                " GROUP BY metric"
            ).fetchall()
            for r in rows:
                last_runs[r["metric"]] = r["last_ts"]
        finally:
            _db.close()
    except Exception:
        pass

    # Auto-heal heartbeat
    autoheal_alive = False
    try:
        from ....ops.auto_heal import get_autoheal_stats

        stats = get_autoheal_stats()
        autoheal_alive = stats.get("alive", False)
    except Exception:
        pass

    result = []
    for d in daemons:
        did = d["id"]
        if did == "watchdog":
            status = "enabled" if _wd_enabled else "disabled"
        elif did == "autoheal":
            status = "running" if autoheal_alive else "idle"
        else:
            status = "scheduled"
        last_run = last_runs.get(f"{did}_cycle") or last_runs.get(did)
        result.append({**d, "status": status, "last_run": last_run})
    return result


# ── LLM Providers ───────────────────────────────────────────────────────────


def _get_llm_status() -> list[dict]:
    try:
        from ....llm.client import get_llm_client

        client = get_llm_client()
    except Exception:
        return []

    providers = ["minimax", "azure-openai", "azure-ai", "openai"]
    result = []
    now = time.monotonic()
    for prov in providers:
        cb_open = client._cb_open_until.get(prov, 0) > now
        cooldown = client._provider_cooldown.get(prov, 0) > now
        failures = len(client._cb_failures.get(prov, []))
        result.append(
            {
                "provider": prov,
                "circuit_open": cb_open,
                "cooldown": cooldown,
                "recent_failures": failures,
                "status": "open" if cb_open else ("cooldown" if cooldown else "ok"),
            }
        )
    return result


# ── Projects ────────────────────────────────────────────────────────────────


def _get_projects(db) -> list[dict]:
    rows = db.execute(
        "SELECT p.id, p.name,"
        "  COUNT(m.id) AS total_missions,"
        "  COUNT(m.id) FILTER (WHERE m.status IN ('active','running')) AS active_missions,"
        "  COUNT(m.id) FILTER (WHERE m.status='completed') AS done_missions,"
        "  MAX(m.created_at) AS last_activity"
        " FROM projects p"
        " LEFT JOIN missions m ON m.project_id = p.id"
        " GROUP BY p.id, p.name"
        " ORDER BY last_activity DESC NULLS LAST"
        " LIMIT 8"
    ).fetchall()
    result = []
    for r in rows:
        total = r["total_missions"] or 0
        done = r["done_missions"] or 0
        progress = int(done * 100 / total) if total > 0 else 0
        result.append(
            {
                "id": r["id"],
                "name": r["name"],
                "total_missions": total,
                "active_missions": r["active_missions"] or 0,
                "done_missions": done,
                "progress": progress,
                "last_activity": str(r["last_activity"])
                if r["last_activity"]
                else None,
            }
        )
    return result


# ── Activity feed ────────────────────────────────────────────────────────────


def _get_activity(db) -> list[dict]:
    """Last 12 messages from active sessions (agent tool calls + system events)."""
    rows = db.execute(
        "SELECT m.from_agent, m.content, m.timestamp, s.project_id,"
        "  p.name AS project_name"
        " FROM messages m"
        " LEFT JOIN sessions s ON s.id = m.session_id"
        " LEFT JOIN projects p ON p.id = s.project_id"
        " WHERE m.from_agent NOT IN ('user','system')"
        " AND m.timestamp >= NOW() - INTERVAL '1 hour'"
        " ORDER BY m.timestamp DESC"
        " LIMIT 12"
    ).fetchall()
    result = []
    for r in rows:
        content = str(r["content"] or "")[:120]
        result.append(
            {
                "ts": str(r["timestamp"]),
                "agent": r["from_agent"],
                "label": content,
                "project_id": r["project_id"],
                "project_name": r["project_name"],
            }
        )
    return result


# ── TMA ─────────────────────────────────────────────────────────────────────


def _get_tma(db) -> dict:
    row = db.execute(
        "SELECT"
        "  COUNT(*) FILTER (WHERE status='open') AS open_count,"
        "  COUNT(*) FILTER (WHERE status='closed'"
        "    AND updated_at >= NOW() - INTERVAL '1 day') AS closed_today,"
        "  COUNT(*) FILTER (WHERE severity='critical') AS critical"
        " FROM support_tickets"
    ).fetchone()
    if not row:
        return {"open": 0, "closed_today": 0, "critical": 0}
    return {
        "open": row["open_count"] or 0,
        "closed_today": row["closed_today"] or 0,
        "critical": row["critical"] or 0,
    }


# ── Incidents ────────────────────────────────────────────────────────────────


def _get_incidents(db) -> dict:
    row = db.execute(
        "SELECT"
        "  COUNT(*) FILTER (WHERE status='open') AS open_count,"
        "  COUNT(*) FILTER (WHERE status='investigating') AS investigating,"
        "  COUNT(*) FILTER (WHERE status='resolved'"
        "    AND resolved_at >= NOW() - INTERVAL '1 day') AS resolved_today"
        " FROM platform_incidents"
    ).fetchone()
    ah_active = 0
    try:
        ah_row = db.execute(
            "SELECT COUNT(*) AS n FROM missions"
            " WHERE created_by='auto-heal' AND status='active'"
        ).fetchone()
        ah_active = ah_row["n"] if ah_row else 0
    except Exception:
        pass
    return {
        "open": row["open_count"] or 0 if row else 0,
        "investigating": row["investigating"] or 0 if row else 0,
        "resolved_today": row["resolved_today"] or 0 if row else 0,
        "autoheal_active": ah_active,
    }


# ── DORA ─────────────────────────────────────────────────────────────────────


def _get_dora(db) -> dict:
    """Approximate DORA metrics from missions data."""
    deploys_week = db.execute(
        "SELECT COUNT(*) AS n FROM missions"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '7 days'"
    ).fetchone()
    deploys_today = db.execute(
        "SELECT COUNT(*) AS n FROM missions"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '1 day'"
    ).fetchone()
    # Lead time: avg(completed_at - created_at) for completed missions this week
    lt_row = db.execute(
        "SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / 3600) AS avg_h"
        " FROM missions"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '7 days'"
    ).fetchone()
    return {
        "deploy_freq_day": round((deploys_week["n"] or 0) / 7, 1)
        if deploys_week
        else 0,
        "deploys_today": deploys_today["n"] if deploys_today else 0,
        "lead_time_h": round(lt_row["avg_h"] or 0, 1)
        if lt_row and lt_row["avg_h"]
        else None,
        "mttr_min": None,
    }
