"""Web routes — Page renders (portfolio, backlog, workflows, etc.)."""
# Ref: feat-cockpit, feat-portfolio, feat-design-system

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from fastapi import Depends,  APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)

from .helpers import (
    _active_mission_tasks,
    _templates,
)
from ...auth.middleware import require_auth

# Prevent asyncio task GC — store references until tasks complete
_bg_tasks: set[asyncio.Task] = set()


def _keep_task(t: asyncio.Task) -> asyncio.Task:
    """Store task reference to prevent GC, auto-discard on completion."""
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)
    return t


log = logging.getLogger(__name__)

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Auth pages ───────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    from ...demo import is_demo_mode

    templates = _templates(request)
    return templates.TemplateResponse(
        "login.html", {"request": request, "demo_mode": is_demo_mode()}
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy policy — GDPR Art. 12-14."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "privacy.html", {"request": request, "page_title": "Privacy Policy"}
    )


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    """SAFe onboarding wizard — choose perspective + project."""
    from ...projects.manager import get_project_store

    projects = get_project_store().list_all()
    templates = _templates(request)
    return templates.TemplateResponse(
        "onboarding.html",
        {"request": request, "projects": projects, "page_title": "Onboarding"},
    )


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """First-time setup wizard."""
    from ...auth.middleware import is_setup_needed

    if not is_setup_needed():
        from starlette.responses import RedirectResponse

        return RedirectResponse(url="/login", status_code=302)
    templates = _templates(request)
    return templates.TemplateResponse("setup.html", {"request": request})


# ── Pages ────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Home — CTO Jarvis, Idéation Business, Idéation Projet."""
    tab = request.query_params.get("tab", "cto")
    return _templates(request).TemplateResponse(
        "home.html",
        {"request": request, "page_title": "Home", "active_tab": tab},
    )


@router.get("/cockpit", response_class=HTMLResponse)
async def cockpit_page(request: Request):
    """Cockpit — vue synthétique de toute la Software Factory."""
    return _templates(request).TemplateResponse(
        "cockpit.html",
        {"request": request, "page_title": "Cockpit"},
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Dashboard redirect to portfolio (backward compat)."""
    from starlette.responses import RedirectResponse

    tab = request.query_params.get("tab", "overview")
    return RedirectResponse(url=f"/portfolio?tab={tab}", status_code=302)


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio dashboard — tour de contrôle DSI (legacy view)."""
    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_run_store, get_epic_store
    from ...projects.manager import get_project_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    epic_store = get_epic_store()
    run_store = get_epic_run_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = epic_store.list_missions(limit=500)
    all_runs = run_store.list_runs(limit=500)
    # Index runs by parent_epic_id for quick lookup
    runs_by_mission: dict = {}
    for r in all_runs:
        if r.parent_epic_id:
            runs_by_mission[r.parent_epic_id] = r
        runs_by_mission[r.id] = r  # Also index by run id (same as mission id)

    strategic_raw = [
        a for a in all_agents if any(t == "strategy" for t in (a.tags or []))
    ]
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
    strategic = []
    for a in strategic_raw:
        jpg = avatar_dir / f"{a.id}.jpg"
        svg = avatar_dir / f"{a.id}.svg"
        avatar_url = (
            f"/static/avatars/{a.id}.jpg"
            if jpg.exists()
            else (
                f"/static/avatars/{a.id}.svg"
                if svg.exists()
                else f"https://i.pravatar.cc/150?u={a.id}"
            )
        )
        strategic.append(
            {
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "avatar": a.avatar or a.icon or "bot",
                "color": a.color or "#7c3aed",
                "avatar_url": avatar_url,
                "tagline": a.tagline or "",
                "persona": a.persona or "",
                "description": a.description or "",
                "motivation": a.motivation or "",
                "skills": a.skills or [],
                "tools": a.tools or [],
                "mcps": a.mcps or [],
                "model": getattr(a, "model", "") or "",
                "provider": getattr(a, "provider", "") or "",
            }
        )

    # Build project cards with missions
    projects_data = []
    total_tasks = 0
    total_done = 0
    active_count = 0
    for p in all_projects:
        p_missions = [m for m in all_missions if m.project_id == p.id]
        p_agents = [
            a
            for a in all_agents
            if a.id.startswith(p.id[:4] + "-") or a.id.startswith(p.id + "-")
        ]
        team_avatars = [
            {"name": a.name, "icon": a.avatar or a.icon or "bot"} for a in p_agents[:8]
        ]

        p_total = 0
        p_done = 0
        p_active = 0
        mission_cards = []
        for m in p_missions:
            # Compute progress from epic_run phases (live data)
            run = runs_by_mission.get(m.id)
            if run and run.phases:
                t_total = len(run.phases)
                t_done = sum(
                    1
                    for ph in run.phases
                    if ph.status.value in ("done", "done_with_issues")
                )
                current = run.current_phase or ""
                current_name = next(
                    (ph.phase_name for ph in run.phases if ph.phase_id == current),
                    current,
                )
            else:
                # Fallback to task-based stats
                stats = epic_store.mission_stats(m.id)
                t_total = stats.get("total", 0)
                t_done = stats.get("done", 0)
                current_name = ""
            p_total += t_total
            p_done += t_done
            if m.status == "active":
                p_active += 1
            progress = f"{t_done}/{t_total}" if t_total > 0 else ""
            run_status = run.status.value if run else m.status
            mission_cards.append(
                {
                    "name": m.name,
                    "status": m.status,
                    "task_progress": progress,
                    "current_phase": current_name,
                    "run_status": run_status,
                }
            )
        total_tasks += p_total
        total_done += p_done
        active_count += p_active

        # Compute badges from mission names/types
        def _is_tma(m):
            return "[TMA" in m.name or m.name.startswith("TMA —") or m.type == "program"

        tma_count = sum(
            1 for m in p_missions if _is_tma(m) and m.status in ("active", "running")
        )
        tma_resolved = sum(
            1 for m in p_missions if _is_tma(m) and m.status == "resolved"
        )
        has_secu = (
            any(
                m.type == "security"
                or m.name.startswith("Sécurité")
                or ("secur" in (m.name + (m.description or "")).lower())
                for m in p_missions
            )
            or p.factory_type == "security"
        )
        has_cicd = p_total > 0 and any(
            run
            and any(ph.phase_id in ("cicd", "deploy-prod") for ph in (run.phases or []))
            for m in p_missions
            for run in [runs_by_mission.get(m.id)]
        )
        running_phases = sum(
            1
            for m in p_missions
            for run in [runs_by_mission.get(m.id)]
            if run and any(ph.status.value == "running" for ph in (run.phases or []))
        )

        projects_data.append(
            {
                "id": p.id,
                "name": p.name,
                "factory_type": p.factory_type,
                "description": p.description or (p.vision or "")[:100],
                "epics": mission_cards,
                "mission_count": len(p_missions),
                "active_mission_count": p_active,
                "team_avatars": team_avatars,
                "total_tasks": p_total,
                "done_tasks": p_done,
                "tma_active": tma_count,
                "tma_resolved": tma_resolved,
                "has_tma": any(_is_tma(m) for m in p_missions),
                "has_secu": has_secu,
                "has_cicd": has_cicd,
                "running_phases": running_phases,
            }
        )

    # Build epics progression table (from live phase data)
    # Filter out spam/invalid missions (xxxx, empty names, duplicates)
    epics_data = []
    seen_names: set = set()
    for m in all_missions:
        # Skip spam/invalid
        if not m.name or len(set(m.name[:20])) <= 2:
            continue
        # Skip duplicates by name
        if m.name in seen_names:
            continue
        seen_names.add(m.name)
        run = runs_by_mission.get(m.id)
        if run and run.phases:
            t_total = len(run.phases)
            t_done = sum(
                1
                for ph in run.phases
                if ph.status.value in ("done", "done_with_issues")
            )
            current = run.current_phase or ""
            current_name = next(
                (ph.phase_name for ph in run.phases if ph.phase_id == current), current
            )
            run_status = run.status.value
        else:
            stats = epic_store.mission_stats(m.id)
            t_total = stats.get("total", 0)
            t_done = stats.get("done", 0)
            current_name = ""
            run_status = m.status
        pct = int(t_done / t_total * 100) if t_total > 0 else 0
        p = next((p for p in all_projects if p.id == m.project_id), None)
        epics_data.append(
            {
                "id": m.id,
                "name": m.name,
                "status": m.status,
                "project_name": p.name if p else m.project_id or "—",
                "done": t_done,
                "total": t_total,
                "pct": pct,
                "wsjf": getattr(m, "wsjf", 0) or 0,
                "current_phase": current_name,
                "run_status": run_status,
            }
        )
    epics_data.sort(
        key=lambda e: (
            0 if e["run_status"] in ("running", "in_progress") else 1,
            -e["pct"],
            e["name"],
        )
    )
    epics_data = epics_data[:100]  # Show up to 100 epics

    # Load strategic committee graph from workflow
    strat_graph = {"nodes": [], "edges": []}
    try:
        from ...workflows.store import get_workflow_store

        wf_store = get_workflow_store()
        strat_wf = wf_store.get("strategic-committee")
        if strat_wf and strat_wf.config:
            sg = strat_wf.config.get("graph", {})
            if sg.get("nodes"):
                agent_map = {a.id: a for a in all_agents}
                for n in sg["nodes"]:
                    aid = n.get("agent_id", "")
                    a = agent_map.get(aid)
                    jpg = avatar_dir / f"{aid}.jpg"
                    svg_f = avatar_dir / f"{aid}.svg"
                    av_url = (
                        f"/static/avatars/{aid}.jpg"
                        if jpg.exists()
                        else (
                            f"/static/avatars/{aid}.svg"
                            if svg_f.exists()
                            else f"https://i.pravatar.cc/150?u={aid}"
                        )
                    )
                    strat_graph["nodes"].append(
                        {
                            "id": n["id"],
                            "agent_id": aid,
                            "label": n.get("label", a.name if a else aid),
                            "x": n.get("x", 0),
                            "y": n.get("y", 0),
                            "color": a.color if a else "#7c3aed",
                            "avatar_url": av_url,
                        }
                    )
                strat_graph["edges"] = sg.get("edges", [])
    except Exception:
        pass

    return _templates(request).TemplateResponse(
        "portfolio.html",
        {
            "request": request,
            "page_title": "Portfolio",
            "active_tab": request.query_params.get("tab", "overview"),
            "projects": projects_data,
            "strategic_agents": strategic,
            "strat_graph": strat_graph,
            "epics": epics_data,
            "total_missions": len(all_missions),
            "active_missions": active_count,
            "total_tasks": total_tasks,
            "total_tasks_done": total_done,
            "total_agents": len(all_agents),
        },
    )


# ── SAFe consolidated pages (tabbed) ─────────────────────────────


@router.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request, tab: str = "backlog"):
    """Backlog — Product + Discovery (ideation) in tabs."""
    return _templates(request).TemplateResponse(
        "backlog.html",
        {
            "request": request,
            "page_title": "Backlog",
            "active_tab": tab,
            "tab_content": "",
        },
    )


@router.get("/pi", response_class=HTMLResponse)
async def pi_board_page(request: Request):
    """PI Board — epics + missions list with creation."""
    from ...db.migrations import get_db
    from ...epics.store import get_epic_run_store
    from ...projects.manager import get_project_store
    from ...workflows.store import get_workflow_store

    runs = get_epic_run_store().list_runs(limit=500)
    projects = get_project_store().list_all()
    workflows = get_workflow_store().list_all()
    active_ids = {mid for mid, t in _active_mission_tasks.items() if not t.done()}
    # Load epics from missions table with feature counts
    epics = []
    try:
        db = get_db()
        rows = db.execute("""
            SELECT m.id, m.project_id, m.name, m.description, m.goal, m.status, m.type, m.created_at,
                   p.name as project_name
            FROM epics m LEFT JOIN projects p ON m.project_id = p.id
            WHERE m.type = 'epic'
            ORDER BY m.created_at DESC
        """).fetchall()
        # Batch feature stats in a single query instead of N+1
        epic_ids = [r["id"] for r in rows]
        feat_stats = {}
        if epic_ids:
            placeholders = ",".join("?" * len(epic_ids))
            feat_rows = db.execute(
                f"""
                SELECT epic_id, status, COUNT(*) as cnt, COALESCE(SUM(story_points),0) as sp
                FROM features WHERE epic_id IN ({placeholders}) GROUP BY epic_id, status
            """,
                epic_ids,
            ).fetchall()
            for fr in feat_rows:
                feat_stats.setdefault(fr["epic_id"], {})[fr["status"]] = {
                    "count": fr["cnt"],
                    "sp": fr["sp"],
                }
        for r in rows:
            eid = r["id"]
            feat_map = feat_stats.get(eid, {})
            total_f = sum(v["count"] for v in feat_map.values())
            done_f = feat_map.get("done", {}).get("count", 0)
            total_sp = sum(v["sp"] for v in feat_map.values())
            done_sp = feat_map.get("done", {}).get("sp", 0)
            epics.append(
                {
                    "id": eid,
                    "project_id": r["project_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "goal": r["goal"],
                    "status": r["status"],
                    "type": r["type"],
                    "project_name": r["project_name"] or r["project_id"],
                    "created_at": r["created_at"],
                    "total_features": total_f,
                    "done_features": done_f,
                    "total_sp": total_sp,
                    "done_sp": done_sp,
                    "features_by_status": feat_map,
                }
            )
    except Exception:
        pass
    # Load TMA tickets (bugs, debt, security)
    tma_tickets = []
    try:
        db = get_db()
        tma_rows = db.execute("""
            SELECT m.id, m.project_id, m.name, m.description, m.goal, m.status, m.type, m.created_at,
                   p.name as project_name
            FROM epics m LEFT JOIN projects p ON m.project_id = p.id
            WHERE m.type IN ('bug', 'debt', 'security')
            ORDER BY
                CASE m.type WHEN 'security' THEN 0 WHEN 'bug' THEN 1 WHEN 'debt' THEN 2 ELSE 3 END,
                m.created_at DESC
        """).fetchall()
        for r in tma_rows:
            tma_tickets.append(
                {
                    "id": r["id"],
                    "project_id": r["project_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "goal": r["goal"],
                    "status": r["status"],
                    "type": r["type"],
                    "project_name": r["project_name"] or r["project_id"],
                    "created_at": r["created_at"],
                }
            )
    except Exception:
        pass
    return _templates(request).TemplateResponse(
        "pi_board.html",
        {
            "request": request,
            "page_title": "PI Board",
            "runs": runs,
            "projects": projects,
            "workflows": workflows,
            "active_ids": active_ids,
            "epics": epics,
            "tma_tickets": tma_tickets,
        },
    )


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request, tab: str = "templates"):
    """Workflows — Mission templates + Orchestration patterns."""
    return _templates(request).TemplateResponse(
        "workflows.html",
        {
            "request": request,
            "page_title": "Workflows",
            "active_tab": tab,
            "tab_content": "",
        },
    )


@router.get("/workflows/list", response_class=HTMLResponse)
async def workflows_list(request: Request):
    """Partial: workflow templates list (no tabs wrapper)."""
    from ...workflows.store import get_workflow_store

    workflows = get_workflow_store().list_all()
    return _templates(request).TemplateResponse(
        "partials/workflows_list.html",
        {"request": request, "workflows": workflows},
    )


@router.get("/workflows/evolution", response_class=HTMLResponse)
async def workflows_evolution(request: Request):
    """Partial: GA evolution proposals + run history."""
    from ...db.migrations import get_db
    from ...workflows.store import get_workflow_store
    import json as _json

    db = get_db()
    proposals = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM evolution_proposals ORDER BY fitness DESC, created_at DESC LIMIT 50"
        ).fetchall()
    ]
    runs = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM evolution_runs ORDER BY completed_at DESC LIMIT 20"
        ).fetchall()
    ]
    db.close()
    from datetime import datetime as _datetime_type

    for p in proposals:
        try:
            p["genome"] = _json.loads(p.pop("genome_json", "{}"))
        except Exception:
            p["genome"] = {}
        for k, v in p.items():
            if isinstance(v, _datetime_type):
                p[k] = v.isoformat()
    for r in runs:
        try:
            r["fitness_history"] = _json.loads(r.pop("fitness_history_json", "[]"))
        except Exception:
            r["fitness_history"] = []
        for k, v in r.items():
            if isinstance(v, _datetime_type):
                r[k] = v.isoformat()
    # RL stats
    rl_stats = {}
    try:
        from ...agents.rl_policy import get_rl_policy

        rl_stats = get_rl_policy().stats()
    except Exception:
        pass
    workflows = get_workflow_store().list_all()
    return _templates(request).TemplateResponse(
        "partials/workflows_evolution.html",
        {
            "request": request,
            "proposals": proposals,
            "runs": runs,
            "rl_stats": rl_stats,
            "workflows": workflows,
        },
    )


