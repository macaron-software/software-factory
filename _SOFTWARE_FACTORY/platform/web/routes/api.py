"""Web routes — Pure API endpoints (memory, LLM, RBAC, DORA, retrospectives)."""
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

# Prime psutil cpu_percent so interval=0 returns meaningful values
try:
    import psutil as _ps, os as _os
    _ps.Process(_os.getpid()).cpu_percent()
    _ps.cpu_percent()
except Exception:
    pass

# ── Health ────────────────────────────────────────────────────────

@router.get("/api/health")
async def health_check():
    """Liveness/readiness probe for Docker healthcheck."""
    from ...db.migrations import get_db
    try:
        db = get_db()
        db.execute("SELECT 1")
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)

# ── Memory API ───────────────────────────────────────────────────

@router.get("/api/memory/stats")
async def memory_stats():
    """Memory layer statistics."""
    from ...memory.manager import get_memory_manager
    return JSONResponse(get_memory_manager().stats())


# ── LLM Observability ──────────────────────────────────────────

@router.get("/api/llm/stats")
async def llm_stats(hours: int = 24, session_id: str = ""):
    """LLM usage statistics: calls, tokens, cost, by provider/agent."""
    from ...llm.observability import get_tracer
    return JSONResponse(get_tracer().stats(session_id=session_id, hours=hours))


@router.get("/api/llm/traces")
async def llm_traces(limit: int = 50, session_id: str = ""):
    """Recent LLM call traces."""
    from ...llm.observability import get_tracer
    return JSONResponse(get_tracer().recent(limit=limit, session_id=session_id))


@router.get("/api/memory/vector/search")
async def vector_search(scope_id: str, q: str, limit: int = 10):
    """Semantic vector search in memory."""
    from ...memory.manager import get_memory_manager
    mem = get_memory_manager()
    results = await mem.semantic_search(scope_id, q, limit=limit)
    return JSONResponse(results)


@router.get("/api/memory/vector/stats")
async def vector_stats(scope_id: str = ""):
    """Vector store statistics."""
    from ...memory.vectors import get_vector_store
    return JSONResponse(get_vector_store().count(scope_id))


@router.get("/api/sandbox/status")
async def sandbox_status():
    """Docker sandbox status."""
    from ...tools.sandbox import SANDBOX_ENABLED, SANDBOX_IMAGE, SANDBOX_NETWORK, SANDBOX_MEMORY
    import shutil
    docker_available = shutil.which("docker") is not None
    return JSONResponse({
        "enabled": SANDBOX_ENABLED,
        "docker_available": docker_available,
        "default_image": SANDBOX_IMAGE,
        "network": SANDBOX_NETWORK,
        "memory_limit": SANDBOX_MEMORY,
    })


@router.get("/api/permissions/denials")
async def permission_denials(limit: int = 50, agent_id: str = ""):
    """Recent permission denials (audit log)."""
    from ...agents.permissions import get_permission_guard
    return JSONResponse(get_permission_guard().recent_denials(limit=limit, agent_id=agent_id))


@router.get("/api/permissions/stats")
async def permission_stats():
    """Permission denial statistics."""
    from ...agents.permissions import get_permission_guard
    return JSONResponse(get_permission_guard().denial_stats())


@router.get("/api/memory/project/{project_id}")
async def project_memory(project_id: str, q: str = "", category: str = ""):
    """Get or search project memory."""
    from ...memory.manager import get_memory_manager
    mem = get_memory_manager()
    if q:
        entries = mem.project_search(project_id, q)
    else:
        entries = mem.project_get(project_id, category=category or None)
    return JSONResponse(entries)


@router.get("/api/memory/global")
async def global_memory(category: str = ""):
    """Get global memory entries."""
    from ...memory.manager import get_memory_manager
    entries = get_memory_manager().global_get(category=category or None)
    return JSONResponse(entries)


@router.post("/api/memory/global")
async def global_memory_store(request: Request):
    """Store a global memory entry."""
    from ...memory.manager import get_memory_manager
    data = await request.json()
    cat = data.get("category", "general")
    key = data.get("key", "")
    val = data.get("value", "")
    if not key or not val:
        return JSONResponse({"error": "key and value required"}, status_code=400)
    get_memory_manager().global_store(key, val, category=cat, confidence=data.get("confidence", 0.8))
    return JSONResponse({"ok": True})


@router.get("/api/memory/search")
async def memory_search(q: str = ""):
    """Search across all memory layers."""
    from ...memory.manager import get_memory_manager
    if not q:
        return HTMLResponse('<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Tapez une requête…</div>')
    mem = get_memory_manager()
    results = mem.global_search(q, limit=20)
    if not results:
        return HTMLResponse(f'<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">No results for "{q}"</div>')
    html = ""
    for r in results:
        cat = r.get("category", "")
        conf = r.get("confidence", 0)
        html += f'''<div class="mem-entry">
            <div><span class="mem-badge {cat}">{cat}</span> <span class="mem-key">{r.get("key","")}</span></div>
            <div class="mem-val">{str(r.get("value",""))[:300]}</div>
            <div class="mem-meta"><span>{int(conf*100)}% confidence</span></div>
        </div>'''
    return HTMLResponse(html)


# ── Retrospectives & Self-Improvement ────────────────────────────

