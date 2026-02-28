"""LLM Metrics + E2E Tests Metrics routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ..routes.helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


# ── E2E Tests helpers ────────────────────────────────────────────────────────


def _get_db():
    from ...db.migrations import get_db

    return get_db()


def _ensure_tests_table():
    conn = _get_db()
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
            trigger TEXT DEFAULT 'manual'
        )
    """)
    conn.commit()


class TestRunRecord(BaseModel):
    spec: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: int = 0
    trigger: str = "manual"
    run_id: str = ""


def _get_tracer():
    from ...llm.observability import get_tracer

    return get_tracer()


@router.get("/metrics/tab/llm", response_class=HTMLResponse)
async def metrics_tab_llm(request: Request):
    """LLM metrics tab partial (HTMX)."""
    return _templates(request).TemplateResponse(
        "metrics.html",
        {"request": request},
    )


@router.get("/api/metrics/llm")
async def api_metrics_llm():
    """LLM stats — 24h and 7d windows."""
    tracer = _get_tracer()
    stats_24h = tracer.stats(hours=24)
    stats_7d = tracer.stats(hours=168)
    return JSONResponse({"h24": stats_24h, "h168": stats_7d})


@router.get("/api/metrics/llm/traces")
async def api_metrics_llm_traces(limit: int = 100, session_id: str = ""):
    """Recent LLM traces."""
    tracer = _get_tracer()
    return JSONResponse({"traces": tracer.recent(limit=limit, session_id=session_id)})


@router.get("/api/metrics/llm/top-agents")
async def api_metrics_llm_top_agents(hours: int = 168):
    """Top 10 agents by cost (last N hours)."""
    tracer = _get_tracer()
    stats = tracer.stats(hours=hours)
    top = sorted(
        stats.get("by_agent", []), key=lambda x: x.get("cost_usd", 0), reverse=True
    )[:10]
    return JSONResponse({"top_agents": top, "hours": hours})


# ── E2E Tests tab ─────────────────────────────────────────────────────────────


@router.get("/metrics/tab/tests", response_class=HTMLResponse)
async def metrics_tab_tests(request: Request):
    """E2E Tests metrics tab partial (HTMX)."""
    _ensure_tests_table()
    conn = _get_db()

    # Latest run_id
    row = conn.execute(
        "SELECT run_id, run_at FROM e2e_test_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    latest_run_id = row["run_id"] if row else ""
    latest_run_at = row["run_at"] if row else ""

    # Per-spec results for latest run
    specs = []
    if latest_run_id:
        rows = conn.execute(
            "SELECT spec, passed, failed, skipped, duration_ms "
            "FROM e2e_test_runs WHERE run_id = ? ORDER BY spec",
            (latest_run_id,),
        ).fetchall()
        for r in rows:
            total = r["passed"] + r["failed"] + r["skipped"]
            rate = round(r["passed"] / total * 100) if total else 0
            specs.append(
                {
                    "spec": r["spec"],
                    "passed": r["passed"],
                    "failed": r["failed"],
                    "skipped": r["skipped"],
                    "total": total,
                    "rate": rate,
                    "duration_s": round(r["duration_ms"] / 1000, 1),
                }
            )

    # Summary totals
    total_passed = sum(s["passed"] for s in specs)
    total_failed = sum(s["failed"] for s in specs)
    total_skipped = sum(s["skipped"] for s in specs)
    total_tests = total_passed + total_failed + total_skipped
    pass_rate = round(total_passed / total_tests * 100) if total_tests else 0

    # Run history (last 10 runs, one row per run_id)
    history_rows = conn.execute(
        "SELECT run_id, run_at, trigger, "
        "SUM(passed) as p, SUM(failed) as f, SUM(skipped) as s "
        "FROM e2e_test_runs GROUP BY run_id ORDER BY MAX(id) DESC LIMIT 10"
    ).fetchall()
    history = []
    for h in history_rows:
        tot = (h["p"] or 0) + (h["f"] or 0) + (h["s"] or 0)
        history.append(
            {
                "run_id": h["run_id"],
                "run_at": h["run_at"],
                "trigger": h["trigger"],
                "passed": h["p"] or 0,
                "failed": h["f"] or 0,
                "skipped": h["s"] or 0,
                "total": tot,
                "rate": round((h["p"] or 0) / tot * 100) if tot else 0,
            }
        )

    return _templates(request).TemplateResponse(
        "_partial_tests.html",
        {
            "request": request,
            "specs": specs,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "total_tests": total_tests,
            "pass_rate": pass_rate,
            "latest_run_at": latest_run_at,
            "latest_run_id": latest_run_id,
            "history": history,
        },
    )


@router.get("/api/metrics/tests")
async def api_metrics_tests(run_id: str = ""):
    """E2E test run results. Returns latest run if run_id not specified."""
    _ensure_tests_table()
    conn = _get_db()
    if not run_id:
        row = conn.execute(
            "SELECT run_id FROM e2e_test_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        run_id = row["run_id"] if row else ""
    rows = conn.execute(
        "SELECT spec, passed, failed, skipped, duration_ms, run_at, trigger "
        "FROM e2e_test_runs WHERE run_id = ? ORDER BY spec",
        (run_id,),
    ).fetchall()
    return JSONResponse({"run_id": run_id, "specs": [dict(r) for r in rows]})


@router.post("/api/metrics/tests/record")
async def api_metrics_tests_record(body: TestRunRecord):
    """Record a single spec test result."""
    _ensure_tests_table()
    conn = _get_db()
    conn.execute(
        "INSERT INTO e2e_test_runs (run_id, spec, passed, failed, skipped, duration_ms, trigger) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            body.run_id,
            body.spec,
            body.passed,
            body.failed,
            body.skipped,
            body.duration_ms,
            body.trigger,
        ),
    )
    conn.commit()
    return JSONResponse({"ok": True})
