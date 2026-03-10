"""Skill Eval REST API — coverage dashboard + eval trigger for /art Skills tab.

WHY:
  Exposes skill eval metrics from platform/tools/skill_eval_tools.py as a REST API
  so the /art dashboard can show skill health alongside Darwin team fitness and
  Thompson Sampling provider scores.

  Reference: https://www.philschmid.de/testing-skills
  "Graduate your evals: once they hit ~100%, they become regression tests."
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory run tracker (job_id → status/result)
_RUNNING: dict[str, dict[str, Any]] = {}


@router.get("/api/skills/eval", summary="Skill eval coverage summary")
async def skill_eval_coverage() -> dict[str, Any]:
    """Return eval coverage summary for all skills."""
    try:
        from ....tools.skill_eval_tools import coverage_summary
        return coverage_summary()
    except Exception as exc:
        logger.error("skill_eval_coverage error: %s", exc, exc_info=True)
        return {"error": str(exc), "total": 0, "with_evals": 0, "coverage_pct": 0,
                "run": 0, "passing": 0, "needing_work": [], "without_evals": []}


@router.get("/api/skills/list", summary="List all skills with eval coverage")
async def skill_list() -> list[dict[str, Any]]:
    """List all skills (agent skills + tech stack skills) with eval coverage."""
    try:
        from ....tools.skill_eval_tools import list_skills_with_evals, list_tech_skills
        agent_skills = list_skills_with_evals()
        # Mark agent skills with source
        for s in agent_skills:
            s.setdefault("source", "agent")
        tech_skills = list_tech_skills()
        return agent_skills + tech_skills
    except Exception as exc:
        logger.error("skill_list error: %s", exc, exc_info=True)
        return []


@router.get("/api/skills/eval/{skill_name}", summary="Full eval result for one skill")
async def skill_eval_result(skill_name: str) -> dict[str, Any]:
    """Return last eval result for a skill (or 404 if never run)."""
    from ....tools.skill_eval_tools import load_eval_result, _load_skill_frontmatter
    # Verify skill exists
    try:
        fm, _ = _load_skill_frontmatter(skill_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    result = load_eval_result(skill_name)
    if result is None:
        return {
            "skill_name": skill_name,
            "status": "never_run",
            "eval_cases_total": len(fm.get("eval_cases", [])),
            "pass_rate": None,
            "ran_at": None,
        }
    return result


@router.post("/api/skills/eval/{skill_name}/run", summary="Trigger eval run for a skill")
async def skill_eval_run(
    skill_name: str,
    background_tasks: BackgroundTasks,
    trials: int = Query(default=3, ge=1, le=10),
) -> dict[str, Any]:
    """Trigger an async eval run for a skill.

    Returns job_id immediately. Poll GET /api/skills/eval/job/{job_id} for status.

    Runs in background so the request returns fast (trials*cases can take 30-120s).
    """
    import uuid
    from ....tools.skill_eval_tools import _load_skill_frontmatter

    try:
        fm, _ = _load_skill_frontmatter(skill_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    if not fm.get("eval_cases"):
        raise HTTPException(status_code=422, detail=f"Skill '{skill_name}' has no eval_cases defined")

    job_id = str(uuid.uuid4())[:8]
    _RUNNING[job_id] = {"status": "running", "skill_name": skill_name, "started_at": _now()}

    async def _run():
        from ....tools.skill_eval_tools import run_skill_eval
        try:
            result = await run_skill_eval(skill_name, trials=trials)
            _RUNNING[job_id].update({
                "status": "done",
                "pass_rate": result.pass_rate,
                "eval_cases_total": result.eval_cases_total,
                "duration_s": result.duration_s,
                "finished_at": _now(),
            })
        except Exception as exc:
            _RUNNING[job_id].update({"status": "error", "error": str(exc)})

    background_tasks.add_task(_run)
    return {"job_id": job_id, "skill_name": skill_name, "status": "running"}


@router.get("/api/skills/eval/job/{job_id}", summary="Poll eval job status")
async def skill_eval_job_status(job_id: str) -> dict[str, Any]:
    """Poll status of a running eval job."""
    if job_id not in _RUNNING:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _RUNNING[job_id]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