# ── AC_PHASES matching dashboard definition ──────────────────────────────────
_AC_PHASES = ["inception", "tdd-sprint", "adversarial", "qa-sprint", "cicd", "deploy"]

_AC_PROJECTS = [
    {
        "id": "ac-hello-html",
        "name": "Hello HTML",
        "tier": "simple",
        "tier_label": "Simple",
        "tech": ["html", "css", "nginx"],
        "max_cycles": 20,
        "description": "Page HTML statique servie par nginx. Affiche un message de bienvenue avec design soigné.",
        "user_stories": [
            "US-01: En tant qu'utilisateur, je vois un titre principal (h1) avec le message de bienvenue",
            "US-02: En tant qu'utilisateur, la page se charge en < 1s et est accessible sans JS",
            "US-03: En tant qu'utilisateur daltonien, je peux lire le contenu (contraste >= 4.5:1)",
            "US-04: En tant qu'utilisateur au clavier, je peux naviguer sans souris (focus-visible)",
            "US-05: En tant qu'utilisateur de lecteur d'écran, tous les éléments ont des labels ARIA",
        ],
        "a11y_requirements": [
            "WCAG AA: contraste ratio >= 4.5:1 pour le texte normal, 3:1 pour le grand texte",
            "focus-visible: outline visible sur tous les éléments interactifs",
            "aria-label sur tous les éléments interactifs sans texte visible",
            "lang='fr' sur la balise html",
            "alt text sur toutes les images",
            "Semantic HTML: h1>h2>h3, nav, main, footer",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-primary-hover": "#1e429f",
            "--color-text": "#111928",
            "--color-text-secondary": "#6b7280",
            "--color-bg": "#ffffff",
            "--color-bg-secondary": "#f9fafb",
            "--color-border": "#e5e7eb",
            "--color-focus-ring": "#3f83f8",
            "--color-success": "#0e9f6e",
            "--color-error": "#f05252",
            "--spacing-xs": "0.25rem",
            "--spacing-sm": "0.5rem",
            "--spacing-md": "1rem",
            "--spacing-lg": "1.5rem",
            "--spacing-xl": "2rem",
            "--font-size-sm": "0.875rem",
            "--font-size-base": "1rem",
            "--font-size-lg": "1.125rem",
            "--font-size-xl": "1.25rem",
            "--font-size-2xl": "1.5rem",
            "--font-weight-normal": "400",
            "--font-weight-medium": "500",
            "--font-weight-bold": "700",
            "--radius-sm": "0.25rem",
            "--radius-md": "0.375rem",
            "--radius-lg": "0.5rem",
        },
    },
    {
        "id": "ac-hello-vue",
        "name": "Hello Vue.js",
        "tier": "simple-compile",
        "tier_label": "Simple + Compile",
        "tech": ["vue", "vite", "node"],
        "max_cycles": 20,
        "description": "Application Vue.js simple avec composant compteur interactif et routing basique.",
        "user_stories": [
            "US-01: En tant qu'utilisateur, je vois un compteur avec boutons +/- et valeur actuelle",
            "US-02: En tant qu'utilisateur, le compteur se remet à zéro via un bouton Reset",
            "US-03: En tant qu'utilisateur au clavier, tous les boutons sont accessibles (Tab, Enter, Space)",
            "US-04: En tant qu'utilisateur de lecteur d'écran, le compteur annonce sa valeur (aria-live)",
        ],
        "a11y_requirements": [
            "WCAG AA compliance",
            "aria-live='polite' sur la valeur du compteur",
            "Boutons avec aria-label explicite",
            "focus-visible sur tous les éléments interactifs",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-bg": "#ffffff",
            "--color-text": "#111928",
            "--spacing-md": "1rem",
            "--radius-md": "0.375rem",
        },
    },
    {
        "id": "ac-fullstack-rs",
        "name": "Fullstack Rust+Svelte",
        "tier": "medium",
        "tier_label": "Medium Fullstack",
        "tech": ["rust", "sveltekit", "postgres"],
        "max_cycles": 20,
        "description": "API REST Rust (Axum) + frontend SvelteKit + PostgreSQL. CRUD complet, auth JWT.",
        "user_stories": [
            "US-01: En tant qu'utilisateur, je peux créer un compte et me connecter (JWT)",
            "US-02: En tant qu'utilisateur authentifié, je peux créer/lire/modifier/supprimer des items",
            "US-03: En tant qu'admin, je vois tous les items via une API paginée",
            "US-04: En tant que développeur, l'API retourne des erreurs structurées (RFC 7807)",
        ],
        "a11y_requirements": [
            "WCAG AA sur le frontend SvelteKit",
            "Formulaires avec labels associés (htmlFor)",
            "Messages d'erreur accessibles (role=alert)",
            "Focus management après soumission de formulaire",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-bg": "#ffffff",
            "--color-text": "#111928",
            "--spacing-md": "1rem",
        },
    },
    {
        "id": "ac-docsign-clone",
        "name": "DocuSign Clone",
        "tier": "complex",
        "tier_label": "Complex",
        "tech": ["react", "fastapi", "postgres"],
        "max_cycles": 20,
        "description": "Clone simplifié DocuSign: upload PDF, signature électronique, workflow multi-signataires.",
        "user_stories": [
            "US-01: En tant qu'expéditeur, je peux uploader un PDF et désigner des signataires",
            "US-02: En tant que signataire, je reçois un lien et peux signer le document",
            "US-03: En tant qu'expéditeur, je vois l'état de signature en temps réel",
            "US-04: En tant qu'auditeur, je peux télécharger le PDF signé avec piste d'audit",
        ],
        "a11y_requirements": [
            "WCAG AA sur toute l'interface React",
            "Drag-and-drop avec alternative clavier pour placement des champs de signature",
            "Annonces ARIA pour les changements d'état de workflow",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-bg": "#ffffff",
            "--color-text": "#111928",
            "--spacing-md": "1rem",
        },
    },
    {
        "id": "ac-ecommerce-solaris",
        "name": "E-commerce + Solaris DS",
        "tier": "enterprise",
        "tier_label": "Enterprise",
        "tech": ["nextjs", "solaris", "stripe", "pg"],
        "max_cycles": 20,
        "description": "E-commerce Next.js avec design system Solaris, Stripe, PostgreSQL. Catalogue, panier, checkout.",
        "user_stories": [
            "US-01: En tant que client, je peux parcourir le catalogue et filtrer par catégorie",
            "US-02: En tant que client, je peux ajouter au panier et procéder au paiement (Stripe)",
            "US-03: En tant que client, je reçois une confirmation email après achat",
            "US-04: En tant qu'admin, je peux gérer le catalogue et voir les commandes",
        ],
        "a11y_requirements": [
            "WCAG AA avec design system Solaris",
            "Composants Solaris utilisés exclusivement (pas de CSS custom hors tokens)",
            "Skip links pour navigation rapide",
            "Panier accessible (live region pour le compteur)",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-bg": "#ffffff",
            "--color-text": "#111928",
            "--spacing-md": "1rem",
        },
    },
    {
        "id": "ac-game-threejs",
        "name": "Jeu Three.js",
        "tier": "game-browser",
        "tier_label": "Jeu Simple",
        "tech": ["threejs", "js", "webgl"],
        "max_cycles": 20,
        "description": "Jeu browser 3D simple avec Three.js: contrôles clavier/souris, score, game over.",
        "user_stories": [
            "US-01: En tant que joueur, je peux déplacer mon personnage avec les flèches/WASD",
            "US-02: En tant que joueur, je vois mon score en temps réel",
            "US-03: En tant que joueur, je reçois un écran game over avec option restart",
            "US-04: En tant que joueur mobile, les contrôles touch fonctionnent",
        ],
        "a11y_requirements": [
            "Écran de titre accessible avec instructions clavier",
            "Bouton Pause accessible (Escape ou bouton visible)",
            "Score annoncé par aria-live au changement",
        ],
        "design_tokens": {
            "--color-primary": "#1a56db",
            "--color-bg": "#0f172a",
            "--color-text": "#f8fafc",
            "--spacing-md": "1rem",
        },
    },
    {
        "id": "ac-game-native",
        "name": "Jeu Natif Compilé",
        "tier": "game-compiled",
        "tier_label": "Jeu Compilé",
        "tech": ["rust", "sdl2", "opengl"],
        "max_cycles": 20,
        "description": "Jeu natif compilé en Rust avec SDL2/OpenGL: rendu 60fps, gestion collisions, score.",
        "user_stories": [
            "US-01: En tant que joueur, le jeu tourne à 60fps stables",
            "US-02: En tant que joueur, les collisions sont détectées précisément",
            "US-03: En tant que joueur, je peux quitter proprement (Escape ou fenêtre)",
            "US-04: En tant que développeur, le binaire se compile sans warnings",
        ],
        "a11y_requirements": [
            "Fenêtre avec titre descriptif",
            "Gestion propre de la fermeture de fenêtre (signal SIGTERM)",
        ],
        "design_tokens": {},
    },
    {
        "id": "ac-migration-php",
        "name": "Migration PHP → FastAPI",
        "tier": "migration",
        "tier_label": "Migration",
        "tech": ["php", "fastapi", "postgres"],
        "max_cycles": 20,
        "description": "Migration d'une API PHP legacy vers FastAPI Python. Parité fonctionnelle + tests de non-régression.",
        "user_stories": [
            "US-01: En tant que client API, tous les endpoints PHP sont disponibles en FastAPI avec la même interface",
            "US-02: En tant que QA, les tests de non-régression couvrent 100% des endpoints",
            "US-03: En tant qu'ops, la migration est documentée avec guide de rollback",
            "US-04: En tant que développeur, le code FastAPI est < 500 LOC/fichier et typé",
        ],
        "a11y_requirements": [
            "API: réponses d'erreur structurées RFC 7807",
            "Documentation OpenAPI complète",
        ],
        "design_tokens": {},
    },
]


def _ac_get_db():
    """Get DB connection — uses platform DB adapter (SQLite or PG via DATABASE_URL)."""
    from ...db.migrations import get_db

    return get_db()


def _ac_ensure_tables(conn) -> None:
    """Create AC tables if they don't exist (idempotent)."""
    is_pg = False
    try:
        from ...db.adapter import is_postgresql

        is_pg = is_postgresql()
    except Exception:
        pass

    if is_pg:
        stmts = [
            """CREATE TABLE IF NOT EXISTS ac_cycles (
                id SERIAL PRIMARY KEY, project_id TEXT NOT NULL, cycle_num INTEGER NOT NULL,
                git_sha TEXT, platform_run_id TEXT, status TEXT DEFAULT 'pending',
                phase_scores TEXT DEFAULT '{}', total_score INTEGER DEFAULT 0,
                defect_count INTEGER DEFAULT 0, fix_commit TEXT, fix_summary TEXT,
                adversarial_scores TEXT DEFAULT '{}', traceability_score INTEGER DEFAULT 0,
                ga_fitness REAL DEFAULT 0, rl_reward REAL DEFAULT 0,
                started_at TEXT, completed_at TEXT, UNIQUE(project_id, cycle_num))""",
            """CREATE TABLE IF NOT EXISTS ac_project_state (
                project_id TEXT PRIMARY KEY, current_cycle INTEGER DEFAULT 0,
                status TEXT DEFAULT 'idle', current_run_id TEXT,
                total_score_avg REAL DEFAULT 0, last_git_sha TEXT,
                ci_status TEXT DEFAULT 'unknown', started_at TEXT, updated_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS ac_adversarial (
                id SERIAL PRIMARY KEY, project_id TEXT NOT NULL, cycle_num INTEGER NOT NULL,
                dimension TEXT NOT NULL, score INTEGER DEFAULT 0, verdict TEXT DEFAULT 'pending',
                findings TEXT DEFAULT '[]', checked_at TEXT,
                UNIQUE(project_id, cycle_num, dimension))""",
        ]
    else:
        stmts = [
            """CREATE TABLE IF NOT EXISTS ac_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                cycle_num INTEGER NOT NULL, git_sha TEXT, platform_run_id TEXT,
                status TEXT DEFAULT 'pending', phase_scores TEXT DEFAULT '{}',
                total_score INTEGER DEFAULT 0, defect_count INTEGER DEFAULT 0,
                fix_commit TEXT, fix_summary TEXT,
                adversarial_scores TEXT DEFAULT '{}', traceability_score INTEGER DEFAULT 0,
                ga_fitness REAL DEFAULT 0, rl_reward REAL DEFAULT 0,
                started_at TEXT, completed_at TEXT, UNIQUE(project_id, cycle_num))""",
            """CREATE TABLE IF NOT EXISTS ac_project_state (
                project_id TEXT PRIMARY KEY, current_cycle INTEGER DEFAULT 0,
                status TEXT DEFAULT 'idle', current_run_id TEXT,
                total_score_avg REAL DEFAULT 0, last_git_sha TEXT,
                ci_status TEXT DEFAULT 'unknown', started_at TEXT, updated_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS ac_adversarial (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                cycle_num INTEGER NOT NULL, dimension TEXT NOT NULL,
                score INTEGER DEFAULT 0, verdict TEXT DEFAULT 'pending',
                findings TEXT DEFAULT '[]', checked_at TEXT,
                UNIQUE(project_id, cycle_num, dimension))""",
        ]
    try:
        for stmt in stmts:
            conn.execute(stmt)
        # Idempotent column additions (use IF NOT EXISTS for PostgreSQL)
        _col = "IF NOT EXISTS " if is_pg else ""
        for alter in [
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}adversarial_scores TEXT DEFAULT '{{}}'",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}traceability_score INTEGER DEFAULT 0",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}rl_reward REAL DEFAULT 0",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}veto_count INTEGER DEFAULT 0",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}next_cycle_hint TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}skill_eval_pending TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}convergence_status TEXT DEFAULT 'cold_start'",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}current_run_id TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}last_escalation_reason TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}last_escalation_at TEXT",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}rolled_back INTEGER DEFAULT 0",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}experiment_id TEXT",
            f"ALTER TABLE ac_cycles ADD COLUMN {_col}screenshot_path TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}builder_session_id TEXT",
            f"ALTER TABLE ac_project_state ADD COLUMN {_col}supervisor_session_id TEXT",
        ]:
            try:
                conn.execute(alter)
            except Exception:
                pass
        conn.commit()
    except Exception:
        pass


