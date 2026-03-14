"""Cockpit — SF global summary endpoint.

Aggregates all SF state into a single JSON payload for the /cockpit dashboard:
pipeline stats, environments, daemons, LLM providers, projects, activity feed,
TMA, incidents, DORA metrics.
"""
# Ref: feat-cockpit

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

    # ── Pattern stats ────────────────────────────────────────────────
    pattern_stats = _safe(lambda: _get_pattern_stats(db), {})

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
        "pattern_stats": pattern_stats,
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
        " FROM epics"
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
        "SELECT COUNT(*) AS n FROM epics"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '1 day'"
    ).fetchone()
    # Epic run stats (24h)
    run_stats = _safe(
        lambda: db.execute(
            "SELECT"
            "  COUNT(*) FILTER (WHERE status='completed') AS completed_24h,"
            "  COUNT(*) FILTER (WHERE status='failed') AS failed_24h,"
            "  COUNT(*) FILTER (WHERE status='cancelled') AS cancelled_24h,"
            "  COUNT(*) AS total_24h,"
            "  COALESCE(AVG(llm_cost_usd) FILTER (WHERE status='completed' AND llm_cost_usd IS NOT NULL), 0) AS avg_cost_usd"
            " FROM epic_runs"
            " WHERE created_at >= NOW() - INTERVAL '24 hours'"
        ).fetchone(),
        None,
    )
    top_failing = _safe(
        lambda: db.execute(
            "SELECT workflow_id, COUNT(*) AS fail_count"
            " FROM epic_runs"
            " WHERE status='failed' AND created_at >= NOW() - INTERVAL '24 hours'"
            " GROUP BY workflow_id ORDER BY fail_count DESC LIMIT 5"
        ).fetchall(),
        [],
    )
    adv_stats = _safe(
        lambda: db.execute(
            "SELECT check_type, COUNT(*) AS cnt,"
            " SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS rejects"
            " FROM adversarial_events"
            " WHERE created_at >= NOW() - INTERVAL '24 hours'"
            " GROUP BY check_type ORDER BY rejects DESC LIMIT 10"
        ).fetchall(),
        [],
    )
    trace_coverage = _safe(
        lambda: db.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN ref_tag != '' THEN 1 ELSE 0 END) AS with_ref"
            " FROM code_traceability"
            " WHERE created_at >= NOW() - INTERVAL '7 days'"
        ).fetchone(),
        None,
    )
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
        # Epic run health (24h)
        "runs_completed_24h": run_stats["completed_24h"] if run_stats else 0,
        "runs_failed_24h": run_stats["failed_24h"] if run_stats else 0,
        "runs_cancelled_24h": run_stats["cancelled_24h"] if run_stats else 0,
        "runs_total_24h": run_stats["total_24h"] if run_stats else 0,
        "runs_avg_cost_usd": round(float(run_stats["avg_cost_usd"]), 4)
        if run_stats
        else 0,
        "top_failing_workflows": [
            {"workflow_id": r["workflow_id"], "fail_count": r["fail_count"]}
            for r in (top_failing or [])
        ],
        # Adversarial guard stats (24h)
        "adv_stats_24h": [
            {"check_type": r["check_type"], "total": r["cnt"], "rejects": r["rejects"]}
            for r in (adv_stats or [])
        ],
        # Traceability coverage (7d)
        "trace_total_7d": trace_coverage["total"] if trace_coverage else 0,
        "trace_with_ref_7d": trace_coverage["with_ref"] if trace_coverage else 0,
    }


# ── Environments ────────────────────────────────────────────────────────────


