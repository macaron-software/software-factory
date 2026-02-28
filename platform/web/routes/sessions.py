"""Web routes — Session management and live views."""

from __future__ import annotations

import asyncio
import html as html_mod
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from .helpers import _templates, _agent_map_for_template
from ...i18n import t, get_lang

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Sessions ─────────────────────────────────────────────────────


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    """Session list with search + pagination."""
    from ...sessions.store import get_session_store

    q = request.query_params.get("q", "").strip()
    status = request.query_params.get("status", "").strip()
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 20
    offset = (page - 1) * per_page

    store = get_session_store()
    sessions_raw, total = store.search(
        q=q, status=status, limit=per_page, offset=offset
    )

    patterns_map = {}
    try:
        from ...db.migrations import get_db as _gdb

        conn = _gdb()
        for r in conn.execute("SELECT id, name FROM patterns").fetchall():
            patterns_map[r["id"]] = r["name"]
        conn.close()
    except Exception:
        pass
    projects_map = {}
    try:
        from ...projects.manager import get_project_store

        for p in get_project_store().list_all():
            projects_map[p.id] = p.name
    except Exception:
        pass
    sessions = []
    for s in sessions_raw:
        sessions.append(
            {
                "session": s,
                "pattern_name": patterns_map.get(s.pattern_id, ""),
                "project_name": projects_map.get(s.project_id, ""),
                "message_count": store.count_messages(s.id),
            }
        )

    total_pages = max(1, (total + per_page - 1) // per_page)
    return _templates(request).TemplateResponse(
        "sessions.html",
        {
            "request": request,
            "page_title": "Live",
            "sessions": sessions,
            "q": q,
            "status": status,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "per_page": per_page,
        },
    )


@router.get("/sessions/new", response_class=HTMLResponse)
async def new_session_page(request: Request):
    """New session form."""
    from ...agents.store import get_agent_store
    from ...patterns.store import get_pattern_store
    from ...workflows.store import get_workflow_store

    agents = get_agent_store().list_all()
    patterns = get_pattern_store().list_all()
    workflows = get_workflow_store().list_all()
    projects = []
    try:
        from ...projects.manager import get_project_store

        projects = get_project_store().list_all()
    except Exception:
        pass
    patterns_json = json.dumps(
        {
            p.id: {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "agents": p.agents,
                "edges": p.edges,
            }
            for p in patterns
        }
    )
    return _templates(request).TemplateResponse(
        "new_session.html",
        {
            "request": request,
            "page_title": "New Session",
            "agents": agents,
            "patterns": patterns,
            "workflows": workflows,
            "projects": projects,
            "patterns_json": patterns_json,
        },
    )


# ── Live session (multi-agent real-time view) ─────────────────────


@router.get("/sessions/{session_id}/live", response_class=HTMLResponse)
async def session_live_page(request: Request, session_id: str):
    """Live multi-agent session view with 3 modes: Thread, Chat+Panel, Graph."""
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store
    from ...agents.loop import get_loop_manager

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("<h2>Session not found</h2>", status_code=404)

    messages = store.get_messages(session_id, limit=200)
    all_agents = get_agent_store().list_all()
    agent_map = {a.id: a for a in all_agents}

    # Get running loop statuses
    mgr = get_loop_manager()

    # Build agent list with status — filtered after graph is built
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    def _build_agent_entry(a, mgr_ref, session_id_ref):
        loop = mgr_ref.get_loop(a.id, session_id_ref)
        avatar_jpg = avatar_dir / f"{a.id}.jpg"
        avatar_svg = avatar_dir / f"{a.id}.svg"
        avatar_url = ""
        if avatar_jpg.exists():
            avatar_url = f"/static/avatars/{a.id}.jpg"
        elif avatar_svg.exists():
            avatar_url = f"/static/avatars/{a.id}.svg"
        return {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "icon": a.icon,
            "color": a.color,
            "avatar": getattr(a, "avatar", "") or "bot",
            "avatar_url": avatar_url,
            "status": loop.status.value if loop else "idle",
            "description": a.description,
            "skills": getattr(a, "skills", []) or [],
            "tools": getattr(a, "tools", []) or [],
            "mcps": getattr(a, "mcps", []) or [],
            "model": getattr(a, "model", "") or "",
            "provider": getattr(a, "provider", "") or "",
            "tagline": getattr(a, "tagline", "") or "",
            "persona": getattr(a, "persona", "") or "",
            "motivation": getattr(a, "motivation", "") or "",
        }

    # Build graph from workflow/pattern definition (structure defined BEFORE execution)
    # Then enrich edges with live message activity counts
    graph = {"nodes": [], "edges": []}
    wf_id = (session.config or {}).get("workflow_id", "")
    wf_graph_loaded = False

    # 1) Try loading graph from workflow config (primary source)
    if wf_id:
        from ...workflows.store import WorkflowStore

        wf_store = WorkflowStore()
        wf = wf_store.get(wf_id)
        if wf:
            wf_config = wf.config if isinstance(wf.config, dict) else {}
            wf_graph = wf_config.get("graph", {})
            if wf_graph.get("nodes"):
                # Resolve node IDs (n1, n2...) to agent_ids
                node_id_to_agent = {}
                for n in wf_graph["nodes"]:
                    aid = n.get("agent_id", "")
                    a = agent_map.get(aid)
                    node_id_to_agent[n["id"]] = aid
                    graph["nodes"].append(
                        {
                            "id": aid,
                            "agent_id": aid,
                            "label": n.get("label") or (a.name if a else aid),
                            "x": n.get("x"),
                            "y": n.get("y"),
                            "hierarchy_rank": a.hierarchy_rank if a else 50,
                        }
                    )
                for e in wf_graph.get("edges", []):
                    f_agent = node_id_to_agent.get(e["from"], e["from"])
                    t_agent = node_id_to_agent.get(e["to"], e["to"])
                    graph["edges"].append(
                        {
                            "from": f_agent,
                            "to": t_agent,
                            "count": 0,
                            "label": e.get("label", ""),
                            "types": [e.get("type", "sequential")],
                            "patterns": [e.get("type", "sequential")],
                            "color": e.get("color"),
                        }
                    )
                wf_graph_loaded = True

            # Fallback: build graph from workflow phases if no explicit graph config
            if not wf_graph_loaded and wf.phases:
                seen_agents = set()
                for phase in wf.phases:
                    phase_agent_ids = (phase.config or {}).get("agents", [])
                    for aid in phase_agent_ids:
                        if aid not in seen_agents:
                            seen_agents.add(aid)
                            a = agent_map.get(aid)
                            graph["nodes"].append(
                                {
                                    "id": aid,
                                    "agent_id": aid,
                                    "label": a.name if a else aid,
                                    "hierarchy_rank": a.hierarchy_rank if a else 50,
                                }
                            )
                    # Infer edges from phase pattern type + agent list
                    ptype = phase.pattern_id or "sequential"
                    if len(phase_agent_ids) >= 2:
                        if ptype == "sequential":
                            for j in range(len(phase_agent_ids) - 1):
                                graph["edges"].append(
                                    {
                                        "from": phase_agent_ids[j],
                                        "to": phase_agent_ids[j + 1],
                                        "count": 0,
                                        "types": ["sequential"],
                                        "patterns": ["sequential"],
                                    }
                                )
                        elif ptype in ("hierarchical", "adversarial-cascade"):
                            leader = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append(
                                    {
                                        "from": leader,
                                        "to": w,
                                        "count": 0,
                                        "types": [ptype],
                                        "patterns": [ptype],
                                    }
                                )
                        elif ptype == "parallel":
                            dispatcher = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append(
                                    {
                                        "from": dispatcher,
                                        "to": w,
                                        "count": 0,
                                        "types": ["parallel"],
                                        "patterns": ["parallel"],
                                    }
                                )
                        elif ptype in ("network", "adversarial-pair", "debate"):
                            for j, a1 in enumerate(phase_agent_ids):
                                for a2 in phase_agent_ids[j + 1 :]:
                                    graph["edges"].append(
                                        {
                                            "from": a1,
                                            "to": a2,
                                            "count": 0,
                                            "types": [ptype],
                                            "patterns": [ptype],
                                        }
                                    )
                        elif ptype == "router":
                            router = phase_agent_ids[0]
                            for w in phase_agent_ids[1:]:
                                graph["edges"].append(
                                    {
                                        "from": router,
                                        "to": w,
                                        "count": 0,
                                        "types": ["route"],
                                        "patterns": ["router"],
                                    }
                                )
                        elif ptype == "aggregator":
                            agg = phase_agent_ids[-1]
                            for w in phase_agent_ids[:-1]:
                                graph["edges"].append(
                                    {
                                        "from": w,
                                        "to": agg,
                                        "count": 0,
                                        "types": ["aggregate"],
                                        "patterns": ["aggregator"],
                                    }
                                )
                        elif ptype == "human-in-the-loop":
                            for j in range(len(phase_agent_ids) - 1):
                                graph["edges"].append(
                                    {
                                        "from": phase_agent_ids[j],
                                        "to": phase_agent_ids[j + 1],
                                        "count": 0,
                                        "types": ["checkpoint"],
                                        "patterns": ["human-in-the-loop"],
                                    }
                                )
                wf_graph_loaded = bool(seen_agents)

    # 2) Fallback: build from session pattern if no workflow
    if not wf_graph_loaded and session.pattern_id:
        from ...patterns.store import get_pattern_store

        pat = get_pattern_store().get(session.pattern_id)
        if pat and pat.agents:
            nid_to_aid = {}
            for n in pat.agents:
                aid = n.get("agent_id", "")
                nid_to_aid[n["id"]] = aid
                a = agent_map.get(aid)
                graph["nodes"].append(
                    {
                        "id": aid,
                        "agent_id": aid,
                        "label": n.get("label") or (a.name if a else aid),
                        "x": n.get("x"),
                        "y": n.get("y"),
                        "hierarchy_rank": a.hierarchy_rank if a else 50,
                    }
                )
            for e in pat.edges or []:
                f_agent = nid_to_aid.get(e.get("from", ""), e.get("from", ""))
                t_agent = nid_to_aid.get(e.get("to", ""), e.get("to", ""))
                graph["edges"].append(
                    {
                        "from": f_agent,
                        "to": t_agent,
                        "count": 0,
                        "types": [e.get("type", "sequential")],
                        "patterns": [e.get("type", "sequential")],
                    }
                )

    # 3) Enrich edges with live message activity (counts, veto/approve types)
    edge_index = {}
    for i, e in enumerate(graph["edges"]):
        edge_index[(e["from"], e["to"])] = i

    for m in messages:
        if m.from_agent in ("system", "user"):
            continue
        to = getattr(m, "to_agent", "") or ""
        if not to or to in ("all", "system", "user", "session"):
            continue
        key = (m.from_agent, to)
        if key in edge_index:
            graph["edges"][edge_index[key]]["count"] += 1
            if m.message_type in ("veto", "approve"):
                types_list = graph["edges"][edge_index[key]]["types"]
                if m.message_type not in types_list:
                    types_list.append(m.message_type)

    # 4) Fallback: if graph still empty, build from message participants
    if not graph["nodes"]:
        seen = set()
        for m in messages:
            if m.from_agent in ("system", "user"):
                continue
            if m.from_agent not in seen:
                seen.add(m.from_agent)
                a = agent_map.get(m.from_agent)
                graph["nodes"].append(
                    {
                        "id": m.from_agent,
                        "agent_id": m.from_agent,
                        "label": a.name if a else m.from_agent,
                        "hierarchy_rank": a.hierarchy_rank if a else 50,
                    }
                )

    # Filter agents to only those in the graph (or all if no graph)
    graph_agent_ids = {n["agent_id"] for n in graph["nodes"]}
    if graph_agent_ids:
        agents = [
            _build_agent_entry(a, mgr, session_id)
            for a in all_agents
            if a.id in graph_agent_ids
        ]
    else:
        agents = [_build_agent_entry(a, mgr, session_id) for a in all_agents]

    # Serialize messages for template
    msg_list = []
    for m in messages:
        a = agent_map.get(m.from_agent)
        # Extract tool activity from metadata
        meta = m.metadata if isinstance(m.metadata, dict) else {}
        tcs = meta.get("tool_calls") or []
        edit_count = sum(
            1
            for tc in tcs
            if isinstance(tc, dict) and tc.get("name") in ("code_edit", "code_write")
        )
        read_count = sum(
            1
            for tc in tcs
            if isinstance(tc, dict)
            and tc.get("name") in ("code_read", "code_search", "list_files")
        )
        shell_count = sum(
            1
            for tc in tcs
            if isinstance(tc, dict)
            and tc.get("name") in ("shell", "git_status", "git_log")
        )
        msg_list.append(
            {
                "id": m.id,
                "from_agent": m.from_agent,
                "to_agent": getattr(m, "to_agent", ""),
                "type": m.message_type,
                "content": m.content,
                "timestamp": m.timestamp
                if isinstance(m.timestamp, str)
                else m.timestamp.isoformat()
                if hasattr(m.timestamp, "isoformat")
                else str(m.timestamp),
                "from_name": a.name if a else m.from_agent,
                "from_color": a.color if a else "#6b7280",
                "from_avatar": getattr(a, "avatar", "bot") if a else "message-circle",
                "edits": edit_count,
                "reads": read_count,
                "shells": shell_count,
                "tool_count": len(tcs),
            }
        )

    # Load memory for this session
    # Extract artifacts from messages (decisions, reports, tool usage)
    artifacts = []
    # Extract PRs/deliverables from messages — [PR] pattern
    import re as _re

    pr_list = []
    pr_seen = set()
    for m in messages:
        if m.from_agent in ("system", "user"):
            continue
        a = agent_map.get(m.from_agent)
        agent_name = a.name if a else m.from_agent
        content = m.content or ""

        # Extract [PR] items from agent messages
        for pr_match in _re.finditer(r"\[PR\]\s*(.+?)(?:\n|$)", content):
            pr_title = pr_match.group(1).strip()
            pr_title = _re.sub(r"[*_`#]", "", pr_title).strip()[:80]
            if pr_title and pr_title not in pr_seen:
                pr_seen.add(pr_title)
                pr_list.append(
                    {
                        "title": pr_title,
                        "agent": agent_name,
                        "agent_id": m.from_agent,
                        "done": False,
                    }
                )

        # Mark PRs as done if later approved
        if m.message_type == "approve":
            for pr in pr_list:
                if pr["agent_id"] == m.from_agent or m.from_agent in (
                    "qa_lead",
                    "lead_dev",
                ):
                    pr["done"] = True

        # Extract title (first ## heading or first line)
        title_match = _re.search(r"^##\s*(.+)", content, _re.MULTILINE)
        title = (
            title_match.group(1).strip()[:60] if title_match else content[:60].strip()
        )
        title = _re.sub(r"[*_`#]", "", title).strip()

        if m.message_type in ("veto", "approve"):
            artifacts.append(
                {
                    "type": m.message_type,
                    "title": title,
                    "agent": agent_name,
                    "agent_id": m.from_agent,
                    "icon": "x-circle" if m.message_type == "veto" else "check-circle",
                }
            )
        elif any(
            kw in content[:200].lower()
            for kw in (
                "report",
                "audit",
                "analysis",
                "summary",
                "conclusion",
                "decomposition",
                "rapport",
                "analyse",
                "synthèse",
            )
        ):
            meta = {}
            if hasattr(m, "metadata") and m.metadata:
                meta = m.metadata if isinstance(m.metadata, dict) else {}
            has_tools = bool(meta.get("tool_calls"))
            artifacts.append(
                {
                    "type": "report",
                    "title": title,
                    "agent": agent_name,
                    "agent_id": m.from_agent,
                    "icon": "wrench" if has_tools else "file-text",
                }
            )

    memory_data = {
        "session": [],
        "project": [],
        "shared": [],
        "artifacts": artifacts,
        "prs": pr_list,
    }
    try:
        from ...memory.manager import get_memory_manager

        mem = get_memory_manager()
        memory_data["session"] = mem.pattern_get(session_id, limit=20)
        if session.project_id:
            memory_data["project"] = mem.project_get(session.project_id, limit=20)
        memory_data["shared"] = mem.global_get(limit=10)
    except Exception:
        pass

    agent_map_dict = _agent_map_for_template(agents)

    # Build prompt suggestions based on workflow/session goal
    lang = get_lang(request)
    suggestions = []
    if wf_id:
        from ...workflows.store import WorkflowStore as _WS2

        _wf2 = _WS2().get(wf_id)
        if _wf2:
            _WORKFLOW_SUGGESTIONS = {
                "strategic-committee": [
                    (
                        "bar-chart-2",
                        "Arbitrage portfolio",
                        "Analysez le portfolio actuel et recommandez les arbitrages d'investissement pour le trimestre",
                    ),
                    (
                        "target",
                        "WSJF Prioritization",
                        "Prioritize current initiatives using WSJF method and identify quick wins",
                    ),
                    (
                        "check-circle",
                        "GO/NOGO Decision",
                        "Evaluate feasibility and decide GO or NOGO for pending projects",
                    ),
                    (
                        "dollar-sign",
                        "Budget Review",
                        "Review budgets per project and identify potential overruns",
                    ),
                ],
                "sf-pipeline": [
                    (
                        "cpu",
                        "Codebase Analysis",
                        "Analyze the codebase and decompose upcoming development tasks",
                    ),
                    (
                        "alert-triangle",
                        "Fix bugs critiques",
                        "Identifiez et corrigez les bugs critiques en production",
                    ),
                    (
                        "shield",
                        "Security Audit",
                        "Run an OWASP security audit on the current code",
                    ),
                    (
                        "trending-up",
                        "Optimisation perf",
                        "Analysez les performances et proposez des optimisations",
                    ),
                ],
                "migration-sharelook": [
                    (
                        "refresh-cw",
                        "Start Migration",
                        "Launch Angular 16→17 migration starting with module inventory",
                    ),
                    (
                        "check-square",
                        "Verify Golden Files",
                        "Compare legacy vs migration golden files to validate ISO 100%",
                    ),
                    (
                        "package",
                        "Migrer module",
                        "Migrez le prochain module standalone avec les codemods",
                    ),
                    (
                        "activity",
                        "Regression Tests",
                        "Run post-migration regression tests",
                    ),
                ],
                "review-cycle": [
                    (
                        "eye",
                        "Review Latest Commits",
                        "Review latest commits and identify issues",
                    ),
                    (
                        "search",
                        "Quality Analysis",
                        "Analyze code quality: complexity, duplication, coverage",
                    ),
                    (
                        "shield",
                        "Security Audit",
                        "Check for security vulnerabilities in recent code",
                    ),
                ],
                "debate-decide": [
                    (
                        "zap",
                        "Technical Proposal",
                        "Debate architecture options for the next feature",
                    ),
                    (
                        "layers",
                        "Stack Choice",
                        "Compare tech stacks and decide the best approach",
                    ),
                ],
                "ideation-to-prod": [
                    (
                        "compass",
                        t("new_idea_explore", lang=lang),
                        t("new_idea_explore_desc", lang=lang),
                    ),
                    (
                        "box",
                        "MVP Architecture",
                        "Define MVP architecture and required components",
                    ),
                    (
                        "play",
                        "Dev Sprint",
                        "Launch a development sprint on priority user stories",
                    ),
                ],
                "feature-request": [
                    (
                        "file-text",
                        "New Requirement",
                        "I have a business need to express for challenge and implementation",
                    ),
                    (
                        "target",
                        "User Story",
                        "Transform this need into prioritized user stories",
                    ),
                ],
                "tech-debt-reduction": [
                    (
                        "tool",
                        "Audit dette",
                        "Lancez un audit cross-projet de la dette technique",
                    ),
                    (
                        "bar-chart-2",
                        "Prioriser fixes",
                        "Priorisez les corrections de dette par impact WSJF",
                    ),
                ],
                "tma-maintenance": [
                    (
                        "alert-triangle",
                        "Incident Triage",
                        "Sort open incidents by severity and assign fixes",
                    ),
                    (
                        "search",
                        "Diagnostic bug",
                        "Diagnostiquez le bug suivant avec analyse root cause et impact",
                    ),
                    (
                        "zap",
                        "Hotfix urgent",
                        "Lancez un correctif hotfix P0 avec deploy express",
                    ),
                    (
                        "bar-chart-2",
                        "TMA Report",
                        "Review SLA status, resolved incidents and remaining tech debt",
                    ),
                ],
                "test-campaign": [
                    (
                        "clipboard",
                        "Test Plan",
                        "Define coverage matrix and critical paths to test",
                    ),
                    (
                        "terminal",
                        "Automate Tests",
                        "Write E2E Playwright tests for identified paths",
                    ),
                    (
                        "play-circle",
                        t("launch_qa", lang=lang),
                        t("launch_qa_desc", lang=lang),
                    ),
                    (
                        "bar-chart-2",
                        "Quality Report",
                        "Consolidate results and decide GO/NOGO for release",
                    ),
                ],
                "cicd-pipeline": [
                    (
                        "settings",
                        "Setup pipeline",
                        "Configurez le pipeline CI/CD GitHub Actions pour le projet",
                    ),
                    (
                        "refresh-cw",
                        "Optimiser CI",
                        "Analysez et optimisez les temps de build du pipeline actuel",
                    ),
                    (
                        "shield",
                        "Quality Gates",
                        "Configure quality gates: coverage, security, performance",
                    ),
                    (
                        "upload-cloud",
                        "Canary Deploy",
                        "Launch canary deployment with monitoring and auto-rollback",
                    ),
                ],
                "product-lifecycle": [
                    (
                        "compass",
                        t("new_idea_product", lang=lang),
                        t("new_idea_product_desc", lang=lang),
                    ),
                    (
                        "git-merge",
                        "Full Cycle from Requirement",
                        "Here's a business need — run it through the full cycle: ideation → strategic committee → dev → CI/CD → QA → prod → TMA",
                    ),
                    (
                        "refresh-cw",
                        "Resume Dev Sprint",
                        "Strategic committee validated GO — launch development sprints",
                    ),
                    (
                        "activity",
                        "Launch QA Campaign",
                        "Code is ready — launch the full QA test campaign before deployment",
                    ),
                ],
            }
            suggestions = _WORKFLOW_SUGGESTIONS.get(wf_id, [])
            if not suggestions and _wf2.description:
                suggestions = [
                    ("play", "Start", f"Let's start: {_wf2.description}"),
                    (
                        "help-circle",
                        "Status Report",
                        "Get a status report before starting",
                    ),
                ]
    if not suggestions and session.goal:
        suggestions = [
            ("play", "Start", f"Commençons : {session.goal}"),
            (
                "clipboard",
                "Plan d'action",
                f"Proposez un plan d'action pour : {session.goal}",
            ),
        ]

    return _templates(request).TemplateResponse(
        "session_live.html",
        {
            "request": request,
            "page_title": f"Live: {session.name}",
            "session": {
                "id": session.id,
                "name": session.name,
                "goal": session.goal,
                "status": session.status,
                "pattern": getattr(session, "pattern_id", ""),
                "project_id": session.project_id,
            },
            "agents": agents,
            "agent_map": agent_map_dict,
            "messages": msg_list,
            "graph": graph,
            "memory": memory_data,
            "suggestions": suggestions,
        },
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_page(request: Request, session_id: str):
    """Active session conversation view."""
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store
    from ...patterns.store import get_pattern_store

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("<h2>Session not found</h2>", status_code=404)
    messages = store.get_messages(session_id)
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)
    pattern_name = ""
    if session.pattern_id:
        pat = get_pattern_store().get(session.pattern_id)
        if pat:
            pattern_name = pat.name
    workflow_name = ""
    wf_id = (session.config or {}).get("workflow_id", "")
    if wf_id:
        from ...workflows.store import get_workflow_store

        wf = get_workflow_store().get(wf_id)
        if wf:
            workflow_name = wf.name
    return _templates(request).TemplateResponse(
        "conversation.html",
        {
            "request": request,
            "page_title": session.name,
            "session": session,
            "messages": messages,
            "agents": agents,
            "agent_map": agent_map,
            "pattern_name": pattern_name,
            "workflow_name": workflow_name,
        },
    )


@router.post("/api/sessions")
async def create_session(request: Request):
    """Create a new session from form data."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef

    form = await request.form()
    store = get_session_store()
    session = SessionDef(
        name=str(form.get("name", "Untitled")),
        goal=str(form.get("goal", "")),
        pattern_id=str(form.get("pattern_id", "")) or None,
        project_id=str(form.get("project_id", "")) or None,
        status="active",
        config={
            "lead_agent": str(form.get("lead_agent", "")),
            "workflow_id": str(form.get("workflow_id", "")),
        },
    )
    session = store.create(session)
    # Add system message
    store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content=f'Session "{session.name}" started. Goal: {session.goal or "not specified"}',
        )
    )
    return RedirectResponse(f"/sessions/{session.id}", status_code=303)


@router.post("/api/sessions/{session_id}/messages", response_class=HTMLResponse)
async def send_message(request: Request, session_id: str):
    """User sends a message — agent responds via LLM."""
    from ...sessions.store import get_session_store, MessageDef
    from ...sessions.runner import handle_user_message
    from ...agents.store import get_agent_store

    form = await request.form()
    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)
    # Auto-resume if stopped
    if session.status in ("completed", "failed"):
        store.update_status(session_id, "active")
    content = str(form.get("content", "")).strip()
    if not content:
        return HTMLResponse("")
    to_agent = str(form.get("to_agent", "")) or session.config.get("lead_agent") or None

    # Store user message
    user_msg = store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            to_agent=to_agent,
            message_type="text",
            content=content,
        )
    )

    # Get agent map for rendering
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)

    # Render user bubble
    user_html = (
        _templates(request)
        .TemplateResponse(
            "partials/msg_unified.html",
            {
                "request": request,
                "msg": user_msg,
                "agent_map": agent_map,
                "msg_mode": "chat",
            },
        )
        .body.decode()
    )

    # Call agent (async LLM)
    agent_msg = await handle_user_message(session_id, content, to_agent or "")

    if agent_msg:
        agent_html = (
            _templates(request)
            .TemplateResponse(
                "partials/msg_unified.html",
                {
                    "request": request,
                    "msg": agent_msg,
                    "agent_map": agent_map,
                    "msg_mode": "chat",
                },
            )
            .body.decode()
        )
        return HTMLResponse(user_html + agent_html)

    return HTMLResponse(user_html)


@router.get("/api/sessions/{session_id}/messages", response_class=HTMLResponse)
async def poll_messages(request: Request, session_id: str, after: str = ""):
    """Poll for new messages (HTMX polling endpoint)."""
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store

    store = get_session_store()
    if not after:
        return HTMLResponse("")
    messages = store.get_messages_after(session_id, after)
    if not messages:
        return HTMLResponse("")
    agents = get_agent_store().list_all()
    agent_map = _agent_map_for_template(agents)
    html_parts = []
    for msg in messages:
        html_parts.append(
            _templates(request)
            .TemplateResponse(
                "partials/msg_unified.html",
                {
                    "request": request,
                    "msg": msg,
                    "agent_map": agent_map,
                    "msg_mode": "chat",
                },
            )
            .body.decode()
        )
    return HTMLResponse("".join(html_parts))


@router.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active session."""
    from ...sessions.store import get_session_store, MessageDef

    store = get_session_store()
    session = store.get(session_id)
    if session and session.status == "completed":
        return HTMLResponse("")  # already stopped
    store.update_status(session_id, "completed")
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content="Session stopped by user.",
        )
    )
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a completed/stopped session back to active."""
    from ...sessions.store import get_session_store, MessageDef

    store = get_session_store()
    store.update_status(session_id, "active")
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content="Session resumed.",
        )
    )
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/run-pattern")
async def run_session_pattern(request: Request, session_id: str):
    """Execute the pattern assigned to this session."""
    from ...sessions.store import get_session_store, MessageDef
    from ...patterns.store import get_pattern_store

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    form = await request.form()
    task = str(form.get("task", session.goal or "Execute the pattern")).strip()
    pattern_id = str(form.get("pattern_id", session.pattern_id or "")).strip()

    if not pattern_id:
        return HTMLResponse(
            '<div class="msg-system-text">No pattern assigned to this session.</div>'
        )

    pattern = get_pattern_store().get(pattern_id)
    if not pattern:
        return HTMLResponse(
            f'<div class="msg-system-text">Pattern {html_mod.escape(str(pattern_id))} not found.</div>'
        )

    # Store user's task as a message
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            message_type="text",
            content=f"Run pattern **{pattern.name}**: {task}",
        )
    )

    # Run pattern asynchronously (agents will post messages to the session)
    asyncio.create_task(
        _run_pattern_background(pattern, session_id, task, session.project_id or "")
    )

    return HTMLResponse(
        '<div class="msg-system-text">Pattern started — agents are working...</div>'
    )


async def _run_pattern_background(pattern, session_id: str, task: str, project_id: str):
    """Background task for pattern execution."""
    from ...patterns.engine import run_pattern

    try:
        await run_pattern(pattern, session_id, task, project_id)
    except Exception as e:
        logger.error("Pattern execution failed: %s", e)
        from ...sessions.store import get_session_store, MessageDef

        get_session_store().add_message(
            MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"Pattern execution error: {e}",
            )
        )


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages."""
    from ...sessions.store import get_session_store

    get_session_store().delete(session_id)
    return HTMLResponse("")