@router.get("/workflows/improvement", response_class=HTMLResponse)
async def workflows_improvement(request: Request):
    """Partial: Amélioration Continue — project cards + cycle history."""
    import json as _json

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            states = {
                r["project_id"]: dict(r)
                for r in conn.execute("SELECT * FROM ac_project_state").fetchall()
            }
        except Exception:
            states = {}
        try:
            adv = [
                dict(r)
                for r in conn.execute(
                    "SELECT dimension, score, verdict, findings FROM ac_adversarial "
                    "WHERE project_id = (SELECT project_id FROM ac_project_state ORDER BY updated_at DESC LIMIT 1) "
                    "ORDER BY score ASC LIMIT 24"
                ).fetchall()
            ]
        except Exception:
            adv = []
        try:
            first_id = _AC_PROJECTS[0]["id"] if _AC_PROJECTS else None
            cycles_raw = (
                conn.execute(
                    "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num",
                    (first_id,),
                ).fetchall()
                if first_id
                else []
            )
        except Exception:
            cycles_raw = []
        conn.close()
        return states, adv, cycles_raw

    states, adv, cycles_raw = await asyncio.to_thread(_load)

    projects = []
    for p in _AC_PROJECTS:
        s = states.get(p["id"], {})
        projects.append(
            {
                **p,
                "current_cycle": s.get("current_cycle", 0),
                "status": s.get("status", "idle"),
                "total_score_avg": s.get("total_score_avg", 0),
            }
        )

    cycles = []
    for c in cycles_raw:
        row = dict(c)
        try:
            row["phase_scores_dict"] = _json.loads(row.get("phase_scores") or "{}")
        except Exception:
            row["phase_scores_dict"] = {}
        cycles.append(row)

    avg_cycle = (
        sum(p["current_cycle"] for p in projects) / len(projects) if projects else 0
    )

    return _templates(request).TemplateResponse(
        "partials/workflows_improvement.html",
        {
            "request": request,
            "projects": projects,
            "cycles": cycles,
            "adversarial": adv,
            "phases": _AC_PHASES,
            "avg_cycle": avg_cycle,
        },
    )


@router.get("/workflows/improvement/cycles/{project_id}", response_class=HTMLResponse)
async def workflows_improvement_cycles(request: Request, project_id: str):
    """HTMX fragment: cycle table for a given project.

    Also auto-backfills cycle records for missions that completed but whose
    CI/CD agent never called inject-cycle (agent failure / timeout).
    """
    import json as _json

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        # ── Auto-backfill: record cycles from missions that were never injected ──
        try:
            from ...missions.store import get_mission_store

            store = get_mission_store()
            all_missions = store.list_missions(project_id=project_id, limit=200)
            # recorded = run_ids of cycles that already have real scores (skip them)
            recorded = {
                row[0]
                for row in conn.execute(
                    "SELECT platform_run_id FROM ac_cycles WHERE project_id=? AND total_score > 0",
                    (project_id,),
                ).fetchall()
                if row[0]
            }
            for m in all_missions:
                cfg = getattr(m, "config", {}) or {}
                if cfg.get("project_id") != project_id:
                    continue
                if not cfg.get("ac"):
                    continue
                run_id = str(m.id)
                if run_id in recorded:
                    continue
                cycle_num = cfg.get("cycle_num")
                if not cycle_num:
                    # parse from name "AC … — Cycle N"
                    import re

                    nm = getattr(m, "name", "") or ""
                    mo = re.search(r"Cycle\s+(\d+)", nm)
                    cycle_num = int(mo.group(1)) if mo else None
                if not cycle_num:
                    continue
                status = getattr(m, "status", "unknown") or "unknown"
                started = getattr(m, "created_at", None)
                completed = getattr(m, "completed_at", None)
                if hasattr(started, "isoformat"):
                    started = started.isoformat()
                if hasattr(completed, "isoformat"):
                    completed = completed.isoformat()
                # Try to extract phase scores + summary from sprints
                phase_scores_dict = {}
                fix_summary = f"Cycle {cycle_num} — {status}"
                total_score = 0
                defect_count = 0
                try:
                    sprints = store.list_sprints(run_id)
                    if sprints:
                        phase_scores_dict = {
                            s.type: s.quality_score for s in sprints if s.quality_score
                        }
                        scored = [v for v in phase_scores_dict.values() if v]
                        total_score = sum(scored) // len(scored) if scored else 0
                        # Build a readable fix_summary: prefer deploy/qa retro_notes
                        _SUMMARY_PRIORITY = [
                            "deploy",
                            "qa-sprint",
                            "adversarial",
                            "tdd-sprint",
                            "inception",
                        ]
                        sprint_by_type = {s.type: s for s in sprints}
                        summary_text = ""
                        for ptype in _SUMMARY_PRIORITY:
                            s = sprint_by_type.get(ptype)
                            if s and s.retro_notes and len(s.retro_notes) > 10:
                                summary_text = s.retro_notes[:300].strip()
                                break
                        if summary_text:
                            scores_compact = " ".join(
                                f"{t[:3]}:{v}"
                                for t, v in phase_scores_dict.items()
                                if v
                            )
                            fix_summary = f"{summary_text} [{scores_compact}]"[:400]
                        else:
                            retros = [
                                f"{s.type}:{s.quality_score}"
                                for s in sprints
                                if s.quality_score
                            ]
                            if retros:
                                fix_summary = f"Cycle {cycle_num} — " + " · ".join(
                                    retros
                                )
                        # Estimate defect_count from adversarial retro_notes
                        adv_sprint = sprint_by_type.get("adversarial")
                        if adv_sprint and adv_sprint.retro_notes:
                            import re as _re

                            defect_count = len(
                                _re.findall(
                                    r"\b(fail|bug|defect|error|issue|reject)\b",
                                    adv_sprint.retro_notes,
                                    _re.IGNORECASE,
                                )
                            )
                except Exception:
                    pass
                import json as _json2

                # Stub record — backfilled from mission/sprint data
                # Use DO UPDATE to enrich stubs that were inserted with no scores
                conn.execute(
                    "INSERT INTO ac_cycles (project_id, cycle_num, platform_run_id, status,"
                    " phase_scores, total_score, defect_count, fix_summary, started_at, completed_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(project_id, cycle_num) DO UPDATE SET"
                    " platform_run_id=COALESCE(NULLIF(excluded.platform_run_id,''), ac_cycles.platform_run_id),"
                    " status=excluded.status,"
                    " phase_scores=CASE WHEN ac_cycles.total_score <= 0 THEN excluded.phase_scores ELSE ac_cycles.phase_scores END,"
                    " total_score=CASE WHEN ac_cycles.total_score <= 0 THEN excluded.total_score ELSE ac_cycles.total_score END,"
                    " defect_count=CASE WHEN ac_cycles.defect_count = 0 THEN excluded.defect_count ELSE ac_cycles.defect_count END,"
                    " fix_summary=CASE WHEN ac_cycles.total_score <= 0 OR ac_cycles.fix_summary LIKE 'Cycle % — %ompleted' OR ac_cycles.fix_summary LIKE 'Cycle % — unknown' THEN excluded.fix_summary ELSE ac_cycles.fix_summary END,"
                    " completed_at=COALESCE(NULLIF(excluded.completed_at,''), ac_cycles.completed_at)",
                    (
                        project_id,
                        cycle_num,
                        run_id,
                        status,
                        _json2.dumps(phase_scores_dict),
                        total_score,
                        defect_count,
                        fix_summary,
                        started,
                        completed,
                    ),
                )
            conn.commit()
        except Exception:
            pass
        # ── Load all cycles ──
        try:
            rows = conn.execute(
                "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num",
                (project_id,),
            ).fetchall()
        except Exception:
            rows = []
        conn.close()
        return rows

    cycles_raw = await asyncio.to_thread(_load)
    cycles = []
    for c in cycles_raw:
        row = dict(c)
        try:
            row["phase_scores_dict"] = _json.loads(row.get("phase_scores") or "{}")
        except Exception:
            row["phase_scores_dict"] = {}
        cycles.append(row)

    return _templates(request).TemplateResponse(
        "partials/workflows_improvement_cycles.html",
        {
            "request": request,
            "cycles": cycles,
            "phases": _AC_PHASES,
            "project_id": project_id,
        },
    )


# Thompson variant selection constants — skills with A/B variants
_AC_SKILL_VARIANTS: dict[str, list[str]] = {
    "ac-codex": ["v1", "v2"],
    "ac-adversarial": ["v1", "v2"],
}


def _ac_select_skill_variants(project_id: str) -> dict[str, str]:
    """Select the best skill variant via Thompson Sampling for each AC skill.

    Returns a dict like {"ac-codex": "v2", "ac-adversarial": "v1"}.
    Falls back to "v1" if the module is unavailable.
    """
    try:
        from ...ac.skill_thompson import ac_skill_select_variant

        # Look up tier for cross-project fallback
        tier = next(
            (p.get("tier") for p in _AC_PROJECTS if p["id"] == project_id), None
        )
        return {
            skill: ac_skill_select_variant(
                skill, variants, project_id=project_id, tier=tier
            )
            for skill, variants in _AC_SKILL_VARIANTS.items()
        }
    except Exception:
        return {skill: "v1" for skill in _AC_SKILL_VARIANTS}


