"""Pulse API — Lean UX dashboard endpoints.

Only useful-now data. Three sections:
1. KPIs: running / blocked / done-today (3 numbers)
2. Blocked: missions needing action (expanded cards)
3. Running: missions in progress (collapsed progress bars)
4. Done: completed today count

Apple-style: no noise, no perspectives, no 8-tab overload.
"""
# Ref: feat-lean-ux

from __future__ import annotations

import html as html_mod
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _phase_status_value(ph) -> str:
    """Extract phase status string safely."""
    s = getattr(ph, "status", None)
    if s is None:
        return ""
    return s.value if hasattr(s, "value") else str(s)


def _run_status_value(run) -> str:
    """Extract run status string safely."""
    s = getattr(run, "status", None)
    if s is None:
        return ""
    return s.value if hasattr(s, "value") else str(s)


def _run_progress(run) -> tuple[int, int, int]:
    """Return (done, total, pct) for a run."""
    phases = getattr(run, "phases", None) or []
    total = len(phases)
    done = sum(1 for p in phases if _phase_status_value(p) in ("done", "done_with_issues"))
    pct = int(done / total * 100) if total > 0 else 0
    return done, total, pct


def _current_phase_name(run) -> str:
    """Return name of currently running phase."""
    for p in getattr(run, "phases", None) or []:
        if _phase_status_value(p) in ("running", "active", "waiting_validation"):
            return getattr(p, "name", None) or getattr(p, "phase_name", "") or getattr(p, "id", "")
    return ""


def _is_blocked(run) -> bool:
    """A run is blocked if paused, waiting_validation, or stuck (running but no progress)."""
    status = _run_status_value(run)
    if status in ("paused", "waiting_validation", "waiting_hitl"):
        return True
    # Check if any phase is waiting
    for p in getattr(run, "phases", None) or []:
        if _phase_status_value(p) in ("waiting_validation", "paused"):
            return True
    return False


def _is_running(run) -> bool:
    status = _run_status_value(run)
    return status in ("running", "active")


def _is_completed(run) -> bool:
    status = _run_status_value(run)
    return status in ("completed", "done", "done_with_issues")


def _is_failed(run) -> bool:
    status = _run_status_value(run)
    return status in ("failed", "error", "cancelled")


def _time_ago(dt) -> str:
    """Human readable time ago."""
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    mins = int(delta.total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}min ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _get_all_data():
    """Fetch missions and runs from stores."""
    from ...epics.store import get_epic_run_store, get_epic_store

    epic_store = get_epic_store()
    run_store = get_epic_run_store()
    missions = epic_store.list_missions(limit=200)
    runs = run_store.list_runs(limit=200)
    # Index runs by parent_epic_id
    runs_map = {}
    for r in runs:
        if r.parent_epic_id:
            runs_map[r.parent_epic_id] = r
        runs_map[r.id] = r
    return missions, runs, runs_map


@router.get("/api/pulse/kpis")
async def pulse_kpis(request: Request):
    """Three KPI cards: running / blocked / done today."""
    missions, runs, runs_map = _get_all_data()

    running = 0
    blocked = 0
    done_today = 0
    today = datetime.now(timezone.utc).date()

    for m in missions:
        run = runs_map.get(m.id)
        if not run:
            continue
        if _is_blocked(run):
            blocked += 1
        elif _is_running(run):
            running += 1
        elif _is_completed(run):
            completed_at = getattr(run, "completed_at", None) or getattr(run, "updated_at", None)
            if completed_at:
                dt = completed_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt.date() == today:
                    done_today += 1

    return HTMLResponse(f"""
    <div class="pulse-kpi pulse-kpi--running"><div class="pulse-kpi-value">{running}</div><div class="pulse-kpi-label">Running</div></div>
    <div class="pulse-kpi pulse-kpi--blocked"><div class="pulse-kpi-value">{blocked}</div><div class="pulse-kpi-label">Blocked</div></div>
    <div class="pulse-kpi pulse-kpi--done"><div class="pulse-kpi-value">{done_today}</div><div class="pulse-kpi-label">Done today</div></div>
    """)


