"""Web routes — Workflow CRUD and DSI workflows."""

from __future__ import annotations

import asyncio
import html as html_mod
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .helpers import _templates, _avatar_url

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Workflows ────────────────────────────────────────────────────


@router.get("/workflows/new", response_class=HTMLResponse)
async def workflow_new(request: Request):
    """New workflow form."""
    from ...patterns.store import get_pattern_store
    from ...agents.store import get_agent_store

    patterns = [
        {"id": p.id, "name": p.name, "type": p.type}
        for p in get_pattern_store().list_all()
    ]
    agents = [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "icon": a.icon,
            "color": a.color,
            "skills": a.skills,
            "description": a.description,
        }
        for a in get_agent_store().list_all()
    ]
    return _templates(request).TemplateResponse(
        "workflow_edit.html",
        {
            "request": request,
            "page_title": "New Workflow",
            "workflow": None,
            "patterns": patterns,
            "agents": agents,
        },
    )


@router.get("/workflows/{wf_id}", response_class=HTMLResponse)
async def workflow_detail(request: Request, wf_id: str):
    """Redirect to edit view (detail = edit for workflows)."""
    return RedirectResponse(f"/workflows/{wf_id}/edit", status_code=302)


@router.get("/workflows/{wf_id}/graph", response_class=HTMLResponse)
async def workflow_graph(request: Request, wf_id: str):
    """Visual DAG graph builder for a workflow."""
    from ...workflows.store import get_workflow_store
    from ...patterns.store import get_pattern_store
    from ...agents.store import get_agent_store

    wf = get_workflow_store().get(wf_id)
    if not wf:
        return HTMLResponse("<h2>Workflow not found</h2>", status_code=404)
    patterns = [
        {"id": p.id, "name": p.name, "type": p.type}
        for p in get_pattern_store().list_all()
    ]
    agents = [
        {"id": a.id, "name": a.name, "role": a.role, "icon": a.icon, "color": a.color}
        for a in get_agent_store().list_all()
    ]
    return _templates(request).TemplateResponse(
        "workflow_graph.html",
        {
            "request": request,
            "page_title": f"Graph: {wf.name}",
            "workflow": wf,
            "patterns": patterns,
            "agents": agents,
        },
    )


@router.get("/workflows/{wf_id}/edit", response_class=HTMLResponse)
async def workflow_edit(request: Request, wf_id: str):
    """Edit workflow form."""
    from ...workflows.store import get_workflow_store
    from ...patterns.store import get_pattern_store
    from ...agents.store import get_agent_store

    wf = get_workflow_store().get(wf_id)
    if not wf:
        return HTMLResponse("<h2>Workflow not found</h2>", status_code=404)
    patterns = [
        {"id": p.id, "name": p.name, "type": p.type}
        for p in get_pattern_store().list_all()
    ]
    agents = [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "icon": a.icon,
            "color": a.color,
            "skills": a.skills,
            "description": a.description,
        }
        for a in get_agent_store().list_all()
    ]
    return _templates(request).TemplateResponse(
        "workflow_edit.html",
        {
            "request": request,
            "page_title": f"Edit: {wf.name}",
            "workflow": wf,
            "patterns": patterns,
            "agents": agents,
        },
    )


@router.post("/api/workflows")
async def create_workflow(request: Request):
    """Create or update a workflow."""
    from ...workflows.store import get_workflow_store, WorkflowDef, WorkflowPhase
    import json as _json

    form = await request.form()
    wf_id = str(form.get("id", ""))
    name = str(form.get("name", "New Workflow"))
    description = str(form.get("description", ""))
    icon = str(form.get("icon", "workflow"))
    phases_raw = str(form.get("phases_json", "[]"))
    try:
        phases_data = _json.loads(phases_raw)
    except Exception:
        phases_data = []
    phases = [
        WorkflowPhase(
            id=p.get("id", f"p{i + 1}"),
            pattern_id=p.get("pattern_id", ""),
            name=p.get("name", f"Phase {i + 1}"),
            description=p.get("description", ""),
            gate=p.get("gate", "always"),
        )
        for i, p in enumerate(phases_data)
    ]

    config_raw = str(form.get("config_json", "{}"))
    try:
        config = _json.loads(config_raw)
    except Exception:
        config = {}
    wf = WorkflowDef(
        id=wf_id,
        name=name,
        description=description,
        icon=icon,
        phases=phases,
        config=config,
    )
    store = get_workflow_store()
    store.create(wf)
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/workflows/resume-all")
async def workflow_resume_all():
    """Mass-resume all interrupted/paused workflows from their last checkpoint."""
    from ...sessions.store import get_session_store
    from ...workflows.store import get_workflow_store

    store = get_session_store()
    wf_store = get_workflow_store()

    conn = store._conn if hasattr(store, "_conn") else None
    if not conn:
        from ...db.migrations import get_db

        conn = get_db()

    rows = conn.execute(
        "SELECT id, config_json FROM sessions WHERE status IN ('interrupted','paused','active') AND config_json LIKE '%workflow_id%'"
    ).fetchall()

    resumed = 0
    errors = []
    for row in rows:
        sid = row[0]
        try:
            config = json.loads(row[1]) if row[1] else {}
            wf_id = config.get("workflow_id")
            if not wf_id:
                continue
            wf = wf_store.get(wf_id)
            if not wf:
                continue
            sess = store.get(sid)
            if not sess:
                continue
            task = sess.goal or sess.name
            project_id = sess.project_id or ""
            resume_from = config.get("workflow_checkpoint", 0)
            asyncio.create_task(
                _run_workflow_background(
                    wf, sid, task, project_id, resume_from=resume_from
                )
            )
            resumed += 1
        except Exception as e:
            errors.append(f"{sid}: {e}")

    return {"resumed": resumed, "total_candidates": len(rows), "errors": errors[:10]}


@router.post("/api/workflows/{wf_id}")
async def update_workflow(request: Request, wf_id: str):
    """Update an existing workflow."""
    from ...workflows.store import get_workflow_store, WorkflowDef, WorkflowPhase
    import json as _json

    form = await request.form()
    name = str(form.get("name", ""))
    description = str(form.get("description", ""))
    icon = str(form.get("icon", "workflow"))
    phases_raw = str(form.get("phases_json", "[]"))
    try:
        phases_data = _json.loads(phases_raw)
    except Exception:
        phases_data = []
    phases = [
        WorkflowPhase(
            id=p.get("id", f"p{i + 1}"),
            pattern_id=p.get("pattern_id", ""),
            name=p.get("name", f"Phase {i + 1}"),
            description=p.get("description", ""),
            gate=p.get("gate", "always"),
        )
        for i, p in enumerate(phases_data)
    ]

    config_raw = str(form.get("config_json", "{}"))
    try:
        config = _json.loads(config_raw)
    except Exception:
        config = {}
    wf = WorkflowDef(
        id=wf_id,
        name=name,
        description=description,
        icon=icon,
        phases=phases,
        config=config,
    )
    store = get_workflow_store()
    store.create(wf)  # INSERT OR REPLACE
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/workflows/{wf_id}/delete")
async def delete_workflow(request: Request, wf_id: str):
    """Delete a workflow."""
    from ...workflows.store import get_workflow_store

    get_workflow_store().delete(wf_id)
    return RedirectResponse(url="/workflows", status_code=303)


