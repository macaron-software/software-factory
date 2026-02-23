"""TMA (Tickets Maintenance) API routes — CRUD operations."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tma", tags=["tma"])


class TMATicketUpdate(BaseModel):
    """TMA Ticket update payload."""

    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    goal: str | None = Field(None, max_length=500)
    status: str | None = Field(None, pattern="^(open|in_progress|resolved|closed)$")
    type: str | None = Field(None, pattern="^(bug|debt|security|performance)$")


@router.get("/tickets/{ticket_id}")
async def get_ticket(request: Request, ticket_id: str):
    """Get TMA ticket details."""
    from ...db.core import get_db

    db = get_db()
    ticket = db.execute(
        """
        SELECT m.id, m.project_id, m.name, m.description, m.goal, m.status, m.type, 
               m.created_at, m.updated_at, p.name as project_name
        FROM missions m 
        LEFT JOIN projects p ON m.project_id = p.id
        WHERE m.id = ? AND m.type IN ('bug', 'debt', 'security', 'performance')
    """,
        (ticket_id,),
    ).fetchone()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "id": ticket["id"],
        "project_id": ticket["project_id"],
        "project_name": ticket["project_name"] or ticket["project_id"],
        "name": ticket["name"],
        "description": ticket["description"],
        "goal": ticket["goal"],
        "status": ticket["status"],
        "type": ticket["type"],
        "created_at": ticket["created_at"],
        "updated_at": ticket["updated_at"],
    }


@router.put("/tickets/{ticket_id}")
async def update_ticket(request: Request, ticket_id: str, payload: TMATicketUpdate):
    """Update TMA ticket."""
    from ...db.core import get_db

    db = get_db()

    # Verify ticket exists and is TMA type
    existing = db.execute(
        """
        SELECT id, type FROM missions 
        WHERE id = ? AND type IN ('bug', 'debt', 'security', 'performance')
    """,
        (ticket_id,),
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Build update query dynamically
    updates = []
    params = []

    if payload.name is not None:
        updates.append("name = ?")
        params.append(payload.name)

    if payload.description is not None:
        updates.append("description = ?")
        params.append(payload.description)

    if payload.goal is not None:
        updates.append("goal = ?")
        params.append(payload.goal)

    if payload.status is not None:
        updates.append("status = ?")
        params.append(payload.status)

    if payload.type is not None:
        updates.append("type = ?")
        params.append(payload.type)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Add updated_at
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(ticket_id)

    query = f"UPDATE missions SET {', '.join(updates)} WHERE id = ?"

    try:
        db.execute(query, tuple(params))
        db.commit()
        logger.info(f"Updated TMA ticket {ticket_id}")

        # Notify on status change
        if payload.status:
            try:
                from ...services.notifications import emit_notification
                emit_notification(
                    f"TMA ticket {payload.status}: {ticket_id[:8]}",
                    type="tma", message=payload.name or "",
                    url=f"/tma/tickets/{ticket_id}",
                    severity="warning" if payload.status in ("open", "in_progress") else "info",
                    source="tma", ref_id=ticket_id,
                )
            except Exception:
                pass

        # Return updated ticket
        return await get_ticket(request, ticket_id)
    except Exception as e:
        logger.error(f"Failed to update ticket {ticket_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(request: Request, ticket_id: str):
    """Delete TMA ticket (soft delete by setting status to archived)."""
    from ...db.core import get_db

    db = get_db()

    # Verify ticket exists
    existing = db.execute(
        """
        SELECT id FROM missions 
        WHERE id = ? AND type IN ('bug', 'debt', 'security', 'performance')
    """,
        (ticket_id,),
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        # Soft delete: mark as archived
        db.execute(
            """
            UPDATE missions 
            SET status = 'archived', updated_at = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), ticket_id),
        )
        db.commit()
        logger.info(f"Deleted (archived) TMA ticket {ticket_id}")

        return {"status": "success", "message": "Ticket deleted", "id": ticket_id}
    except Exception as e:
        logger.error(f"Failed to delete ticket {ticket_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/tickets")
