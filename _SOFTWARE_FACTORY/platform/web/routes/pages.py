"""Web routes — Page renders (portfolio, backlog, ceremonies, etc.)."""
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

# ── Pages ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio dashboard — tour de contrôle DSI."""
    from ...projects.manager import get_project_store
    from ...agents.store import get_agent_store
    from ...missions.store import get_mission_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    mission_store = get_mission_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = mission_store.list_missions()

    strategic_raw = [a for a in all_agents if any(t == 'strategy' for t in (a.tags or []))]
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
    strategic = []
    for a in strategic_raw:
        jpg = avatar_dir / f"{a.id}.jpg"
        svg = avatar_dir / f"{a.id}.svg"
        avatar_url = f"/static/avatars/{a.id}.jpg" if jpg.exists() else (f"/static/avatars/{a.id}.svg" if svg.exists() else "")
        strategic.append({
            "id": a.id, "name": a.name, "role": a.role,
            "avatar": a.avatar or a.icon or "bot", "color": a.color or "#7c3aed",
            "avatar_url": avatar_url,
            "tagline": a.tagline or "", "persona": a.persona or "",
            "description": a.description or "",
            "motivation": a.motivation or "",
            "skills": a.skills or [], "tools": a.tools or [],
            "mcps": a.mcps or [],
            "model": getattr(a, "model", "") or "", "provider": getattr(a, "provider", "") or "",
        })

    # Build project cards with missions
    projects_data = []
    total_tasks = 0
    total_done = 0
    active_count = 0
    for p in all_projects:
        p_missions = [m for m in all_missions if m.project_id == p.id]
        p_agents = [a for a in all_agents
                    if a.id.startswith(p.id[:4] + '-') or a.id.startswith(p.id + '-')]
        team_avatars = [{"name": a.name, "icon": a.avatar or a.icon or "bot"} for a in p_agents[:8]]

        p_total = 0
        p_done = 0
        p_active = 0
        mission_cards = []
        for m in p_missions:
            stats = mission_store.mission_stats(m.id)
            t_total = stats.get("total", 0)
            t_done = stats.get("done", 0)
            p_total += t_total
            p_done += t_done
            if m.status == "active":
                p_active += 1
            progress = f"{t_done}/{t_total}" if t_total > 0 else ""
            mission_cards.append({"name": m.name, "status": m.status, "task_progress": progress})
        total_tasks += p_total
        total_done += p_done
        active_count += p_active

        projects_data.append({
            "id": p.id, "name": p.name, "factory_type": p.factory_type,
            "description": p.description or (p.vision or "")[:100],
            "missions": mission_cards, "mission_count": len(p_missions),
            "active_mission_count": p_active,
            "team_avatars": team_avatars,
            "total_tasks": p_total, "done_tasks": p_done,
        })

    # Build epics progression table
    epics_data = []
    for m in all_missions:
        stats = mission_store.mission_stats(m.id)
        t_total = stats.get("total", 0)
        t_done = stats.get("done", 0)
        pct = int(t_done / t_total * 100) if t_total > 0 else 0
        p = next((p for p in all_projects if p.id == m.project_id), None)
        epics_data.append({
            "id": m.id, "name": m.name, "status": m.status,
            "project_name": p.name if p else m.project_id or "—",
            "done": t_done, "total": t_total, "pct": pct,
            "wsjf": getattr(m, "wsjf", 0) or 0,
        })
    epics_data.sort(key=lambda e: e["pct"], reverse=True)

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
                    av_url = f"/static/avatars/{aid}.jpg" if jpg.exists() else (f"/static/avatars/{aid}.svg" if svg_f.exists() else "")
                    strat_graph["nodes"].append({
                        "id": n["id"], "agent_id": aid,
                        "label": n.get("label", a.name if a else aid),
                        "x": n.get("x", 0), "y": n.get("y", 0),
                        "color": a.color if a else "#7c3aed",
                        "avatar_url": av_url,
                    })
                strat_graph["edges"] = sg.get("edges", [])
    except Exception:
        pass

    return _templates(request).TemplateResponse("portfolio.html", {
        "request": request, "page_title": "Portfolio",
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
    })


# ── SAFe consolidated pages (tabbed) ─────────────────────────────

