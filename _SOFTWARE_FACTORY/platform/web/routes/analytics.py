"""
Analytics API — Real-time metrics and insights
"""

import logging
from datetime import datetime
from typing import Any

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
        from platform.db import get_db

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
        from platform.db import get_db

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
        from platform.db import get_db

        db = get_db()

        # Cache statistics
        total_cache = db.execute("SELECT COUNT(*) FROM skills_cache").fetchone()[0]
        total_hits = db.execute("SELECT SUM(hit_count) FROM skills_cache").fetchone()[0] or 0

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
                "hit_rate": (round(total_hits / total_cache * 100, 2) if total_cache > 0 else 0),
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
        from platform.missions.store import get_mission_store

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
            for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return MissionsStatusResponse(success=True, data={"total": total, "by_status": status_data})

    except Exception:
        logger.exception("Error getting missions status")
        return MissionsStatusResponse(success=False, data={})


@router.get("/api/analytics/missions/performance")
async def get_missions_performance() -> dict[str, Any]:
    """Get missions performance metrics."""
    try:
        from platform.missions.store import get_mission_store

        store = get_mission_store()
        missions = store.list_missions(limit=1000)

        # Calculate metrics
        completed = [m for m in missions if getattr(m, "status", "") == "completed"]
        failed = [m for m in missions if getattr(m, "status", "") == "failed"]
        active = [
            m for m in missions if getattr(m, "status", "") in ["running", "in_progress", "active"]
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
                "backlog_size": len([m for m in missions if getattr(m, "status", "") == "pending"]),
            },
        }

    except Exception:
        logger.exception("Error getting missions performance")
        return {"success": False, "data": {}}


# =============================================================================
# Agents Analytics
# =============================================================================


@router.get("/api/analytics/agents/leaderboard", response_model=AgentsLeaderboardResponse)
async def get_agents_leaderboard(limit: int = 10) -> AgentsLeaderboardResponse:
    """Get top performing agents."""
    try:
        from platform.agents.store import get_agent_store
        from platform.db import get_db

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
        from platform.agents.store import get_agent_store

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
                    round(agents_with_skills / total_agents * 100, 1) if total_agents > 0 else 0
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
        from platform.db import get_db

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
        from platform.db import get_db

        db = get_db()

        # Database size
        db_path = "platform.db"
        db_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0

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
                "tables": sorted(table_stats, key=lambda x: x["rows"], reverse=True)[:10],
                "timestamp": datetime.now().isoformat(),
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
                    "performance": (missions_perf.get("data", {}) if missions_perf else {}),
                },
                "agents": {
                    "leaderboard": (
                        agents_leaderboard.data[:5] if agents_leaderboard.success else []
                    ),
                },
                "tma": tma_overview.data if tma_overview.success else {},
                "system": system_health.data if system_health.success else {},
                "timestamp": datetime.now().isoformat(),
            },
        }

    except Exception as e:
        logger.exception("Error getting analytics overview")
        return {"success": False, "data": {}, "error": str(e)}
