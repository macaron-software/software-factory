"""DORA metrics, burndown, velocity, cycle-time, pipeline & releases endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from ...schemas import DoraMetrics
from ..helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/metrics/tab/dora", response_class=HTMLResponse)
async def metrics_tab_dora(request: Request):
    """DORA metrics tab partial."""
    from ....metrics.dora import get_dora_metrics
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    project_id = request.query_params.get("project", "")
    period = int(request.query_params.get("period", "30"))

    dora = get_dora_metrics()
    try:
        summary = dora.summary(project_id, period)
    except Exception:
        summary = {}
    try:
        trend = dora.trend(project_id, weeks=12)
    except Exception:
        trend = {"deploy": [], "lead_time": [], "failure": [], "mttr": []}

    return _templates(request).TemplateResponse(
        "_partial_dora.html",
        {
            "request": request,
            "projects": projects,
            "selected_project": project_id,
            "period": period,
            "dora": summary,
            "trend": trend,
        },
    )


@router.get("/metrics/tab/quality", response_class=HTMLResponse)
async def metrics_tab_quality(request: Request):
    """Quality scorecard tab partial."""
    from ....metrics.quality import QualityScanner
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    project_id = request.query_params.get("project_id", "")

    snapshot = QualityScanner.get_latest_snapshot(project_id) if project_id else None
    trend = QualityScanner.get_trend(project_id) if project_id else []
    all_scores = QualityScanner.get_all_projects_scores()

    return _templates(request).TemplateResponse(
        "_partial_quality.html",
        {
            "request": request,
            "projects": projects,
            "selected_project": project_id,
            "snapshot": snapshot,
            "trend": trend,
            "all_scores": all_scores,
        },
    )


@router.get("/metrics/tab/analytics", response_class=HTMLResponse)
async def metrics_tab_analytics(request: Request):
    """Analytics tab partial."""
    return _templates(request).TemplateResponse(
        "_partial_analytics.html", {"request": request}
    )


@router.get("/metrics/tab/monitoring", response_class=HTMLResponse)
async def metrics_tab_monitoring(request: Request):
    """Monitoring tab partial."""
    return _templates(request).TemplateResponse(
        "_partial_monitoring.html", {"request": request}
    )


@router.get("/metrics/tab/pipeline", response_class=HTMLResponse)
async def metrics_tab_pipeline(request: Request):
    """Pipeline performance tab partial."""
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    return _templates(request).TemplateResponse(
        "_partial_pipeline.html",
        {"request": request, "projects": projects},
    )


@router.get("/metrics", response_class=HTMLResponse)
async def dora_dashboard_page(request: Request):
    """Unified Metrics dashboard — DORA, Quality, Analytics, Monitoring, Pipeline."""
    return _templates(request).TemplateResponse(
        "metrics_unified.html",
        {"request": request, "page_title": "Metrics"},
    )


@router.get("/teams", response_class=HTMLResponse)
async def teams_page(request: Request):
    """Darwin team fitness dashboard — leaderboard, OKR, evolution, A/B tests."""
    return _templates(request).TemplateResponse(
        "teams.html",
        {"request": request, "page_title": "Teams"},
    )


@router.get("/teams/partial", response_class=HTMLResponse)
async def teams_partial(request: Request):
    """Teams content partial for HTMX embed (art.html tab)."""
    return _templates(request).TemplateResponse(
        "_partial_teams.html",
        {"request": request},
    )


@router.get("/api/version")
async def version_info():
    """Return current git commit SHA and version info."""
    import subprocess

    def _git(args: list[str]) -> str:
        try:
            return subprocess.check_output(
                ["git"] + args,
                cwd=Path(__file__).parent.parent.parent.parent.parent,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            return ""

    sha = _git(["rev-parse", "--short", "HEAD"])
    sha_full = _git(["rev-parse", "HEAD"])
    tag = _git(["describe", "--tags", "--abbrev=0"]) or ""
    commit_date = _git(["log", "-1", "--format=%ci"])
    commit_msg = _git(["log", "-1", "--format=%s"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])

    return JSONResponse(
        {
            "sha": sha,
            "sha_full": sha_full,
            "tag": tag,
            "branch": branch,
            "commit_date": commit_date,
            "commit_message": commit_msg,
            "display": f"{tag or sha}",
        }
    )


@router.get("/api/metrics/dora/{project_id}", responses={200: {"model": DoraMetrics}})
async def dora_api(request: Request, project_id: str):
    """DORA metrics JSON API."""
    from ....metrics.dora import get_dora_metrics

    period = int(request.query_params.get("period", "30"))
    pid = "" if project_id == "all" else project_id
    return JSONResponse(get_dora_metrics().summary(pid, period))


@router.get("/api/metrics/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    import os

    import psutil

    from ....metrics.collector import get_collector

    c = get_collector()
    snap = c.snapshot()
    proc = psutil.Process(os.getpid())
    lines = []

    def _m(name, value, help_text="", labels=""):
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
        lbl = f"{{{labels}}}" if labels else ""
        lines.append(f"{name}{lbl} {value}")

    _m("macaron_uptime_seconds", snap["uptime_seconds"], "Platform uptime")
    _m(
        "macaron_http_requests_total",
        snap["http"]["total_requests"],
        "Total HTTP requests",
    )
    _m("macaron_http_errors_total", snap["http"]["total_errors"], "Total HTTP errors")
    _m("macaron_http_avg_ms", snap["http"]["avg_ms"], "Average HTTP latency ms")
    for code, cnt in snap["http"].get("by_status", {}).items():
        _m("macaron_http_status", cnt, labels=f'code="{code}"')
    _m("macaron_mcp_calls_total", snap["mcp"]["total_calls"], "Total MCP tool calls")
    _m(
        "macaron_process_cpu_percent",
        round(proc.cpu_percent(interval=0), 1),
        "Process CPU",
    )
    mem = proc.memory_info()
    _m("macaron_process_rss_bytes", mem.rss, "Process RSS bytes")
    _m("macaron_process_threads", proc.num_threads(), "Process threads")
    for provider, stats in snap.get("llm", {}).get("by_provider", {}).items():
        _m("macaron_llm_calls", stats.get("calls", 0), labels=f'provider="{provider}"')
        _m(
            "macaron_llm_cost_usd",
            stats.get("cost_usd", 0),
            labels=f'provider="{provider}"',
        )

    return "\n".join(lines) + "\n"


@router.get("/api/metrics/burndown/{epic_id}")
async def burndown_data(epic_id: str):
    """Get burndown data for an epic — features completed over time."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        total_sp = db.execute(
            "SELECT COALESCE(SUM(story_points),0) FROM features WHERE epic_id=?",
            (epic_id,),
        ).fetchone()[0]
        done_features = db.execute(
            "SELECT name, story_points, completed_at FROM features WHERE epic_id=? AND status='done' AND completed_at IS NOT NULL ORDER BY completed_at",
            (epic_id,),
        ).fetchall()

        points = [
            {"date": r["completed_at"][:10], "sp": r["story_points"], "name": r["name"]}
            for r in done_features
        ]
        remaining = total_sp
        burndown = []
        for p in points:
            remaining -= p["sp"]
            burndown.append(
                {"date": p["date"], "remaining": remaining, "done_name": p["name"]}
            )

        return JSONResponse(
            {
                "total_sp": total_sp,
                "remaining_sp": remaining,
                "completed_count": len(done_features),
                "burndown": burndown,
            }
        )
    finally:
        db.close()


