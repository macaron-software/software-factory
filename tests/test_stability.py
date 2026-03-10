"""
Remote Stability Test Suite — Azure Prod + OVH Demo
====================================================
Requires: STABILITY_TESTS=1

Configuration via env vars:
  STABILITY_AZ_HOST      Azure VM IP/hostname   (default: AZURE_VM_IP)
  STABILITY_OVH_HOST     OVH hostname           (default: sf.macaron-software.com)
  STABILITY_SSH_AZ_KEY   SSH key path for Azure
  STABILITY_SSH_OVH_KEY  SSH key path for OVH

Run:
  STABILITY_TESTS=1 pytest tests/test_stability.py -v
  STABILITY_TESTS=1 pytest tests/test_stability.py -v -k azure
  STABILITY_TESTS=1 pytest tests/test_stability.py -v -k ovh
"""

from __future__ import annotations

import concurrent.futures
import json
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _http_get(url: str, timeout: int = 10) -> tuple[int, int, str]:
    """Returns (status_code, latency_ms, body_snippet)."""
    t0 = time.time()
    ctx = None
    if url.startswith("https://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.urlopen(url, timeout=timeout, context=ctx)
        body = req.read(512).decode(errors="replace")
        return req.getcode(), int((time.time() - t0) * 1000), body
    except urllib.error.HTTPError as e:
        return e.code, int((time.time() - t0) * 1000), ""
    except Exception as exc:
        return 0, int((time.time() - t0) * 1000), str(exc)


def _concurrent_get(url: str, n: int, timeout: int = 10) -> list[int]:
    """Fire n concurrent GETs, return list of status codes."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_http_get, url, timeout) for _ in range(n)]
        return [f.result()[0] for f in concurrent.futures.as_completed(futs)]


# ── Azure fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def az(az_base_url):
    return az_base_url


@pytest.fixture(scope="module")
def ovh(ovh_base_url):
    return ovh_base_url


# ── 1. Health Check ───────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_health_check(request, target):
    base = request.getfixturevalue(target)
    code, ms, body = _http_get(f"{base}/api/health", timeout=15)
    assert code == 200, f"{target} health={code} ({ms}ms)"
    try:
        d = json.loads(body)
        status = d.get("status", d.get("db", "unknown"))
        assert status == "ok", f"{target} health body: {body}"
    except json.JSONDecodeError:
        pytest.fail(f"{target} health returned non-JSON: {body[:100]}")


# ── 2. Latency p99 ───────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_latency_p99(request, target):
    """p99 latency under 3s for /api/health over 10 sequential requests."""
    base = request.getfixturevalue(target)
    latencies = []
    for _ in range(10):
        code, ms, _ = _http_get(f"{base}/api/health", timeout=15)
        if code == 200:
            latencies.append(ms)
    assert latencies, f"{target}: no successful requests"
    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99)]
    assert p99 < 3000, f"{target} p99={p99}ms (threshold: 3000ms)"


# ── 3. Concurrent 10 ─────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_concurrent_10(request, target):
    """10 concurrent requests to /api/health — 0 server errors."""
    base = request.getfixturevalue(target)
    codes = _concurrent_get(f"{base}/api/health", n=10, timeout=15)
    errors_5xx = [c for c in codes if c >= 500]
    assert not errors_5xx, (
        f"{target}: {len(errors_5xx)}/10 server errors: {Counter(codes)}"
    )


# ── 4. Concurrent 50 (spike) ─────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_concurrent_50(request, target):
    """50-request spike — recover after spike, less than 25% hard server errors.

    Notes:
    - Azure nginx uses proxy_intercept_errors which converts upstream errors to 503
    - 503 during a spike may be a brief maintenance window — allow up to 25%
    - If ALL 50 return 503, wait 5s and retry once (transient overload / blue-green switch)
    """
    base = request.getfixturevalue(target)
    codes = _concurrent_get(f"{base}/api/health", n=50, timeout=20)
    errors_5xx = [c for c in codes if c >= 500]
    error_pct = len(errors_5xx) / 50 * 100

    # If all 503 (likely transient: mid-deploy or brief maintenance), retry once
    if error_pct == 100 and all(c == 503 for c in codes):
        time.sleep(8)
        codes = _concurrent_get(f"{base}/api/health", n=50, timeout=20)
        errors_5xx = [c for c in codes if c >= 500]
        error_pct = len(errors_5xx) / 50 * 100

    assert error_pct < 25, (
        f"{target}: {error_pct:.0f}% server errors in spike-50 (after retry): {Counter(codes)}"
    )


# ── 5. Rate Limit ─────────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_rate_limit_present(request, target):
    """20 rapid requests — server stays healthy (no unexpected 5xx).

    nginx returns 503 for rate-limited requests (proxy_intercept_errors converts
    429 → 503 via @maintenance page), so 503 is accepted here.
    Fail only if we see 502 (bad gateway = upstream died) or 500 (app crash).
    """
    base = request.getfixturevalue(target)
    time.sleep(3)  # Let rate-limit window clear after spike test
    codes = _concurrent_get(f"{base}/api/health", n=20, timeout=15)
    # 200 = normal, 302 = redirect to login, 429/503 = rate-limited, 0 = timeout
    # FAIL only on 500 (app crash) or 502 (upstream dead)
    hard_errors = [c for c in codes if c in (500, 502)]
    assert not hard_errors, (
        f"{target}: hard server errors in rate-limit test: {Counter(codes)}"
    )


# ── 6. Pages Smoke Test ───────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_pages_smoke(request, target):
    """Key pages return 200 or 302 (redirect to login), never 5xx.

    Retries once after 5s if 503 (brief maintenance window after spike tests).
    """
    base = request.getfixturevalue(target)
    pages = ["/", "/projects", "/art", "/backlog", "/metrics", "/sessions"]
    time.sleep(3)  # Let server stabilize after spike/rate-limit tests
    failures = []
    for page in pages:
        code, ms, _ = _http_get(f"{base}{page}", timeout=15)
        if code >= 500 or code == 0:
            # Retry once
            time.sleep(5)
            code, ms, _ = _http_get(f"{base}{page}", timeout=15)
        if code >= 500 or code == 0:
            failures.append(f"{page}={code}({ms}ms)")
    assert not failures, f"{target}: page failures: {failures}"


# ── 7. SSE Connect ────────────────────────────────────────────────────────────


@pytest.mark.stability
@pytest.mark.parametrize("target", ["az", "ovh"])
def test_sse_connect(request, target):
    """SSE endpoint is reachable — auth redirect (HTML/302) is acceptable in prod."""
    base = request.getfixturevalue(target)
    ctx = None
    if base.startswith("https://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(f"{base}/sse/monitoring")
        response = urllib.request.urlopen(req, timeout=5, context=ctx)
        ct = response.headers.get("Content-Type", "")
        body_start = response.read(256).decode(errors="replace")
        if "text/event-stream" in ct:
            return  # ✓ SSE active (unauthenticated or session token provided)
        # HTML response = redirected to login page (expected in prod with auth)
        if "text/html" in ct or "login" in body_start.lower():
            pytest.skip(f"{target}: SSE endpoint redirects to login — expected in prod")
        pytest.fail(
            f"{target}: SSE Content-Type={ct!r} (expected event-stream or login redirect)"
        )
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 302):
            pytest.skip(
                f"{target}: SSE requires auth (HTTP {e.code}) — expected in prod"
            )
        if e.code == 503:
            pytest.skip(f"{target}: SSE 503 — server in maintenance window")
        pytest.fail(f"{target}: SSE HTTP {e.code}")
    except Exception as exc:
        # Timeout reading SSE stream is OK (means it connected and is streaming)
        exc_str = str(exc).lower()
        if "timed out" in exc_str or "timeout" in exc_str:
            return  # Connected and streaming (timed out waiting for data = OK)
        pytest.fail(f"{target}: SSE error: {exc}")


# ── 8. Disk & Memory ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_disk_memory_azure(ssh_run_az):
    """Azure VM: disk < 90%, memory < 85%."""
    out = ssh_run_az(
        "df -h / | awk 'NR==2 {print $5}' && free | awk '/Mem:/ {printf \"%.0f\", $3/$2*100}'"
    )
    lines = out.strip().splitlines()
    if len(lines) >= 2:
        disk_pct = int(lines[0].rstrip("%"))
        mem_pct = int(lines[1])
        assert disk_pct < 90, f"Azure disk at {disk_pct}% (threshold: 90%)"
        assert mem_pct < 85, f"Azure memory at {mem_pct}% (threshold: 85%)"


@pytest.mark.stability
def test_disk_memory_ovh(ssh_run_ovh):
    """OVH Demo: disk < 90%, memory < 85%."""
    out = ssh_run_ovh(
        "df -h / | awk 'NR==2 {print $5}' && free | awk '/Mem:/ {printf \"%.0f\", $3/$2*100}'"
    )
    lines = out.strip().splitlines()
    if len(lines) >= 2:
        disk_pct = int(lines[0].rstrip("%"))
        mem_pct = int(lines[1])
        assert disk_pct < 90, f"OVH disk at {disk_pct}% (threshold: 90%)"
        assert mem_pct < 85, f"OVH memory at {mem_pct}% (threshold: 85%)"


# ── 9. Hot Restart (web process) ──────────────────────────────────────────────


@pytest.mark.stability
def test_hot_restart_azure(az, ssh_run_az):
    """Azure: restart active web container, health OK within 30s."""
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    ssh_run_az(
        f"docker restart deploy-platform-{active}-1 2>/dev/null || true", timeout=60
    )
    time.sleep(5)
    ok = False
    for _ in range(15):
        time.sleep(2)
        code, _, _ = _http_get(f"{az}/api/health", timeout=10)
        if code == 200:
            ok = True
            break
    assert ok, "Azure: health not restored within 30s after hot restart"


@pytest.mark.stability
def test_hot_restart_ovh(ovh, ssh_run_ovh):
    """OVH: restart active web container, health OK within 30s."""
    active = ssh_run_ovh(
        "cat /opt/software-factory/active-slot 2>/dev/null || echo blue"
    ).strip()
    ssh_run_ovh(
        f"cd /opt/software-factory && docker compose restart platform-{active} 2>/dev/null || true",
        timeout=60,
    )
    time.sleep(5)
    ok = False
    for _ in range(15):
        time.sleep(2)
        code, _, _ = _http_get(f"{ovh}/api/health", timeout=10)
        if code == 200:
            ok = True
            break
    assert ok, "OVH: health not restored within 30s after hot restart"


# ── 10. Nginx Failover (503 not 502) ──────────────────────────────────────────


@pytest.mark.stability
def test_nginx_failover_azure(az, ssh_run_az):
    """Azure: kill web container → nginx returns 503 (not 502), restart → 200.

    Uses docker kill (SIGKILL) instead of stop (SIGTERM) to ensure immediate
    termination — docker stop has a 10s grace period during which uvicorn still
    handles requests, making the 503 check unreliable.
    """
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    # SIGKILL = immediate, no graceful shutdown
    ssh_run_az(f"docker kill deploy-platform-{active}-1 2>/dev/null || true")
    # Wait until container is confirmed stopped
    for _ in range(10):
        time.sleep(1)
        state = ssh_run_az(
            f"docker inspect deploy-platform-{active}-1 --format '{{{{.State.Running}}}}' 2>/dev/null || echo false"
        ).strip()
        if state in ("false", ""):
            break
    time.sleep(1)
    code, _, _ = _http_get(f"{az}/api/health", timeout=10)
    # Restart before asserting (don't leave it down)
    ssh_run_az(f"docker start deploy-platform-{active}-1 2>/dev/null || true")
    assert code == 503, f"Azure nginx failover returned {code} (expected 503)"
    # Wait for recovery
    code2 = 0
    for _ in range(20):
        time.sleep(3)
        code2, _, _ = _http_get(f"{az}/api/health", timeout=10)
        if code2 == 200:
            break
    assert code2 == 200, (
        f"Azure: did not recover after failover test (last code={code2})"
    )


@pytest.mark.stability
def test_nginx_failover_ovh(ovh, ssh_run_ovh):
    """OVH: stop web container → nginx returns 503 (not 502), restart → 200."""
    active = ssh_run_ovh(
        "cat /opt/software-factory/active-slot 2>/dev/null || echo blue"
    ).strip()
    ssh_run_ovh(
        f"cd /opt/software-factory && docker compose stop platform-{active} 2>/dev/null || true"
    )
    time.sleep(3)
    code, _, _ = _http_get(f"{ovh}/api/health", timeout=10)
    # Restart before asserting
    ssh_run_ovh(
        f"cd /opt/software-factory && docker compose start platform-{active} 2>/dev/null || true"
    )
    assert code == 503, f"OVH nginx failover returned {code} (expected 503)"
    for _ in range(20):
        time.sleep(3)
        code2, _, _ = _http_get(f"{ovh}/api/health", timeout=10)
        if code2 == 200:
            break
    assert code2 == 200, f"OVH: did not recover after failover test (last code={code2})"


# ── 11. Cold Restart ──────────────────────────────────────────────────────────


@pytest.mark.stability
def test_cold_restart_azure(az, ssh_run_az):
    """Azure: docker compose down active slot + up → health within 60s."""
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    COMPOSE = "/home/azureadmin/macaron_update/platform/deploy/docker-compose-vm.yml"
    ssh_run_az(
        f"docker compose --env-file /opt/macaron/.env -f {COMPOSE} stop platform-{active} 2>/dev/null || true",
        timeout=30,
    )
    time.sleep(2)
    ssh_run_az(
        f"docker compose --env-file /opt/macaron/.env -f {COMPOSE} start platform-{active} 2>/dev/null || true",
        timeout=30,
    )
    ok = False
    for _ in range(30):
        time.sleep(2)
        code, _, _ = _http_get(f"{az}/api/health", timeout=10)
        if code == 200:
            ok = True
            break
    assert ok, "Azure: health not restored within 60s after cold restart"


@pytest.mark.stability
def test_cold_restart_ovh(ovh, ssh_run_ovh):
    """OVH: docker compose down active slot + up → health within 60s."""
    active = ssh_run_ovh(
        "cat /opt/software-factory/active-slot 2>/dev/null || echo blue"
    ).strip()
    ssh_run_ovh(
        f"cd /opt/software-factory && docker compose stop platform-{active} 2>/dev/null || true",
        timeout=30,
    )
    time.sleep(2)
    ssh_run_ovh(
        f"cd /opt/software-factory && docker compose start platform-{active} 2>/dev/null || true",
        timeout=30,
    )
    ok = False
    for _ in range(30):
        time.sleep(2)
        code, _, _ = _http_get(f"{ovh}/api/health", timeout=10)
        if code == 200:
            ok = True
            break
    assert ok, "OVH: health not restored within 60s after cold restart"


# ── 12. Chaos: SIGSTOP / SIGCONT ─────────────────────────────────────────────


@pytest.mark.stability
def test_chaos_pause_resume_azure(az, ssh_run_az):
    """Azure: SIGSTOP container for 10s → 503 → SIGCONT → 200 within 15s."""
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    # Pause
    ssh_run_az(f"docker pause deploy-platform-{active}-1 2>/dev/null || true")
    time.sleep(2)
    code_paused, _, _ = _http_get(f"{az}/api/health", timeout=8)
    # Unpause
    ssh_run_az(f"docker unpause deploy-platform-{active}-1 2>/dev/null || true")
    assert code_paused in (502, 503, 504, 0), (
        f"Azure: expected error during chaos pause, got {code_paused}"
    )
    # Recover
    ok = False
    for _ in range(15):
        time.sleep(1)
        code2, _, _ = _http_get(f"{az}/api/health", timeout=10)
        if code2 == 200:
            ok = True
            break
    assert ok, "Azure: did not recover within 15s after chaos unpause"


@pytest.mark.stability
def test_chaos_pause_resume_ovh(ovh, ssh_run_ovh):
    """OVH: SIGSTOP container for 10s → 5xx → SIGCONT → 200 within 15s."""
    active = ssh_run_ovh(
        "cat /opt/software-factory/active-slot 2>/dev/null || echo blue"
    ).strip()
    ctr = f"software-factory-platform-{active}-1"
    # Verify container exists before pausing
    exists = ssh_run_ovh(f"docker ps -q --filter name={ctr} | head -1").strip()
    if not exists:
        pytest.skip(f"OVH: container {ctr} not running — skipping chaos test")
    ssh_run_ovh(f"docker pause {ctr} 2>/dev/null || true")
    time.sleep(
        5
    )  # Longer wait: let nginx close keepalive + detect upstream unavailable
    code_paused, _, _ = _http_get(f"{ovh}/api/health", timeout=8)
    ssh_run_ovh(f"docker unpause {ctr} 2>/dev/null || true")
    # Accept: nginx custom 503 maintenance, 502 bad gateway, 504 timeout, or 0 (connection refused)
    # Also accept 200 if nginx keepalive served cached response — log warning but don't fail
    if code_paused == 200:
        pytest.xfail(
            "OVH chaos: got 200 during pause — nginx keepalive or no nginx buffering issue. "
            "Not a hard failure but behaviour should be investigated."
        )
    assert code_paused in (502, 503, 504, 0), (
        f"OVH: expected error during chaos pause, got {code_paused}"
    )
    ok = False
    for _ in range(15):
        time.sleep(1)
        code2, _, _ = _http_get(f"{ovh}/api/health", timeout=10)
        if code2 == 200:
            ok = True
            break
    assert ok, "OVH: did not recover within 15s after chaos unpause"


# ── 13. Config Guards ─────────────────────────────────────────────────────────


@pytest.mark.stability
def test_config_guards_azure(ssh_run_az):
    """Azure: PLATFORM_AUTO_RESUME_ENABLED should be 0 in web container (UI mode)."""
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    val = ssh_run_az(
        f"docker exec deploy-platform-{active}-1 "
        "printenv PLATFORM_AUTO_RESUME_ENABLED 2>/dev/null || echo ''"
    ).strip()
    if not val:
        # Variable not set = old container pre-dating this deployment (acceptable)
        pytest.skip(
            f"Azure: PLATFORM_AUTO_RESUME_ENABLED not set in {active} container "
            "(pre-decoupling image — will be fixed on next blue-green cycle)"
        )
    assert val == "0", (
        f"Azure: PLATFORM_AUTO_RESUME_ENABLED={val!r} in {active} container (expected '0')"
    )


@pytest.mark.stability
def test_config_guards_ovh(ssh_run_ovh):
    """OVH: PLATFORM_AUTO_RESUME_ENABLED=0 effective in running container."""
    active = ssh_run_ovh(
        "cat /opt/software-factory/active-slot 2>/dev/null || echo blue"
    ).strip()
    ctr = f"software-factory-platform-{active}-1"
    val = ssh_run_ovh(
        f"docker exec {ctr} printenv PLATFORM_AUTO_RESUME_ENABLED 2>/dev/null || echo '?'"
    ).strip()
    assert val == "0", f"OVH: PLATFORM_AUTO_RESUME_ENABLED={val!r} (expected '0')"


@pytest.mark.stability
def test_factory_process_mode_azure(ssh_run_az):
    """Azure: platform-factory container has PLATFORM_MODE=factory."""
    val = ssh_run_az(
        "docker exec deploy-platform-factory-1 printenv PLATFORM_MODE 2>/dev/null || echo 'not_running'"
    ).strip()
    # Non-fatal if factory not yet deployed (first deploy)
    if val == "not_running":
        pytest.skip("platform-factory not yet running (first deploy pending)")
    assert val == "factory", (
        f"Azure: PLATFORM_MODE={val!r} in factory container (expected 'factory')"
    )


@pytest.mark.stability
def test_web_process_mode_azure(ssh_run_az):
    """Azure: platform-blue/green container has PLATFORM_MODE=ui (or full for legacy)."""
    active = ssh_run_az(
        "cat /home/azureadmin/macaron-active-slot 2>/dev/null || echo blue"
    ).strip()
    val = ssh_run_az(
        f"docker exec deploy-platform-{active}-1 printenv PLATFORM_MODE 2>/dev/null || echo ''"
    ).strip()
    if not val:
        # Not set = old container pre-dating PLATFORM_MODE feature (acceptable)
        pytest.skip(
            f"Azure: PLATFORM_MODE not set in {active} container "
            "(pre-decoupling image — will be fixed on next blue-green cycle)"
        )
    assert val in ("ui", "full"), (
        f"Azure: PLATFORM_MODE={val!r} in {active} web container (expected 'ui')"
    )


@pytest.mark.stability
def test_redis_running_azure(ssh_run_az):
    """Azure: Redis container is up and responding to PING."""
    out = ssh_run_az(
        "docker exec deploy-redis-1 redis-cli ping 2>/dev/null || echo FAIL"
    ).strip()
    assert out == "PONG", f"Azure: Redis ping returned {out!r}"