@router.get("/api/retrospectives")
async def list_retrospectives(scope: str = "", limit: int = 20):
    """List retrospectives, optionally filtered by scope."""
    from ...db.migrations import get_db
    db = get_db()
    try:
        if scope:
            rows = db.execute(
                "SELECT * FROM retrospectives WHERE scope=? ORDER BY created_at DESC LIMIT ?",
                (scope, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM retrospectives ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return JSONResponse([{
            "id": r["id"], "scope": r["scope"], "scope_id": r["scope_id"],
            "successes": json.loads(r["successes"] or "[]"),
            "failures": json.loads(r["failures"] or "[]"),
            "lessons": json.loads(r["lessons"] or "[]"),
            "improvements": json.loads(r["improvements"] or "[]"),
            "metrics": json.loads(r["metrics_json"] or "{}"),
            "created_at": r["created_at"] or "",
        } for r in rows])
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.post("/api/retrospectives/generate")
async def generate_retrospective(request: Request):
    """Auto-generate a retrospective from session/ideation data using LLM."""
    from ...db.migrations import get_db
    from ...llm.client import get_llm_client, LLMMessage
    from ...memory.manager import get_memory_manager
    import uuid

    data = await request.json()
    scope = data.get("scope", "session")
    scope_id = data.get("scope_id", "")

    db = get_db()
    context_parts = []
    try:
        # Gather context based on scope
        if scope == "ideation" and scope_id:
            msgs = db.execute(
                "SELECT agent_name, role, content FROM ideation_messages WHERE session_id=? ORDER BY created_at",
                (scope_id,),
            ).fetchall()
            findings = db.execute(
                "SELECT type, text FROM ideation_findings WHERE session_id=?",
                (scope_id,),
            ).fetchall()
            context_parts.append(f"Ideation session {scope_id}:")
            for m in msgs:
                role_str = f" ({m['role']})" if "role" in m.keys() and m["role"] else ""
                context_parts.append(f"  {m['agent_name']}{role_str}: {m['content'][:200]}")
            for f in findings:
                context_parts.append(f"  Finding [{f['type']}]: {f['text']}")

        elif scope == "project" and scope_id:
            # Gather tool calls, sessions, and mission data
            tool_rows = db.execute(
                "SELECT tool_name, success, result FROM tool_calls WHERE session_id IN "
                "(SELECT id FROM sessions WHERE id LIKE ?) ORDER BY created_at DESC LIMIT 50",
                (f"%{scope_id}%",),
            ).fetchall()
            for t in tool_rows:
                status = "OK" if t["success"] else "FAIL"
                context_parts.append(f"  Tool {t['tool_name']}: {status} {(t['result'] or '')[:100]}")

        elif scope == "global":
            # Aggregate all recent tool calls + sessions
            tool_rows = db.execute(
                "SELECT tool_name, success, COUNT(*) as cnt FROM tool_calls "
                "GROUP BY tool_name, success ORDER BY cnt DESC LIMIT 30"
            ).fetchall()
            for t in tool_rows:
                status = "OK" if t["success"] else "FAIL"
                context_parts.append(f"  Tool {t['tool_name']}: {status} × {t['cnt']}")
    except Exception:
        pass
    finally:
        db.close()

    if not context_parts:
        context_parts = ["No detailed data available — generate a general retrospective about the platform usage."]

    context = "\n".join(context_parts)

    # LLM generates the retrospective
    retro_prompt = f"""Analyse cette activité et génère une rétrospective structurée.

Contexte:
{context}

Produis un JSON:
{{
  "successes": ["Ce qui a bien fonctionné (3-5 items)"],
  "failures": ["Ce qui a échoué ou peut être amélioré (2-4 items)"],
  "lessons": ["Leçons apprises, patterns identifiés (3-5 items)"],
  "improvements": ["Actions concrètes d'amélioration pour la prochaine itération (2-4 items)"]
}}

Sois CONCRET et ACTIONNABLE. Pas de généralités.
Réponds UNIQUEMENT avec le JSON."""

    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=retro_prompt)],
            system_prompt="Tu es un coach Agile expert en rétrospectives SAFe.",
            temperature=0.5, max_tokens=2048,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        retro_data = json.loads(raw)
    except Exception as e:
        retro_data = {
            "successes": ["Retrospective generation completed"],
            "failures": [f"LLM parsing issue: {str(e)[:100]}"],
            "lessons": ["Auto-retrospective needs more structured data"],
            "improvements": ["Add more instrumentation to sessions"],
        }

    retro_id = str(uuid.uuid4())[:8]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO retrospectives (id, scope, scope_id, successes, failures, lessons, improvements) VALUES (?,?,?,?,?,?,?)",
            (retro_id, scope, scope_id,
             json.dumps(retro_data.get("successes", []), ensure_ascii=False),
             json.dumps(retro_data.get("failures", []), ensure_ascii=False),
             json.dumps(retro_data.get("lessons", []), ensure_ascii=False),
             json.dumps(retro_data.get("improvements", []), ensure_ascii=False)),
        )
        db.commit()

        # Feed lessons into global memory for recursive self-improvement
        mem = get_memory_manager()
        for lesson in retro_data.get("lessons", []):
            mem.global_store(
                key=f"lesson:{scope}:{scope_id}",
                value=lesson,
                category="lesson",
                project_id=scope_id if scope == "project" else "",
                confidence=0.7,
            )
        for improvement in retro_data.get("improvements", []):
            mem.global_store(
                key=f"improvement:{scope}:{scope_id}",
                value=improvement,
                category="improvement",
                project_id=scope_id if scope == "project" else "",
                confidence=0.8,
            )
    finally:
        db.close()

    return JSONResponse({"id": retro_id, **retro_data})


