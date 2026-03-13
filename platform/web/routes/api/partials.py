"""Partial HTML fragment endpoints for deferred (skeleton) loading.

These return HTML fragments that HTMX swaps into skeleton placeholders
via hx-get + hx-trigger="load". Each includes the sk-loaded class for
a smooth fade-in transition.

Cache headers: short Cache-Control for browser + ETag for conditional requests.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

router = APIRouter()
logger = logging.getLogger(__name__)


def _etag(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _cached_html(content: str, max_age: int = 15) -> Response:
    """Return HTML fragment with cache headers + ETag."""
    tag = _etag(content)
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": f"private, max-age={max_age}",
            "ETag": f'"{tag}"',
        },
    )


def _templates(request: Request):
    from ...routes.helpers import _templates as _t
    return _t(request)


# ── Portfolio metrics ──────────────────────────────────────────────
@router.get("/partial/portfolio/metrics")
async def partial_portfolio_metrics(request: Request) -> Response:
    from ....agents.store import get_agent_store
    from ....epics.store import get_epic_run_store, get_epic_store
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    agents = get_agent_store().list_all()
    missions = get_epic_store().list_missions(limit=500)
    runs = get_epic_run_store().list_runs(limit=500)

    active_runs = [r for r in runs if r.status and r.status.value in ("running", "pending")]
    completed = [r for r in runs if r.status and r.status.value == "completed"]

    html = f"""<div class="portfolio-metrics sk-loaded">
      <div class="metric-card"><div class="metric-value">{len(projects)}</div><div class="metric-label">Projects</div></div>
      <div class="metric-card"><div class="metric-value">{len(agents)}</div><div class="metric-label">Agents</div></div>
      <div class="metric-card"><div class="metric-value">{len(missions)}</div><div class="metric-label">Missions</div></div>
      <div class="metric-card"><div class="metric-value">{len(active_runs)}</div><div class="metric-label">Active Runs</div></div>
      <div class="metric-card"><div class="metric-value">{len(completed)}</div><div class="metric-label">Completed</div></div>
    </div>"""
    return _cached_html(html, max_age=15)


# ── Agent list cards ───────────────────────────────────────────────
@router.get("/partial/agents/cards")
async def partial_agents_cards(request: Request) -> Response:
    tpl = _templates(request)
    from ....agents.store import get_agent_store
    agents = get_agent_store().list_all()
    return tpl.TemplateResponse(
        "partials/agent_cards.html",
        {"request": request, "agents": agents},
    )


# ── Cockpit pipeline ──────────────────────────────────────────────
@router.get("/partial/cockpit/pipeline")
async def partial_cockpit_pipeline(request: Request) -> Response:
    from ....epics.store import get_epic_run_store, get_epic_store
    from ....sessions.store import get_session_store

    missions = get_epic_store().list_missions(limit=500)
    runs = get_epic_run_store().list_runs(limit=500)

    # Pipeline stage counts
    status_map: dict[str, int] = {}
    for r in runs:
        s = r.status.value if r.status else "unknown"
        status_map[s] = status_map.get(s, 0) + 1

    stages = [
        ("Backlog", len(missions), "#7c3aed"),
        ("Pending", status_map.get("pending", 0), "#eab308"),
        ("Running", status_map.get("running", 0), "#22c55e"),
        ("Completed", status_map.get("completed", 0), "#06b6d4"),
        ("Failed", status_map.get("failed", 0), "#ef4444"),
    ]

    cells = []
    for label, count, color in stages:
        cells.append(
            f'<div class="pipeline-stage">'
            f'<div class="ps-value" style="color:{color}">{count}</div>'
            f'<div class="ps-label">{label}</div></div>'
        )

    html = f'<div class="pipeline-bar sk-loaded">{"".join(cells)}</div>'
    return _cached_html(html, max_age=10)


# ── Cockpit projects ──────────────────────────────────────────────
@router.get("/partial/cockpit/projects")
async def partial_cockpit_projects(request: Request) -> Response:
    from ....epics.store import get_epic_run_store
    from ....projects.manager import get_project_store

    projects = get_project_store().list_all()
    runs = get_epic_run_store().list_runs(limit=200)

    runs_by_project: dict[str, list] = {}
    for r in runs:
        pid = r.project_id or "unknown"
        runs_by_project.setdefault(pid, []).append(r)

    items = []
    for p in projects[:8]:
        proj_runs = runs_by_project.get(p.id, [])
        total = len(proj_runs)
        done = sum(1 for r in proj_runs if r.status and r.status.value == "completed")
        pct = int(done / total * 100) if total else 0
        items.append(
            f'<div class="proj-item">'
            f'<div class="proj-header"><span class="proj-name">{p.name}</span>'
            f'<span class="proj-meta">{done}/{total} runs</span></div>'
            f'<div class="prog-bar"><div class="prog-fill" style="width:{pct}%"></div></div>'
            f'</div>'
        )

    html = f'<div class="proj-list sk-loaded">{"".join(items)}</div>'
    return _cached_html(html, max_age=15)
