"""
Shared pytest configuration and fixtures for platform tests.
Supports: unit tests (TestClient), endurance/chaos tests (live httpx.Client).
"""
import os
import sys

import pytest

# Ensure platform package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Custom markers ────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "endurance: long-running endurance tests")
    config.addinivalue_line("markers", "chaos: chaos / fault-injection tests")
    config.addinivalue_line("markers", "live: tests that hit a live server (require --live)")


# ─── CLI option: --live ─────────────────────────────────────────

def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="run tests against live server")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="need --live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# ─── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def live_url():
    """Base URL for live-server tests."""
    return os.environ.get("BASE_URL", "http://4.233.64.30")


@pytest.fixture(scope="session")
def live_session(live_url):
    """httpx.Client pointed at the live server."""
    import httpx
    with httpx.Client(base_url=live_url, timeout=30.0) as session:
        yield session


@pytest.fixture(scope="session")
def canvas_project_id(live_session):
    """Create or find the 'macaron-canvas' project, return its id."""
    r = live_session.get("/api/projects")
    r.raise_for_status()
    for p in r.json():
        if p.get("id") == "macaron-canvas" or p.get("name") == "macaron-canvas":
            return p["id"]
    r = live_session.post("/api/projects", json={
        "id": "macaron-canvas",
        "name": "Macaron Canvas",
        "description": "Collaborative design tool — endurance test project",
    })
    r.raise_for_status()
    return "macaron-canvas"


@pytest.fixture(scope="module")
def client():
    """TestClient for the FastAPI app (non-live / unit tests)."""
    from fastapi.testclient import TestClient
    from platform.server import app
    with TestClient(app) as c:
        yield c
