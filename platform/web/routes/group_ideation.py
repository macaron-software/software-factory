"""Web routes — Generic multi-agent group ideation workspace."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Group configurations ─────────────────────────────────────────

GROUP_CONFIGS: dict[str, dict] = {
    "knowledge": {
        "name": "Knowledge & Recherche",
        "description": "Enrichissez la base de connaissances, auditez les mémoires, synthétisez l'expertise.",
        "icon_path": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
        "color": "#34d399",
        "placeholder": "Ex: Audite les mémoires projet et identifie les patterns récurrents...",
        "examples": [
            "Audit des connaissances projet et recommandations",
            "Synthèse des décisions architecturales du trimestre",
            "Compacter et réorganiser la mémoire équipe",
            "Créer un onboarding guide depuis les mémoires",
        ],
        "agents": [
            {
                "id": "knowledge-manager",
                "name": "Sophia Renard",
                "short_role": "Knowledge Manager",
                "color": "#fbbf24",
                "is_lead": True,
            },
            {
                "id": "knowledge-curator",
                "name": "Marc Fontaine",
                "short_role": "Knowledge Curator",
                "color": "#34d399",
            },
            {
                "id": "knowledge-seeder",
                "name": "Léa Dupont",
                "short_role": "Knowledge Seeder",
                "color": "#60a5fa",
            },
            {
                "id": "wiki-maintainer",
                "name": "Hugo Perrin",
                "short_role": "Wiki Maintainer",
                "color": "#a78bfa",
            },
            {
                "id": "principal-engineer",
                "name": "Thomas Berger",
                "short_role": "Principal Engineer",
                "color": "#d97706",
            },
        ],
        "augment_prompt": (
            "Chaque expert contribue dans son domaine:\n"
            "- Sophia (Manager): orchestration et rapport final\n"
            "- Marc (Curator): qualité et déduplication\n"
            "- Léa (Seeder): collecte et enrichissement\n"
            "- Hugo (Wiki): documentation et mise à jour\n"
            "- Thomas (Principal): validation technique\n"
            "Soyez précis, factuels et actionnables."
        ),
    },
    "archi": {
        "name": "Comité Architecture",
        "description": "Revue des décisions architecturales, ADR, choix technologiques et dette technique.",
        "icon_path": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
        "color": "#3b82f6",
        "placeholder": "Ex: Faut-il migrer vers une architecture microservices ou rester monolithique ?",
        "examples": [
            "Migration vers microservices vs monolithe modulaire",
            "Choix base de données : PostgreSQL vs MongoDB",
            "Architecture event-driven pour les notifications",
            "Revue de l'ADR sur l'authentification JWT",
        ],
        "agents": [
            {
                "id": "principal-engineer",
                "name": "Thomas Berger",
                "short_role": "Principal Engineer",
                "color": "#d97706",
                "is_lead": True,
            },
            {
                "id": "architecte",
                "name": "Pierre Duval",
                "short_role": "Solution Architect",
                "color": "#0891b2",
            },
            {
                "id": "api-designer",
                "name": "Julien Carpentier",
                "short_role": "API Designer",
                "color": "#3b82f6",
            },
            {
                "id": "cloud_architect",
                "name": "Éric Fontaine",
                "short_role": "Cloud Architect",
                "color": "#6366f1",
            },
            {
                "id": "system_architect_art",
                "name": "Catherine Vidal",
                "short_role": "System Architect",
                "color": "#58a6ff",
            },
        ],
        "augment_prompt": (
            "Chaque architecte évalue sous son angle:\n"
            "- Thomas (Principal): gouvernance et standards\n"
            "- Pierre (Solution): architecture globale et patterns\n"
            "- Julien (API): contrats et interfaces\n"
            "- Éric (Cloud): infra et scalabilité\n"
            "- Catherine (System): intégrations et dépendances\n"
            "Fournir des recommandations concrètes avec trade-offs."
        ),
    },
    "security": {
        "name": "Conseil Sécurité",
        "description": "Threat modeling, revue de sécurité, analyse de risques et plans de remédiation.",
        "icon_path": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        "color": "#ef4444",
        "placeholder": "Ex: Analyse les risques sécurité de notre nouvelle API publique...",
        "examples": [
            "Threat modeling API REST publique",
            "Revue sécurité authentification OAuth2",
            "Plan de réponse incident ransomware",
            "Audit RGPD traitement données utilisateurs",
        ],
        "agents": [
            {
                "id": "ciso",
                "name": "Isabelle Renaud",
                "short_role": "CISO",
                "color": "#ef4444",
                "is_lead": True,
            },
            {
                "id": "security-architect",
                "name": "Nicolas Moreau",
                "short_role": "Security Architect",
                "color": "#f97316",
            },
            {
                "id": "threat-analyst",
                "name": "Ahmed Benali",
                "short_role": "Threat Analyst",
                "color": "#eab308",
            },
            {
                "id": "devsecops",
                "name": "Romain Leclerc",
                "short_role": "DevSecOps",
                "color": "#22c55e",
            },
            {
                "id": "incident-commander",
                "name": "Victor Lebrun",
                "short_role": "Incident Commander",
                "color": "#a78bfa",
            },
        ],
        "augment_prompt": (
            "Chaque expert sécurité analyse sous son angle:\n"
            "- Isabelle (CISO): gouvernance et conformité\n"
            "- Nicolas (Architect): architecture défense\n"
            "- Ahmed (Threat): threat modeling et MITRE ATT&CK\n"
            "- Romain (DevSecOps): implémentation et pipelines\n"
            "- Victor (Incident): préparation et réponse\n"
            "Donner des recommandations priorisées par risque (CVSS)."
        ),
    },
    "data-ai": {
        "name": "Data & IA",
        "description": "Stratégie IA, architecture data, optimisation LLM, feature engineering et éthique.",
        "icon_path": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>',
        "color": "#8b5cf6",
        "placeholder": "Ex: Comment réduire nos coûts LLM de 40% sans dégrader la qualité ?",
        "examples": [
            "Optimisation coûts LLM : modèles et prompts",
            "Architecture data pipeline temps réel",
            "Évaluation qualité des outputs agents",
            "Stratégie RAG vs fine-tuning pour notre domaine",
        ],
        "agents": [
            {
                "id": "ai-product-manager",
                "name": "Chloé Marchand",
                "short_role": "AI Product Manager",
                "color": "#06b6d4",
                "is_lead": True,
            },
            {
                "id": "llm-ops-engineer",
                "name": "Karim Benchekroun",
                "short_role": "LLM Ops Engineer",
                "color": "#f59e0b",
            },
            {
                "id": "prompt-engineer",
                "name": "Léa Fontaine",
                "short_role": "Prompt Engineer",
                "color": "#8b5cf6",
            },
            {
                "id": "ml_engineer",
                "name": "Ariane Moreau",
                "short_role": "ML Engineer",
                "color": "#3b82f6",
            },
            {
                "id": "data_analyst",
                "name": "Pierre Lambert",
                "short_role": "Data Analyst",
                "color": "#10b981",
            },
        ],
        "augment_prompt": (
            "Chaque expert IA/Data contribue:\n"
            "- Chloé (AI PM): roadmap et valeur business\n"
            "- Karim (LLM Ops): coûts, latence et fiabilité\n"
            "- Léa (Prompt): qualité prompts et évals\n"
            "- Ariane (ML): modèles et algorithmes\n"
            "- Pierre (Data): métriques et insights\n"
            "Soyez quantitatifs, incluez des estimations chiffrées."
        ),
    },
    "pi-planning": {
        "name": "PI Planning",
        "description": "Planification incréments programme SAFe, synchronisation équipes, capacity planning.",
        "icon_path": '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
        "color": "#f59e0b",
        "placeholder": "Ex: Planifie le PI Q2 2026 pour les 4 ARTs avec 5 sprints de 2 semaines...",
        "examples": [
            "Planification PI Q2 2026 — objectifs et dependencies",
            "Retrospective PI précédent et actions correctives",
            "Identification des risques programme et mitigation",
            "Capacity planning équipes pour prochain incrément",
        ],
        "agents": [
            {
                "id": "release_train_engineer",
                "name": "Maxime Lefebvre",
                "short_role": "Release Train Engineer",
                "color": "#f59e0b",
                "is_lead": True,
            },
            {
                "id": "scrum_master",
                "name": "Isabelle Garnier",
                "short_role": "Scrum Master",
                "color": "#3b82f6",
            },
            {
                "id": "agile_coach",
                "name": "Dominique Faure",
                "short_role": "Agile Coach",
                "color": "#10b981",
            },
            {
                "id": "product_manager",
                "name": "Alexandre Faure",
                "short_role": "Product Manager",
                "color": "#8b5cf6",
            },
            {
                "id": "lean_portfolio_manager",
                "name": "Christine Bellamy",
                "short_role": "Lean Portfolio Manager",
                "color": "#ef4444",
            },
        ],
        "augment_prompt": (
            "Chaque expert SAFe contribue:\n"
            "- Maxime (RTE): coordination cross-équipes et risques\n"
            "- Isabelle (SM): capacités équipes et vélocité\n"
            "- Dominique (Coach): amélioration continue et blocages\n"
            "- Alexandre (PM): priorités features et backlog\n"
            "- Christine (LPM): alignement portfolio et budget\n"
            "Produit: objectives PI, ROAM risks, dépendances inter-équipes."
        ),
    },
}


def _get_group(group_id: str) -> dict | None:
    return GROUP_CONFIGS.get(group_id)


# ── Pages ─────────────────────────────────────────────────────────


@router.get("/group/{group_id}", response_class=HTMLResponse)
async def group_ideation_page(request: Request, group_id: str):
    """Generic group ideation workspace."""
    group = _get_group(group_id)
    if not group:
        return HTMLResponse(
            "<div style='padding:2rem;color:red'>Groupe introuvable</div>",
            status_code=404,
        )

    from ...agents.store import get_agent_store
    from ...projects.manager import get_project_store

    agent_store = get_agent_store()
    all_agents = agent_store.list_all()
    db_map = {a.id: a for a in all_agents}
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    enriched_agents = []
    for ag in group["agents"]:
        a = db_map.get(ag["id"])
        jpg = avatar_dir / f"{ag['id']}.jpg"
        svg_f = avatar_dir / f"{ag['id']}.svg"
        avatar_url = (
            f"/static/avatars/{ag['id']}.jpg"
            if jpg.exists()
            else f"/static/avatars/{ag['id']}.svg"
            if svg_f.exists()
            else ""
        )
        enriched_agents.append(
            {
                **ag,
                "avatar_url": avatar_url,
                "description": (a.description or "") if a else "",
                "tagline": (a.tagline or "") if a else "",
            }
        )

    from ...db.migrations import get_db as _gdb

    _db = _gdb()
    try:
        _rows = _db.execute(
            "SELECT id, title, status, created_at FROM group_ideation_sessions "
            "WHERE group_id=? ORDER BY created_at DESC LIMIT 20",
            (group_id,),
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

    enriched_group = {
        **group,
        "id": group_id,
        "agents": enriched_agents,
    }

    return _templates(request).TemplateResponse(
        "group_ideation.html",
        {
            "request": request,
            "page_title": group["name"],
            "group": enriched_group,
            "projects": [
                {"id": p.id, "name": p.name} for p in get_project_store().list_all()
            ],
            "past_sessions": past_sessions,
        },
    )


# ── Launch multi-agent analysis ───────────────────────────────────


@router.post("/api/group/{group_id}")
async def group_ideation_submit(request: Request, group_id: str):
    """Launch group ideation via multi-agent network pattern."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef
    from ...patterns.engine import run_pattern
    from ...patterns.store import PatternDef
    import uuid

    group = _get_group(group_id)
    if not group:
        return JSONResponse({"error": "Groupe introuvable"}, status_code=404)

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return JSONResponse({"error": "Prompt requis"}, status_code=400)

    from ...security.prompt_guard import get_prompt_guard

    prompt, score = get_prompt_guard().check_and_sanitize(
        prompt, source=f"group-{group_id}"
    )
    if score.blocked:
        return JSONResponse({"error": prompt}, status_code=400)

    session_id = data.get("session_id", "") or str(uuid.uuid4())[:8]

    session_store = get_session_store()
    existing = session_store.get(session_id)
    if not existing:
        session = SessionDef(
            id=session_id,
            name=f"{group['name']}: {prompt[:60]}",
            goal=prompt,
            status="active",
            config={"type": f"group_{group_id}", "pattern": "network"},
        )
        session = session_store.create(session)

    session_store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            message_type="delegate",
            content=prompt,
        )
    )

    # Save to group_ideation_sessions
    from ...db.migrations import get_db as _gdb

    _db = _gdb()
    try:
        title = prompt[:80] if len(prompt) > 80 else prompt
        _db.execute(
            "INSERT INTO group_ideation_sessions (id, group_id, title, prompt, status) "
            "VALUES (?, ?, ?, ?, 'active') ON CONFLICT (id) DO NOTHING",
            (session_id, group_id, title, prompt),
        )
        _db.commit()
    except Exception as e:
        logger.warning("group_ideation_sessions insert: %s", e)
    finally:
        _db.close()

    agents = group["agents"]
    lead = next((a for a in agents if a.get("is_lead")), agents[0])
    experts = [a for a in agents if a["id"] != lead["id"]]

    agent_nodes = [{"id": a["id"], "agent_id": a["id"]} for a in agents]
    edges = []
    for i, a in enumerate(experts):
        for b in experts[i + 1 :]:
            edges.append({"from": a["id"], "to": b["id"], "type": "bidirectional"})
    for a in experts:
        edges.append({"from": a["id"], "to": lead["id"], "type": "report"})

    augmented_prompt = f"Analyse pour : {prompt}\n\n{group['augment_prompt']}"

    pattern = PatternDef(
        id=f"group-{group_id}-{session_id}",
        name=f"{group['name']} multi-expert",
        type="network",
        agents=agent_nodes,
        edges=edges,
        config={"max_rounds": 2},
    )

    session_store_ref = session_store

    async def _run():
        try:
            await asyncio.sleep(0.5)
            await run_pattern(pattern, session_id, augmented_prompt)
        except Exception as e:
            logger.error("Group %s pattern failed: %s", group_id, e)
            session_store_ref.add_message(
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


# ── History API ──────────────────────────────────────────────────


@router.get("/api/group/{group_id}/sessions")
async def group_sessions_list(group_id: str):
    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, title, prompt, status, created_at "
            "FROM group_ideation_sessions WHERE group_id=? ORDER BY created_at DESC LIMIT 50",
            (group_id,),
        ).fetchall()
        return JSONResponse([dict(r) for r in rows])
    finally:
        db.close()


@router.get("/api/group/{group_id}/sessions/{session_id}")
async def group_session_detail(group_id: str, session_id: str):
    from ...db.migrations import get_db

    db = get_db()
    try:
        sess = db.execute(
            "SELECT * FROM group_ideation_sessions WHERE id=? AND group_id=?",
            (session_id, group_id),
        ).fetchone()
        if not sess:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        return JSONResponse(
            {
                "id": sess["id"],
                "group_id": sess["group_id"],
                "title": sess["title"],
                "prompt": sess["prompt"],
                "status": sess["status"],
                "created_at": str(sess["created_at"] or ""),
            }
        )
    finally:
        db.close()
