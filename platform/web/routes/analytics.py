"""
Analytics API — Real-time metrics and insights
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================


class SkillsTopResponse(BaseModel):
    """Top skills used."""

    success: bool
    data: list[dict[str, Any]]


class SkillsHeatmapResponse(BaseModel):
    """Heatmap data for domains × roles."""

    success: bool
    data: dict[str, Any]


class MissionsStatusResponse(BaseModel):
    """Missions status distribution."""

    success: bool
    data: dict[str, Any]


class AgentsLeaderboardResponse(BaseModel):
    """Agents performance leaderboard."""

    success: bool
    data: list[dict[str, Any]]


class TMAOverviewResponse(BaseModel):
    """TMA tickets overview."""

    success: bool
    data: dict[str, Any]


class SystemHealthResponse(BaseModel):
    """System health metrics."""

    success: bool
    data: dict[str, Any]


# =============================================================================
# Skills Analytics
# =============================================================================


@router.get("/api/analytics/skills/top", response_model=SkillsTopResponse)
async def get_top_skills(limit: int = 10) -> SkillsTopResponse:
    """Get top N most used skills."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Count how many agents use each skill (via skills_json)
        # skills table: id, name, source
        query = """
            SELECT
                s.id,
                s.name  AS title,
                s.source,
                COUNT(DISTINCT a.id) as usage_count,
                s.updated_at as last_used
            FROM skills s
            LEFT JOIN agents a ON a.skills_json LIKE '%' || s.id || '%'
            GROUP BY s.id, s.name, s.source, s.updated_at
            ORDER BY usage_count DESC, s.name ASC
            LIMIT ?
        """

        results = db.execute(query, (limit,)).fetchall()

        skills_data = [
            {
                "id": row["id"] if hasattr(row, "keys") else row[0],
                "title": row["title"] if hasattr(row, "keys") else row[1],
                "source": row["source"] if hasattr(row, "keys") else row[2],
                "usage_count": row["usage_count"] if hasattr(row, "keys") else row[3],
                "last_used": str(row["last_used"] if hasattr(row, "keys") else row[4]),
            }
            for row in results
        ]

        return SkillsTopResponse(success=True, data=skills_data)

    except Exception:
        logger.exception("Error getting top skills")
        return SkillsTopResponse(success=False, data=[])


@router.get("/api/analytics/skills/heatmap", response_model=SkillsHeatmapResponse)
async def get_skills_heatmap() -> SkillsHeatmapResponse:
    """Get heatmap of domain × role skills usage."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Query skills usage by domain and role
        # Domain extracted from metadata JSON, role from agent
        query = """
            SELECT 
                json_extract(si.metadata, '$.domain') as domain,
                su.agent_role,
                COUNT(*) as count
            FROM skills_usage su
            JOIN skills_index si ON su.skill_id = si.id
            WHERE domain IS NOT NULL AND su.agent_role IS NOT NULL
            GROUP BY domain, su.agent_role
            ORDER BY count DESC
        """

        results = db.execute(query).fetchall()

        # Format as heatmap data
        heatmap_data = {}
        for row in results:
            domain = row[0] or "unknown"
            role = row[1] or "unknown"
            count = row[2]

            if domain not in heatmap_data:
                heatmap_data[domain] = {}
            heatmap_data[domain][role] = count

        return SkillsHeatmapResponse(
            success=True, data={"heatmap": heatmap_data, "total": len(results)}
        )

    except Exception:
        logger.exception("Error getting skills heatmap")
        return SkillsHeatmapResponse(success=False, data={})


@router.get("/api/analytics/skills/cache-stats")
async def get_skills_cache_stats() -> dict[str, Any]:
    """Get LLM cache statistics (replaces skills_cache which is SQLite-only)."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        total_cache = db.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        total_hits = (
            db.execute("SELECT SUM(hit_count) FROM llm_cache").fetchone()[0] or 0
        )

        return {
            "success": True,
            "data": {
                "total_cached_contexts": total_cache,
                "total_cache_hits": int(total_hits),
                "avg_skills_per_context": 0,
                "hit_rate": (
                    round(total_hits / total_cache * 100, 2) if total_cache > 0 else 0
                ),
            },
        }

    except Exception:
        logger.exception("Error getting cache stats")
        return {"success": False, "data": {}}


# =============================================================================
# Missions Analytics
# =============================================================================


