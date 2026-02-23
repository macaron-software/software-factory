"""Web routes — Pure API endpoints (memory, LLM, RBAC, DORA, retrospectives)."""

from __future__ import annotations

import html as html_mod
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)

from ..schemas import (
    AutoHealStats,
    DoraMetrics,
    FeatureOut,
    HealthResponse,
    IncidentOut,
    IncidentStats,
    LlmStatsResponse,
    MemoryStats,
    OkResponse,
)
from .helpers import (
    _templates,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Prime psutil cpu_percent so interval=0 returns meaningful values
try:
    import os as _os

    import psutil as _ps

    _ps.Process(_os.getpid()).cpu_percent()
    _ps.cpu_percent()
except Exception:
    pass

# ── Health ────────────────────────────────────────────────────────


@router.get("/api/health", responses={200: {"model": HealthResponse}})
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


@router.get("/api/memory/stats", responses={200: {"model": MemoryStats}})
async def memory_stats():
    """Memory layer statistics."""
    from ...memory.manager import get_memory_manager

    return JSONResponse(get_memory_manager().stats())


# ── LLM Observability ──────────────────────────────────────────


@router.get("/api/llm/stats", responses={200: {"model": LlmStatsResponse}})
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
    import shutil

    from ...tools.sandbox import SANDBOX_ENABLED, SANDBOX_IMAGE, SANDBOX_MEMORY, SANDBOX_NETWORK

    docker_available = shutil.which("docker") is not None
    return JSONResponse(
        {
            "enabled": SANDBOX_ENABLED,
            "docker_available": docker_available,
            "default_image": SANDBOX_IMAGE,
            "network": SANDBOX_NETWORK,
            "memory_limit": SANDBOX_MEMORY,
        }
    )


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
    get_memory_manager().global_store(
        key, val, category=cat, confidence=data.get("confidence", 0.8)
    )
    return JSONResponse({"ok": True})


@router.get("/api/memory/search")
async def memory_search(q: str = ""):
    """Search across all memory layers."""
    from ...memory.manager import get_memory_manager

    if not q:
        return HTMLResponse(
            '<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Tapez une requête…</div>'
        )
    mem = get_memory_manager()
    results = mem.global_search(q, limit=20)
    if not results:
        return HTMLResponse(
            f'<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">No results for "{html_mod.escape(q)}"</div>'
        )
    html = ""
    for r in results:
        cat = r.get("category", "")
        conf = r.get("confidence", 0)
        html += f"""<div class="mem-entry">
            <div><span class="mem-badge {cat}">{cat}</span> <span class="mem-key">{r.get("key", "")}</span></div>
            <div class="mem-val">{str(r.get("value", ""))[:300]}</div>
            <div class="mem-meta"><span>{int(conf * 100)}% confidence</span></div>
        </div>"""
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
        return JSONResponse(
            [
                {
                    "id": r["id"],
                    "scope": r["scope"],
                    "scope_id": r["scope_id"],
                    "successes": json.loads(r["successes"] or "[]"),
                    "failures": json.loads(r["failures"] or "[]"),
                    "lessons": json.loads(r["lessons"] or "[]"),
                    "improvements": json.loads(r["improvements"] or "[]"),
                    "metrics": json.loads(r["metrics_json"] or "{}"),
                    "created_at": r["created_at"] or "",
                }
                for r in rows
            ]
        )
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.post("/api/retrospectives/generate")
async def generate_retrospective(request: Request):
    """Auto-generate a retrospective from session/ideation data using LLM."""
    import uuid

    from ...db.migrations import get_db
    from ...llm.client import LLMMessage, get_llm_client
    from ...memory.manager import get_memory_manager

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
                context_parts.append(
                    f"  Tool {t['tool_name']}: {status} {(t['result'] or '')[:100]}"
                )

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
        context_parts = [
            "No detailed data available — generate a general retrospective about the platform usage."
        ]

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
            temperature=0.5,
            max_tokens=2048,
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
            (
                retro_id,
                scope,
                scope_id,
                json.dumps(retro_data.get("successes", []), ensure_ascii=False),
                json.dumps(retro_data.get("failures", []), ensure_ascii=False),
                json.dumps(retro_data.get("lessons", []), ensure_ascii=False),
                json.dumps(retro_data.get("improvements", []), ensure_ascii=False),
            ),
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
        return JSONResponse(
            {"error": "No SI blueprint found", "project_id": project_id}, status_code=404
        )
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
    from ...projects import git_service
    from ...projects.manager import get_project_store

    project = get_project_store().get(project_id)
    if not project:
        return HTMLResponse("")
    git = git_service.get_status(project.path) if project.has_git else None
    commits = git_service.get_log(project.path, 10) if project.has_git else []
    changes = git_service.get_changes(project.path) if project.has_git else []
    return _templates(request).TemplateResponse(
        "partials/git_panel.html",
        {
            "request": request,
            "git": git,
            "commits": commits,
            "changes": changes,
        },
    )


@router.get("/api/projects/{project_id}/tasks", response_class=HTMLResponse)
async def api_project_tasks(request: Request, project_id: str):
    """Task panel partial (HTMX)."""
    from ...projects import factory_tasks

    tasks = factory_tasks.get_task_summary(project_id)
    recent = factory_tasks.get_recent_tasks(project_id, 15)
    return _templates(request).TemplateResponse(
        "partials/task_panel.html",
        {
            "request": request,
            "tasks": tasks,
            "recent_tasks": recent,
        },
    )


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

    return _templates(request).TemplateResponse(
        "dora_dashboard.html",
        {
            "request": request,
            "page_title": "DORA Metrics",
            "projects": projects,
            "selected_project": project_id,
            "period": period,
            "dora": summary,
            "trend": trend,
        },
    )


@router.get("/api/metrics/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    import os

    import psutil

    from ...metrics.collector import get_collector

    c = get_collector()
    snap = c.snapshot()
    proc = psutil.Process(os.getpid())
    lines = []

    def _m(name, value, help_text="", labels=""):
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
        lbl = f"{{{labels}}}" if labels else ""
        lines.append(f"{name}{lbl} {value}")

    _m("macaron_uptime_seconds", snap["uptime_seconds"], "Platform uptime")
    _m("macaron_http_requests_total", snap["http"]["total_requests"], "Total HTTP requests")
    _m("macaron_http_errors_total", snap["http"]["total_errors"], "Total HTTP errors")
    _m("macaron_http_avg_ms", snap["http"]["avg_ms"], "Average HTTP latency ms")
    for code, cnt in snap["http"].get("by_status", {}).items():
        _m("macaron_http_status", cnt, labels=f'code="{code}"')
    _m("macaron_mcp_calls_total", snap["mcp"]["total_calls"], "Total MCP tool calls")
    _m("macaron_process_cpu_percent", round(proc.cpu_percent(interval=0), 1), "Process CPU")
    mem = proc.memory_info()
    _m("macaron_process_rss_bytes", mem.rss, "Process RSS bytes")
    _m("macaron_process_threads", proc.num_threads(), "Process threads")
    for provider, stats in snap.get("llm", {}).get("by_provider", {}).items():
        _m("macaron_llm_calls", stats.get("calls", 0), labels=f'provider="{provider}"')
        _m("macaron_llm_cost_usd", stats.get("cost_usd", 0), labels=f'provider="{provider}"')

    return "\n".join(lines) + "\n"


@router.get("/api/metrics/dora/{project_id}", responses={200: {"model": DoraMetrics}})
async def dora_api(request: Request, project_id: str):
    """DORA metrics JSON API."""
    from ...metrics.dora import get_dora_metrics

    period = int(request.query_params.get("period", "30"))
    pid = "" if project_id == "all" else project_id
    return JSONResponse(get_dora_metrics().summary(pid, period))


@router.get("/api/epics/{epic_id}/features", responses={200: {"model": list[FeatureOut]}})
async def epic_features(epic_id: str):
    """List features for an epic."""
    from ...db.migrations import get_db

    db = get_db()
    rows = db.execute(
        """
        SELECT id, name, description, status, story_points, assigned_to, created_at
        FROM features WHERE epic_id = ? ORDER BY
        CASE status WHEN 'in_progress' THEN 0 WHEN 'backlog' THEN 1 WHEN 'done' THEN 2 ELSE 3 END,
        priority ASC, name ASC
    """,
        (epic_id,),
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.get("/api/monitoring/live")
async def monitoring_live(request: Request, hours: int = 24):
    """Live monitoring data: system, LLM, agents, missions, memory.
    Cached for 5 seconds to avoid hammering DB on rapid polling."""
    import os
    import time as _time

    import psutil

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
    disk = psutil.disk_usage("/")

    system = {
        "cpu_percent": round(cpu_percent, 1),
        "mem_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "sys_cpu_percent": round(sys_cpu, 1),
        "sys_mem_percent": round(sys_mem.percent, 1),
        "disk_percent": round(disk.percent, 1),
        "uptime_seconds": round(import_time() - process.create_time()),
        "threads": process.num_threads(),
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
        llm = {
            "total_calls": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cost_usd": 0,
            "avg_duration_ms": 0,
            "error_count": 0,
            "by_provider": [],
            "by_agent": [],
            "hourly": [],
        }

    # Active agents (runtime from AgentLoopManager + historical from DB — single connection)
    agents_runtime = {"active": 0, "loops": 0}
    agents_historical = {"total_registered": 0, "participated": 0, "sessions_with_agents": 0}
    missions = []
    sessions = []
    sprints = []
    features = []
    msg_count = {"cnt": 0}
    msg_total = {"cnt": 0}
    try:
        from ...agents.loop import get_loop_manager

        mgr = get_loop_manager()
        active_loops = {
            k: {"status": v.status, "agent_id": v.agent_id}
            for k, v in mgr._loops.items()
            if v.status in ("thinking", "acting")
        }
        agents_runtime = {"active": len(active_loops), "loops": len(mgr._loops)}
    except Exception:
        active_loops = {}
    try:
        from ...db.migrations import get_db

        adb = get_db()
        agents_historical["total_registered"] = adb.execute(
            "SELECT COUNT(*) FROM agents"
        ).fetchone()[0]
        agents_historical["participated"] = adb.execute(
            "SELECT COUNT(DISTINCT from_agent) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        agents_historical["sessions_with_agents"] = adb.execute(
            "SELECT COUNT(DISTINCT session_id) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        agents_historical["total_messages"] = adb.execute(
            "SELECT COUNT(*) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        top = adb.execute(
            "SELECT from_agent, COUNT(*) as cnt FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system' GROUP BY from_agent ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        agents_historical["top_agents"] = [{"agent": r[0], "messages": r[1]} for r in top]
        # Reuse same connection for missions/sessions/sprints/features/messages
        missions = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM missions GROUP BY status"
        ).fetchall()
        sessions = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM sessions GROUP BY status"
        ).fetchall()
        sprints = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM sprints GROUP BY status"
        ).fetchall()
        features = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM features GROUP BY status"
        ).fetchall()
        msg_count = adb.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE timestamp > datetime('now', '-24 hours')"
        ).fetchone()
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
        sse_connections = len(getattr(bus, "_sse_listeners", []))
    except Exception:
        sse_connections = 0

    # ── Database stats (single pass — no N+1) ──
    db_stats = {}
    try:
        from ...db.migrations import get_db

        db = get_db()
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
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
        db_path = (
            str(db.execute("PRAGMA database_list").fetchone()[2])
            if db.execute("PRAGMA database_list").fetchone()
            else ""
        )
        db_size_mb = 0
        if db_path:
            import pathlib

            p = pathlib.Path(db_path)
            if p.exists():
                db_size_mb = round(p.stat().st_size / 1024 / 1024, 2)
                # Include WAL
                wal = p.with_suffix(".db-wal")
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
        incidents = {
            "open": open_count,
            "total": total_count,
            "by_severity_status": [dict(r) for r in inc_rows],
        }
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
            import http.client
            import urllib.parse

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
                name = (c.get("Names", ["/?"]) or ["/?"])[0].lstrip("/")
                state = c.get("State", "?")
                status = c.get("Status", "?")
                image = (c.get("Image", "?") or "?")[:40]
                ports_raw = c.get("Ports", [])
                ports_str = (
                    ", ".join(
                        f"{p.get('PublicPort', '')}→{p.get('PrivatePort', '')}"
                        for p in ports_raw
                        if p.get("PublicPort")
                    )
                    if ports_raw
                    else ""
                )
                restarts = (
                    c.get("RestartCount", 0) if c.get("HostConfig", {}).get("RestartPolicy") else 0
                )
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
                            cpu_delta = st.get("cpu_stats", {}).get("cpu_usage", {}).get(
                                "total_usage", 0
                            ) - st.get("precpu_stats", {}).get("cpu_usage", {}).get(
                                "total_usage", 0
                            )
                            sys_delta = st.get("cpu_stats", {}).get("system_cpu_usage", 0) - st.get(
                                "precpu_stats", {}
                            ).get("system_cpu_usage", 0)
                            ncpus = st.get("cpu_stats", {}).get("online_cpus", 1) or 1
                            if sys_delta > 0 and cpu_delta > 0:
                                cpu_pct = round((cpu_delta / sys_delta) * ncpus * 100, 1)
                            # Memory
                            mem_usage = st.get("memory_stats", {}).get("usage", 0)
                            mem_cache = st.get("memory_stats", {}).get("stats", {}).get("cache", 0)
                            mem_mb = round((mem_usage - mem_cache) / 1048576, 1)
                            mem_limit_mb = round(
                                st.get("memory_stats", {}).get("limit", 0) / 1048576, 0
                            )
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

                docker_info.append(
                    {
                        "name": name,
                        "id": cid,
                        "status": status,
                        "state": state,
                        "image": image,
                        "ports": ports_str,
                        "restarts": restarts,
                        "cpu_pct": cpu_pct,
                        "mem_mb": mem_mb,
                        "mem_limit_mb": mem_limit_mb,
                        "net_rx_mb": net_rx_mb,
                        "net_tx_mb": net_tx_mb,
                        "pids": pids,
                        "created": created,
                    }
                )

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
        import pathlib
        import subprocess

        for git_dir in ["/app", "/opt/macaron", os.environ.get("GIT_DIR", "")]:
            if not git_dir or not pathlib.Path(git_dir).exists():
                continue
            r = subprocess.run(
                ["git", "log", "--oneline", "-5", "--no-decorate"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=git_dir,
            )
            if r.returncode == 0 and r.stdout.strip():
                git_info["recent_commits"] = [
                    {"hash": line[:7], "message": line[8:]}
                    for line in r.stdout.strip().split("\n")
                    if line
                ]
                r2 = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=git_dir,
                )
                if r2.returncode == 0:
                    git_info["branch"] = r2.stdout.strip()
                r3 = subprocess.run(
                    ["git", "log", "-1", "--format=%ci"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=git_dir,
                )
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
        phase_stats = [
            {"phase_name": k[0], "status": k[1], "cnt": v} for k, v in sorted(phase_counts.items())
        ]
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
            {
                "name": "MCP SF (unified)",
                "port": 9501,
                "status": "up"
                if mcp_status.get("mcp_sf", {}).get("status") in ("up", "ok")
                else "down",
            },
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
            "vm_monthly_usd": 60.74,  # Standard_B2ms francecentral
            "disk_monthly_usd": 9.50,  # P6 Premium SSD 64GB
            "pg_monthly_usd": 12.34,  # PG B1ms 1vCPU/2GB
            "storage_monthly_usd": 2.50,  # Blob GRS ~50GB
            "total_infra_monthly_usd": 85.08,
        }
    except Exception:
        pass

    # Redact sensitive infrastructure details for unauthenticated requests
    is_authed = (
        getattr(request.state, "authenticated", False) if hasattr(request, "state") else False
    )
    if not is_authed and os.getenv("MACARON_API_KEY"):
        # Strip container IDs, kernel, server version, git branch, Azure details
        for d in docker_info:
            d.pop("id", None)
            d.pop("pids", None)
        docker_system.pop("kernel", None)
        docker_system.pop("server_version", None)
        docker_system.pop("os", None)
        git_info.pop("branch", None)
        azure_infra = {}

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

    return JSONResponse(
        {
            "agent_id": agent_id,
            "category": get_agent_category(agent_id),
            "permissions": agent_permissions_summary(agent_id),
        }
    )


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


