"""Web routes — Ideation workspace."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse

from .helpers import _templates, _avatar_url, _agent_map_for_template, _active_mission_tasks, serve_workspace_file

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Ideation Workspace ───────────────────────────────────────────

_IDEATION_AGENTS = [
    {"id": "metier", "name": "Camille Durand", "short_role": "Business Analyst", "color": "#2563eb"},
    {"id": "architecte", "name": "Pierre Duval", "short_role": "Solution Architect", "color": "#0891b2"},
    {"id": "ux_designer", "name": "Chloé Bertrand", "short_role": "UX Designer", "color": "#8b5cf6"},
    {"id": "securite", "name": "Nadia Benali", "short_role": "Sécurité", "color": "#dc2626"},
    {"id": "product_manager", "name": "Alexandre Faure", "short_role": "Product Manager", "color": "#16a34a"},
]


@router.get("/ideation", response_class=HTMLResponse)
async def ideation_page(request: Request):
    """Ideation workspace — brainstorm with expert agents."""
    from ...agents.store import get_agent_store
    from ...projects.manager import get_project_store

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    # Map DB agents by id for enrichment
    db_map = {a.id: a for a in all_agents}

    enriched = []
    for ia in _IDEATION_AGENTS:
        a = db_map.get(ia["id"])
        jpg = avatar_dir / f"{ia['id']}.jpg"
        svg_f = avatar_dir / f"{ia['id']}.svg"
        avatar_url = f"/static/avatars/{ia['id']}.jpg" if jpg.exists() else (f"/static/avatars/{ia['id']}.svg" if svg_f.exists() else "")
        enriched.append({
            **ia,
            "avatar_url": avatar_url,
            "description": (a.description or "") if a else "",
            "tagline": (a.tagline or "") if a else "",
            "persona": (a.persona or "") if a else "",
            "motivation": (a.motivation or "") if a else "",
            "skills": (a.skills or []) if a else [],
            "tools": (a.tools or []) if a else [],
            "mcps": (a.mcps or []) if a else [],
            "model": (a.model or "") if a else "",
            "provider": (getattr(a, "provider", "") or "") if a else "",
        })

    # Load past ideation sessions for sidebar
    from ...db.migrations import get_db as _gdb
    _db = _gdb()
    try:
        _rows = _db.execute(
            "SELECT id, title, status, created_at FROM ideation_sessions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        past_sessions = [{"id": r["id"], "title": r["title"], "status": r["status"],
                          "created_at": r["created_at"] or ""} for r in _rows]
    except Exception:
        past_sessions = []
    finally:
        _db.close()

    return _templates(request).TemplateResponse("ideation.html", {
        "request": request, "page_title": "Idéation",
        "agents": enriched,
        "projects": [{"id": p.id, "name": p.name} for p in get_project_store().list_all()],
        "past_sessions": past_sessions,
    })


@router.post("/api/ideation")
async def ideation_submit(request: Request):
    """Launch a REAL multi-agent ideation via the pattern engine (network pattern).

    Creates a session, builds a network pattern with the 5 ideation agents,
    launches run_pattern() in background. The frontend listens via SSE.
    Returns the session_id immediately so the frontend can connect to SSE.
    """
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...patterns.engine import run_pattern
    from ...patterns.store import PatternDef
    import uuid

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return JSONResponse({"error": "Prompt requis"}, status_code=400)

    session_id = data.get("session_id", "") or str(uuid.uuid4())[:8]

    # Create a real session
    session_store = get_session_store()
    existing = session_store.get(session_id)
    if not existing:
        session = SessionDef(
            id=session_id,
            name=f"Idéation: {prompt[:60]}",
            goal=prompt,
            status="active",
            config={"type": "ideation", "pattern": "network"},
        )
        session = session_store.create(session)
    else:
        session = existing

    # Store user message
    session_store.add_message(MessageDef(
        session_id=session_id,
        from_agent="user",
        message_type="delegate",
        content=prompt,
    ))

    # Build a network pattern with the 5 ideation agents
    agent_nodes = []
    agent_ids = []
    for ia in _IDEATION_AGENTS:
        agent_nodes.append({"id": ia["id"], "agent_id": ia["id"]})
        agent_ids.append(ia["id"])

    # Build bidirectional edges between all debaters + report edges to PO
    edges = []
    debaters = [a for a in agent_ids if a != "product_manager"]
    for i, a in enumerate(debaters):
        for b in debaters[i+1:]:
            edges.append({"from": a, "to": b, "type": "bidirectional"})
    # All debaters report to product_manager (judge)
    for a in debaters:
        edges.append({"from": a, "to": "product_manager", "type": "report"})

    pattern = PatternDef(
        id=f"ideation-{session_id}",
        name="Idéation multi-expert",
        type="network",
        agents=agent_nodes,
        edges=edges,
        config={"max_rounds": 2},
    )

    # Launch pattern in background — small delay lets SSE connect first
    async def _run_ideation():
        try:
            await asyncio.sleep(0.5)  # Let frontend SSE connect before first events
            await run_pattern(pattern, session_id, prompt)
        except Exception as e:
            logger.error("Ideation pattern failed: %s", e)
            session_store.add_message(MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"Ideation error: {e}",
            ))

    asyncio.create_task(_run_ideation())

    return JSONResponse({
        "session_id": session_id,
        "status": "started",
        "sse_url": f"/api/sessions/{session_id}/sse",
    })


_PO_EPIC_SYSTEM = """Tu es Alexandre Faure, Product Owner senior.
Tu reçois la synthèse d'un atelier d'idéation et tu dois structurer un projet complet.

