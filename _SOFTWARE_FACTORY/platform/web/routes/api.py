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
        return HTMLResponse(f'<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Aucun résultat pour "{q}"</div>')
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
    from ..projects import git_service
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
    from ..projects import factory_tasks
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