@router.get("/api/incidents/stats", responses={200: {"model": IncidentStats}})
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
        return JSONResponse(
            {
                "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
                "by_status": {r["status"]: r["cnt"] for r in by_status},
                "recent": [dict(r) for r in recent],
            }
        )
    except Exception:
        return JSONResponse({"by_severity": {}, "by_status": {}, "recent": []})
    finally:
        db.close()


@router.get("/api/incidents", responses={200: {"model": list[IncidentOut]}})
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


@router.post("/api/incidents", responses={200: {"model": OkResponse}})
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
            (
                inc_id,
                title,
                data.get("severity", "P3"),
                data.get("source", "manual"),
                data.get("error_type", ""),
                data.get("error_detail", ""),
                data.get("mission_id", ""),
                data.get("agent_id", ""),
            ),
        )
        db.commit()
        return JSONResponse({"id": inc_id, "title": title})
    finally:
        db.close()


@router.patch("/api/incidents/{incident_id}", responses={200: {"model": OkResponse}})
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


@router.get("/api/autoheal/stats", responses={200: {"model": AutoHealStats}})
async def autoheal_stats():
    """Auto-heal engine statistics."""
    from ...ops.auto_heal import get_autoheal_stats

    return JSONResponse(get_autoheal_stats())


@router.get("/api/autoheal/heartbeat")
async def autoheal_heartbeat():
    """Return animated ECG heartbeat icon for TMA status."""
    from ...ops.auto_heal import get_autoheal_stats

    stats = get_autoheal_stats()
    hb = stats.get("heartbeat", "starting")
    open_inc = stats["incidents"]["open"]
    active = stats["active_heals"]

    if not stats["enabled"]:
        css_class = "stale"
        color = "var(--text-secondary)"
        label = "TMA disabled"
    elif hb == "alive" and open_inc == 0 and active == 0:
        css_class = "alive"
        color = "#22c55e"
        label = "TMA OK — no open incidents"
    elif hb == "alive" and (open_inc > 0 or active > 0):
        css_class = "healing"
        color = "#f59e0b"
        label = f"TMA active — {open_inc} open, {active} healing"
    elif hb == "starting":
        css_class = "stale"
        color = "var(--text-secondary)"
        label = "TMA starting..."
    else:
        css_class = "stale"
        color = "#ef4444"
        label = f"TMA down — {stats.get('last_error', '?')[:50]}"

    html = (
        f'<span class="tma-hb {css_class}" data-tooltip="{label}" style="--tma-color:{color}">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
        f"</svg></span>"
    )
    return HTMLResponse(html)


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


