"""Features, stories, and backlog management routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...schemas import OkResponse, StoryOut

router = APIRouter()

@router.post("/api/epics/{epic_id}/features", responses={200: {"model": OkResponse}})
async def create_feature_api(request: Request, epic_id: str):
    """Create a new feature under an epic."""
    from ....missions.product import FeatureDef, get_product_backlog

    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)
    backlog = get_product_backlog()
    feat = backlog.create_feature(
        FeatureDef(
            epic_id=epic_id,
            name=name,
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            story_points=int(data.get("story_points", 0)),
            priority=int(data.get("priority", 5)),
        )
    )
    return JSONResponse({"ok": True, "feature": {"id": feat.id, "name": feat.name}})




@router.patch("/api/features/{feature_id}", responses={200: {"model": OkResponse}})
async def update_feature(request: Request, feature_id: str):
    """Update feature fields (story points, acceptance criteria, priority, status)."""
    from ....missions.product import get_product_backlog

    data = await request.json()
    backlog = get_product_backlog()
    feat = backlog.get_feature(feature_id)
    if not feat:
        return JSONResponse({"error": "Feature not found"}, status_code=404)
    from ....db.migrations import get_db

    db = get_db()
    updates, params = [], []
    for field in (
        "story_points",
        "acceptance_criteria",
        "priority",
        "status",
        "name",
        "description",
    ):
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    params.append(feature_id)
    db.execute(f"UPDATE features SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    db.close()
    return JSONResponse({"ok": True, "feature_id": feature_id})




@router.get("/api/stories", responses={200: {"model": list[StoryOut]}})
async def list_stories_api(feature_id: str = ""):
    """List user stories, optionally filtered by feature."""
    from ....db.migrations import get_db

    db = get_db()
    if feature_id:
        rows = db.execute(
            "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories WHERE feature_id=?",
            (feature_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories ORDER BY feature_id, id"
        ).fetchall()
    return JSONResponse([dict(r) for r in rows])




@router.get(
    "/api/features/{feature_id}/stories", responses={200: {"model": list[StoryOut]}}
)
async def list_feature_stories_api(feature_id: str):
    """List user stories for a specific feature."""
    from ....db.migrations import get_db

    db = get_db()
    rows = db.execute(
        "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories WHERE feature_id=?",
        (feature_id,),
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])




@router.post(
    "/api/features/{feature_id}/stories", responses={200: {"model": OkResponse}}
)
async def create_story_api(request: Request, feature_id: str):
    """Create a new user story under a feature."""
    from ....missions.product import UserStoryDef, get_product_backlog

    data = await request.json()
    title = data.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "Title required"}, status_code=400)
    backlog = get_product_backlog()
    story = backlog.create_story(
        UserStoryDef(
            feature_id=feature_id,
            title=title,
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            story_points=int(data.get("story_points", 0)),
            priority=int(data.get("priority", 5)),
        )
    )
    return JSONResponse({"ok": True, "story": {"id": story.id, "title": story.title}})


# ── Backlog priority reorder ─────────────────────────────────────




@router.patch("/api/stories/{story_id}", responses={200: {"model": OkResponse}})
async def update_story(request: Request, story_id: str):
    """Update user story fields (story points, acceptance criteria, status, sprint)."""
    from ....missions.product import get_product_backlog

    data = await request.json()
    backlog = get_product_backlog()
    from ....db.migrations import get_db

    db = get_db()
    updates, params = [], []
    for field in (
        "story_points",
        "acceptance_criteria",
        "status",
        "sprint_id",
        "title",
        "description",
    ):
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    params.append(story_id)
    db.execute(f"UPDATE user_stories SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    db.close()
    return JSONResponse({"ok": True, "story_id": story_id})


# ── Feature / Story creation ─────────────────────────────────────




@router.patch("/api/backlog/reorder", responses={200: {"model": OkResponse}})
async def reorder_backlog(request: Request):
    """Reorder features or stories by priority. Body: {type:'feature'|'story', ids:[ordered list]}"""
    from ....db.migrations import get_db

    data = await request.json()
    item_type = data.get("type", "feature")
    ids = data.get("ids", [])
    if not ids:
        return JSONResponse({"error": "ids list required"}, status_code=400)
    table = "features" if item_type == "feature" else "user_stories"
    db = get_db()
    try:
        for priority, item_id in enumerate(ids, 1):
            db.execute(
                f"UPDATE {table} SET priority = ? WHERE id = ?", (priority, item_id)
            )
        db.commit()
    finally:
        db.close()
    return JSONResponse({"ok": True, "reordered": len(ids)})


# ── Feature dependencies ─────────────────────────────────────────




@router.post("/api/features/{feature_id}/deps", responses={200: {"model": OkResponse}})
async def add_feature_dep(request: Request, feature_id: str):
    """Add a dependency: feature_id depends on depends_on_id."""
    from ....db.migrations import get_db

    data = await request.json()
    depends_on = data.get("depends_on", "").strip()
    if not depends_on or depends_on == feature_id:
        return JSONResponse({"error": "Valid depends_on required"}, status_code=400)
    db = get_db()
    try:
        db.execute(
            "INSERT OR IGNORE INTO feature_deps (feature_id, depends_on, dep_type) VALUES (?, ?, ?)",
            (feature_id, depends_on, data.get("dep_type", "blocked_by")),
        )
        db.commit()
    finally:
        db.close()
    return JSONResponse({"ok": True})




@router.delete(
    "/api/features/{feature_id}/deps/{depends_on}",
    responses={200: {"model": OkResponse}},
)
async def remove_feature_dep(feature_id: str, depends_on: str):
    """Remove a feature dependency."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        db.execute(
            "DELETE FROM feature_deps WHERE feature_id = ? AND depends_on = ?",
            (feature_id, depends_on),
        )
        db.commit()
    finally:
        db.close()
    return JSONResponse({"ok": True})




