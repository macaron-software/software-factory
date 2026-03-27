"""Team Bench REST API — trigger + results for team bench harness."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)

_RUNNING: dict[str, dict[str, Any]] = {}


@router.get("/api/team-bench/list", summary="All team benchmarks + last results")
async def team_bench_list() -> dict[str, Any]:
    try:
        from ....tools.team_bench_tools import team_bench_coverage_summary

        return team_bench_coverage_summary()
    except Exception as e:
        logger.error("team_bench_list: %s", e, exc_info=True)
        return {
            "total_benchmarks": 0,
            "with_results": 0,
            "without_results": 0,
            "avg_pass_rate": 0,
            "benchmarks": [],
            "error": str(e),
        }


@router.get("/api/team-bench/{team_id}", summary="Last bench result for one team")
async def team_bench_result(team_id: str) -> dict[str, Any]:
    from ....tools.team_bench_tools import load_team_bench_result, load_team_bench_def

    try:
        load_team_bench_def(team_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"No benchmark YAML for team '{team_id}'"
        )
    result = load_team_bench_result(team_id)
    if result is None:
        return {
            "team_id": team_id,
            "status": "never_run",
            "pass_rate": None,
            "ran_at": None,
        }
    return result


@router.post("/api/team-bench/run", summary="Trigger team bench run (background)")
async def team_bench_run(
    background_tasks: BackgroundTasks,
    team_id: str = Query(...),
    update_darwin: bool = Query(default=True),
) -> dict[str, Any]:
    import uuid

    job_id = f"teambench-{team_id}-{uuid.uuid4().hex[:8]}"
    _RUNNING[job_id] = {"status": "running", "team_id": team_id, "result": None}

    async def _run() -> None:
        from ....tools.team_bench_tools import run_team_bench

        try:
            result = await run_team_bench(team_id=team_id, update_darwin=update_darwin)
            _RUNNING[job_id] = {
                "status": "done",
                "team_id": team_id,
                "result": {
                    "pass_rate": result.pass_rate,
                    "avg_checks": result.avg_checks,
                    "avg_judge": result.avg_judge,
                    "avg_overall": result.avg_overall,
                    "combined_output_length": result.combined_output_length,
                    "tool_calls_made": result.tool_calls_made,
                    "judge_score": result.judge_score,
                    "judge_notes": result.judge_notes[:300]
                    if result.judge_notes
                    else "",
                    "darwin_updated": result.darwin_updated,
                    "status": result.status,
                    "error": result.error,
                    "duration_s": result.duration_s,
                    "ran_at": result.ran_at,
                    "check_details": [
                        {"spec": c.spec, "passed": c.passed, "notes": c.notes}
                        for c in result.check_details
                    ],
                },
            }
        except Exception as e:
            logger.error("team bench job %s failed: %s", job_id, e, exc_info=True)
            _RUNNING[job_id] = {
                "status": "error",
                "team_id": team_id,
                "error": str(e),
                "result": None,
            }

    background_tasks.add_task(_run)
    return {"job_id": job_id, "team_id": team_id, "status": "running"}


@router.get("/api/team-bench/job/{job_id}", summary="Poll team bench job")
async def team_bench_job_status(job_id: str) -> dict[str, Any]:
    if job_id not in _RUNNING:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _RUNNING[job_id]