À partir de l'idée et des analyses des experts, produis un JSON avec:
1. Le projet (nom, description, stack technique, factory_type)
2. L'epic principal (nom, description, critères d'acceptation)
3. 3 à 5 features découpées depuis l'epic
4. 2 à 3 user stories par feature (format "En tant que... je veux... afin de...")
5. L'équipe proposée (rôles nécessaires)

Réponds UNIQUEMENT avec ce JSON:
{
  "project": {
    "id": "slug-kebab-case",
    "name": "Nom du Projet",
    "description": "Description courte",
    "stack": ["SvelteKit", "Rust", "PostgreSQL"],
    "factory_type": "sf"
  },
  "epic": {
    "name": "Nom de l'Epic",
    "description": "Description détaillée de l'epic",
    "goal": "Critères d'acceptation clairs et mesurables"
  },
  "features": [
    {
      "name": "Nom Feature",
      "description": "Description",
      "acceptance_criteria": "Given/When/Then",
      "story_points": 8,
      "stories": [
        {
          "title": "En tant que [persona] je veux [action] afin de [bénéfice]",
          "description": "Détails",
          "acceptance_criteria": "Given/When/Then",
          "story_points": 3
        }
      ]
    }
  ],
  "team": [
    {"role": "lead_dev", "label": "Lead Developer"},
    {"role": "developer", "label": "Développeur Backend"},
    {"role": "developer", "label": "Développeur Frontend"},
    {"role": "tester", "label": "QA Engineer"},
    {"role": "devops", "label": "DevOps"},
    {"role": "security", "label": "Expert Sécurité"}
  ]
}

Sois pragmatique et concret. Les features doivent être actionnables.
Réponds UNIQUEMENT avec le JSON, rien d'autre."""