@router.post("/api/sessions/{session_id}/agents/start")
async def start_session_agents(request: Request, session_id: str):
    """Start agent loops for a session — the agents begin thinking autonomously."""
    from ...sessions.store import get_session_store
    from ...agents.loop import get_loop_manager
    from ...projects.manager import get_project_store

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    form = await request.form()
    agent_ids = str(form.get("agent_ids", "")).split(",")
    agent_ids = [a.strip() for a in agent_ids if a.strip()]
    if not agent_ids:
        return JSONResponse({"error": "No agent_ids provided"}, status_code=400)

    # Resolve project path
    project_path = ""
    if session.project_id:
        try:
            proj = get_project_store().get(session.project_id)
            if proj:
                project_path = proj.path
        except Exception:
            pass

    mgr = get_loop_manager()
    started = []
    for aid in agent_ids:
        try:
            await mgr.start_agent(
                aid, session_id, session.project_id or "", project_path
            )
            started.append(aid)
        except Exception as e:
            logger.error("Failed to start agent %s: %s", aid, e)

    return JSONResponse({"started": started, "count": len(started)})


@router.post("/api/sessions/{session_id}/agents/stop")
async def stop_session_agents(session_id: str):
    """Stop all agent loops for a session."""
    from ...agents.loop import get_loop_manager

    mgr = get_loop_manager()
    await mgr.stop_session(session_id)
    return JSONResponse({"stopped": True})