@router.get("/api/projects/{project_id}/si-blueprint")
async def api_get_si_blueprint(project_id: str):
    """Read SI blueprint for a project."""
    import yaml
    bp_path = Path(__file__).resolve().parents[3] / "data" / "si_blueprints" / f"{project_id}.yaml"
    if not bp_path.exists():
        return JSONResponse({"error": "No SI blueprint found", "project_id": project_id}, status_code=404)
    with open(bp_path) as f:
        return JSONResponse(yaml.safe_load(f))


@router.put("/api/projects/{project_id}/si-blueprint")
async def api_put_si_blueprint(request: Request, project_id: str):
    """Write SI blueprint for a project."""
    import yaml
    bp_dir = Path(__file__).resolve().parents[3] / "data" / "si_blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)
    data = await request.json()
    data["project_id"] = project_id
    with open(bp_dir / f"{project_id}.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return JSONResponse({"ok": True, "project_id": project_id})


async def api_project_git(request: Request, project_id: str):
    """Git panel partial (HTMX)."""
    from ...projects.manager import get_project_store
    from ...projects import git_service
    project = get_project_store().get(project_id)
    if not project:
        return HTMLResponse("")
    git = git_service.get_status(project.path) if project.has_git else None
    commits = git_service.get_log(project.path, 10) if project.has_git else []
    changes = git_service.get_changes(project.path) if project.has_git else []
    return _templates(request).TemplateResponse("partials/git_panel.html", {
        "request": request, "git": git, "commits": commits, "changes": changes,
    })


@router.get("/api/projects/{project_id}/tasks", response_class=HTMLResponse)
async def api_project_tasks(request: Request, project_id: str):
    """Task panel partial (HTMX)."""
    from ...projects import factory_tasks
    tasks = factory_tasks.get_task_summary(project_id)
    recent = factory_tasks.get_recent_tasks(project_id, 15)
    return _templates(request).TemplateResponse("partials/task_panel.html", {
        "request": request, "tasks": tasks, "recent_tasks": recent,
    })


# ── DORA Metrics ─────────────────────────────────────────────────

@router.get("/metrics", response_class=HTMLResponse)
async def dora_dashboard_page(request: Request):
    """DORA Metrics dashboard page."""
    from ...metrics.dora import get_dora_metrics
    from ...projects.manager import get_project_store

    projects = get_project_store().list_all()
    project_id = request.query_params.get("project", "")
    period = int(request.query_params.get("period", "30"))

    dora = get_dora_metrics()
    summary = dora.summary(project_id, period)
    trend = dora.trend(project_id, weeks=12)

    return _templates(request).TemplateResponse("dora_dashboard.html", {
        "request": request,
        "page_title": "DORA Metrics",
        "projects": projects,
        "selected_project": project_id,
        "period": period,
        "dora": summary,
        "trend": trend,
    })


@router.get("/api/metrics/dora/{project_id}")
async def dora_api(request: Request, project_id: str):
    """DORA metrics JSON API."""
    from ...metrics.dora import get_dora_metrics
    period = int(request.query_params.get("period", "30"))
    pid = "" if project_id == "all" else project_id
    return JSONResponse(get_dora_metrics().summary(pid, period))


@router.get("/api/epics/{epic_id}/features")
async def epic_features(epic_id: str):
    """List features for an epic."""
    from ...db.migrations import get_db
    db = get_db()
    rows = db.execute("""
        SELECT id, name, description, status, story_points, assigned_to, created_at
        FROM features WHERE epic_id = ? ORDER BY
        CASE status WHEN 'in_progress' THEN 0 WHEN 'backlog' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
        priority ASC, name ASC
    """, (epic_id,)).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.get("/api/monitoring/live")
async def monitoring_live(hours: int = 24):
    """Live monitoring data: system, LLM, agents, missions, memory.
    Cached for 5 seconds to avoid hammering DB on rapid polling."""
    import os
    import psutil
    import time as _time

    hours = max(1, min(hours, 8760))

    # ── TTL cache (5s) ──
    cache = getattr(monitoring_live, "_cache", None)
    now = _time.monotonic()
    if cache and cache.get("hours") == hours and now - cache.get("ts", 0) < 5:
        return JSONResponse(cache["data"])

    # System metrics — primed at module load, interval=0 measures since last call
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    cpu_percent = process.cpu_percent(interval=0)
    sys_cpu = psutil.cpu_percent(interval=0)
    sys_mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    system = {
        "pid": os.getpid(),
        "cpu_percent": round(cpu_percent, 1),
        "mem_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "mem_vms_mb": round(mem_info.vms / 1024 / 1024, 1),
        "sys_cpu_percent": round(sys_cpu, 1),
        "sys_mem_total_gb": round(sys_mem.total / 1024**3, 1),
        "sys_mem_used_gb": round(sys_mem.used / 1024**3, 1),
        "sys_mem_percent": round(sys_mem.percent, 1),
        "disk_total_gb": round(disk.total / 1024**3, 1),
        "disk_used_gb": round(disk.used / 1024**3, 1),
        "disk_free_gb": round(disk.free / 1024**3, 1),
        "disk_percent": round(disk.percent, 1),
        "uptime_seconds": round(import_time() - process.create_time()),
        "threads": process.num_threads(),
        "open_files": len(process.open_files()),
    }

    # LLM stats
    try:
        from ...llm.observability import get_tracer
        llm = get_tracer().stats(hours=hours)
        # Hourly breakdown for chart
        from ...db.migrations import get_db
        db = get_db()
        # Use day grouping for periods > 48h, else hourly
        if hours > 48:
            hourly = db.execute(f"""
                SELECT strftime('%m-%d', created_at) as hour,
                       COUNT(*) as calls,
                       COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,
                       COALESCE(SUM(cost_usd), 0) as cost
                FROM llm_traces
                WHERE created_at > datetime('now', '-{hours} hours')
                GROUP BY hour ORDER BY hour
            """).fetchall()
        else:
            hourly = db.execute(f"""
                SELECT strftime('%H', created_at) as hour,
                       COUNT(*) as calls,
                       COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,
                       COALESCE(SUM(cost_usd), 0) as cost
                FROM llm_traces
                WHERE created_at > datetime('now', '-{hours} hours')
                GROUP BY hour ORDER BY hour
            """).fetchall()
        llm["hourly"] = [dict(r) for r in hourly]
        db.close()
    except Exception:
        llm = {"total_calls": 0, "total_tokens_in": 0, "total_tokens_out": 0,
               "total_cost_usd": 0, "avg_duration_ms": 0, "error_count": 0,
               "by_provider": [], "by_agent": [], "hourly": []}

    # Active agents (runtime from AgentLoopManager + historical from DB — single connection)
    agents_runtime = {"active": 0, "loops": 0}
    agents_historical = {"total_registered": 0, "participated": 0, "sessions_with_agents": 0}
    missions = []; sessions = []; sprints = []; features = []
    msg_count = {"cnt": 0}; msg_total = {"cnt": 0}
    try:
        from ...agents.loop import get_loop_manager
        mgr = get_loop_manager()
        active_loops = {k: {"status": v.status, "agent_id": v.agent_id}
                        for k, v in mgr._loops.items() if v.status in ("thinking", "acting")}
        agents_runtime = {"active": len(active_loops), "loops": len(mgr._loops)}
    except Exception:
        active_loops = {}
    try:
        from ...db.migrations import get_db
        adb = get_db()
        agents_historical["total_registered"] = adb.execute(
            "SELECT COUNT(*) FROM agents").fetchone()[0]
        agents_historical["participated"] = adb.execute(
            "SELECT COUNT(DISTINCT from_agent) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'").fetchone()[0]
        agents_historical["sessions_with_agents"] = adb.execute(
            "SELECT COUNT(DISTINCT session_id) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'").fetchone()[0]
        agents_historical["total_messages"] = adb.execute(
            "SELECT COUNT(*) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'").fetchone()[0]
        top = adb.execute(
            "SELECT from_agent, COUNT(*) as cnt FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system' GROUP BY from_agent ORDER BY cnt DESC LIMIT 5").fetchall()
        agents_historical["top_agents"] = [{"agent": r[0], "messages": r[1]} for r in top]
        # Reuse same connection for missions/sessions/sprints/features/messages
        missions = adb.execute("SELECT status, COUNT(*) as cnt FROM missions GROUP BY status").fetchall()
        sessions = adb.execute("SELECT status, COUNT(*) as cnt FROM sessions GROUP BY status").fetchall()
        sprints = adb.execute("SELECT status, COUNT(*) as cnt FROM sprints GROUP BY status").fetchall()
        features = adb.execute("SELECT status, COUNT(*) as cnt FROM features GROUP BY status").fetchall()
        msg_count = adb.execute("SELECT COUNT(*) as cnt FROM messages WHERE timestamp > datetime('now', '-24 hours')").fetchone()
        msg_total = adb.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
        adb.close()
    except Exception:
        pass

    # Memory stats
    try:
        from ...memory.manager import get_memory_manager
        mem_stats = get_memory_manager().stats()
    except Exception:
        mem_stats = {}

    # Projects count
    try:
        from ...projects.manager import get_project_store
        projects = get_project_store().list_all()
        project_count = len(projects)
    except Exception:
        projects = []
        project_count = 0

    # SSE connections (from bus)
    try:
        from ...a2a.bus import get_bus
        bus = get_bus()
        sse_connections = len(getattr(bus, '_sse_listeners', []))
    except Exception:
        sse_connections = 0

    # ── Database stats (single pass — no N+1) ──
    db_stats = {}
    try:
        from ...db.migrations import get_db
        db = get_db()
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()]
        # Single query for all table counts via UNION ALL
        if tables:
            union = " UNION ALL ".join(
                f"SELECT '{t}' as tbl, COUNT(*) as cnt FROM [{t}]" for t in tables
            )
            rows = db.execute(union).fetchall()
            table_counts = {r[0]: r[1] for r in rows}
            total_rows = sum(table_counts.values())
        else:
            table_counts = {}
            total_rows = 0
        # DB file size
        db_path = str(db.execute("PRAGMA database_list").fetchone()[2]) if db.execute("PRAGMA database_list").fetchone() else ""
        db_size_mb = 0
        if db_path:
            import pathlib
            p = pathlib.Path(db_path)
            if p.exists():
                db_size_mb = round(p.stat().st_size / 1024 / 1024, 2)
                # Include WAL
                wal = p.with_suffix('.db-wal')
                if wal.exists():
                    db_size_mb += round(wal.stat().st_size / 1024 / 1024, 2)
        # Page stats
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        page_count = db.execute("PRAGMA page_count").fetchone()[0]
        freelist = db.execute("PRAGMA freelist_count").fetchone()[0]
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        db.close()
        db_stats = {
            "size_mb": db_size_mb,
            "tables": len(tables),
            "total_rows": total_rows,
            "top_tables": sorted(table_counts.items(), key=lambda x: -x[1])[:10],
            "page_size": page_size,
            "page_count": page_count,
            "freelist_pages": freelist,
            "journal_mode": journal_mode,
        }
    except Exception as e:
        db_stats = {"error": str(e)}

    # ── Vector store stats ──
    vector_stats = {}
    try:
        from ...db.migrations import get_db
        db = get_db()
        vr = db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN embedding IS NOT NULL AND embedding != '' THEN 1 ELSE 0 END) as embedded,
                   COUNT(DISTINCT scope_id) as scopes
            FROM memory_vectors
        """).fetchone()
        vector_stats = {
            "total_vectors": vr["total"] if vr else 0,
            "with_embedding": vr["embedded"] if vr else 0,
            "scopes": vr["scopes"] if vr else 0,
            "dimension": 1536,
            "provider": os.environ.get("EMBEDDING_ENDPOINT", "azure-openai")[:60],
        }
        db.close()
    except Exception:
        vector_stats = {"total_vectors": 0, "with_embedding": 0, "scopes": 0}

    # ── MCP server status (unified SF server) ──
    mcp_status = {}
    try:
        import urllib.request
        try:
            r = urllib.request.urlopen("http://127.0.0.1:9501/health", timeout=2)
            mcp_sf = json.loads(r.read().decode())
            mcp_status["mcp_sf"] = {"status": "up", "port": 9501, **mcp_sf}
        except Exception:
            mcp_status["mcp_sf"] = {"status": "down", "port": 9501}

        # RLM Cache DB
        import pathlib
        rlm_cache = pathlib.Path(os.environ.get("DATA_DIR", "data")) / "rlm_cache.db"
        if not rlm_cache.exists():
            rlm_cache = pathlib.Path(__file__).resolve().parents[3] / "data" / "rlm_cache.db"
        if rlm_cache.exists():
            import sqlite3
            cdb = sqlite3.connect(str(rlm_cache))
            cdb.row_factory = sqlite3.Row
            try:
                cc = cdb.execute("SELECT COUNT(*) as cnt FROM rlm_cache").fetchone()
                # Anonymization stats from RLM cache
                anon_stats = {}
                try:
                    anon_rows = cdb.execute(
                        "SELECT COALESCE(scope, 'default') as scope, COUNT(*) as cnt "
                        "FROM rlm_cache GROUP BY scope"
                    ).fetchall()
                    anon_stats = {r["scope"]: r["cnt"] for r in anon_rows}
                except Exception:
                    pass
                mcp_status["rlm_cache"] = {
                    "status": "ok",
                    "entries": cc["cnt"] if cc else 0,
                    "size_mb": round(rlm_cache.stat().st_size / 1024 / 1024, 2),
                    "by_scope": anon_stats,
                }
            except Exception:
                mcp_status["rlm_cache"] = {"status": "empty", "entries": 0}
            cdb.close()
    except Exception as e:
        mcp_status["error"] = str(e)

    # ── Incidents stats ──
    incidents = {}
    try:
        from ...db.migrations import get_db
        db = get_db()
        inc_rows = db.execute("""
            SELECT severity, status, COUNT(*) as cnt
            FROM platform_incidents
            GROUP BY severity, status
        """).fetchall()
        open_count = sum(r["cnt"] for r in inc_rows if r["status"] == "open")
        total_count = sum(r["cnt"] for r in inc_rows)
        incidents = {"open": open_count, "total": total_count, "by_severity_status": [dict(r) for r in inc_rows]}
        db.close()
    except Exception:
        incidents = {"open": 0, "total": 0}

    # ── Live metrics from collector ──
    metrics_snapshot = {}
    try:
        from ...metrics.collector import get_collector
        metrics_snapshot = get_collector().snapshot()
    except Exception:
        pass

    # ── Docker containers (via Docker socket API) ──
    docker_info = []
    docker_system = {}
    try:
        import pathlib
        sock_path = "/var/run/docker.sock"
        if pathlib.Path(sock_path).exists():
            import http.client, urllib.parse

            class DockerSocket(http.client.HTTPConnection):
                def __init__(self):
                    super().__init__("localhost")
                def connect(self):
                    import socket as _sock
                    self.sock = _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM)
                    self.sock.connect(sock_path)
                    self.sock.settimeout(5)

            # --- Container list ---
            conn = DockerSocket()
            conn.request("GET", "/containers/json?all=true")
            resp = conn.getresponse()
            containers_raw = []
            if resp.status == 200:
                containers_raw = json.loads(resp.read().decode())
            conn.close()

            for c in containers_raw:
                cid = c.get("Id", "")[:12]
                name = (c.get("Names", ["/?"]) or ["/?"]) [0].lstrip("/")
                state = c.get("State", "?")
                status = c.get("Status", "?")
                image = (c.get("Image", "?") or "?")[:40]
                ports_raw = c.get("Ports", [])
                ports_str = ", ".join(
                    f"{p.get('PublicPort', '')}→{p.get('PrivatePort', '')}"
                    for p in ports_raw if p.get("PublicPort")
                ) if ports_raw else ""
                restarts = c.get("RestartCount", 0) if c.get("HostConfig", {}).get("RestartPolicy") else 0
                created = c.get("Created", 0)

                # Per-container stats (stream=false = single snapshot)
                cpu_pct = 0.0
                mem_mb = 0.0
                mem_limit_mb = 0.0
                net_rx_mb = 0.0
                net_tx_mb = 0.0
                pids = 0
                if state == "running":
                    try:
                        sc = DockerSocket()
                        sc.request("GET", f"/containers/{cid}/stats?stream=false")
                        sr = sc.getresponse()
                        if sr.status == 200:
                            st = json.loads(sr.read().decode())
                            # CPU %
                            cpu_delta = st.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - \
                                        st.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                            sys_delta = st.get("cpu_stats", {}).get("system_cpu_usage", 0) - \
                                        st.get("precpu_stats", {}).get("system_cpu_usage", 0)
                            ncpus = st.get("cpu_stats", {}).get("online_cpus", 1) or 1
                            if sys_delta > 0 and cpu_delta > 0:
                                cpu_pct = round((cpu_delta / sys_delta) * ncpus * 100, 1)
                            # Memory
                            mem_usage = st.get("memory_stats", {}).get("usage", 0)
                            mem_cache = st.get("memory_stats", {}).get("stats", {}).get("cache", 0)
                            mem_mb = round((mem_usage - mem_cache) / 1048576, 1)
                            mem_limit_mb = round(st.get("memory_stats", {}).get("limit", 0) / 1048576, 0)
                            # Network I/O
                            nets = st.get("networks", {})
                            for iface in nets.values():
                                net_rx_mb += iface.get("rx_bytes", 0) / 1048576
                                net_tx_mb += iface.get("tx_bytes", 0) / 1048576
                            net_rx_mb = round(net_rx_mb, 1)
                            net_tx_mb = round(net_tx_mb, 1)
                            pids = st.get("pids_stats", {}).get("current", 0)
                        sc.close()
                    except Exception:
                        pass

                docker_info.append({
                    "name": name, "id": cid, "status": status, "state": state,
                    "image": image, "ports": ports_str, "restarts": restarts,
                    "cpu_pct": cpu_pct, "mem_mb": mem_mb, "mem_limit_mb": mem_limit_mb,
                    "net_rx_mb": net_rx_mb, "net_tx_mb": net_tx_mb, "pids": pids,
                    "created": created,
                })

            # --- Docker system info (images, disk) ---
            try:
                conn2 = DockerSocket()
                conn2.request("GET", "/info")
                resp2 = conn2.getresponse()
                if resp2.status == 200:
                    info = json.loads(resp2.read().decode())
                    docker_system["containers_total"] = info.get("Containers", 0)
                    docker_system["containers_running"] = info.get("ContainersRunning", 0)
                    docker_system["containers_stopped"] = info.get("ContainersStopped", 0)
                    docker_system["images"] = info.get("Images", 0)
                    docker_system["server_version"] = info.get("ServerVersion", "?")
                    docker_system["os"] = info.get("OperatingSystem", "?")
                    docker_system["kernel"] = info.get("KernelVersion", "?")
                    docker_system["cpus"] = info.get("NCPU", 0)
                    docker_system["mem_total_gb"] = round(info.get("MemTotal", 0) / 1073741824, 1)
                conn2.close()
            except Exception:
                pass

            # --- Docker disk usage ---
            try:
                conn3 = DockerSocket()
                conn3.request("GET", "/system/df")
                resp3 = conn3.getresponse()
                if resp3.status == 200:
                    df = json.loads(resp3.read().decode())
                    # Images disk
                    img_size = sum(i.get("Size", 0) for i in df.get("Images", []))
                    img_shared = sum(i.get("SharedSize", 0) for i in df.get("Images", []))
                    docker_system["images_size_gb"] = round(img_size / 1073741824, 2)
                    docker_system["images_shared_gb"] = round(img_shared / 1073741824, 2)
                    # Containers disk
                    ct_size = sum(c.get("SizeRw", 0) for c in df.get("Containers", []))
                    docker_system["containers_disk_mb"] = round(ct_size / 1048576, 1)
                    # Volumes
                    vols = df.get("Volumes", [])
                    docker_system["volumes_count"] = len(vols)
                    vol_size = sum(v.get("UsageData", {}).get("Size", 0) for v in vols)
                    docker_system["volumes_size_gb"] = round(vol_size / 1073741824, 2)
                    # Build cache
                    bc = df.get("BuildCache", [])
                    bc_size = sum(b.get("Size", 0) for b in bc)
                    docker_system["build_cache_gb"] = round(bc_size / 1073741824, 2)
                    docker_system["total_disk_gb"] = round(
                        (img_size + ct_size + vol_size + bc_size) / 1073741824, 2
                    )
                conn3.close()
            except Exception:
                pass
    except Exception:
        pass

    # ── Git info ──
    git_info = {}
    try:
        import subprocess, pathlib
        for git_dir in ["/app", "/opt/macaron", os.environ.get("GIT_DIR", "")]:
            if not git_dir or not pathlib.Path(git_dir).exists():
                continue
            r = subprocess.run(["git", "log", "--oneline", "-5", "--no-decorate"],
                               capture_output=True, text=True, timeout=5, cwd=git_dir)
            if r.returncode == 0 and r.stdout.strip():
                git_info["recent_commits"] = [
                    {"hash": line[:7], "message": line[8:]}
                    for line in r.stdout.strip().split("\n") if line
                ]
                r2 = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                    capture_output=True, text=True, timeout=5, cwd=git_dir)
                if r2.returncode == 0:
                    git_info["branch"] = r2.stdout.strip()
                r3 = subprocess.run(["git", "log", "-1", "--format=%ci"],
                                    capture_output=True, text=True, timeout=5, cwd=git_dir)
                if r3.returncode == 0:
                    git_info["last_commit_time"] = r3.stdout.strip()
                break
        if not git_info:
            import pathlib as _pl
            ver = _pl.Path("/app/VERSION")
            if ver.exists():
                git_info["branch"] = ver.read_text().strip()
    except Exception:
        pass

    # ── Mission phase durations (from mission_runs.phases_json) ──
    phase_stats = []
    try:
        from ...db.migrations import get_db
        db = get_db()
        runs = db.execute("""
            SELECT phases_json, status, current_phase
            FROM mission_runs WHERE phases_json IS NOT NULL
        """).fetchall()
        phase_counts = {}
        for run in runs:
            try:
                phases = json.loads(run["phases_json"]) if run["phases_json"] else []
                for p in phases:
                    key = p.get("phase_name") or p.get("name", "?")
                    st = p.get("status", "pending")
                    k = (key, st)
                    phase_counts[k] = phase_counts.get(k, 0) + 1
            except Exception:
                pass
        phase_stats = [{"phase_name": k[0], "status": k[1], "cnt": v}
                       for k, v in sorted(phase_counts.items())]
        db.close()
    except Exception:
        pass

    # ── Azure infrastructure ──
    azure_infra = {"vm": {}, "backup": {}, "costs": {}, "servers": []}
    try:
        azure_infra["vm"] = {
            "name": "vm-macaron",
            "ip": "4.233.64.30",
            "rg": "RG-MACARON",
            "region": "francecentral",
            "size": "Standard_B2ms",
            "os": "Ubuntu 24.04",
            "disk_gb": 64,
        }
        # Backup info from config
        azure_infra["backup"] = {
            "storage_account": "macaronbackups",
            "replication": "GRS (francesouth)",
            "containers": ["db-backups", "pg-dumps", "secrets"],
            "sqlite_dbs": 7,
            "retention": {"daily": "90d", "weekly": "365d", "monthly": "forever"},
        }
        # Servers running on VM (probe ports)
        import socket
        def _port_up(port, host="127.0.0.1"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return "up"
            except Exception:
                return "down"
        azure_infra["servers"] = [
            {"name": "Platform (uvicorn)", "port": 8090, "status": "up"},
            {"name": "MCP SF (unified)", "port": 9501, "status": "up" if mcp_status.get("mcp_sf", {}).get("status") in ("up", "ok") else "down"},
            {"name": "PostgreSQL", "port": 5432, "status": _port_up(5432)},
            {"name": "Nginx (reverse proxy)", "port": 80, "status": _port_up(80)},
        ]
        # LLM cost summary by provider type (Azure vs non-Azure)
        azure_cost = 0.0
        other_cost = 0.0
        for p in llm.get("by_provider", []):
            prov = p.get("provider", "")
            cost = p.get("cost_usd", 0)
            if "azure" in prov.lower():
                azure_cost += cost
            else:
                other_cost += cost
        azure_infra["costs"] = {
            "azure_llm_usd": round(azure_cost, 4),
            "other_llm_usd": round(other_cost, 4),
            "total_llm_usd": round(azure_cost + other_cost, 4),
            # Azure infra monthly estimates (Standard_B2ms + PG B1ms + storage)
            "vm_monthly_usd": 60.74,        # Standard_B2ms francecentral
            "disk_monthly_usd": 9.50,        # P6 Premium SSD 64GB
            "pg_monthly_usd": 12.34,         # PG B1ms 1vCPU/2GB
            "storage_monthly_usd": 2.50,     # Blob GRS ~50GB
            "total_infra_monthly_usd": 85.08,
        }
    except Exception:
        pass

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "hours": hours,
        "system": system,
        "llm": llm,
        "agents": {
            "active": agents_runtime["active"],
            "loops": agents_runtime["loops"],
            "registered": agents_historical.get("total_registered", 0),
            "participated": agents_historical.get("participated", 0),
            "sessions_with_agents": agents_historical.get("sessions_with_agents", 0),
            "total_messages": agents_historical.get("total_messages", 0),
            "top_agents": agents_historical.get("top_agents", []),
        },
        "missions": {s["status"]: s["cnt"] for s in missions},
        "sessions": {s["status"]: s["cnt"] for s in sessions},
        "sprints": {s["status"]: s["cnt"] for s in sprints},
        "features": {s["status"]: s["cnt"] for s in features},
        "messages": {
            "last_24h": msg_count["cnt"] if msg_count else 0,
            "total": msg_total["cnt"] if msg_total else 0,
        },
        "memory": mem_stats,
        "projects": project_count,
        "sse_connections": sse_connections,
        "database": db_stats,
        "vectors": vector_stats,
        "mcp": mcp_status,
        "incidents": incidents,
        "requests": metrics_snapshot.get("http", {}),
        "mcp_calls": metrics_snapshot.get("mcp", {}),
        "anonymization": metrics_snapshot.get("anonymization", {}),
        "llm_costs": metrics_snapshot.get("llm_costs", {}),
        "azure": azure_infra,
        "docker": docker_info,
        "docker_system": docker_system,
        "git": git_info,
        "phase_stats": phase_stats,
    }

    # Store in cache
    monitoring_live._cache = {"data": result, "hours": hours, "ts": _time.monotonic()}
    return JSONResponse(result)


def import_time():
    """Get current time as epoch."""
    import time
    return time.time()


# ── RBAC ─────────────────────────────────────────────────────────

@router.get("/api/rbac/agent/{agent_id}")
async def rbac_agent_permissions(agent_id: str):
    """Get RBAC permissions for an agent."""
    from ...rbac import agent_permissions_summary, get_agent_category
    return JSONResponse({
        "agent_id": agent_id,
        "category": get_agent_category(agent_id),
        "permissions": agent_permissions_summary(agent_id),
    })


@router.get("/api/rbac/check")
async def rbac_check(request: Request):
    """Check a specific permission. Query: ?actor=agent_id&type=agent&artifact=code&action=create"""
    from ...rbac import check_agent_permission, check_human_permission
    actor = request.query_params.get("actor", "")
    actor_type = request.query_params.get("type", "agent")
    artifact = request.query_params.get("artifact", "")
    action = request.query_params.get("action", "")

    if actor_type == "agent":
        ok, reason = check_agent_permission(actor, artifact, action)
    else:
        ok, reason = check_human_permission(actor, artifact, action)

    return JSONResponse({"allowed": ok, "reason": reason})


# ── Incidents ────────────────────────────────────────────────────

@router.get("/api/incidents/stats")
async def incidents_stats():
    """Incident counts by severity and status."""
    from ...db.migrations import get_db
    db = get_db()
    try:
        by_severity = db.execute(
            "SELECT severity, COUNT(*) as cnt FROM platform_incidents GROUP BY severity"
        ).fetchall()
        by_status = db.execute(
            "SELECT status, COUNT(*) as cnt FROM platform_incidents GROUP BY status"
        ).fetchall()
        recent = db.execute(
            "SELECT id, title, severity, status, source, error_type, created_at "
            "FROM platform_incidents ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        return JSONResponse({
            "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
            "by_status": {r["status"]: r["cnt"] for r in by_status},
            "recent": [dict(r) for r in recent],
        })
    except Exception:
        return JSONResponse({"by_severity": {}, "by_status": {}, "recent": []})
    finally:
        db.close()


@router.get("/api/incidents")
async def list_incidents(request: Request):
    """List incidents, optionally filtered by status/severity."""
    from ...db.migrations import get_db
    status = request.query_params.get("status", "")
    severity = request.query_params.get("severity", "")
    limit = int(request.query_params.get("limit", "50"))
    db = get_db()
    try:
        query = "SELECT * FROM platform_incidents WHERE 1=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        return JSONResponse([dict(r) for r in rows])
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.post("/api/incidents")
async def create_incident(request: Request):
    """Create a manual incident."""
    import uuid
    from ...db.migrations import get_db
    data = await request.json()
    title = data.get("title", "")
    if not title:
        return JSONResponse({"error": "title required"}, status_code=400)
    inc_id = str(uuid.uuid4())[:12]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO platform_incidents (id, title, severity, status, source, error_type, error_detail, mission_id, agent_id) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (inc_id, title, data.get("severity", "P3"), data.get("source", "manual"),
             data.get("error_type", ""), data.get("error_detail", ""),
             data.get("mission_id", ""), data.get("agent_id", "")),
        )
        db.commit()
        return JSONResponse({"id": inc_id, "title": title})
    finally:
        db.close()


@router.patch("/api/incidents/{incident_id}")
async def update_incident(request: Request, incident_id: str):
    """Update incident status (resolve, close)."""
    from ...db.migrations import get_db
    data = await request.json()
    db = get_db()
    try:
        updates = []
        params = []
        if "status" in data:
            updates.append("status=?")
            params.append(data["status"])
            if data["status"] in ("resolved", "closed"):
                updates.append("resolved_at=CURRENT_TIMESTAMP")
        if "resolution" in data:
            updates.append("resolution=?")
            params.append(data["resolution"])
        if not updates:
            return JSONResponse({"error": "nothing to update"}, status_code=400)
        params.append(incident_id)
        db.execute(f"UPDATE platform_incidents SET {', '.join(updates)} WHERE id=?", params)
        db.commit()
        return JSONResponse({"ok": True, "id": incident_id})
    finally:
        db.close()


# ── Auto-Heal API ────────────────────────────────────────────────────

@router.get("/api/autoheal/stats")
async def autoheal_stats():
    """Auto-heal engine statistics."""
    from ...ops.auto_heal import get_autoheal_stats
    return JSONResponse(get_autoheal_stats())


@router.post("/api/autoheal/trigger")
async def autoheal_trigger():
    """Manually trigger one auto-heal cycle."""
    from ...ops.auto_heal import heal_cycle
    try:
        await heal_cycle()
        from ...ops.auto_heal import get_autoheal_stats
        return JSONResponse({"ok": True, **get_autoheal_stats()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)




# ── i18n ─────────────────────────────────────────────────────────────
@router.get("/api/set-lang/{lang}")
async def set_language(lang: str, request: Request):
    """Switch UI language. Sets cookie and redirects back."""
    from ...i18n import SUPPORTED_LANGS
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie("lang", lang, max_age=365 * 86400, httponly=False, samesite="lax")
    return response


@router.get("/api/i18n/{lang}.json")
async def i18n_catalog(lang: str):
    """Serve translation catalog for client-side JS."""
    from ...i18n import SUPPORTED_LANGS, _catalog, _load_catalog
    if not _catalog:
        _load_catalog()
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return JSONResponse(_catalog.get(lang, {}))
