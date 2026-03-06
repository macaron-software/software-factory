"""Web routes — Page renders (portfolio, backlog, workflows, etc.)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)

from .helpers import (
    _active_mission_tasks,
    _templates,
)

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
    },
    {
        "id": "ac-hello-vue",
        "name": "Hello Vue.js",
        "tier": "simple-compile",
        "tier_label": "Simple + Compile",
        "tech": ["vue", "vite", "node"],
        "max_cycles": 20,
    },
    {
        "id": "ac-fullstack-rs",
        "name": "Fullstack Rust+Svelte",
        "tier": "medium",
        "tier_label": "Medium Fullstack",
        "tech": ["rust", "sveltekit", "postgres"],
        "max_cycles": 20,
    },
    {
        "id": "ac-docusign",
        "name": "DocuSign Clone",
        "tier": "complex",
        "tier_label": "Complex",
        "tech": ["react", "fastapi", "postgres"],
        "max_cycles": 20,
    },
    {
        "id": "ac-ecommerce",
        "name": "E-Commerce + Solaris",
        "tier": "enterprise",
        "tier_label": "Enterprise",
        "tech": ["nextjs", "solaris", "stripe", "pg"],
        "max_cycles": 20,
    },
    {
        "id": "ac-game-threejs",
        "name": "Jeu Three.js",
        "tier": "game-browser",
        "tier_label": "Jeu Simple",
        "tech": ["threejs", "js", "webgl"],
        "max_cycles": 20,
    },
    {
        "id": "ac-game-native",
        "name": "Jeu Natif Compilé",
        "tier": "game-compiled",
        "tier_label": "Jeu Compilé",
        "tech": ["rust", "sdl2", "opengl"],
        "max_cycles": 20,
    },
    {
        "id": "ac-migration-php",
        "name": "Migration PHP → FastAPI",
        "tier": "migration",
        "tier_label": "Migration",
        "tech": ["php", "fastapi", "postgres"],
        "max_cycles": 20,
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
        # Idempotent column additions
        for alter in [
            "ALTER TABLE ac_cycles ADD COLUMN adversarial_scores TEXT DEFAULT '{}'",
            "ALTER TABLE ac_cycles ADD COLUMN traceability_score INTEGER DEFAULT 0",
            "ALTER TABLE ac_cycles ADD COLUMN rl_reward REAL DEFAULT 0",
            "ALTER TABLE ac_cycles ADD COLUMN veto_count INTEGER DEFAULT 0",
            "ALTER TABLE ac_project_state ADD COLUMN next_cycle_hint TEXT",
            "ALTER TABLE ac_project_state ADD COLUMN skill_eval_pending TEXT",
            "ALTER TABLE ac_project_state ADD COLUMN convergence_status TEXT DEFAULT 'cold_start'",
        ]:
            try:
                conn.execute(alter)
            except Exception:
                pass
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
    """HTMX fragment: cycle table for a given project."""
    import json as _json

    def _load():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
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
        {"request": request, "cycles": cycles, "phases": _AC_PHASES},
    )


@router.post("/api/improvement/start/{project_id}")
async def api_improvement_start(project_id: str):
    """Launch an AC improvement cycle for a project via the platform workflow engine."""
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
    brief = (
        f"AC Amélioration Continue — {proj['name']} — Cycle {cycle_num}/20\n\n"
        f"Projet : {proj['id']}\nStack : {', '.join(proj['tech'])}\nTier : {proj['tier_label']}\n\n"
        f"Cycle {cycle_num}/20 : inception → TDD sprint → adversarial → QA → CI/CD → enregistrement.\n"
        f"Objectif : score > 80/100, 0 défauts critiques, traçabilité 100%.\n"
        f"Si cycle > 1 : lire ADVERSARIAL_{{N-1}}.md et CICD_FAILURE_{{N-1}}.md pour les corrections.\n"
        f"Workflow : ac-improvement-cycle"
    )

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
            config={"project_id": project_id, "cycle_num": cycle_num, "ac": True},
        )
        created = await asyncio.to_thread(store.create_mission, mission_def)
        run_id = str(created.id)

        # Update project state
        def _update_state():
            import time

            conn = _ac_get_db()
            try:
                conn.execute(
                    "INSERT INTO ac_project_state (project_id, current_cycle, status, current_run_id, updated_at)"
                    " VALUES (?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET"
                    " current_cycle=excluded.current_cycle, status=excluded.status,"
                    " current_run_id=excluded.current_run_id, updated_at=excluded.updated_at",
                    (
                        project_id,
                        cycle_num,
                        "running",
                        run_id,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ),
                )
            except Exception:
                pass
            conn.close()

        await asyncio.to_thread(_update_state)
        return JSONResponse(
            {"run_id": run_id, "cycle_num": cycle_num, "project_id": project_id}
        )

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/improvement/inject-cycle")
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
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write():
        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        try:
            conn.execute(
                "INSERT INTO ac_cycles (project_id, cycle_num, git_sha, status, phase_scores,"
                " total_score, defect_count, fix_summary, adversarial_scores, traceability_score,"
                " started_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(project_id, cycle_num) DO UPDATE SET"
                " git_sha=excluded.git_sha, status=excluded.status, phase_scores=excluded.phase_scores,"
                " total_score=excluded.total_score, defect_count=excluded.defect_count,"
                " fix_summary=excluded.fix_summary, adversarial_scores=excluded.adversarial_scores,"
                " traceability_score=excluded.traceability_score, completed_at=excluded.completed_at",
                (
                    project_id,
                    cycle_num,
                    git_sha,
                    status,
                    _json.dumps(phase_scores)
                    if isinstance(phase_scores, dict)
                    else phase_scores,
                    total_score,
                    defect_count,
                    fix_summary,
                    _json.dumps(adversarial_scores)
                    if isinstance(adversarial_scores, dict)
                    else adversarial_scores,
                    traceability_score,
                    now,
                    now,
                ),
            )
            # Update project state average score
            conn.execute(
                "INSERT INTO ac_project_state (project_id, current_cycle, status, total_score_avg,"
                " last_git_sha, ci_status, updated_at)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(project_id) DO UPDATE SET"
                " current_cycle=MAX(current_cycle, excluded.current_cycle),"
                " status=CASE WHEN excluded.status='completed' THEN 'idle' ELSE excluded.status END,"
                " last_git_sha=excluded.last_git_sha, ci_status=excluded.ci_status,"
                " total_score_avg=("
                "   SELECT AVG(total_score) FROM ac_cycles WHERE project_id=? AND total_score > 0"
                " ), updated_at=excluded.updated_at",
                (
                    project_id,
                    cycle_num,
                    status,
                    total_score,
                    git_sha,
                    "green" if status == "completed" else "red",
                    now,
                    project_id,
                ),
            )
        except Exception as e:
            conn.close()
            raise e
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
                        mission_id=body.get(
                            "platform_run_id", f"ac-{project_id}-{cycle_num}"
                        ),
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

                # ── 2. Convergence detection ──────────────────────────────────
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

    # Thompson stats for AC skills
    skill_stats = {}
    for skill in [
        "ac-architect",
        "ac-codex",
        "ac-adversarial",
        "ac-qa-agent",
        "ac-cicd-agent",
    ]:
        stats = await asyncio.to_thread(ac_skill_stats, skill, project_id)
        if stats:
            skill_stats[skill] = stats

    return JSONResponse(
        {
            "project_id": project_id,
            "cycles": cycles,
            "convergence": conv,
            "avg_reward": round(sum(rewards) / len(rewards), 3) if rewards else 0.0,
            "skill_stats": skill_stats,
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


@router.post("/api/strategic-committee/launch")
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

    asyncio.create_task(
        _run_workflow_background(
            wf,
            session.id,
            "Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO sur les projets en cours",
            "",
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


@router.post("/api/settings/orchestrator")
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


@router.post("/api/settings/security")
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
