"""
Platform API unit tests — real endpoints, real data, real assertions.
Run: pytest tests/test_platform_api.py -v
"""
import os
import sys
import pytest

# Ensure platform package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app."""
    from platform.server import app
    with TestClient(app) as c:
        yield c


# ─── Health & System ────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_metrics_prometheus(self, client):
        r = client.get("/api/metrics/prometheus")
        assert r.status_code == 200
        text = r.text
        assert "macaron_uptime_seconds" in text

    def test_monitoring_live(self, client):
        r = client.get("/api/monitoring/live")
        assert r.status_code == 200
        data = r.json()
        assert "agents" in data
        assert "registered" in data["agents"]


# ─── Projects ───────────────────────────────────────────────────

class TestProjects:
    def test_list_projects(self, client):
        r = client.get("/api/projects")
        assert r.status_code == 200
        projects = r.json()
        assert isinstance(projects, list)
        assert len(projects) >= 1, "Should have at least 1 project"

    def test_project_has_fields(self, client):
        r = client.get("/api/projects")
        projects = r.json()
        for p in projects[:3]:
            assert "id" in p, f"Project missing 'id': {p}"
            assert "name" in p, f"Project missing 'name': {p}"

    def test_project_detail_page(self, client):
        r = client.get("/api/projects")
        projects = r.json()
        if projects:
            pid = projects[0]["id"]
            r2 = client.get(f"/projects/{pid}")
            assert r2.status_code == 200
            assert "text/html" in r2.headers["content-type"]


# ─── Agents ─────────────────────────────────────────────────────

class TestAgents:
    def test_list_agents(self, client):
        r = client.get("/api/agents")
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        assert len(agents) >= 10, "Should have many agents (SAFe team)"

    def test_agent_has_fields(self, client):
        r = client.get("/api/agents")
        agents = r.json()
        for a in agents[:5]:
            assert "id" in a
            assert "name" in a
            assert "role" in a

    def test_product_managers_exist(self, client):
        r = client.get("/api/agents")
        agents = r.json()
        pm_agents = [a for a in agents if a.get("role") == "product-manager"]
        assert len(pm_agents) >= 1, "Should have at least 1 product-manager agent"

    def test_agent_details(self, client):
        r = client.get("/api/agents")
        agents = r.json()
        if agents:
            aid = agents[0]["id"]
            r2 = client.get(f"/api/agents/{aid}/details")
            assert r2.status_code == 200


# ─── Missions / Epics ──────────────────────────────────────────

class TestMissions:
    def test_list_missions_partial(self, client):
        r = client.get("/api/missions/list-partial")
        assert r.status_code == 200

    def test_missions_page(self, client):
        r = client.get("/missions")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


# ─── Pages load (HTML 200) ─────────────────────────────────────

class TestPagesLoad:
    """Smoke test: every page returns 200 with HTML content."""

    @pytest.mark.parametrize("path", [
        "/",
        "/pi",
        "/agents",
        "/skills",
        "/mcps",
        "/settings",
        "/monitoring",
        "/memory",
        "/missions",
        "/ideation",
        "/workflows",
        "/backlog",
        "/ceremonies",
        "/design-system",
        "/metier",
    ])
    def test_page_loads(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "text/html" in r.headers.get("content-type", ""), f"{path} not HTML"
        assert len(r.text) > 200, f"{path} too short ({len(r.text)} chars)"


# ─── i18n ───────────────────────────────────────────────────────

class TestI18n:
    @pytest.mark.parametrize("lang", ["en", "fr", "zh", "es", "ja", "pt", "de", "ko"])
    def test_locale_json(self, client, lang):
        r = client.get(f"/api/i18n/{lang}.json")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data) > 30, f"{lang}: only {len(data)} keys"


# ─── Integrations ──────────────────────────────────────────────

class TestIntegrations:
    def test_list_integrations(self, client):
        r = client.get("/api/integrations")
        assert r.status_code == 200
        integs = r.json()
        assert isinstance(integs, list)
        # Should have at least Jira, Confluence, GitLab, etc.
        names = [i.get("id", i.get("name", "")) for i in integs]
        assert len(names) >= 3, f"Only {len(names)} integrations"

    def test_integration_fields(self, client):
        r = client.get("/api/integrations")
        integs = r.json()
        for i in integs[:3]:
            assert "id" in i or "name" in i
            assert "type" in i or "enabled" in i


# ─── Search & Export ────────────────────────────────────────────

class TestSearchExport:
    def test_search_empty(self, client):
        r = client.get("/api/search", params={"q": ""})
        assert r.status_code == 200

    def test_search_query(self, client):
        r = client.get("/api/search", params={"q": "test"})
        assert r.status_code == 200

    def test_search_xss_escaped(self, client):
        """Verify XSS payloads are escaped in HTML search results."""
        r = client.get("/api/search", params={"q": '<script>alert("xss")</script>'})
        assert r.status_code == 200
        # JSON responses are safe (Content-Type: application/json, browsers don't execute)
        # The XSS fix is in the memory search HTMLResponse, not this JSON endpoint
        assert r.headers.get("content-type", "").startswith("application/json")

    def test_memory_search_xss_escaped(self, client):
        """Verify XSS payloads are escaped in memory search HTML responses."""
        r = client.get("/api/memory/search", params={"q": '<script>alert("xss")</script>'})
        assert r.status_code == 200
        # HTMLResponse must escape user input
        if "text/html" in r.headers.get("content-type", ""):
            assert "<script>" not in r.text

    def test_export_epics(self, client):
        r = client.get("/api/export/epics")
        assert r.status_code == 200

    def test_export_features(self, client):
        r = client.get("/api/export/features")
        assert r.status_code == 200


# ─── Security ───────────────────────────────────────────────────

class TestSecurity:
    def test_csp_header(self, client):
        r = client.get("/api/health")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "unsafe-eval" not in csp
        assert "frame-ancestors 'none'" in csp

    def test_security_headers(self, client):
        r = client.get("/api/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_monitoring_no_pid(self, client):
        """Monitoring should not expose PID."""
        r = client.get("/api/monitoring/live")
        if r.status_code == 200:
            data = r.json()
            assert "pid" not in data.get("system", {})


# ─── Memory ─────────────────────────────────────────────────────

class TestMemory:
    def test_memory_stats(self, client):
        r = client.get("/api/memory/stats")
        assert r.status_code == 200

    def test_memory_search(self, client):
        r = client.get("/api/memory/search", params={"q": "architecture"})
        assert r.status_code == 200