@router.post("/api/improvement/start/{project_id}", dependencies=[Depends(require_auth())])
async def api_improvement_start(project_id: str):
    """Launch an AC improvement cycle to improve the SF itself, using a pilot project workspace.

    NOTE: This is NOT the SAFe project lifecycle for the pilot project itself.
    For the full project lifecycle (ideation → epics → features → sprints → deploy),
    use ideation-to-prod / epic-decompose / feature-sprint workflows via the SF teams
    (Team CI/CD, Team Deploy, Feature Teams, etc.).

    This endpoint triggers ac-improvement-cycle which analyses the pilot project workspace
    to detect and fix SF issues (skills, prompts, workflow YAML).
    Scope: skills/*.md, agents/store.py, workflows/definitions/*.yaml — NOT project source code.
    """
    from fastapi.responses import JSONResponse

    # Validate project_id
    valid_ids = {p["id"] for p in _AC_PROJECTS}
    if project_id not in valid_ids:
        return JSONResponse(
            {"error": f"Unknown project: {project_id}"}, status_code=404
        )

    # Determine next cycle number
    def _get_next_cycle():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            row = conn.execute(
                "SELECT current_cycle FROM ac_project_state WHERE project_id=?",
                (project_id,),
            ).fetchone()
            cycle_num = (row["current_cycle"] if row else 0) + 1
        except Exception:
            cycle_num = 1
        conn.close()
        return cycle_num

    cycle_num = await asyncio.to_thread(_get_next_cycle)

    # Build mission brief for the workflow
    proj = next(p for p in _AC_PROJECTS if p["id"] == project_id)

    # Build enriched brief with user stories, a11y requirements, and design tokens
    _stories = "\n".join(f"  - {s}" for s in proj.get("user_stories", []))
    _a11y = "\n".join(f"  - {a}" for a in proj.get("a11y_requirements", []))
    _tokens = "\n".join(f"  {k}: {v}" for k, v in proj.get("design_tokens", {}).items())
    from ...config import DATA_DIR as _DATA_DIR

    _workspace = str(_DATA_DIR / "workspaces" / project_id)
    brief = (
        f"AC Amélioration Continue — {proj['name']} — Cycle {cycle_num}/20\n\n"
        f"Projet : {proj['id']}\nStack : {', '.join(proj['tech'])}\nTier : {proj['tier_label']}\n"
        f"## Workspace\n{_workspace}\n"
        f"TOUS les chemins de fichiers DOIVENT commencer par : {_workspace}/\n"
        + (f"Description : {proj['description']}\n" if proj.get("description") else "")
        + (f"\nUser Stories:\n{_stories}\n" if _stories else "")
        + (
            f"\nExigences Accessibilité (WCAG AA obligatoire):\n{_a11y}\n"
            if _a11y
            else ""
        )
        + (
            f"\nDesign Tokens CSS (utiliser UNIQUEMENT ces valeurs, aucune valeur hardcodée):\n{_tokens}\n"
            if _tokens
            else ""
        )
        + f"\nCycle {cycle_num}/20 : inception → TDD sprint → adversarial → QA → CI/CD → enregistrement.\n"
        f"Objectif : score > 80/100, 0 défauts critiques, traçabilité 100%.\n"
        f"INCEPTION (phase 0) : OBLIGATOIRE — appeler code_write pour créer/mettre à jour {_workspace}/INCEPTION.md avec le cycle {cycle_num}, user stories complètes, stack, et critères d'acceptance GIVEN/WHEN/THEN.\n"
        f"Si cycle > 1 : lire ADVERSARIAL_{{N-1}}.md et CICD_FAILURE_{{N-1}}.md pour les corrections à intégrer dans INCEPTION.md.\n"
        f"Workflow : ac-improvement-cycle"
    )

    # Ensure pilot project is registered in projects table with PILOTE domain + protected
    def _ensure_pilot_project():
        from ...projects.manager import get_project_store, Project
        from ...config import DATA_DIR

        ps = get_project_store()
        existing = ps.get(project_id)
        workspace = str(DATA_DIR / "workspaces" / project_id)
        if not existing:
            ps.create(
                Project(
                    id=project_id,
                    name=proj["name"],
                    description=proj.get("description", ""),
                    factory_type="sf",
                    domains=proj.get("tech", []),
                    path=workspace,
                    client_domain="PILOTE",
                    is_protected=True,
                )
            )
        else:
            # Always ensure path points to the canonical project workspace
            existing.client_domain = "PILOTE"
            existing.is_protected = True
            existing.path = workspace
            ps.update(existing)

    await asyncio.to_thread(_ensure_pilot_project)

    # Stop previous AC sessions for this project (preserve non-AC sessions)
    # ⚠️ AC = SUPERVISION — dual sessions: [BUILD] feature-sprint + [SUPERVISE] ac-supervision
    # Only interrupt previous AC sessions (type=ac-builder/ac-supervision), not unrelated sessions
    def _stop_existing_ac_sessions():
        from ...db.migrations import get_db
        import json as _json

        db = get_db()
        try:
            rows = db.execute(
                "SELECT id, config_json FROM sessions WHERE project_id=? AND status IN ('active','running')",
                (project_id,),
            ).fetchall()
            for row in rows:
                try:
                    cfg = _json.loads(row["config_json"] or "{}")
                except Exception:
                    cfg = {}
                # Only interrupt AC sessions (builder + supervision), preserve everything else
                if (
                    cfg.get("type") in ("ac-builder", "ac-supervision")
                    or cfg.get("workflow_id") == "ac-improvement-cycle"
                ):
                    db.execute(
                        "UPDATE sessions SET status='interrupted' WHERE id=?",
                        (row["id"],),
                    )
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    await asyncio.to_thread(_stop_existing_ac_sessions)

    # Pause auto-resume during AC cycle — give 100% LLM budget to AC
    import os as _os_ac

    _os_ac.environ["PLATFORM_AUTO_RESUME_ENABLED"] = "0"
    logger.warning(
        "AC cycle: auto-resume PAUSED for project %s cycle %d", project_id, cycle_num
    )

    # Ingest previous cycle artifacts into project memory BEFORE workspace reset
    # so agents can recall previous findings, failures, and corrections next cycle.
    def _ingest_previous_artifacts():
        from ...memory.manager import get_memory_manager

        mem = get_memory_manager()
        ws = _DATA_DIR / "workspaces" / project_id
        if not ws.exists():
            return
        prev = cycle_num - 1
        artifacts = [
            (f"ADVERSARIAL_{prev}.md", f"adversarial-cycle-{prev}", "learning"),
            (f"QA_REPORT_{prev}.md", f"qa-report-cycle-{prev}", "learning"),
            (f"CICD_FAILURE_{prev}.md", f"cicd-failure-cycle-{prev}", "learning"),
            ("INCEPTION.md", f"inception-cycle-{prev}", "context"),
        ]
        for filename, key, category in artifacts:
            fpath = ws / filename
            if fpath.exists():
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")[:4096]
                    mem.project_store(
                        project_id,
                        key,
                        content,
                        category=category,
                        source="auto-ingest",
                        confidence=0.9,
                    )
                except Exception:
                    pass

    if cycle_num > 1:
        await asyncio.to_thread(_ingest_previous_artifacts)

    # Reset workspace for fresh cycle — keep .git/ history but remove all other files
    def _reset_workspace():
        import shutil

        ws = _DATA_DIR / "workspaces" / project_id
        if ws.exists():
            for item in ws.iterdir():
                if item.name == ".git":
                    continue
                if item.is_symlink():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink(missing_ok=True)

    await asyncio.to_thread(_reset_workspace)

    # Store project context in memory AFTER workspace reset so all agents know the stack
    def _seed_project_memory():
        from ...memory.manager import get_memory_manager

        mem = get_memory_manager()
        stack_str = ", ".join(proj.get("tech", []))
        mem.project_store(
            project_id,
            "project-stack",
            f"Stack: {stack_str}\nWorkspace: {_workspace}\nCycle: {cycle_num}/20",
            category="context",
            source="auto-seed",
            confidence=1.0,
        )
        if proj.get("description"):
            mem.project_store(
                project_id,
                "project-brief",
                proj["description"],
                category="context",
                source="auto-seed",
                confidence=1.0,
            )
        if proj.get("user_stories"):
            mem.project_store(
                project_id,
                "project-user-stories",
                "\n".join(proj["user_stories"]),
                category="context",
                source="auto-seed",
                confidence=1.0,
            )

    await asyncio.to_thread(_seed_project_memory)

    try:
        from ...missions.store import get_mission_store
        from ...epics.store import MissionDef

        store = get_mission_store()
        mission_def = MissionDef(
            name=f"AC {proj['name']} — Cycle {cycle_num}",
            description=brief,
            goal=f"Score > 80/100, 0 défauts critiques, traçabilité 100% — cycle {cycle_num}/20",
            type="improvement",
            workflow_id="ac-improvement-cycle",
            status="active",
            project_id=project_id,
            config={
                "project_id": project_id,
                "cycle_num": cycle_num,
                "ac": True,
                "skill_variants": _ac_select_skill_variants(project_id),
            },
        )
        created = await asyncio.to_thread(store.create_mission, mission_def)
        run_id = str(created.id)

        # ── DUAL SESSION LAUNCH: [BUILD] + [SUPERVISE] in parallel ──
        # ⚠️ AC = SUPERVISION: builders run feature-sprint, supervisors run ac-supervision-cycle
        from ...sessions.store import get_session_store, SessionDef
        from ...workflows.store import get_workflow_store
        from .workflows import _run_workflow_background

        wf_store = get_workflow_store()
        sess_store = get_session_store()
        skill_variants = _ac_select_skill_variants(project_id)
        builder_sess_id = None
        supervisor_sess_id = None

        # ── Session [BUILD] — feature-sprint with normal Feature Teams ──
        builder_wf = wf_store.get("feature-sprint")
        if builder_wf:
            builder_sess = SessionDef(
                name=f"AC {proj['name']} — Cycle {cycle_num} [BUILD]",
                goal=brief,
                project_id=project_id,
                status="active",
                config={
                    "type": "ac-builder",
                    "workflow_id": "feature-sprint",
                    "mission_id": run_id,
                    "ac": True,
                    "cycle_num": cycle_num,
                    "project_id": project_id,
                    "skill_variants": skill_variants,
                },
            )
            created_builder = await asyncio.to_thread(sess_store.create, builder_sess)
            builder_sess_id = created_builder.id
            _keep_task(
                asyncio.create_task(
                    _run_workflow_background(
                        builder_wf, builder_sess_id, brief, project_id
                    )
                )
            )

        # ── Session [SUPERVISE] — ac-supervision-cycle with AC supervisors (read-only) ──
        supervisor_wf = wf_store.get("ac-supervision-cycle")
        if supervisor_wf and builder_sess_id:
            supervisor_sess = SessionDef(
                name=f"AC {proj['name']} — Cycle {cycle_num} [SUPERVISE]",
                goal=f"Supervise & grade cycle {cycle_num} outputs — READ-ONLY",
                project_id=project_id,
                status="active",
                config={
                    "type": "ac-supervision",
                    "workflow_id": "ac-supervision-cycle",
                    "mission_id": run_id,
                    "ac": True,
                    "cycle_num": cycle_num,
                    "project_id": project_id,
                    "builder_session_id": builder_sess_id,
                    "supervisors": [
                        "ac-architect",
                        "ac-adversarial",
                        "ac-qa-agent",
                        "ac-coach",
                    ],
                },
            )
            created_supervisor = await asyncio.to_thread(
                sess_store.create, supervisor_sess
            )
            supervisor_sess_id = created_supervisor.id
            # Small delay so builder starts first, supervisors observe
            await asyncio.sleep(1)
            _keep_task(
                asyncio.create_task(
                    _run_workflow_background(
                        supervisor_wf, supervisor_sess_id, brief, project_id
                    )
                )
            )

        # Primary session_id = builder (backward compat for CLI/API)
        sess_id = builder_sess_id

        # Update project state
        def _update_state():
            import time

            conn = _ac_get_db()
            try:
                conn.execute(
                    "INSERT INTO ac_project_state (project_id, current_cycle, status, current_run_id, builder_session_id, supervisor_session_id, updated_at)"
                    " VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET"
                    " current_cycle=excluded.current_cycle, status=excluded.status,"
                    " current_run_id=excluded.current_run_id,"
                    " builder_session_id=excluded.builder_session_id,"
                    " supervisor_session_id=excluded.supervisor_session_id,"
                    " updated_at=excluded.updated_at",
                    (
                        project_id,
                        cycle_num,
                        "running",
                        run_id,
                        builder_sess_id,
                        supervisor_sess_id,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ),
                )
                conn.commit()
            except Exception:
                pass
            conn.close()

        await asyncio.to_thread(_update_state)
        return JSONResponse(
            {
                "run_id": run_id,
                "session_id": sess_id,
                "builder_session_id": builder_sess_id,
                "supervisor_session_id": supervisor_sess_id,
                "cycle_num": cycle_num,
                "project_id": project_id,
            }
        )

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/improvement/stop/{project_id}", dependencies=[Depends(require_auth())])
async def api_improvement_stop(project_id: str):
    """Stop/abort a running AC cycle for a project."""
    import time
    from fastapi.responses import JSONResponse

    valid_ids = {p["id"] for p in _AC_PROJECTS}
    if project_id not in valid_ids:
        return JSONResponse(
            {"error": f"Unknown project: {project_id}"}, status_code=404
        )

    cancelled_run_id = None

    def _stop():
        nonlocal cancelled_run_id
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            row = conn.execute(
                "SELECT current_run_id, status FROM ac_project_state WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if row:
                cancelled_run_id = row["current_run_id"]
                conn.execute(
                    "UPDATE ac_project_state SET status='idle', current_run_id=NULL, updated_at=? WHERE project_id=?",
                    (time.strftime("%Y-%m-%dT%H:%M:%SZ"), project_id),
                )
                conn.commit()
        except Exception:
            pass
        conn.close()

    await asyncio.to_thread(_stop)

    # Try to cancel the mission run if it exists
    if cancelled_run_id:
        try:
            from ...missions.store import get_mission_store

            store = get_mission_store()
            await asyncio.to_thread(
                store.update_mission_status, cancelled_run_id, "cancelled"
            )
        except Exception:
            pass

    return JSONResponse(
        {"ok": True, "project_id": project_id, "cancelled_run": cancelled_run_id}
    )


@router.post("/api/improvement/rollback/{project_id}", dependencies=[Depends(require_auth())])
async def api_improvement_rollback(project_id: str, request: Request):
    """
    AC Coach rollback: git revert last commit in workspace + delete current cycle from DB.
    Called by ac-coach when score drops > 10pts.
    """
    import time
    import subprocess
    from fastapi.responses import JSONResponse
    from .helpers import _parse_body

    body = await _parse_body(request)
    reason = body.get("reason", "score regression")
    cycle_num = int(body.get("cycle_num", 0))

    valid_ids = {p["id"] for p in _AC_PROJECTS}
    if project_id not in valid_ids:
        return JSONResponse(
            {"error": f"Unknown project: {project_id}"}, status_code=404
        )

    def _rollback():
        from ...config import DATA_DIR

        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            state = conn.execute(
                "SELECT last_git_sha, current_cycle, current_run_id FROM ac_project_state WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if not state:
                return {"error": "no state found"}

            last_sha = state.get("last_git_sha", "")
            _ = last_sha  # kept for potential future use (git reset --hard)
            current_cycle = state.get("current_cycle", 0)
            run_id = state.get("current_run_id", "")
            rollback_cycle = cycle_num or current_cycle

            # Find workspace for git revert
            workspace_path = None
            if run_id:
                try:
                    from ...agents.store import get_session_store

                    for s in get_session_store().list():
                        cfg = s.config if isinstance(s.config, dict) else {}
                        if cfg.get("mission_id") == run_id or s.id == run_id:
                            ws = DATA_DIR / "workspaces" / s.id
                            if ws.exists():
                                workspace_path = str(ws)
                                break
                except Exception:
                    pass
                if not workspace_path:
                    ws = DATA_DIR / "workspaces" / run_id
                    if ws.exists():
                        workspace_path = str(ws)

            git_reverted = False
            git_output = ""
            if workspace_path:
                try:
                    r = subprocess.run(
                        ["git", "revert", "--no-commit", "HEAD"],
                        cwd=workspace_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if r.returncode == 0:
                        subprocess.run(
                            [
                                "git",
                                "commit",
                                "-m",
                                f"revert(ac-coach): rollback cycle {rollback_cycle} — {reason[:120]}",
                            ],
                            cwd=workspace_path,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        git_reverted = True
                        git_output = "git revert HEAD applied"
                    else:
                        git_output = r.stderr[:200]
                except Exception as e:
                    git_output = str(e)

            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            # Mark cycle as rolled back (don't delete, keep for history)
            conn.execute(
                "UPDATE ac_cycles SET rolled_back=1 WHERE project_id=? AND cycle_num=?",
                (project_id, rollback_cycle),
            )
            # Reset project state to previous cycle
            prev_cycle = max(0, rollback_cycle - 1)
            conn.execute(
                "UPDATE ac_project_state SET status='idle', current_cycle=?, current_run_id=NULL, updated_at=? WHERE project_id=?",
                (prev_cycle, now, project_id),
            )
            conn.commit()

            # Close any active experiment as rolled_back
            try:
                from ...ac.experiments import get_active_experiment, close_experiment

                exp = get_active_experiment(project_id)
                if exp:
                    close_experiment(
                        exp["id"],
                        None,
                        None,
                        "none",
                        strategy_notes=reason,
                        rolled_back=True,
                    )
            except Exception:
                pass

            return {
                "ok": True,
                "project_id": project_id,
                "cycle_rolled_back": rollback_cycle,
                "reset_to_cycle": prev_cycle,
                "git_reverted": git_reverted,
                "git_output": git_output,
                "reason": reason,
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()

    result = await asyncio.to_thread(_rollback)
    if "error" in result:
        return JSONResponse(result, status_code=500)
    return JSONResponse(result)


@router.post("/api/improvement/experiment", dependencies=[Depends(require_auth())])
async def api_improvement_experiment(request: Request):
    """
    Register an A/B experiment for the current cycle.
    Called by ac-coach when it decides to test a new variant.
    """
    from fastapi.responses import JSONResponse
    from .helpers import _parse_body

    body = await _parse_body(request)
    project_id = body.get("project_id")
    cycle_num = int(body.get("cycle_num", 0))
    experiment_key = body.get("experiment_key", "")
    variant_a = body.get("variant_a", "v1")
    variant_b = body.get("variant_b", "v2")
    score_before = int(body.get("score_before", 0))
    strategy_notes = body.get("strategy_notes", "")

    if not project_id or not experiment_key:
        return JSONResponse(
            {"error": "project_id and experiment_key required"}, status_code=400
        )

    def _record():
        from ...ac.experiments import record_experiment

        exp_id = record_experiment(
            project_id=project_id,
            cycle_num=cycle_num,
            experiment_key=experiment_key,
            variant_a=variant_a,
            variant_b=variant_b,
            score_before=score_before,
            strategy_notes=strategy_notes,
        )
        return exp_id

    exp_id = await asyncio.to_thread(_record)
    return JSONResponse(
        {
            "ok": True,
            "experiment_id": exp_id,
            "project_id": project_id,
            "experiment_key": experiment_key,
            "variant_a": variant_a,
            "variant_b": variant_b,
        }
    )


@router.post("/api/improvement/inject-cycle", dependencies=[Depends(require_auth())])
async def api_improvement_inject_cycle(request: Request):
    """Record a completed AC cycle — called by ac-cicd-agent after CI/CD."""
    import time
    import json as _json
    from fastapi.responses import JSONResponse
    from .helpers import _parse_body

    body = await _parse_body(request)
    project_id = body.get("project_id")
    cycle_num = int(body.get("cycle_num", 0))
    if not project_id or not cycle_num:
        return JSONResponse(
            {"error": "project_id and cycle_num required"}, status_code=400
        )

    git_sha = body.get("git_sha", "")
    status = body.get("status", "completed")
    phase_scores = body.get("phase_scores", {})
    total_score = int(body.get("total_score", 0))
    defect_count = int(body.get("defect_count", 0))
    fix_summary = body.get("fix_summary", "")
    adversarial_scores = body.get("adversarial_scores", {})
    traceability_score = int(body.get("traceability_score", 0))
    screenshot_path = body.get("screenshot_path", "")  # relative path in workspace
    platform_run_id = body.get("platform_run_id", f"ac-{project_id}-{cycle_num}")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            phase_scores_json = (
                _json.dumps(phase_scores)
                if isinstance(phase_scores, dict)
                else phase_scores
            )
            adv_scores_json = (
                _json.dumps(adversarial_scores)
                if isinstance(adversarial_scores, dict)
                else adversarial_scores
            )
            conn.execute(
                "INSERT INTO ac_cycles (project_id, cycle_num, git_sha, status, phase_scores,"
                " total_score, defect_count, fix_summary, adversarial_scores, traceability_score,"
                " screenshot_path, started_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(project_id, cycle_num) DO UPDATE SET"
                " git_sha=excluded.git_sha, status=excluded.status, phase_scores=excluded.phase_scores,"
                " total_score=excluded.total_score, defect_count=excluded.defect_count,"
                " fix_summary=excluded.fix_summary, adversarial_scores=excluded.adversarial_scores,"
                " traceability_score=excluded.traceability_score,"
                " screenshot_path=COALESCE(NULLIF(excluded.screenshot_path,''), ac_cycles.screenshot_path),"
                " completed_at=excluded.completed_at",
                (
                    project_id,
                    cycle_num,
                    git_sha,
                    status,
                    phase_scores_json,
                    total_score,
                    defect_count,
                    fix_summary,
                    adv_scores_json,
                    traceability_score,
                    screenshot_path,
                    now,
                    now,
                ),
            )
            # Compute average from existing cycles
            avg_row = conn.execute(
                "SELECT AVG(total_score) as avg FROM ac_cycles WHERE project_id=? AND total_score > 0",
                (project_id,),
            ).fetchone()
            avg_score = float(avg_row["avg"] or 0) if avg_row else 0.0
            ci_status = "green" if status == "completed" else "red"
            new_status = "idle" if status == "completed" else status
            # Two-step upsert: INSERT then UPDATE — avoids GREATEST/MAX cross-DB issues
            conn.execute(
                "INSERT INTO ac_project_state (project_id, current_cycle, status, total_score_avg,"
                " last_git_sha, ci_status, updated_at)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(project_id) DO NOTHING",
                (project_id, cycle_num, new_status, avg_score, git_sha, ci_status, now),
            )
            conn.execute(
                "UPDATE ac_project_state SET"
                " current_cycle=CASE WHEN current_cycle < ? THEN ? ELSE current_cycle END,"
                " status=?, total_score_avg=?, last_git_sha=?, ci_status=?, updated_at=?"
                " WHERE project_id=?",
                (
                    cycle_num,
                    cycle_num,
                    new_status,
                    avg_score,
                    git_sha,
                    ci_status,
                    now,
                    project_id,
                ),
            )
        except Exception as e:
            conn.close()
            raise e
        conn.commit()
        conn.close()

    try:
        await asyncio.to_thread(_write)

        # ── Intelligence feedback loop (async, non-blocking) ──────────────────
        async def _run_intelligence():
            try:
                from ...ac.reward import ac_reward_from_cycle, ac_rl_state
                from ...ac.convergence import (
                    ac_convergence_check,
                    ac_check_skill_eval_trigger,
                    ac_intervention_plan,
                )

                # Build cycle dict for reward computation
                cycle_data = {
                    "total_score": total_score,
                    "adversarial_scores": adversarial_scores
                    if isinstance(adversarial_scores, dict)
                    else {},
                    "traceability_score": traceability_score,
                    "defect_count": defect_count,
                    "veto_count": int(body.get("veto_count", 0)),
                }

                # Load previous cycle for regression detection
                def _load_prev():
                    conn2 = _ac_get_db()
                    try:
                        row = conn2.execute(
                            "SELECT total_score FROM ac_cycles WHERE project_id=? AND cycle_num=?",
                            (project_id, cycle_num - 1),
                        ).fetchone()
                        return dict(row) if row else None
                    except Exception:
                        return None
                    finally:
                        conn2.close()

                prev_cycle = await asyncio.to_thread(_load_prev)
                reward = ac_reward_from_cycle(cycle_data, prev_cycle)

                # ── 1. RL: record experience ──────────────────────────────────
                proj_meta = next((p for p in _AC_PROJECTS if p["id"] == project_id), {})
                tier = proj_meta.get("tier", "simple")
                state = ac_rl_state(
                    project_id, cycle_num, total_score, defect_count, tier
                )
                next_state = ac_rl_state(
                    project_id,
                    cycle_num + 1,
                    total_score,
                    defect_count,
                    tier,
                )
                try:
                    from ...agents.rl_policy import get_rl_policy

                    rl = get_rl_policy()
                    rl.record_experience(
                        mission_id=platform_run_id,
                        state_dict=state,
                        action="keep",
                        reward=reward,
                        next_state_dict=next_state,
                    )

                    # Persist reward back to cycle row
                    def _update_reward():
                        conn_r = _ac_get_db()
                        try:
                            conn_r.execute(
                                "UPDATE ac_cycles SET rl_reward=? WHERE project_id=? AND cycle_num=?",
                                (reward, project_id, cycle_num),
                            )
                        except Exception:
                            pass
                        finally:
                            conn_r.close()

                    await asyncio.to_thread(_update_reward)

                    # Get recommendation for next cycle
                    rec = rl.recommend(
                        mission_id=f"ac-{project_id}-next",
                        phase_id="ac-tdd-sprint",
                        state_dict=next_state,
                    )
                    if rec.get("fired"):
                        # Store RL hint in ac_project_state
                        def _store_hint():
                            import json as _j

                            conn3 = _ac_get_db()
                            try:
                                conn3.execute(
                                    "UPDATE ac_project_state SET next_cycle_hint=? WHERE project_id=?",
                                    (_j.dumps(rec), project_id),
                                )
                            except Exception:
                                pass
                            finally:
                                conn3.close()

                        await asyncio.to_thread(_store_hint)
                        log.info(
                            "AC RL hint for %s cycle %d: %s (confidence=%.2f)",
                            project_id,
                            cycle_num + 1,
                            rec["action"],
                            rec["confidence"],
                        )
                except Exception as e:
                    log.debug("AC RL feedback error: %s", e)

                # ── 2. Thompson sampling feedback ─────────────────────────────
                prev_score = prev_cycle["total_score"] if prev_cycle else None
                if prev_score is not None:
                    try:
                        from ...ac.skill_thompson import ac_skill_record
                        from ...db.migrations import get_db

                        # Read skill_variants from the mission config (set at cycle start)
                        def _load_variants():
                            import json as _j

                            conn_v = get_db()
                            try:
                                row = conn_v.execute(
                                    "SELECT config_json FROM missions WHERE id=? LIMIT 1",
                                    (platform_run_id,),
                                ).fetchone()
                                if row and row["config_json"]:
                                    cfg = _j.loads(row["config_json"])
                                    return cfg.get("skill_variants", {})
                                return {}
                            except Exception:
                                return {}
                            finally:
                                conn_v.close()

                        variants_used = await asyncio.to_thread(_load_variants)
                        for skill_id, variant in variants_used.items():
                            ac_skill_record(
                                skill_id=skill_id,
                                variant=variant,
                                project_id=project_id,
                                cycle_score=total_score,
                                prev_cycle_score=prev_score,
                                tier=tier,
                            )
                            log.info(
                                "AC Thompson: recorded %s=%s score=%d prev=%d → %s",
                                skill_id,
                                variant,
                                total_score,
                                prev_score,
                                "win" if total_score > prev_score else "loss",
                            )
                    except Exception as e:
                        log.debug("AC Thompson record error: %s", e)

                # ── 3. Convergence detection ──────────────────────────────────
                def _load_scores():
                    conn4 = _ac_get_db()
                    try:
                        rows = conn4.execute(
                            "SELECT total_score FROM ac_cycles WHERE project_id=? ORDER BY cycle_num",
                            (project_id,),
                        ).fetchall()
                        return [r["total_score"] for r in rows]
                    except Exception:
                        return []
                    finally:
                        conn4.close()

                all_scores = await asyncio.to_thread(_load_scores)
                if all_scores:
                    conv = ac_convergence_check(all_scores)
                    # intervention plan is logged; GA/skill-eval triggers follow
                    ac_intervention_plan(conv["status"], project_id)
                    log.info(
                        "AC convergence %s: %s → %s (reward=%.3f)",
                        project_id,
                        conv["status"],
                        conv["recommendation"],
                        reward,
                    )

                    # Trigger GA evolution on plateau
                    if conv["status"] == "plateau" and len(all_scores) >= 5:
                        try:
                            from ...agents.evolution import GAEngine

                            def _ga_evolve():
                                GAEngine().evolve(
                                    "ac-improvement-cycle", generations=20
                                )

                            asyncio.ensure_future(asyncio.to_thread(_ga_evolve))
                            log.info(
                                "AC: triggered GA evolution for %s (plateau)",
                                project_id,
                            )
                        except Exception as e:
                            log.debug("AC GA trigger error: %s", e)

                    # Skill eval trigger check
                    eval_triggers = ac_check_skill_eval_trigger(cycle_num, {})
                    if eval_triggers:
                        log.info(
                            "AC: skill eval triggered at cycle %d for: %s",
                            cycle_num,
                            eval_triggers,
                        )

                        # Store in ac_project_state for the next cycle inception to read
                        def _store_eval_trigger():
                            import json as _j

                            conn5 = _ac_get_db()
                            try:
                                conn5.execute(
                                    "UPDATE ac_project_state SET skill_eval_pending=? WHERE project_id=?",
                                    (_j.dumps(eval_triggers), project_id),
                                )
                            except Exception:
                                pass
                            finally:
                                conn5.close()

                        await asyncio.to_thread(_store_eval_trigger)

            except Exception as e:
                log.debug("AC intelligence loop error: %s", e)

        asyncio.ensure_future(_run_intelligence())

        return JSONResponse(
            {"ok": True, "project_id": project_id, "cycle_num": cycle_num}
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/api/improvement/screenshot/{project_id}/{cycle_num}")
async def api_improvement_screenshot(project_id: str, cycle_num: int):
    """Serve the screenshot captured during a cycle's QA phase."""
    from fastapi.responses import FileResponse, Response

    def _find_screenshot():
        from ...config import DATA_DIR

        conn = _ac_get_db()
        try:
            row = conn.execute(
                "SELECT screenshot_path, platform_run_id FROM ac_cycles"
                " WHERE project_id=? AND cycle_num=?",
                (project_id, cycle_num),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        screenshot_path = (row.get("screenshot_path") or "").strip()
        run_id = (row.get("platform_run_id") or "").strip()
        # Find session_ids linked to this run
        session_ids = []
        if run_id:
            try:
                from ...agents.store import get_session_store

                for s in get_session_store().list():
                    cfg = s.config if isinstance(s.config, dict) else {}
                    if cfg.get("mission_id") == run_id or s.id == run_id:
                        session_ids.append(s.id)
            except Exception:
                pass
        candidates = [DATA_DIR / "workspaces" / sid for sid in session_ids]
        if run_id:
            candidates.append(DATA_DIR / "workspaces" / run_id)
        # Also check project-level workspace dir
        candidates.append(DATA_DIR / "workspaces" / project_id)
        # Try explicit path first
        if screenshot_path:
            for ws in candidates:
                p = ws / screenshot_path
                if p.exists():
                    return str(p)
            # Also try absolute path
            from pathlib import Path as _Path

            _abs = _Path(screenshot_path)
            if _abs.is_absolute() and _abs.exists():
                return str(_abs)
        # Auto-discover screenshot
        for ws in candidates:
            if not ws.exists():
                continue
            # Check screenshots/ subdir first
            ss_dir = ws / "screenshots"
            if ss_dir.exists():
                for pat in ("desktop*.png", "screen*.png", "*.png"):
                    pngs = sorted(ss_dir.glob(pat))
                    if pngs:
                        return str(pngs[0])
            # Also check workspace root for any PNG
            root_pngs = sorted(ws.glob("*.png"))
            if root_pngs:
                return str(root_pngs[0])
        return None

    path = await asyncio.to_thread(_find_screenshot)
    if path:
        return FileResponse(path, media_type="image/png")
    return Response(status_code=404)


@router.post("/api/improvement/backfill/{project_id}", dependencies=[Depends(require_auth())])
async def api_improvement_backfill(project_id: str):
    """Force re-backfill of cycle records from mission/sprint data. Updates stubs."""
    from fastapi.responses import JSONResponse

    def _force_backfill():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        updated = 0
        try:
            # Delete all stub rows (total_score=0 with no git_sha = backfill-only stubs)
            conn.execute(
                "DELETE FROM ac_cycles WHERE project_id=? AND total_score = 0 AND (git_sha IS NULL OR git_sha = '')",
                (project_id,),
            )
            conn.commit()
            updated = conn.total_changes
        except Exception:
            pass
        finally:
            conn.close()
        return updated

    deleted = await asyncio.to_thread(_force_backfill)
    return JSONResponse(
        {
            "ok": True,
            "project_id": project_id,
            "stubs_cleared": deleted,
            "message": "Stub cycles cleared. Reload the page to re-backfill from missions.",
        }
    )


@router.get("/api/improvement/project/{project_id}")
async def api_improvement_project_state(project_id: str):
    """
    Return current AC project state including RL hint, convergence, skill eval pending.
    Called by ac-architect at the start of each cycle to get intelligence context.
    """
    import json as _json
    from fastapi.responses import JSONResponse
    from ...ac.convergence import ac_convergence_check

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            state_row = conn.execute(
                "SELECT * FROM ac_project_state WHERE project_id=?", (project_id,)
            ).fetchone()
            cycles = conn.execute(
                "SELECT cycle_num, total_score, defect_count, adversarial_scores, rl_reward "
                "FROM ac_cycles WHERE project_id=? ORDER BY cycle_num",
                (project_id,),
            ).fetchall()
        except Exception:
            state_row = None
            cycles = []
        finally:
            conn.close()
        return state_row, [dict(c) for c in cycles]

    state_row, cycles = await asyncio.to_thread(_load)

    scores = [c["total_score"] for c in cycles]
    conv = (
        ac_convergence_check(scores) if len(scores) >= 3 else {"status": "cold_start"}
    )

    state = dict(state_row) if state_row else {}

    # Parse JSON fields
    for field in ("next_cycle_hint", "skill_eval_pending"):
        raw = state.get(field)
        if raw and isinstance(raw, str):
            try:
                state[field] = _json.loads(raw)
            except Exception:
                pass

    # Project metadata (user stories, a11y, design tokens)
    proj_meta = next((p for p in _AC_PROJECTS if p["id"] == project_id), {})

    return JSONResponse(
        {
            "project_id": project_id,
            "current_cycle": state.get("current_cycle", 0),
            "status": state.get("status", "idle"),
            "total_score_avg": state.get("total_score_avg", 0),
            "convergence": conv,
            "next_cycle_hint": state.get("next_cycle_hint"),  # RL recommendation
            "skill_eval_pending": state.get(
                "skill_eval_pending"
            ),  # skills needing eval
            "last_git_sha": state.get("last_git_sha"),
            "cycle_count": len(cycles),
            "recent_scores": scores[-5:],
            # Dual-session IDs (for watch CLI fallback)
            "builder_session_id": state.get("builder_session_id"),
            "supervisor_session_id": state.get("supervisor_session_id"),
            # Project spec (read by ac-architect to generate INCEPTION.md)
            "user_stories": proj_meta.get("user_stories", []),
            "a11y_requirements": proj_meta.get("a11y_requirements", []),
            "design_tokens": proj_meta.get("design_tokens", {}),
            "description": proj_meta.get("description", ""),
        }
    )


@router.get("/api/improvement/scores/{project_id}")
async def api_improvement_scores(project_id: str):
    """Return aggregated intelligence metrics for the improvement dashboard."""
    from fastapi.responses import JSONResponse
    from ...ac.convergence import ac_convergence_check
    from ...ac.skill_thompson import ac_skill_stats

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            cycles = conn.execute(
                "SELECT cycle_num, total_score, defect_count, rl_reward, "
                "adversarial_scores, traceability_score "
                "FROM ac_cycles WHERE project_id=? ORDER BY cycle_num",
                (project_id,),
            ).fetchall()
        except Exception:
            cycles = []
        finally:
            conn.close()
        return [dict(c) for c in cycles]

    cycles = await asyncio.to_thread(_load)
    scores = [c["total_score"] for c in cycles]
    rewards = [c.get("rl_reward", 0.0) for c in cycles]
    conv = (
        ac_convergence_check(scores) if len(scores) >= 3 else {"status": "cold_start"}
    )

    # Thompson stats for AC skills — nested {skill: {variant: {wins, losses, avg_score}}}
    skill_stats: dict = {}
    for skill in [
        "ac-architect",
        "ac-codex",
        "ac-adversarial",
        "ac-qa-agent",
        "ac-cicd-agent",
    ]:
        stats_list = await asyncio.to_thread(ac_skill_stats, skill, project_id)
        if stats_list:
            skill_stats[skill] = {
                row["variant"]: {
                    "wins": row.get("wins", 0),
                    "losses": row.get("losses", 0),
                    "avg_score": row.get("avg_score", 0.0),
                }
                for row in stats_list
            }

    return JSONResponse(
        {
            "project_id": project_id,
            "cycles": cycles,
            "convergence": conv,
            "avg_reward": round(sum(rewards) / len(rewards), 3) if rewards else 0.0,
            "skill_stats": skill_stats,
        }
    )


@router.get("/api/improvement/live/{project_id}")
async def api_improvement_live(project_id: str):
    """Comprehensive live snapshot for the project detail modal.
    Returns state, all cycles (phase breakdown, adversarial, fix_summary, tools, errors),
    adversarial findings, and mission run status.
    """
    import json as _json
    from fastapi.responses import JSONResponse

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            state_row = conn.execute(
                "SELECT * FROM ac_project_state WHERE project_id=?", (project_id,)
            ).fetchone()
            cycles = conn.execute(
                "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num DESC LIMIT 20",
                (project_id,),
            ).fetchall()
            adv_rows = conn.execute(
                "SELECT cycle_num, dimension, score, verdict, findings, checked_at "
                "FROM ac_adversarial WHERE project_id=? ORDER BY cycle_num DESC, score ASC LIMIT 50",
                (project_id,),
            ).fetchall()
        except Exception:
            state_row = None
            cycles = []
            adv_rows = []
        finally:
            conn.close()
        return state_row, [dict(c) for c in cycles], [dict(r) for r in adv_rows]

    state_row, cycles_raw, adv_rows = await asyncio.to_thread(_load)

    # Parse cycles
    cycles = []
    all_scores = []
    for c in cycles_raw:
        row = dict(c)
        try:
            row["phase_scores_dict"] = _json.loads(row.get("phase_scores") or "{}")
        except Exception:
            row["phase_scores_dict"] = {}
        try:
            row["adv_dict"] = _json.loads(row.get("adversarial_scores") or "{}")
        except Exception:
            row["adv_dict"] = {}
        all_scores.append(row.get("total_score", 0))
        cycles.append(row)
    all_scores.reverse()  # chronological

    # Parse adversarial findings
    adv_by_cycle: dict = {}
    for r in adv_rows:
        cn = r["cycle_num"]
        if cn not in adv_by_cycle:
            adv_by_cycle[cn] = []
        try:
            r["findings_list"] = _json.loads(r.get("findings") or "[]")
        except Exception:
            r["findings_list"] = []
        adv_by_cycle[cn].append(r)

    # State
    state = dict(state_row) if state_row else {}
    for field in ("next_cycle_hint", "skill_eval_pending"):
        raw = state.get(field)
        if raw and isinstance(raw, str):
            try:
                state[field] = _json.loads(raw)
            except Exception:
                pass

    # Convergence
    from ...ac.convergence import ac_convergence_check

    conv = (
        ac_convergence_check(all_scores)
        if len(all_scores) >= 3
        else {"status": "cold_start"}
    )

    # Mission run status + live activity (events + tool calls)
    run_status = {}
    live_events = []
    tool_activity = []
    agents_active = []
    current_run_id = state.get("current_run_id")
    if current_run_id:
        try:
            from ...missions.store import get_mission_store

            store = get_mission_store()
            run = await asyncio.to_thread(store.get_mission, current_run_id)
            if run:
                run_status = {
                    "id": str(run.id),
                    "name": run.name,
                    "status": run.status,
                    "current_phase": getattr(run, "current_phase", None),
                    "started_at": str(getattr(run, "started_at", "") or ""),
                    "updated_at": str(getattr(run, "updated_at", "") or ""),
                }
        except Exception:
            pass

        # Live events for this mission (last 30)
        def _load_activity():
            import json as _json
            from ...db.migrations import get_db

            db = get_db()
            evts = []
            tools = []
            try:
                rows = db.execute(
                    "SELECT timestamp, event_type, actor, data FROM events "
                    "WHERE mission_id=? ORDER BY timestamp DESC LIMIT 30",
                    (current_run_id,),
                ).fetchall()
                for r in rows:
                    try:
                        d = _json.loads(r["data"] or "{}")
                    except Exception:
                        d = {}
                    evts.append(
                        {
                            "ts": r["timestamp"],
                            "type": r["event_type"],
                            "actor": r["actor"],
                            "summary": d.get("summary")
                            or d.get("message")
                            or d.get("content", "")[:120],
                            "phase": d.get("phase", ""),
                            "tool": d.get("tool_name", ""),
                        }
                    )
            except Exception:
                pass
            # Tool calls linked to sessions of this mission
            try:
                tc_rows = db.execute(
                    """SELECT tc.tool_name, tc.agent_id, tc.success, COUNT(*) as cnt
                       FROM tool_calls tc
                       WHERE tc.session_id IN (
                           SELECT id FROM sessions WHERE config_json LIKE ?
                       )
                       GROUP BY tc.tool_name, tc.agent_id
                       ORDER BY cnt DESC LIMIT 20""",
                    (f"%{current_run_id}%",),
                ).fetchall()
                for r in tc_rows:
                    tools.append(
                        {
                            "tool": r["tool_name"],
                            "agent": r["agent_id"],
                            "count": r["cnt"],
                            "success": bool(r["success"]),
                        }
                    )
            except Exception:
                pass
            db.close()
            return evts, tools

        live_events, tool_activity = await asyncio.to_thread(_load_activity)

        # Aggregate active agents from events + tool_calls
        seen = {}
        for e in live_events:
            a = e.get("actor", "")
            if a and a != "system":
                seen[a] = seen.get(a, 0) + 1
        for t in tool_activity:
            a = t.get("agent", "")
            if a:
                seen[a] = seen.get(a, 0) + t.get("count", 1)
        agents_active = [
            {"id": k, "activity": v}
            for k, v in sorted(seen.items(), key=lambda x: -x[1])[:10]
        ]

    # Latest cycle full detail
    latest = cycles[0] if cycles else {}

    return JSONResponse(
        {
            "project_id": project_id,
            "state": {
                "current_cycle": state.get("current_cycle", 0),
                "status": state.get("status", "idle"),
                "ci_status": state.get("ci_status", "unknown"),
                "last_git_sha": state.get("last_git_sha", ""),
                "total_score_avg": round(state.get("total_score_avg") or 0, 1),
                "next_cycle_hint": state.get("next_cycle_hint"),
                "skill_eval_pending": state.get("skill_eval_pending"),
                "updated_at": state.get("updated_at", ""),
            },
            "convergence": conv,
            "run": run_status,
            "latest_cycle": {
                "cycle_num": latest.get("cycle_num", 0),
                "status": latest.get("status", ""),
                "total_score": latest.get("total_score", 0),
                "defect_count": latest.get("defect_count", 0),
                "veto_count": latest.get("veto_count", 0),
                "traceability_score": latest.get("traceability_score", 0),
                "ga_fitness": latest.get("ga_fitness", 0),
                "rl_reward": latest.get("rl_reward", 0),
                "fix_summary": latest.get("fix_summary", ""),
                "git_sha": latest.get("git_sha", ""),
                "phase_scores": latest.get("phase_scores_dict", {}),
                "adversarial_scores": latest.get("adv_dict", {}),
                "started_at": latest.get("started_at", ""),
                "completed_at": latest.get("completed_at", ""),
            },
            "cycles": [
                {
                    "cycle_num": c.get("cycle_num"),
                    "total_score": c.get("total_score", 0),
                    "defect_count": c.get("defect_count", 0),
                    "veto_count": c.get("veto_count", 0),
                    "rl_reward": c.get("rl_reward", 0),
                    "traceability_score": c.get("traceability_score", 0),
                    "phase_scores": c.get("phase_scores_dict", {}),
                    "fix_summary": c.get("fix_summary", ""),
                    "status": c.get("status", ""),
                    "started_at": c.get("started_at", ""),
                    "completed_at": c.get("completed_at", ""),
                }
                for c in reversed(cycles)
            ],
            "adversarial": [
                {
                    "cycle_num": r["cycle_num"],
                    "dimension": r["dimension"],
                    "score": r["score"],
                    "verdict": r["verdict"],
                    "findings": r["findings_list"],
                }
                for r in adv_rows
            ],
            "phases": _AC_PHASES,
            "all_scores": all_scores,
            "live_events": live_events[:20],
            "tool_activity": tool_activity,
            "agents_active": agents_active,
            "total_tool_calls": sum(t.get("count", 0) for t in tool_activity),
        }
    )


# ── Legacy redirects ─────────────────────────────────────────────────────────
@router.get("/ceremonies", response_class=HTMLResponse)
async def ceremonies_redirect(request: Request):
    """Legacy redirect — /ceremonies moved to /workflows."""
    from starlette.responses import RedirectResponse

    return RedirectResponse("/workflows", status_code=301)


@router.get("/live", response_class=HTMLResponse)
async def live_page(request: Request):
    """Live — redirect to sessions list."""
    from starlette.responses import RedirectResponse

    return RedirectResponse("/sessions", status_code=302)


@router.get("/live/{session_id}", response_class=HTMLResponse)
async def live_session_page(request: Request, session_id: str):
    """Live ceremony — redirect to session live view."""
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/sessions/{session_id}/live", status_code=302)


@router.get("/art", response_class=HTMLResponse)
async def art_page(request: Request, tab: str = "agents"):
    """ART — Agile Release Trains dashboard with real teams and agents."""
    from ...agents.org import get_org_store

    org = get_org_store()
    tree = org.get_org_tree()
    portfolios = org.list_portfolios()
    all_arts = org.list_arts()
    all_teams = org.list_teams()
    total_members = sum(len(t.members) for t in all_teams)
    return _templates(request).TemplateResponse(
        "art.html",
        {
            "request": request,
            "page_title": "ART",
            "org_tree": tree,
            "portfolios": portfolios,
            "total_arts": len(all_arts),
            "total_teams": len(all_teams),
            "total_members": total_members,
        },
    )


@router.get("/api/art/amelio/specbar/{subtab}")
async def api_art_amelio_specbar(subtab: str):
    """Return SAFe spec bar context for the given Amélioration Continue sub-tab.
    Called live on each tab switch in art.html to populate Programme/Epic/Feature/etc.
    """
    from fastapi.responses import JSONResponse

    def _build():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            # All active AC projects
            states = conn.execute(
                "SELECT project_id, current_cycle, status, current_run_id, total_score_avg,"
                " ci_status FROM ac_project_state ORDER BY updated_at DESC"
            ).fetchall()
            states = [dict(s) for s in states]
            # Most recent cycle for the primary active project
            active = next(
                (s for s in states if s.get("status") not in ("idle", None)), None
            ) or (states[0] if states else None)
            latest_cycle = None
            sprints = []
            if active:
                c = conn.execute(
                    "SELECT * FROM ac_cycles WHERE project_id=? ORDER BY cycle_num DESC LIMIT 1",
                    (active["project_id"],),
                ).fetchone()
                if c:
                    latest_cycle = dict(c)
            # Tasks from current mission via epics/sprints
            if active and active.get("current_run_id"):
                try:
                    from ...missions.store import get_mission_store

                    st = get_mission_store()
                    sp_list = st.list_sprints(active["current_run_id"])
                    sprints = [
                        {
                            "title": f"{s.type} — {s.name or s.type}",
                            "status": s.status,
                        }
                        for s in sp_list
                    ]
                except Exception:
                    pass
        except Exception:
            states, active, latest_cycle, sprints = [], None, None, []
        finally:
            conn.close()
        return states, active, latest_cycle, sprints

    states, active, latest_cycle, sprints = await asyncio.to_thread(_build)

    # Build context per sub-tab
    n_active = sum(1 for s in states if s.get("status") not in ("idle", None))
    n_total = len(states)
    programme = "Software Factory"
    programme_sub = f"{n_active}/{n_total} projets actifs" if n_total else ""

    if subtab == "cycles" or subtab == "ac-panel-cycles":
        if active:
            epic_name = f"AC {active['project_id']} — Cycle {active['current_cycle']}"
            feature = {
                "name": latest_cycle.get("status", "pending")
                if latest_cycle
                else active.get("ci_status", "unknown"),
                "status": active.get("status", ""),
            }
            stories = sprints or (
                [
                    {
                        "title": f"Cycle {active['current_cycle']} en cours",
                        "status": "active",
                    }
                ]
                if active.get("current_cycle")
                else []
            )
            persona = "Marc Lefèvre (Platform Lead)"
            rbac = ["admin", "developer"]
        else:
            epic_name = "Aucun cycle actif"
            feature = None
            stories = []
            persona = "—"
            rbac = []
    elif subtab == "skills" or subtab == "ac-panel-skills":
        epic_name = "Skills Improvement"
        feature = {"name": "Eval coverage", "status": "ongoing"}
        stories = [
            {"title": "Skills avec evals ≥ 80%", "status": "active"},
            {"title": "Skills manquants à créer", "status": "pending"},
        ]
        persona = "Sophia Renard (Knowledge Lead)"
        rbac = ["admin", "developer", "viewer"]
    elif subtab == "thompson" or subtab == "ac-panel-thompson":
        epic_name = "Thompson Sampling — Skill Variants"
        feature = {"name": "Beta distribution selection", "status": "running"}
        stories = [
            {"title": "Variant A/B skill selection", "status": "active"},
            {"title": "Bayesian reward update", "status": "active"},
        ]
        persona = "Karim Benchekroun (ML Lead)"
        rbac = ["admin", "developer"]
    elif subtab == "darwin" or subtab == "ac-panel-darwin":
        epic_name = "Darwin Teams — GA Evolution"
        feature = {"name": "Fitness GA", "status": "running"}
        stories = [
            {"title": "Team fitness scoring", "status": "active"},
            {"title": "Natural selection + crossover", "status": "active"},
        ]
        persona = "Thomas Dubois (ART Lead)"
        rbac = ["admin", "project_manager"]
    elif subtab == "evolution" or subtab == "ac-panel-evolution":
        epic_name = "Evolution nocturne — GA + RL"
        feature = {"name": "Orchestration évolutive", "status": "scheduled"}
        stories = [
            {"title": "GA orchestration nocturne", "status": "active"},
            {"title": "RL reward propagation", "status": "active"},
        ]
        persona = "Orchestrateur Évolution"
        rbac = ["admin"]
    elif subtab == "rl" or subtab == "ac-panel-rl":
        epic_name = "RL Reward — Politique d'apprentissage"
        feature = {
            "name": f"Score moy. {active['total_score_avg']:.0f}/100"
            if active
            else "RL policy",
            "status": "active",
        }
        stories = [
            {
                "title": "Reward R = f(qualité, adversarial, traceability)",
                "status": "active",
            },
        ]
        persona = "Arnaud Delacroix (Cost Lead)"
        rbac = ["admin", "developer"]
    else:
        epic_name = f"Amélioration Continue — {subtab}"
        feature = None
        stories = []
        persona = "—"
        rbac = ["admin"]

    return JSONResponse(
        {
            "programme": programme,
            "programme_sub": programme_sub,
            "epic": {"name": epic_name},
            "feature": feature,
            "user_stories": stories,
            "persona": persona,
            "rbac_roles": rbac,
            "slug": f"/art#amelio/{subtab}",
        }
    )


@router.get("/toolbox", response_class=HTMLResponse)
async def toolbox_page(request: Request, tab: str = "skills"):
    """Toolbox — Skills + Memory + MCPs in tabs."""
    return _templates(request).TemplateResponse(
        "toolbox.html",
        {
            "request": request,
            "page_title": "Toolbox",
            "active_tab": tab,
            "tab_content": "",
        },
    )


@router.get("/bricks", response_class=HTMLResponse)
async def bricks_page(request: Request, project_id: str = ""):
    """Bricks — infrastructure modulaire par projet."""
    from ...tools.bricks import get_brick_registry
    from ...tools.brick_loader import load_project_brick_config

    registry = get_brick_registry()
    all_bricks = registry.list_bricks()

    # Build brick cards: show all bricks, highlight active ones for the project
    project_config: dict = {}
    if project_id:
        project_config = load_project_brick_config(project_id)

    bricks_data = []
    for b in all_bricks:
        active = b.id in project_config
        cfg = project_config.get(b.id, {})
        skill = b.skill()
        bricks_data.append({
            "id": b.id,
            "version": b.version,
            "capabilities": b.capabilities,
            "active": active,
            "config": cfg,
            "skill_name": skill.name if skill else None,
            "skill_tools": skill.tools if skill else [],
            "skill_patterns": [{"name": p.name, "description": p.description} for p in (skill.patterns if skill else [])],
            "tool_schemas_count": len(b.tool_schemas()),
            "has_skill": skill is not None,
        })

    # Get available projects for the selector
    projects = []
    try:
        from ...projects.manager import get_project_store
        projects = [{"id": p.id, "name": p.name} for p in get_project_store().list()]
    except Exception:
        pass

    return _templates(request).TemplateResponse(
        "bricks.html",
        {
            "request": request,
            "page_title": "Tool Bricks",
            "bricks": bricks_data,
            "project_id": project_id,
            "projects": projects,
            "total": len(all_bricks),
            "active_count": sum(1 for b in bricks_data if b["active"]),
        },
    )


@router.get("/api/bricks", response_class=JSONResponse)
async def api_bricks_list(project_id: str = ""):
    """Return all bricks with their active status for a project."""
    from ...tools.bricks import get_brick_registry
    from ...tools.brick_loader import load_project_brick_config

    registry = get_brick_registry()
    project_config = load_project_brick_config(project_id) if project_id else {}

    result = []
    for b in registry.list_bricks():
        skill = b.skill()
        result.append({
            "id": b.id,
            "version": b.version,
            "capabilities": b.capabilities,
            "active": b.id in project_config,
            "tool_schemas_count": len(b.tool_schemas()),
            "has_skill": skill is not None,
            "skill_name": skill.name if skill else None,
            "skill_patterns": len(skill.patterns) if skill else 0,
        })
    return JSONResponse({"bricks": result, "project_id": project_id})


@router.get("/api/bricks/skill-ac")
async def api_bricks_skill_ac():
    """Run Skill AC (Layer 2 quality + Layer 3 trigger routing) on all registered bricks."""
    from ...ac.skill_eval import run_all_skills_ac, skill_ac_summary
    results = run_all_skills_ac()
    summary = skill_ac_summary(results)
    return JSONResponse({"summary": summary, "results": {k: v.to_dict() for k, v in results.items()}})


@router.get("/api/bricks/{project_id}/health")
async def api_bricks_health(project_id: str):
    """Run health checks for all bricks declared in a project."""
    from ...tools.brick_loader import health_check_project_bricks
    results = await health_check_project_bricks(project_id)
    all_ok = all(r["ok"] for r in results.values())
    return JSONResponse({"ok": all_ok, "project_id": project_id, "bricks": results})


@router.get("/api/bricks/{project_id}/skills")
async def api_bricks_skills(project_id: str):
    """Return the combined brick skills prompt for a project."""
    from ...tools.brick_loader import get_project_brick_skills_prompt
    prompt = get_project_brick_skills_prompt(project_id)
    return JSONResponse({"project_id": project_id, "skills_prompt": prompt, "length": len(prompt)})


@router.get("/api/bricks/ac")
async def api_bricks_ac(project_id: str = ""):
    """Run AC (Acceptance Criteria) checks on all registered bricks."""
    from ...ac.brick_eval import run_all_bricks_ac, ac_summary
    results = run_all_bricks_ac(project_id=project_id or None, sandbox=True)
    summary = ac_summary(results)
    return JSONResponse(summary)


@router.get("/design-system", response_class=HTMLResponse)
async def design_system_page(request: Request):
    """Design System — tokens, colors, icons, atoms, molecules, patterns."""
    import re

    # Extract icon names from SVG sprites
    sprites_path = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "partials"
        / "svg_sprites.html"
    )
    icons = []
    if sprites_path.exists():
        text = sprites_path.read_text()
        icons = re.findall(r'id="icon-([^"]+)"', text)
    return _templates(request).TemplateResponse(
        "design_system.html",
        {
            "request": request,
            "page_title": "Design System",
            "icons": icons,
        },
    )


@router.post("/api/strategic-committee/launch", dependencies=[Depends(require_auth())])
async def launch_strategic_committee(request: Request):
    """Launch a strategic committee session from the portfolio page."""
    from ...sessions.store import MessageDef, SessionDef, get_session_store
    from ...workflows.store import get_workflow_store

    wf_store = get_workflow_store()
    wf = wf_store.get("strategic-committee")
    if not wf:
        return JSONResponse(
            {"error": "Workflow 'strategic-committee' not found"}, status_code=404
        )

    session_store = get_session_store()
    session = SessionDef(
        name="Comité Stratégique",
        goal="Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO",
        status="active",
        config={"workflow_id": "strategic-committee"},
    )
    session = session_store.create(session)
    session_store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content="Comité Stratégique lancé. Les agents du comité vont débattre des priorités portfolio.",
        )
    )

    # Auto-start workflow — agents debate autonomously
    from .workflows import _run_workflow_background

    _keep_task(
        asyncio.create_task(
            _run_workflow_background(
                wf,
                session.id,
                "Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO sur les projets en cours",
                "",
            )
        )
    )

    return JSONResponse({"session_id": session.id})


# ── Memory ───────────────────────────────────────────────────────


@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    """Memory dashboard."""
    from ...memory.manager import get_memory_manager
    from ...projects.manager import get_project_store

    mem = get_memory_manager()
    stats = mem.stats()
    recent_global = mem.global_get(limit=20)

    # Project memories grouped by project
    project_store = get_project_store()
    projects = project_store.list_all()
    project_memories = []
    for p in projects:
        entries = mem.project_get(p.id, limit=10)
        if entries:
            project_memories.append(
                {
                    "project_id": p.id,
                    "project_name": p.name,
                    "entries": entries,
                    "count": len(entries),
                }
            )

    return _templates(request).TemplateResponse(
        "memory.html",
        {
            "request": request,
            "page_title": "Memory",
            "stats": stats,
            "recent_global": recent_global,
            "project_memories": project_memories,
        },
    )


# ── Monitoring / Settings ────────────────────────────────────────


@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    from starlette.responses import RedirectResponse

    return RedirectResponse("/metrics?tab=monitoring", status_code=302)


@router.get("/ops", response_class=HTMLResponse)
async def ops_page(request: Request):
    """Redirect to Metrics Ops tab."""
    from starlette.responses import RedirectResponse

    return RedirectResponse("/metrics?tab=ops", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    import json as _json
    import os
    import socket

    from ...config import get_config
    from ...db.adapter import is_postgresql
    from ...db.migrations import get_db
    from ...llm.providers import list_providers

    cfg = get_config()
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM integrations ORDER BY category, name"
        ).fetchall()
        integrations = []
        for r in rows:
            d = dict(r)
            d["config"] = _json.loads(d.get("config_json") or "{}")
            d["agent_roles"] = _json.loads(d.get("agent_roles") or "[]")
            integrations.append(d)
    except Exception:
        integrations = []
    finally:
        db.close()

    # Distributed infra status (read-only, shown in General tab)
    infra = {
        "db_type": "postgresql" if is_postgresql() else "sqlite",
        "redis_url": os.environ.get("REDIS_URL") or "",
        "node_id": os.environ.get("SF_NODE_ID")
        or os.environ.get("HOSTNAME")
        or socket.gethostname(),
        "drain_timeout": int(os.environ.get("SF_DRAIN_TIMEOUT_S", "30")),
        "pg_dsn": (os.environ.get("PG_DSN") or "")[:40]
        + ("…" if len(os.environ.get("PG_DSN", "")) > 40 else ""),
        "infisical": bool(os.environ.get("INFISICAL_TOKEN")),
    }

    return _templates(request).TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "Settings",
            "config": cfg,
            "providers": list_providers(),
            "integrations": integrations,
            "infra": infra,
        },
    )


@router.post("/api/settings/orchestrator", dependencies=[Depends(require_auth())])
async def save_orchestrator_settings(request: Request):
    """Save mission concurrency + backpressure + worker_nodes settings and apply them live."""
    from ...config import get_config, save_config
    from .helpers import get_mission_semaphore

    body = await request.json()
    cfg = get_config()
    oc = cfg.orchestrator

    if "mission_semaphore" in body:
        oc.mission_semaphore = max(1, min(10, int(body["mission_semaphore"])))
    if "resume_stagger_startup" in body:
        oc.resume_stagger_startup = max(1.0, float(body["resume_stagger_startup"]))
    if "resume_stagger_watchdog" in body:
        oc.resume_stagger_watchdog = max(1.0, float(body["resume_stagger_watchdog"]))
    if "resume_batch_startup" in body:
        oc.resume_batch_startup = max(1, min(20, int(body["resume_batch_startup"])))
    if "cpu_green" in body:
        oc.cpu_green = max(10.0, min(60.0, float(body["cpu_green"])))
    if "cpu_yellow" in body:
        oc.cpu_yellow = max(oc.cpu_green + 5, min(80.0, float(body["cpu_yellow"])))
    if "cpu_red" in body:
        oc.cpu_red = max(oc.cpu_yellow + 5, min(95.0, float(body["cpu_red"])))
    if "ram_red" in body:
        oc.ram_red = max(50.0, min(95.0, float(body["ram_red"])))
    if "max_active_projects" in body:
        oc.max_active_projects = max(0, min(20, int(body["max_active_projects"])))
    if "deployed_container_ttl_hours" in body:
        oc.deployed_container_ttl_hours = max(
            0.0, min(168.0, float(body["deployed_container_ttl_hours"]))
        )
    if "worker_nodes" in body:
        raw = body["worker_nodes"]
        if isinstance(raw, list):
            oc.worker_nodes = [u.strip() for u in raw if u.strip()]
        elif isinstance(raw, str):
            oc.worker_nodes = [u.strip() for u in raw.splitlines() if u.strip()]
    if "yolo_mode" in body:
        oc.yolo_mode = bool(body["yolo_mode"])

    save_config(cfg)
    # Apply semaphore change live
    get_mission_semaphore()

    # Append live system metrics to response
    try:
        import psutil

        _cpu_now = psutil.cpu_percent(interval=0.5)
        _ram = psutil.virtual_memory()
        _ram_now = _ram.percent
        _ram_total_gb = round(_ram.total / 1024**3, 1)
        _ram_used_gb = round(_ram.used / 1024**3, 1)
    except Exception:
        _cpu_now = _ram_now = _ram_total_gb = _ram_used_gb = 0

    return {
        "ok": True,
        "mission_semaphore": oc.mission_semaphore,
        "resume_stagger_startup": oc.resume_stagger_startup,
        "resume_stagger_watchdog": oc.resume_stagger_watchdog,
        "resume_batch_startup": oc.resume_batch_startup,
        "cpu_green": oc.cpu_green,
        "cpu_yellow": oc.cpu_yellow,
        "cpu_red": oc.cpu_red,
        "ram_red": oc.ram_red,
        "max_active_projects": oc.max_active_projects,
        "deployed_container_ttl_hours": oc.deployed_container_ttl_hours,
        "worker_nodes": oc.worker_nodes,
        "yolo_mode": oc.yolo_mode,
        "cpu_now": _cpu_now,
        "ram_now": _ram_now,
        "ram_total_gb": _ram_total_gb,
        "ram_used_gb": _ram_used_gb,
    }


@router.get("/api/settings/security")
async def get_security_settings():
    """Return current security settings + Landlock status."""
    import os as _os

    from ...config import get_config
    from ...tools.sandbox import _LANDLOCK_DEFAULT, _LANDLOCK_PATH, _landlock_enabled

    cfg = get_config()
    binary_exists = bool(_LANDLOCK_PATH) and _os.path.isfile(_LANDLOCK_PATH)
    binary_path = _LANDLOCK_PATH or _LANDLOCK_DEFAULT
    return {
        "landlock_enabled": cfg.security.landlock_enabled,
        "landlock_active": _landlock_enabled(),
        "landlock_binary_found": binary_exists,
        "landlock_binary_path": binary_path,
        "sandbox_enabled": _os.environ.get("SANDBOX_ENABLED", "false").lower()
        in ("true", "1", "yes"),
    }


@router.post("/api/settings/security", dependencies=[Depends(require_auth())])
async def save_security_settings(request: Request):
    """Toggle security settings (Landlock, etc.)."""
    from ...config import get_config, save_config

    body = await request.json()
    cfg = get_config()
    if "landlock_enabled" in body:
        cfg.security.landlock_enabled = bool(body["landlock_enabled"])
    save_config(cfg)
    return {"ok": True, "landlock_enabled": cfg.security.landlock_enabled}


# ── Admin Users ──────────────────────────────────────────────────


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Admin page for user management (CRUD) — kept for backward compat."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/rbac", status_code=302)


@router.get("/rbac", response_class=HTMLResponse)
async def rbac_page(request: Request):
    """RBAC — Users, Roles & Permissions management page."""
    from ...auth import service as auth_svc

    try:
        users = auth_svc.list_users()
        user_list = [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "avatar": u.avatar,
                "is_active": u.is_active,
                "auth_provider": u.auth_provider,
                "last_login": u.last_login,
                "created_at": u.created_at,
            }
            for u in users
        ]
    except Exception:
        user_list = []
    return _templates(request).TemplateResponse(
        "rbac.html",
        {"request": request, "page_title": "Users & Roles", "users": user_list},
    )


