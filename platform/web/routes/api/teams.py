"""Team template export/import endpoints.

Allows saving and loading agent team configurations as YAML templates.
"""
# Ref: feat-art, feat-mercato

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import Depends,  APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from ....auth.middleware import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_rows(rows):
    result = []
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif type(v).__name__ in ("Decimal", "float32", "float64"):
                d[k] = float(v)
        result.append(d)
    return result


TEAMS_DIR = Path(__file__).parents[4] / "teams"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.get("/api/teams/export")
async def export_team(request: Request):
    """Export a set of agents + pattern as a YAML team template.

    Query params:
      - agent_ids: comma-separated agent IDs  OR  project_id to export all agents of a project
      - pattern: pattern id (optional)
      - name: team name (optional)
      - description: team description (optional)
    """
    from ...agents.store import get_agent_store

    store = get_agent_store()
    params = request.query_params

    agent_ids_raw = params.get("agent_ids", "")
    project_id = params.get("project_id", "")

    if project_id:
        from ....db.adapter import get_db

        db = get_db()
        rows = db.execute(
            "SELECT agent_id FROM agent_assignments WHERE project_id = ?", (project_id,)
        ).fetchall()
        agent_ids = [r[0] for r in rows]
        if not agent_ids:
            # Fall back: list all non-builtin agents for that project
            agent_ids = [a.id for a in store.list_all() if not a.is_builtin]
    elif agent_ids_raw:
        agent_ids = [x.strip() for x in agent_ids_raw.split(",") if x.strip()]
    else:
        raise HTTPException(400, "Provide agent_ids or project_id")

    agents = []
    for aid in agent_ids:
        agent = store.get(aid)
        if agent:
            agents.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "description": agent.description,
                    "system_prompt": agent.system_prompt,
                    "provider": agent.provider,
                    "model": agent.model,
                    "temperature": agent.temperature,
                    "max_tokens": agent.max_tokens,
                    "skills": agent.skills,
                    "tools": agent.tools,
                    "mcps": agent.mcps,
                    "tags": agent.tags,
                    "icon": agent.icon,
                    "color": agent.color,
                    "avatar": agent.avatar,
                    "tagline": agent.tagline,
                    "persona": agent.persona,
                    "motivation": agent.motivation,
                    "hierarchy_rank": agent.hierarchy_rank,
                }
            )

    team = {
        "name": params.get("name", "My Team"),
        "description": params.get("description", ""),
        "pattern": params.get("pattern", "hierarchical"),
        "tags": [],
        "agents": agents,
    }

    fmt = params.get("format", "yaml")
    if fmt == "json":
        return JSONResponse(team)

    return PlainTextResponse(
        yaml.dump(team, allow_unicode=True, sort_keys=False, default_flow_style=False),
        media_type="application/x-yaml",
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@router.post("/api/teams/import", dependencies=[Depends(require_auth())])
async def import_team(request: Request):
    """Import a YAML team template — creates agents in DB.

    Body: YAML or JSON team definition.
    Query param: project_id (optional, assigns agents to project).
    """
    from ...agents.store import get_agent_store, AgentDef
    import json as _json

    body = await request.body()
    content_type = request.headers.get("content-type", "")

    try:
        if "json" in content_type:
            team = _json.loads(body)
        else:
            team = yaml.safe_load(body)
    except Exception as e:
        raise HTTPException(400, f"Invalid YAML/JSON: {e}")

    store = get_agent_store()
    project_id = request.query_params.get("project_id", "")
    created = []

    for a in team.get("agents", []):
        agent = AgentDef(
            id=a.get("id", ""),
            name=a.get("name", ""),
            role=a.get("role", "worker"),
            description=a.get("description", ""),
            system_prompt=a.get("system_prompt", ""),
            provider=a.get("provider", ""),
            model=a.get("model", ""),
            temperature=float(a.get("temperature", 0.7)),
            max_tokens=int(a.get("max_tokens", 4096)),
            skills=a.get("skills", []),
            tools=a.get("tools", []),
            mcps=a.get("mcps", []),
            tags=a.get("tags", []),
            icon=a.get("icon", "bot"),
            color=a.get("color", "#f78166"),
            avatar=a.get("avatar", ""),
            tagline=a.get("tagline", ""),
            persona=a.get("persona", ""),
            motivation=a.get("motivation", ""),
            hierarchy_rank=int(a.get("hierarchy_rank", 50)),
            is_builtin=False,
        )
        store.upsert(agent)

        if project_id:
            from ....db.adapter import get_db

            db = get_db()
            db.execute(
                "INSERT OR IGNORE INTO agent_assignments (agent_id, project_id, assignment_type) VALUES (?, ?, 'permanent')",
                (agent.id, project_id),
            )
            db.commit()

        created.append(agent.id)

    return JSONResponse(
        {
            "status": "ok",
            "team": team.get("name"),
            "agents_created": created,
            "pattern": team.get("pattern"),
        }
    )


# ---------------------------------------------------------------------------
# Darwin Team Fitness API
# ---------------------------------------------------------------------------


def _db():
    from ....db.migrations import get_db

    return get_db()


@router.get("/api/teams/contexts")
async def list_contexts():
    """Distinct (technology, phase_type) combos with fitness data."""
    try:
        db = _db()
        rows = db.execute("""
            SELECT DISTINCT technology, phase_type, COUNT(*) as teams
            FROM team_fitness
            GROUP BY technology, phase_type
            ORDER BY teams DESC
        """).fetchall()
        db.close()
        return JSONResponse(
            _safe_rows(rows)
            or [{"technology": "generic", "phase_type": "generic", "teams": 0}]
        )
    except Exception as e:
        logger.warning("contexts error: %s", e)
        return JSONResponse(
            [{"technology": "generic", "phase_type": "generic", "teams": 0}]
        )


@router.get("/api/teams/leaderboard")
async def team_leaderboard(
    technology: str = "generic", phase_type: str = "generic", limit: int = 30
):
    """Fitness leaderboard. phase_type='generic' aggregates across all phases."""
    try:
        db = _db()
        if phase_type == "generic":
            # Aggregate across ALL phases for that technology
            rows = db.execute(
                """
                SELECT tf.agent_id, tf.pattern_id, tf.technology,
                       'all' as phase_type,
                       AVG(tf.fitness_score) as fitness_score,
                       SUM(tf.runs) as runs,
                       SUM(tf.wins) as wins,
                       SUM(tf.losses) as losses,
                       AVG(tf.avg_iterations) as avg_iterations,
                       MAX(tf.weight_multiplier) as weight_multiplier,
                       MAX(tf.retired) as retired,
                       MAX(tf.pinned) as pinned,
                       MAX(tf.last_updated) as last_updated,
                       a.name as agent_name, a.role as agent_role,
                       CASE
                         WHEN SUM(tf.runs) >= 5 AND AVG(tf.fitness_score) >= 80 THEN 'champion'
                         WHEN SUM(tf.runs) >= 3 AND AVG(tf.fitness_score) >= 60 THEN 'rising'
                         WHEN MAX(tf.retired) = 1 THEN 'retired'
                         WHEN SUM(tf.runs) >= 10 AND AVG(tf.fitness_score) < 40 THEN 'declining'
                         ELSE 'active'
                       END as badge
                FROM team_fitness tf
                LEFT JOIN agents a ON a.id = tf.agent_id
                WHERE tf.technology = ?
                GROUP BY tf.agent_id, tf.pattern_id, tf.technology, a.name, a.role
                ORDER BY MAX(tf.pinned) DESC, AVG(tf.fitness_score) DESC
                LIMIT ?
            """,
                (technology, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT tf.agent_id, tf.pattern_id, tf.technology, tf.phase_type,
                       tf.fitness_score, tf.runs, tf.wins, tf.losses,
                       tf.avg_iterations, tf.weight_multiplier, tf.retired, tf.pinned,
                       tf.last_updated,
                       a.name as agent_name, a.role as agent_role,
                       CASE
                         WHEN tf.runs >= 5 AND tf.fitness_score >= 80 THEN 'champion'
                         WHEN tf.runs >= 3 AND tf.fitness_score >= 60 THEN 'rising'
                         WHEN tf.retired = 1 THEN 'retired'
                         WHEN tf.runs >= 10 AND tf.fitness_score < 40 THEN 'declining'
                         ELSE 'active'
                       END as badge
                FROM team_fitness tf
                LEFT JOIN agents a ON a.id = tf.agent_id
                WHERE tf.technology = ? AND tf.phase_type = ?
                ORDER BY tf.pinned DESC, tf.fitness_score DESC
                LIMIT ?
            """,
                (technology, phase_type, limit),
            ).fetchall()
        db.close()
        return JSONResponse(
            {
                "data": _safe_rows(rows),
                "technology": technology,
                "phase_type": phase_type,
            }
        )
    except Exception as e:
        logger.warning("leaderboard error: %s", e)
        return JSONResponse(
            {"data": [], "technology": technology, "phase_type": phase_type}
        )


@router.post("/api/teams/{agent_id}/{pattern_id}/retire", dependencies=[Depends(require_auth())])
async def retire_team(
    agent_id: str,
    pattern_id: str,
    technology: str = "generic",
    phase_type: str = "generic",
):
    """Soft-retire a team (weight_multiplier → 0.1)."""
    try:
        db = _db()
        db.execute(
            """
            UPDATE team_fitness SET retired = 1, weight_multiplier = 0.1, retired_at = CURRENT_TIMESTAMP
            WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
        """,
            (agent_id, pattern_id, technology, phase_type),
        )
        db.commit()
        db.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/teams/{agent_id}/{pattern_id}/unretire", dependencies=[Depends(require_auth())])
async def unretire_team(
    agent_id: str,
    pattern_id: str,
    technology: str = "generic",
    phase_type: str = "generic",
):
    """Restore a retired team."""
    try:
        db = _db()
        db.execute(
            """
            UPDATE team_fitness SET retired = 0, weight_multiplier = 1.0, retired_at = NULL
            WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
        """,
            (agent_id, pattern_id, technology, phase_type),
        )
        db.commit()
        db.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/teams/okr")
async def list_okr(technology: str = "", phase_type: str = ""):
    """List OKR/KPI objectives."""
    try:
        db = _db()
        q = "SELECT * FROM team_okr"
        params: list = []
        filters = []
        if technology:
            filters.append("technology = ?")
            params.append(technology)
        if phase_type:
            filters.append("phase_type = ?")
            params.append(phase_type)
        if filters:
            q += " WHERE " + " AND ".join(filters)
        q += " ORDER BY team_key, kpi_name"
        rows = db.execute(q, params).fetchall()
        db.close()
        # Compute progress percentage
        result = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
                elif hasattr(v, "__float__") and not isinstance(v, (int, float)):
                    d[k] = float(v)
            if d["kpi_target"] and d["kpi_target"] > 0:
                d["progress_pct"] = round(
                    min(100, d["kpi_current"] / d["kpi_target"] * 100), 1
                )
            else:
                d["progress_pct"] = 0.0
            result.append(d)
        return JSONResponse(result)
    except Exception as e:
        logger.warning("okr error: %s", e)
        return JSONResponse([])


@router.post("/api/teams/okr/refresh", dependencies=[Depends(require_auth())])
async def refresh_okr_kpis():
    """Auto-update OKR kpi_current values from live team_fitness data."""
    try:
        db = _db()
        techs = [
            r[0]
            for r in db.execute(
                "SELECT DISTINCT technology FROM team_fitness"
            ).fetchall()
        ]
        for tech in techs:
            stats = db.execute(
                """
                SELECT AVG(fitness_score) as avg_fitness,
                       SUM(wins)*100.0/NULLIF(SUM(runs),0) as win_rate,
                       SUM(CASE WHEN fitness_score>=60 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0) as competent_rate,
                       SUM(CASE WHEN fitness_score>=80 AND runs>=5 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0) as champion_rate
                FROM team_fitness WHERE technology = ?
                """,
                (tech,),
            ).fetchone()
            if not stats:
                continue
            kpi_map = {
                "avg_fitness_score": stats["avg_fitness"] or 0,
                "champion_rate": stats["champion_rate"] or 0,
                "win_rate": stats["win_rate"] or 0,
                "competent_rate": stats["competent_rate"] or 0,
            }
            for kpi_name, val in kpi_map.items():
                db.execute(
                    "UPDATE team_okr SET kpi_current=?, updated_at=CURRENT_TIMESTAMP WHERE technology=? AND kpi_name=?",
                    (round(float(val), 1), tech, kpi_name),
                )
        db.commit()
        db.close()
        return JSONResponse({"ok": True, "message": "OKR kpi_current refreshed"})
    except Exception as e:
        logger.warning("okr refresh error: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.put("/api/teams/okr/{okr_id}", dependencies=[Depends(require_auth())])
async def update_okr(okr_id: int, request: Request):
    """Update OKR target or current value."""
    try:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"ok": False, "error": "invalid body"}, status_code=422)
        db = _db()
        if "kpi_current" in body:
            val = float(body["kpi_current"])  # raises if not numeric
            db.execute(
                "UPDATE team_okr SET kpi_current = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (val, okr_id),
            )
        if "kpi_target" in body:
            val = float(body["kpi_target"])
            db.execute(
                "UPDATE team_okr SET kpi_target = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (val, okr_id),
            )
        db.commit()
        db.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/teams/evolution")
async def team_evolution(
    technology: str = "generic", phase_type: str = "generic", days: int = 30
):
    """Fitness history for evolution chart."""
    try:
        db = _db()
        from datetime import date, timedelta

        cutoff = (date.today() - timedelta(days=days)).isoformat()
        if phase_type == "generic":
            rows = db.execute(
                """
                SELECT tfh.agent_id, tfh.pattern_id, tfh.snapshot_date,
                       AVG(tfh.fitness_score) as fitness_score, SUM(tfh.runs) as runs,
                       a.name as agent_name
                FROM team_fitness_history tfh
                LEFT JOIN agents a ON a.id = tfh.agent_id
                WHERE tfh.technology = ?
                  AND tfh.snapshot_date >= ?
                GROUP BY tfh.agent_id, tfh.pattern_id, tfh.snapshot_date, a.name
                ORDER BY tfh.agent_id, tfh.pattern_id, tfh.snapshot_date
            """,
                (technology, cutoff),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT tfh.agent_id, tfh.pattern_id, tfh.snapshot_date,
                       tfh.fitness_score, tfh.runs,
                       a.name as agent_name
                FROM team_fitness_history tfh
                LEFT JOIN agents a ON a.id = tfh.agent_id
                WHERE tfh.technology = ? AND tfh.phase_type = ?
                  AND tfh.snapshot_date >= ?
                ORDER BY tfh.agent_id, tfh.pattern_id, tfh.snapshot_date
            """,
                (technology, phase_type, cutoff),
            ).fetchall()
        db.close()
        # Group by agent+pattern for chart series
        series: dict = {}
        for r in rows:
            key = f"{r['agent_id']}:{r['pattern_id']}"
            if key not in series:
                series[key] = {
                    "agent_id": r["agent_id"],
                    "agent_name": r["agent_name"] or r["agent_id"],
                    "pattern_id": r["pattern_id"],
                    "dates": [],
                    "scores": [],
                }
            snap = r["snapshot_date"]
            series[key]["dates"].append(
                snap.isoformat() if hasattr(snap, "isoformat") else str(snap)
            )
            series[key]["scores"].append(round(float(r["fitness_score"]), 1))
        return JSONResponse(
            {
                "series": list(series.values()),
                "technology": technology,
                "phase_type": phase_type,
            }
        )
    except Exception as e:
        logger.warning("evolution error: %s", e)
        return JSONResponse(
            {"series": [], "technology": technology, "phase_type": phase_type}
        )


@router.get("/api/teams/selections")
async def team_selections(limit: int = 50):
    """Recent team selection events."""
    try:
        db = _db()
        rows = db.execute(
            """
            SELECT ts.*, a.name as agent_name
            FROM team_selections ts
            LEFT JOIN agents a ON a.id = ts.agent_id
            ORDER BY ts.selected_at DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        db.close()
        return JSONResponse({"data": _safe_rows(rows)})
    except Exception as e:
        logger.warning("selections error: %s", e)
        return JSONResponse({"data": []})


@router.get("/api/teams/ab-tests")
async def team_ab_tests(limit: int = 30, status: str = ""):
    """A/B shadow test results."""
    try:
        db = _db()
        q = """
            SELECT tab.*,
                   a1.name as team_a_name,
                   a2.name as team_b_name
            FROM team_ab_tests tab
            LEFT JOIN agents a1 ON a1.id = tab.team_a_agent
            LEFT JOIN agents a2 ON a2.id = tab.team_b_agent
        """
        params: list = []
        if status:
            q += " WHERE tab.status = ?"
            params.append(status)
        q += " ORDER BY tab.started_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(q, params).fetchall()
        db.close()
        return JSONResponse({"data": _safe_rows(rows)})
    except Exception as e:
        logger.warning("ab-tests error: %s", e)
        return JSONResponse({"data": []})


@router.get("/api/teams/llm-leaderboard")
async def llm_leaderboard(
    technology: str = "generic",
    phase_type: str = "generic",
    agent_id: str = "",
    limit: int = 30,
):
    """LLM model leaderboard: Thompson Sampling fitness scores per (team × LLM model)."""
    try:
        from ....patterns.team_selector import LLMTeamSelector

        data = LLMTeamSelector.get_leaderboard(
            agent_id=agent_id or None,
            technology=technology,
            phase_type=phase_type,
            limit=limit,
        )
        return JSONResponse(
            {"data": data, "technology": technology, "phase_type": phase_type}
        )
    except Exception as e:
        logger.warning("llm-leaderboard error: %s", e)
        return JSONResponse({"data": []})


@router.get("/api/teams/llm-ab-tests")
async def llm_ab_tests(limit: int = 30, status: str = ""):
    """LLM A/B test results: same team, different LLM models."""
    try:
        from ....patterns.team_selector import LLMTeamSelector

        data = LLMTeamSelector.get_llm_ab_tests(status=status, limit=limit)
        return JSONResponse({"data": data})
    except Exception as e:
        logger.warning("llm-ab-tests error: %s", e)
        return JSONResponse({"data": []})


# ---------------------------------------------------------------------------
# List saved templates from teams/ dir
# ---------------------------------------------------------------------------


@router.get("/api/teams")
async def list_teams():
    """List all team templates saved in the teams/ directory."""
    if not TEAMS_DIR.exists():
        return JSONResponse([])

    teams = []
    for f in sorted(TEAMS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            teams.append(
                {
                    "file": f.name,
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "pattern": data.get("pattern", ""),
                    "agent_count": len(data.get("agents", [])),
                    "tags": data.get("tags", []),
                }
            )
        except Exception:
            pass

    return JSONResponse(teams)


@router.get("/api/teams/{filename}")
async def get_team(filename: str):
    """Get a specific team template by filename."""
    path = TEAMS_DIR / filename
    if not path.exists() or not filename.endswith(".yaml"):
        raise HTTPException(404, "Team not found")

    return PlainTextResponse(
        path.read_text(),
        media_type="application/x-yaml",
    )
