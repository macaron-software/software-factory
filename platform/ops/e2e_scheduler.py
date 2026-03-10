"""
E2E Test Scheduler — nightly Playwright run at 05:00 UTC.

- Runs the full Playwright test suite against localhost:8090
- Records results in e2e_test_runs (DB)
- Creates platform_incidents for any failing spec
- Gracefully skips if Playwright is not available (Docker prod without Chromium)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Path to E2E tests directory
_E2E_DIR = Path(__file__).parent.parent.parent / "platform" / "tests" / "e2e"
_PLAYWRIGHT_TIMEOUT = 600  # 10 min max for the full suite
_RUN_HOUR_UTC = 5  # 05:00 UTC


def _get_db():
    from ..db.migrations import get_db

    return get_db()


def _ensure_tests_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS e2e_test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT DEFAULT (datetime('now')),
            run_id TEXT DEFAULT '',
            spec TEXT NOT NULL,
            passed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            trigger TEXT DEFAULT 'scheduled'
        )
    """)
    conn.commit()


async def _wait_until_next_run() -> None:
    """Wait until next 05:00 UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=_RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_secs = (target - now).total_seconds()
    log.info(
        f"E2E scheduler: next run at {target.isoformat()} (in {wait_secs / 3600:.1f}h)"
    )
    await asyncio.sleep(wait_secs)


def _find_playwright() -> str | None:
    """Return path to playwright binary if available, else None."""
    # Try node_modules/.bin/playwright relative to e2e dir or repo root
    candidates = [
        _E2E_DIR / "node_modules" / ".bin" / "playwright",
        _E2E_DIR.parent.parent / "node_modules" / ".bin" / "playwright",
        Path("/usr/local/bin/playwright"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Try npx (available if Node is installed)
    try:
        result = subprocess.run(
            ["npx", "--yes", "playwright", "--version"], capture_output=True, timeout=10
        )
        if result.returncode == 0:
            return "npx playwright"
    except Exception:
        pass
    return None


def _parse_playwright_json(json_path: Path) -> list[dict]:
    """Parse playwright JSON report into per-spec summary dicts."""
    try:
        data = json.loads(json_path.read_text())
    except Exception as e:
        log.warning(f"E2E: failed to parse JSON report: {e}")
        return []

    specs: dict[str, dict] = {}

    def _walk(suites, spec_file=""):
        for suite in suites:
            file = suite.get("file") or suite.get("title") or spec_file
            if suite.get("file"):
                file = Path(suite["file"]).name
            # Recurse into sub-suites
            _walk(suite.get("suites", []), file)
            for spec in suite.get("specs", []):
                fname = file or spec_file
                if fname not in specs:
                    specs[fname] = {
                        "passed": 0,
                        "failed": 0,
                        "skipped": 0,
                        "duration_ms": 0,
                    }
                for test in spec.get("tests", []):
                    status = test.get("status", "")
                    duration = sum(
                        r.get("duration", 0) for r in test.get("results", [])
                    )
                    specs[fname]["duration_ms"] += duration
                    if status in ("expected", "passed"):
                        specs[fname]["passed"] += 1
                    elif status in ("unexpected", "failed"):
                        specs[fname]["failed"] += 1
                    else:  # skipped / fixme
                        specs[fname]["skipped"] += 1

    _walk(data.get("suites", []))
    return [{"spec": k, **v} for k, v in specs.items() if k]


def _create_incident(conn, spec: str, failed: int, run_id: str) -> None:
    """Create a platform_incident for a failing E2E spec."""
    incident_id = f"e2e-{uuid.uuid4().hex[:8]}"
    title = f"[E2E] {failed} test(s) failed in {spec}"
    detail = (
        f"Nightly Playwright run (run_id={run_id}) detected {failed} failure(s) "
        f"in {spec}. Check /metrics?tab=tests for details."
    )
    try:
        conn.execute(
            "INSERT OR IGNORE INTO platform_incidents "
            "(id, title, severity, status, source, error_type, error_detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (incident_id, title, "P2", "open", "e2e-scheduler", "test_failure", detail),
        )
        conn.commit()
        log.warning(f"E2E: incident created — {title}")
    except Exception as e:
        log.warning(f"E2E: failed to create incident: {e}")


async def _run_e2e_cycle() -> None:
    """Run full E2E suite, record results, raise incidents on failure."""
    log.info("E2E scheduler: starting nightly cycle")

    playwright = _find_playwright()
    if not playwright:
        log.warning("E2E scheduler: Playwright not found — skipping test run")
        return

    if not _E2E_DIR.exists():
        log.warning(f"E2E scheduler: tests dir not found at {_E2E_DIR}")
        return

    run_id = f"nightly-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    report_path = _E2E_DIR / f"_report_{run_id}.json"

    # Build command
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8090")
    if playwright.startswith("npx"):
        cmd = ["npx", "playwright", "test"]
    else:
        cmd = [playwright, "test"]
    cmd += [
        "--reporter=json",
        f"--output={report_path}",
        "--timeout=30000",
    ]

    log.info(f"E2E scheduler: running {' '.join(cmd[:3])} ... (BASE_URL={base_url})")

    try:
        env = {**os.environ, "BASE_URL": base_url, "CI": "1"}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(_E2E_DIR),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_PLAYWRIGHT_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            log.warning(f"E2E scheduler: timed out after {_PLAYWRIGHT_TIMEOUT}s")
            return
    except Exception as e:
        log.warning(f"E2E scheduler: subprocess error: {e}")
        return

    log.info(f"E2E scheduler: playwright exit code={proc.returncode}")

    # Parse results from JSON report
    # Playwright --reporter=json writes to stdout when --output is set
    specs = []
    if report_path.exists():
        specs = _parse_playwright_json(report_path)
        try:
            report_path.unlink()
        except Exception:
            pass
    else:
        # Try stdout
        try:
            data_str = stdout.decode("utf-8", errors="replace").strip()
            # Find JSON in output (may have non-JSON prefix)
            idx = data_str.find("{")
            if idx >= 0:
                tmp = report_path.with_suffix(".tmp")
                tmp.write_text(data_str[idx:])
                specs = _parse_playwright_json(tmp)
                tmp.unlink(missing_ok=True)
        except Exception as e:
            log.warning(f"E2E scheduler: could not parse stdout JSON: {e}")

    if not specs:
        log.warning("E2E scheduler: no spec results parsed — check Playwright output")
        return

    conn = _get_db()
    _ensure_tests_table(conn)

    total_passed = total_failed = total_skipped = 0
    for s in specs:
        conn.execute(
            "INSERT INTO e2e_test_runs (run_id, spec, passed, failed, skipped, duration_ms, trigger) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                s["spec"],
                s["passed"],
                s["failed"],
                s["skipped"],
                s["duration_ms"],
                "scheduled",
            ),
        )
        total_passed += s["passed"]
        total_failed += s["failed"]
        total_skipped += s["skipped"]

        if s["failed"] > 0:
            _create_incident(conn, s["spec"], s["failed"], run_id)

    conn.commit()
    log.info(
        f"E2E scheduler: done — {total_passed}✓ {total_failed}✗ {total_skipped}⊘ "
        f"({len(specs)} specs, run_id={run_id})"
    )


async def e2e_scheduler_loop() -> None:
    """Long-running coroutine — runs E2E tests every night at 05:00 UTC."""
    log.info(f"E2E scheduler: started (runs nightly at {_RUN_HOUR_UTC:02d}:00 UTC)")
    while True:
        await _wait_until_next_run()
        await _run_e2e_cycle()
