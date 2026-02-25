"""
Analytics API — Real-time metrics and insights
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
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

        # Query skills usage with counts
        query = """
            SELECT 
                si.id,
                si.title,
                si.source,
                COUNT(su.id) as usage_count,
                MAX(su.used_at) as last_used
            FROM skills_index si
            LEFT JOIN skills_usage su ON si.id = su.skill_id
            GROUP BY si.id, si.title, si.source
            HAVING usage_count > 0
            ORDER BY usage_count DESC
            LIMIT ?
        """

        results = db.execute(query, (limit,)).fetchall()

        skills_data = [
            {
                "id": row[0],
                "title": row[1],
                "source": row[2],
                "usage_count": row[3],
                "last_used": row[4],
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
    """Get skills cache statistics."""
    try:
        from ...db.migrations import get_db

        db = get_db()

        # Cache statistics
        total_cache = db.execute("SELECT COUNT(*) FROM skills_cache").fetchone()[0]
        total_hits = (
            db.execute("SELECT SUM(hit_count) FROM skills_cache").fetchone()[0] or 0
        )

        # Avg skills per cache entry
        avg_skills = (
            db.execute(
                """
            SELECT AVG(json_array_length(matched_skills)) 
            FROM skills_cache
            WHERE matched_skills IS NOT NULL
        """
            ).fetchone()[0]
            or 0
        )

        return {
            "success": True,
            "data": {
                "total_cached_contexts": total_cache,
                "total_cache_hits": total_hits,
                "avg_skills_per_context": round(avg_skills, 2),
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
        from ...missions.store import get_mission_store

        store = get_mission_store()
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
        from ...missions.store import get_mission_store

        store = get_mission_store()
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
            # Count skills used by this agent
            skills_count = (
                db.execute(
                    "SELECT COUNT(*) FROM skills_usage WHERE agent_role = ?",
                    (agent.role,),
                ).fetchone()[0]
                or 0
            )

            leaderboard.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "skills_used": skills_count,
                    "skills_available": len(agent.skills or []),
                    "tools_count": len(agent.tools or []),
                }
            )

        # Sort by skills usage
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

        # Count by type
        by_type = db.execute(
            """
            SELECT type, COUNT(*) as count
            FROM tma_tickets
            WHERE status != 'archived'
            GROUP BY type
            ORDER BY count DESC
        """
        ).fetchall()

        # Count by status
        by_status = db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM tma_tickets
            WHERE status != 'archived'
            GROUP BY status
            ORDER BY count DESC
        """
        ).fetchall()

        # Total tickets
        total = db.execute(
            "SELECT COUNT(*) FROM tma_tickets WHERE status != 'archived'"
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

        db = get_db()

        # Database size
        db_path = "platform.db"
        db_size_mb = (
            os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        )

        # Table counts
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        table_stats = []
        total_rows = 0
        for (table_name,) in tables:
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
                    "tables": len(tables),
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
        tma_overview = await get_tma_overview()
        system_health = await get_system_health()
        cache_stats = await get_skills_cache_stats()

        return {
            "success": True,
            "data": {
                "skills": {
                    "top": top_skills.data[:5] if top_skills.success else [],
                    "cache": cache_stats.get("data", {}),
                },
                "missions": {
                    "status": missions_status.data if missions_status.success else {},
                    "performance": (
                        missions_perf.get("data", {}) if missions_perf else {}
                    ),
                },
                "agents": {
                    "leaderboard": (
                        agents_leaderboard.data[:5]
                        if agents_leaderboard.success
                        else []
                    ),
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
        db.row_factory = __import__("sqlite3").Row

        # 1. Error category classification (Python-based for accuracy)
        all_failed = db.execute(
            "SELECT id, phases_json FROM mission_runs WHERE status = 'failed'"
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
            SELECT id, phases_json FROM mission_runs
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
            SELECT COUNT(*) as cnt FROM mission_runs mr
            JOIN sessions s ON mr.session_id = s.id
            WHERE mr.status = 'paused'
            AND s.status IN ('interrupted', 'paused', 'active')
        """).fetchone()

        # 4. Run status summary
        run_stats = db.execute("""
            SELECT status, COUNT(*) as cnt FROM mission_runs GROUP BY status
        """).fetchall()

        # 5. Recent failures (last 20)
        recent = db.execute("""
            SELECT mr.id, mr.workflow_name, mr.current_phase, mr.status,
                   mr.created_at, mr.updated_at
            FROM mission_runs mr
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
        db.row_factory = __import__("sqlite3").Row

        paused = db.execute("""
            SELECT mr.session_id, mr.id, s.config_json
            FROM mission_runs mr
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
                    "UPDATE mission_runs SET status='running' WHERE session_id=?",
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


# ── Team Score ────────────────────────────────────────────────────────────────


@router.get("/api/analytics/team-score")
async def get_team_score(
    project_id: str = "",
    workflow_id: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Score agent teams across 4 dimensions: production, collaboration, coherence, efficiency.

    Aggregates data from agent_scores, messages, quality_reports, llm_traces.
    Optionally filter by project_id or workflow_id.
    """
    from ...db.migrations import get_db
    import json as _json

    db = get_db()

    # ── 1. Production score: accept ratio + avg quality ──────────────────────
    prod_rows = db.execute(
        """SELECT a.agent_id,
                  SUM(a.accepted) AS accepted,
                  SUM(a.rejected) AS rejected,
                  AVG(a.iterations) AS avg_iter,
                  COUNT(DISTINCT a.epic_id) AS epics
           FROM agent_scores a
           GROUP BY a.agent_id"""
    ).fetchall()

    production: dict[str, dict] = {}
    for r in prod_rows:
        aid, accepted, rejected, avg_iter, epics = r
        total = (accepted or 0) + (rejected or 0)
        accept_ratio = (accepted or 0) / total if total else 1.0
        # Penalize high iteration counts (ideal = 5, worst = 30+)
        iter_score = max(0, 1 - ((avg_iter or 5) - 5) / 30)
        production[aid] = {
            "accept_ratio": round(accept_ratio, 3),
            "accepted": accepted or 0,
            "rejected": rejected or 0,
            "avg_iter": round(avg_iter or 0, 1),
            "epics": epics,
            "iter_score": round(iter_score, 3),
            "production_score": round((accept_ratio * 0.6 + iter_score * 0.4) * 100, 1),
        }

    # ── 2. Collaboration score: agent↔agent message density ──────────────────
    collab_rows = db.execute(
        """SELECT from_agent, message_type, COUNT(*) n
           FROM messages
           WHERE from_agent NOT IN ('system','rte','')
           GROUP BY from_agent, message_type"""
    ).fetchall()

    collaboration: dict[str, dict] = {}
    for r in collab_rows:
        aid, mtype, n = r
        if aid not in collaboration:
            collaboration[aid] = {
                "agent": 0,
                "veto": 0,
                "approve": 0,
                "delegate": 0,
                "total": 0,
            }
        collaboration[aid][mtype] = collaboration[aid].get(mtype, 0) + n
        collaboration[aid]["total"] += n

    for aid, c in collaboration.items():
        total = c["total"] or 1
        # Active participation = agent+delegate messages vs passive system
        active = c.get("agent", 0) + c.get("delegate", 0)
        active_ratio = active / total
        # Collab density = how much meaningful agent↔agent communication
        c["active_ratio"] = round(active_ratio, 3)
        c["collaboration_score"] = round(min(100, active_ratio * 150), 1)

    # ── 3. Coherence score: low veto rate + consistent approvals ─────────────
    coherence: dict[str, dict] = {}
    for aid, c in collaboration.items():
        vetos = c.get("veto", 0)
        approvals = c.get("approve", 0)
        decisions = vetos + approvals
        if decisions > 0:
            # Low veto rate = high coherence (agents that always veto are disruptive)
            veto_rate = vetos / decisions
            # But some vetos are healthy — pure 0 veto = rubber-stamp (bad)
            # Optimal: 10-30% veto rate
            if veto_rate == 0:
                coherence_score = 70  # rubber-stamp penalty
            elif veto_rate <= 0.3:
                coherence_score = 100 - (veto_rate * 100)
            else:
                coherence_score = max(20, 100 - (veto_rate * 130))
            coherence[aid] = {
                "veto_count": vetos,
                "approve_count": approvals,
                "veto_rate": round(veto_rate, 3),
                "coherence_score": round(coherence_score, 1),
            }

    # ── 4. Efficiency score: tokens/cost vs output quality ───────────────────
    efficiency_rows = db.execute(
        """SELECT agent_id,
                  COUNT(*) calls,
                  AVG(duration_ms) avg_ms,
                  AVG(tokens_out) avg_out,
                  SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) success_pct
           FROM llm_traces
           WHERE agent_id != ''
           GROUP BY agent_id"""
    ).fetchall()

    efficiency: dict[str, dict] = {}
    for r in efficiency_rows:
        aid, calls, avg_ms, avg_out, success_pct = r
        # Fast + reliable = high efficiency
        speed_score = max(0, 100 - ((avg_ms or 0) / 100))  # -1pt per 100ms
        output_score = min(100, ((avg_out or 0) / 50))  # 50 tokens = 1pt
        eff_score = speed_score * 0.4 + (success_pct or 0) * 0.4 + output_score * 0.2
        efficiency[aid] = {
            "calls": calls,
            "avg_ms": round(avg_ms or 0, 0),
            "avg_out": round(avg_out or 0, 0),
            "success_pct": round(success_pct or 0, 1),
            "efficiency_score": round(max(0, min(100, eff_score)), 1),
        }

    # ── 5. Workflow-level team scores ────────────────────────────────────────
    wf_filter = "AND config_json LIKE ?" if workflow_id else ""
    wf_params = (f'%"workflow_id": "{workflow_id}"%',) if workflow_id else ()
    proj_filter = "AND project_id = ?" if project_id else ""
    proj_params = (project_id,) if project_id else ()

    wf_rows = db.execute(
        f"""SELECT config_json, status, COUNT(*) n
            FROM sessions
            WHERE config_json LIKE '%workflow_id%'
            {wf_filter} {proj_filter}
            GROUP BY config_json, status""",
        wf_params + proj_params,
    ).fetchall()

    workflow_scores: dict[str, dict] = {}
    for r in wf_rows:
        try:
            cfg = _json.loads(r[0]) if r[0] else {}
            wf = cfg.get("workflow_id", "")
            if not wf:
                continue
            if wf not in workflow_scores:
                workflow_scores[wf] = {"completed": 0, "failed": 0, "total": 0}
            workflow_scores[wf][r[1]] = workflow_scores[wf].get(r[1], 0) + r[2]
            workflow_scores[wf]["total"] += r[2]
        except Exception:
            pass

    for wf, s in workflow_scores.items():
        total = s["total"] or 1
        s["success_rate"] = round(s.get("completed", 0) * 100.0 / total, 1)
        s["workflow_score"] = s["success_rate"]

    # ── 6. Assemble composite scores ─────────────────────────────────────────
    all_agents = set(production) | set(collaboration) | set(coherence) | set(efficiency)
    composite: list[dict] = []

    for aid in all_agents:
        p = production.get(aid, {})
        col = collaboration.get(aid, {})
        coh = coherence.get(aid, {})
        eff = efficiency.get(aid, {})

        p_score = p.get("production_score", 0)
        col_score = col.get("collaboration_score", 0)
        coh_score = coh.get("coherence_score", 0)
        eff_score = eff.get("efficiency_score", 0)

        # Composite: weighted average
        # Only include agents with meaningful data (>=5 epics or >=10 messages)
        has_data = p.get("epics", 0) >= 3 or col.get("total", 0) >= 10
        if not has_data:
            continue

        weights = {
            "production": 0.35,
            "collaboration": 0.25,
            "coherence": 0.25,
            "efficiency": 0.15,
        }
        composite_score = (
            p_score * weights["production"]
            + col_score * weights["collaboration"]
            + coh_score * weights["coherence"]
            + eff_score * weights["efficiency"]
        )

        composite.append(
            {
                "agent_id": aid,
                "composite_score": round(composite_score, 1),
                "scores": {
                    "production": round(p_score, 1),
                    "collaboration": round(col_score, 1),
                    "coherence": round(coh_score, 1),
                    "efficiency": round(eff_score, 1),
                },
                "raw": {
                    "accept_ratio": p.get("accept_ratio", 0),
                    "accepted": p.get("accepted", 0),
                    "rejected": p.get("rejected", 0),
                    "avg_iter": p.get("avg_iter", 0),
                    "veto_rate": coh.get("veto_rate", 0),
                    "calls": eff.get("calls", 0),
                    "success_pct": eff.get("success_pct", 0),
                },
            }
        )

    composite.sort(key=lambda x: -x["composite_score"])

    # ── 7. Best combos: top workflow + top agents ─────────────────────────────
    top_workflows = sorted(
        [{"workflow_id": k, **v} for k, v in workflow_scores.items()],
        key=lambda x: -x["success_rate"],
    )[:10]

    return {
        "agents": composite[:limit],
        "workflows": top_workflows,
        "quality_dimensions": {
            r[0]: {"avg": round(r[1], 1), "count": r[2]}
            for r in db.execute(
                "SELECT dimension, AVG(score), COUNT(*) FROM quality_reports GROUP BY dimension ORDER BY AVG(score) DESC"
            ).fetchall()
        },
        "scoring_model": {
            "production": "35% — accept ratio × 0.6 + iter efficiency × 0.4",
            "collaboration": "25% — agent↔agent message ratio",
            "coherence": "25% — veto rate (optimal 10-30%, 0%=rubber-stamp, >30%=disruptive)",
            "efficiency": "15% — LLM speed × success rate × output volume",
        },
    }


@router.get("/api/analytics/agent-pattern-score")
async def get_agent_pattern_score(limit: int = 20):
    """
    Score agents grouped by (agent_id, pattern_id).
    Returns combos ranked by production ratio (accepted / (accepted + rejected)).
    Requires at least 3 runs to appear (filters noise).
    """
    from ...db.migrations import get_db

    db = get_db()
    rows = db.execute(
        """
        SELECT
            aps.agent_id,
            aps.pattern_id,
            aps.accepted,
            aps.rejected,
            aps.iterations,
            (aps.accepted + aps.rejected) AS total_runs,
            CASE WHEN (aps.accepted + aps.rejected) > 0
                 THEN ROUND(100.0 * aps.accepted / (aps.accepted + aps.rejected), 1)
                 ELSE 0 END AS accept_rate,
            CASE WHEN aps.iterations > 0
                 THEN ROUND(100.0 * aps.accepted / aps.iterations, 1)
                 ELSE 0 END AS efficiency
        FROM agent_pattern_scores aps
        WHERE (aps.accepted + aps.rejected) >= 3
        ORDER BY accept_rate DESC, total_runs DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    db.close()

    combos = [
        {
            "agent_id": r["agent_id"],
            "pattern_id": r["pattern_id"],
            "accept_rate": r["accept_rate"],
            "efficiency": r["efficiency"],
            "accepted": r["accepted"],
            "rejected": r["rejected"],
            "total_runs": r["total_runs"],
        }
        for r in rows
    ]

    # Group by pattern to surface best agent per pattern
    by_pattern: dict = {}
    for c in combos:
        pid = c["pattern_id"]
        if pid not in by_pattern:
            by_pattern[pid] = []
        by_pattern[pid].append(c)

    return {
        "combos": combos,
        "best_per_pattern": {
            pid: agents[0] for pid, agents in by_pattern.items() if agents
        },
        "total_combos": len(combos),
        "note": "Only combos with ≥3 runs shown. New data accumulates as agents run.",
    }
