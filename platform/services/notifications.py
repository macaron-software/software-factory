"""In-app notification store — persistent notifications with bell icon support."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    id: str
    type: str  # mission, tma, autoheal, agent, system
    title: str
    message: str
    url: str
    severity: str  # info, warning, critical
    source: str
    ref_id: str
    is_read: bool
    created_at: str


def _row_to_notif(row) -> Notification:
    return Notification(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        message=row["message"] or "",
        url=row["url"] or "",
        severity=row["severity"] or "info",
        source=row["source"] or "",
        ref_id=row["ref_id"] or "",
        is_read=bool(row["is_read"]),
        created_at=row["created_at"] or "",
    )


class NotificationStore:
    """CRUD for in-app notifications."""

    def create(
        self,
        title: str,
        *,
        type: str = "info",
        message: str = "",
        url: str = "",
        severity: str = "info",
        source: str = "",
        ref_id: str = "",
    ) -> str:
        nid = uuid.uuid4().hex[:12]
        db = get_db()
        try:
            db.execute(
                "INSERT INTO notifications (id, type, title, message, url, severity, source, ref_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (nid, type, title, message, url, severity, source, ref_id),
            )
            db.commit()
            logger.info("Notification created: [%s] %s", type, title)
        finally:
            db.close()
        return nid

    def list_recent(self, limit: int = 30, unread_only: bool = False) -> list[Notification]:
        db = get_db()
        try:
            where = "WHERE is_read = 0" if unread_only else ""
            rows = db.execute(
                f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_row_to_notif(r) for r in rows]
        finally:
            db.close()

    def count_unread(self) -> int:
        db = get_db()
        try:
            row = db.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()
            return row[0] if row else 0
        finally:
            db.close()

    def mark_read(self, nid: str) -> bool:
        db = get_db()
        try:
            db.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (nid,))
            db.commit()
            return True
        finally:
            db.close()

    def mark_all_read(self) -> int:
        db = get_db()
        try:
            cur = db.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
            db.commit()
            return cur.rowcount
        finally:
            db.close()

    def delete_old(self, keep_days: int = 30) -> int:
        db = get_db()
        try:
            cur = db.execute(
                "DELETE FROM notifications WHERE created_at < datetime('now', ?)",
                (f"-{keep_days} days",),
            )
            db.commit()
            return cur.rowcount
        finally:
            db.close()


_store: Optional[NotificationStore] = None


def get_notification_store() -> NotificationStore:
    global _store
    if _store is None:
        _store = NotificationStore()
    return _store


def emit_notification(
    title: str,
    *,
    type: str = "info",
    message: str = "",
    url: str = "",
    severity: str = "info",
    source: str = "",
    ref_id: str = "",
) -> str:
    """Convenience function to create a notification from anywhere in the codebase."""
    return get_notification_store().create(
        title, type=type, message=message, url=url,
        severity=severity, source=source, ref_id=ref_id,
    )