# ── Chaos Endurance ──────────────────────────────────────────────────


@router.get("/api/chaos/history")
async def chaos_history():
    """Get chaos run history."""
    from ...ops.chaos_endurance import _ensure_table, get_chaos_history

    try:
        _ensure_table()
    except Exception:
        pass
    return JSONResponse(get_chaos_history())


@router.post("/api/chaos/trigger")
async def chaos_trigger(request: Request):
    """Manually trigger a chaos scenario."""
    from ...ops.chaos_endurance import trigger_chaos

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    scenario = body.get("scenario")
    try:
        result = await trigger_chaos(scenario)
        return JSONResponse(
            {
                "ok": result.success,
                "scenario": result.scenario,
                "mttr_ms": result.mttr_ms,
                "detail": result.detail,
            }
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── Endurance Watchdog ───────────────────────────────────────────────


@router.get("/api/watchdog/metrics")
async def watchdog_metrics():
    """Get endurance watchdog metrics."""
    from ...ops.endurance_watchdog import _ensure_table, get_metrics

    try:
        _ensure_table()
    except Exception:
        pass
    return JSONResponse(get_metrics(limit=100))


@router.get("/api/llm/usage")
async def llm_usage_stats():
    """Get LLM usage aggregate (cost by day/phase/agent)."""
    try:
        from ...llm.client import get_llm_client

        client = get_llm_client()
        data = await client.aggregate_usage(days=7)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── i18n ─────────────────────────────────────────────────────────────
@router.get("/api/set-lang/{lang}")
async def set_language(lang: str, request: Request):
    """Switch UI language. Sets cookie and redirects back."""
    from ...i18n import SUPPORTED_LANGS

    if lang not in SUPPORTED_LANGS:
        lang = "en"
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie("sf_lang", lang, max_age=365 * 86400, httponly=True, samesite="lax")
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


# ── Reactions Engine ─────────────────────────────────────────────


@router.get("/api/reactions/stats")
async def reactions_stats():
    """Get reaction engine statistics."""
    from ...reactions import get_reaction_engine

    engine = get_reaction_engine()
    stats = engine.get_stats()
    rules = {
        e.value: {"action": r.action.value, "auto": r.auto, "retries": r.retries}
        for e, r in engine.rules.items()
    }
    return JSONResponse({"stats": stats, "rules": rules})


@router.get("/api/reactions/history")
async def reactions_history(request: Request):
    """Get reaction history."""
    from ...reactions import get_reaction_engine

    project_id = request.query_params.get("project", "")
    limit = int(request.query_params.get("limit", "50"))
    return JSONResponse(get_reaction_engine().get_history(project_id, limit))


@router.get("/api/workspaces")
async def list_workspaces():
    """List active agent workspaces."""
    from ...workspaces import get_workspace_manager

    mgr = get_workspace_manager()
    active = await mgr.list_active()
    return JSONResponse(
        [
            {
                "session_id": w.session_id[:8],
                "project_id": w.project_id,
                "branch": w.branch,
                "path": w.path,
                "type": w.workspace_type.value,
                "status": w.status.value,
                "created_at": w.created_at,
            }
            for w in active
        ]
    )


# ── Integrations CRUD ────────────────────────────────────────────


@router.get("/api/integrations")
async def list_integrations():
    """List all integrations."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute("SELECT * FROM integrations ORDER BY name").fetchall()
        return JSONResponse([dict(r) for r in rows])
    finally:
        db.close()


@router.patch("/api/integrations/{integ_id}")
async def update_integration(integ_id: str, request: Request):
    """Toggle or update integration config."""
    from ...db.migrations import get_db

    data = await request.json()
    db = get_db()
    try:
        if "enabled" in data:
            db.execute(
                "UPDATE integrations SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (1 if data["enabled"] else 0, integ_id),
            )
        if "config" in data:
            existing = db.execute(
                "SELECT config_json FROM integrations WHERE id=?", (integ_id,)
            ).fetchone()
            if existing:
                import json as _json

                cfg = _json.loads(existing["config_json"] or "{}")
                cfg.update(data["config"])
                db.execute(
                    "UPDATE integrations SET config_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (_json.dumps(cfg), integ_id),
                )
        db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


@router.post("/api/integrations/{integ_id}/test")
async def test_integration(integ_id: str):
    """Test integration connectivity."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        row = db.execute("SELECT * FROM integrations WHERE id=?", (integ_id,)).fetchone()
        if not row:
            return JSONResponse({"ok": False, "error": "not found"}, 404)
        import json as _json

        cfg = _json.loads(row["config_json"] or "{}")
        url = cfg.get("url", "")
        if not url:
            db.execute(
                "UPDATE integrations SET status='error', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": False, "error": "no URL configured"})
        # Basic connectivity test
        try:
            import urllib.request

            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Macaron-Platform/1.0")
            token = cfg.get("api_token", "")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            urllib.request.urlopen(req, timeout=10)
            db.execute(
                "UPDATE integrations SET status='connected', last_sync=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": True})
        except Exception as e:
            db.execute(
                "UPDATE integrations SET status='error', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (integ_id,),
            )
            db.commit()
            return JSONResponse({"ok": False, "error": str(e)[:200]})
    finally:
        db.close()