@router.get("/api/analytics/missions/status", response_model=MissionsStatusResponse)
async def get_missions_status() -> MissionsStatusResponse:
    """Get missions distribution by status."""
    try:
        from ...epics.store import get_epic_store

        store = get_epic_store()
        missions = store.list_missions(limit=1000)

        # Count by status
        status_counts = {}
        for mission in missions:
            status = getattr(mission, "status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate total and percentages
        total = len(missions)
        status_data = [
            {
                "status": status,
                "count": count,
                "percentage": round(count / total * 100, 1) if total > 0 else 0,
            }
            for status, count in sorted(
                status_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

        return MissionsStatusResponse(
            success=True, data={"total": total, "by_status": status_data}
        )

    except Exception:
        logger.exception("Error getting missions status")
        return MissionsStatusResponse(success=False, data={})


@router.get("/api/analytics/missions/performance")
async def get_missions_performance() -> dict[str, Any]:
    """Get missions performance metrics."""
    try:
        from ...epics.store import get_epic_store

        store = get_epic_store()
        missions = store.list_missions(limit=1000)

        # Calculate metrics
        completed = [m for m in missions if getattr(m, "status", "") == "completed"]
        failed = [m for m in missions if getattr(m, "status", "") == "failed"]
        active = [
            m
            for m in missions
            if getattr(m, "status", "") in ["running", "in_progress", "active"]
        ]

        success_rate = (
            round(len(completed) / (len(completed) + len(failed)) * 100, 1)
            if (len(completed) + len(failed)) > 0
            else 0
        )

        return {
            "success": True,
            "data": {
                "total_missions": len(missions),
                "completed": len(completed),
                "failed": len(failed),
                "active": len(active),
                "success_rate": success_rate,
                "backlog_size": len(
                    [m for m in missions if getattr(m, "status", "") == "pending"]
                ),
            },
        }

    except Exception:
        logger.exception("Error getting missions performance")
        return {"success": False, "data": {}}


# =============================================================================
# Agents Analytics
# =============================================================================


@router.get(
    "/api/analytics/agents/leaderboard", response_model=AgentsLeaderboardResponse
)
async def get_agents_leaderboard(limit: int = 10) -> AgentsLeaderboardResponse:
    """Get top performing agents."""
    try:
        from ...agents.store import get_agent_store
        from ...db.migrations import get_db

        agent_store = get_agent_store()
        db = get_db()

        # Get agents with skills usage
        agents = agent_store.list_all()

        leaderboard = []
        for agent in agents[:limit]:
            # Count actual tool calls by this agent
            tool_calls_count = (
                db.execute(
                    "SELECT COUNT(*) FROM tool_calls WHERE agent_id = ?",
                    (agent.id,),
                ).fetchone()[0]
                or 0
            )

            leaderboard.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "description": agent.description or "",
                    "icon": getattr(agent, "icon", "bot"),
                    "color": getattr(agent, "color", "#8b5cf6"),
                    "avatar": getattr(agent, "avatar", ""),
                    "skills_used": tool_calls_count,
                    "skills_available": len(agent.skills or []),
                    "tools_count": len(agent.tools or []),
                }
            )

        # Sort by actual tool calls
        leaderboard.sort(key=lambda x: x["skills_used"], reverse=True)

        return AgentsLeaderboardResponse(success=True, data=leaderboard[:limit])

    except Exception:
        logger.exception("Error getting agents leaderboard")
        return AgentsLeaderboardResponse(success=False, data=[])


@router.get("/api/analytics/agents/utilization")
async def get_agents_utilization() -> dict[str, Any]:
    """Get agents utilization metrics."""
    try:
        from ...agents.store import get_agent_store

        agent_store = get_agent_store()
        agents = agent_store.list_all()

        total_agents = len(agents)
        agents_with_skills = len([a for a in agents if a.skills and len(a.skills) > 0])

        return {
            "success": True,
            "data": {
                "total_agents": total_agents,
                "agents_with_skills": agents_with_skills,
                "utilization_rate": (
                    round(agents_with_skills / total_agents * 100, 1)
                    if total_agents > 0
                    else 0
                ),
            },
        }

    except Exception:
        logger.exception("Error getting agents utilization")
        return {"success": False, "data": {}}


# =============================================================================
# TMA Analytics
# =============================================================================


@router.get("/api/analytics/tma/overview", response_model=TMAOverviewResponse)
async def get_tma_overview() -> TMAOverviewResponse:
    """Get TMA tickets overview."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Count by category
        by_type = db.execute(
            """
            SELECT category as type, COUNT(*) as count
            FROM support_tickets
            WHERE status != 'archived'
            GROUP BY category
            ORDER BY count DESC
        """
        ).fetchall()

        # Count by status
        by_status = db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM support_tickets
            WHERE status != 'archived'
            GROUP BY status
            ORDER BY count DESC
        """
        ).fetchall()

        # Total tickets
        total = db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE status != 'archived'"
        ).fetchone()[0]

        return TMAOverviewResponse(
            success=True,
            data={
                "total": total,
                "by_type": [{"type": row[0], "count": row[1]} for row in by_type],
                "by_status": [{"status": row[0], "count": row[1]} for row in by_status],
            },
        )

    except Exception:
        logger.exception("Error getting TMA overview")
        return TMAOverviewResponse(success=False, data={})


