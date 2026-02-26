"""Web routes — Marketing Ideation workspace."""

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

# ── Marketing team agents ────────────────────────────────────────

_MKT_AGENTS = [
    {
        "id": "mkt-cmo",
        "name": "Sophie Laurent",
        "short_role": "CMO",
        "color": "#f59e0b",
    },
    {
        "id": "mkt-trend",
        "name": "Hugo Renard",
        "short_role": "Market & Trends",
        "color": "#0891b2",
    },
    {
        "id": "mkt-bench",
        "name": "Emma Petit",
        "short_role": "Competitive Intel",
        "color": "#8b5cf6",
    },
    {
        "id": "mkt-growth",
        "name": "Lucas Martin",
        "short_role": "Growth Hacker",
        "color": "#16a34a",
    },
    {
        "id": "mkt-brand",
        "name": "Léa Bernard",
        "short_role": "Brand Strategist",
        "color": "#ec4899",
    },
    {
        "id": "mkt-insights",
        "name": "Marie Leclerc",
        "short_role": "Customer Insights",
        "color": "#f97316",
    },
]

# ── Pages ─────────────────────────────────────────────────────────


@router.get("/mkt-ideation", response_class=HTMLResponse)
async def mkt_ideation_page(request: Request):
    """Marketing ideation workspace."""
    from ...agents.store import get_agent_store
    from ...projects.manager import get_project_store

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    db_map = {a.id: a for a in all_agents}
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    enriched = []
    for ma in _MKT_AGENTS:
        a = db_map.get(ma["id"])
        jpg = avatar_dir / f"{ma['id']}.jpg"
        svg_f = avatar_dir / f"{ma['id']}.svg"
        avatar_url = (
            f"/static/avatars/{ma['id']}.jpg"
            if jpg.exists()
            else f"/static/avatars/{ma['id']}.svg"
            if svg_f.exists()
            else ""
        )
        enriched.append(
            {
                **ma,
                "avatar_url": avatar_url,
                "description": (a.description or "") if a else "",
                "tagline": (a.tagline or "") if a else "",
            }
        )

    from ...db.migrations import get_db as _gdb

    _db = _gdb()
    try:
        _rows = _db.execute(
            "SELECT id, title, status, created_at FROM mkt_ideation_sessions ORDER BY created_at DESC LIMIT 20"
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

    return _templates(request).TemplateResponse(
        "mkt_ideation.html",
        {
            "request": request,
            "page_title": "Idéation Business",
            "agents": enriched,
            "projects": [
                {"id": p.id, "name": p.name} for p in get_project_store().list_all()
            ],
            "past_sessions": past_sessions,
        },
    )


# ── Launch multi-agent marketing analysis ────────────────────────


@router.post("/api/mkt-ideation")
async def mkt_ideation_submit(request: Request):
    """Launch marketing ideation via multi-agent network pattern."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...patterns.engine import run_pattern
    from ...patterns.store import PatternDef
    import uuid

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return JSONResponse({"error": "Prompt requis"}, status_code=400)

    from ...security.prompt_guard import get_prompt_guard

    prompt, score = get_prompt_guard().check_and_sanitize(prompt, source="mkt-ideation")
    if score.blocked:
        return JSONResponse({"error": prompt}, status_code=400)

    session_id = data.get("session_id", "") or str(uuid.uuid4())[:8]

    session_store = get_session_store()
    existing = session_store.get(session_id)
    if not existing:
        session = SessionDef(
            id=session_id,
            name=f"MktIdeation: {prompt[:60]}",
            goal=prompt,
            status="active",
            config={"type": "mkt_ideation", "pattern": "network"},
        )
        session = session_store.create(session)
    else:
        session = existing

    session_store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            message_type="delegate",
            content=prompt,
        )
    )

    # Save to mkt_ideation_sessions
    from ...db.migrations import get_db as _gdb

    _db = _gdb()
    try:
        title = prompt[:80] if len(prompt) > 80 else prompt
        _db.execute(
            "INSERT INTO mkt_ideation_sessions (id, title, prompt, status) VALUES (?, ?, ?, 'active') "
            "ON CONFLICT (id) DO NOTHING",
            (session_id, title, prompt),
        )
        _db.commit()
    except Exception as e:
        logger.warning("mkt_ideation_sessions insert: %s", e)
    finally:
        _db.close()

    # Build network pattern: all experts debate, CMO synthesizes
    agent_nodes = [{"id": a["id"], "agent_id": a["id"]} for a in _MKT_AGENTS]
    experts = [a["id"] for a in _MKT_AGENTS if a["id"] != "mkt-cmo"]
    edges = []
    for i, a in enumerate(experts):
        for b in experts[i + 1 :]:
            edges.append({"from": a, "to": b, "type": "bidirectional"})
    for a in experts:
        edges.append({"from": a, "to": "mkt-cmo", "type": "report"})

    # Augment prompt with marketing-specific instructions
    augmented_prompt = (
        f"Analyse marketing complète pour : {prompt}\n\n"
        "Chaque expert doit contribuer dans son domaine :\n"
        "- Hugo (Trends) : taille du marché, tendances émergentes, timing\n"
        "- Emma (Competitive Intel) : paysage concurrentiel, différenciateurs\n"
        "- Lucas (Growth) : canaux d'acquisition, modèle de croissance, CAC/LTV\n"
        "- Léa (Brand) : positionnement, UVP, messaging, identité de marque\n"
        "- Marie (Customer Insights) : personas, JTBD, pain points, segmentation\n"
        "- Sophie (CMO) : synthèse stratégique et recommandations go-to-market\n"
        "Soyez concrets, chiffrés et actionnables."
    )

    pattern = PatternDef(
        id=f"mkt-ideation-{session_id}",
        name="Idéation Marketing multi-expert",
        type="network",
        agents=agent_nodes,
        edges=edges,
        config={"max_rounds": 2},
    )

    async def _run():
        try:
            await asyncio.sleep(0.5)
            await run_pattern(pattern, session_id, augmented_prompt)
        except Exception as e:
            logger.error("MktIdeation pattern failed: %s", e)
            session_store.add_message(
                MessageDef(
                    session_id=session_id,
                    from_agent="system",
                    message_type="system",
                    content=f"Erreur: {e}",
                )
            )

    asyncio.create_task(_run())

    return JSONResponse(
        {
            "session_id": session_id,
            "status": "started",
            "sse_url": f"/api/sessions/{session_id}/sse",
        }
    )


# ── Generate structured marketing plan ───────────────────────────

_MKT_PLAN_SYSTEM = """Tu es Sophie Laurent, Chief Marketing Officer expérimentée.
Tu reçois les analyses de ton équipe marketing (trends, competitive intel, growth, brand, customer insights)
et tu dois structurer un Plan Marketing complet et une Vision Business.

Produis un JSON structuré avec ces sections :
{
  "executive_summary": "Résumé exécutif en 3-4 phrases percutantes",
  "business_vision": {
    "problem": "Quel problème résout-on ?",
    "solution": "Notre solution en une phrase",
    "uvp": "Unique Value Proposition",
    "market_timing": "Pourquoi maintenant ?"
  },
  "market_analysis": {
    "tam": "Total Addressable Market (€ ou nb utilisateurs)",
    "sam": "Serviceable Addressable Market",
    "som": "Serviceable Obtainable Market (an 1-3)",
    "growth_rate": "Taux de croissance annuel du marché",
    "key_trends": ["tendance 1", "tendance 2", "tendance 3"],
    "swot": {
      "strengths": ["force 1", "force 2"],
      "weaknesses": ["faiblesse 1", "faiblesse 2"],
      "opportunities": ["opportunité 1", "opportunité 2"],
      "threats": ["menace 1", "menace 2"]
    }
  },
  "competitive_analysis": [
    {
      "name": "Concurrent A",
      "type": "direct",
      "strengths": ["force"],
      "weaknesses": ["faiblesse"],
      "positioning": "Comment ils se positionnent"
    }
  ],
  "differentiators": ["Ce qui nous rend unique 1", "Ce qui nous rend unique 2"],
  "target_personas": [
    {
      "name": "Persona 1",
      "profile": "Description courte (âge, rôle, contexte)",
      "jtbd": "Job-to-be-Done principal",
      "pain_points": ["douleur 1", "douleur 2"],
      "channels": ["où les trouver"],
      "wtp": "Willingness to Pay estimée"
    }
  ],
  "go_to_market": {
    "strategy": "GTM strategy en 2-3 phrases",
    "beachhead": "Premier marché cible (niche beachhead)",
    "phases": [
      {
        "name": "Phase 1 — Pré-lancement",
        "duration": "Mois 1-3",
        "objectives": ["objectif 1"],
        "actions": ["action 1", "action 2"],
        "kpis": ["KPI 1"]
      },
      {
        "name": "Phase 2 — Lancement",
        "duration": "Mois 4-6",
        "objectives": ["objectif 1"],
        "actions": ["action 1", "action 2"],
        "kpis": ["KPI 1"]
      },
      {
        "name": "Phase 3 — Croissance",
        "duration": "Mois 7-12",
        "objectives": ["objectif 1"],
        "actions": ["action 1", "action 2"],
        "kpis": ["KPI 1"]
      }
    ]
  },
  "marketing_channels": [
    {
      "channel": "SEO / Content Marketing",
      "priority": "high",
      "rationale": "Pourquoi ce canal",
      "budget_pct": 25,
      "tactics": ["tactique 1"],
      "kpis": ["trafic organique", "leads"]
    }
  ],
  "growth_model": {
    "primary_engine": "content | virality | sales | paid",
    "cac_target": "CAC cible",
    "ltv_estimate": "LTV estimée",
    "payback_period": "Période de remboursement CAC",
    "viral_loop": "Description du mécanisme viral (si applicable)"
  },
  "brand_strategy": {
    "archetype": "Archétype de marque",
    "personality": ["trait 1", "trait 2", "trait 3"],
    "tone_of_voice": "Description du ton",
    "headline": "Headline principal",
    "tagline": "Tagline",
    "elevator_pitch": "Pitch ascenseur (30 secondes)"
  },
  "kpis_dashboard": [
    {"metric": "CAC", "target": "< 50€", "timeline": "6 mois"},
    {"metric": "MRR", "target": "50k€", "timeline": "12 mois"},
    {"metric": "NPS", "target": "> 40", "timeline": "12 mois"}
  ],
  "budget_indicatif": {
    "total_an1": "Budget total indicatif an 1",
    "breakdown": [
      {"poste": "Content & SEO", "pct": 25},
      {"poste": "Paid Acquisition", "pct": 30},
      {"poste": "Events & PR", "pct": 15},
      {"poste": "Brand & Creative", "pct": 20},
      {"poste": "Outils & Analytics", "pct": 10}
    ]
  },
  "next_actions": [
    "Action immédiate 1 (cette semaine)",
    "Action immédiate 2",
    "Action 30 jours",
    "Action 90 jours"
  ]
}

Sois précis, concret et actionnable. Adapte toutes les valeurs au contexte spécifique de l'idée analysée.
Réponds UNIQUEMENT avec le JSON, sans markdown wrapper."""


@router.post("/api/mkt-ideation/generate-plan")
async def mkt_generate_plan(request: Request):
    """CMO generates a full structured marketing plan from the ideation session."""
    from ...llm.client import get_llm_client, LLMMessage

    data = await request.json()
    session_id = data.get("session_id", "")
    prompt = data.get("prompt", "")
    context = data.get("context", "")  # agent messages collected by frontend

    full_prompt = f"Idée / projet analysé :\n{prompt}\n\nAnalyses de l'équipe marketing :\n{context}"

    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=full_prompt)],
            system_prompt=_MKT_PLAN_SYSTEM,
            temperature=0.5,
            max_tokens=8000,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        plan = json.loads(raw)
    except Exception as e:
        logger.error("Marketing plan generation failed: %s", e)
        return JSONResponse({"error": f"Génération échouée: {e}"}, status_code=500)

    # Persist plan to DB
    if session_id:
        from ...db.migrations import get_db as _gdb

        _db = _gdb()
        try:
            _db.execute(
                "UPDATE mkt_ideation_sessions SET marketing_plan=?, status='plan_ready', updated_at=NOW() WHERE id=?",
                (json.dumps(plan, ensure_ascii=False), session_id),
            )
            _db.commit()
        except Exception as e:
            logger.warning("mkt plan persist: %s", e)
        finally:
            _db.close()

    return JSONResponse({"plan": plan, "session_id": session_id})


@router.post("/api/mkt-ideation/create-mission")
async def mkt_create_mission(request: Request):
    """Create a Go-to-Market mission from a completed marketing plan."""
    from ...missions.store import get_mission_store, MissionDef

    data = await request.json()
    plan = data.get("plan", {})
    project_id = data.get("project_id", "")
    session_id = data.get("session_id", "")

    gtm = plan.get("go_to_market", {})
    vision = plan.get("business_vision", {})
    brand = plan.get("brand_strategy", {})

    mission_store = get_mission_store()
    mission = MissionDef(
        name=f"Go-to-Market — {brand.get('headline', 'Lancement produit')}",
        description=(
            f"{plan.get('executive_summary', '')}\n\n"
            f"UVP: {vision.get('uvp', '')}\n"
            f"Stratégie GTM: {gtm.get('strategy', '')}\n"
            f"Beachhead market: {gtm.get('beachhead', '')}"
        ),
        goal=vision.get("uvp", plan.get("executive_summary", "")),
        status="planning",
        type="marketing",
        project_id=project_id,
        workflow_id="feature-request",
        created_by="mkt-cmo",
        config={
            "marketing_plan": plan,
            "session_id": session_id,
            "type": "go_to_market",
        },
    )
    mission = mission_store.create_mission(mission)

    if session_id:
        from ...db.migrations import get_db as _gdb

        _db = _gdb()
        try:
            _db.execute(
                "UPDATE mkt_ideation_sessions SET mission_id=?, project_id=?, status='mission_created' WHERE id=?",
                (mission.id, project_id, session_id),
            )
            _db.commit()
        except Exception:
            pass
        finally:
            _db.close()

    return JSONResponse(
        {
            "mission_id": mission.id,
            "mission_name": mission.name,
            "redirect": f"/missions/{mission.id}" if project_id else "/backlog",
        }
    )


# ── History API ──────────────────────────────────────────────────


@router.get("/api/mkt-ideation/sessions")
async def mkt_sessions_list():
    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, title, prompt, status, mission_id, project_id, created_at "
            "FROM mkt_ideation_sessions ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return JSONResponse([dict(r) for r in rows])
    finally:
        db.close()


@router.get("/api/mkt-ideation/sessions/{session_id}")
async def mkt_session_detail(session_id: str):
    from ...db.migrations import get_db

    db = get_db()
    try:
        sess = db.execute(
            "SELECT * FROM mkt_ideation_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not sess:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        messages = db.execute(
            "SELECT * FROM mkt_ideation_messages WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        findings = db.execute(
            "SELECT * FROM mkt_ideation_findings WHERE session_id=?",
            (session_id,),
        ).fetchall()
        plan = None
        if sess["marketing_plan"]:
            try:
                plan = json.loads(sess["marketing_plan"])
            except Exception:
                pass
        return JSONResponse(
            {
                "id": sess["id"],
                "title": sess["title"],
                "prompt": sess["prompt"],
                "status": sess["status"],
                "mission_id": sess["mission_id"] or "",
                "project_id": sess["project_id"] or "",
                "created_at": str(sess["created_at"] or ""),
                "marketing_plan": plan,
                "messages": [dict(m) for m in messages],
                "findings": [dict(f) for f in findings],
            }
        )
    finally:
        db.close()
