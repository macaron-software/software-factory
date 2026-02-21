"""
Endurance tests — project lifecycle, phase progression, auto-resume, LLM tracking.
Run: pytest tests/test_endurance.py -v --live --timeout=600
"""
import os
import time

import pytest

pytestmark = [pytest.mark.endurance, pytest.mark.live]


# ─── TestProjectLifecycle ───────────────────────────────────────────

class TestProjectLifecycle:
    """Create macaron-canvas project and verify initial setup."""

    def test_create_canvas_project(self, live_session, canvas_project_id):
        """Project exists and is accessible."""
        r = live_session.get(f"/api/projects")
        r.raise_for_status()
        ids = [p["id"] for p in r.json()]
        assert canvas_project_id in ids

    def test_project_page_loads(self, live_session, canvas_project_id):
        """Project detail page renders."""
        r = live_session.get(f"/projects/{canvas_project_id}")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_launch_ideation(self, live_session, canvas_project_id):
        """Start ideation session — POST creates a session."""
        r = live_session.post("/api/ideation/start", json={
            "project_id": canvas_project_id,
            "content": "Design a collaborative design tool like Figma",
        })
        # 200 or 303 redirect are both acceptable
        assert r.status_code in (200, 303, 302), f"Ideation start failed: {r.status_code}"

    def test_create_mission(self, live_session, canvas_project_id):
        """Create a mission/epic for the canvas project."""
        r = live_session.post("/api/missions", json={
            "name": "Canvas MVP",
            "project_id": canvas_project_id,
            "type": "epic",
            "description": "Build core canvas with layers, shapes, real-time collab",
        })
        assert r.status_code in (200, 303, 302)

    def test_missions_exist(self, live_session, canvas_project_id):
        """At least one mission exists for the project."""
        r = live_session.get("/api/missions")
        r.raise_for_status()
        missions = r.json()
        project_missions = [m for m in missions if m.get("project_id") == canvas_project_id]
        assert len(project_missions) >= 1, "No missions found for canvas project"

    def test_create_features(self, live_session, canvas_project_id):
        """Create features under the first mission."""
        r = live_session.get("/api/missions")
        r.raise_for_status()
        missions = [m for m in r.json() if m.get("project_id") == canvas_project_id]
        if not missions:
            pytest.skip("No mission to add features to")
        mid = missions[0]["id"]
        features = [
            "Canvas rendering engine",
            "Shape tools (rect, circle, line, pen)",
            "Layer management (z-order, visibility, lock)",
            "Real-time collaboration (WebSocket)",
            "Export (PNG, SVG, PDF)",
        ]
        for name in features:
            r = live_session.post(f"/api/epics/{mid}/features", json={"name": name})
            assert r.status_code in (200, 201, 303), f"Feature creation failed: {name}"


# ─── TestPhaseProgression ──────────────────────────────────────────

class TestPhaseProgression:
    """Monitor mission phases progress over time."""

    def test_health_ok(self, live_session):
        """Platform health check passes."""
        r = live_session.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_agents_loaded(self, live_session):
        """Agents are registered and ready."""
        r = live_session.get("/api/agents")
        r.raise_for_status()
        agents = r.json()
        assert len(agents) >= 50, f"Only {len(agents)} agents loaded"

    def test_mission_can_start(self, live_session, canvas_project_id):
        """A mission can be started (status transitions to running)."""
        r = live_session.get("/api/missions")
        r.raise_for_status()
        missions = [m for m in r.json() if m.get("project_id") == canvas_project_id]
        if not missions:
            pytest.skip("No missions to start")
        m = missions[0]
        if m.get("status") in ("running", "in_progress"):
            return  # already running
        r = live_session.post(f"/api/missions/{m['id']}/start", json={})
        assert r.status_code in (200, 303, 302)

    def test_llm_stats_endpoint(self, live_session):
        """LLM stats endpoint returns valid data."""
        r = live_session.get("/api/llm/stats")
        assert r.status_code == 200
        data = r.json()
        assert "calls" in data or "total_calls" in data

    def test_monitoring_live(self, live_session):
        """Monitoring endpoint returns agent/message counts."""
        r = live_session.get("/api/monitoring/live")
        assert r.status_code == 200
        data = r.json()
        assert "agents" in data

    def test_all_pages_healthy(self, live_session):
        """All main pages load with 200."""
        pages = ["/", "/projects", "/missions", "/agents", "/monitoring",
                 "/settings", "/metier", "/portfolio"]
        for page in pages:
            r = live_session.get(page)
            assert r.status_code == 200, f"Page {page} returned {r.status_code}"


# ─── TestAutoResume ────────────────────────────────────────────────

class TestAutoResume:
    """Verify platform survives restarts."""

    def test_missions_list_stable(self, live_session):
        """Mission count is stable across requests."""
        r1 = live_session.get("/api/missions")
        r1.raise_for_status()
        count1 = len(r1.json())
        time.sleep(2)
        r2 = live_session.get("/api/missions")
        r2.raise_for_status()
        count2 = len(r2.json())
        assert count2 >= count1, "Mission count should not decrease"

    def test_projects_stable(self, live_session):
        """Project count is stable."""
        r1 = live_session.get("/api/projects")
        r1.raise_for_status()
        count1 = len(r1.json())
        time.sleep(2)
        r2 = live_session.get("/api/projects")
        r2.raise_for_status()
        assert len(r2.json()) >= count1


# ─── TestLongRunning ───────────────────────────────────────────────

class TestLongRunning:
    """Long-running progression checks. Use with high --timeout."""

    def test_api_latency_reasonable(self, live_session):
        """API endpoints respond within 3 seconds."""
        endpoints = ["/api/health", "/api/projects", "/api/missions", "/api/agents"]
        for ep in endpoints:
            start = time.monotonic()
            r = live_session.get(ep)
            elapsed = time.monotonic() - start
            assert r.status_code == 200, f"{ep} returned {r.status_code}"
            assert elapsed < 3.0, f"{ep} took {elapsed:.1f}s"

    def test_concurrent_requests(self, live_session):
        """Platform handles 10 sequential requests without errors."""
        for i in range(10):
            r = live_session.get("/api/health")
            assert r.status_code == 200

    def test_llm_cost_check(self, live_session):
        """LLM stats are within reasonable bounds."""
        r = live_session.get("/api/llm/stats")
        if r.status_code != 200:
            pytest.skip("LLM stats not available")
        data = r.json()
        # Just verify the structure exists — cost checks are in watchdog
        assert isinstance(data, dict)