@router.post("/api/sessions/{session_id}/agents/{agent_id}/message")
async def send_to_agent(request: Request, session_id: str, agent_id: str):
    """Send a message to a specific agent via the bus (user → agent)."""
    from ...a2a.bus import get_bus
    from ...models import A2AMessage, MessageType
    from ...sessions.store import get_session_store, MessageDef

    form = await request.form()
    content = str(form.get("content", "")).strip()
    if not content:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    # Store user message in session
    store = get_session_store()
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            message_type="text",
            content=content,
        )
    )

    # Publish to bus so the agent's loop picks it up
    bus = get_bus()
    msg = A2AMessage(
        session_id=session_id,
        from_agent="user",
        to_agent=agent_id,
        message_type=MessageType.REQUEST,
        content=content,
        requires_response=True,
    )
    await bus.publish(msg)

    return JSONResponse({"sent": True, "to": agent_id})


@router.post("/api/sessions/{session_id}/conversation")
async def start_conversation(request: Request, session_id: str):
    """Start a real multi-agent conversation with streaming.

    Each agent is called individually with its own persona/LLM,
    sees the full conversation history, and responds in real-time via SSE.
    """
    from ...sessions.runner import run_conversation

    form = await request.form()
    message = str(form.get("message", "")).strip()
    agent_ids_raw = str(form.get("agent_ids", ""))
    agent_ids = [a.strip() for a in agent_ids_raw.split(",") if a.strip()]
    lead = str(form.get("lead_agent", ""))
    max_rounds = int(form.get("max_rounds", 6))

    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    if not agent_ids:
        return JSONResponse({"error": "agent_ids required"}, status_code=400)

    # Run in background — SSE will stream the conversation
    async def _run_conv():
        try:
            await run_conversation(
                session_id=session_id,
                initial_message=message,
                agent_ids=agent_ids,
                max_rounds=max_rounds,
                lead_agent_id=lead,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Conversation failed: %s", exc, exc_info=True
            )

    asyncio.create_task(_run_conv())

    return JSONResponse(
        {"status": "started", "agents": agent_ids, "max_rounds": max_rounds}
    )