async def list_tickets(
    request: Request,
    status: str | None = None,
    type: str | None = None,
    project_id: str | None = None,
):
    """List TMA tickets with optional filters."""
    from ...db.core import get_db

    db = get_db()

    # Build query with filters
    where_clauses = ["m.type IN ('bug', 'debt', 'security', 'performance')"]
    params = []

    if status:
        where_clauses.append("m.status = ?")
        params.append(status)

    if type:
        where_clauses.append("m.type = ?")
        params.append(type)

    if project_id:
        where_clauses.append("m.project_id = ?")
        params.append(project_id)

    where_sql = " AND ".join(where_clauses)

    tickets = db.execute(
        f"""
        SELECT m.id, m.project_id, m.name, m.description, m.goal, m.status, m.type,
               m.created_at, m.updated_at, p.name as project_name
        FROM missions m
        LEFT JOIN projects p ON m.project_id = p.id
        WHERE {where_sql}
        ORDER BY
            CASE m.type 
                WHEN 'security' THEN 0 
                WHEN 'bug' THEN 1 
                WHEN 'debt' THEN 2 
                WHEN 'performance' THEN 3 
                ELSE 4 
            END,
            m.created_at DESC
    """,
        tuple(params),
    ).fetchall()

    return {
        "tickets": [
            {
                "id": t["id"],
                "project_id": t["project_id"],
                "project_name": t["project_name"] or t["project_id"],
                "name": t["name"],
                "description": t["description"],
                "goal": t["goal"],
                "status": t["status"],
                "type": t["type"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
            }
            for t in tickets
        ],
        "count": len(tickets),
    }


class JSErrorReport(BaseModel):
    """Browser JS error report."""
    message: str = ""
    source: str = ""
    line: int = 0
    col: int = 0
    url: str = ""
    ua: str = ""


@router.post("/js-error")
async def report_js_error(request: Request, report: JSErrorReport):
    """Receive JS errors from browser and create TMA support tickets."""
    import uuid
    from ...db.migrations import get_db

    # Skip noise
    if not report.message or "Script error" in report.message:
        return {"status": "ignored"}

    tid = str(uuid.uuid4())[:8]
    title = f"[JS] {report.message[:120]}"
    desc = (
        f"Source: {report.source}:{report.line}:{report.col}\n"
        f"Page: {report.url}\n"
        f"UA: {report.ua}"
    )
    try:
        db = get_db()
        # Deduplicate: skip if same title exists and is still open
        existing = db.execute(
            "SELECT id FROM support_tickets WHERE title=? AND status='open' LIMIT 1",
            (title,),
        ).fetchone()
        if existing:
            db.close()
            return {"status": "duplicate", "ticket_id": existing[0]}
        db.execute(
            "INSERT INTO support_tickets (id, mission_id, title, description, severity, category, reporter, status) "
            "VALUES (?, '', ?, ?, 'medium', 'js-error', 'browser', 'open')",
            (tid, title, desc),
        )
        # Bridge to platform_incidents so auto-heal picks it up
        db.execute(
            "INSERT OR IGNORE INTO platform_incidents (id, title, severity, status, source, error_type, error_detail, created_at) "
            "VALUES (?, ?, 'P3', 'open', 'js-error', 'js-error', ?, datetime('now'))",
            (f"js-{tid}", title, desc),
        )
        db.commit()
        db.close()
        # In-app notification
        try:
            from ...services.notifications import emit_notification
            emit_notification(
                title, type="tma", message=report.source or report.url,
                severity="warning", source="js-error", ref_id=tid,
            )
        except Exception:
            pass
        logger.info("JS error ticket created: %s — %s", tid, title)
        return {"status": "created", "ticket_id": tid}
    except Exception as e:
        logger.warning("Failed to create JS error ticket: %s", e)
        return {"status": "error", "detail": str(e)}
