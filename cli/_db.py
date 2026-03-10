"""DB backend — direct PostgreSQL access (psycopg3).

Replaces the old SQLite offline backend. Uses DATABASE_URL env var.
Same interface as APIBackend — read/write via direct SQL.
"""

import os
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row

    _HAS_PSYCOPG = True
except ImportError:
    _HAS_PSYCOPG = False


def _get_pg_url(pg_url: str | None = None) -> str:
    """Resolve PostgreSQL connection URL (priority: arg > env > .env file)."""
    if pg_url and not pg_url.startswith("sqlite"):
        return pg_url
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    # Try loading from .env in repo root
    for candidate in [
        Path(".env"),
        Path(__file__).parent.parent / ".env",
        Path.home() / ".sf" / ".env",
    ]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError(
        "DATABASE_URL not set. Add it to .env or set the DATABASE_URL env var.\n"
        "  Example: DATABASE_URL=postgresql://macaron:pass@localhost:5432/macaron_platform"
    )


class DBBackend:
    """Direct PostgreSQL access — same interface as APIBackend."""

    def __init__(self, db_path: str | None = None):
        if not _HAS_PSYCOPG:
            raise ImportError(
                "psycopg not installed. Run: pip3 install psycopg[binary]"
            )
        pg_url = _get_pg_url(db_path)
        self._conn = psycopg.connect(pg_url, row_factory=dict_row)
        self._conn.autocommit = False
        self.base_url = pg_url.split("@")[-1] if "@" in pg_url else pg_url  # hide creds

    def close(self):
        self._conn.close()

    def _q(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params or None)
            return cur.fetchall() or []

    def _q1(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._q(sql, params)
        return rows[0] if rows else None

    def _exec(self, sql: str, params: tuple = ()):
        with self._conn.cursor() as cur:
            cur.execute(sql, params or None)
        self._conn.commit()

    # ── Platform ──

    def health(self) -> dict:
        return {"status": "ok", "mode": "db/postgresql", "db": self.base_url}

    def monitoring(self) -> dict:
        agents = self._q("SELECT COUNT(*) as c FROM agents")[0]["c"]
        missions = self._q("SELECT COUNT(*) as c FROM epics")[0]["c"]
        return {"agents_total": agents, "missions_total": missions, "mode": "db"}

    # ── Projects ──

    def projects_list(self) -> list:
        return self._q(
            "SELECT id, name, path, description, status, factory_type, vision, created_at FROM projects ORDER BY created_at DESC"
        )

    def project_create(
        self, name: str, desc: str = "", path: str = "", proj_type: str = "web"
    ) -> dict:
        import uuid

        pid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO projects (id, name, description, path, factory_type, status) VALUES (%s,%s,%s,%s,%s,%s)",
            (pid, name, desc, path, proj_type, "active"),
        )
        return {"id": pid, "name": name, "status": "created"}

    def project_show(self, pid: str) -> dict:
        r = self._q1(
            "SELECT * FROM projects WHERE id=%s OR LOWER(name)=LOWER(%s)", (pid, pid)
        )
        return r or {"error": f"Project {pid} not found"}

    def project_vision(self, pid: str, text: str | None = None) -> dict:
        if text:
            self._exec("UPDATE projects SET vision=%s WHERE id=%s", (text, pid))
            return {"status": "ok"}
        p = self.project_show(pid)
        return {"vision": p.get("vision", "")}

    def project_git_status(self, pid: str) -> dict:
        p = self.project_show(pid)
        return {"path": p.get("path", ""), "note": "db mode — run git status locally"}

    def project_chat_url(self, pid: str) -> str:
        return ""

    def project_phase_get(self, pid: str) -> dict:
        row = self._q1("SELECT current_phase FROM projects WHERE id=%s", (pid,))
        if not row:
            return {"error": "not found"}
        return {"project_id": pid, "current_phase": row["current_phase"] or "discovery"}

    def project_phase_set(self, pid: str, phase: str) -> dict:
        self._exec("UPDATE projects SET current_phase=%s WHERE id=%s", (phase, pid))
        return {"project_id": pid, "current_phase": phase, "ok": True}

    def project_health(self, pid: str) -> dict:
        rows = self._q(
            "SELECT status, COUNT(*) as cnt FROM epics WHERE project_id=%s GROUP BY status",
            (pid,),
        )
        counts = {r["status"]: r["cnt"] for r in rows}
        total = sum(counts.values())
        healthy = counts.get("completed", 0)
        score = round((healthy / total * 100) if total else 0)
        return {
            "project_id": pid,
            "health_score": score,
            "mission_counts": counts,
            "total": total,
        }

    def project_missions_suggest(self, pid: str) -> dict:
        row = self._q1("SELECT current_phase FROM projects WHERE id=%s", (pid,))
        phase = (row["current_phase"] or "discovery") if row else "discovery"
        existing = {
            r["name"].lower()
            for r in self._q("SELECT name FROM epics WHERE project_id=%s", (pid,))
        }
        SUGGESTIONS = {
            "discovery": [
                "Exploration marché",
                "Analyse concurrentielle",
                "Identification des besoins",
                "Proof of Concept",
            ],
            "mvp": [
                "Architecture technique",
                "Sprint MVP 1",
                "Tests utilisateurs",
                "CI/CD setup",
            ],
            "v1": [
                "Feature dev Sprint 1",
                "Optimisation performance",
                "Documentation",
                "Beta test",
            ],
            "run": [
                "Monitoring production",
                "Sprint amélioration",
                "Scalabilité",
                "Sécurité audit",
            ],
            "maintenance": [
                "Patch sécurité",
                "Dette technique",
                "Migration",
                "Archivage",
            ],
        }
        candidates = SUGGESTIONS.get(phase, SUGGESTIONS["discovery"])
        return {
            "project_id": pid,
            "current_phase": phase,
            "suggestions": [s for s in candidates if s.lower() not in existing][:5],
        }

    # ── Missions ──

    def missions_list(
        self, project: str | None = None, status: str | None = None
    ) -> list:
        sql = "SELECT id, project_id, name, status, type, wsjf_score, workflow_id, created_at FROM epics"
        conds, params = [], []
        if project:
            conds.append("project_id=%s")
            params.append(project)
        if status:
            conds.append("status=%s")
            params.append(status)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY created_at DESC"
        return self._q(sql, tuple(params))

    def mission_show(self, mid: str) -> dict:
        return self._q1("SELECT * FROM epics WHERE id=%s", (mid,)) or {
            "error": "not found"
        }

    def mission_create(
        self, name: str, project_id: str, mission_type: str = "epic", **kwargs
    ) -> dict:
        import uuid

        mid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO epics (id, name, project_id, type, status) VALUES (%s,%s,%s,%s,%s)",
            (mid, name, project_id, mission_type, "draft"),
        )
        return {"id": mid, "name": name, "status": "draft"}

    def mission_start(self, mid: str) -> dict:
        return {"error": "Cannot start missions in db mode — server required"}

    def epic_run(self, mid: str) -> dict:
        return {"error": "Cannot run missions in db mode — server required"}

    def mission_reset(self, mid: str) -> dict:
        self._exec("UPDATE epics SET status='draft' WHERE id=%s", (mid,))
        return {"status": "reset"}

    def mission_wsjf(
        self, mid: str, bv: int = 5, tc: int = 5, rr: int = 5, jd: int = 5
    ) -> dict:
        score = round((bv + tc + rr) / max(jd, 1), 2)
        self._exec(
            "UPDATE epics SET wsjf_score=%s, business_value=%s, time_criticality=%s, risk_reduction=%s, job_duration=%s WHERE id=%s",
            (score, bv, tc, rr, jd, mid),
        )
        return {"wsjf_score": score}

    def mission_children(self, mid: str) -> list:
        return self._q(
            "SELECT id, name, status, type FROM epics WHERE parent_epic_id=%s", (mid,)
        )

    def mission_chat_url(self, mid: str) -> str:
        return ""

    def epic_run_sse_url(self, mid: str) -> str:
        return ""

    # ── Features ──

    def features_list(self, epic_id: str) -> list:
        return self._q(
            "SELECT * FROM features WHERE epic_id=%s ORDER BY priority", (epic_id,)
        )

    def feature_create(self, epic_id: str, name: str, sp: int = 3) -> dict:
        import uuid

        fid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO features (id, epic_id, name, story_points, status) VALUES (%s,%s,%s,%s,%s)",
            (fid, epic_id, name, sp, "backlog"),
        )
        return {"id": fid, "name": name}

    def feature_update(self, fid: str, **kwargs) -> dict:
        sets = ", ".join(f"{k}=%s" for k in kwargs)
        self._exec(f"UPDATE features SET {sets} WHERE id=%s", (*kwargs.values(), fid))
        return {"status": "ok"}

    def feature_deps(self, fid: str) -> list:
        return self._q("SELECT * FROM feature_deps WHERE feature_id=%s", (fid,))

    def feature_add_dep(
        self, fid: str, dep_id: str, dep_type: str = "blocked_by"
    ) -> dict:
        self._exec(
            "INSERT INTO feature_deps (feature_id, depends_on, dep_type) VALUES (%s,%s,%s)",
            (fid, dep_id, dep_type),
        )
        return {"status": "ok"}

    def feature_rm_dep(self, fid: str, dep_id: str) -> dict:
        self._exec(
            "DELETE FROM feature_deps WHERE feature_id=%s AND depends_on=%s",
            (fid, dep_id),
        )
        return {"status": "ok"}

    # ── Stories ──

    def stories_list(self, feature_id: str | None = None) -> list:
        if feature_id:
            return self._q(
                "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories WHERE feature_id=%s",
                (feature_id,),
            )
        return self._q(
            "SELECT id, feature_id, title, story_points, status, sprint_id FROM user_stories ORDER BY feature_id, id"
        )

    def story_create(self, feature_id: str, title: str, sp: int = 2) -> dict:
        import uuid

        sid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO user_stories (id, feature_id, title, story_points, status) VALUES (%s,%s,%s,%s,%s)",
            (sid, feature_id, title, sp, "backlog"),
        )
        return {"id": sid, "title": title}

    def story_update(self, sid: str, **kwargs) -> dict:
        sets = ", ".join(f"{k}=%s" for k in kwargs)
        self._exec(
            f"UPDATE user_stories SET {sets} WHERE id=%s", (*kwargs.values(), sid)
        )
        return {"status": "ok"}

    # ── Sprints ──

    def sprint_create(self, mission_id: str, name: str, number: int = 1) -> dict:
        import uuid

        sid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO sprints (id, mission_id, name, number, status) VALUES (%s,%s,%s,%s,%s)",
            (sid, mission_id, name, number, "planned"),
        )
        return {"id": sid, "name": name}

    def sprint_assign(self, sprint_id: str, story_ids: list[str]) -> dict:
        for sid in story_ids:
            self._exec(
                "UPDATE user_stories SET sprint_id=%s WHERE id=%s", (sprint_id, sid)
            )
        return {"assigned": len(story_ids)}

    def sprint_unassign(self, sprint_id: str, story_id: str) -> dict:
        self._exec(
            "UPDATE user_stories SET sprint_id=NULL WHERE id=%s AND sprint_id=%s",
            (story_id, sprint_id),
        )
        return {"status": "ok"}

    def sprint_available(self, sprint_id: str) -> list:
        sprint = self._q1("SELECT mission_id FROM sprints WHERE id=%s", (sprint_id,))
        if not sprint:
            return []
        return self._q(
            "SELECT us.* FROM user_stories us JOIN features f ON us.feature_id=f.id "
            "WHERE f.epic_id=%s AND us.sprint_id IS NULL",
            (sprint["mission_id"],),
        )

    # ── Backlog ──

    def backlog_reorder(self, item_type: str, ids: list[str]) -> dict:
        tbl = "features" if item_type == "features" else "user_stories"
        for i, fid in enumerate(ids):
            self._exec(f"UPDATE {tbl} SET priority=%s WHERE id=%s", (i + 1, fid))
        return {"reordered": len(ids)}

    # ── Agents ──

    def agents_list(self, level: str | None = None) -> list:
        return self._q(
            "SELECT id, name, role, provider, model, icon, color, tagline FROM agents ORDER BY name"
        )

    def agent_show(self, aid: str) -> dict:
        return self._q1("SELECT * FROM agents WHERE id=%s", (aid,)) or {
            "error": "not found"
        }

    def agent_delete(self, aid: str) -> dict:
        self._exec("DELETE FROM agents WHERE id=%s", (aid,))
        return {"status": "ok"}

    # ── Sessions ──

    def sessions_list(self, project: str | None = None) -> list:
        rows = self._q(
            "SELECT id, name, status, project_id, goal, created_at FROM sessions ORDER BY created_at DESC"
        )
        if project:
            rows = [r for r in rows if r.get("project_id") == project]
        return rows

    def session_show(self, sid: str) -> dict:
        session = self._q1("SELECT * FROM sessions WHERE id=%s", (sid,))
        if not session:
            return {"error": "not found"}
        msgs = self._q(
            "SELECT from_agent, content, timestamp FROM messages WHERE session_id=%s ORDER BY timestamp",
            (sid,),
        )
        session["messages"] = msgs
        return session

    def session_create(
        self,
        project: str | None = None,
        agents: list[str] | None = None,
        pattern: str = "solo",
    ) -> dict:
        return {"error": "Cannot create sessions in db mode — server required"}

    def session_stop(self, sid: str) -> dict:
        self._exec("UPDATE sessions SET status='stopped' WHERE id=%s", (sid,))
        return {"status": "stopped"}

    def session_checkpoints(self, sid: str) -> dict:
        has_table = self._q1(
            "SELECT 1 FROM information_schema.tables WHERE table_name='agent_step_checkpoints'"
        )
        if not has_table:
            return {"session_id": sid, "checkpoints": [], "agent_count": 0}
        rows = self._q(
            "SELECT agent_id, step_index, tool_calls, partial_content FROM agent_step_checkpoints "
            "WHERE session_id=%s ORDER BY agent_id, step_index DESC",
            (sid,),
        )
        import json as _json

        seen: dict = {}
        for r in rows:
            aid = r["agent_id"]
            if aid in seen:
                continue
            try:
                tools = _json.loads(r["tool_calls"] or "[]")
                last_tool = tools[-1].get("name", "") if tools else ""
            except Exception:
                last_tool = ""
            seen[aid] = {
                "agent_id": aid,
                "step": r["step_index"],
                "last_tool": last_tool,
                "preview": (r["partial_content"] or "")[:100],
            }
        checkpoints = list(seen.values())
        return {
            "session_id": sid,
            "checkpoints": checkpoints,
            "agent_count": len(checkpoints),
        }

    def session_chat_url(self, sid: str) -> str:
        return ""

    # ── Ideation ──

    def ideation_start(self, prompt: str, project_id: str | None = None) -> dict:
        return {"error": "Cannot start ideation in db mode — server required"}

    def ideation_start_url(self) -> str:
        return ""

    def ideation_create_epic(self, session_id: str) -> dict:
        return {"error": "Cannot create epic in db mode — server required"}

    def ideation_list(self) -> list:
        return self._q(
            "SELECT id, prompt, status, project_id, created_at FROM ideation_sessions ORDER BY created_at DESC"
        )

    def ideation_session_url(self, session_id: str) -> str:
        return ""

    # ── Metrics ──

    def metrics_dora(self, project_id: str | None = None) -> dict:
        total = self._q("SELECT COUNT(*) as c FROM epics WHERE status='completed'")[0][
            "c"
        ]
        return {"deployments": total, "note": "db approximation"}

    def metrics_velocity(self) -> dict:
        rows = self._q(
            "SELECT s.name, s.velocity, s.planned_sp FROM sprints s WHERE s.velocity IS NOT NULL ORDER BY s.number DESC LIMIT 10"
        )
        return {"sprints": rows}

    def metrics_burndown(self, epic_id: str | None = None) -> dict:
        if epic_id:
            features = self._q(
                "SELECT status, COUNT(*) as c FROM features WHERE epic_id=%s GROUP BY status",
                (epic_id,),
            )
            return {"features": features}
        return {"note": "provide epic_id"}

    def metrics_cycle_time(self) -> dict:
        return {"note": "db mode — limited data"}

    # ── LLM ──

    def llm_stats(self) -> dict:
        try:
            rows = self._q(
                "SELECT COUNT(*) as calls, SUM(tokens_in) as ti, SUM(tokens_out) as to_, SUM(cost_estimate) as cost FROM llm_usage"
            )
            return rows[0] if rows else {}
        except Exception:
            return {"note": "llm_usage table not available"}

    def llm_usage(self) -> dict:
        return self.llm_stats()

    def llm_traces(self, limit: int = 20) -> list:
        try:
            return self._q(
                "SELECT * FROM llm_traces ORDER BY timestamp DESC LIMIT %s", (limit,)
            )
        except Exception:
            return []

    # ── Tasks ──

    def task_brief_submit(self, brief: dict) -> dict:
        import uuid

        mid = f"tma-copilot-{uuid.uuid4().hex[:8]}"
        title = brief.get("title", "Untitled")
        goal = f"[Copilot brief] {brief.get('description', '')}"
        project_id = brief.get("project_id", "software-factory")
        try:
            self._exec(
                "INSERT INTO epics (id, project_id, name, status, type, goal, wsjf_score, created_at) "
                "VALUES (%s, %s, %s, 'planning', 'program', %s, 5.0, NOW())",
                (mid, project_id, f"[Copilot] {title}", goal),
            )
            return {
                "mission_id": mid,
                "session_url": f"/missions/{mid}",
                "status": "created",
            }
        except Exception as e:
            return {"error": str(e)}

    def task_brief_status(self, mid: str) -> dict:
        row = self._q1(
            "SELECT id, name, status, created_at FROM epics WHERE id=%s", (mid,)
        )
        if not row:
            return {"error": "not found"}
        return {
            "mission_id": row["id"],
            "title": row["name"],
            "status": row["status"],
            "created_at": str(row["created_at"]),
        }

    # ── Memory ──

    def memory_search(self, query: str) -> list:
        try:
            return self._q(
                "SELECT * FROM memory_project WHERE to_tsvector('french', content) @@ plainto_tsquery('french', %s) LIMIT 20",
                (query,),
            )
        except Exception:
            return self._q(
                "SELECT * FROM memory_project WHERE content ILIKE %s LIMIT 20",
                (f"%{query}%",),
            )

    def memory_project(self, pid: str) -> list:
        return self._q(
            "SELECT * FROM memory_project WHERE project_id=%s ORDER BY updated_at DESC",
            (pid,),
        )

    def memory_global(self) -> list:
        return self._q("SELECT * FROM memory_global ORDER BY updated_at DESC LIMIT 50")

    def memory_global_set(self, key: str, value: str) -> dict:
        self._exec(
            "INSERT INTO memory_global (key, value, updated_at) VALUES (%s, %s, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()",
            (key, value),
        )
        return {"status": "ok"}

    # ── Chaos ──

    def chaos_history(self) -> list:
        try:
            return self._q("SELECT * FROM chaos_runs ORDER BY ts DESC LIMIT 20")
        except Exception:
            return []

    def chaos_trigger(self, scenario: str | None = None) -> dict:
        return {"error": "Cannot trigger chaos in db mode — server required"}

    # ── Watchdog ──

    def watchdog_metrics(self) -> list:
        try:
            return self._q("SELECT * FROM endurance_metrics ORDER BY ts DESC LIMIT 50")
        except Exception:
            return []

    # ── Incidents ──

    def incidents_list(self) -> list:
        return self._q(
            "SELECT id, title, severity, status, source, created_at FROM platform_incidents ORDER BY created_at DESC LIMIT 50"
        )

    def incident_create(
        self, title: str, severity: str = "P2", source: str = "cli"
    ) -> dict:
        import uuid

        iid = str(uuid.uuid4())[:8]
        self._exec(
            "INSERT INTO platform_incidents (id, title, severity, status, source, created_at) VALUES (%s,%s,%s,%s,%s,NOW())",
            (iid, title, severity, "open", source),
        )
        return {"id": iid, "status": "created"}

    # ── Autoheal ──

    def autoheal_stats(self) -> dict:
        healed = self._q(
            "SELECT COUNT(*) as c FROM platform_incidents WHERE status='resolved'"
        )[0]["c"]
        total = self._q("SELECT COUNT(*) as c FROM platform_incidents")[0]["c"]
        return {"healed": healed, "total": total}

    def autoheal_trigger(self) -> dict:
        return {"error": "Cannot trigger autoheal in db mode — server required"}

    # ── Search ──

    def search(self, query: str) -> dict:
        msgs = self._q(
            "SELECT id, from_agent, content FROM messages WHERE content ILIKE %s LIMIT 10",
            (f"%{query}%",),
        )
        projs = self._q(
            "SELECT id, name FROM projects WHERE name ILIKE %s LIMIT 5", (f"%{query}%",)
        )
        missions = self._q(
            "SELECT id, name FROM epics WHERE name ILIKE %s LIMIT 5", (f"%{query}%",)
        )
        return {"messages": msgs, "projects": projs, "epics": missions}

    # ── Export ──

    def export_epics(self, fmt: str = "json") -> Any:
        return self._q(
            "SELECT id, project_id, name, status, type, wsjf_score FROM epics WHERE type='epic' ORDER BY created_at DESC"
        )

    def export_features(self, fmt: str = "json") -> Any:
        return self._q(
            "SELECT id, epic_id, name, status, story_points, priority FROM features ORDER BY priority"
        )

    # ── Releases ──

    def releases(self, project_id: str) -> list:
        return self._q(
            "SELECT * FROM epics WHERE project_id=%s AND status='completed' ORDER BY completed_at DESC",
            (project_id,),
        )

    # ── Notifications ──

    def notifications_status(self) -> dict:
        return {"note": "db mode — check integrations table"}

    def notifications_test(self) -> dict:
        return {"error": "Cannot send notifications in db mode — server required"}

    # ── Darwin Teams ──

    def teams_contexts(self) -> list:
        return self._q(
            "SELECT DISTINCT technology, phase_type, COUNT(*) as teams FROM team_fitness GROUP BY technology, phase_type"
        )

    def teams_leaderboard(
        self, technology: str = "generic", phase_type: str = "generic", limit: int = 30
    ) -> dict:
        rows = self._q(
            """SELECT tf.agent_id, tf.pattern_id, tf.technology, tf.phase_type,
                      tf.fitness_score, tf.runs, tf.wins, tf.losses, tf.retired,
                      a.name as agent_name,
                      CASE WHEN tf.runs >= 5 AND tf.fitness_score >= 80 THEN 'champion'
                           WHEN tf.runs >= 3 AND tf.fitness_score >= 60 THEN 'rising'
                           WHEN tf.retired = TRUE THEN 'retired'
                           WHEN tf.runs >= 10 AND tf.fitness_score < 40 THEN 'declining'
                           ELSE 'active' END as badge
               FROM team_fitness tf LEFT JOIN agents a ON a.id = tf.agent_id
               WHERE tf.technology = %s AND tf.phase_type = %s
               ORDER BY tf.fitness_score DESC LIMIT %s""",
            (technology, phase_type, limit),
        )
        return {"data": rows, "technology": technology, "phase_type": phase_type}

    def teams_okr(self, technology: str = "", phase_type: str = "") -> list:
        q = "SELECT * FROM team_okr"
        p: list = []
        filters = []
        if technology:
            filters.append("technology = %s")
            p.append(technology)
        if phase_type:
            filters.append("phase_type = %s")
            p.append(phase_type)
        if filters:
            q += " WHERE " + " AND ".join(filters)
        rows = self._q(q, tuple(p))
        for r in rows:
            r["progress_pct"] = (
                round(r["kpi_current"] / r["kpi_target"] * 100, 1)
                if r.get("kpi_target")
                else 0.0
            )
        return rows

    def teams_evolution(
        self, technology: str = "generic", phase_type: str = "generic", days: int = 30
    ) -> dict:
        rows = self._q(
            """SELECT tfh.agent_id, tfh.pattern_id, tfh.snapshot_date,
                      tfh.fitness_score, a.name as agent_name
               FROM team_fitness_history tfh LEFT JOIN agents a ON a.id = tfh.agent_id
               WHERE tfh.technology = %s AND tfh.phase_type = %s
                 AND tfh.snapshot_date >= NOW() - INTERVAL '%s days'
               ORDER BY tfh.agent_id, tfh.pattern_id, tfh.snapshot_date""",
            (technology, phase_type, days),
        )
        series: dict = {}
        for r in rows:
            key = f"{r['agent_id']}:{r['pattern_id']}"
            if key not in series:
                series[key] = {
                    "agent_id": r["agent_id"],
                    "agent_name": r.get("agent_name") or r["agent_id"],
                    "pattern_id": r["pattern_id"],
                    "dates": [],
                    "scores": [],
                }
            series[key]["dates"].append(str(r["snapshot_date"]))
            series[key]["scores"].append(round(r["fitness_score"], 1))
        return {
            "series": list(series.values()),
            "technology": technology,
            "phase_type": phase_type,
        }

    def teams_selections(self, limit: int = 20) -> dict:
        rows = self._q(
            "SELECT ts.*, a.name as agent_name FROM team_selections ts "
            "LEFT JOIN agents a ON a.id = ts.agent_id ORDER BY ts.selected_at DESC LIMIT %s",
            (limit,),
        )
        return {"data": rows}

    def teams_ab_tests(self, status: str = "", limit: int = 20) -> dict:
        q = (
            "SELECT tab.*, a1.name as team_a_name, a2.name as team_b_name "
            "FROM team_ab_tests tab "
            "LEFT JOIN agents a1 ON a1.id = tab.team_a_agent "
            "LEFT JOIN agents a2 ON a2.id = tab.team_b_agent"
        )
        p: list = []
        if status:
            q += " WHERE tab.status = %s"
            p.append(status)
        q += " ORDER BY tab.started_at DESC LIMIT %s"
        p.append(limit)
        return {"data": self._q(q, tuple(p))}

    def teams_retire(
        self,
        agent_id: str,
        pattern_id: str,
        technology: str = "generic",
        phase_type: str = "generic",
    ) -> dict:
        self._exec(
            "UPDATE team_fitness SET retired=TRUE, weight_multiplier=0.1 "
            "WHERE agent_id=%s AND pattern_id=%s AND technology=%s AND phase_type=%s",
            (agent_id, pattern_id, technology, phase_type),
        )
        return {"ok": True}

    def teams_unretire(
        self,
        agent_id: str,
        pattern_id: str,
        technology: str = "generic",
        phase_type: str = "generic",
    ) -> dict:
        self._exec(
            "UPDATE team_fitness SET retired=FALSE, weight_multiplier=1.0 "
            "WHERE agent_id=%s AND pattern_id=%s AND technology=%s AND phase_type=%s",
            (agent_id, pattern_id, technology, phase_type),
        )
        return {"ok": True}
