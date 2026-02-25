"""Search, export, i18n, perspective, notifications, reactions, SI blueprints, workspaces, webhooks & retrospectives."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from ...schemas import FeatureOut
from ..helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)

# ── SAFe Perspective ───────────────────────────────────────────────────

SAFE_PERSPECTIVES = {
    "overview",
    "dsi",
    "portfolio_manager",
    "rte",
    "product_owner",
    "scrum_master",
    "developer",
    "architect",
    "qa_security",
    "business_owner",
    "admin",
}

PERSPECTIVE_LABELS = {
    "overview": "Overview",
    "dsi": "DSI",
    "portfolio_manager": "Portfolio Manager",
    "rte": "RTE",
    "product_owner": "Product Owner",
    "scrum_master": "Scrum Master",
    "developer": "Developer",
    "architect": "Architect",
    "qa_security": "QA / Security",
    "business_owner": "Business Owner",
    "admin": "Admin",
}

# Which sidebar links each perspective can see
PERSPECTIVE_SIDEBAR = {
    "overview": {
        "/",
        "/backlog",
        "/pi",
        "/workflows",
        "/metrics",
        "/art",
    },
    "dsi": {
        "/",
        "/backlog",
        "/pi",
        "/workflows",
        "/metrics",
        "/art",
        "/projects",
        "/settings",
    },
    "portfolio_manager": {
        "/",
        "/backlog",
        "/pi",
        "/metrics",
        "/projects",
        "/settings",
    },
    "rte": {
        "/",
        "/pi",
        "/workflows",
        "/sessions",
        "/art",
        "/metrics",
        "/projects",
        "/settings",
    },
    "product_owner": {
        "/",
        "/backlog",
        "/pi",
        "/projects",
        "/sessions",
        "/metrics",
        "/settings",
    },
    "scrum_master": {
        "/",
        "/pi",
        "/workflows",
        "/sessions",
        "/art",
        "/metrics",
        "/projects",
        "/settings",
    },
    "developer": {
        "/",
        "/projects",
        "/sessions",
        "/toolbox",
        "/art",
        "/metrics",
        "/settings",
    },
    "architect": {
        "/",
        "/backlog",
        "/pi",
        "/projects",
        "/toolbox",
        "/metrics",
        "/settings",
    },
    "qa_security": {
        "/",
        "/projects",
        "/workflows",
        "/sessions",
        "/metrics",
        "/settings",
    },
    "business_owner": {
        "/",
        "/backlog",
        "/pi",
        "/metrics",
        "/projects",
        "/settings",
    },
    "admin": {
        "/",
        "/backlog",
        "/pi",
        "/workflows",
        "/sessions",
        "/art",
        "/toolbox",
        "/mercato",
        "/metrics",
        "/projects",
        "/settings",
    },
}


# ── Retrospectives & Self-Improvement ────────────────────────────


@router.get("/api/retrospectives")
async def list_retrospectives(scope: str = "", limit: int = 20):
    """List retrospectives, optionally filtered by scope."""
    from ....db.migrations import get_db

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

    from ....db.migrations import get_db
    from ....llm.client import LLMMessage, get_llm_client
    from ....memory.manager import get_memory_manager

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
                context_parts.append(
                    f"  {m['agent_name']}{role_str}: {m['content'][:200]}"
                )
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

    bp_path = (
        Path(__file__).resolve().parents[4]
        / "data"
        / "si_blueprints"
        / f"{project_id}.yaml"
    )
    if not bp_path.exists():
        return JSONResponse(
            {"error": "No SI blueprint found", "project_id": project_id},
            status_code=404,
        )
    with open(bp_path) as f:
        return JSONResponse(yaml.safe_load(f))


@router.put("/api/projects/{project_id}/si-blueprint")
async def api_put_si_blueprint(request: Request, project_id: str):
    """Write SI blueprint for a project."""
    import yaml

    bp_dir = Path(__file__).resolve().parents[4] / "data" / "si_blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)
    data = await request.json()
    data["project_id"] = project_id
    with open(bp_dir / f"{project_id}.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return JSONResponse({"ok": True, "project_id": project_id})


async def api_project_git(request: Request, project_id: str):
    """Git panel partial (HTMX)."""
    from ....projects import git_service
    from ....projects.manager import get_project_store

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
    from ....projects import factory_tasks

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


@router.get(
    "/api/epics/{epic_id}/features", responses={200: {"model": list[FeatureOut]}}
)
async def epic_features(epic_id: str):
    """List features for an epic."""
    from ....db.migrations import get_db

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


@router.get("/api/set-lang/{lang}")
async def set_language(lang: str, request: Request):
    """Switch UI language. Sets cookie and redirects back."""
    from ....i18n import SUPPORTED_LANGS

    if lang not in SUPPORTED_LANGS:
        lang = "en"
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie(
        "sf_lang", lang, max_age=365 * 86400, httponly=True, samesite="lax"
    )
    return response


@router.get("/api/i18n/{lang}.json")
async def i18n_catalog(lang: str):
    """Serve translation catalog for client-side JS."""
    from ....i18n import SUPPORTED_LANGS, _catalog, _load_catalog

    if not _catalog:
        _load_catalog()
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    return JSONResponse(_catalog.get(lang, {}))


@router.post("/api/perspective")
async def set_perspective(request: Request):
    """Set SAFe perspective cookie."""
    body = await request.json()
    perspective = body.get("perspective", "admin")
    if perspective not in SAFE_PERSPECTIVES:
        perspective = "admin"
    response = JSONResponse({"ok": True, "perspective": perspective})
    response.set_cookie(
        key="safe_perspective",
        value=perspective,
        max_age=31536000,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/api/perspective")
async def get_perspective(request: Request):
    """Get current perspective + sidebar config."""
    p = getattr(request.state, "perspective", "admin")
    return JSONResponse(
        {
            "perspective": p,
            "label": PERSPECTIVE_LABELS.get(p, p),
            "sidebar": list(PERSPECTIVE_SIDEBAR.get(p) or []),
            "labels": PERSPECTIVE_LABELS,
        }
    )


@router.get("/api/notifications/status")
async def notification_status():
    """Check notification configuration status."""
    from ....services.notification_service import get_notification_service

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
    from ....services.notification_service import (
        NotificationPayload,
        get_notification_service,
    )

    svc = get_notification_service()
    if not svc.is_configured:
        return JSONResponse(
            {"error": "No notification channels configured"}, status_code=400
        )
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


@router.get("/api/reactions/stats")
async def reactions_stats():
    """Get reaction engine statistics."""
    from ....reactions import get_reaction_engine

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
    from ....reactions import get_reaction_engine

    project_id = request.query_params.get("project", "")
    limit = int(request.query_params.get("limit", "50"))
    return JSONResponse(get_reaction_engine().get_history(project_id, limit))


@router.get("/api/workspaces")
async def list_workspaces():
    """List active agent workspaces."""
    from ....workspaces import get_workspace_manager

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


@router.get("/api/search")
async def search_all(request: Request):
    """Search epics, features, missions, tickets across all projects."""
    from ....db.migrations import get_db

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


@router.get("/api/export/epics")
async def export_epics_csv(request: Request):
    """Export all epics as CSV."""
    import csv
    import io

    from ....db.migrations import get_db

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

    from ....db.migrations import get_db

    epic_id = request.query_params.get("epic_id", "")
    db = get_db()
    try:
        if epic_id:
            rows = db.execute(
                "SELECT * FROM features WHERE epic_id=? ORDER BY priority", (epic_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM features ORDER BY epic_id, priority"
            ).fetchall()

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
        expected = (
            "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(sig_header, expected):
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    event = request.headers.get("X-GitHub-Event", "ping")

    if event == "ping":
        return JSONResponse({"ok": True, "event": "ping"})

    from ....db.connection import get_db

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
                    {
                        "ok": True,
                        "event": "pull_request",
                        "action": action,
                        "mission_id": mid,
                    }
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
