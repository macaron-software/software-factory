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
    type: str = "feature"                 # feature|epic|bug|debt|migration|security|hacking|program
    workflow_id: Optional[str] = None     # safe-veligo, safe-ppz...
    parent_mission_id: Optional[str] = None  # corrective mission → parent
    wsjf_score: float = 0.0
    kanban_status: str = "funnel"         # SAFe: funnel|analyzing|backlog|implementing|done
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
    velocity: int = 0                     # SAFe: story points completed
    planned_sp: int = 0                   # SAFe: story points planned
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
        type=row["type"] if "type" in row.keys() else "feature",
        workflow_id=row["workflow_id"], parent_mission_id=row["parent_mission_id"],
        wsjf_score=row["wsjf_score"] or 0.0, created_by=row["created_by"] or "",
        config=json.loads(row["config_json"] or "{}"),
        created_at=row["created_at"] or "", completed_at=row["completed_at"],
    )


def _row_to_sprint(row) -> SprintDef:
    cols = row.keys() if hasattr(row, 'keys') else []
    return SprintDef(
        id=row["id"], mission_id=row["mission_id"],
        number=row["number"] or 1, name=row["name"] or "",
        goal=row["goal"] or "", status=row["status"] or "planning",
        retro_notes=row["retro_notes"] or "",
        velocity=row["velocity"] if "velocity" in cols else 0,
        planned_sp=row["planned_sp"] if "planned_sp" in cols else 0,
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
                """INSERT INTO missions (id, project_id, name, description, goal, status, type,
                   workflow_id, parent_mission_id, wsjf_score, created_by, config_json,
                   created_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (m.id, m.project_id, m.name, m.description, m.goal, m.status, m.type,
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
            # SAFe: auto-update kanban_status based on mission status
            kanban_map = {"planning": "analyzing", "active": "implementing", "completed": "done", "failed": "backlog"}
            kanban = kanban_map.get(status)
            if kanban:
                cur = db.execute(
                    "UPDATE missions SET status = ?, completed_at = ?, kanban_status = ? WHERE id = ?",
                    (status, completed, kanban, mission_id),
                )
            else:
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
                   retro_notes, velocity, planned_sp, started_at, completed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (s.id, s.mission_id, s.number, s.name, s.goal, s.status,
                 s.retro_notes, s.velocity, s.planned_sp, s.started_at, s.completed_at),
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

    def update_sprint_retro(self, sprint_id: str, retro_notes: str) -> bool:
        """Store retrospective notes for a sprint (SAFe I&A)."""
        db = get_db()
        try:
            cur = db.execute("UPDATE sprints SET retro_notes = ? WHERE id = ?", (retro_notes, sprint_id))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def update_sprint_velocity(self, sprint_id: str, velocity: int, planned_sp: int = 0) -> bool:
        """Update velocity tracking for a sprint (SAFe predictability)."""
        db = get_db()
        try:
            cur = db.execute(
                "UPDATE sprints SET velocity = ?, planned_sp = ? WHERE id = ?",
                (velocity, planned_sp, sprint_id),
            )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def get_velocity_history(self, mission_id: str) -> list:
        """Get velocity trend for a mission's sprints."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT number, velocity, planned_sp, status FROM sprints WHERE mission_id = ? ORDER BY number",
                (mission_id,),
            ).fetchall()
            return [{"sprint": r[0], "velocity": r[1], "planned_sp": r[2], "status": r[3]} for r in rows]
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


# ============================================================================
# MISSION RUNS (lifecycle orchestration)
# ============================================================================

from ..models import MissionRun, MissionStatus, PhaseRun, PhaseStatus


def _row_to_mission_run(row) -> MissionRun:
    phases = json.loads(row["phases_json"]) if row["phases_json"] else []
    # Safe access for workspace_path (may not exist in older DBs)
    wp = ""
    try:
        wp = row["workspace_path"] or ""
    except (IndexError, KeyError):
        pass
    return MissionRun(
        id=row["id"],
        workflow_id=row["workflow_id"],
        workflow_name=row["workflow_name"] or "",
        session_id=row["session_id"] or "",
        cdp_agent_id=row["cdp_agent_id"] or "chef_de_programme",
        project_id=row["project_id"] or "",
        workspace_path=wp,
        status=MissionStatus(row["status"]),
        current_phase=row["current_phase"] or "",
        phases=[PhaseRun(**p) for p in phases],
        brief=row["brief"] or "",
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )


class MissionRunStore:
    """CRUD for mission lifecycle runs."""

    def create(self, run: MissionRun) -> MissionRun:
        db = get_db()
        try:
            db.execute(
                """INSERT INTO mission_runs (id, workflow_id, workflow_name, session_id,
                   cdp_agent_id, project_id, workspace_path, status, current_phase,
                   phases_json, brief, created_at, updated_at, completed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run.id, run.workflow_id, run.workflow_name, run.session_id,
                 run.cdp_agent_id, run.project_id, run.workspace_path, run.status.value,
                 run.current_phase, json.dumps([p.model_dump() for p in run.phases]),
                 run.brief, run.created_at.isoformat(), run.updated_at.isoformat(),
                 run.completed_at.isoformat() if run.completed_at else None),
            )
            db.commit()
        finally:
            db.close()
        return run

    def get(self, run_id: str) -> Optional[MissionRun]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM mission_runs WHERE id = ?", (run_id,)).fetchone()
            return _row_to_mission_run(row) if row else None
        finally:
            db.close()

    def list_runs(self, project_id: str = "", limit: int = 20) -> list[MissionRun]:
        db = get_db()
        try:
            if project_id:
                rows = db.execute(
                    "SELECT * FROM mission_runs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM mission_runs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [_row_to_mission_run(r) for r in rows]
        finally:
            db.close()

    def update(self, run: MissionRun) -> bool:
        run.updated_at = datetime.utcnow()
        db = get_db()
        try:
            cur = db.execute(
                """UPDATE mission_runs SET status=?, current_phase=?, phases_json=?,
                   session_id=?, workspace_path=?, updated_at=?, completed_at=? WHERE id=?""",
                (run.status.value, run.current_phase,
                 json.dumps([p.model_dump() for p in run.phases], default=str),
                 run.session_id or "", run.workspace_path or "",
                 run.updated_at.isoformat(),
                 run.completed_at.isoformat() if run.completed_at else None,
                 run.id),
            )
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def update_phase(self, run_id: str, phase_id: str, **kwargs) -> Optional[MissionRun]:
        """Update a specific phase within a mission run."""
        run = self.get(run_id)
        if not run:
            return None
        for p in run.phases:
            if p.phase_id == phase_id:
                for k, v in kwargs.items():
                    if hasattr(p, k):
                        setattr(p, k, v)
                break
        self.update(run)
        return run

    def delete(self, run_id: str) -> bool:
        db = get_db()
        try:
            cur = db.execute("DELETE FROM mission_runs WHERE id = ?", (run_id,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()


_run_store: Optional[MissionRunStore] = None


def get_mission_run_store() -> MissionRunStore:
    global _run_store
    if _run_store is None:
        _run_store = MissionRunStore()
    return _run_store