@router.get("/api/features/{feature_id}/deps")
async def list_feature_deps(feature_id: str):
    """List dependencies for a feature."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            """SELECT fd.depends_on, fd.dep_type, f.name, f.status
               FROM feature_deps fd LEFT JOIN features f ON fd.depends_on = f.id
               WHERE fd.feature_id = ?""",
            (feature_id,),
        ).fetchall()
        return JSONResponse(
            {
                "deps": [
                    {
                        "depends_on": r["depends_on"],
                        "dep_type": r["dep_type"],
                        "name": r["name"] or r["depends_on"],
                        "status": r["status"] or "unknown",
                    }
                    for r in rows
                ]
            }
        )
    finally:
        db.close()


# ── Sprint planning: assign stories to sprint ────────────────────




@router.post("/api/missions/{mission_id}/wsjf", responses={200: {"model": OkResponse}})
async def compute_wsjf(mission_id: str, request: Request):
    """Compute and store WSJF score from components."""
    from ....db.migrations import get_db as _gdb

    data = await request.json()
    bv = float(data.get("business_value", 0))
    tc = float(data.get("time_criticality", 0))
    rr = float(data.get("risk_reduction", 0))
    jd = max(float(data.get("job_duration", 1)), 0.1)
    cost_of_delay = bv + tc + rr
    wsjf = round(cost_of_delay / jd, 1)
    # Update mission
    db = _gdb()
    try:
        db.execute(
            "UPDATE missions SET wsjf_score=?, business_value=?, time_criticality=?, risk_reduction=?, job_duration=? WHERE id=?",
            (wsjf, bv, tc, rr, jd, mission_id),
        )
        db.commit()
    finally:
        db.close()
    return JSONResponse(
        {"wsjf": wsjf, "cost_of_delay": cost_of_delay, "job_duration": jd}
    )




@router.get("/api/portfolio/kanban", response_class=HTMLResponse)
async def portfolio_kanban(request: Request):
    """SAFe Portfolio Kanban — epics by kanban_status."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, name, project_id, wsjf_score, kanban_status, status, jira_key FROM missions ORDER BY wsjf_score DESC"
        ).fetchall()
    finally:
        db.close()
    columns = {
        "funnel": [],
        "analyzing": [],
        "backlog": [],
        "implementing": [],
        "done": [],
    }
    for r in rows:
        ks = r["kanban_status"] if r["kanban_status"] else "funnel"
        if ks in columns:
            columns[ks].append(dict(r))
    # WIP limit: max 3 in implementing
    wip_limit = 3
    wip_over = len(columns["implementing"]) > wip_limit
    # Jira sync button
    html = '<div style="display:flex;justify-content:flex-end;padding:0 16px 8px">'
    html += '<button class="btn btn-sm btn-secondary" hx-post="/api/jira/kanban-sync" hx-target="#jira-sync-result" hx-swap="innerHTML">'
    html += '<svg class="icon icon-xs"><use href="#icon-refresh-cw"/></svg> Sync Jira</button>'
    html += ' <span id="jira-sync-result" style="font-size:0.75rem;color:var(--text-secondary);margin-left:8px;align-self:center"></span>'
    html += "</div>"
    html += '<div style="display:flex;gap:12px;overflow-x:auto;padding:0 16px 16px;">'
    for col_name, label in [
        ("funnel", "Funnel"),
        ("analyzing", "Analyzing"),
        ("backlog", "Backlog"),
        ("implementing", "Implementing"),
        ("done", "Done"),
    ]:
        items = columns[col_name]
        border_color = (
            "var(--red)" if col_name == "implementing" and wip_over else "var(--border)"
        )
        html += f'<div style="flex:1;min-width:180px;background:var(--bg-secondary);border:1px solid {border_color};border-radius:var(--radius);padding:10px;">'
        wip_tag = (
            f' <span style="color:var(--red);font-size:0.7rem;">WIP {len(items)}/{wip_limit}</span>'
            if col_name == "implementing"
            else ""
        )
        html += f'<h4 style="margin:0 0 8px;font-size:0.85rem;color:var(--text-secondary)">{label} ({len(items)}){wip_tag}</h4>'
        for item in items:
            wsjf = item.get("wsjf_score", 0) or 0
            html += '<div style="background:var(--bg-tertiary);border-radius:6px;padding:8px;margin-bottom:6px;font-size:0.8rem;">'
            html += f'<a href="/missions/{item["id"]}" style="color:var(--purple-light);text-decoration:none">{item["name"][:40]}</a>'
            jira_key = item.get("jira_key", "")
            jira_badge = (
                f' <span style="font-size:0.6rem;background:var(--bg-primary);color:var(--purple-light);padding:1px 4px;border-radius:3px">{jira_key}</span>'
                if jira_key
                else ""
            )
            html += f'<div style="color:var(--text-muted);font-size:0.7rem;">WSJF: {wsjf:.0f} | {item.get("project_id", "")}{jira_badge}</div>'
            html += "</div>"
        html += "</div>"
    html += "</div>"
    return HTMLResponse(html)