# ── Search (JQL-like) ────────────────────────────────────────────


@router.get("/api/search")
async def search_all(request: Request):
    """Search epics, features, missions, tickets across all projects."""
    from ...db.migrations import get_db

    q = request.query_params.get("q", "").strip()
    if not q:
        return JSONResponse({"results": [], "total": 0})

    db = get_db()
    try:
        like = f"%{q}%"
        results = []

        # Search missions (epics)
        for r in db.execute(
            "SELECT id, name, status, project_id, type, workflow_id FROM missions WHERE name LIKE ? OR description LIKE ? LIMIT 20",
            (like, like),
        ).fetchall():
            results.append(
                {
                    "type": "epic",
                    "id": r["id"],
                    "name": r["name"],
                    "status": r["status"],
                    "project": r["project_id"],
                    "subtype": r["type"],
                }
            )

        # Search features
        for r in db.execute(
            "SELECT f.id, f.name, f.status, f.epic_id, f.story_points FROM features f WHERE f.name LIKE ? OR f.description LIKE ? LIMIT 20",
            (like, like),
        ).fetchall():
            results.append(
                {
                    "type": "feature",
                    "id": r["id"],
                    "name": r["name"],
                    "status": r["status"],
                    "epic_id": r["epic_id"],
                    "sp": r["story_points"],
                }
            )

        # Search tickets
        for r in db.execute(
            "SELECT id, title, status, severity, mission_id FROM support_tickets WHERE title LIKE ? OR description LIKE ? LIMIT 10",
            (like, like),
        ).fetchall():
            results.append(
                {
                    "type": "ticket",
                    "id": r["id"],
                    "name": r["title"],
                    "status": r["status"],
                    "severity": r["severity"],
                }
            )

        # Search memory
        try:
            for r in db.execute(
                "SELECT key, category, content FROM memory WHERE key LIKE ? OR content LIKE ? LIMIT 10",
                (like, like),
            ).fetchall():
                results.append(
                    {
                        "type": "memory",
                        "id": r["key"],
                        "name": r["key"],
                        "category": r["category"],
                        "preview": r["content"][:100],
                    }
                )
        except Exception:
            pass

        return JSONResponse({"results": results, "total": len(results), "query": q})
    finally:
        db.close()


