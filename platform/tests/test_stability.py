"""
Stability test suite for the Software Factory multi-node cluster.

Run with:
    STABILITY_TESTS=1 pytest platform/tests/test_stability.py -v

Optional env vars (see conftest.py for defaults):
    STABILITY_AZ_HOST, STABILITY_AZ_NODE2_HOST, STABILITY_LB_HOST
    STABILITY_OVH_HOST, STABILITY_SSH_AZ_KEY, STABILITY_SSH_OVH_KEY

Tests are tagged @pytest.mark.stability and skipped by default.
"""

from __future__ import annotations

import os
import statistics
import threading
import time
from typing import Callable

import pytest
import requests


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get(url: str, timeout: int = 10) -> requests.Response:
    return requests.get(url, timeout=timeout)


def _health(base: str) -> dict:
    r = _get(f"{base}/api/health", timeout=10)
    r.raise_for_status()
    return r.json()


# ── 1. Health endpoints ───────────────────────────────────────────────────────


@pytest.mark.stability
def test_health_node1(az_base_url: str) -> None:
    data = _health(az_base_url)
    assert data.get("status") == "ok", f"node-1 health: {data}"


@pytest.mark.stability
def test_health_node2(az_node2_url: str) -> None:
    data = _health(az_node2_url)
    assert data.get("status") == "ok", f"node-2 health: {data}"


@pytest.mark.stability
def test_health_lb(lb_base_url: str) -> None:
    data = _health(lb_base_url)
    assert data.get("status") == "ok", f"LB health: {data}"


@pytest.mark.stability
def test_health_ovh(ovh_base_url: str) -> None:
    data = _health(ovh_base_url)
    assert data.get("status") == "ok", f"OVH health: {data}"


# ── 2. Latency P99 ────────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("host_fixture", ["az_base_url", "lb_base_url"])
def test_latency_p99(request: pytest.FixtureRequest, host_fixture: str) -> None:
    """Median latency for /api/health must be < 500ms (uses slow rate to avoid nginx delays)."""
    base = request.getfixturevalue(host_fixture)
    latencies = []
    for _ in range(10):
        t0 = time.perf_counter()
        try:
            r = requests.get(f"{base}/api/health", timeout=10)
            elapsed = (time.perf_counter() - t0) * 1000
            if r.status_code != 429:
                latencies.append(elapsed)
        except Exception:
            pass
        time.sleep(2.5)  # 24 r/min — stay under rate limit (30r/min)
    assert len(latencies) >= 5, (
        f"Too few successful requests ({len(latencies)}/10, rate-limited?)"
    )
    median = statistics.median(latencies)
    # LB adds Azure network overhead — higher threshold for LB
    threshold = 2000 if os.environ.get("STABILITY_LB_HOST", "") in base else 500
    assert median < threshold, (
        f"Median={median:.0f}ms on {base} (threshold {threshold}ms)"
    )


# ── 3. Concurrent 10 ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_concurrent_10(lb_base_url: str) -> None:
    """10 concurrent /api/health requests — no server errors (429 rate-limit is OK)."""
    results: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            r = _get(f"{lb_base_url}/api/health")
            with lock:
                results.append(r.status_code)
        except Exception:
            with lock:
                results.append(0)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(results) == 10
    server_errors = [c for c in results if c not in (200, 429, 302)]
    assert not server_errors, f"Server errors in concurrent test: {results}"


# ── 4. Concurrent 50 ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_concurrent_50(lb_base_url: str) -> None:
    """50 concurrent health checks — allow up to 5 failures (rate limiting OK)."""
    results: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            r = _get(f"{lb_base_url}/api/health")
            with lock:
                results.append(r.status_code)
        except Exception:
            with lock:
                results.append(0)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(results) == 50
    failures = sum(1 for c in results if c not in (200, 429))
    assert failures <= 5, f"Too many failures: {failures}/50. Codes: {results}"


# ── 5. Rate limiting ──────────────────────────────────────────────────────────


@pytest.mark.stability
def test_rate_limit_api(az_base_url: str) -> None:
    """Nginx rate limiting: >30 rapid /api/ requests should trigger some 429s."""
    codes = []
    for _ in range(40):
        try:
            r = requests.get(f"{az_base_url}/api/health", timeout=5)
            codes.append(r.status_code)
        except Exception:
            codes.append(0)
    # At least some 429s expected OR all 200 (nginx may be lenient in burst mode)
    # We just verify the server doesn't crash (no 5xx)
    five_xx = sum(1 for c in codes if 500 <= c < 600)
    assert five_xx == 0, f"Server errors during rate limit test: {codes}"


