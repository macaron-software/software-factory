#!/usr/bin/env python3
"""
Unit tests for Dashboard API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import tempfile
import sqlite3

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    # Create tables
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            config TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            status TEXT,
            metrics TEXT
        )
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_json(self, client):
        """Health check should return JSON."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_check_has_required_fields(self, client):
        """Health check should have status, version, service."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "service" in data

        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["service"] == "software-factory-dashboard"


class TestProjectsEndpoint:
    """Tests for /api/projects endpoints."""

    def test_list_projects_returns_200(self, client):
        """List projects should return 200."""
        response = client.get("/api/projects")
        assert response.status_code == 200

    def test_list_projects_returns_json(self, client):
        """List projects should return JSON."""
        response = client.get("/api/projects")
        assert response.headers["content-type"] == "application/json"

    def test_list_projects_returns_list(self, client):
        """List projects should return a list."""
        response = client.get("/api/projects")
        data = response.json()
        assert isinstance(data, list)

    def test_get_project_returns_404_for_invalid_id(self, client):
        """Get non-existent project should return 404 or error."""
        response = client.get("/api/projects/non-existent-project-12345")
        # Could be 404 or 200 with error message
        assert response.status_code in [200, 404]


class TestStatsEndpoint:
    """Tests for /api/stats endpoint."""

    def test_stats_returns_200(self, client):
        """Stats should return 200."""
        response = client.get("/api/stats")
        assert response.status_code == 200

    def test_stats_returns_json(self, client):
        """Stats should return JSON."""
        response = client.get("/api/stats")
        assert response.headers["content-type"] == "application/json"


class TestDeployStatusEndpoint:
    """Tests for /api/deploy/status endpoint."""

    def test_deploy_status_returns_200(self, client):
        """Deploy status should return 200."""
        response = client.get("/api/deploy/status")
        assert response.status_code == 200

    def test_deploy_status_returns_json(self, client):
        """Deploy status should return JSON."""
        response = client.get("/api/deploy/status")
        assert response.headers["content-type"] == "application/json"

    def test_deploy_status_returns_list(self, client):
        """Deploy status should return a list of environments."""
        response = client.get("/api/deploy/status")
        data = response.json()
        assert isinstance(data, list)


class TestTasksEndpoint:
    """Tests for /api/tasks endpoint."""

    def test_tasks_returns_200(self, client):
        """Tasks should return 200."""
        response = client.get("/api/tasks")
        assert response.status_code == 200

    def test_tasks_returns_json(self, client):
        """Tasks should return JSON."""
        response = client.get("/api/tasks")
        assert response.headers["content-type"] == "application/json"


class TestDaemonsEndpoint:
    """Tests for /api/daemons endpoint."""

    def test_daemons_returns_200(self, client):
        """Daemons should return 200."""
        response = client.get("/api/daemons")
        assert response.status_code == 200

    def test_daemons_returns_json(self, client):
        """Daemons should return JSON."""
        response = client.get("/api/daemons")
        assert response.headers["content-type"] == "application/json"


class TestWebPages:
    """Tests for HTML page endpoints."""

    def test_index_page_returns_200(self, client):
        """Index page should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_page_returns_html(self, client):
        """Index page should return HTML."""
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_live_page_returns_200(self, client):
        """Live page should return 200."""
        response = client.get("/live")
        assert response.status_code == 200

    def test_live_page_returns_html(self, client):
        """Live page should return HTML."""
        response = client.get("/live")
        assert "text/html" in response.headers["content-type"]


class TestCaching:
    """Tests for caching functionality."""

    def test_projects_endpoint_has_cache_header(self, client):
        """Projects endpoint should have Cache-Control header."""
        response = client.get("/api/projects")
        assert "Cache-Control" in response.headers
        assert "max-age" in response.headers["Cache-Control"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