# ── Vue Métier ───────────────────────────────────────────────────


@router.get("/metier", response_class=HTMLResponse)
async def metier_page(request: Request):
    """Vue Métier — SAFe / LEAN product-centric live dashboard."""
    from datetime import timedelta

    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_run_store
    from ...sessions.store import get_session_store
    from ...workflows.store import get_workflow_store

    wf_store = get_workflow_store()
    session_store = get_session_store()
    agent_store = get_agent_store()
    epic_store = get_epic_run_store()

    all_missions = epic_store.list_runs(limit=500)
    all_sessions = session_store.list_all(limit=200)
    all_agents = agent_store.list_all()
    all_workflows = wf_store.list_all()

    # helper to normalize enum → string
    def _s(val):
        return val.value if hasattr(val, "value") else str(val) if val else "pending"

    # ── Epics Pipeline (missions as value items) — separated by Value Stream ──
    epics = []
    tma_missions: list[dict] = []
    security_missions: list[dict] = []
    rse_missions: list[dict] = []
    for m in all_missions:
        phases_total = len(m.phases) if m.phases else 0
        phases_done = sum(
            1 for p in (m.phases or []) if _s(p.status) in ("done", "done_with_issues")
        )
        phases_running = sum(1 for p in (m.phases or []) if _s(p.status) == "running")
        progress = int(phases_done / phases_total * 100) if phases_total else 0

        phase_nodes = []
        for p in m.phases or []:
            phase_nodes.append(
                {
                    "id": p.phase_id,
                    "name": p.phase_name or p.phase_id,
                    "pattern": p.pattern_id or "solo",
                    "status": _s(p.status),
                }
            )

        # Compute lead time
        lead_time_h = None
        if m.created_at:
            end = m.completed_at or datetime.utcnow()
            if isinstance(m.created_at, str):
                try:
                    start = datetime.fromisoformat(
                        m.created_at.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    start = datetime.utcnow()
            else:
                start = (
                    m.created_at.replace(tzinfo=None)
                    if hasattr(m.created_at, "replace")
                    else m.created_at
                )
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end.replace("Z", "+00:00")).replace(
                        tzinfo=None
                    )
                except Exception:
                    end = datetime.utcnow()
            elif hasattr(end, "replace"):
                end = end.replace(tzinfo=None)
            lead_time_h = round((end - start).total_seconds() / 3600, 1)

        _TMA_WF = {"tma-maintenance", "tma-autoheal", "dsi-platform-tma"}
        _SEC_WF = {"security-hacking"}
        _RSE_WF = {"rse-compliance"}
        wf_id = m.workflow_id or ""
        entry = {
            "id": m.id,
            "name": m.workflow_name or m.workflow_id or "Mission",
            "brief": (m.brief or "")[:120],
            "status": _s(m.status),
            "current_phase": m.current_phase or "",
            "progress": progress,
            "phases_done": phases_done,
            "phases_total": phases_total,
            "phases_running": phases_running,
            "phase_nodes": phase_nodes,
            "lead_time_h": lead_time_h,
            "session_id": m.session_id or "",
            "workflow_id": wf_id,
            "project_id": m.project_id or "",
        }
        if wf_id in _TMA_WF:
            tma_missions.append(entry)
        elif wf_id in _SEC_WF:
            security_missions.append(entry)
        elif wf_id in _RSE_WF:
            rse_missions.append(entry)
        else:
            epics.append(entry)

    # ── Flow Metrics (LEAN) ──
    all_vs = epics + tma_missions + security_missions + rse_missions
    wip = sum(1 for e in all_vs if e["status"] == "running")
    completed = sum(1 for e in all_vs if e["status"] in ("completed", "done"))
    failed = sum(1 for e in all_vs if e["status"] == "failed")
    total = len(all_vs)
    throughput_pct = int(completed / total * 100) if total else 0

    lead_times = [
        e["lead_time_h"]
        for e in all_vs
        if e["lead_time_h"] is not None and e["status"] in ("completed", "done")
    ]
    avg_lead_time = round(sum(lead_times) / len(lead_times), 1) if lead_times else 0

    # ── Agent Velocity (top contributors by message count) ──
    agent_map = {a.id: a for a in all_agents}
    agent_msg_counts: dict[str, int] = {}
    for s in all_sessions[:30]:
        try:
            msgs = session_store.get_messages(s.id, limit=500)
            for msg in msgs:
                if msg.from_agent and msg.from_agent != "user":
                    agent_msg_counts[msg.from_agent] = (
                        agent_msg_counts.get(msg.from_agent, 0) + 1
                    )
        except Exception:
            pass
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
    top_agents = sorted(agent_msg_counts.items(), key=lambda x: -x[1])[:8]
    max_msgs = top_agents[0][1] if top_agents else 1
    agent_velocity = []
    for aid, count in top_agents:
        a = agent_map.get(aid)
        jpg = avatar_dir / f"{aid}.jpg"
        svg_f = avatar_dir / f"{aid}.svg"
        avatar_url = (
            f"/static/avatars/{aid}.jpg"
            if jpg.exists()
            else (
                f"/static/avatars/{aid}.svg"
                if svg_f.exists()
                else f"https://i.pravatar.cc/150?u={aid}"
            )
        )
        agent_velocity.append(
            {
                "id": aid,
                "name": a.name if a else aid,
                "role": (a.role if a else "")[:30],
                "count": count,
                "pct": int(count / max_msgs * 100),
                "avatar": a.avatar if a else "",
                "avatar_url": avatar_url,
            }
        )

    # ── Activity Heatmap (real message timestamps, last 28 days) ──
    now = datetime.utcnow()
    day_counts: dict[int, int] = dict.fromkeys(range(28), 0)
    for s in all_sessions[:50]:
        try:
            msgs = session_store.get_messages(s.id, limit=200)
            for msg in msgs:
                if msg.timestamp:
                    ts = msg.timestamp
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(
                                ts.replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                        except Exception:
                            continue
                    delta = (now - ts).days
                    if 0 <= delta < 28:
                        day_counts[delta] = day_counts.get(delta, 0) + 1
        except Exception:
            pass

    max_day_count = max(day_counts.values()) if day_counts else 1
    calendar_days = []
    for i in range(27, -1, -1):
        day_date = now - timedelta(days=i)
        count = day_counts.get(i, 0)
        if max_day_count > 0:
            level = min(4, int(count / max(max_day_count, 1) * 5))
        else:
            level = 0
        calendar_days.append({"num": day_date.day, "level": level, "count": count})

    # ── Workflow catalog ──
    workflows = []
    for wf in all_workflows:
        mission_count = sum(1 for m in all_missions if m.workflow_id == wf.id)
        workflows.append(
            {
                "id": wf.id,
                "name": wf.name,
                "phases_count": len(wf.phases) if wf.phases else 0,
                "mission_count": mission_count,
                "icon": getattr(wf, "icon", ""),
            }
        )

    return _templates(request).TemplateResponse(
        "metier.html",
        {
            "request": request,
            "page_title": "Vue Métier",
            "epics": epics,
            "tma_missions": tma_missions,
            "security_missions": security_missions,
            "rse_missions": rse_missions,
            "wip": wip,
            "completed": completed,
            "failed": failed,
            "total": total,
            "throughput_pct": throughput_pct,
            "avg_lead_time": avg_lead_time,
            "agent_velocity": agent_velocity,
            "calendar_days": calendar_days,
            "workflows": workflows,
            "agents_total": len(all_agents),
        },
    )


# ── Product Line Manager ─────────────────────────────────────────


@router.get("/product-line", response_class=HTMLResponse)
async def product_line_page(request: Request):
    """Product Line Manager — produits, roadmap, milestones, DORA."""
    from ...metrics.dora import get_dora_metrics
    from ...missions.product import get_product_backlog
    from ...epics.store import get_epic_run_store, get_epic_store
    from ...projects.manager import LEAN_VALUES, get_project_store

    project_store = get_project_store()
    epic_store = get_epic_store()
    run_store = get_epic_run_store()
    backlog = get_product_backlog()
    dora_engine = get_dora_metrics()

    all_projects = project_store.list_all()
    all_missions = epic_store.list_missions()
    all_runs = run_store.list_runs(limit=200)

    # Group missions by project
    missions_by_project: dict[str, list] = {}
    for m in all_missions:
        pid = m.project_id or "default"
        missions_by_project.setdefault(pid, []).append(m)

    # Group epic_runs by project
    runs_by_project: dict[str, list] = {}
    for r in all_runs:
        pid = r.project_id or "default"
        runs_by_project.setdefault(pid, []).append(r)

    # Build product data
    products = []
    total_epics = 0
    total_features = 0
    total_stories = 0
    total_done_stories = 0

    for proj in all_projects:
        proj_missions = missions_by_project.get(proj.id, [])
        proj_runs = runs_by_project.get(proj.id, [])
        epics_data = []
        proj_features = 0
        proj_stories = 0
        proj_done = 0
        proj_points = 0

        for m in proj_missions:
            features = backlog.list_features(m.id)
            feat_count = len(features)
            story_count = 0
            done_count = 0
            ep_points = 0

            for f in features:
                stories = backlog.list_stories(f.id)
                f_pts = f.story_points or sum(s.story_points for s in stories)
                ep_points += f_pts
                story_count += len(stories)
                done_count += sum(1 for s in stories if s.status == "done")

            proj_features += feat_count
            proj_stories += story_count
            proj_done += done_count
            proj_points += ep_points

            epics_data.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status.value
                    if hasattr(m.status, "value")
                    else str(m.status),
                    "feature_count": feat_count,
                    "story_count": story_count,
                    "done_pct": round(done_count / max(story_count, 1) * 100),
                }
            )

        # Also include epic_runs as epics
        for r in proj_runs:
            epic_name = r.brief.split(" - ")[0] if " - " in r.brief else r.brief[:50]
            done_phases = (
                sum(1 for p in r.phases if p.status.value == "done") if r.phases else 0
            )
            total_phases = len(r.phases) if r.phases else 0
            epics_data.append(
                {
                    "id": r.id,
                    "name": epic_name,
                    "status": r.status.value
                    if hasattr(r.status, "value")
                    else str(r.status),
                    "feature_count": total_phases,
                    "story_count": total_phases,
                    "done_pct": round(done_phases / max(total_phases, 1) * 100),
                    "is_run": True,
                }
            )

        run_epic_count = len(proj_runs)
        total_epics += len(proj_missions) + run_epic_count
        total_features += proj_features
        total_stories += proj_stories
        total_done_stories += proj_done

        # Milestones: derive from epic status progression
        milestones = []
        if proj_missions:
            completed = sum(1 for e in epics_data if e["status"] == "completed")
            _running = sum(1 for e in epics_data if e["status"] == "running")
            total_ep = len(epics_data)

            milestones.append(
                {
                    "name": "Kickoff",
                    "date": "",
                    "pct": 100,
                    "state": "done",
                }
            )
            if proj_features > 0:
                feat_pct = min(100, round(proj_done / max(proj_stories, 1) * 100))
                milestones.append(
                    {
                        "name": f"Développement ({proj_features} features)",
                        "date": "",
                        "pct": feat_pct,
                        "state": "done"
                        if feat_pct == 100
                        else ("active" if feat_pct > 0 else "upcoming"),
                    }
                )
            if total_ep > 0:
                deploy_pct = round(completed / total_ep * 100)
                milestones.append(
                    {
                        "name": f"Déploiement ({completed}/{total_ep} epics)",
                        "date": "",
                        "pct": deploy_pct,
                        "state": "done"
                        if deploy_pct == 100
                        else ("active" if deploy_pct > 0 else "upcoming"),
                    }
                )
            milestones.append(
                {
                    "name": "Production",
                    "date": "",
                    "pct": 100
                    if all(e["status"] == "completed" for e in epics_data)
                    else 0,
                    "state": "done"
                    if all(e["status"] == "completed" for e in epics_data)
                    else "upcoming",
                }
            )

        # Per-product DORA
        proj_dora = None
        try:
            proj_dora = dora_engine.summary(proj.id, 30)
        except Exception:
            pass

        # Project values
        proj_values = []
        for vid in proj.values or []:
            for lv in LEAN_VALUES:
                if lv["id"] == vid:
                    proj_values.append(lv)
                    break

        products.append(
            {
                "id": proj.id,
                "name": proj.name,
                "description": proj.description,
                "status": proj.status,
                "epics": epics_data,
                "feature_count": proj_features,
                "total_points": proj_points,
                "done_pct": round(proj_done / max(proj_stories, 1) * 100),
                "milestones": milestones,
                "dora": proj_dora,
                "values": proj_values,
            }
        )

    # Overall DORA
    overall_dora = dora_engine.summary("", 30)
    overall_done = round(total_done_stories / max(total_stories, 1) * 100)

    # Global values (union of all project values)
    all_value_ids = set()
    for p in products:
        all_value_ids.update(v["id"] for v in p.get("values", []))
    global_values = (
        [lv for lv in LEAN_VALUES if lv["id"] in all_value_ids]
        if all_value_ids
        else LEAN_VALUES[:4]
    )

    return _templates(request).TemplateResponse(
        "product_line.html",
        {
            "request": request,
            "page_title": "Ligne de Produit",
            "products": products,
            "total_epics": total_epics,
            "total_features": total_features,
            "total_stories": total_stories,
            "overall_done_pct": overall_done,
            "dora": overall_dora,
            "values": global_values,
        },
    )


