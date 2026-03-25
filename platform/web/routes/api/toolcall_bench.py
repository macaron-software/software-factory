"""ToolCall-15 Bench REST API — trigger + results for tool-calling benchmark.

Port of stevibe/ToolCall-15 (MIT). Routes:
  GET  /api/toolcall-bench/list     — all stored results
  GET  /api/toolcall-bench/{key}    — result for provider_model key
  POST /api/toolcall-bench/run      — launch bench (background)
  GET  /api/toolcall-bench/job/{id} — poll job status
"""
# Ref: feat-evals — ToolCall-15

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from ....auth.middleware import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)

_RUNNING: dict[str, dict[str, Any]] = {}


@router.get("/api/toolcall-bench/list", summary="All ToolCall-15 results")
async def toolcall_bench_list() -> dict[str, Any]:
    """Return all stored ToolCall-15 benchmark results."""
    try:
        from ....tools.toolcall_bench import load_results
        results = load_results()
        return {
            "total": len(results),
            "results": results,
        }
    except Exception as e:
        logger.error("toolcall_bench_list: %s", e, exc_info=True)
        return {"total": 0, "results": [], "error": str(e)}


@router.get("/api/toolcall-bench/{key}", summary="Result for provider_model key")
async def toolcall_bench_result(key: str) -> dict[str, Any]:
    """Return last result for a specific provider_model key."""
    from ....tools.toolcall_bench import RESULTS_DIR
    import json

    path = RESULTS_DIR / f"{key}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No result for '{key}'")
    return json.loads(path.read_text())


@router.post(
    "/api/toolcall-bench/run",
    summary="Launch ToolCall-15 bench (background)",
    dependencies=[Depends(require_auth())],
)
async def toolcall_bench_run(
    background_tasks: BackgroundTasks,
    model: str = Query(..., description="Model name (e.g. MiniMax-M2.7)"),
    provider: str = Query(..., description="Provider id (e.g. minimax)"),
    tool_choice: str = Query(default="auto", description="Tool choice: auto or required"),
) -> dict[str, Any]:
    """Launch ToolCall-15 benchmark in background. Returns job_id to poll."""
    import uuid

    job_id = f"tc15-{provider}-{uuid.uuid4().hex[:8]}"
    _RUNNING[job_id] = {"status": "running", "model": model, "provider": provider, "result": None}

    async def _run():
        try:
            from ....tools.toolcall_bench import run_toolcall_bench
            import dataclasses
            result = await run_toolcall_bench(model, provider, tool_choice=tool_choice)
            _RUNNING[job_id] = {
                "status": "done",
                "model": model,
                "provider": provider,
                "result": dataclasses.asdict(result),
            }
        except Exception as e:
            logger.error("toolcall_bench job %s failed: %s", job_id, e, exc_info=True)
            _RUNNING[job_id] = {
                "status": "error",
                "model": model,
                "provider": provider,
                "error": str(e),
            }

    background_tasks.add_task(_run)
    return {"job_id": job_id, "model": model, "provider": provider, "status": "running"}


@router.get("/api/toolcall-bench/job/{job_id}", summary="Poll ToolCall-15 job")
async def toolcall_bench_job(job_id: str) -> dict[str, Any]:
    """Poll status of a ToolCall-15 benchmark job."""
    job = _RUNNING.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'")
    return {"job_id": job_id, **job}
