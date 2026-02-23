"""Web routes — Page renders (portfolio, backlog, ceremonies, etc.)."""

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

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Auth pages ───────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    templates = _templates(request)
    return templates.TemplateResponse("login.html", {"request": request})


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
    """Adaptive dashboard — content varies by SAFe perspective."""
    perspective = getattr(request.state, "perspective", "admin")
    return _templates(request).TemplateResponse(
        "dashboard.html",
        {"request": request, "page_title": "Dashboard"},
    )


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio dashboard — tour de contrôle DSI (legacy view)."""
    from ...agents.store import get_agent_store
    from ...missions.store import get_mission_run_store, get_mission_store
    from ...projects.manager import get_project_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    mission_store = get_mission_store()
    run_store = get_mission_run_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = mission_store.list_missions(limit=500)
    all_runs = run_store.list_runs(limit=500)
    # Index runs by parent_mission_id for quick lookup
    runs_by_mission: dict = {}
    for r in all_runs:
        if r.parent_mission_id:
            runs_by_mission[r.parent_mission_id] = r
        runs_by_mission[r.id] = r  # Also index by run id (same as mission id)

    strategic_raw = [a for a in all_agents if any(t == "strategy" for t in (a.tags or []))]
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
    strategic = []
    for a in strategic_raw:
        jpg = avatar_dir / f"{a.id}.jpg"
        svg = avatar_dir / f"{a.id}.svg"
        avatar_url = (
            f"/static/avatars/{a.id}.jpg"
            if jpg.exists()
            else (f"/static/avatars/{a.id}.svg" if svg.exists() else "")
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
            a for a in all_agents if a.id.startswith(p.id[:4] + "-") or a.id.startswith(p.id + "-")
        ]
        team_avatars = [{"name": a.name, "icon": a.avatar or a.icon or "bot"} for a in p_agents[:8]]

        p_total = 0
        p_done = 0
        p_active = 0
        mission_cards = []
        for m in p_missions:
            # Compute progress from mission_run phases (live data)
            run = runs_by_mission.get(m.id)
            if run and run.phases:
                t_total = len(run.phases)
                t_done = sum(
                    1 for ph in run.phases if ph.status.value in ("done", "done_with_issues")
                )
                current = run.current_phase or ""
                current_name = next(
                    (ph.phase_name for ph in run.phases if ph.phase_id == current), current
                )
            else:
                # Fallback to task-based stats
                stats = mission_store.mission_stats(m.id)
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

        tma_count = sum(1 for m in p_missions if _is_tma(m) and m.status in ("active", "running"))
        tma_resolved = sum(1 for m in p_missions if _is_tma(m) and m.status == "resolved")
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
            run and any(ph.phase_id in ("cicd", "deploy-prod") for ph in (run.phases or []))
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
                "missions": mission_cards,
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
            t_done = sum(1 for ph in run.phases if ph.status.value in ("done", "done_with_issues"))
            current = run.current_phase or ""
            current_name = next(
                (ph.phase_name for ph in run.phases if ph.phase_id == current), current
            )
            run_status = run.status.value
        else:
            stats = mission_store.mission_stats(m.id)
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
    epics_data = epics_data[:20]  # Cap at 20 for readability

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
                        else (f"/static/avatars/{aid}.svg" if svg_f.exists() else "")
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
    from ...missions.store import get_mission_run_store
    from ...projects.manager import get_project_store
    from ...workflows.store import get_workflow_store

    runs = get_mission_run_store().list_runs(limit=50)
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
            FROM missions m LEFT JOIN projects p ON m.project_id = p.id
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
            FROM missions m LEFT JOIN projects p ON m.project_id = p.id
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


@router.get("/ceremonies", response_class=HTMLResponse)
async def ceremonies_page(request: Request, tab: str = "templates"):
    """Ceremonies — Workflow templates + Patterns in tabs."""
    return _templates(request).TemplateResponse(
        "ceremonies.html",
        {
            "request": request,
            "page_title": "Ceremonies",
            "active_tab": tab,
            "tab_content": "",
        },
    )


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
        Path(__file__).resolve().parent.parent / "templates" / "partials" / "svg_sprites.html"
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
        return JSONResponse({"error": "Workflow 'strategic-committee' not found"}, status_code=404)

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
    return _templates(request).TemplateResponse(
        "monitoring.html",
        {
            "request": request,
            "page_title": "Monitoring",
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    import json as _json

    from ...config import get_config
    from ...db.migrations import get_db
    from ...llm.providers import list_providers

    cfg = get_config()
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM integrations ORDER BY name").fetchall()
        integrations = []
        for r in rows:
            d = dict(r)
            d["config"] = _json.loads(d.get("config_json") or "{}")
            integrations.append(d)
    except Exception:
        integrations = []
    finally:
        db.close()
    return _templates(request).TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "Settings",
            "config": cfg,
            "providers": list_providers(),
            "integrations": integrations,
        },
    )


# ── Admin Users ──────────────────────────────────────────────────


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Admin page for user management (CRUD)."""
    from ...auth import service as auth_svc

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
    return _templates(request).TemplateResponse(
        "admin_users.html",
        {"request": request, "page_title": "Users", "users": user_list},
    )


