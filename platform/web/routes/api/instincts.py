"""Instinct system API — list, create, evolve, delete instincts.

SOURCE: ECC continuous-learning-v2 (https://github.com/affaan-m/everything-claude-code)
WHY: Instincts are atomic learned behaviors extracted from agent sessions.
     This API exposes CRUD + /evolve (cluster instincts → skill YAML) + stocktake.

Endpoints:
  GET  /api/instincts            — list instincts (filter by agent_id, project_id, scope, domain)
  POST /api/instincts            — manually create an instinct
  DELETE /api/instincts/{id}     — delete
  POST /api/instincts/evolve     — cluster high-confidence instincts into a skill YAML
  GET  /api/instincts/stats      — confidence distribution, domain breakdown
  GET  /api/skills/stocktake     — audit all skill YAML definitions for quality
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import yaml
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Path to skill YAML definitions
_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills" / "definitions"


# ─────────────────────────────────────────────────────────────────────────────
# Instinct endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/api/instincts")
async def list_instincts(
    agent_id: str = Query(default=""),
    project_id: str = Query(default=""),
    scope: str = Query(default=""),
    domain: str = Query(default=""),
    min_confidence: float = Query(default=0.0),
    limit: int = Query(default=50, le=200),
):
    """List instincts with optional filters."""
    try:
        from ....db.migrations import get_db

        with get_db() as db:
            wheres = []
            params: list = []
            if agent_id:
                wheres.append("agent_id = ?")
                params.append(agent_id)
            if project_id:
                wheres.append("project_id = ?")
                params.append(project_id)
            if scope:
                wheres.append("scope = ?")
                params.append(scope)
            if domain:
                wheres.append("domain = ?")
                params.append(domain)
            if min_confidence > 0:
                wheres.append("confidence >= ?")
                params.append(min_confidence)
            clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
            rows = db.execute(
                f"""SELECT id, agent_id, project_id, trigger, action, confidence,
                           domain, scope, evidence_json, source, evolved_into, created_at, updated_at
                    FROM instincts {clause}
                    ORDER BY confidence DESC, updated_at DESC LIMIT ?""",
                params + [limit],
            ).fetchall()
            cols = [
                "id",
                "agent_id",
                "project_id",
                "trigger",
                "action",
                "confidence",
                "domain",
                "scope",
                "evidence_json",
                "source",
                "evolved_into",
                "created_at",
                "updated_at",
            ]
            return JSONResponse(
                {"instincts": [dict(zip(cols, r)) for r in rows], "total": len(rows)}
            )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/api/instincts/stats")
async def instinct_stats():
    """Confidence distribution + domain breakdown."""
    try:
        from ....db.migrations import get_db

        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM instincts").fetchone()[0]
            by_domain = db.execute(
                "SELECT domain, COUNT(*), AVG(confidence) FROM instincts GROUP BY domain ORDER BY COUNT(*) DESC"
            ).fetchall()
            by_conf = db.execute(
                """SELECT
                     SUM(CASE WHEN confidence < 0.4 THEN 1 ELSE 0 END) as tentative,
                     SUM(CASE WHEN confidence >= 0.4 AND confidence < 0.65 THEN 1 ELSE 0 END) as developing,
                     SUM(CASE WHEN confidence >= 0.65 AND confidence < 0.85 THEN 1 ELSE 0 END) as established,
                     SUM(CASE WHEN confidence >= 0.85 THEN 1 ELSE 0 END) as near_certain
                   FROM instincts"""
            ).fetchone()
            evolved = db.execute(
                "SELECT COUNT(*) FROM instincts WHERE evolved_into IS NOT NULL"
            ).fetchone()[0]
        return JSONResponse(
            {
                "total": total,
                "evolved": evolved,
                "by_confidence": {
                    "tentative_0.3": by_conf[0] or 0,
                    "developing_0.5": by_conf[1] or 0,
                    "established_0.7": by_conf[2] or 0,
                    "near_certain_0.9": by_conf[3] or 0,
                },
                "by_domain": [
                    {"domain": r[0], "count": r[1], "avg_confidence": round(r[2], 2)}
                    for r in by_domain
                ],
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/instincts")
async def create_instinct(request: Request):
    """Manually create an instinct.

    Body: {agent_id, trigger, action, domain?, confidence?, scope?, project_id?}
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    agent_id = body.get("agent_id", "")
    trigger = body.get("trigger", "")
    action = body.get("action", "")
    if not trigger or not action:
        return JSONResponse(
            {"error": "trigger and action are required"}, status_code=400
        )

    try:
        from ....db.migrations import get_db

        rid = str(uuid.uuid4())
        with get_db() as db:
            db.execute(
                """INSERT INTO instincts
                   (id, agent_id, project_id, trigger, action, confidence, domain, scope, evidence_json, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    rid,
                    agent_id,
                    body.get("project_id", ""),
                    trigger,
                    action,
                    float(body.get("confidence", 0.5)),
                    body.get("domain", "general"),
                    body.get("scope", "global"),
                    "[]",
                    "manual",
                ),
            )
        return JSONResponse({"id": rid, "trigger": trigger, "action": action})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.delete("/api/instincts/{instinct_id}")
async def delete_instinct(instinct_id: str):
    """Delete an instinct by ID."""
    try:
        from ....db.migrations import get_db

        with get_db() as db:
            rows = db.execute(
                "DELETE FROM instincts WHERE id = ?", (instinct_id,)
            ).rowcount
        if rows == 0:
            return JSONResponse({"error": "Not found"}, status_code=404)
        return JSONResponse({"deleted": instinct_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/instincts/evolve")
async def evolve_instincts(request: Request):
    """Cluster high-confidence instincts → generate skill YAML + write to disk.

    SOURCE: ECC /evolve command (continuous-learning-v2)
    WHY: Instincts with confidence ≥ 0.6 sharing a domain are clustered into a
         reusable skill YAML definition written to platform/skills/definitions/.

    Body: {agent_id?, project_id?, min_confidence?}
    If agent_id is omitted, evolves all agents that have eligible instincts.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    agent_id = body.get("agent_id", "")

    from ....hooks.instinct import evolve_instincts as _evolve
    from ....db.migrations import get_db

    if agent_id:
        result = _evolve(
            agent_id=agent_id,
            project_id=body.get("project_id", ""),
            min_confidence=float(body.get("min_confidence", 0.6)),
        )
        if "error" in result:
            return JSONResponse(result, status_code=400)
        return JSONResponse({"success": True, "clusters": [result]})

    # No agent_id — evolve all agents with eligible instincts
    min_conf = float(body.get("min_confidence", 0.6))
    try:
        with get_db() as db:
            agents = db.execute(
                "SELECT DISTINCT agent_id FROM instincts WHERE confidence >= ? AND evolved_into IS NULL AND agent_id IS NOT NULL",
                (min_conf,),
            ).fetchall()
        results = []
        for row in agents:
            r = _evolve(agent_id=row["agent_id"], min_confidence=min_conf)
            if "skill_id" in r:
                results.append(r)
        return JSONResponse({"success": True, "clusters": results})
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.post("/api/instincts/promote")
async def promote_instincts(request: Request):
    """Promote project-scoped instincts to global when seen across 2+ projects.

    SOURCE: ECC instinct promotion logic
    WHY: Cross-project patterns are universal agent behaviors → global scope.

    Body: {min_projects?: int, min_confidence?: float}
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    from ....hooks.instinct import promote_global_instincts

    count = promote_global_instincts(
        min_projects=int(body.get("min_projects", 2)),
        min_confidence=float(body.get("min_confidence", 0.7)),
    )
    return JSONResponse({"success": True, "promoted": count})


# ─────────────────────────────────────────────────────────────────────────────
# Skill stocktake endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/api/skills/stocktake")
async def skill_stocktake(
    mode: str = Query(default="quick", description="'quick' or 'full'"),
):
    """Audit all skill YAML definitions for quality.

    SOURCE: ECC skill-stocktake SKILL.md
    WHY: Regular audits prevent skill sprawl. Each skill is scored on:
         actionability, scope-fit, uniqueness, and currency.
         Returns Keep/Improve/Update/Retire/Merge verdict per skill.

    mode=quick  — inventory only (no LLM judge)
    mode=full   — inventory + heuristic quality check
    """
    try:
        skills_dir = _SKILLS_DIR
        if not skills_dir.exists():
            return JSONResponse(
                {"error": f"Skills dir not found: {skills_dir}"}, status_code=404
            )

        skills = []
        for f in sorted(skills_dir.glob("*.yaml")):
            try:
                raw = f.read_text()
                data = yaml.safe_load(raw) or {}
            except Exception:
                data = {}

            name = f.stem
            description = data.get("description", "")
            triggers = data.get("triggers", [])
            tools = data.get("tools", [])
            skills_list = data.get("skills", [])
            line_count = len(raw.splitlines())
            mtime = f.stat().st_mtime

            # Heuristic quality score (quick mode)
            issues = []
            if not description:
                issues.append("missing description")
            if line_count < 10:
                issues.append("very short (<10 lines)")
            if line_count > 200:
                issues.append("very long (>200 lines) — consider splitting")
            if not triggers and not tools and not skills_list:
                issues.append("no triggers/tools/skills defined")

            verdict = "Keep"
            if len(issues) >= 3:
                verdict = "Improve"
            elif "missing description" in issues and line_count < 15:
                verdict = "Retire"
            elif line_count > 200:
                verdict = "Improve"

            skills.append(
                {
                    "name": name,
                    "description": description[:100] if description else "",
                    "line_count": line_count,
                    "has_triggers": bool(triggers),
                    "has_tools": bool(tools),
                    "issues": issues,
                    "verdict": verdict,
                    "mtime": mtime,
                    "path": str(f.relative_to(skills_dir.parent.parent)),
                }
            )

        summary = {
            "total": len(skills),
            "keep": sum(1 for s in skills if s["verdict"] == "Keep"),
            "improve": sum(1 for s in skills if s["verdict"] == "Improve"),
            "retire": sum(1 for s in skills if s["verdict"] == "Retire"),
            "mode": mode,
        }
        return JSONResponse({"summary": summary, "skills": skills})
    except Exception as exc:
        logger.error("skill_stocktake error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
