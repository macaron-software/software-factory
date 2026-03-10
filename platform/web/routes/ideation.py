"""Web routes — Ideation workspace."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Ideation Workspace ───────────────────────────────────────────

_IDEATION_AGENTS = [
    {
        "id": "metier",
        "name": "Camille Durand",
        "short_role": "Business Analyst",
        "color": "#2563eb",
    },
    {
        "id": "architecte",
        "name": "Pierre Duval",
        "short_role": "Solution Architect",
        "color": "#0891b2",
    },
    {
        "id": "ux_designer",
        "name": "Chloé Bertrand",
        "short_role": "UX Designer",
        "color": "#8b5cf6",
    },
    {
        "id": "securite",
        "name": "Nadia Benali",
        "short_role": "Sécurité",
        "color": "#dc2626",
    },
    {
        "id": "product_manager",
        "name": "Alexandre Faure",
        "short_role": "Product Manager",
        "color": "#16a34a",
    },
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
        # Use local jpg only if it's a real photo (>10KB); tiny files are DiceBear SVG conversions
        if jpg.exists() and jpg.stat().st_size > 10_000:
            avatar_url = f"/static/avatars/{ia['id']}.jpg"
        elif svg_f.exists() and svg_f.stat().st_size > 10_000:
            avatar_url = f"/static/avatars/{ia['id']}.svg"
        else:
            # Photorealistic avatar via pravatar.cc (consistent per agent id)
            avatar_url = f"https://i.pravatar.cc/150?u={ia['id']}"
        enriched.append(
            {
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
            }
        )

    # Load past ideation sessions for sidebar
    from ...db.adapter import get_connection as _gdb

    _db = _gdb()
    try:
        _rows = _db.execute(
            "SELECT id, title, status, created_at FROM ideation_sessions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        past_sessions = [
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"] or "",
            }
            for r in _rows
        ]
    except Exception:
        past_sessions = []
    finally:
        _db.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    return _templates(request).TemplateResponse(
        "ideation.html",
        {
            "request": request,
            "page_title": "Idéation",
            "agents": enriched,
            "projects": [
                {"id": p.id, "name": p.name} for p in get_project_store().list_all()
            ],
            "past_sessions": past_sessions,
            "base_template": "base_partial.html" if is_htmx else "base.html",
        },
    )


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

    # Prompt injection guard
    from ...security.prompt_guard import get_prompt_guard

    prompt, score = get_prompt_guard().check_and_sanitize(prompt, source="ideation")
    if score.blocked:
        return JSONResponse({"error": prompt}, status_code=400)

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

    # Persist to ideation_sessions table so /api/ideation/sessions can find it
    from ...db.adapter import get_connection as _gdb_i
    from ...auth.middleware import get_current_user as _get_user

    _db_i = _gdb_i()
    _user_id = ""
    try:
        _u = await _get_user(request)
        _user_id = _u.id if _u else ""
    except Exception:
        pass
    try:
        title = prompt[:80]
        _db_i.execute(
            "INSERT INTO ideation_sessions (id, title, prompt, status, user_id) VALUES (?, ?, ?, 'active', ?)"
            " ON CONFLICT (id) DO NOTHING",
            (session_id, title, prompt, _user_id),
        )
        _db_i.commit()
    except Exception as _e:
        logger.warning("ideation_sessions insert: %s", _e)
    finally:
        _db_i.close()

    # Store user message
    session_store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            message_type="delegate",
            content=prompt,
        )
    )

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
        for b in debaters[i + 1 :]:
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
            # Persist agent messages to ideation_messages + ideation_findings
            _msgs = session_store.get_messages(session_id)
            from ...db.adapter import get_connection as _gdb_m

            _db_m = _gdb_m()
            try:
                for _m in _msgs:
                    if getattr(_m, "from_agent", "") == "user":
                        continue
                    _agent_id = getattr(_m, "from_agent", "")
                    _content = getattr(_m, "content", "")
                    _agent_meta = next(
                        (a for a in _IDEATION_AGENTS if a["id"] == _agent_id), {}
                    )
                    try:
                        _db_m.execute(
                            "INSERT INTO ideation_messages (session_id, agent_id, agent_name, role, content, color, avatar_url)"
                            " VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                session_id,
                                _agent_id,
                                _agent_meta.get("name", _agent_id),
                                _agent_meta.get("role", ""),
                                _content,
                                _agent_meta.get("color", "#666"),
                                "",
                            ),
                        )
                    except Exception:
                        pass
                # Save consolidated findings (product_manager's last message)
                _po_msgs = [
                    _m
                    for _m in _msgs
                    if getattr(_m, "from_agent", "") == "product_manager"
                ]
                if _po_msgs:
                    _findings_text = getattr(_po_msgs[-1], "content", "")
                    try:
                        _db_m.execute(
                            "INSERT INTO ideation_findings (session_id, type, text) VALUES (?, ?, ?)",
                            (session_id, "synthesis", _findings_text),
                        )
                    except Exception:
                        pass
                _db_m.execute(
                    "UPDATE ideation_sessions SET status='complete' WHERE id=?",
                    (session_id,),
                )
                _db_m.commit()
            except Exception as _e:
                logger.warning("ideation persist messages: %s", _e)
            finally:
                _db_m.close()
        except Exception as e:
            logger.error("Ideation pattern failed: %s", e)
            session_store.add_message(
                MessageDef(
                    session_id=session_id,
                    from_agent="system",
                    message_type="system",
                    content=f"Ideation error: {e}",
                )
            )

    asyncio.create_task(_run_ideation())

    return JSONResponse(
        {
            "session_id": session_id,
            "status": "started",
            "sse_url": f"/api/sessions/{session_id}/sse",
        }
    )


_PO_EPIC_SYSTEM = """Tu es Alexandre Faure, Product Owner senior, certifié SAFe Program Consultant.
Tu reçois la synthèse d'un atelier d'idéation et tu dois structurer un projet en missions pilotées par la valeur.

