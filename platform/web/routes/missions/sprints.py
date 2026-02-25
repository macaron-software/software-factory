"""Sprint and task management routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...schemas import OkResponse, StoryOut

router = APIRouter()

@router.post(
    "/api/missions/{mission_id}/sprints", responses={200: {"model": OkResponse}}
)
async def create_sprint(mission_id: str):
    """Add a sprint to a mission."""
    from ....missions.store import SprintDef, get_mission_store

    store = get_mission_store()
    existing = store.list_sprints(mission_id)
    num = len(existing) + 1
    s = SprintDef(mission_id=mission_id, number=num, name=f"Sprint {num}")
    store.create_sprint(s)
    return JSONResponse({"ok": True})




@router.post("/api/missions/{mission_id}/tasks")
async def create_task(request: Request, mission_id: str):
    """Create a task in a mission sprint (inline kanban creation)."""
    from ....missions.store import TaskDef, get_mission_store

    data = await request.json()
    title = data.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "Title required"}, status_code=400)
    store = get_mission_store()
    sprint_id = data.get("sprint_id", "")
    if not sprint_id:
        sprints = store.list_sprints(mission_id)
        if sprints:
            sprint_id = sprints[-1].id
        else:
            return JSONResponse({"error": "No sprint"}, status_code=400)
    task = TaskDef(
        sprint_id=sprint_id,
        mission_id=mission_id,
        title=title,
        type=data.get("type", "feature"),
        domain=data.get("domain", ""),
        status="pending",
    )
    task = store.create_task(task)
    return JSONResponse({"ok": True, "task_id": task.id})




@router.patch("/api/tasks/{task_id}/status")
async def update_task_status(request: Request, task_id: str):
    """Update task status (drag-drop kanban)."""
    from ....missions.store import get_mission_store

    data = await request.json()
    new_status = data.get("status", "").strip()
    valid = {"pending", "assigned", "in_progress", "review", "done", "failed"}
    if new_status not in valid:
        return JSONResponse(
            {"error": f"Invalid status. Must be one of: {valid}"}, status_code=400
        )
    store = get_mission_store()
    ok = store.update_task_status(task_id, new_status)
    if not ok:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse({"ok": True, "task_id": task_id, "status": new_status})




@router.post(
    "/api/sprints/{sprint_id}/assign-stories", responses={200: {"model": OkResponse}}
)
async def assign_stories_to_sprint(request: Request, sprint_id: str):
    """Assign multiple stories to a sprint. Body: {story_ids: [...]}"""
    from ....db.migrations import get_db

    data = await request.json()
    story_ids = data.get("story_ids", [])
    if not story_ids:
        return JSONResponse({"error": "story_ids required"}, status_code=400)
    db = get_db()
    try:
        for sid in story_ids:
            db.execute(
                "UPDATE user_stories SET sprint_id = ? WHERE id = ?", (sprint_id, sid)
            )
        db.commit()
    finally:
        db.close()
    return JSONResponse({"ok": True, "assigned": len(story_ids)})




@router.delete(
    "/api/sprints/{sprint_id}/stories/{story_id}",
    responses={200: {"model": OkResponse}},
)
async def unassign_story_from_sprint(sprint_id: str, story_id: str):
    """Remove a story from a sprint."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        db.execute(
            "UPDATE user_stories SET sprint_id = '' WHERE id = ? AND sprint_id = ?",
            (story_id, sprint_id),
        )
        db.commit()
    finally:
        db.close()
    return JSONResponse({"ok": True})




@router.get(
    "/api/sprints/{sprint_id}/available-stories",
    responses={200: {"model": list[StoryOut]}},
)
async def available_stories_for_sprint(sprint_id: str):
    """List unassigned stories (backlog) available for sprint planning."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        # Get the mission for this sprint
        sprint = db.execute(
            "SELECT mission_id FROM sprints WHERE id = ?", (sprint_id,)
        ).fetchone()
        if not sprint:
            return JSONResponse({"error": "Sprint not found"}, status_code=404)
        mission_id = sprint["mission_id"]
        rows = db.execute(
            """SELECT us.id, us.title, us.story_points, us.status, us.priority, f.name as feature_name
               FROM user_stories us
               JOIN features f ON us.feature_id = f.id
               WHERE f.epic_id = ? AND (us.sprint_id = '' OR us.sprint_id IS NULL)
               ORDER BY us.priority""",
            (mission_id,),
        ).fetchall()
        return JSONResponse({"stories": [dict(r) for r in rows]})
    finally:
        db.close()



