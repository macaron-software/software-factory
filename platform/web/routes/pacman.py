"""PACMAN web routes — Dynamic PM Orchestrator API."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Deep fractal runs need more iterations and more time
_DEFAULT_MAX_ITERATIONS = 30   # was 8 — SPECS elaboration + module phases + integration
_DEFAULT_TIMEOUT_S = 1800      # was 600 — 30 min for full fractal run


@router.post("/api/pacman/run")
async def api_pacman_run(request: Request):
    """Run PACMAN dynamic PM orchestrator for a given goal.

    Body (JSON):
        goal:           Epic/goal description (required)
        project_id:     Project ID (optional)
        max_iterations: Max orchestration iterations (default 30)
        timeout:        Timeout seconds (default 1800)

    Returns session_id, completed phases with judge/adversarial scores, and final output.
    """
    body = await request.json()
    goal = body.get("goal", "").strip()
    if not goal:
        return JSONResponse({"error": "Missing required field: goal"}, status_code=400)

    project_id = body.get("project_id", "")
    max_iter = int(body.get("max_iterations", _DEFAULT_MAX_ITERATIONS))
    timeout_s = int(body.get("timeout", _DEFAULT_TIMEOUT_S))

    from ...agents.pacman import get_pacman

    orchestrator = get_pacman(project_id=project_id)
    orchestrator.MAX_RETRIES_PER_PHASE = 2

    try:
        state = await asyncio.wait_for(orchestrator.run(goal), timeout=timeout_s)
        return JSONResponse(
            {
                "session_id": orchestrator.session_id,
                "done": state.done,
                "iterations": state.iteration,
                "failed_ac": state.failed_ac,
                "open_ac_count": len(state.failed_ac),
                "phases": [
                    {
                        "id": r.phase_id,
                        "pattern": r.pattern_id,
                        "judge_passed": r.judge_passed,
                        "judge_score": r.judge_score,
                        "judge_reason": r.judge_reason,
                        "adversarial_passed": r.adversarial_passed,
                        "adversarial_issues": r.adversarial_issues,
                        "ac_score": r.ac_score,
                        "ac_summary": r.ac_summary,
                        "output_excerpt": r.output[:500],
                    }
                    for r in state.completed_phases
                ],
                "final_output": state.final_output,
                "context": state.context_summary,
            }
        )
    except asyncio.TimeoutError:
        return JSONResponse({"error": f"PACMAN timeout ({timeout_s}s)"}, status_code=504)
    except Exception as e:
        logger.error("PACMAN run failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/pacman/status/{session_id}")
async def api_pacman_status(session_id: str):
    """Placeholder status endpoint — PACMAN runs synchronously for now."""
    return JSONResponse(
        {
            "session_id": session_id,
            "status": "unknown",
            "note": "PACMAN currently runs synchronously via POST /api/pacman/run",
        }
    )