@router.post("/api/sessions/{session_id}/run-workflow")
async def run_session_workflow(request: Request, session_id: str):
    """Execute a workflow in a session."""
    from ...sessions.store import get_session_store, MessageDef
    from ...workflows.store import get_workflow_store

    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return HTMLResponse("Session not found", status_code=404)

    form = await request.form()
    workflow_id = str(form.get("workflow_id", "")).strip()
    task = str(form.get("task", session.goal or "Execute workflow")).strip()

    wf = get_workflow_store().get(workflow_id)
    if not wf:
        return HTMLResponse(
            f'<div class="msg-system-text">Workflow {html_mod.escape(str(workflow_id))} not found.</div>'
        )

    # User message targets the workflow leader (first agent of first phase)
    leader = ""
    if wf.phases:
        first_agents = wf.phases[0].config.get("agents", [])
        if first_agents:
            leader = first_agents[0]

    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="user",
            to_agent=leader or "all",
            message_type="text",
            content=f"Run workflow **{wf.name}**: {task}",
        )
    )

    # Save workflow_id in session config (needed for graph rendering)
    from ...sessions.store import get_db
    import json as _json

    db = get_db()
    try:
        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["workflow_id"] = workflow_id
        if leader:
            existing_config["lead_agent"] = leader
        db.execute(
            "UPDATE sessions SET config_json=? WHERE id=?",
            (_json.dumps(existing_config), session_id),
        )
        db.commit()
    finally:
        db.close()

    # Resolve project_id: from session, or from workflow config
    project_id = session.project_id or ""
    if not project_id and wf.config:
        project_id = wf.config.get("project_ref", "")
    if project_id and not session.project_id:
        db = get_db()
        try:
            db.execute(
                "UPDATE sessions SET project_id=? WHERE id=?", (project_id, session_id)
            )
            db.commit()
        finally:
            db.close()

    asyncio.create_task(_run_workflow_background(wf, session_id, task, project_id))
    return HTMLResponse(
        f'<div class="msg-system-text">Workflow "{wf.name}" started — {len(wf.phases)} phases.</div>'
    )


# Phase name mapping: feature-sprint phase IDs → dashboard AC phase names
_PHASE_MAP = {
    "feature-design": "inception",
    "env-setup": "cicd",
    "tdd-sprint": "tdd-sprint",
    "adversarial-review": "adversarial",
    "feature-e2e": "qa-sprint",
    "feature-deploy": "deploy",
}


def _auto_inject_ac_cycle(
    project_id: str,
    cycle_num: int,
    result,
    session_id: str,
    run_status: str = "completed",
) -> None:
    """Auto-inject AC cycle results into ac_cycles after builder completion.

    Harvests data from phase_results + workspace artifacts instead of relying
    on the CI/CD agent to call /api/improvement/inject-cycle.
    Runs for ALL statuses (completed, failed, escalated) to capture partial data.
    """
    if not cycle_num:
        return

    import time as _time_inject
    import json as _json_inject
    from pathlib import Path as _Path_inject
    from ...config import DATA_DIR

    now = _time_inject.strftime("%Y-%m-%dT%H:%M:%SZ")
    ws = _Path_inject(DATA_DIR) / "workspaces" / project_id

    # 1. Compute phase scores from workflow result
    phase_scores = {}
    if result and hasattr(result, "phase_results"):
        for pr in result.phase_results:
            phase_name = pr.get("phase", "")
            dashboard_name = _PHASE_MAP.get(phase_name)
            if dashboard_name:
                phase_scores[dashboard_name] = 80 if pr.get("success") else 30

    # 2. Get git SHA from workspace
    git_sha = ""
    try:
        head_ref = ws / ".git" / "refs" / "heads" / "main"
        if head_ref.exists():
            git_sha = head_ref.read_text().strip()[:12]
        elif (ws / ".git" / "HEAD").exists():
            head_content = (ws / ".git" / "HEAD").read_text().strip()
            if not head_content.startswith("ref:"):
                git_sha = head_content[:12]
            else:
                ref_path = ws / ".git" / head_content.split("ref: ", 1)[1].strip()
                if ref_path.exists():
                    git_sha = ref_path.read_text().strip()[:12]
    except Exception:
        pass

    # 3. Build fix_summary from workspace artifacts
    fix_summary = f"Cycle {cycle_num} — completed"
    try:
        inception = ws / "INCEPTION.md"
        if inception.exists():
            content = inception.read_text(encoding="utf-8", errors="replace")[:500]
            lines = [
                ln.strip()
                for ln in content.split("\n")
                if ln.strip() and not ln.startswith("#")
            ]
            if lines:
                fix_summary = f"Cycle {cycle_num} — " + " · ".join(lines[:3])
    except Exception:
        pass

    # 4. Count defects from adversarial artifacts
    defect_count = 0
    try:
        import re as _re_inject

        for f in ws.glob("ADVERSARIAL*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")
            defect_count += len(
                _re_inject.findall(
                    r"\b(fail|bug|defect|error|reject|violation)\b",
                    text,
                    _re_inject.IGNORECASE,
                )
            )
    except Exception:
        pass

    # 5. Compute total score
    if phase_scores:
        total_score = sum(phase_scores.values()) // len(phase_scores)
    elif run_status in ("failed", "gated", "escalated"):
        total_score = 0
    else:
        total_score = 70  # default for completed cycles with no phase data

    # 6. Check for screenshot
    screenshot_path = ""
    try:
        for ext in ("png", "jpg", "jpeg", "webp"):
            shots = list(ws.glob(f"screenshot*.{ext}")) + list(ws.glob(f"*.{ext}"))
            if shots:
                screenshot_path = str(shots[0].relative_to(ws))
                break
    except Exception:
        pass

    # 7. Write to ac_cycles
    try:
        from ..routes.pages import _ac_get_db, _ac_ensure_tables

        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        conn.execute(
            "INSERT INTO ac_cycles (project_id, cycle_num, git_sha, status, phase_scores,"
            " total_score, defect_count, fix_summary, screenshot_path, started_at, completed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(project_id, cycle_num) DO UPDATE SET"
            " git_sha=COALESCE(NULLIF(excluded.git_sha,''), ac_cycles.git_sha),"
            " status=excluded.status,"
            " phase_scores=CASE WHEN ac_cycles.total_score <= 0 THEN excluded.phase_scores ELSE ac_cycles.phase_scores END,"
            " total_score=CASE WHEN ac_cycles.total_score <= 0 THEN excluded.total_score ELSE ac_cycles.total_score END,"
            " defect_count=CASE WHEN ac_cycles.defect_count = 0 THEN excluded.defect_count ELSE ac_cycles.defect_count END,"
            " fix_summary=CASE WHEN ac_cycles.fix_summary LIKE 'Cycle % — completed' OR ac_cycles.fix_summary LIKE 'Cycle % — active'"
            "   OR ac_cycles.fix_summary LIKE 'Cycle % — unknown' OR ac_cycles.total_score <= 0"
            "   THEN excluded.fix_summary ELSE ac_cycles.fix_summary END,"
            " screenshot_path=COALESCE(NULLIF(excluded.screenshot_path,''), ac_cycles.screenshot_path),"
            " completed_at=COALESCE(NULLIF(excluded.completed_at,''), ac_cycles.completed_at)",
            (
                project_id,
                cycle_num,
                git_sha,
                run_status,
                _json_inject.dumps(phase_scores),
                total_score,
                defect_count,
                fix_summary[:500],
                screenshot_path,
                now,
                now,
            ),
        )
        # Update project state average score
        avg_row = conn.execute(
            "SELECT AVG(total_score) as avg FROM ac_cycles WHERE project_id=? AND total_score > 0",
            (project_id,),
        ).fetchone()
        avg_score = float(avg_row["avg"] or 0) if avg_row else 0.0
        conn.execute(
            "UPDATE ac_project_state SET total_score_avg=?, last_git_sha=?, ci_status='green', updated_at=?"
            " WHERE project_id=?",
            (avg_score, git_sha, now, project_id),
        )
        conn.commit()
        conn.close()
        logger.warning(
            "AUTO-INJECT AC cycle %s/%d: score=%d phases=%s sha=%s defects=%d",
            project_id,
            cycle_num,
            total_score,
            _json_inject.dumps(phase_scores),
            git_sha,
            defect_count,
        )
    except Exception as _db_err:
        logger.warning("Auto-inject DB write failed: %s", _db_err)