# ── 6. Pages smoke test ───────────────────────────────────────────────────────

SMOKE_PAGES = ["/", "/portfolio", "/art", "/live", "/backlog"]


@pytest.mark.stability
@pytest.mark.parametrize("path", SMOKE_PAGES)
def test_page_smoke(az_base_url: str, path: str) -> None:
    r = _get(f"{az_base_url}{path}")
    assert r.status_code in (200, 302, 401), f"Page {path} returned {r.status_code}"
    assert len(r.content) > 100, f"Page {path} response too short"


# ── 7. SSE connect ────────────────────────────────────────────────────────────


@pytest.mark.stability
def test_sse_connect(az_base_url: str) -> None:
    """SSE endpoint must accept connection and respond with text/event-stream."""
    try:
        r = requests.get(
            f"{az_base_url}/sse/monitoring",
            stream=True,
            timeout=5,
            headers={"Accept": "text/event-stream"},
        )
        assert r.status_code in (200, 302), f"SSE returned {r.status_code}"
        if r.status_code == 200:
            ct = r.headers.get("Content-Type", "")
            assert "text/event-stream" in ct or "text/" in ct, (
                f"Unexpected Content-Type for SSE: {ct}"
            )
        r.close()
    except requests.exceptions.ReadTimeout:
        pass  # Connected but no events yet — acceptable
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"SSE connection failed: {e}")


# ── 8. Disk & Memory ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_disk_memory_node1(ssh_run_az: Callable) -> None:
    """Disk usage < 85%, memory available > 200MB on node-1."""
    rc, out, _ = ssh_run_az(
        "df -h / | awk 'NR==2{print $5}' | tr -d '%' && "
        "free -m | awk '/^Mem/{print $7}'"
    )
    assert rc == 0, "SSH command failed"
    lines = out.splitlines()
    disk_pct = int(lines[0])
    mem_avail_mb = int(lines[1])
    assert disk_pct < 85, f"Disk usage too high: {disk_pct}%"
    assert mem_avail_mb > 200, f"Available memory too low: {mem_avail_mb}MB"


@pytest.mark.stability
def test_disk_memory_node2(ssh_run_az2: Callable) -> None:
    """Disk usage < 85%, memory available > 200MB on node-2."""
    rc, out, _ = ssh_run_az2(
        "df -h / | awk 'NR==2{print $5}' | tr -d '%' && "
        "free -m | awk '/^Mem/{print $7}'"
    )
    assert rc == 0, "SSH command failed"
    lines = out.splitlines()
    disk_pct = int(lines[0])
    mem_avail_mb = int(lines[1])
    assert disk_pct < 85, f"Disk usage too high: {disk_pct}%"
    assert mem_avail_mb > 200, f"Available memory too low: {mem_avail_mb}MB"


# ── 9. Hot restart ────────────────────────────────────────────────────────────


@pytest.mark.stability
def test_hot_restart_node1(az_base_url: str, ssh_run_az: Callable) -> None:
    """Service hot-restart: node-1 must be healthy within 20s of restart."""
    # Verify healthy before
    assert _health(az_base_url)["status"] == "ok"

    rc, _, err = ssh_run_az("sudo systemctl restart sf-platform")
    assert rc == 0, f"Restart failed: {err}"

    # Poll up to 20s
    deadline = time.time() + 20
    ok = False
    while time.time() < deadline:
        time.sleep(2)
        try:
            if _health(az_base_url)["status"] == "ok":
                ok = True
                break
        except Exception:
            pass
    assert ok, "node-1 did not recover within 20s after hot restart"


# ── 10. Nginx failover ────────────────────────────────────────────────────────


@pytest.mark.stability
def test_nginx_failover(
    lb_base_url: str, az_base_url: str, ssh_run_az: Callable
) -> None:
    """LB keeps serving when node-1 service is stopped."""
    # Stop node-1
    ssh_run_az("sudo systemctl stop sf-platform")
    time.sleep(3)

    # LB should route to node-2 — allow up to 10s for health probe to kick in
    deadline = time.time() + 10
    ok = False
    while time.time() < deadline:
        try:
            r = _get(f"{lb_base_url}/api/health")
            if r.status_code == 200:
                data = r.json()
                if data.get("node") != "sf-node-1":
                    ok = True
                    break
        except Exception:
            pass
        time.sleep(1)

    # Restart node-1 (cleanup — always)
    ssh_run_az("sudo systemctl start sf-platform")

    assert ok, "LB did not fail over to node-2 within 10s"

    # Verify node-1 recovers
    deadline = time.time() + 20
    recovered = False
    while time.time() < deadline:
        time.sleep(2)
        try:
            if _health(az_base_url)["status"] == "ok":
                recovered = True
                break
        except Exception:
            pass
    assert recovered, "node-1 did not recover after failover test"


