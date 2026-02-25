"""HTML partial / HTMX fragment routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..helpers import _active_mission_tasks, _templates

router = APIRouter()

@router.get("/api/missions/{mission_id}/board", response_class=HTMLResponse)
async def mission_board_partial(request: Request, mission_id: str):
    """HTMX partial — kanban board for a sprint."""
    from ....missions.store import get_mission_store

    store = get_mission_store()
    sprint_id = request.query_params.get("sprint")
    if not sprint_id:
        return HTMLResponse("")
    tasks = store.list_tasks(sprint_id=sprint_id)
    tasks_by_status = {}
    for t in tasks:
        col = (
            t.status
            if t.status in ("pending", "in_progress", "review", "done")
            else "pending"
        )
        tasks_by_status.setdefault(col, []).append(t)

    cols = [
        ("pending", "Backlog", "clipboard"),
        ("in_progress", "In Progress", "zap"),
        ("review", "Review", "eye"),
        ("done", "Done", "check"),
    ]
    html_parts = []
    for col_status, col_name, col_icon in cols:
        col_tasks = tasks_by_status.get(col_status, [])
        cards = ""
        for t in col_tasks:
            agent = (
                f'<span class="kanban-task-agent"><svg class="icon icon-xs"><use href="#icon-user"/></svg> {t.assigned_to}</span>'
                if t.assigned_to
                else ""
            )
            domain = f"<span>{t.domain}</span>" if t.domain else ""
            cards += f"""<div class="kanban-task">
                <div class="kanban-task-title">{t.title}</div>
                <div class="kanban-task-meta">
                    <span class="kanban-task-type {t.type}">{t.type}</span>
                    {domain}{agent}
                </div></div>"""
        if not cards:
            cards = '<div class="kanban-empty">—</div>'
        html_parts.append(f"""<div class="kanban-col">
            <div class="kanban-col-title"><svg class="icon icon-xs"><use href="#icon-{col_icon}"/></svg> {col_name}
                <span class="kanban-col-count">{len(col_tasks)}</span>
            </div>{cards}</div>""")
    return HTMLResponse("".join(html_parts))


# ══════════════════════════════════════════════════════════════════════════════
#  MISSION CONTROL — CDP orchestrator dashboard
# ══════════════════════════════════════════════════════════════════════════════




@router.get("/api/missions/list-partial", response_class=HTMLResponse)
async def missions_list_partial(request: Request):
    """HTMX partial: refreshes mission list every 15s."""
    from ....missions.store import get_mission_run_store

    runs = get_mission_run_store().list_runs(limit=50)
    # Detect stuck missions: status=running but no active asyncio task
    active_ids = {mid for mid, t in _active_mission_tasks.items() if not t.done()}
    return _templates(request).TemplateResponse(
        "partials/mission_list.html",
        {
            "request": request,
            "runs": runs,
            "active_ids": active_ids,
        },
    )