# ── Product Management ───────────────────────────────────────────


@router.get("/product", response_class=HTMLResponse)
async def product_page(request: Request):
    """Product backlog — Epic → Feature → User Story hierarchy."""
    from ...missions.product import get_product_backlog
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store

    epic_store = get_epic_store()
    backlog = get_product_backlog()
    project_store = get_project_store()

    all_projects = project_store.list_all()
    all_missions = epic_store.list_missions()
    filter_project = request.query_params.get("project", "")

    if filter_project:
        all_missions = [m for m in all_missions if m.project_id == filter_project]

    project_names = {p.id: p.name for p in all_projects}

    # Load feature dependencies
    from ...db.migrations import get_db as _gdb

    _db = _gdb()
    try:
        dep_rows = _db.execute(
            "SELECT feature_id, depends_on, dep_type FROM feature_deps"
        ).fetchall()
        # Build lookup: feature_id → list of deps
        deps_map = {}
        for r in dep_rows:
            deps_map.setdefault(r["feature_id"], []).append(
                {"depends_on": r["depends_on"], "dep_type": r["dep_type"]}
            )
        # Reverse lookup: who depends on me
        blocked_by_map = {}
        for r in dep_rows:
            blocked_by_map.setdefault(r["depends_on"], []).append(r["feature_id"])
        # Persona name lookup
        persona_names = {}
        try:
            persona_rows = _db.execute("SELECT id, name FROM personas").fetchall()
            persona_names = {r["id"]: r["name"] for r in persona_rows}
        except Exception:
            pass
    finally:
        _db.close()

    # Build epic → features → stories tree
    epics = []
    total_features = 0
    total_stories = 0
    total_points = 0
    total_done_stories = 0

    for m in all_missions:
        features = backlog.list_features(m.id)
        epic_features = []
        epic_points = 0
        epic_stories = 0
        epic_done = 0

        for f in features:
            stories = backlog.list_stories(f.id)
            f_points = f.story_points or sum(s.story_points for s in stories)
            epic_points += f_points
            epic_stories += len(stories)
            epic_done += sum(1 for s in stories if s.status == "done")
            total_stories += len(stories)
            total_points += f_points

            epic_features.append(
                {
                    "id": f.id,
                    "name": f.name,
                    "status": f.status,
                    "story_points": f_points,
                    "assigned_to": f.assigned_to,
                    "acceptance_criteria": f.acceptance_criteria or "",
                    "description": f.description or "",
                    "user_story": f.user_story or "",
                    "persona_id": persona_names.get(f.persona_id, f.persona_id) if f.persona_id else "",
                    "deps": deps_map.get(f.id, []),
                    "depended_by": blocked_by_map.get(f.id, []),
                    "stories": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "status": s.status,
                            "story_points": s.story_points,
                            "priority": s.priority,
                        }
                        for s in stories
                    ],
                }
            )

        total_features += len(features)
        total_done_stories += epic_done

        epics.append(
            {
                "id": m.id,
                "name": m.name,
                "status": m.status,
                "project_id": m.project_id,
                "project_name": project_names.get(m.project_id, m.project_id),
                "wsjf_score": getattr(m, "wsjf_score", 0) or 0,
                "business_value": getattr(m, "business_value", 0) or 0,
                "time_criticality": getattr(m, "time_criticality", 0) or 0,
                "risk_reduction": getattr(m, "risk_reduction", 0) or 0,
                "job_duration": getattr(m, "job_duration", 1) or 1,
                "features": epic_features,
                "total_points": epic_points,
                "total_stories": epic_stories,
                "done_pct": round(epic_done / max(epic_stories, 1) * 100),
            }
        )

    done_pct = round(total_done_stories / max(total_stories, 1) * 100)

    return _templates(request).TemplateResponse(
        "product.html",
        {
            "request": request,
            "page_title": "Product",
            "epics": epics,
            "projects": all_projects,
            "filter_project": filter_project,
            "summary": {
                "epics": len(epics),
                "features": total_features,
                "stories": total_stories,
                "total_points": total_points,
                "done_pct": done_pct,
            },
        },
    )