# =============================================================================
# System Health
# =============================================================================


@router.get("/api/analytics/system/health", response_model=SystemHealthResponse)
async def get_system_health() -> SystemHealthResponse:
    """Get system health metrics."""
    try:
        import os
        from ...db.migrations import get_db
        from ...db.adapter import is_postgresql

        db = get_db()

        # Database size
        db_path = "platform.db"
        db_size_mb = (
            os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        )

        # Table list — SQLite vs PostgreSQL
        if is_postgresql():
            tables_raw = db.execute(
                "SELECT tablename as name FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            ).fetchall()
        else:
            tables_raw = db.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name NOT LIKE 'pg_%'"
            ).fetchall()

        table_stats = []
        total_rows = 0
        for row in tables_raw:
            table_name = (
                row[0]
                if not hasattr(row, "keys")
                else (row["name"] if "name" in row.keys() else row["tablename"])
            )
            try:
                count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]  # noqa: S608
                table_stats.append({"table": table_name, "rows": count})
                total_rows += count
            except Exception as e:
                logger.debug(f"Could not count table {table_name}: {e}")

        return SystemHealthResponse(
            success=True,
            data={
                "database": {
                    "size_mb": round(db_size_mb, 2),
                    "tables": len(tables_raw),
                    "total_rows": total_rows,
                },
                "tables": sorted(table_stats, key=lambda x: x["rows"], reverse=True)[
                    :10
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception:
        logger.exception("Error getting system health")
        return SystemHealthResponse(success=False, data={})


@router.get("/api/analytics/overview")
async def get_analytics_overview() -> dict[str, Any]:
    """Get complete analytics overview (dashboard summary)."""
    try:
        # Aggregate key metrics from all endpoints
        top_skills = await get_top_skills(limit=5)
        missions_status = await get_missions_status()
        missions_perf = await get_missions_performance()
        agents_leaderboard = await get_agents_leaderboard(limit=5)
        agents_util = await get_agents_utilization()
        tma_overview = await get_tma_overview()
        system_health = await get_system_health()
        cache_stats = await get_skills_cache_stats()

        leaderboard = agents_leaderboard.data[:5] if agents_leaderboard.success else []
        util_data = agents_util.get("data", {}) if agents_util.get("success") else {}

        return {
            "success": True,
            "data": {
                "skills": {
                    "top": top_skills.data[:5] if top_skills.success else [],
                    "cache": cache_stats.get("data", {}),
                },
                "epics": {
                    "status": missions_status.data if missions_status.success else {},
                    "performance": (
                        missions_perf.get("data", {}) if missions_perf else {}
                    ),
                },
                "agents": {
                    "leaderboard": leaderboard,
                    "utilization": {
                        "total": util_data.get("total_agents", len(leaderboard)),
                        "with_skills": util_data.get("agents_with_skills", 0),
                        "utilization_rate": util_data.get("utilization_rate", 0),
                    },
                },
                "tma": tma_overview.data if tma_overview.success else {},
                "system": system_health.data if system_health.success else {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    except Exception as e:
        logger.exception("Error getting analytics overview")
        return {"success": False, "data": {}, "error": str(e)}


# =============================================================================
# OpenTelemetry / Tracing API
# =============================================================================


@router.get("/api/analytics/tracing/services")
async def get_tracing_services() -> dict[str, Any]:
    """List services reporting traces to Jaeger."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    jaeger_ui = endpoint.replace(":4317", ":16686").replace(":4318", ":16686")
    if not jaeger_ui:
        return {"success": False, "error": "OTEL not configured", "data": []}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{jaeger_ui}/api/services")
            data = resp.json()
            return {
                "success": True,
                "data": data.get("data", []),
                "jaeger_ui": jaeger_ui,
            }
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@router.get("/api/analytics/tracing/traces")
async def get_tracing_traces(
    service: str = "macaron-prod",
    limit: int = 20,
    lookback: str = "1h",
) -> dict[str, Any]:
    """Get recent traces from Jaeger for a service."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    jaeger_ui = endpoint.replace(":4317", ":16686").replace(":4318", ":16686")
    if not jaeger_ui:
        return {"success": False, "error": "OTEL not configured", "data": []}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{jaeger_ui}/api/traces",
                params={"service": service, "limit": limit, "lookback": lookback},
            )
            raw = resp.json()
            traces = []
            for t in raw.get("data", []):
                spans = t.get("spans", [])
                if not spans:
                    continue
                root = spans[0]
                duration_us = root.get("duration", 0)
                traces.append(
                    {
                        "traceID": t.get("traceID", ""),
                        "operation": root.get("operationName", "?"),
                        "duration_ms": round(duration_us / 1000, 1),
                        "spans_count": len(spans),
                        "start": root.get("startTime", 0),
                        "tags": {
                            tag["key"]: tag["value"]
                            for tag in root.get("tags", [])
                            if tag["key"]
                            in ("http.method", "http.status_code", "http.url")
                        },
                    }
                )
            return {"success": True, "data": traces, "total": len(traces)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@router.get("/api/analytics/tracing/stats")
async def get_tracing_stats(
    service: str = "macaron-prod", lookback: str = "1h"
) -> dict[str, Any]:
    """Compute latency stats (p50/p95/p99, throughput, errors) from Jaeger traces."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    jaeger_ui = endpoint.replace(":4317", ":16686").replace(":4318", ":16686")
    if not jaeger_ui:
        return {"success": False, "error": "OTEL not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{jaeger_ui}/api/traces",
                params={"service": service, "limit": 200, "lookback": lookback},
            )
            raw = resp.json()

        durations = []
        errors = 0
        ops: dict[str, list[float]] = {}
        for t in raw.get("data", []):
            spans = t.get("spans", [])
            if not spans:
                continue
            root = spans[0]
            d_ms = root.get("duration", 0) / 1000
            durations.append(d_ms)
            op = root.get("operationName", "?")
            ops.setdefault(op, []).append(d_ms)
            for tag in root.get("tags", []):
                if tag["key"] == "http.status_code" and int(tag.get("value", 0)) >= 400:
                    errors += 1

        if not durations:
            return {"success": True, "data": {"traces": 0}}

        durations.sort()
        n = len(durations)
        return {
            "success": True,
            "data": {
                "traces": n,
                "errors": errors,
                "error_rate": round(errors * 100 / n, 1),
                "latency": {
                    "p50": round(durations[n // 2], 1),
                    "p95": round(durations[int(n * 0.95)], 1),
                    "p99": round(durations[int(n * 0.99)], 1),
                    "avg": round(sum(durations) / n, 1),
                    "max": round(max(durations), 1),
                },
                "top_operations": [
                    {
                        "operation": op,
                        "count": len(ds),
                        "avg_ms": round(sum(ds) / len(ds), 1),
                        "p95_ms": round(sorted(ds)[int(len(ds) * 0.95)], 1)
                        if len(ds) > 1
                        else round(ds[0], 1),
                    }
                    for op, ds in sorted(ops.items(), key=lambda x: -len(x[1]))[:10]
                ],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Pipeline Failure Analysis API
# =============================================================================


@router.get("/api/analytics/failures")
async def get_failure_analysis() -> dict[str, Any]:
    """Analyze failed mission runs — classify errors and suggest fixes."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # 1. Error category classification (Python-based for accuracy)
        all_failed = db.execute(
            "SELECT id, phases_json FROM epic_runs WHERE status = 'failed'"
        ).fetchall()

        cat_counts: dict[str, int] = {}
        for row in all_failed:
            blob = (row["phases_json"] or "").lower()
            import json as _jc

            phases = _jc.loads(row["phases_json"] or "[]")
            statuses = set(p.get("status", "") for p in phases) if phases else set()

            if not phases or blob in ("[]", "", "null"):
                cat = "no_phases"
            elif statuses == {"pending"} or statuses <= {"pending", ""}:
                cat = "setup_failed"
            elif "all llm providers failed" in blob:
                cat = "llm_all_failed"
            elif "timeout" in blob or "timed out" in blob:
                cat = "timeout"
            elif "429" in blob or "rate limit" in blob:
                cat = "rate_limit"
            elif "llm" in blob and ("error" in blob or "fail" in blob):
                cat = "llm_error"
            elif "tool" in blob and "error" in blob:
                cat = "tool_error"
            elif "connection refused" in blob or "network" in blob:
                cat = "network"
            elif "no pattern" in blob or "not found" in blob:
                cat = "config_error"
            else:
                cat = "other"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        categories_list = sorted(cat_counts.items(), key=lambda x: -x[1])

        # 2. Phase failure heatmap — which phases fail most
        phase_failures = []
        rows = db.execute("""
            SELECT id, phases_json FROM epic_runs
            WHERE status IN ('failed', 'paused') AND phases_json != '[]'
        """).fetchall()

        phase_stats: dict[str, dict] = {}
        for row in rows:
            import json as _json

            phases = _json.loads(row["phases_json"] or "[]")
            for ph in phases:
                name = ph.get("phase_name", ph.get("name", "unknown"))
                if name not in phase_stats:
                    phase_stats[name] = {
                        "total": 0,
                        "failed": 0,
                        "timeout": 0,
                        "errors": [],
                    }
                phase_stats[name]["total"] += 1
                status = ph.get("status", "")
                if status == "failed":
                    phase_stats[name]["failed"] += 1
                    summary = ph.get("summary", "")[:100]
                    if summary and len(phase_stats[name]["errors"]) < 3:
                        phase_stats[name]["errors"].append(summary)
                if "timeout" in (ph.get("summary", "") or "").lower():
                    phase_stats[name]["timeout"] += 1

        phase_failures = sorted(
            [
                {
                    "phase": name,
                    "total": s["total"],
                    "failed": s["failed"],
                    "timeout": s["timeout"],
                    "fail_rate": round(s["failed"] * 100 / max(s["total"], 1), 1),
                    "sample_errors": s["errors"][:2],
                }
                for name, s in phase_stats.items()
            ],
            key=lambda x: -x["failed"],
        )

        # 3. Resumable runs — paused runs that can be auto-resumed
        resumable = db.execute("""
            SELECT COUNT(*) as cnt FROM epic_runs mr
            JOIN sessions s ON mr.session_id = s.id
            WHERE mr.status = 'paused'
            AND s.status IN ('interrupted', 'paused', 'active')
        """).fetchone()

        # 4. Run status summary
        run_stats = db.execute("""
            SELECT status, COUNT(*) as cnt FROM epic_runs GROUP BY status
        """).fetchall()

        # 5. Recent failures (last 20)
        recent = db.execute("""
            SELECT mr.id, mr.workflow_name, mr.current_phase, mr.status,
                   mr.created_at, mr.updated_at
            FROM epic_runs mr
            WHERE mr.status = 'failed'
            ORDER BY mr.updated_at DESC LIMIT 20
        """).fetchall()

        db.close()

        return {
            "success": True,
            "data": {
                "error_categories": [
                    {"category": cat, "count": cnt} for cat, cnt in categories_list
                ],
                "phase_failures": phase_failures[:15],
                "resumable_count": resumable["cnt"] if resumable else 0,
                "run_status": {r["status"]: r["cnt"] for r in run_stats},
                "recent_failures": [
                    {
                        "id": r["id"][:12],
                        "workflow": r["workflow_name"],
                        "phase": r["current_phase"],
                        "updated": r["updated_at"],
                    }
                    for r in recent
                ],
                "recommendations": _generate_recommendations(
                    [{"category": c, "cnt": n} for c, n in categories_list],
                    phase_failures,
                ),
            },
        }
    except Exception as e:
        logger.exception("Failure analysis error")
        return {"success": False, "error": str(e)}


@router.post("/api/analytics/failures/resume-all")
async def resume_all_paused() -> dict[str, Any]:
    """Mass-resume all paused runs that can be continued."""
    try:
        from ...db.migrations import get_db
        from ...workflows.store import get_workflow_store, run_workflow

        db = get_db()

        paused = db.execute("""
            SELECT mr.session_id, mr.id, s.config_json
            FROM epic_runs mr
            JOIN sessions s ON mr.session_id = s.id
            WHERE mr.status = 'paused'
            AND s.status IN ('interrupted', 'paused')
            ORDER BY mr.updated_at DESC LIMIT 30
        """).fetchall()

        resumed = 0
        errors = 0
        for row in paused:
            try:
                import json as _json
                import asyncio

                config = _json.loads(row["config_json"]) if row["config_json"] else {}
                wf_id = config.get("workflow_id", "")
                if not wf_id:
                    continue

                wf = get_workflow_store().get(wf_id)
                if not wf:
                    continue

                checkpoint = config.get("workflow_checkpoint", 0)
                proj_id = config.get("project_id", "")
                task = config.get("task", config.get("brief", "Resume"))
                sid = row["session_id"]

                db.execute("UPDATE sessions SET status='active' WHERE id=?", (sid,))
                db.execute(
                    "UPDATE epic_runs SET status='running' WHERE session_id=?",
                    (sid,),
                )
                db.commit()

                asyncio.create_task(
                    run_workflow(wf, sid, task, proj_id, resume_from=checkpoint)
                )
                resumed += 1
            except Exception as e:
                logger.warning("Resume failed for %s: %s", row["id"][:8], e)
                errors += 1

        db.close()
        return {
            "success": True,
            "resumed": resumed,
            "errors": errors,
            "total_paused": len(paused),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _generate_recommendations(
    categories: list[dict], phase_failures: list[dict]
) -> list[str]:
    """Generate actionable recommendations from failure patterns."""
    recs = []
    cat_map = {c["category"]: c["cnt"] for c in categories}

    if cat_map.get("llm_all_failed", 0) > 3:
        recs.append(
            f"🔴 {cat_map['llm_all_failed']} runs failed — All LLM providers down. Check API keys, model names, and provider health."
        )
    if cat_map.get("rate_limit", 0) > 5:
        recs.append(
            f"🔴 {cat_map['rate_limit']} rate limit errors — increase LLM cooldown or add provider fallback"
        )
    if cat_map.get("timeout", 0) > 5:
        recs.append(
            f"🟡 {cat_map['timeout']} timeouts — increase PHASE_TIMEOUT or optimize agent prompts"
        )
    if cat_map.get("llm_error", 0) > 3:
        recs.append(
            f"🔴 {cat_map['llm_error']} LLM errors — check API keys and provider health"
        )
    if cat_map.get("config_error", 0) > 2:
        recs.append(
            f"🟡 {cat_map['config_error']} config errors — missing patterns or workflows"
        )
    if cat_map.get("no_phases", 0) > 5:
        recs.append(
            f"🟡 {cat_map['no_phases']} runs failed before any phase started — check workflow setup"
        )
    if cat_map.get("setup_failed", 0) > 5:
        recs.append(
            f"🟡 {cat_map['setup_failed']} runs failed during setup (all phases pending) — "
            f"check workspace creation, session init, or early LLM errors"
        )

    # Phase-specific recommendations
    for pf in phase_failures[:3]:
        if pf["fail_rate"] > 50:
            recs.append(
                f"⚠️ Phase '{pf['phase']}' fails {pf['fail_rate']}% — needs retry or skip_on_failure"
            )

    if not recs:
        recs.append("✅ No critical failure patterns detected")

    return recs


@router.get("/api/analytics/agents/scores")
async def get_agent_scores() -> dict[str, Any]:
    """Thompson Sampling scores per agent — built from llm_traces (live) + agent_scores (veto)."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Ensure agent_scores table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_scores (
                agent_id TEXT NOT NULL,
                epic_id TEXT NOT NULL DEFAULT '',
                accepted INTEGER NOT NULL DEFAULT 0,
                rejected INTEGER NOT NULL DEFAULT 0,
                iterations INTEGER NOT NULL DEFAULT 0,
                quality_score REAL NOT NULL DEFAULT 0.5,
                PRIMARY KEY (agent_id, epic_id)
            )
        """)

        # Primary source: llm_traces — real per-agent/model performance data
        trace_rows = db.execute("""
            SELECT
                t.agent_id,
                COALESCE(a.name, t.agent_id) as agent_name,
                t.provider,
                t.model,
                COUNT(*) as iterations,
                SUM(CASE WHEN t.status='ok' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN t.status!='ok' THEN 1 ELSE 0 END) as rejected,
                ROUND(CAST(AVG(t.duration_ms) AS NUMERIC)) as avg_duration_ms,
                SUM(t.tokens_in + t.tokens_out) as total_tokens,
                ROUND(CAST(SUM(t.cost_usd) AS NUMERIC), 4) as total_cost,
                ROUND(CAST(100.0 * SUM(CASE WHEN t.status='ok' THEN 1 ELSE 0 END) /
                    (COUNT(*) + 0.001) AS NUMERIC), 1) as success_pct,
                ROUND(CAST(100.0 * SUM(CASE WHEN t.status!='ok' THEN 1 ELSE 0 END) /
                    (COUNT(*) + 0.001) AS NUMERIC), 1) as rejection_pct,
                0.0 as quality_score
            FROM llm_traces t
            LEFT JOIN agents a ON a.id = t.agent_id
            WHERE t.agent_id != ''
            GROUP BY t.agent_id, COALESCE(a.name, t.agent_id), t.provider, t.model
            ORDER BY iterations DESC
        """).fetchall()

        # Provider-level A/B summary from llm_traces
        provider_rows = db.execute("""
            SELECT
                t.provider,
                t.model,
                COUNT(*) as calls,
                SUM(CASE WHEN t.status='ok' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN t.status!='ok' THEN 1 ELSE 0 END) as rejected,
                ROUND(CAST(AVG(t.duration_ms) AS NUMERIC)) as avg_duration_ms,
                ROUND(CAST(SUM(t.cost_usd) AS NUMERIC), 4) as total_cost,
                ROUND(CAST(100.0 * SUM(CASE WHEN t.status='ok' THEN 1 ELSE 0 END) /
                    (COUNT(*) + 0.001) AS NUMERIC), 1) as success_pct
            FROM llm_traces t
            GROUP BY t.provider, t.model
            ORDER BY calls DESC
        """).fetchall()

        # Darwin team fitness (accumulates as missions complete)
        try:
            fitness_rows = db.execute("""
                SELECT
                    f.agent_id,
                    COALESCE(a.name, f.agent_id) as agent_name,
                    f.pattern_id,
                    f.technology,
                    f.phase_type,
                    f.wins,
                    f.losses,
                    ROUND(CAST(f.fitness_score AS NUMERIC), 1) as fitness_score,
                    f.updated_at
                FROM team_fitness f
                LEFT JOIN agents a ON a.id = f.agent_id
                ORDER BY f.fitness_score DESC
                LIMIT 50
            """).fetchall()
        except Exception:
            fitness_rows = []

        db.close()

        agents = [dict(r) for r in trace_rows]
        providers = [dict(r) for r in provider_rows]
        fitness = [dict(r) for r in fitness_rows]
        high_rejection = [a for a in agents if a["rejection_pct"] > 40]

        return {
            "success": True,
            "agents": agents,
            "providers": providers,
            "fitness": fitness,
            "summary": {
                "total_agents": len(agents),
                "total_accepted": sum(a["accepted"] for a in agents),
                "total_rejected": sum(a["rejected"] for a in agents),
                "total_calls": sum(a["iterations"] for a in agents),
                "high_rejection_count": len(high_rejection),
                "high_rejection_agents": [a["agent_id"] for a in high_rejection],
            },
        }
    except Exception as e:
        logger.exception("Agent scores error")
        return {"success": False, "error": str(e)}


@router.get("/api/analytics/patterns")
async def get_pattern_analytics() -> dict[str, Any]:
    """Pattern observability: usage counts, success rates, quality, timing per pattern.

    Aggregates phase_outcomes (written by engine.py run_pattern() on every execution).
    Includes top-3 agents per pattern from team_fitness table.
    Also returns per-epic pattern trace via epic_runs.pattern_type.

    WHY: phase_outcomes was always written in epic_orchestrator but never in engine.py
    directly. Fixed 2026-03 — now every run_pattern() call produces a row.
    """
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Per-pattern aggregate stats
        pattern_rows = db.execute("""
            SELECT
                pattern_id,
                COUNT(*) as total_runs,
                ROUND(100.0 * SUM(success) / GREATEST(COUNT(*), 1), 1) as success_rate,
                ROUND(AVG(quality_score), 3) as avg_quality,
                ROUND(AVG(duration_secs), 1) as avg_duration_s,
                SUM(rejection_count) as total_rejections,
                ROUND(AVG(team_size), 1) as avg_team_size,
                MAX(created_at) as last_used
            FROM phase_outcomes
            GROUP BY pattern_id
            ORDER BY total_runs DESC
        """).fetchall()

        patterns = [dict(r) for r in pattern_rows]

        # Top agents per pattern (team_fitness)
        fitness_rows = db.execute("""
            SELECT pattern_id, agent_id, fitness_score, runs, wins
            FROM team_fitness
            ORDER BY pattern_id, fitness_score DESC
        """).fetchall()
        from collections import defaultdict

        agents_by_pattern: dict[str, list] = defaultdict(list)
        for r in fitness_rows:
            if len(agents_by_pattern[r["pattern_id"]]) < 3:
                agents_by_pattern[r["pattern_id"]].append(
                    {
                        "agent_id": r["agent_id"],
                        "fitness": round(float(r["fitness_score"]), 2),
                        "runs": r["runs"],
                        "wins": r["wins"],
                    }
                )
        for p in patterns:
            p["top_agents"] = agents_by_pattern.get(p["pattern_id"], [])

        # Per-epic pattern trace: Jarvis -> epic -> pattern
        chain_rows = db.execute("""
            SELECT
                e.id as epic_id,
                e.workflow_name,
                e.pattern_type,
                e.status,
                e.project_id,
                e.cdp_agent_id as launched_by,
                e.created_at,
                e.llm_cost_usd,
                COUNT(po.id) as phase_count,
                ROUND(AVG(po.quality_score), 3) as avg_quality
            FROM epic_runs e
            LEFT JOIN phase_outcomes po ON po.mission_id = e.session_id
            WHERE e.pattern_type IS NOT NULL AND e.pattern_type != ''
            GROUP BY e.id
            ORDER BY e.created_at DESC
            LIMIT 50
        """).fetchall()
        chain = [dict(r) for r in chain_rows]

        # Summary
        total_runs = sum(p["total_runs"] for p in patterns)
        overall_success = (
            round(
                sum(p["success_rate"] * p["total_runs"] for p in patterns)
                / max(total_runs, 1),
                1,
            )
            if patterns
            else 0.0
        )

        db.close()
        return {
            "success": True,
            "patterns": patterns,
            "chain": chain,
            "summary": {
                "total_pattern_runs": total_runs,
                "patterns_used": len(patterns),
                "overall_success_rate": overall_success,
                "data_since": patterns[-1]["last_used"] if patterns else None,
            },
        }
    except Exception as e:
        logger.exception("Pattern analytics error")
        return {"success": False, "error": str(e)}


@router.get("/api/analytics/patterns/vetoes")
async def pattern_veto_analytics() -> JSONResponse:
    """Veto analytics per pattern — which agents veto most, which patterns have most rejections.
    WHY: rejection_count captured in phase_outcomes; surfacing it enables tuning GuardrailsPattern
    and identifying over-aggressive safety agents.
    Ref: SF pattern observability, 2026-03.
    """
    try:
        from ....db.migrations import get_db

        db = get_db()
        # Per-pattern rejection summary
        pattern_rows = db.execute("""
            SELECT
                pattern_id,
                COUNT(*) AS runs,
                SUM(rejection_count) AS total_vetoes,
                ROUND(AVG(rejection_count), 2) AS avg_vetoes_per_run,
                MAX(rejection_count) AS max_vetoes,
                ROUND(100.0 * SUM(CASE WHEN rejection_count > 0 THEN 1 ELSE 0 END)
                      / GREATEST(COUNT(*), 1), 0) AS pct_runs_with_veto
            FROM phase_outcomes
            GROUP BY pattern_id
            ORDER BY total_vetoes DESC
            LIMIT 20
        """).fetchall()
        patterns = [dict(r) for r in pattern_rows]

        # Top agents by veto count (from agent_scores join on session context)
        # Use team_fitness table which tracks agent performance per session
        agent_rows = db.execute("""
            SELECT
                po.pattern_id,
                tf.agent_id,
                COUNT(*) AS sessions_with_veto,
                ROUND(AVG(po.rejection_count), 2) AS avg_vetoes
            FROM phase_outcomes po
            JOIN team_fitness tf ON tf.session_id = po.mission_id
            WHERE po.rejection_count > 0
            GROUP BY po.pattern_id, tf.agent_id
            ORDER BY sessions_with_veto DESC
            LIMIT 30
        """).fetchall()

        # Group agents by pattern
        from collections import defaultdict

        by_pattern: dict[str, list] = defaultdict(list)
        for r in agent_rows:
            d = dict(r)
            by_pattern[d["pattern_id"]].append(
                {
                    "agent_id": d["agent_id"],
                    "sessions_with_veto": d["sessions_with_veto"],
                    "avg_vetoes": d["avg_vetoes"],
                }
            )

        db.close()
        return JSONResponse(
            {
                "success": True,
                "patterns": patterns,
                "top_vetoing_agents": dict(by_pattern),
            }
        )
    except Exception as e:
        logger.exception("Veto analytics error")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