@router.get("/api/pulse/blocked")
async def pulse_blocked(request: Request):
    """Blocked missions — expanded cards with GO/NOGO actions."""
    missions, runs, runs_map = _get_all_data()

    blocked = []
    for m in missions:
        run = runs_map.get(m.id)
        if run and _is_blocked(run):
            blocked.append((m, run))

    if not blocked:
        return HTMLResponse("")  # No section if nothing blocked

    html = '<div class="pulse-section-head">'
    html += f'<div class="pulse-section-title">Needs Attention <span class="pulse-badge pulse-badge--warn">{len(blocked)}</span></div>'
    html += "</div>"
    html += '<div class="pulse-missions">'

    for m, run in blocked:
        name = html_mod.escape((m.name or m.id)[:50])
        done, total, pct = _run_progress(run)
        phase = html_mod.escape(_current_phase_name(run)[:30])
        updated = getattr(run, "updated_at", None)
        ago = _time_ago(updated)
        run_id = run.id

        # Phase status for context
        status_label = _run_status_value(run)
        for p in getattr(run, "phases", None) or []:
            ps = _phase_status_value(p)
            if ps in ("waiting_validation", "paused"):
                status_label = ps.replace("_", " ")
                break

        html += f"""<div class="pulse-card pulse-card--blocked">
  <div class="pulse-card-main" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
    <div class="pulse-card-info">
      <div class="pulse-card-name">{name}</div>
      <div class="pulse-card-meta">
        <span class="pulse-card-phase">{phase or status_label}</span>
        <span class="pulse-card-time">{ago}</span>
        <span>{done}/{total} phases</span>
      </div>
    </div>
    <div class="pulse-bar"><div class="pulse-bar-fill pulse-bar-fill--yellow" style="width:{pct}%"></div></div>
    <div class="pulse-pct">{pct}%</div>
    <div class="pulse-actions">
      <button class="pulse-btn pulse-btn--go"
              hx-post="/api/epics/{run_id}/hitl-go"
              hx-swap="none"
              hx-confirm="Approve and continue this mission?">GO</button>
      <button class="pulse-btn pulse-btn--nogo"
              hx-post="/api/epics/{run_id}/hitl-nogo"
              hx-swap="none"
              hx-confirm="Reject this phase?">NO GO</button>
    </div>
  </div>
  <div class="pulse-card-detail" style="display:none"
       hx-get="/api/pulse/mission/{m.id}"
       hx-trigger="intersect once"
       hx-swap="innerHTML">
  </div>
</div>"""

    html += "</div>"
    return HTMLResponse(html)


@router.get("/api/pulse/running")
async def pulse_running(request: Request):
    """Running missions — collapsed progress bars."""
    missions, runs, runs_map = _get_all_data()

    running = []
    for m in missions:
        run = runs_map.get(m.id)
        if run and _is_running(run) and not _is_blocked(run):
            running.append((m, run))

    if not running:
        return HTMLResponse("")

    html = '<div class="pulse-section-head">'
    html += f'<div class="pulse-section-title">Running <span class="pulse-badge pulse-badge--info">{len(running)}</span></div>'
    html += "</div>"
    html += '<div class="pulse-missions">'

    for m, run in running:
        name = html_mod.escape((m.name or m.id)[:50])
        done, total, pct = _run_progress(run)
        phase = html_mod.escape(_current_phase_name(run)[:30])

        html += f"""<div class="pulse-card pulse-card--running">
  <div class="pulse-card-main" hx-get="/api/pulse/mission/{m.id}" hx-target="next .pulse-card-expand" hx-swap="innerHTML" style="cursor:pointer">
    <div class="pulse-card-info">
      <div class="pulse-card-name">{name}</div>
      <div class="pulse-card-meta">
        <span class="pulse-card-phase">{phase}</span>
        <span>{done}/{total}</span>
      </div>
    </div>
    <div class="pulse-bar"><div class="pulse-bar-fill pulse-bar-fill--purple" style="width:{pct}%"></div></div>
    <div class="pulse-pct">{pct}%</div>
  </div>
  <div class="pulse-card-expand"></div>
</div>"""

    html += "</div>"
    return HTMLResponse(html)


@router.get("/api/pulse/done")
async def pulse_done(request: Request):
    """Completed today strip."""
    missions, runs, runs_map = _get_all_data()

    today = datetime.now(timezone.utc).date()
    done_today = []
    for m in missions:
        run = runs_map.get(m.id)
        if not run or not _is_completed(run):
            continue
        completed_at = getattr(run, "completed_at", None) or getattr(run, "updated_at", None)
        if completed_at:
            dt = completed_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.date() == today:
                done_today.append(m)

    if not done_today:
        return HTMLResponse("")

    names = ", ".join(html_mod.escape((m.name or m.id)[:25]) for m in done_today[:5])
    extra = f" +{len(done_today) - 5} more" if len(done_today) > 5 else ""

    return HTMLResponse(f"""<div class="pulse-done-strip">
  <div class="pulse-done-label">Completed today: {names}{extra}</div>
  <div class="pulse-done-count">{len(done_today)}</div>
</div>""")