@router.post("/api/ideation/create-epic")
async def ideation_create_epic(request: Request):
    """PO agent structures project + epic + features + stories from ideation."""
    import subprocess as _sp
    from ...llm.client import get_llm_client, LLMMessage
    from ...missions.store import get_mission_store, MissionDef
    from ...missions.product import get_product_backlog, FeatureDef, UserStoryDef
    from ...projects.manager import get_project_store, Project
    from ...config import FACTORY_ROOT

    data = await request.json()
    idea = data.get("goal", "") or data.get("name", "")
    findings = data.get("description", "")

    # ── Step 1: PO agent structures via LLM ──
    client = get_llm_client()
    prompt = f"Idée originale:\n{idea}\n\nAnalyses des experts:\n{findings}"
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt=_PO_EPIC_SYSTEM,
            temperature=0.5,
            max_tokens=4096,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        plan = json.loads(raw)
    except Exception as e:
        logger.error("PO epic structuring failed: %s", e)
        slug = idea[:30].lower().replace(" ", "-").replace("'", "")
        slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
        plan = {
            "project": {"id": slug or "new-project", "name": idea[:60] or "New Project",
                        "description": idea, "stack": [], "factory_type": "standalone"},
            "epic": {"name": data.get("name", idea[:100]),
                     "description": findings, "goal": idea},
            "features": [], "team": [],
        }

    proj_data = plan.get("project", {})
    epic_data = plan.get("epic", {})
    features_data = plan.get("features", [])
    team_data = plan.get("team", [])

    # ── Step 2 & 3: Create project or use existing ──
    existing_project_id = data.get("project_id", "").strip()
    project_store = get_project_store()

    if existing_project_id:
        # Use existing project
        project_id = existing_project_id
        existing = project_store.get(project_id)
        project_name = existing.name if existing else project_id
        stack = proj_data.get("stack", [])
    else:
        # Create new project directory + git init
        project_id = proj_data.get("id", "new-project")
        project_path = str(FACTORY_ROOT.parent / project_id)
        proj_dir = Path(project_path)
        vision_content = ""

        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
            for d in ("src", "tests", "docs"):
                (proj_dir / d).mkdir(exist_ok=True)

            stack = proj_data.get("stack", [])
            vision_content = f"# {proj_data.get('name', project_id)}\n\n"
            vision_content += f"## Vision\n\n{proj_data.get('description', '')}\n\n"
            vision_content += f"## Epic: {epic_data.get('name', '')}\n\n{epic_data.get('description', '')}\n\n"
            vision_content += f"## Objectifs\n\n{epic_data.get('goal', '')}\n\n"
            if features_data:
                vision_content += "## Features\n\n"
                for f in features_data:
                    vision_content += f"- **{f.get('name', '')}**: {f.get('description', '')}\n"
            vision_content += f"\n## Stack technique\n\n{', '.join(stack)}\n"
            (proj_dir / "VISION.md").write_text(vision_content, encoding="utf-8")

            readme = f"# {proj_data.get('name', project_id)}\n\n{proj_data.get('description', '')}\n\n"
            readme += f"Stack: {', '.join(stack)}\n"
            (proj_dir / "README.md").write_text(readme, encoding="utf-8")

            if not (proj_dir / ".git").exists():
                _sp.run(["git", "init"], cwd=str(proj_dir), capture_output=True, timeout=10)
                _sp.run(["git", "add", "."], cwd=str(proj_dir), capture_output=True, timeout=10)
                _sp.run(["git", "commit", "-m", "Initial commit from ideation"],
                        cwd=str(proj_dir), capture_output=True, timeout=10)
        except Exception as e:
            logger.warning("Project dir creation: %s", e)

        project = Project(
            id=project_id,
            name=proj_data.get("name", project_id),
            path=project_path,
            description=proj_data.get("description", ""),
            factory_type=proj_data.get("factory_type", "standalone"),
            domains=[s.lower() for s in stack],
            vision=vision_content,
            values=["quality", "feedback", "tdd"],
            lead_agent_id="product_manager",
            agents=[t.get("role", "") for t in team_data],
            status="active",
        )
        project_store.create(project)
        project_name = project.name

    # ── Step 4: Create epic (mission) with type & workflow routing ──
    request_type = data.get("request_type", "new_project")
    type_map = {
        "new_project": "epic", "new_feature": "feature", "bug_fix": "bug",
        "tech_debt": "debt", "migration": "migration", "security_audit": "security",
    }
    workflow_map = {
        "new_project": "ideation-to-prod", "new_feature": "feature-request",
        "bug_fix": "sf-pipeline", "tech_debt": "tech-debt-reduction",
        "migration": "migration-sharelook", "security_audit": "review-cycle",
    }
    mission_type = type_map.get(request_type, "epic")
    workflow_id = workflow_map.get(request_type, "feature-request")
    po = data.get("po_proposal", {})

    mission_store = get_mission_store()
    mission = MissionDef(
        name=epic_data.get("name", "Epic from ideation"),
        description=epic_data.get("description", ""),
        goal=epic_data.get("goal", ""),
        status="planning",
        type=mission_type,
        project_id=project_id,
        workflow_id=workflow_id,
        wsjf_score=po.get("priority_wsjf", 0),
        created_by="product_manager",
        config={"team": team_data, "stack": stack, "idea": idea,
                "request_type": request_type, "po_proposal": po},
    )
    mission = mission_store.create_mission(mission)

    # ── Step 5: Create features + user stories ──
    backlog = get_product_backlog()
    created_features = []
    for fd in features_data:
        feat = backlog.create_feature(FeatureDef(
            epic_id=mission.id,
            name=fd.get("name", ""),
            description=fd.get("description", ""),
            acceptance_criteria=fd.get("acceptance_criteria", ""),
            story_points=fd.get("story_points", 5),
        ))
        stories_out = []
        for sd in fd.get("stories", []):
            story = backlog.create_story(UserStoryDef(
                feature_id=feat.id,
                title=sd.get("title", ""),
                description=sd.get("description", ""),
                acceptance_criteria=sd.get("acceptance_criteria", ""),
                story_points=sd.get("story_points", 3),
            ))
            stories_out.append({"id": story.id, "title": story.title,
                                "points": story.story_points})
        created_features.append({"id": feat.id, "name": feat.name,
                                 "points": feat.story_points, "stories": stories_out})

    # ── Step 6: Link ideation session → epic ──
    ideation_sid = data.get("session_id", "")
    if ideation_sid:
        from ...db.migrations import get_db as _get_db
        db = _get_db()
        try:
            db.execute(
                "UPDATE ideation_sessions SET status='epic_created', mission_id=?, project_id=? WHERE id=?",
                (mission.id, project_id, ideation_sid),
            )
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    # ── Step 7: Populate project memory (wiki-like knowledge) ──
    try:
        from ...memory.manager import get_memory_manager
        mem = get_memory_manager()
        if stack:
            mem.project_store(project_id, "stack", ", ".join(stack),
                              category="architecture", source="ideation", confidence=0.9)
        mem.project_store(project_id, "epic", epic_data.get("name", ""),
                          category="vision", source="ideation", confidence=0.9)
        if epic_data.get("goal"):
            mem.project_store(project_id, "goal", epic_data["goal"],
                              category="vision", source="ideation", confidence=0.9)
        for t in team_data:
            mem.project_store(project_id, f"team:{t.get('role','')}",
                              t.get("justification", ""),
                              category="team", source="ideation", confidence=0.8)
        mem.project_store(project_id, "workflow", workflow_id,
                          category="process", source="ideation", confidence=0.85)
        for fd in features_data:
            mem.project_store(project_id, f"feature:{fd.get('name','')}",
                              fd.get("description", ""),
                              category="backlog", source="ideation", confidence=0.85)
        if ideation_sid:
            from ...db.migrations import get_db as _gdb2
            _db2 = _gdb2()
            try:
                findings_rows = _db2.execute(
                    "SELECT type, text FROM ideation_findings WHERE session_id=?",
                    (ideation_sid,),
                ).fetchall()
                for fr in findings_rows:
                    cat = "risk" if fr["type"] == "risk" else "opportunity" if fr["type"] == "opportunity" else "decision"
                    mem.project_store(project_id, f"{fr['type']}:{fr['text'][:50]}",
                                      fr["text"], category=cat, source="ideation", confidence=0.75)
            except Exception:
                pass
            finally:
                _db2.close()
    except Exception as e:
        logger.warning("Memory auto-populate: %s", e)

    # ── Step 8: Auto-launch workflow (agents take over) ──
    session_id_live = None
    try:
        from ...sessions.store import get_session_store, SessionDef, MessageDef
        from ...workflows.store import get_workflow_store

        wf_store = get_workflow_store()
        wf = wf_store.get(workflow_id)
        if wf:
            session_store = get_session_store()
            session = SessionDef(
                name=f"{mission.name}",
                goal=mission.goal or mission.description or "",
                project_id=project_id,
                status="active",
                config={"workflow_id": workflow_id, "mission_id": mission.id},
            )
            session = session_store.create(session)
            session_store.add_message(MessageDef(
                session_id=session.id,
                from_agent="system",
                message_type="system",
                content=f"Workflow **{wf.name}** lancé pour l'epic **{mission.name}**.\nStack: {', '.join(stack)}\nGoal: {mission.goal or 'N/A'}",
            ))
            task_desc = (
                f"Projet: {project_name}\n"
                f"Epic: {mission.name}\n"
                f"Goal: {mission.goal or mission.description}\n"
                f"Stack: {', '.join(stack)}\n"
                f"Features: {', '.join(f.get('name','') for f in features_data)}\n"
                f"Répertoire projet: {str(FACTORY_ROOT.parent / project_id)}"
            )
            asyncio.create_task(_run_workflow_background(wf, session.id, task_desc, project_id))
            session_id_live = session.id
            logger.info("Auto-launched workflow %s for project %s (session %s)", workflow_id, project_id, session.id)
    except Exception as e:
        logger.warning("Auto-launch workflow: %s", e)

    return JSONResponse({
        "project_id": project_id,
        "project_name": project_name,
        "mission_id": mission.id,
        "mission_name": mission.name,
        "type": mission_type,
        "workflow_id": workflow_id,
        "features": created_features,
        "team": team_data,
        "stack": stack,
        "session_id": session_id_live,
        "redirect": f"/sessions/{session_id_live}/live" if session_id_live else f"/projects/{project_id}/overview",
    })


