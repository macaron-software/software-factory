"""Team template export/import endpoints.

Allows saving and loading agent team configurations as YAML templates.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter()
logger = logging.getLogger(__name__)

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
            agent_ids = [
                a.id for a in store.list_all() if not a.is_builtin
            ]
    elif agent_ids_raw:
        agent_ids = [x.strip() for x in agent_ids_raw.split(",") if x.strip()]
    else:
        raise HTTPException(400, "Provide agent_ids or project_id")

    agents = []
    for aid in agent_ids:
        agent = store.get(aid)
        if agent:
            agents.append({
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
            })

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

@router.post("/api/teams/import")
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

    return JSONResponse({
        "status": "ok",
        "team": team.get("name"),
        "agents_created": created,
        "pattern": team.get("pattern"),
    })


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
        return JSONResponse([dict(r) for r in rows] or [{"technology": "generic", "phase_type": "generic", "teams": 0}])
    except Exception as e:
        logger.warning("contexts error: %s", e)
        return JSONResponse([{"technology": "generic", "phase_type": "generic", "teams": 0}])


@router.get("/api/teams/leaderboard")
async def team_leaderboard(technology: str = "generic", phase_type: str = "generic", limit: int = 30):
    """Fitness leaderboard for a (technology, phase_type) context."""
    try:
        db = _db()
        rows = db.execute("""
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
        """, (technology, phase_type, limit)).fetchall()
        db.close()
        return JSONResponse({"data": [dict(r) for r in rows], "technology": technology, "phase_type": phase_type})
    except Exception as e:
        logger.warning("leaderboard error: %s", e)
        return JSONResponse({"data": [], "technology": technology, "phase_type": phase_type})


@router.post("/api/teams/{agent_id}/{pattern_id}/retire")
async def retire_team(agent_id: str, pattern_id: str, technology: str = "generic", phase_type: str = "generic"):
    """Soft-retire a team (weight_multiplier → 0.1)."""
    try:
        db = _db()
        db.execute("""
            UPDATE team_fitness SET retired = 1, weight_multiplier = 0.1, retired_at = CURRENT_TIMESTAMP
            WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
        """, (agent_id, pattern_id, technology, phase_type))
        db.commit()
        db.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/teams/{agent_id}/{pattern_id}/unretire")
async def unretire_team(agent_id: str, pattern_id: str, technology: str = "generic", phase_type: str = "generic"):
    """Restore a retired team."""
    try:
        db = _db()
        db.execute("""
            UPDATE team_fitness SET retired = 0, weight_multiplier = 1.0, retired_at = NULL
            WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
        """, (agent_id, pattern_id, technology, phase_type))
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
            if d["kpi_target"] and d["kpi_target"] > 0:
                d["progress_pct"] = round(min(100, d["kpi_current"] / d["kpi_target"] * 100), 1)
            else:
                d["progress_pct"] = 0.0
            result.append(d)
        return JSONResponse(result)
    except Exception as e:
        logger.warning("okr error: %s", e)
        return JSONResponse([])


@router.put("/api/teams/okr/{okr_id}")
async def update_okr(okr_id: int, request: Request):
    """Update OKR target or current value."""
    try:
        body = await request.json()
        db = _db()
        if "kpi_current" in body:
            db.execute("UPDATE team_okr SET kpi_current = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                       (body["kpi_current"], okr_id))
        if "kpi_target" in body:
            db.execute("UPDATE team_okr SET kpi_target = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                       (body["kpi_target"], okr_id))
        db.commit()
        db.close()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/api/teams/evolution")
async def team_evolution(technology: str = "generic", phase_type: str = "generic", days: int = 30):
    """Fitness history for evolution chart."""
    try:
        db = _db()
        cutoff = db.execute("SELECT date('now', ?)", (f"-{days} days",)).fetchone()[0]
        rows = db.execute("""
            SELECT tfh.agent_id, tfh.pattern_id, tfh.snapshot_date,
                   tfh.fitness_score, tfh.runs,
                   a.name as agent_name
            FROM team_fitness_history tfh
            LEFT JOIN agents a ON a.id = tfh.agent_id
            WHERE tfh.technology = ? AND tfh.phase_type = ?
              AND tfh.snapshot_date >= ?
            ORDER BY tfh.agent_id, tfh.pattern_id, tfh.snapshot_date
        """, (technology, phase_type, cutoff)).fetchall()
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
            series[key]["dates"].append(r["snapshot_date"])
            series[key]["scores"].append(round(r["fitness_score"], 1))
        return JSONResponse({"series": list(series.values()), "technology": technology, "phase_type": phase_type})
    except Exception as e:
        logger.warning("evolution error: %s", e)
        return JSONResponse({"series": [], "technology": technology, "phase_type": phase_type})


@router.get("/api/teams/selections")
async def team_selections(limit: int = 50):
    """Recent team selection events."""
    try:
        db = _db()
        rows = db.execute("""
            SELECT ts.*, a.name as agent_name
            FROM team_selections ts
            LEFT JOIN agents a ON a.id = ts.agent_id
            ORDER BY ts.selected_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        db.close()
        return JSONResponse({"data": [dict(r) for r in rows]})
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
        return JSONResponse({"data": [dict(r) for r in rows]})
    except Exception as e:
        logger.warning("ab-tests error: %s", e)
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
            teams.append({
                "file": f.name,
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "pattern": data.get("pattern", ""),
                "agent_count": len(data.get("agents", [])),
                "tags": data.get("tags", []),
            })
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