@router.get("/api/sessions/{session_id}/messages/json")
async def session_messages_json(session_id: str):
    """JSON list of all agent messages for a session (for fallback on pattern_end)."""
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store

    store = get_session_store()
    msgs = store.get_messages(session_id)
    agents = {a.id: a for a in get_agent_store().list_all()}
    result = []
    for m in msgs:
        if m.from_agent in ("system", "user"):
            continue
        a = agents.get(m.from_agent)
        result.append(
            {
                "agent_id": m.from_agent,
                "agent_name": a.name if a else m.from_agent,
                "role": a.role if a else "",
                "content": m.content,
                "to_agent": m.to_agent,
            }
        )
    return JSONResponse(result)


@router.get("/api/sessions/{session_id}/checkpoints")
async def session_checkpoints(request: Request, session_id: str):
    """Latest step checkpoints per agent (live activity panel).
    Returns JSON by default; HTML partial when called from htmx."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            """SELECT agent_id, step_index, tool_calls, partial_content
               FROM agent_step_checkpoints
               WHERE session_id = ?
               ORDER BY agent_id, step_index DESC""",
            (session_id,),
        ).fetchall()
    except Exception:
        rows = []
    finally:
        db.close()

    import json as _json

    seen: dict[str, dict] = {}
    for r in rows:
        aid = r["agent_id"]
        if aid in seen:
            continue
        try:
            tools = _json.loads(r["tool_calls"] or "[]")
            last_tool = tools[-1].get("name", "") if tools else ""
        except Exception:
            last_tool = ""
        seen[aid] = {
            "agent_id": aid,
            "step": r["step_index"],
            "last_tool": last_tool,
            "preview": (r["partial_content"] or "")[:100],
        }
    items = list(seen.values())

    # Return HTML partial when called via htmx
    if request.headers.get("HX-Request"):
        if not items:
            return HTMLResponse("")
        rows_html = "".join(
            f'<div style="font-size:0.72rem;padding:2px 0;display:flex;gap:6px;align-items:center">'
            f'<span style="color:var(--text-muted,#999);font-weight:600">{i["agent_id"][:20]}</span>'
            f'<span style="color:var(--accent-blue,#60a5fa)">step {i["step"]}</span>'
            + (
                f'<span style="background:#1e293b;padding:0 4px;border-radius:3px;font-family:monospace">{i["last_tool"]}</span>'
                if i["last_tool"]
                else ""
            )
            + (
                f'<span style="color:var(--text-muted,#888);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px">{i["preview"]}</span>'
                if i["preview"]
                else ""
            )
            + "</div>"
            for i in items
        )
        return HTMLResponse(
            f'<div style="border-top:1px solid #ffffff15;padding:6px 0 2px;margin-bottom:4px">'
            f'<div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted,#888);margin-bottom:4px">Agent activity</div>'
            f"{rows_html}</div>"
        )
    return JSONResponse(
        {
            "session_id": session_id,
            "checkpoints": items,
            "agent_count": len(items),
        }
    )


@router.get("/api/sessions/{session_id}/sse")
async def session_sse(request: Request, session_id: str):
    """SSE endpoint for real-time session updates."""
    from ...sessions.runner import add_sse_listener, remove_sse_listener

    q = add_sse_listener(session_id)

    async def event_generator():
        try:
            yield 'data: {"type":"connected"}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            remove_sse_listener(session_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