# ── Ideation History ─────────────────────────────────────────────

@router.get("/api/ideation/sessions")
async def ideation_sessions_list():
    """List all ideation sessions (most recent first)."""
    from ...db.migrations import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM ideation_sessions ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return JSONResponse([{
            "id": r["id"], "title": r["title"], "prompt": r["prompt"],
            "status": r["status"], "mission_id": r["mission_id"] or "",
            "project_id": r["project_id"] or "",
            "created_at": r["created_at"] or "",
        } for r in rows])
    finally:
        db.close()


@router.get("/api/ideation/sessions/{session_id}")
async def ideation_session_detail(session_id: str):
    """Get full ideation session with messages and findings."""
    from ...db.migrations import get_db
    db = get_db()
    try:
        sess = db.execute(
            "SELECT * FROM ideation_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not sess:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        messages = db.execute(
            "SELECT * FROM ideation_messages WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        findings = db.execute(
            "SELECT * FROM ideation_findings WHERE session_id=?", (session_id,),
        ).fetchall()
        return JSONResponse({
            "id": sess["id"], "title": sess["title"], "prompt": sess["prompt"],
            "status": sess["status"], "mission_id": sess["mission_id"] or "",
            "project_id": sess["project_id"] or "",
            "created_at": sess["created_at"] or "",
            "messages": [{"agent_id": m["agent_id"], "agent_name": m["agent_name"],
                          "role": m["role"] if "role" in m.keys() else "",
                          "target": m["target"] if "target" in m.keys() else "",
                          "content": m["content"], "color": m["color"],
                          "avatar_url": m["avatar_url"] or "",
                          "created_at": m["created_at"] or ""} for m in messages],
            "findings": [{"type": f["type"], "text": f["text"]} for f in findings],
        })
    finally:
        db.close()


@router.get("/ideation/history", response_class=HTMLResponse)
async def ideation_history_page(request: Request):
    """Dedicated ideation history page."""
    from ...db.migrations import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM ideation_sessions ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        sessions = []
        for r in rows:
            msg_count = db.execute(
                "SELECT COUNT(*) as c FROM ideation_messages WHERE session_id=?",
                (r["id"],),
            ).fetchone()["c"]
            finding_count = db.execute(
                "SELECT COUNT(*) as c FROM ideation_findings WHERE session_id=?",
                (r["id"],),
            ).fetchone()["c"]
            sessions.append({
                "id": r["id"], "title": r["title"], "prompt": r["prompt"],
                "status": r["status"], "mission_id": r["mission_id"] or "",
                "project_id": r["project_id"] or "",
                "created_at": r["created_at"] or "",
                "msg_count": msg_count, "finding_count": finding_count,
            })
    finally:
        db.close()
    return _templates(request).TemplateResponse("ideation_history.html", {
        "request": request, "page_title": "Historique Idéation",
        "sessions": sessions,
    })


