"""
Evolution & RL API — GA proposals + RL policy stats.

Endpoints:
  GET  /api/evolution/proposals           — list pending/approved/rejected proposals
  POST /api/evolution/proposals/{id}/approve
  POST /api/evolution/proposals/{id}/reject
  POST /api/evolution/run/{wf_id}         — manual GA trigger
  GET  /api/rl/policy/stats               — RL Q-table stats
  POST /api/rl/policy/recommend           — get RL recommendation for a state
  GET  /api/evolution/runs                — GA run history
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
router = APIRouter()


def _db():
    from ...db.migrations import get_db
    return get_db()


# ── Proposals ────────────────────────────────────────────────────────────────

@router.get("/api/evolution/proposals")
async def list_proposals(status: str = "", limit: int = 50) -> JSONResponse:
    """List evolution proposals, optionally filtered by status."""
    try:
        db = _db()
        where = "WHERE status = ?" if status else ""
        params = [status] if status else []
        rows = db.execute(
            f"SELECT * FROM evolution_proposals {where} ORDER BY fitness DESC, created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        db.close()
        proposals = []
        for r in rows:
            p = dict(r)
            try:
                p["genome"] = json.loads(p.pop("genome_json", "{}"))
            except Exception:
                p["genome"] = {}
            proposals.append(p)
        return JSONResponse({"proposals": proposals, "total": len(proposals)})
    except Exception as e:
        log.warning(f"list_proposals: {e}")
        return JSONResponse({"proposals": [], "total": 0, "error": str(e)})


@router.post("/api/evolution/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str) -> JSONResponse:
    """Approve an evolution proposal (mark for workflow template update)."""
    return _update_proposal_status(proposal_id, "approved")


@router.post("/api/evolution/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str) -> JSONResponse:
    """Reject an evolution proposal."""
    return _update_proposal_status(proposal_id, "rejected")


def _update_proposal_status(proposal_id: str, status: str) -> JSONResponse:
    try:
        db = _db()
        row = db.execute(
            "SELECT id FROM evolution_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        if not row:
            db.close()
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")
        db.execute(
            "UPDATE evolution_proposals SET status = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, proposal_id),
        )
        db.commit()
        db.close()
        log.info(f"Proposal {proposal_id} → {status}")
        return JSONResponse({"ok": True, "proposal_id": proposal_id, "status": status})
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"update_proposal_status: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── Manual GA trigger ─────────────────────────────────────────────────────────

@router.post("/api/evolution/run/{wf_id}")
async def trigger_evolution(wf_id: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Trigger GA evolution for a specific workflow (runs in background)."""
    background_tasks.add_task(_run_ga, wf_id)
    return JSONResponse({"ok": True, "wf_id": wf_id, "message": "Evolution started in background"})


async def _run_ga(wf_id: str) -> None:
    try:
        from ...agents.evolution import GAEngine
        engine = GAEngine()
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        best = await loop.run_in_executor(None, engine.evolve, wf_id)
        log.info(f"Manual GA [{wf_id}]: best_fitness={best.fitness:.4f}")
    except Exception as e:
        log.warning(f"Manual GA [{wf_id}] failed: {e}")


# ── GA Run history ────────────────────────────────────────────────────────────

@router.get("/api/evolution/runs")
async def list_runs(wf_id: str = "", limit: int = 20) -> JSONResponse:
    """List GA run history."""
    try:
        db = _db()
        where = "WHERE wf_id = ?" if wf_id else ""
        params = [wf_id] if wf_id else []
        rows = db.execute(
            f"SELECT * FROM evolution_runs {where} ORDER BY started_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        db.close()
        runs = []
        for r in rows:
            run = dict(r)
            try:
                run["fitness_history"] = json.loads(run.pop("fitness_history_json", "[]"))
            except Exception:
                run["fitness_history"] = []
            runs.append(run)
        return JSONResponse({"runs": runs, "total": len(runs)})
    except Exception as e:
        log.warning(f"list_runs: {e}")
        return JSONResponse({"runs": [], "total": 0, "error": str(e)})


# ── RL Policy ─────────────────────────────────────────────────────────────────

@router.get("/api/rl/policy/stats")
async def rl_stats() -> JSONResponse:
    """Return RL policy Q-table statistics."""
    try:
        from ...agents.rl_policy import get_rl_policy
        policy = get_rl_policy()
        stats = policy.stats()
        return JSONResponse(stats)
    except Exception as e:
        log.warning(f"rl_stats: {e}")
        return JSONResponse({
            "states": 0,
            "actions": [],
            "total_experience": 0,
            "recommendations_total": 0,
            "recommendations_fired": 0,
            "error": str(e),
        })


@router.post("/api/rl/policy/recommend")
async def rl_recommend(body: dict[str, Any]) -> JSONResponse:
    """
    Get RL recommendation for a phase context.
    Body: {wf_id, phase_index, rejection_rate, quality_score}
    """
    try:
        from ...agents.rl_policy import get_rl_policy
        policy = get_rl_policy()
        wf_id = body.get("wf_id", "")
        phase_index = int(body.get("phase_index", 0))
        rejection_rate = float(body.get("rejection_rate", 0.0))
        quality_score = float(body.get("quality_score", 0.0))
        rec = policy.recommend(wf_id, phase_index, rejection_rate, quality_score)
        return JSONResponse(rec or {"action": "keep", "confidence": 0.0, "fired": False})
    except Exception as e:
        log.warning(f"rl_recommend: {e}")
        return JSONResponse({"action": "keep", "confidence": 0.0, "fired": False, "error": str(e)})