@router.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request, tab: str = "backlog"):
    """Backlog — Product + Discovery (ideation) in tabs."""
    return _templates(request).TemplateResponse("backlog.html", {
        "request": request, "page_title": "Backlog",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/pi", response_class=HTMLResponse)
async def pi_board_page(request: Request):
    """PI Board — missions list with creation."""
    from ...missions.store import get_mission_run_store
    from ...projects.manager import get_project_store
    from ...workflows.store import get_workflow_store
    runs = get_mission_run_store().list_runs(limit=50)
    projects = get_project_store().list_all()
    workflows = get_workflow_store().list_all()
    active_ids = {mid for mid, t in _active_mission_tasks.items() if not t.done()}
    return _templates(request).TemplateResponse("pi_board.html", {
        "request": request, "page_title": "PI Board",
        "runs": runs, "projects": projects, "workflows": workflows,
        "active_ids": active_ids,
    })

@router.get("/ceremonies", response_class=HTMLResponse)
async def ceremonies_page(request: Request, tab: str = "templates"):
    """Ceremonies — Workflow templates + Patterns in tabs."""
    return _templates(request).TemplateResponse("ceremonies.html", {
        "request": request, "page_title": "Ceremonies",
        "active_tab": tab, "tab_content": "",
    })

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
    return _templates(request).TemplateResponse("art.html", {
        "request": request, "page_title": "ART",
        "org_tree": tree,
        "portfolios": portfolios,
        "total_arts": len(all_arts),
        "total_teams": len(all_teams),
        "total_members": total_members,
    })

@router.get("/toolbox", response_class=HTMLResponse)
async def toolbox_page(request: Request, tab: str = "skills"):
    """Toolbox — Skills + Memory + MCPs in tabs."""
    return _templates(request).TemplateResponse("toolbox.html", {
        "request": request, "page_title": "Toolbox",
        "active_tab": tab, "tab_content": "",
    })

@router.get("/design-system", response_class=HTMLResponse)
async def design_system_page(request: Request):
    """Design System — tokens, colors, icons, atoms, molecules, patterns."""
    import re
    # Extract icon names from SVG sprites
    sprites_path = Path(__file__).resolve().parent.parent / "templates" / "partials" / "svg_sprites.html"
    icons = []
    if sprites_path.exists():
        text = sprites_path.read_text()
        icons = re.findall(r'id="icon-([^"]+)"', text)
    return _templates(request).TemplateResponse("design_system.html", {
        "request": request, "page_title": "Design System",
        "icons": icons,
    })

@router.post("/api/strategic-committee/launch")
async def launch_strategic_committee(request: Request):
    """Launch a strategic committee session from the portfolio page."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef
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
    session_store.add_message(MessageDef(
        session_id=session.id,
        from_agent="system",
        message_type="system",
        content="Comité Stratégique lancé. Les agents du comité vont débattre des priorités portfolio.",
    ))

    # Auto-start workflow — agents debate autonomously
    from .workflows import _run_workflow_background
    import asyncio
    asyncio.create_task(_run_workflow_background(
        wf, session.id,
        "Revue stratégique du portfolio — arbitrages, priorités, GO/NOGO sur les projets en cours",
        "",
    ))

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
            project_memories.append({
                "project_id": p.id,
                "project_name": p.name,
                "entries": entries,
                "count": len(entries),
            })

    return _templates(request).TemplateResponse("memory.html", {
        "request": request,
        "page_title": "Memory",
        "stats": stats,
        "recent_global": recent_global,
        "project_memories": project_memories,
    })


# ── Monitoring / Settings ────────────────────────────────────────

@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    return _templates(request).TemplateResponse("monitoring.html", {
        "request": request,
        "page_title": "Monitoring",
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    from ...config import get_config
    from ...llm.providers import list_providers
    cfg = get_config()
    return _templates(request).TemplateResponse("settings.html", {
        "request": request,
        "page_title": "Settings",
        "config": cfg,
        "providers": list_providers(),
    })


# ── Vue Métier ───────────────────────────────────────────────────

@router.get("/metier", response_class=HTMLResponse)
async def metier_page(request: Request):
    """Vue Métier — business process flows by department."""
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store
    import random

    wf_store = get_workflow_store()
    session_store = get_session_store()
    all_workflows = wf_store.list_all()
    all_sessions = session_store.list_all()

    # Build department swim lanes from workflows
    dept_map = {
        "Sales": {"color": "var(--blue)", "icon": "trending-up", "workflows": []},
        "Supply Chain": {"color": "var(--green)", "icon": "truck", "workflows": []},
        "Support": {"color": "var(--yellow)", "icon": "headphones", "workflows": []},
    }
    for wf in all_workflows:
        pattern = wf.phases[0].pattern_id if wf.phases else "sequential"
        entry = {"name": wf.name, "pattern": pattern}
        # Distribute workflows across departments
        if "migration" in wf.id or "pipeline" in wf.id:
            dept_map["Supply Chain"]["workflows"].append(entry)
        elif "review" in wf.id or "debate" in wf.id:
            dept_map["Support"]["workflows"].append(entry)
        else:
            dept_map["Sales"]["workflows"].append(entry)

    departments = []
    for dept_name, dept_data in dept_map.items():
        nodes = []
        # Agent node
        nodes.append({"type": "agent", "icon": dept_data["icon"], "label": dept_name, "active": True})
        nodes.append({"type": "agent", "icon": "layers", "label": "Sequential", "active": False})
        nodes.append({"type": "agent", "icon": "users", "label": "Agent", "active": False})
        # Pattern box
        if dept_data["workflows"]:
            patterns = ", ".join(set(w["pattern"] for w in dept_data["workflows"]))
            nodes.append({"type": "pattern", "label": f"Patterns\n{patterns.title()}", "active": False})
        nodes.append({"type": "agent", "icon": "check-circle", "label": "Agent", "active": False})
        departments.append({
            "name": dept_name,
            "nodes": nodes,
            "efficiency": random.randint(55, 95),
            "color": dept_data["color"],
        })

    # Productivity
    total_efficiency = sum(d["efficiency"] for d in departments) // max(len(departments), 1)

    # Calendar heatmap (31 days)
    calendar_days = []
    for i in range(1, 32):
        level = random.choice([0, 0, 1, 1, 2, 3, 4]) if i <= 28 else random.choice([0, 1])
        calendar_days.append({"num": i, "level": level})

    return _templates(request).TemplateResponse("metier.html", {
        "request": request, "page_title": "Vue Métier",
        "departments": departments,
        "productivity_pct": total_efficiency,
        "calendar_days": calendar_days,
    })


# ── Product Line Manager ─────────────────────────────────────────

@router.get("/product-line", response_class=HTMLResponse)
async def product_line_page(request: Request):
    """Product Line Manager — produits, roadmap, milestones, DORA."""
    from ...missions.store import get_mission_store, get_mission_run_store
    from ...missions.product import get_product_backlog
    from ...projects.manager import get_project_store, LEAN_VALUES
    from ...metrics.dora import get_dora_metrics

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

            epics_data.append({
                "id": m.id,
                "name": m.name,
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "feature_count": feat_count,
                "story_count": story_count,
                "done_pct": round(done_count / max(story_count, 1) * 100),
            })

        # Also include mission_runs as epics
        for r in proj_runs:
            epic_name = r.brief.split(' - ')[0] if ' - ' in r.brief else r.brief[:50]
            done_phases = sum(1 for p in r.phases if p.status.value == 'done') if r.phases else 0
            total_phases = len(r.phases) if r.phases else 0
            epics_data.append({
                "id": r.id,
                "name": epic_name,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "feature_count": total_phases,
                "story_count": total_phases,
                "done_pct": round(done_phases / max(total_phases, 1) * 100),
                "is_run": True,
            })

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

            milestones.append({
                "name": "Kickoff", "date": "", "pct": 100, "state": "done",
            })
            if proj_features > 0:
                feat_pct = min(100, round(proj_done / max(proj_stories, 1) * 100))
                milestones.append({
                    "name": f"Développement ({proj_features} features)",
                    "date": "", "pct": feat_pct,
                    "state": "done" if feat_pct == 100 else ("active" if feat_pct > 0 else "upcoming"),
                })
            if total_ep > 0:
                deploy_pct = round(completed / total_ep * 100)
                milestones.append({
                    "name": f"Déploiement ({completed}/{total_ep} epics)",
                    "date": "", "pct": deploy_pct,
                    "state": "done" if deploy_pct == 100 else ("active" if deploy_pct > 0 else "upcoming"),
                })
            milestones.append({
                "name": "Production",
                "date": "",
                "pct": 100 if all(e["status"] == "completed" for e in epics_data) else 0,
                "state": "done" if all(e["status"] == "completed" for e in epics_data) else "upcoming",
            })

        # Per-product DORA
        proj_dora = None
        try:
            proj_dora = dora_engine.summary(proj.id, 30)
        except Exception:
            pass

        # Project values
        proj_values = []
        for vid in (proj.values or []):
            for lv in LEAN_VALUES:
                if lv["id"] == vid:
                    proj_values.append(lv)
                    break

        products.append({
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
        })

    # Overall DORA
    overall_dora = dora_engine.summary("", 30)
    overall_done = round(total_done_stories / max(total_stories, 1) * 100)

    # Global values (union of all project values)
    all_value_ids = set()
    for p in products:
        all_value_ids.update(v["id"] for v in p.get("values", []))
    global_values = [lv for lv in LEAN_VALUES if lv["id"] in all_value_ids] if all_value_ids else LEAN_VALUES[:4]

    return _templates(request).TemplateResponse("product_line.html", {
        "request": request,
        "page_title": "Ligne de Produit",
        "products": products,
        "total_epics": total_epics,
        "total_features": total_features,
        "total_stories": total_stories,
        "overall_done_pct": overall_done,
        "dora": overall_dora,
        "values": global_values,
    })


# ── Product Management ───────────────────────────────────────────

@router.get("/product", response_class=HTMLResponse)
async def product_page(request: Request):
    """Product backlog — Epic → Feature → User Story hierarchy."""
    from ...missions.store import get_mission_store
    from ...missions.product import get_product_backlog
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

            epic_features.append({
                "id": f.id, "name": f.name, "status": f.status,
                "story_points": f_points, "assigned_to": f.assigned_to,
                "stories": [{"id": s.id, "title": s.title, "status": s.status,
                             "story_points": s.story_points} for s in stories],
            })

        total_features += len(features)
        total_done_stories += epic_done

        epics.append({
            "id": m.id, "name": m.name, "status": m.status,
            "project_name": project_names.get(m.project_id, m.project_id),
            "features": epic_features,
            "total_points": epic_points,
            "total_stories": epic_stories,
            "done_pct": round(epic_done / max(epic_stories, 1) * 100),
        })

    done_pct = round(total_done_stories / max(total_stories, 1) * 100)

    return _templates(request).TemplateResponse("product.html", {
        "request": request, "page_title": "Product",
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
    })