# ── Export (CSV) ─────────────────────────────────────────────────


@router.get("/api/export/epics")
async def export_epics_csv(request: Request):
    """Export all epics as CSV."""
    import csv
    import io

    from ...db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute("""
            SELECT m.id, m.name, m.status, m.project_id, m.type, m.workflow_id, m.wsjf_score,
                   m.created_at, COUNT(f.id) as feature_count, COALESCE(SUM(f.story_points),0) as total_sp
            FROM missions m LEFT JOIN features f ON f.epic_id = m.id
            GROUP BY m.id ORDER BY m.created_at DESC
        """).fetchall()

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "ID",
                "Name",
                "Status",
                "Project",
                "Type",
                "Workflow",
                "WSJF",
                "Created",
                "Features",
                "Story Points",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["id"],
                    r["name"],
                    r["status"],
                    r["project_id"],
                    r["type"],
                    r["workflow_id"],
                    r["wsjf_score"],
                    r["created_at"],
                    r["feature_count"],
                    r["total_sp"],
                ]
            )

        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=epics_export.csv"},
        )
    finally:
        db.close()


@router.get("/api/export/features")
async def export_features_csv(request: Request):
    """Export features as CSV, optionally filtered by epic."""
    import csv
    import io

    from ...db.migrations import get_db

    epic_id = request.query_params.get("epic_id", "")
    db = get_db()
    try:
        if epic_id:
            rows = db.execute(
                "SELECT * FROM features WHERE epic_id=? ORDER BY priority", (epic_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM features ORDER BY epic_id, priority").fetchall()

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "ID",
                "Epic ID",
                "Name",
                "Status",
                "Priority",
                "Story Points",
                "Assigned To",
                "Created",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["id"],
                    r["epic_id"],
                    r["name"],
                    r["status"],
                    r["priority"],
                    r["story_points"],
                    r["assigned_to"],
                    r["created_at"],
                ]
            )

        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=features_export{'_' + epic_id if epic_id else ''}.csv"
            },
        )
    finally:
        db.close()


