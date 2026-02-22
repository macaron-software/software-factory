"""DB backend — direct sqlite3 access for offline mode."""
import json
import os
import sqlite3
from typing import Any


def _find_db() -> str:
    """Auto-detect platform.db location."""
    candidates = [
        "data/platform.db",
        "../data/platform.db",
        os.path.expanduser("~/.sf/platform.db"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "data/platform.db"


class DBBackend:
    """Direct SQLite access — same interface as APIBackend (read-only mostly)."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _find_db()
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"DB not found: {self.db_path}")
        self._conn = sqlite3.connect(self.db_path, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def close(self):
        self._conn.close()

    def _q(self, sql: str, params: tuple = ()) -> list[dict]:
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _q1(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._q(sql, params)
        return rows[0] if rows else None

    # ── Platform ──

    def health(self) -> dict:
        return {"status": "ok", "mode": "offline/db", "db": self.db_path}

    def monitoring(self) -> dict:
        agents = self._q("SELECT COUNT(*) as c FROM agents")[0]["c"]
        missions = self._q("SELECT COUNT(*) as c FROM missions")[0]["c"]
        return {"agents_total": agents, "missions_total": missions, "mode": "offline"}

    # ── Projects ──

    def projects_list(self) -> list:
        return self._q("SELECT id, name, path, description, status, factory_type, vision, created_at FROM projects ORDER BY created_at DESC")

    def project_create(self, name: str, desc: str = "", path: str = "",
                       proj_type: str = "web") -> dict:
        import uuid
        pid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO projects (id, name, description, path, factory_type, status) VALUES (?,?,?,?,?,?)",
            (pid, name, desc, path, proj_type, "active"))
        self._conn.commit()
        return {"id": pid, "name": name, "status": "created"}

    def project_show(self, pid: str) -> dict:
        r = self._q1("SELECT * FROM projects WHERE id=? OR LOWER(name)=LOWER(?)", (pid, pid))
        return r or {"error": f"Project {pid} not found"}

    def project_vision(self, pid: str, text: str | None = None) -> dict:
        if text:
            self._conn.execute("UPDATE projects SET vision=? WHERE id=?", (text, pid))
            self._conn.commit()
            return {"status": "ok"}
        p = self.project_show(pid)
        return {"vision": p.get("vision", "")}

    def project_git_status(self, pid: str) -> dict:
        p = self.project_show(pid)
        return {"path": p.get("path", ""), "note": "offline — run git status locally"}

    def project_chat_url(self, pid: str) -> str:
        return ""  # not available offline

    # ── Missions ──

    def missions_list(self, project: str | None = None, status: str | None = None) -> list:
        sql = "SELECT id, project_id, name, status, type, wsjf_score, workflow_id, created_at FROM missions"
        conds, params = [], []
        if project:
            conds.append("project_id=?"); params.append(project)
        if status:
            conds.append("status=?"); params.append(status)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY created_at DESC"
        return self._q(sql, tuple(params))

    def mission_show(self, mid: str) -> dict:
        return self._q1("SELECT * FROM missions WHERE id=?", (mid,)) or {"error": "not found"}

    def mission_create(self, name: str, project_id: str, mission_type: str = "epic",
                       **kwargs) -> dict:
        import uuid
        mid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO missions (id, name, project_id, type, status) VALUES (?,?,?,?,?)",
            (mid, name, project_id, mission_type, "draft"))
        self._conn.commit()
        return {"id": mid, "name": name, "status": "draft"}

    def mission_start(self, mid: str) -> dict:
        return {"error": "Cannot start missions in offline mode — server required"}

    def mission_run(self, mid: str) -> dict:
        return {"error": "Cannot run missions in offline mode — server required"}

    def mission_reset(self, mid: str) -> dict:
        self._conn.execute("UPDATE missions SET status='draft' WHERE id=?", (mid,))
        self._conn.commit()
        return {"status": "reset"}

    def mission_wsjf(self, mid: str, bv: int = 5, tc: int = 5,
                     rr: int = 5, jd: int = 5) -> dict:
        score = round((bv + tc + rr) / max(jd, 1), 2)
        self._conn.execute(
            "UPDATE missions SET wsjf_score=?, business_value=?, time_criticality=?, risk_reduction=?, job_duration=? WHERE id=?",
            (score, bv, tc, rr, jd, mid))
        self._conn.commit()
        return {"wsjf_score": score}

    def mission_children(self, mid: str) -> list:
        return self._q("SELECT id, name, status, type FROM missions WHERE parent_mission_id=?", (mid,))

    def mission_chat_url(self, mid: str) -> str:
        return ""

    def mission_run_sse_url(self, mid: str) -> str:
        return ""

    # ── Features ──

    def features_list(self, epic_id: str) -> list:
        return self._q("SELECT * FROM features WHERE epic_id=? ORDER BY priority", (epic_id,))

    def feature_create(self, epic_id: str, name: str, sp: int = 3) -> dict:
        import uuid
        fid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO features (id, epic_id, name, story_points, status) VALUES (?,?,?,?,?)",
            (fid, epic_id, name, sp, "backlog"))
        self._conn.commit()
        return {"id": fid, "name": name}

    def feature_update(self, fid: str, **kwargs) -> dict:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        self._conn.execute(f"UPDATE features SET {sets} WHERE id=?", (*kwargs.values(), fid))
        self._conn.commit()
        return {"status": "ok"}

    def feature_deps(self, fid: str) -> list:
        return self._q("SELECT * FROM feature_deps WHERE feature_id=?", (fid,))

    def feature_add_dep(self, fid: str, dep_id: str, dep_type: str = "blocked_by") -> dict:
        self._conn.execute(
            "INSERT INTO feature_deps (feature_id, depends_on, dep_type) VALUES (?,?,?)",
            (fid, dep_id, dep_type))
        self._conn.commit()
        return {"status": "ok"}

    def feature_rm_dep(self, fid: str, dep_id: str) -> dict:
        self._conn.execute("DELETE FROM feature_deps WHERE feature_id=? AND depends_on=?", (fid, dep_id))
        self._conn.commit()
        return {"status": "ok"}

    # ── Stories ──

    def stories_list(self, feature_id: str | None = None) -> list:
        if feature_id:
            rows = self._conn.execute(
                "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories WHERE feature_id=?",
                (feature_id,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories ORDER BY feature_id, id"
            ).fetchall()
        return [dict(r) for r in rows]

    def story_create(self, feature_id: str, title: str, sp: int = 2) -> dict:
        import uuid
        sid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO user_stories (id, feature_id, title, story_points, status) VALUES (?,?,?,?,?)",
            (sid, feature_id, title, sp, "backlog"))
        self._conn.commit()
        return {"id": sid, "title": title}

    def story_update(self, sid: str, **kwargs) -> dict:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        self._conn.execute(f"UPDATE user_stories SET {sets} WHERE id=?", (*kwargs.values(), sid))
        self._conn.commit()
        return {"status": "ok"}

    # ── Sprints ──

    def sprint_create(self, mission_id: str, name: str, number: int = 1) -> dict:
        import uuid
        sid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO sprints (id, mission_id, name, number, status) VALUES (?,?,?,?,?)",
            (sid, mission_id, name, number, "planned"))
        self._conn.commit()
        return {"id": sid, "name": name}

    def sprint_assign(self, sprint_id: str, story_ids: list[str]) -> dict:
        for sid in story_ids:
            self._conn.execute("UPDATE user_stories SET sprint_id=? WHERE id=?", (sprint_id, sid))
        self._conn.commit()
        return {"assigned": len(story_ids)}

    def sprint_unassign(self, sprint_id: str, story_id: str) -> dict:
        self._conn.execute(
            "UPDATE user_stories SET sprint_id=NULL WHERE id=? AND sprint_id=?",
            (story_id, sprint_id))
        self._conn.commit()
        return {"status": "ok"}

    def sprint_available(self, sprint_id: str) -> list:
        sprint = self._q1("SELECT mission_id FROM sprints WHERE id=?", (sprint_id,))
        if not sprint:
            return []
        return self._q(
            "SELECT us.* FROM user_stories us JOIN features f ON us.feature_id=f.id "
            "WHERE f.epic_id=? AND us.sprint_id IS NULL",
            (sprint["mission_id"],))

    # ── Backlog ──

    def backlog_reorder(self, item_type: str, ids: list[str]) -> dict:
        tbl = "features" if item_type == "features" else "user_stories"
        for i, fid in enumerate(ids):
            self._conn.execute(f"UPDATE {tbl} SET priority=? WHERE id=?", (i + 1, fid))
        self._conn.commit()
        return {"reordered": len(ids)}

    # ── Agents ──

    def agents_list(self, level: str | None = None) -> list:
        rows = self._q("SELECT id, name, role, provider, model, icon, color, tagline FROM agents ORDER BY name")
        # level filtering would need hierarchy_rank mapping
        return rows

    def agent_show(self, aid: str) -> dict:
        return self._q1("SELECT * FROM agents WHERE id=?", (aid,)) or {"error": "not found"}

    def agent_delete(self, aid: str) -> dict:
        self._conn.execute("DELETE FROM agents WHERE id=?", (aid,))
        self._conn.commit()
        return {"status": "ok"}

    # ── Sessions ──

    def sessions_list(self, project: str | None = None) -> list:
        sql = "SELECT id, name, status, project_id, goal, created_at FROM sessions ORDER BY created_at DESC"
        rows = self._q(sql)
        if project:
            rows = [r for r in rows if r.get("project_id") == project]
        return rows

    def session_show(self, sid: str) -> dict:
        session = self._q1("SELECT * FROM sessions WHERE id=?", (sid,))
        if not session:
            return {"error": "not found"}
        msgs = self._q("SELECT from_agent, content, timestamp FROM messages WHERE session_id=? ORDER BY timestamp", (sid,))
        session["messages"] = msgs
        return session

    def session_create(self, project: str | None = None,
                       agents: list[str] | None = None,
                       pattern: str = "solo") -> dict:
        return {"error": "Cannot create sessions in offline mode — server required"}

    def session_stop(self, sid: str) -> dict:
        self._conn.execute("UPDATE sessions SET status='stopped' WHERE id=?", (sid,))
        self._conn.commit()
        return {"status": "stopped"}

    def session_chat_url(self, sid: str) -> str:
        return ""

    # ── Ideation ──

    def ideation_start(self, prompt: str, project_id: str | None = None) -> dict:
        return {"error": "Cannot start ideation in offline mode — server required"}

    def ideation_start_url(self) -> str:
        return ""

    def ideation_create_epic(self, session_id: str) -> dict:
        return {"error": "Cannot create epic in offline mode — server required"}

    def ideation_list(self) -> list:
        return self._q("SELECT id, prompt, status, project_id, created_at FROM ideation_sessions ORDER BY created_at DESC")

    def ideation_session_url(self, session_id: str) -> str:
        return ""

    # ── Metrics (computed from DB) ──

    def metrics_dora(self, project_id: str | None = None) -> dict:
        total = self._q("SELECT COUNT(*) as c FROM missions WHERE status='completed'")[0]["c"]
        return {"deployments": total, "note": "offline approximation"}

    def metrics_velocity(self) -> dict:
        rows = self._q("SELECT s.name, s.velocity, s.planned_sp FROM sprints s WHERE s.velocity IS NOT NULL ORDER BY s.number DESC LIMIT 10")
        return {"sprints": rows}

    def metrics_burndown(self, epic_id: str | None = None) -> dict:
        if epic_id:
            features = self._q("SELECT status, COUNT(*) as c FROM features WHERE epic_id=? GROUP BY status", (epic_id,))
            return {"features": features}
        return {"note": "provide epic_id"}

    def metrics_cycle_time(self) -> dict:
        return {"note": "offline — limited data"}

    # ── LLM ──

    def llm_stats(self) -> dict:
        try:
            rows = self._q("SELECT COUNT(*) as calls, SUM(tokens_in) as ti, SUM(tokens_out) as to_, SUM(cost_estimate) as cost FROM llm_usage")
            return rows[0] if rows else {}
        except Exception:
            return {"note": "llm_usage table not available"}

    def llm_usage(self) -> dict:
        return self.llm_stats()

    def llm_traces(self, limit: int = 20) -> list:
        try:
            return self._q("SELECT * FROM llm_traces ORDER BY timestamp DESC LIMIT ?", (limit,))
        except Exception:
            return []

    # ── Memory ──

    def memory_search(self, query: str) -> list:
        try:
            return self._q("SELECT * FROM memory_project_fts WHERE memory_project_fts MATCH ? LIMIT 20", (query,))
        except Exception:
            return self._q("SELECT * FROM memory_project WHERE content LIKE ? LIMIT 20", (f"%{query}%",))

    def memory_project(self, pid: str) -> list:
        return self._q("SELECT * FROM memory_project WHERE project_id=? ORDER BY updated_at DESC", (pid,))

    def memory_global(self) -> list:
        return self._q("SELECT * FROM memory_global ORDER BY updated_at DESC LIMIT 50")

    def memory_global_set(self, key: str, value: str) -> dict:
        self._conn.execute(
            "INSERT OR REPLACE INTO memory_global (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value))
        self._conn.commit()
        return {"status": "ok"}

    # ── Chaos ──

    def chaos_history(self) -> list:
        try:
            return self._q("SELECT * FROM chaos_runs ORDER BY ts DESC LIMIT 20")
        except Exception:
            return []

    def chaos_trigger(self, scenario: str | None = None) -> dict:
        return {"error": "Cannot trigger chaos in offline mode"}

    # ── Watchdog ──

    def watchdog_metrics(self) -> list:
        try:
            return self._q("SELECT * FROM endurance_metrics ORDER BY ts DESC LIMIT 50")
        except Exception:
            return []

    # ── Incidents ──

    def incidents_list(self) -> list:
        return self._q("SELECT id, title, severity, status, source, created_at FROM platform_incidents ORDER BY created_at DESC LIMIT 50")

    def incident_create(self, title: str, severity: str = "P2",
                        source: str = "cli") -> dict:
        import uuid
        iid = str(uuid.uuid4())[:8]
        self._conn.execute(
            "INSERT INTO platform_incidents (id, title, severity, status, source, created_at) VALUES (?,?,?,?,?,datetime('now'))",
            (iid, title, severity, "open", source))
        self._conn.commit()
        return {"id": iid, "status": "created"}

    # ── Autoheal ──

    def autoheal_stats(self) -> dict:
        healed = self._q("SELECT COUNT(*) as c FROM platform_incidents WHERE status='resolved'")[0]["c"]
        total = self._q("SELECT COUNT(*) as c FROM platform_incidents")[0]["c"]
        return {"healed": healed, "total": total}

    def autoheal_trigger(self) -> dict:
        return {"error": "Cannot trigger autoheal in offline mode"}

    # ── Search ──

    def search(self, query: str) -> dict:
        msgs = self._q("SELECT id, from_agent, content FROM messages WHERE content LIKE ? LIMIT 10", (f"%{query}%",))
        projs = self._q("SELECT id, name FROM projects WHERE name LIKE ? LIMIT 5", (f"%{query}%",))
        missions = self._q("SELECT id, name FROM missions WHERE name LIKE ? LIMIT 5", (f"%{query}%",))
        return {"messages": msgs, "projects": projs, "missions": missions}

    # ── Export ──

    def export_epics(self, fmt: str = "json") -> Any:
        return self._q("SELECT id, project_id, name, status, type, wsjf_score FROM missions WHERE type='epic' ORDER BY created_at DESC")

    def export_features(self, fmt: str = "json") -> Any:
        return self._q("SELECT id, epic_id, name, status, story_points, priority FROM features ORDER BY priority")

    # ── Releases ──

    def releases(self, project_id: str) -> list:
        return self._q("SELECT * FROM missions WHERE project_id=? AND status='completed' ORDER BY completed_at DESC", (project_id,))

    # ── Notifications ──

    def notifications_status(self) -> dict:
        return {"note": "offline — check integrations table"}

    def notifications_test(self) -> dict:
        return {"error": "Cannot send notifications in offline mode"}
