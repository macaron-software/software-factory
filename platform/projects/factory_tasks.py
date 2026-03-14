"""Factory Tasks — read task data from factory.db for each project."""
# Ref: feat-projects

from __future__ import annotations

from dataclasses import dataclass

from ..db.adapter import get_connection


@dataclass
class TaskSummary:
    pending: int = 0
    locked: int = 0
    tdd_in_progress: int = 0
    code_written: int = 0
    build_ok: int = 0
    build_failed: int = 0
    deployed: int = 0
    tdd_failed: int = 0
    total: int = 0


@dataclass
class TaskInfo:
    id: str
    title: str
    domain: str
    status: str
    priority: float = 0.0
    task_type: str = ""


def _get_db():
    try:
        conn = get_connection()
        return conn
    except Exception:
        return None


def get_task_summary(project_id: str) -> TaskSummary:
    conn = _get_db()
    if not conn:
        return TaskSummary()
    try:
        cursor = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE project_id = ? GROUP BY status",
            (project_id,),
        )
        summary = TaskSummary()
        for row in cursor:
            s, cnt = row["status"], row["cnt"]
            summary.total += cnt
            if hasattr(summary, s):
                setattr(summary, s, cnt)
        return summary
    except Exception:
        return TaskSummary()
    finally:
        conn.close()


def get_recent_tasks(project_id: str, limit: int = 20) -> list[TaskInfo]:
    conn = _get_db()
    if not conn:
        return []
    try:
        cursor = conn.execute(
            """SELECT id, title, domain, status, priority, type
               FROM tasks WHERE project_id = ?
               ORDER BY CASE status
                   WHEN 'tdd_in_progress' THEN 0 WHEN 'locked' THEN 1
                   WHEN 'pending' THEN 2 WHEN 'code_written' THEN 3
                   WHEN 'build_failed' THEN 4 WHEN 'tdd_failed' THEN 5
                   WHEN 'build_ok' THEN 6 WHEN 'deployed' THEN 7 ELSE 8
                 END, priority DESC LIMIT ?""",
            (project_id, limit),
        )
        return [
            TaskInfo(
                id=row["id"],
                title=row["title"],
                domain=row["domain"],
                status=row["status"],
                priority=row["priority"] or 0,
                task_type=row["type"] if "type" in row.keys() else "",
            )
            for row in cursor
        ]
    except Exception:
        return []
    finally:
        conn.close()