async def _run_workflow_background(
    wf, session_id: str, task: str, project_id: str, resume_from: int = 0
):
    """Background workflow execution."""
    from ...workflows.store import run_workflow
    from ...sessions.store import get_session_store, MessageDef
    from .helpers import _active_mission_tasks

    # Mark epic_run as running at task start — overrides any 'paused' set by
    # startup cleanup that raced with asyncio task scheduling.
    try:
        from ...db.migrations import get_db as _gdb_start

        _db_start = _gdb_start()
        _db_start.execute(
            "UPDATE epic_runs SET status='running' WHERE session_id=?",
            (session_id,),
        )
        _db_start.commit()
        _db_start.close()
    except Exception:
        pass

    _final_run_status = "failed"  # track for finally block — default "failed" so any crash resets ac_project_state
    _run_exception: Exception | None = None  # captured for escalation reason extraction
    try:
        result = await run_workflow(
            wf, session_id, task, project_id, resume_from=resume_from
        )
        _final_run_status = result.status  # "completed", "paused", "failed", etc.

        # Update linked mission status if autoheal
        sess_store = get_session_store()
        sess = sess_store.get(session_id)
        if (
            sess
            and sess.config
            and sess.config.get("autoheal")
            and result.status != "paused"
        ):
            mission_id = sess.config.get("mission_id")
            if mission_id:
                from ...epics.store import get_epic_store

                ms = get_epic_store()
                final = "completed" if result.status == "completed" else "failed"
                ms.update_mission_status(mission_id, final)
                logger.info("Auto-heal mission %s → %s", mission_id, final)

        # Workflow chaining: auto-launch next workflow on completion (not when paused)
        on_complete = wf.config.get("on_complete") if wf.config else None
        if on_complete and isinstance(on_complete, dict) and result.status != "paused":
            condition = on_complete.get("condition", "completed")
            if condition == "always" or result.status == condition:
                next_wf_id = on_complete.get("workflow_id")
                if next_wf_id:
                    try:
                        from ...workflows.store import (
                            get_workflow_store as _get_wf_store,
                        )
                        from ...sessions.store import SessionDef

                        next_wf = _get_wf_store().get(next_wf_id)
                        if next_wf:
                            next_sess = get_session_store().create(
                                SessionDef(
                                    name=f"{next_wf.name} ← {wf.name}",
                                    description=f"Auto-chaîné depuis '{wf.name}'",
                                    project_id=project_id,
                                    status="active",
                                    goal=task,
                                    config={
                                        "workflow_id": next_wf_id,
                                        "chained_from": session_id,
                                    },
                                )
                            )
                            asyncio.create_task(
                                _run_workflow_background(
                                    next_wf, next_sess.id, task, project_id
                                )
                            )
                            logger.info(
                                "Workflow chain: %s → %s (new session %s)",
                                wf.id,
                                next_wf_id,
                                next_sess.id,
                            )
                    except Exception as _chain_err:
                        logger.error(
                            "Workflow chaining failed %s → %s: %s",
                            wf.id,
                            next_wf_id,
                            _chain_err,
                        )
    except Exception as e:
        _run_exception = e
        logger.error("Workflow failed: %s", e)
        # Detect adversarial escalation to track reason separately from generic failures
        if type(e).__name__ in ("AdversarialEscalation", "AdversarialEscalationError"):
            _final_run_status = "escalated"
        get_session_store().add_message(
            MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"Workflow error: {e}",
            )
        )
        # Mark session as failed
        try:
            get_session_store().update_status(session_id, "failed")
        except Exception:
            pass
    finally:
        # Update linked epic_run status so it doesn't stay 'running' on restart
        # Use the actual final status: "paused" when awaiting human, "completed" otherwise
        try:
            from ...db.migrations import get_db as _gdb

            _db = _gdb()
            mr_status = "paused" if _final_run_status == "paused" else "completed"
            _db.execute(
                "UPDATE epic_runs SET status=? WHERE session_id=? AND status='running'",
                (mr_status, session_id),
            )
            _db.commit()
        except Exception:
            pass
        _active_mission_tasks.pop(session_id, None)
        # If an AC cycle was gated/failed, reset ac_project_state so watchdog doesn't retry infinitely
        if project_id and _final_run_status in ("gated", "failed", "escalated"):
            try:
                from ...db.migrations import get_db as _gdb2
                from datetime import datetime as _dt

                # Extract escalation reason from exception or phase_results if available
                _escalation_reason = None
                try:
                    # Primary: extract from the caught exception (AdversarialEscalation etc.)
                    if _run_exception is not None:
                        _escalation_reason = str(_run_exception)[:500]
                    else:
                        _phase_results = (
                            getattr(result, "phase_results", [])
                            if "result" in dir()
                            else []
                        )
                        # Pick the first failed phase as the reason (escalated or error)
                        for _pr in _phase_results:
                            if not _pr.get("success", True):
                                _escalation_reason = str(_pr.get("error") or _pr)[:500]
                                break
                except Exception:
                    pass

                _db2 = _gdb2()
                _now = _dt.utcnow().isoformat()
                if _escalation_reason:
                    _db2.execute(
                        "UPDATE ac_project_state SET status='idle', current_run_id=NULL, updated_at=?,"
                        " last_escalation_reason=?, last_escalation_at=?"
                        " WHERE project_id=? AND status='running'",
                        (_now, _escalation_reason, _now, project_id),
                    )
                else:
                    _db2.execute(
                        "UPDATE ac_project_state SET status='idle', current_run_id=NULL, updated_at=?"
                        " WHERE project_id=? AND status='running'",
                        (_now, project_id),
                    )
                # Also mark session as completed so the watchdog doesn't resume it
                _db2.execute(
                    "UPDATE sessions SET status='completed' WHERE id=? AND status IN ('interrupted','active','running')",
                    (session_id,),
                )
                _db2.commit()
                logger.warning(
                    "AC cycle gated/failed — reset project %s to idle (run=%s, reason=%s)",
                    project_id,
                    _final_run_status,
                    (_escalation_reason or "")[:100],
                )
                # Record failed/gated cycle in ac_cycles for history UI
                try:
                    import json as _json_ac

                    _sess_row2 = _db2.execute(
                        "SELECT config_json FROM sessions WHERE id=?", (session_id,)
                    ).fetchone()
                    _sess_cfg2 = _json_ac.loads(
                        _sess_row2["config_json"]
                        if _sess_row2 and _sess_row2.get("config_json")
                        else "{}"
                    )
                    _cycle_num_fail = _sess_cfg2.get("cycle_num", 0)
                    if _cycle_num_fail:
                        _db2.execute(
                            "INSERT INTO ac_cycles (project_id, cycle_num, status, fix_summary, started_at, completed_at)"
                            " VALUES (?,?,?,?,?,?)"
                            " ON CONFLICT(project_id, cycle_num) DO UPDATE SET"
                            " status=excluded.status, fix_summary=excluded.fix_summary, completed_at=excluded.completed_at",
                            (
                                project_id,
                                _cycle_num_fail,
                                "failed",
                                (_escalation_reason or "gated/failed")[:500],
                                _now,
                                _now,
                            ),
                        )
                        _db2.commit()
                except Exception as _ace:
                    logger.warning("Failed to record failed AC cycle: %s", _ace)
            except Exception as _e:
                logger.warning("Failed to reset AC project state: %s", _e)
        # Re-enable auto-resume after AC cycle completes (any status)
        try:
            _sess_for_ar = get_session_store().get(session_id)
            _cfg_for_ar = (
                _sess_for_ar.config if _sess_for_ar and _sess_for_ar.config else {}
            )
            if _cfg_for_ar.get("type") == "ac-builder":
                import os as _os_ar

                _os_ar.environ["PLATFORM_AUTO_RESUME_ENABLED"] = "1"
                logger.warning(
                    "AC cycle ended (%s): auto-resume RE-ENABLED", _final_run_status
                )
        except Exception:
            pass

        # ── Auto-inject AC cycle results on ANY builder completion ──
        # Always capture data (even partial) for the dashboard.
        if project_id:
            try:
                _sess_for_inject = get_session_store().get(session_id)
                _cfg_inject = (
                    _sess_for_inject.config
                    if _sess_for_inject and _sess_for_inject.config
                    else {}
                )
                if _cfg_inject.get("type") == "ac-builder":
                    _auto_inject_ac_cycle(
                        project_id,
                        _cfg_inject.get("cycle_num", 0),
                        result if "result" in dir() else None,
                        session_id,
                        run_status=_final_run_status,
                    )
            except Exception as _inject_err:
                logger.warning("Auto-inject AC cycle failed: %s", _inject_err)

        # Safety net: always reset to idle if still running at end of workflow
        if project_id and _final_run_status not in ("gated", "failed", "escalated"):
            try:
                from ...db.migrations import get_db as _gdb3
                from datetime import datetime as _dt2

                _db3 = _gdb3()
                _db3.execute(
                    "UPDATE ac_project_state SET status='idle', current_run_id=NULL, updated_at=?"
                    " WHERE project_id=? AND status='running'",
                    (_dt2.utcnow().isoformat(), project_id),
                )
                _db3.commit()
                _db3.close()
            except Exception as _e3:
                logger.warning("Safety idle reset failed: %s", _e3)


