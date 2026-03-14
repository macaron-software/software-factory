"""Agent Bench REST API — trigger + results for agent bench harness.

Mirrors skill_eval.py pattern. Routes grafted onto existing /api router.
Uses PG via get_db() — no separate DB, no SQLite fallback.
"""
# Ref: feat-agents-list, feat-evals

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from ....auth.middleware import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory job tracker (same pattern as skill_eval)
_RUNNING: dict[str, dict[str, Any]] = {}


@router.get("/api/agent-bench/list", summary="All agent benchmarks + last results")
async def agent_bench_list() -> dict[str, Any]:
    """Return coverage summary + all benchmark definitions with last result metadata."""
    try:
        from ....tools.agent_bench_tools import bench_coverage_summary

        return bench_coverage_summary()
    except Exception as e:
        logger.error("agent_bench_list: %s", e, exc_info=True)
        return {
            "total_benchmarks": 0,
            "with_results": 0,
            "without_results": 0,
            "avg_pass_rate": 0,
            "benchmarks": [],
            "error": str(e),
        }


@router.get("/api/agent-bench/{agent_id}", summary="Last bench result for one agent")
async def agent_bench_result(agent_id: str) -> dict[str, Any]:
    """Return last bench result for agent_id, or 404 if never run."""
    from ....tools.agent_bench_tools import load_bench_result, load_bench_def

    try:
        load_bench_def(agent_id)  # verify YAML exists
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"No benchmark YAML for agent '{agent_id}'"
        )
    result = load_bench_result(agent_id)
    if result is None:
        return {
            "agent_id": agent_id,
            "status": "never_run",
            "pass_rate": None,
            "ran_at": None,
        }
    return result


@router.post(
    "/api/agent-bench/run", summary="Trigger bench run for an agent (background)",
    dependencies=[Depends(require_auth())],
)
async def agent_bench_run(
    background_tasks: BackgroundTasks,
    agent_id: str = Query(..., description="Agent ID from the agents table"),
    trials: int = Query(default=1, ge=1, le=3),
    update_darwin: bool = Query(
        default=True, description="Feed result into Darwin/Thompson (PG)"
    ),
) -> dict[str, Any]:
    """Launch agent bench run in background. Returns job_id to poll."""
    import uuid

    job_id = f"bench-{agent_id}-{uuid.uuid4().hex[:8]}"
    _RUNNING[job_id] = {"status": "running", "agent_id": agent_id, "result": None}

    async def _run() -> None:
        from ....tools.agent_bench_tools import run_agent_bench

        try:
            result = await run_agent_bench(
                agent_id=agent_id, trials=trials, update_darwin=update_darwin
            )
            _RUNNING[job_id] = {
                "status": "done",
                "agent_id": agent_id,
                "result": {
                    "pass_rate": result.pass_rate,
                    "avg_checks": result.avg_checks,
                    "avg_judge": result.avg_judge,
                    "avg_overall": result.avg_overall,
                    "cases_total": result.cases_total,
                    "ran_at": result.ran_at,
                    "duration_s": result.duration_s,
                    "status": result.status,
                    "error": result.error,
                    "darwin_updated": result.darwin_updated,
                    "case_results": [
                        {
                            "case_id": c.case_id,
                            "overall": c.overall,
                            "check_pass_rate": c.check_pass_rate,
                            "judge_score": c.judge_score,
                            "tool_calls_made": c.tool_calls_made,
                            "check_details": [
                                {
                                    "spec": ch.spec,
                                    "passed": ch.passed,
                                    "notes": ch.notes,
                                }
                                for ch in c.check_details
                            ],
                            "judge_notes": c.judge_notes,
                            "output_excerpt": c.output_excerpt[:300],
                            "error": c.error,
                        }
                        for c in result.case_results
                    ],
                },
            }
        except Exception as e:
            logger.error("agent bench job %s failed: %s", job_id, e, exc_info=True)
            _RUNNING[job_id] = {
                "status": "error",
                "agent_id": agent_id,
                "error": str(e),
                "result": None,
            }

    background_tasks.add_task(_run)
    return {"job_id": job_id, "agent_id": agent_id, "status": "running"}


@router.get("/api/agent-bench/job/{job_id}", summary="Poll bench job status")
async def agent_bench_job_status(job_id: str) -> dict[str, Any]:
    """Return status and result of a bench run job."""
    if job_id not in _RUNNING:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _RUNNING[job_id]
