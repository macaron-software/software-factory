"""External integration routes (Confluence, tickets, security, TMA, etc.)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...schemas import OkResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/epics/{epic_id}/confluence/sync")
@router.post("/api/missions/{epic_id}/confluence/sync")
async def api_confluence_sync_all(epic_id: str):
    """Sync all mission tabs to Confluence."""
    try:
        from ....confluence.sync import get_sync_engine

        engine = get_sync_engine()
        results = engine.sync_mission(epic_id)
        return JSONResponse(results)
    except FileNotFoundError:
        return JSONResponse({"error": "Confluence PAT not configured"}, status_code=503)
    except Exception as e:
        logger.error("Confluence sync failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/epics/{epic_id}/confluence/sync/{tab}")
@router.post("/api/missions/{epic_id}/confluence/sync/{tab}")
async def api_confluence_sync_tab(epic_id: str, tab: str):
    """Sync a single tab to Confluence."""
    try:
        from ....confluence.sync import get_sync_engine

        engine = get_sync_engine()
        result = engine.sync_tab(epic_id, tab)
        return JSONResponse(result)
    except FileNotFoundError:
        return JSONResponse({"error": "Confluence PAT not configured"}, status_code=503)
    except Exception as e:
        logger.error("Confluence sync tab %s failed: %s", tab, e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/epics/{epic_id}/confluence/status")
@router.get("/api/missions/{epic_id}/confluence/status")
async def api_confluence_status(epic_id: str):
    """Get Confluence sync status for a mission."""
    try:
        from ....confluence.sync import get_sync_engine

        engine = get_sync_engine()
        status = engine.get_sync_status(epic_id)
        healthy = engine.client.health_check()
        return JSONResponse({"status": status, "connected": healthy})
    except FileNotFoundError:
        return JSONResponse({"connected": False, "status": {}})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Screenshots API ──


@router.get("/api/epics/{epic_id}/screenshots")
@router.get("/api/missions/{epic_id}/screenshots")
async def api_mission_screenshots(epic_id: str):
    """List screenshots from mission workspace."""
    from ....epics.store import get_epic_run_store

    store = get_epic_run_store()
    mission = store.get(epic_id)
    if not mission or not mission.workspace_path:
        return JSONResponse({"screenshots": [], "workspace": ""})
    ws = Path(mission.workspace_path)
    screenshots = []
    for img_dir in [ws / "screenshots", ws]:
        if img_dir.exists():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"):
                for img in sorted(img_dir.glob(ext)):
                    if img.stat().st_size > 1000:
                        rel = img.relative_to(ws)
                        screenshots.append(
                            {
                                "name": img.name,
                                "path": str(rel),
                                "size_kb": round(img.stat().st_size / 1024, 1),
                                "url": f"/workspace/{epic_id}/{rel}",
                            }
                        )
    return JSONResponse({"screenshots": screenshots[:20], "workspace": str(ws)})


# ── Support Tickets API (TMA) ──


@router.get("/api/epics/{epic_id}/tickets")
@router.get("/api/missions/{epic_id}/tickets")
async def api_list_tickets(epic_id: str, status: str = ""):
    from ....db.migrations import get_db

    db = get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM support_tickets WHERE mission_id=? AND status=? ORDER BY "
            "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
            (epic_id, status),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM support_tickets WHERE mission_id=? ORDER BY "
            "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
            (epic_id,),
        ).fetchall()
    db.close()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/epics/{epic_id}/tickets")
@router.post("/api/missions/{epic_id}/tickets")
async def api_create_ticket(request: Request, epic_id: str):
    import uuid

    from ....db.migrations import get_db

    body = await request.json()
    tid = str(uuid.uuid4())[:8]
    db = get_db()
    db.execute(
        "INSERT INTO support_tickets (id, mission_id, title, description, severity, category, reporter, assignee) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            tid,
            epic_id,
            body.get("title", ""),
            body.get("description", ""),
            body.get("severity", "P3"),
            body.get("category", "incident"),
            body.get("reporter", ""),
            body.get("assignee", ""),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM support_tickets WHERE id=?", (tid,)).fetchone()
    db.close()
    return JSONResponse(dict(row), status_code=201)


@router.patch("/api/epics/{epic_id}/tickets/{ticket_id}")
@router.patch("/api/missions/{epic_id}/tickets/{ticket_id}")
async def api_update_ticket(request: Request, epic_id: str, ticket_id: str):
    from ....db.migrations import get_db

    body = await request.json()
    db = get_db()
    sets, vals = [], []
    for field in (
        "status",
        "severity",
        "assignee",
        "resolution",
        "title",
        "description",
        "category",
    ):
        if field in body:
            sets.append(f"{field}=?")
            vals.append(body[field])
    if not sets:
        db.close()
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    sets.append("updated_at=CURRENT_TIMESTAMP")
    if body.get("status") in ("resolved", "closed"):
        sets.append("resolved_at=CURRENT_TIMESTAMP")
    vals.extend([ticket_id, epic_id])
    db.execute(
        f"UPDATE support_tickets SET {','.join(sets)} WHERE id=? AND mission_id=?", vals
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM support_tickets WHERE id=?", (ticket_id,)
    ).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(dict(row))


@router.delete("/api/mission-runs/{run_id}", responses={200: {"model": OkResponse}})
async def delete_epic_run(run_id: str):
    """Delete a mission run and ALL associated data (cascade)."""
    from ....db.migrations import get_db
    from ....epics.store import get_epic_run_store

    store = get_epic_run_store()
    run = store.get(run_id)
    if not run:
        return JSONResponse({"error": "Not found"}, status_code=404)
    conn = get_db()
    # Cascade: messages, tool_calls, sessions, sprints, tasks, traces, incidents, confluence
    if run.session_id:
        conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (run.session_id,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (run.session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (run.session_id,))
    conn.execute("DELETE FROM sprints WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM tasks WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM confluence_pages WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM llm_traces WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM llm_usage WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM platform_incidents WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM support_tickets WHERE mission_id = ?", (run_id,))
    conn.execute("DELETE FROM epic_runs WHERE id = ?", (run_id,))
    conn.commit()
    return JSONResponse({"status": "deleted"})


@router.patch("/api/projects/{project_id}/settings")
async def patch_project_settings(project_id: str, request: Request):
    """Update project settings: path, description, git_url, lead_agent_id."""
    from ....projects.manager import get_project_store
    from ....db.migrations import get_db

    store = get_project_store()
    project = store.get(project_id)
    if not project:
        return JSONResponse({"error": "Not found"}, status_code=404)
    body = await request.json()
    if "path" in body:
        raw_path = str(body["path"])
        project.path = (
            os.path.normpath(os.path.expanduser(raw_path)) if raw_path else ""
        )
    if "description" in body:
        project.description = str(body["description"])
    if "lead_agent_id" in body:
        project.lead_agent_id = str(body["lead_agent_id"])
    if "git_url" in body:
        conn = get_db()
        conn.execute(
            "UPDATE projects SET git_url=? WHERE id=?", (body["git_url"], project_id)
        )
        conn.commit()
    store.update(project)
    return {"ok": True, "project_id": project_id, "path": project.path}


@router.delete("/api/projects/{project_id}", responses={200: {"model": OkResponse}})
async def delete_project(project_id: str):
    """Delete a project and ALL associated missions, sessions, memory, agents."""
    from ....db.migrations import get_db

    # Protected domains — projects in these domains cannot be deleted
    _PROTECTED_DOMAINS = {"PILOTE", "SF"}

    conn = get_db()
    conn.execute("PRAGMA busy_timeout = 10000")  # 10s wait for lock
    project = conn.execute(
        "SELECT id, name, is_protected, client_domain FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if not project:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Block deletion of protected projects
    keys = project.keys() if hasattr(project, "keys") else []
    _is_protected = bool(project["is_protected"]) if "is_protected" in keys else False
    _client_domain = (project["client_domain"] or "") if "client_domain" in keys else ""
    if _is_protected or _client_domain.upper() in _PROTECTED_DOMAINS:
        return JSONResponse(
            {
                "error": f"Le projet '{project['name']}' est protégé et ne peut pas être supprimé."
            },
            status_code=403,
        )
    try:
        conn.execute("BEGIN IMMEDIATE")
    except Exception:
        pass  # Already in transaction or WAL mode
    # Delete all missions for this project (cascade)
    missions = conn.execute(
        "SELECT id FROM epics WHERE project_id = ?", (project_id,)
    ).fetchall()
    for (mid,) in missions:
        # Delete runs
        runs = conn.execute(
            "SELECT id, session_id FROM epic_runs WHERE parent_epic_id = ?",
            (mid,),
        ).fetchall()
        for run_id, session_id in runs:
            if session_id:
                conn.execute(
                    "DELETE FROM tool_calls WHERE session_id = ?", (session_id,)
                )
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            for tbl in (
                "sprints",
                "tasks",
                "confluence_pages",
                "llm_traces",
                "llm_usage",
                "platform_incidents",
                "support_tickets",
            ):
                try:
                    conn.execute(f"DELETE FROM {tbl} WHERE mission_id = ?", (run_id,))
                except Exception:
                    pass  # Table may not exist
        conn.execute("DELETE FROM epic_runs WHERE parent_epic_id = ?", (mid,))
        # Delete features (epic_id = mission_id in SAFe terms)
        conn.execute(
            "DELETE FROM user_stories WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
            (mid,),
        )
        try:
            conn.execute(
                "DELETE FROM feature_deps WHERE feature_id IN (SELECT id FROM features WHERE epic_id = ?)",
                (mid,),
            )
            conn.execute(
                "DELETE FROM feature_deps WHERE depends_on IN (SELECT id FROM features WHERE epic_id = ?)",
                (mid,),
            )
        except Exception:
            pass
        conn.execute("DELETE FROM features WHERE epic_id = ?", (mid,))
        conn.execute("DELETE FROM sprints WHERE mission_id = ?", (mid,))
        conn.execute("DELETE FROM tasks WHERE mission_id = ?", (mid,))
        try:
            conn.execute(
                "DELETE FROM ideation_findings WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
                (mid,),
            )
            conn.execute(
                "DELETE FROM ideation_messages WHERE session_id IN (SELECT id FROM ideation_sessions WHERE mission_id = ?)",
                (mid,),
            )
            conn.execute("DELETE FROM ideation_sessions WHERE mission_id = ?", (mid,))
        except Exception:
            pass
    conn.execute("DELETE FROM epics WHERE project_id = ?", (project_id,))
    # Delete orphan epic_runs for this project
    conn.execute("DELETE FROM epic_runs WHERE project_id = ?", (project_id,))
    # Delete project sessions
    proj_sessions = conn.execute(
        "SELECT id FROM sessions WHERE project_id = ?", (project_id,)
    ).fetchall()
    for (sid,) in proj_sessions:
        conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM sessions WHERE project_id = ?", (project_id,))
    # Delete project memory
    conn.execute("DELETE FROM memory_project WHERE project_id = ?", (project_id,))
    # Delete project agents (agent-{project_id})
    conn.execute("DELETE FROM agents WHERE id = ?", (f"agent-{project_id}",))
    # Delete project
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    return JSONResponse({"status": "deleted", "name": project[1]})


@router.post("/api/projects/{project_id}/feedback/security-alert")
async def api_security_alert(request: Request, project_id: str):
    """Create a priority bug for a security vulnerability."""
    from ....missions.feedback import on_security_alert

    data = await request.json()
    cve_id = data.get("cve_id", "UNKNOWN")
    severity = data.get("severity", "critical")
    description = data.get("description", "")
    bug = on_security_alert(project_id, cve_id, severity, description)
    if bug:
        return JSONResponse({"ok": True, "mission_id": bug.id, "name": bug.name})
    return JSONResponse({"ok": False, "reason": "Already tracked or severity too low"})


@router.post("/api/projects/{project_id}/feedback/tma-incident")
async def api_tma_incident(request: Request, project_id: str):
    """Track a recurring TMA incident. Creates debt item after 3+ occurrences."""
    from ....missions.feedback import on_tma_incident_fixed

    data = await request.json()
    incident_key = data.get("incident_key", "unknown")
    result = on_tma_incident_fixed(project_id, incident_key)
    if result:
        return JSONResponse(
            {
                "ok": True,
                "mission_id": result.id,
                "name": result.name,
                "message": "Root-cause fix mission created",
            }
        )
    return JSONResponse({"ok": True, "message": "Incident tracked, below threshold"})


@router.post("/api/projects/{project_id}/provision")
async def api_project_provision(request: Request, project_id: str):
    """Manually trigger auto-provision (TMA+security+debt) for an existing project."""
    from ....projects.manager import get_project_store

    store = get_project_store()
    project = store.get(project_id)
    if not project:
        return JSONResponse(
            {"ok": False, "reason": "Project not found"}, status_code=404
        )
    created = store.auto_provision(project_id, project.name)
    return JSONResponse(
        {
            "ok": True,
            "created": [{"id": m.id, "type": m.type, "name": m.name} for m in created],
        }
    )