@router.get("/manifest.json")
async def manifest_json():
    """Serve PWA manifest."""
    from pathlib import Path as _Path
    from fastapi.responses import FileResponse

    manifest_path = _Path(__file__).parent.parent / "static" / "manifest.json"
    return FileResponse(str(manifest_path), media_type="application/manifest+json")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics dashboard — redirects to unified Metrics page."""
    from starlette.responses import RedirectResponse

    return RedirectResponse("/metrics?tab=analytics", status_code=302)


# ── Annotation Studio ─────────────────────────────────────────────


def _get_deploy_url(project_id: str) -> str:
    """Try to find deployed URL for a project."""
    import json as _json

    try:
        from ...db.migrations import get_db

        db = get_db()
        for table in ("projects", "project_missions"):
            try:
                row = db.execute(
                    f"SELECT config_json FROM {table} WHERE id=?", (project_id,)
                ).fetchone()
                if row:
                    cfg = _json.loads(row["config_json"] or "{}")
                    url = cfg.get("deploy_url") or cfg.get("result_deploy_url", "")
                    if url:
                        return url
            except Exception:
                pass
    except Exception:
        pass
    return ""


@router.get("/annotate/{project_id}", response_class=HTMLResponse)
async def annotation_studio(project_id: str, request: Request):
    """Annotation Studio — standalone business-user page."""
    templates = _templates(request)
    try:
        from ...projects.manager import get_project_store

        proj = get_project_store().get(project_id)
    except Exception:
        proj = None

    deploy_url = _get_deploy_url(project_id)

    return templates.TemplateResponse(
        "annotate.html",
        {
            "request": request,
            "project_id": project_id,
            "project_name": proj.name if proj else project_id,
            "deploy_url": deploy_url,
            "has_live": bool(deploy_url),
        },
    )


@router.api_route(
    "/annotate/{project_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def annotation_proxy(project_id: str, path: str, request: Request):
    """HTTP proxy that injects annotation overlay script into the project's deployed app."""
    import httpx
    from fastapi.responses import Response as FResponse

    try:
        deploy_url = _get_deploy_url(project_id)
        if not deploy_url:
            return HTMLResponse(
                "<h1>No deployed URL for this project</h1>", status_code=404
            )

        target = deploy_url.rstrip("/") + "/" + path
        qs = str(request.url.query)
        if qs:
            target += "?" + qs

        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("Host", None)

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=await request.body(),
            )

        # Inject annotation script into HTML responses
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            html = resp.text
            inject = (
                f'<script>window.SF_ANNOTATE={{projectId:"{project_id}",proxyBase:"/annotate/{project_id}/proxy",apiBase:"/api/projects/{project_id}"}};</script>'
                '<link rel="stylesheet" href="/static/sf-annotate.css">'
                '<script src="/static/sf-annotate.js" defer></script>'
            )
            if "<head>" in html:
                html = html.replace("<head>", "<head>" + inject, 1)
            else:
                html = inject + html

            # Rewrite absolute URLs to go through proxy
            html = html.replace('href="/', f'href="/annotate/{project_id}/proxy/')
            html = html.replace('src="/', f'src="/annotate/{project_id}/proxy/')
            html = html.replace("href='/", f"href='/annotate/{project_id}/proxy/")
            html = html.replace("src='/", f"src='/annotate/{project_id}/proxy/")

            resp_headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower()
                not in (
                    "x-frame-options",
                    "content-security-policy",
                    "content-length",
                    "transfer-encoding",
                    "content-encoding",
                )
            }
            return HTMLResponse(
                content=html, status_code=resp.status_code, headers=resp_headers
            )

        # Pass through non-HTML responses
        resp_headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower()
            not in (
                "x-frame-options",
                "content-security-policy",
                "transfer-encoding",
            )
        }
        return FResponse(
            content=resp.content,
            status_code=resp.status_code,
            media_type=content_type,
            headers=resp_headers,
        )
    except Exception as e:
        logger.error(f"Annotation proxy error: {e}")
        return HTMLResponse(f"<h1>Proxy error: {e}</h1>", status_code=502)