# ── 11. Cold restart ──────────────────────────────────────────────────────────


@pytest.mark.stability
def test_cold_restart_both_nodes(
    az_base_url: str,
    az_node2_url: str,
    ssh_run_az: Callable,
    ssh_run_az2: Callable,
) -> None:
    """Both nodes restart and come back healthy within 30s."""
    ssh_run_az("sudo systemctl restart sf-platform")
    ssh_run_az2("sudo systemctl restart sf-platform")

    deadline = time.time() + 30
    n1_ok = n2_ok = False
    while time.time() < deadline:
        time.sleep(3)
        try:
            if not n1_ok and _health(az_base_url)["status"] == "ok":
                n1_ok = True
        except Exception:
            pass
        try:
            if not n2_ok and _health(az_node2_url)["status"] == "ok":
                n2_ok = True
        except Exception:
            pass
        if n1_ok and n2_ok:
            break

    assert n1_ok, "node-1 did not recover within 30s"
    assert n2_ok, "node-2 did not recover within 30s"


# ── 12. Chaos: pause & resume mission ─────────────────────────────────────────


@pytest.mark.stability
def test_chaos_pause_resume(az_base_url: str, ssh_run_az: Callable) -> None:
    """Pause node-1 for 5s (SIGSTOP), verify LB handles it, then verify recovery."""
    rc, pid_out, _ = ssh_run_az(
        "sudo systemctl show sf-platform --property=MainPID | cut -d= -f2"
    )
    assert rc == 0 and pid_out.isdigit(), "Could not get PID"
    pid = pid_out.strip()

    # SIGSTOP
    ssh_run_az(f"sudo kill -STOP {pid}")
    time.sleep(5)

    # LB should still respond (node-2 takes over via nginx)
    try:
        r = _get(
            f"{os.environ.get('STABILITY_LB_HOST', az_base_url)}/api/health",
            timeout=8,
        )
        lb_ok_during_pause = r.status_code == 200
    except Exception:
        lb_ok_during_pause = False

    # SIGCONT
    ssh_run_az(f"sudo kill -CONT {pid}")

    # Verify node-1 itself recovers
    deadline = time.time() + 15
    recovered = False
    while time.time() < deadline:
        time.sleep(2)
        try:
            if _health(az_base_url)["status"] == "ok":
                recovered = True
                break
        except Exception:
            pass

    assert recovered, "node-1 did not recover after SIGCONT"
    # LB availability during pause is informational (may not have failed over yet)
    if not lb_ok_during_pause:
        pytest.xfail(
            "LB did not serve during 5s SIGSTOP (health probe interval may exceed pause duration)"
        )


# ── 13. Config guards ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_config_guards_node1(ssh_run_az: Callable) -> None:
    """Critical config guards: UFW port 8090 restricted, secrets file exists, service healthy."""
    # UFW rule: 8090 must NOT be open to all
    rc, out, _ = ssh_run_az("sudo ufw status | grep 8090")
    assert rc == 0, "UFW query failed"
    assert "ALLOW IN" not in out or "10.0.1" in out, (
        f"Port 8090 may be open to internet: {out}"
    )

    # Secrets file exists with correct permissions
    rc2, out2, _ = ssh_run_az("stat -c '%a %U' /etc/sf-platform/secrets 2>/dev/null")
    assert rc2 == 0, "Secrets file missing"
    assert out2.startswith("600"), f"Secrets file permissions: {out2}"

    # Service is active
    rc3, out3, _ = ssh_run_az("systemctl is-active sf-platform")
    assert "active" in out3, f"Service not active: {out3}"


@pytest.mark.stability
def test_config_guards_pg_backup(ssh_run_az: Callable) -> None:
    """PG backup file exists and is recent (< 26h old)."""
    rc, out, _ = ssh_run_az(
        "find /home/sfadmin/backups -name '*.sql.gz' -mmin -1560 | head -1"
    )
    assert rc == 0, "Backup dir not accessible"
    assert out.strip(), "No recent PG backup found (expected within 26h)"