@router.get("/api/metrics/velocity")
async def velocity_data():
    """Get velocity across weeks — from mission_runs completed per week."""
    from datetime import datetime, timedelta

    from ....db.migrations import get_db

    db = get_db()
    try:
        # Last 12 weeks of completed mission runs, grouped by week
        cutoff = (datetime.utcnow() - timedelta(weeks=12)).isoformat()
        rows = db.execute(
            """SELECT completed_at FROM mission_runs
               WHERE status='completed' AND completed_at IS NOT NULL AND completed_at >= ?
               ORDER BY completed_at""",
            (cutoff,),
        ).fetchall()

        # Group by ISO week
        week_counts: dict[str, int] = {}
        for r in rows:
            try:
                dt = datetime.fromisoformat(str(r["completed_at"])[:19])
                wk = dt.strftime("%Y-W%V")
                week_counts[wk] = week_counts.get(wk, 0) + 1
            except Exception:
                pass

        # Build last 12 weeks in order (fill missing with 0)
        result = []
        now = datetime.utcnow()
        for i in range(11, -1, -1):
            dt = now - timedelta(weeks=i)
            wk = dt.strftime("%Y-W%V")
            result.append(
                {
                    "id": wk,
                    "name": wk,
                    "status": "closed",
                    "velocity": week_counts.get(wk, 0),
                    "planned_sp": 0,
                    "started_at": (now - timedelta(weeks=i)).isoformat(),
                }
            )
        return JSONResponse(result)
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.get("/api/metrics/cycle-time")
async def cycle_time_data(project_id: str = ""):
    """Cycle time distribution — time from created to completed for missions."""
    from datetime import datetime

    from ....db.migrations import get_db

    db = get_db()
    try:
        where = "AND m.project_id=?" if project_id else ""
        params = (project_id,) if project_id else ()

        missions = db.execute(
            f"""SELECT m.name, m.created_at, mr.completed_at
                FROM missions m
                JOIN mission_runs mr ON mr.mission_id = m.id
                WHERE mr.status='completed' AND mr.completed_at IS NOT NULL
                  AND m.created_at IS NOT NULL {where}
                ORDER BY mr.completed_at""",
            params,
        ).fetchall()

        feat_days = []
        for r in missions:
            try:
                ca = datetime.fromisoformat(str(r["created_at"])[:19])
                done = datetime.fromisoformat(str(r["completed_at"])[:19])
                d = (done - ca).total_seconds() / 86400
                if d > 0:
                    feat_days.append(round(d, 1))
            except Exception:
                pass

        def histogram(values, bins=10):
            if not values:
                return []
            mn, mx = min(values), max(values)
            if mn == mx:
                return [{"range": f"{mn:.0f}", "count": len(values)}]
            step = (mx - mn) / bins
            result = []
            for i in range(bins):
                lo = mn + step * i
                hi = lo + step
                cnt = (
                    sum(1 for v in values if lo <= v < hi)
                    if i < bins - 1
                    else sum(1 for v in values if lo <= v <= hi)
                )
                result.append({"range": f"{lo:.0f}-{hi:.0f}", "count": cnt})
            return result

        return JSONResponse(
            {
                "features": {
                    "count": len(feat_days),
                    "avg_days": round(sum(feat_days) / len(feat_days), 1)
                    if feat_days
                    else 0,
                    "median_days": round(sorted(feat_days)[len(feat_days) // 2], 1)
                    if feat_days
                    else 0,
                    "p90_days": round(sorted(feat_days)[int(len(feat_days) * 0.9)], 1)
                    if feat_days
                    else 0,
                    "histogram": histogram(feat_days),
                },
                "stories": {"count": 0, "histogram": []},
            }
        )
    except Exception:
        return JSONResponse(
            {
                "features": {"count": 0, "histogram": []},
                "stories": {"count": 0, "histogram": []},
            }
        )
    finally:
        db.close()


@router.get("/api/metrics/pipeline/{mission_id}")
async def pipeline_metrics(mission_id: str):
    """Pipeline metrics for a specific mission run: duration, tool stats, agent performance."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        # Tool call stats
        tool_stats = db.execute(
            "SELECT tool_name, COUNT(*) as total, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok "
            "FROM tool_calls WHERE session_id IN "
            "(SELECT id FROM sessions WHERE mission_run_id=?) "
            "GROUP BY tool_name ORDER BY total DESC",
            (mission_id,),
        ).fetchall()

        # Agent performance
        agent_stats = db.execute(
            "SELECT agent_id, COUNT(*) as messages, "
            "SUM(CASE WHEN role='assistant' THEN 1 ELSE 0 END) as responses "
            "FROM messages WHERE session_id IN "
            "(SELECT id FROM sessions WHERE mission_run_id=?) "
            "GROUP BY agent_id ORDER BY messages DESC",
            (mission_id,),
        ).fetchall()

        # Phase timing
        phases = db.execute(
            "SELECT phase_id, status, started_at, completed_at FROM sessions "
            "WHERE mission_run_id=? ORDER BY created_at",
            (mission_id,),
        ).fetchall()

        # Screenshots count
        from ....missions.store import get_mission_run_store

        store = get_mission_run_store()
        mission = store.get(mission_id)
        screenshot_count = 0
        if mission and mission.workspace_path:
            ws = Path(mission.workspace_path)
            ss_dir = ws / "screenshots"
            if ss_dir.exists():
                screenshot_count = len(list(ss_dir.glob("*.png")))

        # Tickets count
        tickets = db.execute(
            "SELECT status, COUNT(*) as cnt FROM support_tickets "
            "WHERE mission_id=? GROUP BY status",
            (mission_id,),
        ).fetchall()

        total_tools = sum(r["total"] for r in tool_stats)
        ok_tools = sum(r["ok"] for r in tool_stats)

        return JSONResponse(
            {
                "mission_id": mission_id,
                "tools": {
                    "total": total_tools,
                    "success": ok_tools,
                    "rate": round(ok_tools / total_tools * 100, 1)
                    if total_tools
                    else 0,
                    "by_tool": [
                        {"name": r["tool_name"], "total": r["total"], "ok": r["ok"]}
                        for r in tool_stats
                    ],
                },
                "agents": [
                    {
                        "id": r["agent_id"],
                        "messages": r["messages"],
                        "responses": r["responses"],
                    }
                    for r in agent_stats
                ],
                "phases": [
                    {"id": r["phase_id"], "status": r["status"]} for r in phases
                ],
                "screenshots": screenshot_count,
                "tickets": {r["status"]: r["cnt"] for r in tickets},
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/analytics/costs")
async def llm_costs():
    """LLM cost breakdown by provider, mission and agent."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        total = db.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM llm_traces"
        ).fetchone()[0]

        by_provider = db.execute("""
            SELECT t.provider, t.model,
                   COUNT(*) as calls,
                   SUM(t.tokens_in + t.tokens_out) as tokens,
                   COALESCE(SUM(t.cost_usd), 0) as cost_usd
            FROM llm_traces t
            GROUP BY t.provider, t.model
            ORDER BY cost_usd DESC
        """).fetchall()

        by_mission = db.execute("""
            SELECT mission_id,
                   COUNT(*) as calls,
                   SUM(tokens_in + tokens_out) as tokens,
                   COALESCE(SUM(cost_usd), 0) as cost_usd
            FROM llm_traces
            WHERE mission_id != ''
            GROUP BY mission_id
            ORDER BY cost_usd DESC
            LIMIT 10
        """).fetchall()

        by_agent = db.execute("""
            SELECT agent_id,
                   COUNT(*) as calls,
                   SUM(tokens_in + tokens_out) as tokens,
                   COALESCE(SUM(cost_usd), 0) as cost_usd
            FROM llm_traces
            WHERE agent_id != ''
            GROUP BY agent_id
            ORDER BY cost_usd DESC
            LIMIT 10
        """).fetchall()

        daily = db.execute("""
            SELECT substr(created_at, 1, 10) as date,
                   COUNT(*) as calls,
                   COALESCE(SUM(cost_usd), 0) as cost_usd
            FROM llm_traces
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY date
            ORDER BY date
        """).fetchall()

        return JSONResponse(
            {
                "total_cost_usd": round(total, 6),
                "by_provider": [
                    {
                        "provider": r["provider"],
                        "model": r["model"],
                        "calls": r["calls"],
                        "tokens": r["tokens"] or 0,
                        "cost_usd": round(r["cost_usd"], 6),
                    }
                    for r in by_provider
                ],
                "by_mission": [
                    {
                        "mission_id": r["mission_id"],
                        "calls": r["calls"],
                        "tokens": r["tokens"] or 0,
                        "cost_usd": round(r["cost_usd"], 6),
                    }
                    for r in by_mission
                ],
                "by_agent": [
                    {
                        "agent_id": r["agent_id"],
                        "calls": r["calls"],
                        "tokens": r["tokens"] or 0,
                        "cost_usd": round(r["cost_usd"], 6),
                    }
                    for r in by_agent
                ],
                "daily": [
                    {
                        "date": r["date"],
                        "calls": r["calls"],
                        "cost_usd": round(r["cost_usd"], 6),
                    }
                    for r in daily
                ],
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/releases/{project_id}")
async def releases_data(project_id: str):
    """Get release notes — completed mission_runs + active epics with done features."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        releases = []

        # 1. Completed mission_runs as releases (primary source)
        pid_filter = "AND project_id=?" if project_id and project_id != "all" else ""
        params = (project_id,) if project_id and project_id != "all" else ()
        runs = db.execute(
            f"SELECT id, workflow_name, project_id, phases_json, updated_at "
            f"FROM mission_runs WHERE status='completed' {pid_filter} "
            f"ORDER BY updated_at DESC LIMIT 30",
            params,
        ).fetchall()

        import json as _json

        for run in runs:
            try:
                phases = _json.loads(run["phases_json"] or "[]")
            except Exception:
                phases = []
            done_phases = [p["name"] for p in phases if p.get("status") == "completed"]
            releases.append(
                {
                    "epic_id": run["id"],
                    "epic_name": f"{run['workflow_name']} — {run['project_id']}",
                    "completed_at": run["updated_at"],
                    "feature_count": len(done_phases),
                    "total_sp": len(done_phases),
                    "features": [
                        {"name": p, "sp": 1, "date": run["updated_at"]}
                        for p in done_phases
                    ],
                }
            )

        # 2. Active epics with partial completion (backlog view) — skip if tables missing
        try:
            active = db.execute(
                f"SELECT id, name, status FROM missions WHERE type='epic' "
                f"AND status IN ('active','planning') {pid_filter} ORDER BY created_at DESC LIMIT 10",
                params,
            ).fetchall()
            for epic in active:
                try:
                    features = db.execute(
                        "SELECT name, status, story_points, completed_at FROM features WHERE epic_id=? ORDER BY status, completed_at",
                        (epic["id"],),
                    ).fetchall()
                except Exception:
                    features = []
                done = [f for f in features if f["status"] == "done"]
                total = len(features)
                if total == 0:
                    continue
                releases.append(
                    {
                        "epic_id": epic["id"],
                        "epic_name": epic["name"] + " (in progress)",
                        "completed_at": None,
                        "feature_count": total,
                        "done_count": len(done),
                        "progress_pct": round(len(done) / total * 100) if total else 0,
                        "total_sp": sum(f["story_points"] or 0 for f in features),
                        "features": [
                            {
                                "name": f["name"],
                                "sp": f["story_points"],
                                "status": f["status"],
                                "date": f["completed_at"],
                            }
                            for f in features
                        ],
                    }
                )
        except Exception:
            pass  # missions/features tables may not exist yet

        import datetime as _dt

        def _serial(obj):
            if isinstance(obj, (_dt.datetime, _dt.date)):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        return JSONResponse(
            content=_json.loads(
                _json.dumps(
                    {"project_id": project_id, "releases": releases}, default=_serial
                )
            )
        )
    except Exception as exc:
        return JSONResponse(
            {"project_id": project_id, "releases": [], "error": str(exc)}
        )
    finally:
        db.close()