# ── Workflow Resume ───────────────────────────────────────────────


@router.post("/api/workflow/{session_id}/resume")
async def workflow_resume(session_id: str):
    """Resume a workflow from its last checkpoint (skips completed phases)."""
    from ...sessions.store import get_session_store
    from ...workflows.store import get_workflow_store

    store = get_session_store()
    sess = store.get(session_id)
    if not sess:
        return {"error": "Session not found"}
    config = sess.config or {}
    wf_id = config.get("workflow_id")
    if not wf_id:
        return {"error": "No workflow_id in session config"}
    wf = get_workflow_store().get(wf_id)
    if not wf:
        return {"error": f"Workflow {wf_id} not found"}
    task = sess.goal or sess.name
    project_id = sess.project_id or ""
    resume_from = config.get("workflow_checkpoint", 0)
    asyncio.create_task(
        _run_workflow_background(
            wf, session_id, task, project_id, resume_from=resume_from
        )
    )
    return {
        "status": "resumed",
        "session_id": session_id,
        "workflow_id": wf_id,
        "resume_from_phase": resume_from,
    }


@router.post("/api/workflow/{session_id}/nogo")
async def workflow_nogo(session_id: str):
    """Reject a paused workflow checkpoint — stops the workflow as failed."""
    from ...sessions.store import get_session_store
    from ...db.migrations import get_db

    store = get_session_store()
    sess = store.get(session_id)
    if not sess:
        return {"error": "Session not found"}

    store.update_status(session_id, "failed")

    # Record NO GO message in thread
    from ...sessions.store import MessageDef

    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="system",
            to_agent="user",
            message_type="system",
            content="**❌ NO GO — Workflow arrêté**\n\nLe checkpoint humain a été rejeté. Le workflow a été interrompu.",
        )
    )

    # Update mission run to failed if linked
    config = sess.config or {}
    epic_run_id = config.get("epic_run_id")
    if epic_run_id:
        try:
            from datetime import datetime, timezone

            db = get_db()
            db.execute(
                "UPDATE epic_runs SET status='failed', completed_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), epic_run_id),
            )
            db.commit()
            db.close()
        except Exception:
            pass

    return {"status": "nogo", "session_id": session_id}


