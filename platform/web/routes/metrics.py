"""LLM Metrics + E2E Tests Metrics routes."""
# Ref: feat-metrics

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from ...auth.middleware import require_auth
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
    try:
        tracer = _get_tracer()
        stats_24h = tracer.stats(hours=24)
        stats_7d = tracer.stats(hours=168)
        return JSONResponse({"h24": stats_24h, "h168": stats_7d})
    except Exception as exc:
        logger.error("api_metrics_llm failed: %s", exc, exc_info=True)
        return JSONResponse({"error": str(exc), "h24": {}, "h168": {}}, status_code=500)


@router.get("/api/metrics/llm/traces")
async def api_metrics_llm_traces(limit: int = 100, session_id: str = ""):
    """Recent LLM traces."""
    try:
        tracer = _get_tracer()
        return JSONResponse(
            {"traces": tracer.recent(limit=limit, session_id=session_id)}
        )
    except Exception as exc:
        logger.error("api_metrics_llm_traces failed: %s", exc, exc_info=True)
        return JSONResponse({"error": str(exc), "traces": []}, status_code=500)


@router.get("/api/metrics/llm/top-agents")
async def api_metrics_llm_top_agents(hours: int = 168):
    """Top 10 agents by cost (last N hours)."""
    try:
        tracer = _get_tracer()
        stats = tracer.stats(hours=hours)
        top = sorted(
            stats.get("by_agent", []), key=lambda x: x.get("cost_usd", 0), reverse=True
        )[:10]
        return JSONResponse({"top_agents": top, "hours": hours})
    except Exception as exc:
        logger.error("api_metrics_llm_top_agents failed: %s", exc, exc_info=True)
        return JSONResponse(
            {"error": str(exc), "top_agents": [], "hours": hours}, status_code=500
        )


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


@router.post("/api/metrics/tests/record", dependencies=[Depends(require_auth())])
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


# ── Modules metrics tab ───────────────────────────────────────────────────────


@router.get("/metrics/tab/modules", response_class=HTMLResponse)
async def metrics_tab_modules(request: Request):
    """Modules usage metrics tab partial (HTMX)."""
    return _templates(request).TemplateResponse(
        "metrics_modules.html", {"request": request}
    )


@router.get("/api/metrics/modules")
async def api_metrics_modules():
    """Aggregated module usage stats (RTK + module activation overview)."""
    import yaml
    from pathlib import Path

    try:
        conn = _get_db()

        # RTK compression stats — table may not exist yet
        rtk_empty = {"n": 0, "orig": 0, "comp": 0, "avg_pct": 0}
        rtk_24h_empty = {"calls": 0, "avg_pct": 0, "tokens_saved": 0}
        try:
            rtk_total = (
                conn.execute(
                    "SELECT COUNT(*) as n, COALESCE(SUM(original_tokens),0) as orig, "
                    "COALESCE(SUM(compressed_tokens),0) as comp, COALESCE(AVG(savings_pct),0) as avg_pct "
                    "FROM rtk_compression_stats"
                ).fetchone()
                or rtk_empty
            )
        except Exception:
            rtk_total = rtk_empty

        try:
            rtk_24h = (
                conn.execute(
                    "SELECT COUNT(*) as calls, COALESCE(AVG(savings_pct),0) as avg_pct, "
                    "COALESCE(SUM(original_tokens - compressed_tokens),0) as tokens_saved "
                    "FROM rtk_compression_stats WHERE ts > NOW() - INTERVAL '24 hours'"
                ).fetchone()
                or rtk_24h_empty
            )
        except Exception:
            rtk_24h = rtk_24h_empty

        try:
            rtk_by_provider = conn.execute(
                "SELECT provider, COUNT(*) as calls, "
                "COALESCE(SUM(original_tokens),0) as orig_tokens, "
                "COALESCE(SUM(compressed_tokens),0) as comp_tokens, "
                "COALESCE(AVG(savings_pct),0) as avg_pct "
                "FROM rtk_compression_stats GROUP BY provider ORDER BY calls DESC"
            ).fetchall()
        except Exception:
            rtk_by_provider = []

        try:
            rtk_daily = conn.execute(
                "SELECT DATE(ts) as day, COUNT(*) as calls, "
                "COALESCE(SUM(original_tokens - compressed_tokens),0) as tokens_saved "
                "FROM rtk_compression_stats WHERE ts > NOW() - INTERVAL '7 days' "
                "GROUP BY DATE(ts) ORDER BY day"
            ).fetchall()
        except Exception:
            rtk_daily = []

        # Module activation status from registry
        registry_path = (
            Path(__file__).parent.parent.parent / "modules" / "registry.yaml"
        )
        modules_list = []
        if registry_path.exists():
            with open(registry_path) as f:
                all_modules = (yaml.safe_load(f) or {}).get("modules", [])
            enabled_ids = set()
            try:
                rows = conn.execute(
                    "SELECT value FROM settings WHERE key = 'enabled_modules'"
                ).fetchone()
                if rows:
                    import json

                    enabled_ids = set(json.loads(rows["value"]) or [])
            except Exception:
                pass
            modules_list = [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "category": m.get("category", "other"),
                    "icon": m.get("icon", "🔧"),
                    "enabled": m.get("id") in enabled_ids,
                }
                for m in all_modules
            ]

        return JSONResponse(
            {
                "rtk": {
                    "total_calls": rtk_total["n"] or 0,
                    "total_tokens_original": rtk_total["orig"] or 0,
                    "total_tokens_compressed": rtk_total["comp"] or 0,
                    "total_tokens_saved": (rtk_total["orig"] or 0)
                    - (rtk_total["comp"] or 0),
                    "avg_savings_pct": round(rtk_total["avg_pct"] or 0, 1),
                    "last_24h": {
                        "calls": rtk_24h["calls"] or 0,
                        "avg_pct": round(rtk_24h["avg_pct"] or 0, 1),
                        "tokens_saved": rtk_24h["tokens_saved"] or 0,
                    },
                    "by_provider": [dict(r) for r in rtk_by_provider],
                    "daily_7d": [dict(r) for r in rtk_daily],
                },
                "modules": modules_list,
                "enabled_count": sum(1 for m in modules_list if m["enabled"]),
                "total_count": len(modules_list),
            }
        )
    except Exception as exc:
        logger.error("api_metrics_modules failed: %s", exc, exc_info=True)
        return JSONResponse({"error": str(exc)}, status_code=500)
