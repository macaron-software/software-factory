"""Pattern API routes — recommender, A/B stats, composite config.

WHY: phase_outcomes data now available; expose data-driven pattern selection
so agents and UI can choose the best orchestration pattern for a given context.
Ref: SF pattern observability, 2026-03.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/patterns/recommend")
async def recommend_pattern(body: dict[str, Any]) -> JSONResponse:
    """Score and rank patterns for a given project context.

    Input: {project_type, team_size, complexity_tier, available_agents[]}
    Output: {top: [{pattern_id, score, rationale}], fallback}

    WHY: RLPolicy + GA have priors; this endpoint surfaces them as actionable
    recommendations so humans and orchestrators make informed pattern choices.
    """
    project_type: str = body.get("project_type", "")
    team_size: int = int(body.get("team_size", 3))
    complexity_tier: str = body.get("complexity_tier", "simple")
    available_agents: list[str] = body.get("available_agents", [])

    try:
        from ....db.migrations import get_db

        db = get_db()

        # Base stats per pattern from phase_outcomes
        rows = db.execute("""
            SELECT
                pattern_id,
                COUNT(*) AS runs,
                ROUND(AVG(quality_score), 3) AS avg_quality,
                ROUND(100.0 * SUM(success) / GREATEST(COUNT(*), 1), 1) AS success_pct,
                ROUND(AVG(duration_secs), 1) AS avg_duration_s,
                ROUND(AVG(rejection_count), 2) AS avg_vetoes,
                ROUND(AVG(team_size), 1) AS avg_team_size
            FROM phase_outcomes
            GROUP BY pattern_id
            ORDER BY avg_quality DESC
        """).fetchall()
        db.close()

        stats = [dict(r) for r in rows]

        # Scoring: quality 40% + success 30% + speed 20% + veto penalty 10%
        scored = []
        for s in stats:
            if s["runs"] < 2:
                continue  # not enough data
            # Normalise speed: faster is better, cap at 300s
            speed_score = max(0.0, 1.0 - (s["avg_duration_s"] or 300) / 300)
            # Team size fit: prefer patterns whose avg team size is close to requested
            team_fit = max(0.0, 1.0 - abs((s["avg_team_size"] or team_size) - team_size) / 10)
            # Veto penalty: high rejection count → penalise
            veto_penalty = min(1.0, (s["avg_vetoes"] or 0) / 5)

            score = (
                0.40 * (s["avg_quality"] or 0)
                + 0.30 * (s["success_pct"] or 0) / 100
                + 0.20 * speed_score * team_fit
                - 0.10 * veto_penalty
            )
            rationale = _build_rationale(s, complexity_tier)
            scored.append({
                "pattern_id": s["pattern_id"],
                "score": round(score, 3),
                "runs": s["runs"],
                "success_pct": s["success_pct"],
                "avg_quality": s["avg_quality"],
                "avg_duration_s": s["avg_duration_s"],
                "rationale": rationale,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:3]

        # Fallback if no data: static defaults by complexity
        fallback = {
            "simple": "sequential",
            "medium": "parallel",
            "complex": "hierarchical",
        }.get(complexity_tier, "sequential")

        return JSONResponse({
            "success": True,
            "top": top,
            "fallback": fallback,
            "context": {
                "project_type": project_type,
                "team_size": team_size,
                "complexity_tier": complexity_tier,
                "available_agents": len(available_agents),
            },
        })
    except Exception as e:
        logger.exception("Pattern recommender error")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


def _build_rationale(stats: dict, complexity_tier: str) -> str:
    parts = []
    if (stats.get("success_pct") or 0) >= 80:
        parts.append(f"{stats['success_pct']}% success rate")
    if (stats.get("avg_quality") or 0) >= 0.8:
        parts.append("high quality score")
    if (stats.get("avg_duration_s") or 999) < 60:
        parts.append("fast execution")
    if (stats.get("avg_vetoes") or 0) < 0.5:
        parts.append("low rejection rate")
    return "; ".join(parts) if parts else "based on historical performance"


@router.get("/api/analytics/patterns/ab")
async def pattern_ab_stats() -> JSONResponse:
    """Compare A/B groups for patterns that have ab_alt_id configured.

    WHY: A/B test routing added in engine.py; this endpoint surfaces the delta
    in quality/success between control and treatment groups.
    """
    try:
        from ....db.migrations import get_db

        db = get_db()
        rows = db.execute("""
            SELECT
                pattern_id,
                ab_group,
                COUNT(*) AS runs,
                ROUND(100.0 * SUM(success) / GREATEST(COUNT(*), 1), 1) AS success_pct,
                ROUND(AVG(quality_score), 3) AS avg_quality,
                ROUND(AVG(duration_secs), 1) AS avg_duration_s,
                ROUND(AVG(rejection_count), 2) AS avg_vetoes
            FROM phase_outcomes
            WHERE ab_group IS NOT NULL AND ab_group != ''
            GROUP BY pattern_id, ab_group
            ORDER BY pattern_id, ab_group
        """).fetchall()
        db.close()

        # Group by pattern, compare control vs treatment
        from collections import defaultdict
        by_pattern: dict[str, dict] = defaultdict(dict)
        for r in rows:
            d = dict(r)
            by_pattern[d["pattern_id"]][d["ab_group"]] = d

        results = []
        for pid, groups in by_pattern.items():
            ctrl = groups.get("control", {})
            treat = groups.get("treatment", {})
            delta_quality = None
            if ctrl.get("avg_quality") and treat.get("avg_quality"):
                delta_quality = round(treat["avg_quality"] - ctrl["avg_quality"], 3)
            results.append({
                "pattern_id": pid,
                "control": ctrl,
                "treatment": treat,
                "delta_quality": delta_quality,
            })

        return JSONResponse({"success": True, "ab_results": results})
    except Exception as e:
        logger.exception("AB stats error")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