@router.get("/dsi", response_class=HTMLResponse)
async def dsi_board_page(request: Request):
    """DSI strategic dashboard — kanban pipeline + KPIs."""
    from ...projects.manager import get_project_store
    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_store

    project_store = get_project_store()
    agent_store = get_agent_store()
    epic_store = get_epic_store()

    all_projects = project_store.list_all()
    all_agents = agent_store.list_all()
    all_missions = epic_store.list_missions()

    # Load mission runs for live phase progress
    from ...epics.store import get_epic_run_store

    run_store = get_epic_run_store()
    all_runs = run_store.list_runs(limit=100)
    runs_by_mission: dict = {}
    for r in all_runs:
        if r.parent_epic_id:
            runs_by_mission[r.parent_epic_id] = r
        runs_by_mission[r.id] = r

    def _phase_stats(mission_id):
        """Get progress from epic_run phases (live) or fallback to tasks."""
        run = runs_by_mission.get(mission_id)
        if run and run.phases:
            total = len(run.phases)
            done = sum(
                1
                for ph in run.phases
                if ph.status.value in ("done", "done_with_issues")
            )
            current = run.current_phase or ""
            current_name = next(
                (ph.phase_name for ph in run.phases if ph.phase_id == current), current
            )
            return {
                "total": total,
                "done": done,
                "current_phase": current_name,
                "run_status": run.status.value,
            }
        stats = epic_store.mission_stats(mission_id)
        return {
            "total": stats.get("total", 0),
            "done": stats.get("done", 0),
            "current_phase": "",
            "run_status": "",
        }

    # KPIs
    active_missions = sum(1 for m in all_missions if m.status == "active")
    blocked_missions = sum(1 for m in all_missions if m.status == "blocked")
    total_phases = 0
    total_phases_done = 0
    for m in all_missions:
        ps = _phase_stats(m.id)
        total_phases += ps["total"]
        total_phases_done += ps["done"]

    # Pipeline kanban columns
    project_names = {p.id: p.name for p in all_projects}
    statuses = [
        ("backlog", "Backlog", "planning"),
        ("planning", "Planning", "planning"),
        ("active", "En cours", "active"),
        ("review", "Review", "completed"),
        ("completed", "Terminé", "completed"),
    ]
    pipeline = []
    for status_key, label, match_status in statuses:
        col_missions = []
        # "backlog" = missions in planning with no sprint
        if status_key == "backlog":
            for m in all_missions:
                if m.status == "planning":
                    sprints = epic_store.list_sprints(m.id)
                    if not sprints:
                        ps = _phase_stats(m.id)
                        col_missions.append(
                            {
                                "id": m.id,
                                "name": m.name,
                                "project_name": project_names.get(
                                    m.project_id, m.project_id
                                ),
                                "wsjf": m.wsjf_score,
                                "total": ps["total"],
                                "done": ps["done"],
                                "current_phase": ps["current_phase"],
                            }
                        )
        elif status_key == "planning":
            for m in all_missions:
                if m.status == "planning":
                    sprints = epic_store.list_sprints(m.id)
                    if sprints:
                        ps = _phase_stats(m.id)
                        col_missions.append(
                            {
                                "id": m.id,
                                "name": m.name,
                                "project_name": project_names.get(
                                    m.project_id, m.project_id
                                ),
                                "wsjf": m.wsjf_score,
                                "total": ps["total"],
                                "done": ps["done"],
                                "current_phase": ps["current_phase"],
                            }
                        )
        elif status_key == "review":
            for m in all_missions:
                sprints = epic_store.list_sprints(m.id)
                if any(s.status == "review" for s in sprints) and m.status == "active":
                    ps = _phase_stats(m.id)
                    col_missions.append(
                        {
                            "id": m.id,
                            "name": m.name,
                            "project_name": project_names.get(
                                m.project_id, m.project_id
                            ),
                            "wsjf": m.wsjf_score,
                            "total": ps["total"],
                            "done": ps["done"],
                            "current_phase": ps["current_phase"],
                        }
                    )
        else:
            for m in all_missions:
                if m.status == match_status:
                    if status_key == "active":
                        sprints = epic_store.list_sprints(m.id)
                        if any(s.status == "review" for s in sprints):
                            continue
                    ps = _phase_stats(m.id)
                    col_missions.append(
                        {
                            "id": m.id,
                            "name": m.name,
                            "project_name": project_names.get(
                                m.project_id, m.project_id
                            ),
                            "wsjf": m.wsjf_score,
                            "total": ps["total"],
                            "done": ps["done"],
                            "current_phase": ps["current_phase"],
                        }
                    )
        pipeline.append({"status": status_key, "label": label, "epics": col_missions})

    # Resource allocation per project (phase-based progress)
    resources = []
    project_colors = [
        "var(--purple)",
        "var(--blue)",
        "var(--green)",
        "var(--yellow)",
        "var(--red)",
        "#06b6d4",
        "#8b5cf6",
    ]
    for i, p in enumerate(all_projects):
        p_missions = [m for m in all_missions if m.project_id == p.id]
        if not p_missions:
            continue
        p_phases_total = 0
        p_phases_done = 0
        for m in p_missions:
            ps = _phase_stats(m.id)
            p_phases_total += ps["total"]
            p_phases_done += ps["done"]
        pct = round(p_phases_done / max(p_phases_total, 1) * 100)
        resources.append(
            {
                "name": p.name,
                "total": p_phases_total,
                "active": p_phases_done,
                "pct": pct,
                "color": project_colors[i % len(project_colors)],
            }
        )

    # Strategic agents
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"
    strategic = []
    for a in all_agents:
        if any(t == "strategy" for t in (a.tags or [])):
            jpg = avatar_dir / f"{a.id}.jpg"
            svg_f = avatar_dir / f"{a.id}.svg"
            avatar_url = (
                f"/static/avatars/{a.id}.jpg"
                if jpg.exists()
                else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
            )
            strategic.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                    "avatar": a.avatar or a.icon or "bot",
                    "color": a.color or "#7c3aed",
                    "avatar_url": avatar_url,
                    "description": a.description or "",
                    "tagline": a.tagline or "",
                    "persona": a.persona or "",
                    "motivation": a.motivation or "",
                    "skills": a.skills or [],
                    "tools": a.tools or [],
                    "mcps": a.mcps or [],
                    "model": a.model or "",
                    "provider": getattr(a, "provider", "") or "",
                }
            )

    # Recent session messages for decisions feed
    from ...sessions.store import get_session_store

    session_store = get_session_store()
    recent_sessions = session_store.list_all(limit=5)
    decisions = []
    for sess in recent_sessions:
        msgs = session_store.get_messages(sess.id, limit=3)
        for msg in msgs:
            if msg.from_agent != "user" and len(msg.content) > 20:
                decisions.append(
                    {
                        "session_name": sess.name or sess.id[:8],
                        "agent_name": msg.from_agent or "Agent",
                        "content": msg.content[:120],
                        "time": str(msg.timestamp)[:16].replace(" ", "T")
                        if msg.timestamp
                        else "",
                        "status": "approved",
                    }
                )
        if len(decisions) >= 6:
            break

    # Workflow patterns for system map
    from ...workflows.store import get_workflow_store

    wf_store = get_workflow_store()
    all_workflows = wf_store.list_all()
    system_patterns = []
    for wf in all_workflows:
        cfg = wf.config or {}
        graph = cfg.get("graph", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        pattern = wf.phases[0].pattern_id if wf.phases else "sequential"
        system_patterns.append(
            {
                "id": wf.id,
                "name": wf.name,
                "pattern": pattern,
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        )

    # DORA metrics
    from ...metrics.dora import get_dora_metrics

    dora = get_dora_metrics().summary(period_days=30)

    # Org summary
    from ...agents.org import get_org_store

    org = get_org_store()
    org_portfolios = org.list_portfolios()
    org_arts = org.list_arts()
    org_teams = org.list_teams()

    return _templates(request).TemplateResponse(
        "dsi.html",
        {
            "request": request,
            "page_title": "Vue DSI",
            "total_missions": len(all_missions),
            "active_missions": active_missions,
            "blocked_missions": blocked_missions,
            "total_tasks": total_phases,
            "total_done": total_phases_done,
            "total_agents": len(all_agents),
            "total_projects": len(all_projects),
            "pipeline": pipeline,
            "resources": resources,
            "strategic_agents": strategic,
            "decisions": decisions,
            "system_patterns": system_patterns,
            "dora": dora,
            "org_portfolios": len(org_portfolios),
            "org_arts": len(org_arts),
            "org_teams": len(org_teams),
        },
    )


# ── DSI Workflow Phases ──────────────────────────────────────────


@router.get("/dsi/workflow/{workflow_id}", response_class=HTMLResponse)
async def dsi_workflow_page(request: Request, workflow_id: str):
    """DSI workflow with phased timeline, agent graph, and message feed."""
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store
    from ...agents.store import get_agent_store
    from pathlib import Path

    wf_store = get_workflow_store()
    session_store = get_session_store()
    agent_store = get_agent_store()

    wf = wf_store.get(workflow_id)
    if not wf:
        return HTMLResponse("<h2>Workflow introuvable</h2>", 404)

    cfg = wf.config or {}
    graph_cfg = cfg.get("graph", {})
    # Phases from WorkflowPhase objects (phases_json) or fallback to config
    if wf.phases:
        phases_cfg = []
        for wp in wf.phases:
            pc = wp.config or {}
            phases_cfg.append(
                {
                    "id": wp.id,
                    "name": wp.name,
                    "pattern_id": wp.pattern_id,
                    "gate": wp.gate,
                    "description": wp.description,
                    "agents": pc.get("agents", []),
                    "leader": pc.get("leader", ""),
                    "deliverables": pc.get("deliverables", []),
                }
            )
    else:
        phases_cfg = cfg.get("phases", [])
    avatar_dir = Path(__file__).parent.parent / "static" / "avatars"

    # Find active session for this workflow
    all_sessions = session_store.list_all(limit=50)
    session = None
    for s in all_sessions:
        s_cfg = s.config or {}
        if s_cfg.get("workflow_id") == workflow_id:
            session = s
            break

    # Determine current phase from session config
    current_phase_id = None
    phase_statuses = {}
    if session:
        s_cfg = session.config or {}
        current_phase_id = s_cfg.get(
            "current_phase", phases_cfg[0]["id"] if phases_cfg else None
        )
        phase_statuses = s_cfg.get("phase_statuses", {})

    # Build phases list with status
    phase_colors = ["#a855f7", "#3b82f6", "#f59e0b", "#34d399"]
    phases = []
    current_phase = None
    current_phase_idx = 0
    for i, p in enumerate(phases_cfg):
        status = phase_statuses.get(p["id"], "waiting")
        if current_phase_id and p["id"] == current_phase_id:
            status = "active"
            current_phase_idx = i
        elif current_phase_id:
            idx_current = next(
                (j for j, pp in enumerate(phases_cfg) if pp["id"] == current_phase_id),
                0,
            )
            if i < idx_current:
                status = "done"
        phase_data = {
            "id": p["id"],
            "name": p["name"],
            "pattern_id": p.get("pattern_id", ""),
            "gate": p.get("gate", ""),
            "description": p.get("description", ""),
            "agents": p.get("agents", []),
            "leader": p.get("leader", ""),
            "deliverables": p.get("deliverables", []),
            "status": status,
            "color": phase_colors[i % len(phase_colors)],
        }
        phases.append(phase_data)
        if status == "active":
            current_phase = phase_data

    if not current_phase and phases:
        current_phase = phases[0]
        current_phase["status"] = "active"
        current_phase_idx = 0

    # Build phase agents
    phase_agents = []
    if current_phase:
        for aid in current_phase["agents"]:
            a = agent_store.get(aid)
            if a:
                jpg = avatar_dir / f"{a.id}.jpg"
                svg_f = avatar_dir / f"{a.id}.svg"
                avatar_url = (
                    f"/static/avatars/{a.id}.jpg"
                    if jpg.exists()
                    else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
                )
                phase_agents.append(
                    {
                        "id": a.id,
                        "name": a.name,
                        "role": a.role,
                        "avatar_url": avatar_url,
                        "color": a.color or "#7c3aed",
                        "is_leader": aid == current_phase.get("leader"),
                        "status": "idle",
                    }
                )

    # Deliverables for current phase
    deliverables = []
    if current_phase:
        for d in current_phase.get("deliverables", []):
            deliverables.append({"label": d, "done": False})

    # Messages from session
    messages = []
    agent_names = {}
    # Build agent_map for unified message component
    dsi_agent_map = {}

    def _resolve_agent(aid):
        if aid and aid not in agent_names:
            a = agent_store.get(aid)
            if a:
                jpg = avatar_dir / f"{a.id}.jpg"
                svg_f = avatar_dir / f"{a.id}.svg"
                agent_names[aid] = {
                    "name": a.name,
                    "avatar_url": f"/static/avatars/{a.id}.jpg"
                    if jpg.exists()
                    else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else ""),
                }
                dsi_agent_map[aid] = {
                    "name": a.name,
                    "icon": a.icon or "bot",
                    "color": a.color or "#8b949e",
                    "role": a.role or "",
                    "avatar": getattr(a, "avatar", "bot"),
                    "avatar_url": _avatar_url(a.id),
                }
            else:
                agent_names[aid] = {"name": aid, "avatar_url": ""}
        return agent_names.get(aid, {"name": aid or "?", "avatar_url": ""})

    if session:
        all_msgs = session_store.get_messages(session.id, limit=100)
        for msg in all_msgs:
            if msg.message_type == "system" or msg.from_agent == "system":
                continue
            content = (msg.content or "").strip()
            if not content:
                continue
            from_info = _resolve_agent(msg.from_agent)
            to_info = _resolve_agent(msg.to_agent) if msg.to_agent else None
            action = None
            if "[DELEGATE" in content:
                action = "delegate"
            elif "[VETO" in content:
                action = "veto"
            elif "[APPROVE" in content:
                action = "approve"
            # Clean action tags from display content
            import re as _re

            display = _re.sub(r"\[DELEGATE:[^\]]*\]\s*", "", content)
            display = _re.sub(r"\[VETO[^\]]*\]\s*", "", display)
            display = _re.sub(r"\[APPROVE\]\s*", "", display)
            display = _re.sub(r"\[ASK:[^\]]*\]\s*", "", display)
            display = _re.sub(r"\[ESCALATE[^\]]*\]\s*", "", display)
            display = display.strip()[:800]
            messages.append(
                {
                    "from_name": from_info["name"],
                    "from_id": msg.from_agent,
                    "avatar_url": from_info["avatar_url"],
                    "to_name": to_info["name"] if to_info else None,
                    "to_id": msg.to_agent,
                    "content": display,
                    "time": str(msg.timestamp or "")[:16].replace(" ", "T"),
                    "action": action,
                    "message_type": msg.message_type,
                }
            )

    # Build graph nodes with positions
    graph_nodes_cfg = graph_cfg.get("nodes", [])
    graph_edges_cfg = graph_cfg.get("edges", [])

    # Map node positions — remap Y to fit phase bands
    phase_y_bands = {
        "p1-cadrage": 55,
        "p2-architecture": 145,
        "p3-sprint-setup": 240,
        "p4-delivery": 335,
    }
    node_positions = {}
    graph_nodes = []
    for n in graph_nodes_cfg:
        node_phases = (n.get("phase") or "").split(",")
        primary_phase = node_phases[0] if node_phases else ""
        phase_color = "#7c3aed"
        y = n.get("y", 100)
        if primary_phase in phase_y_bands:
            y = phase_y_bands[primary_phase]
            idx = list(phase_y_bands.keys()).index(primary_phase)
            phase_color = phase_colors[idx % len(phase_colors)]
        # Scale x to fit 850px viewbox
        x = max(40, min(810, n.get("x", 400)))

        a = agent_store.get(n.get("agent_id", ""))
        avatar_url = ""
        if a:
            jpg = avatar_dir / f"{a.id}.jpg"
            svg_f = avatar_dir / f"{a.id}.svg"
            avatar_url = (
                f"/static/avatars/{a.id}.jpg"
                if jpg.exists()
                else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
            )

        is_active = current_phase and n.get("agent_id") in current_phase.get(
            "agents", []
        )
        node_positions[n["id"]] = (x, y)
        graph_nodes.append(
            {
                "id": n["id"],
                "agent_id": n.get("agent_id", ""),
                "x": x,
                "y": y,
                "label": n.get("label", ""),
                "phase_color": phase_color,
                "avatar_url": avatar_url,
                "is_active": is_active,
            }
        )

    # Build graph edges
    graph_edges = []
    for e in graph_edges_cfg:
        from_pos = node_positions.get(e["from"])
        to_pos = node_positions.get(e["to"])
        if from_pos and to_pos:
            graph_edges.append(
                {
                    "x1": from_pos[0],
                    "y1": from_pos[1],
                    "x2": to_pos[0],
                    "y2": to_pos[1],
                    "color": e.get("color", "#7c3aed"),
                }
            )

    # All agents JSON for popover
    all_agents_json = {}
    for a in agent_store.list_all():
        jpg = avatar_dir / f"{a.id}.jpg"
        svg_f = avatar_dir / f"{a.id}.svg"
        avatar_url = (
            f"/static/avatars/{a.id}.jpg"
            if jpg.exists()
            else (f"/static/avatars/{a.id}.svg" if svg_f.exists() else "")
        )
        all_agents_json[a.id] = {
            "name": a.name,
            "role": a.role,
            "avatar_url": avatar_url,
            "color": a.color or "#7c3aed",
            "description": a.description or "",
            "tagline": a.tagline or "",
            "persona": a.persona or "",
            "motivation": a.motivation or "",
            "skills": a.skills or [],
            "tools": a.tools or [],
        }

    return _templates(request).TemplateResponse(
        "dsi_workflow.html",
        {
            "request": request,
            "page_title": f"DSI — {wf.name}",
            "workflow": wf,
            "phases": phases,
            "current_phase": current_phase,
            "current_phase_idx": current_phase_idx,
            "phase_agents": phase_agents,
            "deliverables": deliverables,
            "messages": messages,
            "agent_map": dsi_agent_map,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "session": session,
            "session_id": session.id if session else None,
            "all_agents_json": all_agents_json,
        },
    )


@router.api_route(
    "/api/dsi/workflow/{workflow_id}/start",
    methods=["GET", "POST"],
    response_class=HTMLResponse,
)
async def dsi_workflow_start(request: Request, workflow_id: str):
    """Start phase 1 of a DSI workflow — creates session and launches agents."""
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store, SessionDef
    from ...agents.loop import get_loop_manager
    from ...a2a.bus import get_bus
    import uuid

    wf_store = get_workflow_store()
    wf = wf_store.get(workflow_id)
    if not wf:
        return HTMLResponse("Workflow introuvable", 404)

    cfg = wf.config or {}
    # Read phases from wf.phases (WorkflowPhase objects), fallback to config
    if wf.phases:
        phases = []
        for p in wf.phases:
            pd = {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "pattern_id": p.pattern_id,
                "gate": p.gate,
            }
            pd.update(p.config or {})
            phases.append(pd)
    else:
        phases = cfg.get("phases", [])
    if not phases:
        return HTMLResponse("Pas de phases", 400)

    phase1 = phases[0]
    project_id = cfg.get("project_id", "")

    # Create session
    session_store = get_session_store()
    session = SessionDef(
        name=f"{wf.name} — {phase1['name']}",
        description=wf.description,
        project_id=project_id,
        status="active",
        goal=phase1.get("description", ""),
        config={
            "workflow_id": workflow_id,
            "current_phase": phase1["id"],
            "phase_statuses": {phase1["id"]: "active"},
        },
    )
    session = session_store.create(session)

    # Start agent loops for phase 1
    manager = get_loop_manager()
    bus = get_bus()
    # Load project for path
    from ...projects.manager import get_project_store

    project = get_project_store().get(project_id)
    project_path = project.path if project and project.path else ""
    for aid in phase1.get("agents", []):
        await manager.start_agent(
            aid, session.id, project_id=project_id, project_path=project_path
        )

    # Send kickoff message to the leader
    leader = phase1.get(
        "leader", phase1.get("agents", [""])[0] if phase1.get("agents") else ""
    )
    if leader:
        # Load project VISION if exists
        vision = ""
        if project and project.path:
            import os

            vision_path = os.path.join(project.path, "VISION.md")
            if os.path.exists(vision_path):
                with open(vision_path, "r") as f:
                    vision = f.read()[:3000]

        kickoff = f"""**Phase 1 : {phase1["name"]}**

**Objectif:** {phase1.get("description", "")}

**Livrables attendus:** {", ".join(phase1.get("deliverables", []))}

**Équipe disponible:** {", ".join(phase1.get("agents", []))}

**Pattern:** {phase1.get("pattern_id", "hierarchical")}

{f"**VISION du projet:**{chr(10)}{vision}" if vision else ""}

**INSTRUCTIONS:**
1. Vous êtes le leader de cette phase. Coordonnez votre équipe.
2. Utilisez `[DELEGATE:agent_id] instruction` pour assigner des tâches aux membres de l'équipe.
3. Utilisez les outils `deep_search` et `code_read` pour analyser le code source du projet.
4. Produisez chaque livrable de façon concrète et détaillée.
5. Quand tous les livrables sont prêts, utilisez `[APPROVE]` pour valider la phase.
6. Si un problème bloque, utilisez `[ESCALATE]` pour remonter.

Commencez par analyser la situation et déléguer les premières tâches."""

        from ...models import A2AMessage, MessageType

        msg = A2AMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            from_agent="user",
            to_agent=leader,
            message_type=MessageType.REQUEST,
            content=kickoff,
        )
        await bus.publish(msg)

    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)


