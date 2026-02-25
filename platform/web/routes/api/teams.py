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