## Principes directeurs (LEAN, XP, SAFe, KISS)

**LEAN** : Éliminer le gaspillage. Commence par ce qui délivre le plus de valeur au plus tôt.
**XP** : Itérations courtes, feedback rapide, livraison continue.
**SAFe** : Organise par Value Streams (flux de valeur), pas par couches techniques.
  - Utilise le score WSJF (Weighted Shortest Job First) pour prioriser : (valeur + urgence + réduction risque) / effort
  - Structure en Program Increments (PI) : chaque mission = un PI livrable de bout en bout
**KISS** : Minimum de missions pour couvrir la valeur. Ne pas sur-découper par composant technique.

## Règles de découpage

❌ NE PAS découper par couche technique (ex: "backend", "frontend", "mobile" comme missions séparées)
✅ Découper par **flux de valeur livrable** :
  - Une mission doit livrer de la valeur end-to-end à un persona
  - Exemples : "MVP RDV Patient+Thérapeute", "Foundation & Common Libs", "Mobile Native iOS/Android"
  - Les apps qui servent le même persona/scénario = regrouper si possible
  - Les fondations (infra, libs communes, DevOps) = 1 mission dédiée si critique

## Nombre de missions
- Minimum 1, maximum 6
- Favoriser 2-4 missions bien scoped plutôt que 6-8 missions trop granulaires
- Chaque mission doit être autonome et livrer de la valeur mesurable