# ── Vue Métier ───────────────────────────────────────────────────


@router.get("/metier", response_class=HTMLResponse)
async def metier_page(request: Request):
    """Vue Métier — SAFe / LEAN product-centric live dashboard."""
    from datetime import timedelta

    from ...agents.store import get_agent_store
    from ...missions.store import get_mission_run_store
    from ...sessions.store import get_session_store
    from ...workflows.store import get_workflow_store

    wf_store = get_workflow_store()
    session_store = get_session_store()
    agent_store = get_agent_store()
    mission_store = get_mission_run_store()

    all_missions = mission_store.list_runs(limit=50)
    all_sessions = session_store.list_all(limit=100)
    all_agents = agent_store.list_all()
    all_workflows = wf_store.list_all()

    # helper to normalize enum → string
    def _s(val):
        return val.value if hasattr(val, "value") else str(val) if val else "pending"

    # ── Epics Pipeline (missions as value items) ──
    epics = []
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
                    start = datetime.fromisoformat(m.created_at.replace("Z", "+00:00")).replace(
                        tzinfo=None
                    )
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
                    end = datetime.fromisoformat(end.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    end = datetime.utcnow()
            elif hasattr(end, "replace"):
                end = end.replace(tzinfo=None)
            lead_time_h = round((end - start).total_seconds() / 3600, 1)

        epics.append(
            {
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
            }
        )

    # ── Flow Metrics (LEAN) ──
    wip = sum(1 for e in epics if e["status"] == "running")
    completed = sum(1 for e in epics if e["status"] in ("completed", "done"))
    failed = sum(1 for e in epics if e["status"] == "failed")
    total = len(epics)
    throughput_pct = int(completed / total * 100) if total else 0

    lead_times = [
        e["lead_time_h"]
        for e in epics
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
                    agent_msg_counts[msg.from_agent] = agent_msg_counts.get(msg.from_agent, 0) + 1
        except Exception:
            pass
    top_agents = sorted(agent_msg_counts.items(), key=lambda x: -x[1])[:8]
    max_msgs = top_agents[0][1] if top_agents else 1
    agent_velocity = []
    for aid, count in top_agents:
        a = agent_map.get(aid)
        agent_velocity.append(
            {
                "id": aid,
                "name": a.name if a else aid,
                "role": (a.role if a else "")[:30],
                "count": count,
                "pct": int(count / max_msgs * 100),
                "avatar": a.avatar if a else "",
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
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(
                                tzinfo=None
                            )
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
    from ...missions.store import get_mission_run_store, get_mission_store
    from ...projects.manager import LEAN_VALUES, get_project_store

    project_store = get_project_store()
    mission_store = get_mission_store()
    run_store = get_mission_run_store()
    backlog = get_product_backlog()
    dora_engine = get_dora_metrics()

    all_projects = project_store.list_all()
    all_missions = mission_store.list_missions()
    all_runs = run_store.list_runs(limit=200)

    # Group missions by project
    missions_by_project: dict[str, list] = {}
    for m in all_missions:
        pid = m.project_id or "default"
        missions_by_project.setdefault(pid, []).append(m)

    # Group mission_runs by project
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
                    "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                    "feature_count": feat_count,
                    "story_count": story_count,
                    "done_pct": round(done_count / max(story_count, 1) * 100),
                }
            )

        # Also include mission_runs as epics
        for r in proj_runs:
            epic_name = r.brief.split(" - ")[0] if " - " in r.brief else r.brief[:50]
            done_phases = sum(1 for p in r.phases if p.status.value == "done") if r.phases else 0
            total_phases = len(r.phases) if r.phases else 0
            epics_data.append(
                {
                    "id": r.id,
                    "name": epic_name,
                    "status": r.status.value if hasattr(r.status, "value") else str(r.status),
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
            running = sum(1 for e in epics_data if e["status"] == "running")
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
                    "pct": 100 if all(e["status"] == "completed" for e in epics_data) else 0,
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
    from ...missions.store import get_mission_store
    from ...projects.manager import get_project_store

    mission_store = get_mission_store()
    backlog = get_product_backlog()
    project_store = get_project_store()

    all_projects = project_store.list_all()
    all_missions = mission_store.list_missions()
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


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics dashboard - Real-time metrics and insights."""
    return _templates(request).TemplateResponse(
        "analytics.html", {"request": request, "page_title": "Analytics Dashboard"}
    )