# ── Burndown / Velocity ─────────────────────────────────────────


@router.get("/api/metrics/burndown/{epic_id}")
async def burndown_data(epic_id: str):
    """Get burndown data for an epic — features completed over time."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        total_sp = db.execute(
            "SELECT COALESCE(SUM(story_points),0) FROM features WHERE epic_id=?", (epic_id,)
        ).fetchone()[0]
        done_features = db.execute(
            "SELECT name, story_points, completed_at FROM features WHERE epic_id=? AND status='done' AND completed_at IS NOT NULL ORDER BY completed_at",
            (epic_id,),
        ).fetchall()

        points = [
            {"date": r["completed_at"][:10], "sp": r["story_points"], "name": r["name"]}
            for r in done_features
        ]
        remaining = total_sp
        burndown = []
        for p in points:
            remaining -= p["sp"]
            burndown.append({"date": p["date"], "remaining": remaining, "done_name": p["name"]})

        return JSONResponse(
            {
                "total_sp": total_sp,
                "remaining_sp": remaining,
                "completed_count": len(done_features),
                "burndown": burndown,
            }
        )
    finally:
        db.close()


@router.get("/api/metrics/velocity")
async def velocity_data():
    """Get velocity across sprints."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        sprints = db.execute(
            "SELECT id, name, status, velocity, planned_sp FROM sprints ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        return JSONResponse(
            [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "status": s["status"],
                    "velocity": s["velocity"],
                    "planned_sp": s["planned_sp"],
                }
                for s in sprints
            ]
        )
    except Exception:
        return JSONResponse([])
    finally:
        db.close()


