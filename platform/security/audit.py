"""Append-only audit log for admin/system actions."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def audit_log(
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    detail: str = "",
    actor: str = "system",
    ip: str = "",
    user_agent: str = "",
) -> None:
    """Append a record to admin_audit_log. Never raises."""
    try:
        from ..db.migrations import get_db

        conn = get_db()
        conn.execute(
            "INSERT INTO admin_audit_log (actor, action, resource_type, resource_id, detail, ip, user_agent) VALUES (?,?,?,?,?,?,?)",
            (
                actor,
                action,
                resource_type,
                resource_id,
                detail[:500],
                ip[:100],
                user_agent[:200],
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("audit_log failed: %s", e)