Réponds UNIQUEMENT avec ce JSON (sans commentaires, JSON valide strict):
{
  "project": {
    "id": "slug-kebab-case",
    "name": "Nom du Projet",
    "description": "Description courte",
    "stack": ["React Native", "React", "Node.js", "PostgreSQL"],
    "factory_type": "sf"
  },
  "epics": [
    {
      "name": "Nom de la mission (orienté valeur, pas technique)",
      "description": "Ce que ça délivre et à qui",
      "goal": "Critères d'acceptation mesurables (Definition of Done)",
      "stack": ["React Native", "Expo"],
      "type": "epic",
      "wsjf_note": "Justification priorité WSJF courte"
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

Sois pragmatique et concret. Réponds UNIQUEMENT avec le JSON valide, rien d'autre."""


@router.post("/api/ideation/create-epic")
async def ideation_create_epic(request: Request):
    """PO agent structures project + epic + features + stories from ideation."""
    import subprocess as _sp
    from ...llm.client import get_llm_client, LLMMessage
    from ...epics.store import get_epic_store, MissionDef
    from ...missions.product import get_product_backlog, FeatureDef, UserStoryDef
    from ...projects.manager import get_project_store, Project
    from ...config import FACTORY_ROOT

    data = await request.json()
    idea = data.get("goal", "") or data.get("name", "")
    findings = data.get("description", "")

    # If session_id provided, try to load idea + findings from session store / DB
    session_id_in = data.get("session_id", "").strip()
    if session_id_in and not (idea and findings):
        from ...db.adapter import get_connection as _gdb_epic

        _db_epic = _gdb_epic()
        try:
            _sess_row = _db_epic.execute(
                "SELECT prompt, title FROM ideation_sessions WHERE id=?",
                (session_id_in,),
            ).fetchone()
            if _sess_row:
                if not idea:
                    idea = _sess_row["prompt"] or _sess_row["title"] or ""
                if not findings:
                    # Use only the last PM synthesis + one message per other agent (avoid token overflow)
                    _pm_row = _db_epic.execute(
                        "SELECT content FROM ideation_messages WHERE session_id=? AND agent_id='product_manager' ORDER BY created_at DESC LIMIT 1",
                        (session_id_in,),
                    ).fetchone()
                    _other_rows = _db_epic.execute(
                        "SELECT agent_name, content FROM ideation_messages WHERE session_id=? AND agent_id!='product_manager' AND agent_id!='system' ORDER BY created_at DESC LIMIT 4",
                        (session_id_in,),
                    ).fetchall()
                    parts = []
                    if _pm_row and _pm_row["content"]:
                        parts.append(
                            f"[Synthèse Product Manager]:\n{_pm_row['content']}"
                        )
                    for r in _other_rows:
                        if r["content"]:
                            parts.append(f"[{r['agent_name']}]:\n{r['content'][:800]}")
                    findings = "\n\n---\n\n".join(parts)
        except Exception as _ep:
            logger.warning("create-epic session lookup: %s", _ep)
        finally:
            _db_epic.close()
        # Fallback: read from in-memory session_store
        if not findings:
            from ...sessions.store import get_session_store as _gss

            _ss = _gss()
            _session = _ss.get(session_id_in)
            if _session:
                if not idea:
                    idea = getattr(_session, "goal", "") or getattr(
                        _session, "name", ""
                    )
                _msgs = _ss.get_messages(session_id_in)
                findings = "\n\n".join(
                    f"[{getattr(m, 'from_agent', '')}]: {getattr(m, 'content', '')}"
                    for m in _msgs
                    if getattr(m, "from_agent", "") not in ("user", "system")
                    and getattr(m, "content", "")
                )

    # ── Prompt injection guard ──
    from ...security.prompt_guard import get_prompt_guard

    guard = get_prompt_guard()
    idea, score = guard.check_and_sanitize(idea, source="ideation-idea")
    if score.blocked:
        return JSONResponse({"error": idea}, status_code=400)
    findings, score2 = guard.check_and_sanitize(findings, source="ideation-findings")
    if score2.blocked:
        return JSONResponse({"error": findings}, status_code=400)

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
            "project": {
                "id": slug or "new-project",
                "name": idea[:60] or "New Project",
                "description": idea,
                "stack": [],
                "factory_type": "standalone",
            },
            "epic": {
                "name": data.get("name", idea[:100]),
                "description": findings,
                "goal": idea,
            },
            "features": [],
            "team": [],
        }

    proj_data = plan.get("project", {})
    epic_data = plan.get("epic", {})
    # Support both new "epics" array and legacy "features" array
    missions_data = plan.get("epics", [])
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
            if missions_data:
                vision_content += "## Missions\n\n"
                for m in missions_data:
                    vision_content += (
                        f"- **{m.get('name', '')}**: {m.get('description', '')}\n"
                    )
            elif epic_data:
                vision_content += f"## Epic: {epic_data.get('name', '')}\n\n{epic_data.get('description', '')}\n\n"
                vision_content += f"## Objectifs\n\n{epic_data.get('goal', '')}\n\n"
                if features_data:
                    vision_content += "## Features\n\n"
                    for f in features_data:
                        vision_content += (
                            f"- **{f.get('name', '')}**: {f.get('description', '')}\n"
                        )
            vision_content += f"\n## Stack technique\n\n{', '.join(stack)}\n"
            (proj_dir / "VISION.md").write_text(vision_content, encoding="utf-8")

            readme = f"# {proj_data.get('name', project_id)}\n\n{proj_data.get('description', '')}\n\n"
            readme += f"Stack: {', '.join(stack)}\n"
            (proj_dir / "README.md").write_text(readme, encoding="utf-8")

            if not (proj_dir / ".git").exists():
                _sp.run(
                    ["git", "init"], cwd=str(proj_dir), capture_output=True, timeout=10
                )
                _sp.run(
                    ["git", "add", "."],
                    cwd=str(proj_dir),
                    capture_output=True,
                    timeout=10,
                )
                _sp.run(
                    ["git", "commit", "-m", "Initial commit from ideation"],
                    cwd=str(proj_dir),
                    capture_output=True,
                    timeout=10,
                )

            # Generate CI/CD pipeline based on stack
            from ...projects.manager import ProjectStore

            ProjectStore.generate_cicd(project_path, stack)
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
        project_store.auto_provision(project_id, project.name)
        project_name = project.name

    # ── Step 4: Create missions with type & workflow routing ──
    request_type = data.get("request_type", "new_project")
    type_map = {
        "new_project": "epic",
        "new_feature": "feature",
        "bug_fix": "bug",
        "tech_debt": "debt",
        "migration": "migration",
        "security_audit": "security",
    }
    workflow_map = {
        "new_project": "ideation-to-prod",
        "new_feature": "feature-request",
        "bug_fix": "sf-pipeline",
        "tech_debt": "tech-debt-reduction",
        "migration": "migration-angular",
        "security_audit": "review-cycle",
    }
    mission_type = type_map.get(request_type, "epic")
    workflow_id = workflow_map.get(request_type, "feature-request")
    po = data.get("po_proposal", {})

    epic_store = get_epic_store()

    # Create one mission per component (new format) or fallback to single epic (legacy)
    created_missions = []
    if missions_data:
        for md in missions_data:
            m_stack = md.get("stack", stack)
            m_type = md.get("type", mission_type)
            m_wf = (
                workflow_map.get(m_type, workflow_id)
                if m_type in workflow_map
                else workflow_id
            )
            m = MissionDef(
                name=md.get("name", "Mission from ideation"),
                description=md.get("description", ""),
                goal=md.get("goal", ""),
                status="planning",
                type=m_type,
                project_id=project_id,
                workflow_id=m_wf,
                wsjf_score=po.get("priority_wsjf", 0),
                created_by="product_manager",
                config={
                    "team": team_data,
                    "stack": m_stack,
                    "idea": idea,
                    "request_type": request_type,
                    "po_proposal": po,
                },
            )
            m = epic_store.create_mission(m)
            created_missions.append(m)
        mission = created_missions[0] if created_missions else None
    else:
        # Legacy: single epic mission
        mission = MissionDef(
            name=epic_data.get("name", idea[:100]) if epic_data else idea[:100],
            description=epic_data.get("description", "") if epic_data else "",
            goal=epic_data.get("goal", "") if epic_data else "",
            status="planning",
            type=mission_type,
            project_id=project_id,
            workflow_id=workflow_id,
            wsjf_score=po.get("priority_wsjf", 0),
            created_by="product_manager",
            config={
                "team": team_data,
                "stack": stack,
                "idea": idea,
                "request_type": request_type,
                "po_proposal": po,
            },
        )
        mission = epic_store.create_mission(mission)
        created_missions.append(mission)

    # ── Step 5: Create features + user stories (legacy, for single epic) ──
    backlog = get_product_backlog()
    created_features = []
    for fd in features_data:
        feat = backlog.create_feature(
            FeatureDef(
                epic_id=mission.id,
                name=fd.get("name", ""),
                description=fd.get("description", ""),
                acceptance_criteria=fd.get("acceptance_criteria", ""),
                story_points=fd.get("story_points", 5),
            )
        )
        stories_out = []
        for sd in fd.get("stories", []):
            story = backlog.create_story(
                UserStoryDef(
                    feature_id=feat.id,
                    title=sd.get("title", ""),
                    description=sd.get("description", ""),
                    acceptance_criteria=sd.get("acceptance_criteria", ""),
                    story_points=sd.get("story_points", 3),
                )
            )
            stories_out.append(
                {"id": story.id, "title": story.title, "points": story.story_points}
            )
        created_features.append(
            {
                "id": feat.id,
                "name": feat.name,
                "points": feat.story_points,
                "stories": stories_out,
            }
        )

    # ── Step 6: Link ideation session → epic ──
    ideation_sid = data.get("session_id", "")
    if ideation_sid:
        from ...db.adapter import get_connection as _get_db

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
            mem.project_store(
                project_id,
                "stack",
                ", ".join(stack),
                category="architecture",
                source="ideation",
                confidence=0.9,
            )
        mem.project_store(
            project_id,
            "epic",
            epic_data.get("name", ""),
            category="vision",
            source="ideation",
            confidence=0.9,
        )
        if epic_data.get("goal"):
            mem.project_store(
                project_id,
                "goal",
                epic_data["goal"],
                category="vision",
                source="ideation",
                confidence=0.9,
            )
        for t in team_data:
            mem.project_store(
                project_id,
                f"team:{t.get('role', '')}",
                t.get("justification", ""),
                category="team",
                source="ideation",
                confidence=0.8,
            )
        mem.project_store(
            project_id,
            "workflow",
            workflow_id,
            category="process",
            source="ideation",
            confidence=0.85,
        )
        for fd in features_data:
            mem.project_store(
                project_id,
                f"feature:{fd.get('name', '')}",
                fd.get("description", ""),
                category="backlog",
                source="ideation",
                confidence=0.85,
            )
        if ideation_sid:
            from ...db.adapter import get_connection as _gdb2

            _db2 = _gdb2()
            try:
                findings_rows = _db2.execute(
                    "SELECT type, text FROM ideation_findings WHERE session_id=?",
                    (ideation_sid,),
                ).fetchall()
                for fr in findings_rows:
                    cat = (
                        "risk"
                        if fr["type"] == "risk"
                        else "opportunity"
                        if fr["type"] == "opportunity"
                        else "decision"
                    )
                    mem.project_store(
                        project_id,
                        f"{fr['type']}:{fr['text'][:50]}",
                        fr["text"],
                        category=cat,
                        source="ideation",
                        confidence=0.75,
                    )
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
        from .workflows import _run_workflow_background

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
            session_store.add_message(
                MessageDef(
                    session_id=session.id,
                    from_agent="system",
                    message_type="system",
                    content=f"Workflow **{wf.name}** lancé pour l'epic **{mission.name}**.\nStack: {', '.join(stack)}\nGoal: {mission.goal or 'N/A'}",
                )
            )
            task_desc = (
                f"Projet: {project_name}\n"
                f"Epic: {mission.name}\n"
                f"Goal: {mission.goal or mission.description}\n"
                f"Stack: {', '.join(stack)}\n"
                f"Features: {', '.join(f.get('name', '') for f in features_data)}\n"
                f"Répertoire projet: {str(FACTORY_ROOT.parent / project_id)}"
            )
            asyncio.create_task(
                _run_workflow_background(wf, session.id, task_desc, project_id)
            )
            session_id_live = session.id
            logger.info(
                "Auto-launched workflow %s for project %s (session %s)",
                workflow_id,
                project_id,
                session.id,
            )
    except Exception as e:
        logger.warning("Auto-launch workflow: %s", e)

    return JSONResponse(
        {
            "project_id": project_id,
            "project_name": project_name,
            "mission_id": created_missions[0].id if created_missions else None,
            "mission_name": created_missions[0].name if created_missions else None,
            "epics": [{"id": m.id, "name": m.name} for m in created_missions],
            "missions_count": len(created_missions),
            "type": mission_type,
            "workflow_id": workflow_id,
            "features": created_features,
            "team": team_data,
            "stack": stack,
            "session_id": session_id_live,
            "redirect": f"/sessions/{session_id_live}/live"
            if session_id_live
            else f"/projects/{project_id}/overview",
        }
    )


# ── Ideation History ─────────────────────────────────────────────


@router.get("/api/ideation/sessions")
async def ideation_sessions_list(request: Request):
    """List ideation sessions for the current user (most recent first)."""
    from ...db.adapter import get_connection as get_db
    from ...auth.middleware import get_current_user

    user = await get_current_user(request)
    db = get_db()
    try:
        if user and user.role != "admin":
            rows = db.execute(
                "SELECT * FROM ideation_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (user.id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM ideation_sessions ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        return JSONResponse(
            [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "prompt": r["prompt"],
                    "status": r["status"],
                    "mission_id": r["mission_id"] or "",
                    "project_id": r["project_id"] or "",
                    "created_at": r["created_at"] or "",
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@router.get("/api/ideation/sessions/{session_id}")
async def ideation_session_detail(session_id: str):
    """Get full ideation session with messages and findings."""
    from ...db.adapter import get_connection as get_db

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
            "SELECT * FROM ideation_findings WHERE session_id=?",
            (session_id,),
        ).fetchall()
        return JSONResponse(
            {
                "id": sess["id"],
                "title": sess["title"],
                "prompt": sess["prompt"],
                "status": sess["status"],
                "mission_id": sess["mission_id"] or "",
                "project_id": sess["project_id"] or "",
                "created_at": sess["created_at"] or "",
                "messages": [
                    {
                        "agent_id": m["agent_id"],
                        "agent_name": m["agent_name"],
                        "role": m["role"] if "role" in m.keys() else "",
                        "target": m["target"] if "target" in m.keys() else "",
                        "content": m["content"],
                        "color": m["color"],
                        "avatar_url": m["avatar_url"] or "",
                        "created_at": m["created_at"] or "",
                    }
                    for m in messages
                ],
                "findings": [{"type": f["type"], "text": f["text"]} for f in findings],
            }
        )
    finally:
        db.close()


@router.get("/ideation/history", response_class=HTMLResponse)
async def ideation_history_page(request: Request):
    """Dedicated ideation history page."""
    from ...db.adapter import get_connection as get_db

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
            sessions.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "prompt": r["prompt"],
                    "status": r["status"],
                    "mission_id": r["mission_id"] or "",
                    "project_id": r["project_id"] or "",
                    "created_at": r["created_at"] or "",
                    "msg_count": msg_count,
                    "finding_count": finding_count,
                }
            )
    finally:
        db.close()
    return _templates(request).TemplateResponse(
        "ideation_history.html",
        {
            "request": request,
            "page_title": "Historique Idéation",
            "sessions": sessions,
        },
    )