def _get_environments() -> list[dict]:
    """Read cluster nodes from platform_nodes registry instead of hardcoded envs."""
    from datetime import datetime

    db = None
    rows = []
    try:
        from ....db.migrations import get_db

        db = get_db()
        rows = db.execute(
            "SELECT node_id, role, mode, url, last_seen, status, cpu_pct, mem_pct, version"
            " FROM platform_nodes ORDER BY role DESC, node_id"
        ).fetchall()
    except Exception as _exc:
        logger.warning("_get_environments DB error: %s", _exc)
        rows = []
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    if not rows:
        # Fallback: no nodes registered yet — show static config if env vars set
        results = []
        for id_, name, env_var in [
            ("ovh", "OVH Demo", "OVH_PLATFORM_URL"),
            ("azure", "Azure Prod", "AZURE_PLATFORM_URL"),
        ]:
            url = os.environ.get(env_var, "")
            if url:
                results.append(
                    {
                        "id": id_,
                        "name": name,
                        "url": url,
                        "status": "not_configured",
                        "version": None,
                    }
                )
        return results

    now = datetime.utcnow()
    results = []
    for r in rows:
        db_status = r["status"] or "unknown"
        try:
            last_seen_dt = datetime.fromisoformat(
                str(r["last_seen"]).replace("Z", "").split(".")[0]
            )
            age_s = int((now - last_seen_dt).total_seconds())
            # Consider online if DB says so AND heartbeat within last 3 minutes
            is_online = db_status == "online" and age_s < 180
        except Exception:
            age_s = 9999
            is_online = db_status == "online"
        role = r["role"] or ""
        mode = r["mode"] or ""
        name = f"{r['node_id']} ({role}/{mode})"
        results.append(
            {
                "id": r["node_id"],
                "name": name,
                "url": r["url"] or "",
                "status": "online" if is_online else "offline",
                "version": r["version"],
                "cpu_pct": round(r["cpu_pct"] or 0, 1),
                "mem_pct": round(r["mem_pct"] or 0, 1),
                "age_s": age_s,
            }
        )
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
    """Return status of configured LLM providers in fallback-chain order.

    WHY: Previously iterated ALL _PROVIDERS and filtered by has_key — this showed
    all 6 providers as '✓ OK' because key files exist locally for all of them.
    Now uses _FALLBACK_CHAIN (the ordered list of providers actually configured for
    this deployment) so the cockpit reflects real production config.
    Shows provider display name + active model instead of just the provider ID.
    """
    try:
        from ....llm.client import get_llm_client, _FALLBACK_CHAIN, _primary, _PROVIDERS

        client = get_llm_client()
    except Exception:
        return []

    now = time.monotonic()
    avail = {p["id"]: p for p in client.available_providers() if p.get("has_key")}
    result = []
    seen: set[str] = set()
    for pid in _FALLBACK_CHAIN:
        if pid in seen or pid not in avail:
            continue
        seen.add(pid)
        pcfg = _PROVIDERS.get(pid, {})
        cb_open = client._cb_open_until.get(pid, 0) > now
        cooldown = client._provider_cooldown.get(pid, 0) > now
        failures = len(client._cb_failures.get(pid, []))
        result.append(
            {
                "provider": pcfg.get("name", pid),
                "model": pcfg.get("default", ""),
                "primary": pid == _primary,
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
        "SELECT p.id, p.name, COALESCE(p.starred, FALSE) AS starred,"
        "  COALESCE(p.container_url, '') AS container_url,"
        "  COUNT(m.id) AS total_missions,"
        "  COUNT(m.id) FILTER (WHERE m.status IN ('active','running')) AS active_missions,"
        "  COUNT(m.id) FILTER (WHERE m.status='completed') AS done_missions,"
        "  MAX(m.created_at) AS last_activity"
        " FROM projects p"
        " LEFT JOIN epics m ON m.project_id = p.id"
        " GROUP BY p.id, p.name, p.starred, p.container_url"
        " ORDER BY p.starred DESC NULLS LAST, last_activity DESC NULLS LAST"
        " LIMIT 12"
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
                "starred": bool(r["starred"]),
                "container_url": r["container_url"] or "",
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
            "SELECT COUNT(*) AS n FROM epics"
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
        "SELECT COUNT(*) AS n FROM epics"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '7 days'"
    ).fetchone()
    deploys_today = db.execute(
        "SELECT COUNT(*) AS n FROM epics"
        " WHERE status='completed'"
        " AND completed_at >= NOW() - INTERVAL '1 day'"
    ).fetchone()
    # Lead time: avg(completed_at - created_at) for completed missions this week
    lt_row = db.execute(
        "SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / 3600) AS avg_h"
        " FROM epics"
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


def _get_pattern_stats(db) -> dict:
    """Top-5 patterns by usage + overall success rate from phase_outcomes."""
    rows = db.execute("""
        SELECT pattern_id,
               COUNT(*) as runs,
               ROUND(100.0 * SUM(success) / GREATEST(COUNT(*), 1), 0) as success_pct,
               ROUND(AVG(quality_score), 2) as avg_quality,
               ROUND(AVG(duration_secs), 0) as avg_s
        FROM phase_outcomes
        GROUP BY pattern_id
        ORDER BY runs DESC
        LIMIT 5
    """).fetchall()
    top = [dict(r) for r in rows]
    total = db.execute("SELECT COUNT(*) as n FROM phase_outcomes").fetchone()
    return {
        "total_runs": int(total["n"]) if total else 0,
        "top": top,
    }
