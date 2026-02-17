"""Mission, Sprint & Task store — drives the production pipeline.

A Mission is a high-level objective (from VISION.md) executed as PI → Sprints → Tasks.
Replaces the old chat-centric 'sessions' for production workloads.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..db.migrations import get_db


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class MissionDef:
    """A production mission — a measurable objective for a project."""
    id: str = ""
    project_id: str = ""
    name: str = ""
    description: str = ""
    goal: str = ""                        # acceptance criteria
    status: str = "planning"              # planning|active|completed|failed|blocked
    workflow_id: Optional[str] = None     # safe-veligo, safe-ppz...
    parent_mission_id: Optional[str] = None  # corrective mission → parent
    wsjf_score: float = 0.0
    created_by: str = ""                  # agent who created it (strat-cpo, etc.)
    config: dict = field(default_factory=dict)
    created_at: str = ""
    completed_at: Optional[str] = None


@dataclass
class SprintDef:
    """A sprint within a mission — time-boxed iteration."""
    id: str = ""
    mission_id: str = ""
    number: int = 1
    name: str = ""
    goal: str = ""
    status: str = "planning"              # planning|active|review|completed|failed
    retro_notes: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class TaskDef:
    """An atomic task within a sprint — assigned to one agent."""
    id: str = ""
    sprint_id: str = ""
    mission_id: str = ""
    title: str = ""
    description: str = ""
    type: str = "feature"                 # feature|fix|refactor|test|security
    domain: str = ""                      # rust, svelte, angular, python...
    status: str = "pending"               # pending|assigned|in_progress|review|done|failed
    assigned_to: Optional[str] = None     # agent_id
    priority: int = 0
    files_changed: list = field(default_factory=list)
    created_at: str = ""
    completed_at: Optional[str] = None


# ── Row converters ───────────────────────────────────────────────────

def _row_to_mission(row) -> MissionDef:
    return MissionDef(
        id=row["id"], project_id=row["project_id"],
        name=row["name"], description=row["description"] or "",
        goal=row["goal"] or "", status=row["status"] or "planning",
        workflow_id=row["workflow_id"], parent_mission_id=row["parent_mission_id"],
        wsjf_score=row["wsjf_score"] or 0.0, created_by=row["created_by"] or "",
        config=json.loads(row["config_json"] or "{}"),
        created_at=row["created_at"] or "", completed_at=row["completed_at"],
    )


def _row_to_sprint(row) -> SprintDef:
    return SprintDef(
        id=row["id"], mission_id=row["mission_id"],
        number=row["number"] or 1, name=row["name"] or "",
        goal=row["goal"] or "", status=row["status"] or "planning",
        retro_notes=row["retro_notes"] or "",
        started_at=row["started_at"], completed_at=row["completed_at"],
    )


def _row_to_task(row) -> TaskDef:
    return TaskDef(
        id=row["id"], sprint_id=row["sprint_id"],
        mission_id=row["mission_id"], title=row["title"],
        description=row["description"] or "", type=row["type"] or "feature",
        domain=row["domain"] or "", status=row["status"] or "pending",
        assigned_to=row["assigned_to"], priority=row["priority"] or 0,
        files_changed=json.loads(row["files_changed"] or "[]"),
        created_at=row["created_at"] or "", completed_at=row["completed_at"],
    )


# ── MissionStore ─────────────────────────────────────────────────────

class MissionStore:
    """CRUD for missions, sprints and tasks."""

    # ── Missions ─────────────────────────────────────────────────

    def list_missions(self, project_id: str = None, limit: int = 50) -> list[MissionDef]:
        db = get_db()
        try:
            if project_id:
                rows = db.execute(
                    "SELECT * FROM missions WHERE project_id = ? ORDER BY wsjf_score DESC, created_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM missions ORDER BY wsjf_score DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [_row_to_mission(r) for r in rows]
        finally:
            db.close()

    def get_mission(self, mission_id: str) -> Optional[MissionDef]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
            return _row_to_mission(row) if row else None
        finally:
            db.close()

    def create_mission(self, m: MissionDef) -> MissionDef:
        if not m.id:
            m.id = str(uuid.uuid4())[:8]
        m.created_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT INTO missions (id, project_id, name, description, goal, status,
                   workflow_id, parent_mission_id, wsjf_score, created_by, config_json,
                   created_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (m.id, m.project_id, m.name, m.description, m.goal, m.status,
                 m.workflow_id, m.parent_mission_id, m.wsjf_score, m.created_by,
                 json.dumps(m.config), m.created_at, m.completed_at),
            )
            db.commit()
        finally:
            db.close()
        return m

    def update_mission_status(self, mission_id: str, status: str) -> bool:
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status in ("completed", "failed") else None
            cur = db.execute(
                "UPDATE missions SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed, mission_id),
            )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def delete_mission(self, mission_id: str) -> bool:
        db = get_db()
        try:
            db.execute("DELETE FROM tasks WHERE mission_id = ?", (mission_id,))
            db.execute("DELETE FROM sprints WHERE mission_id = ?", (mission_id,))
            cur = db.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    # ── Sprints ──────────────────────────────────────────────────

    def list_sprints(self, mission_id: str) -> list[SprintDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM sprints WHERE mission_id = ? ORDER BY number ASC",
                (mission_id,),
            ).fetchall()
            return [_row_to_sprint(r) for r in rows]
        finally:
            db.close()

    def get_sprint(self, sprint_id: str) -> Optional[SprintDef]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM sprints WHERE id = ?", (sprint_id,)).fetchone()
            return _row_to_sprint(row) if row else None
        finally:
            db.close()

    def create_sprint(self, s: SprintDef) -> SprintDef:
        if not s.id:
            s.id = str(uuid.uuid4())[:8]
        db = get_db()
        try:
            db.execute(
                """INSERT INTO sprints (id, mission_id, number, name, goal, status,
                   retro_notes, started_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (s.id, s.mission_id, s.number, s.name, s.goal, s.status,
                 s.retro_notes, s.started_at, s.completed_at),
            )
            db.commit()
        finally:
            db.close()
        return s

    def update_sprint_status(self, sprint_id: str, status: str) -> bool:
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status in ("completed", "failed") else None
            started = datetime.utcnow().isoformat() if status == "active" else None
            if started:
                cur = db.execute(
                    "UPDATE sprints SET status = ?, started_at = COALESCE(started_at, ?) WHERE id = ?",
                    (status, started, sprint_id),
                )
            else:
                cur = db.execute(
                    "UPDATE sprints SET status = ?, completed_at = ? WHERE id = ?",
                    (status, completed, sprint_id),
                )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    # ── Tasks ────────────────────────────────────────────────────

    def list_tasks(self, sprint_id: str = None, mission_id: str = None,
                   status: str = None) -> list[TaskDef]:
        db = get_db()
        try:
            clauses, params = [], []
            if sprint_id:
                clauses.append("sprint_id = ?"); params.append(sprint_id)
            if mission_id:
                clauses.append("mission_id = ?"); params.append(mission_id)
            if status:
                clauses.append("status = ?"); params.append(status)
            where = " AND ".join(clauses) if clauses else "1=1"
            rows = db.execute(
                f"SELECT * FROM tasks WHERE {where} ORDER BY priority DESC, created_at ASC",
                params,
            ).fetchall()
            return [_row_to_task(r) for r in rows]
        finally:
            db.close()

    def get_task(self, task_id: str) -> Optional[TaskDef]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return _row_to_task(row) if row else None
        finally:
            db.close()

    def create_task(self, t: TaskDef) -> TaskDef:
        if not t.id:
            t.id = str(uuid.uuid4())[:8]
        t.created_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT INTO tasks (id, sprint_id, mission_id, title, description,
                   type, domain, status, assigned_to, priority, files_changed,
                   created_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (t.id, t.sprint_id, t.mission_id, t.title, t.description,
                 t.type, t.domain, t.status, t.assigned_to, t.priority,
                 json.dumps(t.files_changed), t.created_at, t.completed_at),
            )
            db.commit()
        finally:
            db.close()
        return t

    def update_task_status(self, task_id: str, status: str,
                           assigned_to: str = None) -> bool:
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status in ("done", "failed") else None
            if assigned_to is not None:
                cur = db.execute(
                    "UPDATE tasks SET status = ?, assigned_to = ?, completed_at = ? WHERE id = ?",
                    (status, assigned_to, completed, task_id),
                )
            else:
                cur = db.execute(
                    "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                    (status, completed, task_id),
                )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    # ── Stats ────────────────────────────────────────────────────

    def mission_stats(self, mission_id: str) -> dict:
        """Get task counts by status for a mission."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks WHERE mission_id = ? GROUP BY status",
                (mission_id,),
            ).fetchall()
            stats = {r["status"]: r["cnt"] for r in rows}
            stats["total"] = sum(stats.values())
            return stats
        finally:
            db.close()

    def sprint_stats(self, sprint_id: str) -> dict:
        """Get task counts by status for a sprint."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks WHERE sprint_id = ? GROUP BY status",
                (sprint_id,),
            ).fetchall()
            stats = {r["status"]: r["cnt"] for r in rows}
            stats["total"] = sum(stats.values())
            return stats
        finally:
            db.close()

    def portfolio_stats(self) -> list[dict]:
        """Get mission counts and task progress per project."""
        db = get_db()
        try:
            rows = db.execute("""
                SELECT m.project_id,
                       COUNT(DISTINCT m.id) as mission_count,
                       SUM(CASE WHEN m.status = 'active' THEN 1 ELSE 0 END) as active_missions,
                       SUM(CASE WHEN m.status = 'completed' THEN 1 ELSE 0 END) as completed_missions
                FROM missions m GROUP BY m.project_id ORDER BY m.project_id
            """).fetchall()
            results = []
            for r in rows:
                pid = r["project_id"]
                task_rows = db.execute("""
                    SELECT status, COUNT(*) as cnt FROM tasks
                    WHERE mission_id IN (SELECT id FROM missions WHERE project_id = ?)
                    GROUP BY status
                """, (pid,)).fetchall()
                task_stats = {tr["status"]: tr["cnt"] for tr in task_rows}
                task_stats["total"] = sum(task_stats.values())
                results.append({
                    "project_id": pid,
                    "mission_count": r["mission_count"],
                    "active_missions": r["active_missions"],
                    "completed_missions": r["completed_missions"],
                    "tasks": task_stats,
                })
            return results
        finally:
            db.close()


_store: Optional[MissionStore] = None


def get_mission_store() -> MissionStore:
    global _store
    if _store is None:
        _store = MissionStore()
    return _store
