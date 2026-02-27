"""API backend — httpx client wrapping all REST endpoints."""

from typing import Any

try:
    import httpx
except ImportError:
    httpx = None


class APIBackend:
    """Connects to the Macaron platform via REST API."""

    def __init__(self, base_url: str, token: str | None = None):
        if httpx is None:
            raise RuntimeError("httpx required: pip install httpx")
        self.base_url = base_url.rstrip("/")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=30,
            headers=headers,
            follow_redirects=True,
        )

    def close(self):
        self._client.close()

    # ── helpers ──

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict | None = None) -> Any:
        r = self._client.post(path, json=data or {})
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": "ok", "text": r.text}

    def _patch(self, path: str, data: dict | None = None) -> Any:
        r = self._client.patch(path, json=data or {})
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": "ok"}

    def _delete(self, path: str) -> Any:
        r = self._client.delete(path)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": "ok"}

    def _put(self, path: str, data: dict | None = None) -> Any:
        r = self._client.put(path, json=data or {})
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": "ok"}

    # ── Platform ──

    def health(self) -> dict:
        try:
            return self._get("/api/health")
        except Exception:
            return {"status": "unknown", "url": self.base_url}

    def monitoring(self) -> dict:
        return self._get("/api/monitoring/live")

    # ── Projects ──

    def projects_list(self) -> list:
        return self._get("/api/projects")

    def project_create(
        self, name: str, desc: str = "", path: str = "", proj_type: str = "web"
    ) -> dict:
        return self._post(
            "/api/projects",
            {
                "name": name,
                "description": desc,
                "path": path,
                "type": proj_type,
            },
        )

    def project_show(self, pid: str) -> dict:
        projs = self.projects_list()
        for p in projs:
            if p.get("id") == pid or p.get("name", "").lower() == pid.lower():
                return p
        return {"error": f"Project {pid} not found"}

    def project_vision(self, pid: str, text: str | None = None) -> dict:
        if text:
            return self._post(f"/api/projects/{pid}/vision", {"vision": text})
        p = self.project_show(pid)
        return {"vision": p.get("vision", "")}

    def project_git_status(self, pid: str) -> dict:
        return self._get(f"/api/projects/{pid}/git-status")

    def project_phase_get(self, pid: str) -> dict:
        return self._get(f"/api/projects/{pid}/phase")

    def project_phase_set(self, pid: str, phase: str) -> dict:
        return self._post(f"/api/projects/{pid}/phase", {"phase": phase})

    def project_health(self, pid: str) -> dict:
        return self._get(f"/api/projects/{pid}/health")

    def project_missions_suggest(self, pid: str) -> dict:
        return self._get(f"/api/projects/{pid}/missions/suggest")

    def project_chat_url(self, pid: str) -> str:
        return f"{self.base_url}/api/projects/{pid}/chat/stream"

    # ── Missions ──

    def missions_list(
        self, project: str | None = None, status: str | None = None
    ) -> list:
        data = self._get("/api/missions")
        missions = data.get("missions", data) if isinstance(data, dict) else data
        if project:
            missions = [m for m in missions if m.get("project_id") == project]
        if status:
            missions = [m for m in missions if m.get("status") == status]
        return missions

    def mission_show(self, mid: str) -> dict:
        return self._get(f"/api/missions/{mid}")

    def mission_create(
        self, name: str, project_id: str, mission_type: str = "epic", **kwargs
    ) -> dict:
        body = {"name": name, "project_id": project_id, "type": mission_type, **kwargs}
        return self._post("/api/missions", body)

    def mission_start(self, mid: str) -> dict:
        return self._post(f"/api/missions/{mid}/start")

    def mission_run(self, mid: str) -> dict:
        return self._post(f"/api/missions/{mid}/run")

    def mission_reset(self, mid: str) -> dict:
        return self._post(f"/api/missions/{mid}/reset")

    def mission_wsjf(
        self, mid: str, bv: int = 5, tc: int = 5, rr: int = 5, jd: int = 5
    ) -> dict:
        return self._post(
            f"/api/missions/{mid}/wsjf",
            {
                "business_value": bv,
                "time_criticality": tc,
                "risk_reduction": rr,
                "job_duration": jd,
            },
        )

    def mission_children(self, mid: str) -> list:
        return self._get(f"/api/missions/{mid}/children")

    def mission_chat_url(self, mid: str) -> str:
        return f"{self.base_url}/api/missions/{mid}/chat/stream"

    def mission_run_sse_url(self, mid: str) -> str:
        return f"{self.base_url}/api/sessions/{mid}/stream"

    # ── Features ──

    def features_list(self, epic_id: str) -> list:
        return self._get(f"/api/epics/{epic_id}/features")

    def feature_create(self, epic_id: str, name: str, sp: int = 3) -> dict:
        return self._post(
            f"/api/epics/{epic_id}/features",
            {
                "name": name,
                "story_points": sp,
            },
        )

    def feature_update(self, fid: str, **kwargs) -> dict:
        return self._patch(f"/api/features/{fid}", kwargs)

    def feature_deps(self, fid: str) -> list:
        return self._get(f"/api/features/{fid}/deps")

    def feature_add_dep(
        self, fid: str, dep_id: str, dep_type: str = "blocked_by"
    ) -> dict:
        return self._post(
            f"/api/features/{fid}/deps",
            {
                "depends_on": dep_id,
                "dep_type": dep_type,
            },
        )

    def feature_rm_dep(self, fid: str, dep_id: str) -> dict:
        return self._delete(f"/api/features/{fid}/deps/{dep_id}")

    # ── Stories ──

    def stories_list(self, feature_id: str | None = None) -> list:
        if feature_id:
            return self._get(f"/api/features/{feature_id}/stories")
        return self._get("/api/stories")

    def story_create(self, feature_id: str, title: str, sp: int = 2) -> dict:
        return self._post(
            f"/api/features/{feature_id}/stories",
            {
                "title": title,
                "story_points": sp,
            },
        )

    def story_update(self, sid: str, **kwargs) -> dict:
        return self._patch(f"/api/stories/{sid}", kwargs)

    # ── Sprints ──

    def sprint_create(self, mission_id: str, name: str, number: int = 1) -> dict:
        return self._post(
            f"/api/missions/{mission_id}/sprints",
            {
                "name": name,
                "number": number,
            },
        )

    def sprint_assign(self, sprint_id: str, story_ids: list[str]) -> dict:
        return self._post(
            f"/api/sprints/{sprint_id}/assign-stories",
            {
                "story_ids": story_ids,
            },
        )

    def sprint_unassign(self, sprint_id: str, story_id: str) -> dict:
        return self._delete(f"/api/sprints/{sprint_id}/stories/{story_id}")

    def sprint_available(self, sprint_id: str) -> list:
        return self._get(f"/api/sprints/{sprint_id}/available-stories")

    # ── Backlog ──

    def backlog_reorder(self, item_type: str, ids: list[str]) -> dict:
        return self._patch(
            "/api/backlog/reorder",
            {
                "type": item_type,
                "ordered_ids": ids,
            },
        )

    # ── Agents ──

    def agents_list(self, level: str | None = None) -> list:
        agents = self._get("/api/agents")
        if level:
            agents = [a for a in agents if a.get("level") == level]
        return agents

    def agent_show(self, aid: str) -> dict:
        agents = self.agents_list()
        for a in agents:
            if a.get("id") == aid:
                return a
        return {"error": f"Agent {aid} not found"}

    def agent_delete(self, aid: str) -> dict:
        return self._delete(f"/api/agents/{aid}")

    # ── Sessions ──

    def sessions_list(self, project: str | None = None) -> list:
        data = self._get("/api/sessions")
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        if project:
            sessions = [s for s in sessions if s.get("project_id") == project]
        return sessions

    def session_show(self, sid: str) -> dict:
        return self._get(f"/api/sessions/{sid}")

    def session_create(
        self,
        project: str | None = None,
        agents: list[str] | None = None,
        pattern: str = "solo",
    ) -> dict:
        body = {"pattern": pattern}
        if project:
            body["project_id"] = project
        if agents:
            body["agents"] = agents
        return self._post("/api/sessions", body)

    def session_stop(self, sid: str) -> dict:
        return self._post(f"/api/sessions/{sid}/stop")

    def session_checkpoints(self, sid: str) -> dict:
        return self._get(f"/api/sessions/{sid}/checkpoints")

    def session_chat_url(self, sid: str) -> str:
        return f"{self.base_url}/api/sessions/{sid}/stream"

    # ── Ideation ──

    def ideation_start(self, prompt: str, project_id: str | None = None) -> dict:
        body = {"prompt": prompt}
        if project_id:
            body["project_id"] = project_id
        return self._post("/api/ideation", body)

    def ideation_start_url(self) -> str:
        return f"{self.base_url}/api/ideation"

    def ideation_create_epic(self, session_id: str) -> dict:
        return self._post("/api/ideation/create-epic", {"session_id": session_id})

    def ideation_list(self) -> list:
        return self._get("/api/ideation/sessions")

    def ideation_session_url(self, session_id: str) -> str:
        return f"{self.base_url}/api/sessions/{session_id}/stream"

    # ── Metrics ──

    def metrics_dora(self, project_id: str | None = None) -> dict:
        params = {"project_id": project_id} if project_id else None
        return self._get("/api/metrics/dora", params)

    def metrics_velocity(self) -> dict:
        return self._get("/api/metrics/velocity")

    def metrics_burndown(self, epic_id: str | None = None) -> dict:
        params = {"epic_id": epic_id} if epic_id else None
        return self._get("/api/metrics/burndown", params)

    def metrics_cycle_time(self) -> dict:
        return self._get("/api/metrics/cycle-time")

    # ── LLM ──

    def llm_stats(self) -> dict:
        return self._get("/api/llm/stats")

    def llm_usage(self) -> dict:
        return self._get("/api/llm/usage")

    def llm_traces(self, limit: int = 20) -> list:
        return self._get("/api/llm/traces", {"limit": limit})

    # ── Memory ──

    def memory_search(self, query: str) -> list:
        return self._get("/api/memory/search", {"q": query})

    def memory_project(self, pid: str) -> list:
        return self._get(f"/api/memory/project/{pid}")

    def memory_global(self) -> list:
        return self._get("/api/memory/global")

    def memory_global_set(self, key: str, value: str) -> dict:
        return self._post("/api/memory/global", {"key": key, "value": value})

    # ── Workflows ──

    def workflows_list(self) -> list:
        """List all workflows."""
        wfs = self._get("/api/workflows")
        return wfs if isinstance(wfs, list) else []

    def workflow_show(self, wf_id: str) -> dict:
        """Show workflow details."""
        return self._get(f"/api/workflows/{wf_id}")

    # ── Patterns ──

    def patterns_list(self) -> list:
        """List all patterns."""
        patterns = self._get("/api/patterns")
        return patterns if isinstance(patterns, list) else []

    def pattern_show(self, pattern_id: str) -> dict:
        """Show pattern details."""
        return self._get(f"/api/patterns/{pattern_id}")

    # ── Chaos ──

    def chaos_history(self) -> list:
        return self._get("/api/chaos/history")

    def chaos_trigger(self, scenario: str | None = None) -> dict:
        body = {}
        if scenario:
            body["scenario"] = scenario
        return self._post("/api/chaos/trigger", body)

    # ── Watchdog ──

    def watchdog_metrics(self) -> list:
        return self._get("/api/watchdog/metrics")

    # ── Incidents ──

    def incidents_list(self) -> list:
        return self._get("/api/incidents")

    def incident_create(
        self, title: str, severity: str = "P2", source: str = "cli"
    ) -> dict:
        return self._post(
            "/api/incidents",
            {
                "title": title,
                "severity": severity,
                "source": source,
            },
        )

    # ── Autoheal ──

    def autoheal_stats(self) -> dict:
        return self._get("/api/autoheal/stats")

    def autoheal_trigger(self) -> dict:
        return self._get("/api/autoheal/trigger")

    # ── Search ──

    def search(self, query: str) -> dict:
        return self._get("/api/search", {"q": query})

    # ── Export ──

    def export_epics(self, fmt: str = "json") -> Any:
        return self._get("/api/export/epics", {"format": fmt})

    def export_features(self, fmt: str = "json") -> Any:
        return self._get("/api/export/features", {"format": fmt})

    # ── Releases ──

    def releases(self, project_id: str) -> list:
        return self._get(f"/api/releases/{project_id}")

    # ── Notifications ──

    def notifications_status(self) -> dict:
        return self._post("/api/notifications/status")

    def notifications_test(self) -> dict:
        return self._post("/api/notifications/test")

    # ── Darwin Teams ──

    def teams_contexts(self) -> list:
        return self._get("/api/teams/contexts")

    def teams_leaderboard(
        self, technology: str = "generic", phase_type: str = "generic", limit: int = 30
    ) -> dict:
        return self._get(
            "/api/teams/leaderboard",
            {"technology": technology, "phase_type": phase_type, "limit": limit},
        )

    def teams_okr(self, technology: str = "", phase_type: str = "") -> list:
        params = {}
        if technology:
            params["technology"] = technology
        if phase_type:
            params["phase_type"] = phase_type
        return self._get("/api/teams/okr", params)

    def teams_evolution(
        self, technology: str = "generic", phase_type: str = "generic", days: int = 30
    ) -> dict:
        return self._get(
            "/api/teams/evolution",
            {"technology": technology, "phase_type": phase_type, "days": days},
        )

    def teams_selections(self, limit: int = 20) -> dict:
        return self._get("/api/teams/selections", {"limit": limit})

    def teams_ab_tests(self, status: str = "", limit: int = 20) -> dict:
        params: dict = {"limit": limit}
        if status:
            params["status"] = status
        return self._get("/api/teams/ab-tests", params)

    def teams_retire(
        self,
        agent_id: str,
        pattern_id: str,
        technology: str = "generic",
        phase_type: str = "generic",
    ) -> dict:
        return self._post(
            f"/api/teams/{agent_id}/{pattern_id}/retire",
            {"technology": technology, "phase_type": phase_type},
        )

    def teams_unretire(
        self,
        agent_id: str,
        pattern_id: str,
        technology: str = "generic",
        phase_type: str = "generic",
    ) -> dict:
        return self._post(
            f"/api/teams/{agent_id}/{pattern_id}/unretire",
            {"technology": technology, "phase_type": phase_type},
        )
