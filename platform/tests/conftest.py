"""
Pytest configuration for platform tests.

Stability tests require STABILITY_TESTS=1 env var + optional host/SSH vars:
  STABILITY_AZ_HOST      — Azure SF node-1 base URL
  STABILITY_OVH_HOST     — OVH demo base URL (default: https://sf.macaron-software.com)
  STABILITY_LB_HOST      — Azure LB public IP
  STABILITY_SSH_AZ_KEY   — path to SSH private key for Azure nodes
  STABILITY_SSH_OVH_KEY  — path to SSH private key for OVH
"""
# Ref: feat-quality

from __future__ import annotations

import os
import subprocess

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "stability: end-to-end stability tests (set STABILITY_TESTS=1 to enable)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get("STABILITY_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="STABILITY_TESTS=1 not set")
    for item in items:
        if "stability" in item.keywords:
            item.add_marker(skip)


# ── Base URLs ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def az_base_url() -> str:
    return os.environ.get("STABILITY_AZ_HOST", "").rstrip("/")


@pytest.fixture(scope="session")
def az_node2_url() -> str:
    return os.environ.get("STABILITY_AZ_NODE2_HOST", "").rstrip("/")


@pytest.fixture(scope="session")
def lb_base_url() -> str:
    return os.environ.get("STABILITY_LB_HOST", "").rstrip("/")


@pytest.fixture(scope="session")
def ovh_base_url() -> str:
    return os.environ.get(
        "STABILITY_OVH_HOST", "https://sf.macaron-software.com"
    ).rstrip("/")


# ── SSH helpers ───────────────────────────────────────────────────────────────


def _ssh_run(host: str, cmd: str, key: str | None) -> tuple[int, str, str]:
    """Run a command on a remote host via SSH. Returns (returncode, stdout, stderr)."""
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    if key:
        ssh_cmd += ["-i", key]
    ssh_cmd += [host, cmd]
    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


@pytest.fixture(scope="session")
def ssh_key_az() -> str | None:
    return os.environ.get("STABILITY_SSH_AZ_KEY") or os.path.expanduser(
        "~/.ssh/sf_innovation_ed25519"
    )


@pytest.fixture(scope="session")
def ssh_key_ovh() -> str | None:
    return os.environ.get("STABILITY_SSH_OVH_KEY")


@pytest.fixture(scope="session")
def ssh_run_az(ssh_key_az: str | None):
    """Run a command on sf-node-1 (Azure). Returns (rc, stdout, stderr)."""

    def _run(cmd: str) -> tuple[int, str, str]:
        return _ssh_run(os.environ.get("AZ_NODE1_SSH_HOST", ""), cmd, ssh_key_az)

    return _run


@pytest.fixture(scope="session")
def ssh_run_az2(ssh_key_az: str | None):
    """Run a command on sf-node-2 (Azure). Returns (rc, stdout, stderr)."""

    def _run(cmd: str) -> tuple[int, str, str]:
        return _ssh_run(os.environ.get("AZ_NODE2_SSH_HOST", ""), cmd, ssh_key_az)

    return _run


@pytest.fixture(scope="session")
def ssh_run_ovh(ssh_key_ovh: str | None):
    """Run a command on OVH demo server. Returns (rc, stdout, stderr)."""

    def _run(cmd: str) -> tuple[int, str, str]:
        return _ssh_run(os.environ.get("OVH_SSH_HOST", ""), cmd, ssh_key_ovh)

    return _run