@router.get("/api/pulse/search")
async def pulse_search(request: Request, q: str = ""):
    """Command palette search — missions, agents, projects."""
    if not q or len(q) < 2:
        return HTMLResponse('<div class="cmd-palette-empty">Type to search...</div>')

    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store

    query = q.lower().strip()
    html = ""

    # Search missions
    epic_store = get_epic_store()
    missions = epic_store.list_missions(limit=200)
    matched_missions = [m for m in missions if query in (m.name or "").lower() or query in (m.id or "").lower()][:5]
    if matched_missions:
        html += '<div class="cmd-palette-group"><div class="cmd-palette-group-label">Missions</div>'
        for m in matched_missions:
            name = html_mod.escape((m.name or m.id)[:40])
            status = html_mod.escape(getattr(m, "status", "") or "")
            html += f'<a class="cmd-palette-item cmd-palette-item--mission" href="/epics/{m.id}/control"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10"/></svg> {name} <span style="opacity:0.5;font-size:0.7rem;margin-left:auto">{status}</span></a>'
        html += "</div>"

    # Search agents
    agent_store = get_agent_store()
    agents = agent_store.list_all()
    matched_agents = [a for a in agents if query in (a.name or "").lower() or query in (a.role or "").lower()][:5]
    if matched_agents:
        html += '<div class="cmd-palette-group"><div class="cmd-palette-group-label">Agents</div>'
        for a in matched_agents:
            name = html_mod.escape((a.name or a.id)[:30])
            role = html_mod.escape((a.role or "")[:30])
            html += f'<a class="cmd-palette-item cmd-palette-item--agent" href="/agents/{a.id}/edit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg> {name} <span style="opacity:0.5;font-size:0.7rem;margin-left:auto">{role}</span></a>'
        html += "</div>"

    # Search projects
    project_store = get_project_store()
    projects = project_store.list_all()
    matched_projects = [p for p in projects if query in (getattr(p, "name", "") or "").lower() or query in (getattr(p, "id", "") or "").lower()][:5]
    if matched_projects:
        html += '<div class="cmd-palette-group"><div class="cmd-palette-group-label">Projects</div>'
        for p in matched_projects:
            name = html_mod.escape((getattr(p, "name", "") or getattr(p, "id", ""))[:30])
            html += f'<a class="cmd-palette-item" href="/projects/{getattr(p, "id", "")}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg> {name}</a>'
        html += "</div>"

    if not html:
        html = f'<div class="cmd-palette-empty">No results for "{html_mod.escape(q)}"</div>'

    return HTMLResponse(html)


@router.get("/api/pulse/mission/{epic_id}")
async def pulse_mission_detail(request: Request, epic_id: str):
    """Compact mission detail — phase dots timeline + current phase expanded."""
    from ...epics.store import get_epic_store
    from ...workflows.runs import get_run_store

    epic_store = get_epic_store()
    run_store = get_run_store()

    mission = epic_store.get_mission(epic_id)
    if not mission:
        return HTMLResponse('<div class="pulse-empty">Mission not found</div>', status_code=404)

    name = html_mod.escape((mission.name or mission.id)[:50])
    status = getattr(mission, "status", "") or ""

    # Find latest run
    runs = run_store.list_runs(epic_id=epic_id, limit=5)
    latest = runs[0] if runs else None

    # Build phase timeline
    phases_html = ""
    current_phase_html = ""
    if latest:
        phases = getattr(latest, "phases", None) or []
        for i, ph in enumerate(phases):
            ph_name = html_mod.escape(getattr(ph, "name", f"Phase {i+1}")[:20])
            ph_status = _phase_status_value(ph)

            dot_cls = "dot-pending"
            if ph_status in ("done", "done_with_issues"):
                dot_cls = "dot-done"
            elif ph_status in ("running", "in_progress"):
                dot_cls = "dot-active"
            elif ph_status in ("failed", "blocked"):
                dot_cls = "dot-fail"

            phases_html += f'<div class="phase-dot-wrap" title="{ph_name}: {ph_status}"><div class="phase-dot {dot_cls}"></div><span class="phase-dot-label">{ph_name}</span></div>'

            # Current/active phase gets expanded
            if ph_status in ("running", "in_progress"):
                quality = getattr(ph, "quality_score", None)
                q_str = f'<span class="phase-quality">Quality: {quality}%</span>' if quality is not None else ""
                agent = html_mod.escape(getattr(ph, "agent_id", "")[:25] or "")
                agent_str = f'<span class="phase-agent">Agent: {agent}</span>' if agent else ""
                current_phase_html = f"""<div class="phase-expanded">
  <div class="phase-expanded-name">{ph_name}</div>
  <div class="phase-expanded-meta">{q_str}{agent_str}</div>
</div>"""

        run_status = _run_status_value(latest)
        done_count, total, pct = _run_progress(latest)
        progress_html = f'<div class="pulse-progress-mini"><div class="pulse-progress-fill" style="width:{pct}%"></div></div><span class="pulse-progress-text">{done_count}/{total} phases • {pct}%</span>'
    else:
        progress_html = '<span class="pulse-progress-text">No runs yet</span>'

    status_cls = "badge-green" if status == "active" else "badge-blue" if status == "completed" else "badge-red" if status in ("blocked", "failed") else "badge-yellow"

    return HTMLResponse(f"""<div class="pulse-mission-detail">
  <div class="pulse-mission-header">
    <h3 class="pulse-mission-name">{name}</h3>
    <span class="badge {status_cls}">{html_mod.escape(status)}</span>
    <a href="/epics/{epic_id}/control" class="btn btn-sm btn-ghost" style="margin-left:auto">Full view →</a>
  </div>
  <div class="phase-timeline">{phases_html}</div>
  {current_phase_html}
  <div class="pulse-mission-progress">{progress_html}</div>
</div>""")