@router.get("/api/debug/agents")
async def debug_agents():
    """Debug endpoint: show running agent loops and their status."""
    from ...agents.loop import get_loop_manager

    manager = get_loop_manager()
    import asyncio

    result = []
    for key, loop in manager._loops.items():
        task_done = loop._task.done() if loop._task else True
        task_exception = None
        if task_done and loop._task:
            try:
                exc = loop._task.exception()
                task_exception = str(exc) if exc else None
            except (asyncio.CancelledError, asyncio.InvalidStateError):
                pass
        result.append(
            {
                "key": key,
                "agent_id": loop.agent.id,
                "session_id": loop.session_id,
                "status": loop.status.value,
                "task_done": task_done,
                "task_exception": task_exception,
                "inbox_size": loop._inbox.qsize(),
                "messages_sent": loop.instance.messages_sent,
                "messages_received": loop.instance.messages_received,
                "tokens_used": loop.instance.tokens_used,
            }
        )
    return JSONResponse(result)


@router.api_route(
    "/api/dsi/workflow/{workflow_id}/next-phase",
    methods=["GET", "POST"],
    response_class=HTMLResponse,
)
async def dsi_workflow_next_phase(request: Request, workflow_id: str):
    """Advance to next phase in workflow."""
    from ...workflows.store import get_workflow_store
    from ...sessions.store import get_session_store
    from ...agents.loop import get_loop_manager
    from ...a2a.bus import get_bus
    import uuid

    if request.method == "POST":
        form = await request.form()
        session_id = form.get("session_id", "")
    else:
        session_id = request.query_params.get("session_id", "")

    wf_store = get_workflow_store()
    session_store = get_session_store()
    wf = wf_store.get(workflow_id)
    session = session_store.get_session(session_id)
    if not wf or not session:
        return HTMLResponse("Not found", 404)

    cfg = wf.config or {}
    # Read phases from wf.phases (WorkflowPhase objects), fallback to config
    if wf.phases:
        phases = []
        for p in wf.phases:
            pd = {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "pattern_id": p.pattern_id,
                "gate": p.gate,
            }
            pd.update(p.config or {})
            phases.append(pd)
    else:
        phases = cfg.get("phases", [])
    s_cfg = session.config or {}
    current_phase_id = s_cfg.get("current_phase", "")
    phase_statuses = s_cfg.get("phase_statuses", {})

    # Find next phase
    current_idx = next(
        (i for i, p in enumerate(phases) if p["id"] == current_phase_id), 0
    )
    if current_idx >= len(phases) - 1:
        from starlette.responses import RedirectResponse

        return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)

    # Mark current as done, advance
    phase_statuses[current_phase_id] = "done"
    next_phase = phases[current_idx + 1]
    phase_statuses[next_phase["id"]] = "active"
    s_cfg["current_phase"] = next_phase["id"]
    s_cfg["phase_statuses"] = phase_statuses

    # Update session
    from ...db.migrations import get_db
    import json

    db = get_db()
    db.execute(
        "UPDATE sessions SET config_json=?, name=? WHERE id=?",
        (json.dumps(s_cfg), f"{wf.name} — {next_phase['name']}", session_id),
    )
    db.commit()

    # Stop old loops, start new ones
    manager = get_loop_manager()
    await manager.stop_session(session_id)
    project_id = cfg.get("project_id", "")
    from ...projects.manager import get_project_store

    project = get_project_store().get(project_id) if project_id else None
    project_path = project.path if project and project.path else ""
    for aid in next_phase.get("agents", []):
        await manager.start_agent(
            aid, session_id, project_id=project_id, project_path=project_path
        )

    # Send kickoff to new phase leader
    leader = next_phase.get(
        "leader", next_phase["agents"][0] if next_phase["agents"] else ""
    )
    if leader:
        kickoff = f"""**Phase {current_idx + 2} : {next_phase["name"]}**

**Objectif:** {next_phase.get("description", "")}

**Livrables attendus:** {", ".join(next_phase.get("deliverables", []))}

**Équipe:** {", ".join(next_phase.get("agents", []))}

La phase précédente est terminée. Prenez le relais et produisez les livrables de cette phase.
Utilisez [DELEGATE:agent_id] pour assigner des tâches."""

        from ...models import A2AMessage, MessageType

        msg = A2AMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            from_agent="user",
            to_agent=leader,
            message_type=MessageType.REQUEST,
            content=kickoff,
        )
        bus = get_bus()
        await bus.publish(msg)

    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/dsi/workflow/{workflow_id}", status_code=303)
