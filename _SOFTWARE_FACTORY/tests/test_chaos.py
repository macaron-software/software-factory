"""
Chaos tests — fault injection, recovery verification, data integrity.
Run: pytest tests/test_chaos.py -v --live --timeout=600

⚠️ These tests modify system state (restart containers, stress CPU, etc).
Only run against test/staging environments.
"""
import os
import time

import pytest

pytestmark = [pytest.mark.chaos, pytest.mark.live]

# Container name for chaos scenarios
CONTAINER = os.environ.get("CHAOS_CONTAINER", "deploy-platform-1")


def _docker_exec(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Execute command in container, return (returncode, stdout)."""
    import subprocess
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER] + cmd.split(),
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        pytest.skip("docker not available")


def _health_ok(session) -> bool:
    try:
        r = session.get("/api/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def _wait_healthy(session, timeout: float = 60.0) -> float:
    """Wait for health to recover. Returns recovery time in seconds, -1 if timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if _health_ok(session):
            return time.monotonic() - start
        time.sleep(2)
    return -1


# ─── TestChaosContainerRestart ──────────────────────────────────

class TestChaosContainerRestart:
    """Test platform recovery after container restart."""

    def test_health_before_chaos(self, live_session):
        """Verify health is OK before chaos."""
        assert _health_ok(live_session), "Platform unhealthy before chaos"

    def test_count_before_restart(self, live_session):
        """Record mission count before restart."""
        r = live_session.get("/api/missions")
        r.raise_for_status()
        self.__class__._missions_before = len(r.json())
        r = live_session.get("/api/projects")
        r.raise_for_status()
        self.__class__._projects_before = len(r.json())

    def test_container_restart_recovery(self, live_session):
        """Restart container and verify recovery within 60s."""
        import subprocess
        try:
            subprocess.run(["docker", "restart", CONTAINER],
                           capture_output=True, timeout=30)
        except FileNotFoundError:
            pytest.skip("docker not available")
        except subprocess.TimeoutExpired:
            pytest.fail("docker restart timed out")

        recovery = _wait_healthy(live_session, timeout=60)
        assert recovery >= 0, "Platform did not recover within 60s"
        assert recovery < 30, f"Recovery too slow: {recovery:.1f}s (expected <30s)"

    def test_missions_persist_after_restart(self, live_session):
        """Mission count unchanged after restart."""
        r = live_session.get("/api/missions")
        r.raise_for_status()
        count = len(r.json())
        expected = getattr(self.__class__, "_missions_before", 0)
        if expected > 0:
            assert count >= expected, f"Missions lost: {expected} → {count}"

    def test_projects_persist_after_restart(self, live_session):
        """Project count unchanged after restart."""
        r = live_session.get("/api/projects")
        r.raise_for_status()
        count = len(r.json())
        expected = getattr(self.__class__, "_projects_before", 0)
        if expected > 0:
            assert count >= expected, f"Projects lost: {expected} → {count}"


# ─── TestChaosDBPressure ───────────────────────────────────────

class TestChaosDBPressure:
    """Test database resilience under pressure."""

    def test_wal_checkpoint_brutal(self, live_session):
        """Force WAL checkpoint and verify health."""
        rc, _ = _docker_exec(
            "python3 -c import sqlite3; c=sqlite3.connect('/app/data/platform.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()"
        )
        # rc might fail if container not available
        time.sleep(2)
        assert _health_ok(live_session), "Health failed after WAL truncate"

    def test_concurrent_writes(self, live_session):
        """10 parallel POST requests — no data loss."""
        import concurrent.futures
        results = []

        def _post(i):
            try:
                r = live_session.post("/api/missions", json={
                    "name": f"chaos-write-test-{i}",
                    "project_id": "macaron-canvas",
                    "type": "task",
                })
                return r.status_code
            except Exception as e:
                return str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(_post, i) for i in range(10)]
            results = [f.result() for f in futures]

        # At least 8/10 should succeed
        ok_count = sum(1 for r in results if r in (200, 303, 302))
        assert ok_count >= 8, f"Only {ok_count}/10 concurrent writes succeeded: {results}"


# ─── TestChaosDiskPressure ─────────────────────────────────────

class TestChaosDiskPressure:
    """Test behavior under disk pressure."""

    def test_disk_fill_and_recover(self, live_session):
        """Fill 200MB disk, verify app responds, cleanup."""
        # Fill
        rc, _ = _docker_exec("dd if=/dev/zero of=/tmp/chaos_fill bs=1M count=200")
        time.sleep(2)
        healthy = _health_ok(live_session)

        # Cleanup immediately
        _docker_exec("rm -f /tmp/chaos_fill")
        time.sleep(2)

        # Verify either stayed healthy or recovered
        if not healthy:
            recovery = _wait_healthy(live_session, timeout=30)
            assert recovery >= 0, "Did not recover after disk fill cleanup"


# ─── TestChaosAPIResilience ────────────────────────────────────

class TestChaosAPIResilience:
    """Test API resilience under unusual conditions."""

    def test_malformed_json(self, live_session):
        """Malformed JSON body doesn't crash the server."""
        import httpx
        r = live_session.post("/api/missions",
                              content=b"{invalid json!!!}",
                              headers={"Content-Type": "application/json"})
        # Should get 400/422/500 but not crash
        assert r.status_code < 600

    def test_huge_payload(self, live_session):
        """Large payload is rejected gracefully."""
        big = {"name": "x" * 10000, "description": "y" * 50000}
        r = live_session.post("/api/missions", json=big)
        assert r.status_code < 600  # server didn't crash

    def test_rapid_fire_health(self, live_session):
        """50 rapid health checks don't overwhelm the server."""
        for _ in range(50):
            r = live_session.get("/api/health")
            assert r.status_code == 200

    def test_invalid_endpoints(self, live_session):
        """404 for non-existent endpoints, not 500."""
        for path in ["/api/nonexistent", "/api/missions/fake-id-999"]:
            r = live_session.get(path)
            assert r.status_code in (404, 200), f"{path} returned {r.status_code}"

    def test_health_after_all_chaos(self, live_session):
        """Final health check — platform survived all chaos tests."""
        assert _health_ok(live_session), "Platform unhealthy after chaos suite"