@router.get("/api/releases/{project_id}")
async def releases_data(project_id: str):
    """Get release notes — completed features grouped by epic, with dates."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        epics = db.execute(
            "SELECT id, name, status, completed_at FROM missions WHERE project_id=? AND type='epic' AND status='completed' ORDER BY completed_at DESC",
            (project_id,),
        ).fetchall()

        releases = []
        for epic in epics:
            features = db.execute(
                "SELECT name, status, story_points, completed_at, acceptance_criteria FROM features WHERE epic_id=? AND status='done' ORDER BY completed_at",
                (epic["id"],),
            ).fetchall()
            total_sp = sum(f["story_points"] or 0 for f in features)
            releases.append(
                {
                    "epic_id": epic["id"],
                    "epic_name": epic["name"],
                    "completed_at": epic["completed_at"],
                    "feature_count": len(features),
                    "total_sp": total_sp,
                    "features": [
                        {"name": f["name"], "sp": f["story_points"], "date": f["completed_at"]}
                        for f in features
                    ],
                }
            )

        # Also include active epics with partial completion
        active = db.execute(
            "SELECT id, name, status FROM missions WHERE project_id=? AND type='epic' AND status IN ('active','planning') ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        for epic in active:
            features = db.execute(
                "SELECT name, status, story_points, completed_at FROM features WHERE epic_id=? ORDER BY status, completed_at",
                (epic["id"],),
            ).fetchall()
            done = [f for f in features if f["status"] == "done"]
            total = len(features)
            releases.append(
                {
                    "epic_id": epic["id"],
                    "epic_name": epic["name"] + " (in progress)",
                    "completed_at": None,
                    "feature_count": total,
                    "done_count": len(done),
                    "progress_pct": round(len(done) / total * 100) if total else 0,
                    "total_sp": sum(f["story_points"] or 0 for f in features),
                    "features": [
                        {
                            "name": f["name"],
                            "sp": f["story_points"],
                            "status": f["status"],
                            "date": f["completed_at"],
                        }
                        for f in features
                    ],
                }
            )

        return JSONResponse({"project_id": project_id, "releases": releases})
    finally:
        db.close()


@router.get("/api/metrics/cycle-time")
async def cycle_time_data(project_id: str = ""):
    """Cycle time distribution — time from created to completed for features and stories."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        where = (
            "AND f.epic_id IN (SELECT id FROM missions WHERE project_id=?)" if project_id else ""
        )
        params = (project_id,) if project_id else ()

        features = db.execute(
            f"""
            SELECT f.name,
                   julianday(f.completed_at) - julianday(f.created_at) as days
            FROM features f
            WHERE f.status='done' AND f.completed_at IS NOT NULL AND f.created_at IS NOT NULL {where}
            ORDER BY days
        """,
            params,
        ).fetchall()

        stories = db.execute(
            f"""
            SELECT s.title,
                   julianday(s.completed_at) - julianday(s.created_at) as days
            FROM user_stories s
            JOIN features f ON s.feature_id = f.id
            WHERE s.status='done' AND s.completed_at IS NOT NULL AND s.created_at IS NOT NULL {where}
            ORDER BY days
        """,
            params,
        ).fetchall()

        feat_days = [round(r["days"], 1) for r in features if r["days"] and r["days"] > 0]
        story_days = [round(r["days"], 1) for r in stories if r["days"] and r["days"] > 0]

        def histogram(values, bins=10):
            if not values:
                return []
            mn, mx = min(values), max(values)
            if mn == mx:
                return [{"range": f"{mn:.0f}", "count": len(values)}]
            step = (mx - mn) / bins
            result = []
            for i in range(bins):
                lo = mn + step * i
                hi = lo + step
                cnt = (
                    sum(1 for v in values if lo <= v < hi)
                    if i < bins - 1
                    else sum(1 for v in values if lo <= v <= hi)
                )
                result.append({"range": f"{lo:.0f}-{hi:.0f}", "count": cnt})
            return result

        return JSONResponse(
            {
                "features": {
                    "count": len(feat_days),
                    "avg_days": round(sum(feat_days) / len(feat_days), 1) if feat_days else 0,
                    "median_days": round(sorted(feat_days)[len(feat_days) // 2], 1)
                    if feat_days
                    else 0,
                    "p90_days": round(sorted(feat_days)[int(len(feat_days) * 0.9)], 1)
                    if feat_days
                    else 0,
                    "histogram": histogram(feat_days),
                },
                "stories": {
                    "count": len(story_days),
                    "avg_days": round(sum(story_days) / len(story_days), 1) if story_days else 0,
                    "median_days": round(sorted(story_days)[len(story_days) // 2], 1)
                    if story_days
                    else 0,
                    "histogram": histogram(story_days),
                },
            }
        )
    except Exception:
        return JSONResponse(
            {"features": {"count": 0, "histogram": []}, "stories": {"count": 0, "histogram": []}}
        )
    finally:
        db.close()


@router.get("/api/metrics/pipeline/{mission_id}")
async def pipeline_metrics(mission_id: str):
    """Pipeline metrics for a specific mission run: duration, tool stats, agent performance."""
    from ...db.migrations import get_db

    db = get_db()
    try:
        # Tool call stats
        tool_stats = db.execute(
            "SELECT tool_name, COUNT(*) as total, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok "
            "FROM tool_calls WHERE session_id IN "
            "(SELECT id FROM sessions WHERE mission_run_id=?) "
            "GROUP BY tool_name ORDER BY total DESC",
            (mission_id,),
        ).fetchall()

        # Agent performance
        agent_stats = db.execute(
            "SELECT agent_id, COUNT(*) as messages, "
            "SUM(CASE WHEN role='assistant' THEN 1 ELSE 0 END) as responses "
            "FROM messages WHERE session_id IN "
            "(SELECT id FROM sessions WHERE mission_run_id=?) "
            "GROUP BY agent_id ORDER BY messages DESC",
            (mission_id,),
        ).fetchall()

        # Phase timing
        phases = db.execute(
            "SELECT phase_id, status, started_at, completed_at FROM sessions "
            "WHERE mission_run_id=? ORDER BY created_at",
            (mission_id,),
        ).fetchall()

        # Screenshots count
        from ...missions.store import get_mission_run_store

        store = get_mission_run_store()
        mission = store.get(mission_id)
        screenshot_count = 0
        if mission and mission.workspace_path:
            ws = Path(mission.workspace_path)
            ss_dir = ws / "screenshots"
            if ss_dir.exists():
                screenshot_count = len(list(ss_dir.glob("*.png")))

        # Tickets count
        tickets = db.execute(
            "SELECT status, COUNT(*) as cnt FROM support_tickets "
            "WHERE mission_id=? GROUP BY status",
            (mission_id,),
        ).fetchall()

        total_tools = sum(r["total"] for r in tool_stats)
        ok_tools = sum(r["ok"] for r in tool_stats)

        return JSONResponse(
            {
                "mission_id": mission_id,
                "tools": {
                    "total": total_tools,
                    "success": ok_tools,
                    "rate": round(ok_tools / total_tools * 100, 1) if total_tools else 0,
                    "by_tool": [
                        {"name": r["tool_name"], "total": r["total"], "ok": r["ok"]}
                        for r in tool_stats
                    ],
                },
                "agents": [
                    {"id": r["agent_id"], "messages": r["messages"], "responses": r["responses"]}
                    for r in agent_stats
                ],
                "phases": [{"id": r["phase_id"], "status": r["status"]} for r in phases],
                "screenshots": screenshot_count,
                "tickets": {r["status"]: r["cnt"] for r in tickets},
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


import hashlib
import hmac
import os
import uuid


@router.post("/api/webhooks/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events (push, pull_request, issues).

    Configure in GitHub: Settings → Webhooks → Add webhook
    Payload URL: https://your-domain/api/webhooks/github
    Content type: application/json
    Secret: set GITHUB_WEBHOOK_SECRET env var
    Events: push, pull_request, issues
    """
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    body = await request.body()

    # HMAC signature verification
    if secret:
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    event = request.headers.get("X-GitHub-Event", "ping")

    if event == "ping":
        return JSONResponse({"ok": True, "event": "ping"})

    from ...db.connection import get_db

    db = get_db()
    now = datetime.utcnow().isoformat()

    try:
        if event == "push":
            repo = payload.get("repository", {}).get("full_name", "unknown")
            branch = payload.get("ref", "").split("/")[-1]
            commits = payload.get("commits", [])
            mid = str(uuid.uuid4())[:8]
            db.execute(
                "INSERT INTO missions (id, name, project_id, type, status, description, created_at) VALUES (?, ?, ?, 'feature', 'planning', ?, ?)",
                (
                    mid,
                    f"Build: {repo}@{branch}",
                    repo,
                    f"{len(commits)} commit(s) pushed to {branch}",
                    now,
                ),
            )
            db.commit()
            return JSONResponse({"ok": True, "event": "push", "mission_id": mid})

        if event == "pull_request":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            repo = payload.get("repository", {}).get("full_name", "unknown")
            if action in ("opened", "synchronize"):
                mid = str(uuid.uuid4())[:8]
                db.execute(
                    "INSERT INTO missions (id, name, project_id, type, status, description, created_at) VALUES (?, ?, ?, 'feature', 'in_review', ?, ?)",
                    (
                        mid,
                        f"Review: PR #{pr.get('number')} {pr.get('title', '')}",
                        repo,
                        pr.get("body", "")[:500],
                        now,
                    ),
                )
                db.commit()
                return JSONResponse(
                    {"ok": True, "event": "pull_request", "action": action, "mission_id": mid}
                )

        elif event == "issues":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            repo = payload.get("repository", {}).get("full_name", "unknown")
            if action == "opened":
                mid = str(uuid.uuid4())[:8]
                mtype = (
                    "bug"
                    if any(l.get("name") == "bug" for l in issue.get("labels", []))
                    else "feature"
                )
                db.execute(
                    "INSERT INTO missions (id, name, project_id, type, status, description, created_at) VALUES (?, ?, ?, ?, 'planning', ?, ?)",
                    (
                        mid,
                        f"Issue #{issue.get('number')}: {issue.get('title', '')}",
                        repo,
                        mtype,
                        issue.get("body", "")[:500],
                        now,
                    ),
                )
                db.commit()
                return JSONResponse({"ok": True, "event": "issues", "mission_id": mid})
    finally:
        db.close()

    return JSONResponse({"ok": True, "event": event, "action": "ignored"})


# ── Notification Configuration ────────────────────────────────────────────────


@router.get("/api/notifications/status")
async def notification_status():
    """Check notification configuration status."""
    from ...services.notification_service import get_notification_service

    svc = get_notification_service()
    return JSONResponse(
        {
            "configured": svc.is_configured,
            "channels": {
                "slack": svc.has_slack,
                "email": svc.has_email,
                "webhook": svc.has_webhook,
            },
        }
    )


@router.post("/api/notifications/test")
async def notification_test():
    """Send a test notification to all configured channels."""
    from ...services.notification_service import NotificationPayload, get_notification_service

    svc = get_notification_service()
    if not svc.is_configured:
        return JSONResponse({"error": "No notification channels configured"}, status_code=400)
    payload = NotificationPayload(
        event="test",
        title="Test Notification",
        message="This is a test notification from Software Factory.",
        severity="info",
    )
    await svc.notify(payload)
    return JSONResponse(
        {
            "ok": True,
            "channels": {
                "slack": svc.has_slack,
                "email": svc.has_email,
                "webhook": svc.has_webhook,
            },
        }
    )
