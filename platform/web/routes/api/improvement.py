"""
Amélioration Continue API — REST endpoints for AC project management.

GET  /api/ac/projects              List all AC projects with current state
GET  /api/ac/projects/{id}         Project detail + last cycle info
GET  /api/ac/projects/{id}/cycles  Cycle history (paginated)
POST /api/ac/projects/{id}/start   Launch next AC cycle
GET  /api/ac/projects/{id}/scores  Intelligence metrics (RL, Thompson, convergence)
GET  /api/ac/stats                 Global AC statistics
POST /api/ac/cycles/inject         Record a completed cycle (CI/CD callback)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ac", tags=["amélioration-continue"])


# ── Helpers — reuse DB + project list from pages.py ──────────────────────────

def _get_projects() -> list[dict]:
    from ..pages import _AC_PROJECTS
    return _AC_PROJECTS


def _get_db():
    from ..pages import _ac_get_db, _ac_ensure_tables
    conn = _ac_get_db()
    _ac_ensure_tables(conn)
    return conn


def _load_states(conn) -> dict[str, dict]:
    try:
        return {
            r["project_id"]: dict(r)
            for r in conn.execute("SELECT * FROM ac_project_state").fetchall()
        }
    except Exception:
        return {}


def _load_cycles(conn, project_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    try:
        rows = conn.execute(
            "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            try:
                row["phase_scores"] = json.loads(row.get("phase_scores") or "{}")
            except Exception:
                row["phase_scores"] = {}
            try:
                adv = row.get("adversarial_scores") or "{}"
                row["adversarial_scores"] = json.loads(adv) if isinstance(adv, str) else adv
            except Exception:
                row["adversarial_scores"] = {}
            result.append(row)
        return result
    except Exception:
        return []


def _enrich_project(p: dict, state: dict) -> dict:
    """Merge project def with live state."""
    return {
        **p,
        "current_cycle": state.get("current_cycle", 0),
        "status": state.get("status", "idle"),
        "total_score_avg": round(state.get("total_score_avg") or 0, 1),
        "last_git_sha": state.get("last_git_sha"),
        "ci_status": state.get("ci_status", "unknown"),
        "current_run_id": state.get("current_run_id"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "convergence_status": state.get("convergence_status", "cold_start"),
    }


# ── GET /api/ac/projects ──────────────────────────────────────────────────────

@router.get("/projects")
async def ac_list_projects() -> JSONResponse:
    """List all AC pilot projects with their current state."""
    def _load():
        conn = _get_db()
        states = _load_states(conn)
        conn.close()
        return states

    states = await asyncio.to_thread(_load)
    projects = [_enrich_project(p, states.get(p["id"], {})) for p in _get_projects()]
    return JSONResponse({"projects": projects, "total": len(projects)})


# ── GET /api/ac/projects/{id} ─────────────────────────────────────────────────

@router.get("/projects/{project_id}")
async def ac_get_project(project_id: str) -> JSONResponse:
    """Get a single AC project with its last cycle details."""
    projects = {p["id"]: p for p in _get_projects()}
    if project_id not in projects:
        return JSONResponse({"error": f"Project not found: {project_id}"}, status_code=404)

    def _load():
        conn = _get_db()
        state = dict(conn.execute(
            "SELECT * FROM ac_project_state WHERE project_id=?", (project_id,)
        ).fetchone() or {})
        last_cycle = None
        try:
            row = conn.execute(
                "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if row:
                last_cycle = dict(row)
                try:
                    last_cycle["phase_scores"] = json.loads(last_cycle.get("phase_scores") or "{}")
                except Exception:
                    last_cycle["phase_scores"] = {}
                try:
                    adv = last_cycle.get("adversarial_scores") or "{}"
                    last_cycle["adversarial_scores"] = json.loads(adv) if isinstance(adv, str) else adv
                except Exception:
                    last_cycle["adversarial_scores"] = {}
        except Exception:
            pass
        conn.close()
        return state, last_cycle

    state, last_cycle = await asyncio.to_thread(_load)
    result = _enrich_project(projects[project_id], state)
    result["last_cycle"] = last_cycle
    return JSONResponse(result)


# ── GET /api/ac/projects/{id}/cycles ─────────────────────────────────────────

@router.get("/projects/{project_id}/cycles")
async def ac_get_cycles(
    project_id: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    """Paginated cycle history for a project."""
    projects = {p["id"] for p in _get_projects()}
    if project_id not in projects:
        return JSONResponse({"error": f"Project not found: {project_id}"}, status_code=404)

    def _load():
        conn = _get_db()
        cycles = _load_cycles(conn, project_id, limit, offset)
        try:
            total = conn.execute(
                "SELECT COUNT(*) as n FROM ac_cycles WHERE project_id=?", (project_id,)
            ).fetchone()["n"]
        except Exception:
            total = len(cycles)
        conn.close()
        return cycles, total

    cycles, total = await asyncio.to_thread(_load)
    return JSONResponse({
        "project_id": project_id,
        "cycles": cycles,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


# ── POST /api/ac/projects/{id}/start ─────────────────────────────────────────

@router.post("/projects/{project_id}/start")
async def ac_start_cycle(project_id: str) -> JSONResponse:
    """Launch the next AC improvement cycle for a project."""
    # Delegate to the existing start endpoint in pages.py
    from ..pages import api_improvement_start
    from fastapi import Request as FARequest

    # Reuse existing implementation (no need to duplicate)
    response = await api_improvement_start(project_id)
    return response


# ── GET /api/ac/projects/{id}/scores ─────────────────────────────────────────

@router.get("/projects/{project_id}/scores")
async def ac_get_scores(project_id: str) -> JSONResponse:
    """Intelligence metrics: RL reward, convergence, Thompson sampling stats."""
    # Delegate to existing endpoint
    from ..pages import api_improvement_scores
    response = await api_improvement_scores(project_id)
    return response


# ── GET /api/ac/stats ─────────────────────────────────────────────────────────

@router.get("/stats")
async def ac_global_stats() -> JSONResponse:
    """Global AC statistics across all projects."""
    def _load():
        conn = _get_db()
        states = _load_states(conn)
        try:
            total_cycles = conn.execute("SELECT COUNT(*) as n FROM ac_cycles").fetchone()["n"]
        except Exception:
            total_cycles = 0
        try:
            running = conn.execute(
                "SELECT COUNT(*) as n FROM ac_project_state WHERE status='running'"
            ).fetchone()["n"]
        except Exception:
            running = 0
        try:
            avg_score = conn.execute(
                "SELECT AVG(total_score) as v FROM ac_cycles WHERE total_score > 0"
            ).fetchone()["v"] or 0
        except Exception:
            avg_score = 0
        try:
            best = conn.execute(
                "SELECT project_id, MAX(total_score) as best_score FROM ac_cycles GROUP BY project_id ORDER BY best_score DESC LIMIT 1"
            ).fetchone()
        except Exception:
            best = None
        conn.close()
        return states, total_cycles, running, avg_score, best

    states, total_cycles, running, avg_score, best = await asyncio.to_thread(_load)
    projects = _get_projects()

    return JSONResponse({
        "projects_total": len(projects),
        "projects_running": running,
        "cycles_total": total_cycles,
        "avg_score": round(avg_score, 1),
        "best_project": dict(best) if best else None,
        "projects": [
            {
                "id": p["id"],
                "name": p["name"],
                "tier": p["tier"],
                "status": states.get(p["id"], {}).get("status", "idle"),
                "current_cycle": states.get(p["id"], {}).get("current_cycle", 0),
                "max_cycles": p["max_cycles"],
                "score_avg": round(states.get(p["id"], {}).get("total_score_avg") or 0, 1),
            }
            for p in projects
        ],
    })


# ── POST /api/ac/cycles/inject ────────────────────────────────────────────────

@router.post("/cycles/inject")
async def ac_inject_cycle(request: Any) -> JSONResponse:
    """Record a completed cycle from CI/CD. Alias for /api/improvement/inject-cycle."""
    from ..pages import api_improvement_inject_cycle
    from fastapi import Request as FARequest
    return await api_improvement_inject_cycle(request)
