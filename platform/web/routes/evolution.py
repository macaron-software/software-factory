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
            raise HTTPException(
                status_code=404, detail=f"Proposal {proposal_id!r} not found"
            )
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
async def trigger_evolution(
    wf_id: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Trigger GA evolution for a specific workflow (runs in background)."""
    background_tasks.add_task(_run_ga, wf_id)
    return JSONResponse(
        {"ok": True, "wf_id": wf_id, "message": "Evolution started in background"}
    )


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
                run["fitness_history"] = json.loads(
                    run.pop("fitness_history_json", "[]")
                )
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
        return JSONResponse(
            {
                "states": 0,
                "actions": [],
                "total_experience": 0,
                "recommendations_total": 0,
                "recommendations_fired": 0,
                "error": str(e),
            }
        )


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
        return JSONResponse(
            rec or {"action": "keep", "confidence": 0.0, "fired": False}
        )
    except Exception as e:
        log.warning(f"rl_recommend: {e}")
        return JSONResponse(
            {"action": "keep", "confidence": 0.0, "fired": False, "error": str(e)}
        )


@router.post("/api/darwin/seed")
async def seed_darwin(background_tasks: BackgroundTasks) -> JSONResponse:
    """Seed team_fitness warmup data for Darwin Teams leaderboard."""
    background_tasks.add_task(_run_darwin_seed_bg)
    return JSONResponse({"ok": True, "message": "Darwin seed started in background"})


async def _run_darwin_seed_bg():
    import asyncio
    import random as _random

    loop = asyncio.get_event_loop()

    def _seed():
        from ...db.migrations import get_db as _get_db
        from ...patterns.team_selector import (
            _get_agents_with_skill,
            _upsert_team_fitness,
            update_team_fitness,
        )

        _db2 = _get_db()
        _existing = _db2.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
        _has_nf = _db2.execute(
            "SELECT COUNT(*) FROM team_fitness WHERE phase_type='new_feature'"
        ).fetchone()[0]
        if _existing >= 100 and _has_nf >= 10:
            log.info(f"Darwin seed: already {_existing} rows with new_feature")
            _db2.close()
            return _existing
        _skills = ["developer", "tester", "security", "devops"]
        _patterns = ["loop", "sequential", "parallel", "hierarchical", "aggregator"]
        _phases = [
            "new_feature",
            "bugfix",
            "refactoring",
            "migration",
            "review",
            "testing",
            "audit",
            "design",
            "docs",
            "tdd",
            "feature",
            "sprint",
            "deploy",
            "exploitation",
            "load",
            "perf",
        ]
        _techs = ["generic", "python", "typescript", "java", "rust", "go"]
        _seeded = 0
        for _skill in _skills:
            _agents = _get_agents_with_skill(_db2, _skill)
            if not _agents:
                continue
            for _pattern in _patterns[:4]:
                for _phase in _phases[:6]:
                    for _tech in _techs[:3]:
                        for _aid in _agents[:6]:
                            _upsert_team_fitness(_db2, _aid, _pattern, _tech, _phase)
                            _runs = _random.randint(5, 15)
                            _wins = int(_runs * _random.uniform(0.4, 0.92))
                            for _r in range(_runs):
                                update_team_fitness(
                                    _db2,
                                    _aid,
                                    _pattern,
                                    _tech,
                                    _phase,
                                    won=(_r < _wins),
                                    iterations=_random.randint(1, 3),
                                )
                                _seeded += 1
                        if _seeded % 1000 == 0:
                            _db2.commit()
        _db2.commit()
        _after = _db2.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
        _db2.close()
        return _after

    try:
        after = await loop.run_in_executor(None, _seed)
        log.info(f"Darwin seed complete: {after} team_fitness rows")
    except Exception as e:
        log.warning(f"Darwin seed failed: {e}")


# ── Warmup ────────────────────────────────────────────────────────────────────


@router.post("/api/warmup")
async def trigger_warmup(
    body: dict[str, Any], background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Trigger adaptive intelligence warmup in background.
    Body: {n_runs: int (default 300), generations: int (default 5)}
    Returns immediately; warmup runs async and writes to DB.
    """
    n_runs = int(body.get("n_runs", 300))
    generations = int(body.get("generations", 5))
    background_tasks.add_task(_run_warmup_bg, n_runs, generations)
    return JSONResponse(
        {
            "ok": True,
            "n_runs": n_runs,
            "generations": generations,
            "message": "Warmup started in background",
        }
    )


@router.get("/api/warmup/status")
async def warmup_status() -> JSONResponse:
    """Current state of adaptive intelligence data layers (row counts)."""
    try:
        db = _db()
        agent_scores = db.execute("SELECT COUNT(*) FROM agent_scores").fetchone()[0]
        sim_scores = db.execute(
            "SELECT COUNT(*) FROM agent_scores WHERE epic_id LIKE 'sim-%'"
        ).fetchone()[0]
        team_fitness = db.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
        rl_exp = db.execute("SELECT COUNT(*) FROM rl_experience").fetchone()[0]
        proposals = db.execute("SELECT COUNT(*) FROM evolution_proposals").fetchone()[0]
        runs = db.execute("SELECT COUNT(*) FROM evolution_runs").fetchone()[0]
        db.close()
        warmed = agent_scores >= 1000 and proposals >= 5
        return JSONResponse(
            {
                "warmed_up": warmed,
                "agent_scores": {
                    "total": agent_scores,
                    "synthetic": sim_scores,
                    "real": agent_scores - sim_scores,
                },
                "team_fitness": team_fitness,
                "rl_experiences": rl_exp,
                "ga_proposals": proposals,
                "ga_runs": runs,
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def _run_warmup_bg(n_runs: int, generations: int):
    """Background warmup task — runs simulator + GA + RL in a thread pool."""
    import asyncio

    loop = asyncio.get_event_loop()
    log.info(f"Warmup starting: n_runs={n_runs}, generations={generations}")
    try:
        # Simulator
        from ...agents.simulator import MissionSimulator

        sim = MissionSimulator()
        result = await loop.run_in_executor(
            None, lambda: sim.run_all(n_runs_per_workflow=n_runs)
        )
        log.info(
            f"Warmup simulator: {sum(result.values())} rows across {len(result)} workflows"
        )
    except Exception as e:
        log.warning(f"Warmup simulator failed: {e}")
    try:
        # GA
        from ...agents.evolution import GAEngine

        ga = GAEngine()
        fitnesses = await loop.run_in_executor(
            None, lambda: ga.evolve_all(generations=generations)
        )
        log.info(
            f"Warmup GA: {len(fitnesses)} workflows, avg fitness {sum(fitnesses.values()) / max(len(fitnesses), 1):.3f}"
        )
    except Exception as e:
        log.warning(f"Warmup GA failed: {e}")
    try:
        # RL
        from ...agents.rl_policy import get_rl_policy

        stats = await loop.run_in_executor(
            None, lambda: get_rl_policy().train(max_rows=100_000)
        )
        log.info(f"Warmup RL trained: {stats}")
    except Exception as e:
        log.warning(f"Warmup RL failed: {e}")
    try:
        # Darwin team_fitness seed — populate leaderboard from agent_scores
        import random as _random

        from ...db.migrations import get_db as _get_db
        from ...patterns.team_selector import (
            _get_agents_with_skill,
            _upsert_team_fitness,
            update_team_fitness,
        )

        _db = _get_db()
        _existing = _db.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
        if _existing < 100:
            _skills = ["developer", "tester", "security", "devops"]
            _patterns = ["loop", "sequential", "parallel", "hierarchical", "aggregator"]
            _phases = [
                "new_feature",
                "bugfix",
                "refactoring",
                "migration",
                "review",
                "testing",
                "audit",
                "design",
                "docs",
                "tdd",
                "feature",
                "sprint",
                "deploy",
                "exploitation",
                "load",
                "perf",
            ]
            _techs = ["generic", "python", "typescript", "java", "rust", "go"]
            _seeded = 0
            for _skill in _skills:
                _agents = _get_agents_with_skill(_db, _skill)
                if not _agents:
                    continue
                for _pattern in _patterns[:3]:
                    for _phase in _phases[:5]:
                        for _tech in _techs[:3]:
                            for _aid in _agents[:6]:
                                _upsert_team_fitness(_db, _aid, _pattern, _tech, _phase)
                                _runs = _random.randint(5, 15)
                                _wins = int(_runs * _random.uniform(0.4, 0.92))
                                for _r in range(_runs):
                                    update_team_fitness(
                                        _db,
                                        _aid,
                                        _pattern,
                                        _tech,
                                        _phase,
                                        won=(_r < _wins),
                                        iterations=_random.randint(1, 3),
                                    )
                                    _seeded += 1
                            if _seeded % 1000 == 0:
                                _db.commit()
            _db.commit()
            _after = _db.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
            log.info(f"Darwin warmup: {_after} team_fitness rows seeded")
        else:
            log.info(f"Darwin warmup: already {_existing} rows, skipping seed")
        _db.close()
    except Exception as e:
        log.warning(f"Warmup Darwin team_fitness failed: {e}")
    log.info("Warmup complete")
