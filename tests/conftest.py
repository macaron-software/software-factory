"""
Shared pytest configuration and fixtures for platform tests.
Supports: unit tests (TestClient), endurance/chaos tests (live httpx.Client).
"""

import os
import sys
import subprocess

import pytest

# Ensure platform package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Custom markers ────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line("markers", "endurance: long-running endurance tests")
    config.addinivalue_line("markers", "chaos: chaos / fault-injection tests")
    config.addinivalue_line(
        "markers", "live: tests that hit a live server (require --live)"
    )
    config.addinivalue_line(
        "markers",
        "stability: remote stability/stress tests (require STABILITY_TESTS=1)",
    )


# ─── CLI option: --live ─────────────────────────────────────────


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests against live server",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="need --live option to run")
    # Skip stability tests unless STABILITY_TESTS=1
    skip_stability = pytest.mark.skip(
        reason="set STABILITY_TESTS=1 to run remote stability tests"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
        if "stability" in item.keywords and not os.environ.get("STABILITY_TESTS"):
            item.add_marker(skip_stability)


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def live_url():
    """Base URL for live-server tests."""
    return os.environ.get("BASE_URL", "http://localhost:8090")


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
    r = live_session.post(
        "/api/projects",
        json={
            "id": "macaron-canvas",
            "name": "Macaron Canvas",
            "description": "Collaborative design tool — endurance test project",
        },
    )
    r.raise_for_status()
    return "macaron-canvas"


@pytest.fixture(scope="module")
def client():
    """TestClient for the FastAPI app (non-live / unit tests)."""
    from fastapi.testclient import TestClient
    from platform.server import app

    with TestClient(app) as c:
        yield c


# ─── Stability / Remote fixtures ────────────────────────────────


@pytest.fixture(scope="session")
def az_base_url():
    host = os.environ.get("STABILITY_AZ_HOST", "AZURE_VM_IP")
    return f"http://{host}"


@pytest.fixture(scope="session")
def ovh_base_url():
    host = os.environ.get("STABILITY_OVH_HOST", "sf.macaron-software.com")
    return f"https://{host}"


@pytest.fixture(scope="session")
def ssh_key_az():
    return os.environ.get(
        "STABILITY_SSH_AZ_KEY",
        os.path.expanduser("~/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"),
    )


@pytest.fixture(scope="session")
def ssh_key_ovh():
    return os.environ.get(
        "STABILITY_SSH_OVH_KEY",
        os.path.expanduser("~/.ssh/id_ed25519"),
    )


@pytest.fixture(scope="session")
def ssh_run_az(ssh_key_az):
    """Run a command on Azure VM and return stdout+stderr."""

    def _run(cmd: str, timeout: int = 30) -> str:
        full = (
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "
            f"-i {ssh_key_az} azureadmin@AZURE_VM_IP '{cmd}'"
        )
        try:
            r = subprocess.run(
                ["/bin/bash", "-c", full],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as exc:
            return str(exc)

    return _run


@pytest.fixture(scope="session")
def ssh_run_ovh(ssh_key_ovh):
    """Run a command on OVH demo server and return stdout+stderr."""

    def _run(cmd: str, timeout: int = 30) -> str:
        full = (
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "
            f"-i {ssh_key_ovh} debian@OVH_IP '{cmd}'"
        )
        try:
            r = subprocess.run(
                ["/bin/bash", "-c", full],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as exc:
            return str(exc)

    return _run
