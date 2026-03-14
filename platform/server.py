"""Software Factory — FastAPI web server.

Serves the HTMX-based UI with SSE real-time updates.
Runs on port 8090 (separate from Factory dashboard on 8080).
"""
# Ref: feat-cockpit

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import JSONResponse

from .config import get_config
from .db.migrations import init_db

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


# ── OpenTelemetry setup (module-level, before create_app) ──────────────────
_otel_provider = None
_otel_meter_provider = None
if os.environ.get("OTEL_ENABLED"):
    try:
        import atexit

        from opentelemetry import metrics as otel_metrics
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        _otel_resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "macaron-platform"),
                "service.version": "1.2.0",
                "deployment.environment": os.environ.get("PLATFORM_ENV", "production"),
            }
        )

        # ── Traces ─────────────────────────────────────────────────────────
        _otel_provider = TracerProvider(resource=_otel_resource)
        _otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        _http_ep = _otlp_endpoint.replace(":4317", ":4318")

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            _traces_ep = _http_ep + "/v1/traces"
            _otel_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=_traces_ep))
            )
            logger.warning("OTEL: exporting traces to %s", _traces_ep)
        except ImportError:
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )

            _otel_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.warning("OTEL: OTLP exporter not available, using console")

        trace.set_tracer_provider(_otel_provider)
        atexit.register(_otel_provider.shutdown)

        # ── Metrics ────────────────────────────────────────────────────────
        try:
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )

            _metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=_http_ep + "/v1/metrics"),
                export_interval_millis=15_000,
            )
            _otel_meter_provider = MeterProvider(
                resource=_otel_resource, metric_readers=[_metric_reader]
            )
            otel_metrics.set_meter_provider(_otel_meter_provider)
            atexit.register(_otel_meter_provider.shutdown)

            # Register observable gauges bridging MetricsCollector → OTEL
            _meter = otel_metrics.get_meter("macaron-platform")

            def _obs_http_requests(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["http"]["total_requests"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_http_errors(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["http"]["total_errors"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_http_avg_ms(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["http"]["avg_ms"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_mcp_calls(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["mcp"]["total_calls"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_llm_cost(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["llm_costs"]["total_usd"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_db_queries(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["db_queries"]["total"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            def _obs_uptime(options):
                try:
                    from .metrics.collector import get_collector

                    yield otel_metrics.Observation(
                        get_collector().snapshot()["uptime_seconds"]
                    )
                except Exception:
                    yield otel_metrics.Observation(0)

            _meter.create_observable_gauge(
                "macaron_http_requests_total",
                callbacks=[_obs_http_requests],
                description="Total HTTP requests",
            )
            _meter.create_observable_gauge(
                "macaron_http_errors_total",
                callbacks=[_obs_http_errors],
                description="Total HTTP errors (4xx+5xx)",
            )
            _meter.create_observable_gauge(
                "macaron_http_latency_avg_ms",
                callbacks=[_obs_http_avg_ms],
                description="Avg HTTP latency (ms)",
            )
            _meter.create_observable_gauge(
                "macaron_mcp_calls_total",
                callbacks=[_obs_mcp_calls],
                description="Total MCP tool calls",
            )
            _meter.create_observable_gauge(
                "macaron_llm_cost_usd_total",
                callbacks=[_obs_llm_cost],
                description="Cumulative LLM cost (USD)",
            )
            _meter.create_observable_gauge(
                "macaron_db_queries_total",
                callbacks=[_obs_db_queries],
                description="Total DB queries",
            )
            _meter.create_observable_gauge(
                "macaron_uptime_seconds",
                callbacks=[_obs_uptime],
                description="Process uptime (seconds)",
            )

            logger.warning(
                "OTEL: MeterProvider ready, OTLP push + /metrics scrape endpoint"
            )
        except ImportError as e:
            logger.warning("OTEL: metrics exporter not available (%s)", e)

        logger.warning(
            "OpenTelemetry tracing enabled (service: %s)",
            _otel_resource.attributes.get("service.name"),
        )
    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")


def _recover_db_lock():
    """No-op: WAL checkpoint is SQLite-specific, not needed with current DB adapter."""
    logger.debug("_recover_db_lock: skipped (managed by db adapter)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    from .log_config import setup_logging

    setup_logging(level=os.environ.get("LOG_LEVEL", "WARNING"))

    # PLATFORM_MODE: full (default) | factory (headless) | ui (web-only) | slave (API-only, no IHM)
    _mode = os.environ.get("PLATFORM_MODE", "full").lower()
    if _mode not in ("full", "factory", "ui", "slave"):
        logger.warning("Unknown PLATFORM_MODE=%r — falling back to 'full'", _mode)
        _mode = "full"
    if _mode != "full":
        logger.warning("PLATFORM_MODE=%s", _mode)

    cfg = get_config()
    logger.info("Starting Software Factory on port %s", cfg.server.port)

    # Recover from stale WAL/lock left by a previously crashed process
    _recover_db_lock()

    init_db()

    # SAFe rename migration: missions → epics, mission_runs → epic_runs
    try:
        from .db.migration_epic_rename import run_migration as _epic_migration

        _epic_migration()
    except Exception as _me:
        logger.warning("Epic rename migration failed (non-fatal): %s", _me)

    # Agent plan tables (TodoList middleware)
    try:
        from .db.migrations import get_db as _gdb_plans

        with _gdb_plans() as _pdb:
            _pdb.execute("""
                CREATE TABLE IF NOT EXISTS agent_plans (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    project_id TEXT,
                    agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            _pdb.execute("""
                CREATE TABLE IF NOT EXISTS agent_plan_steps (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL REFERENCES agent_plans(id) ON DELETE CASCADE,
                    step_num INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            _pdb.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_plans_session ON agent_plans(session_id)"
            )
            _pdb.execute(
                "CREATE INDEX IF NOT EXISTS idx_plan_steps_plan ON agent_plan_steps(plan_id)"
            )
    except Exception as _pe:
        logger.warning("Agent plan tables migration failed (non-fatal): %s", _pe)

    # Seed built-in agents
    from .agents.store import get_agent_store

    get_agent_store().seed_builtins()

    # Seed built-in patterns
    from .patterns.store import get_pattern_store

    get_pattern_store().seed_builtins()

    # Seed built-in workflows
    from .workflows.store import get_workflow_store

    get_workflow_store().seed_builtins()

    # Seed skills library into DB
    from .skills.library import get_skill_library

    n = get_skill_library().seed_db()
    if n:
        logger.info("Seeded %d skills into DB", n)

    # Ensure every project has TMA + Security + Debt (+ MVP if applicable) missions
    # Moved to background task to reduce startup/MTTR time
    from .projects.manager import get_project_store
    import asyncio as _asyncio

    ps = get_project_store()
    ps.seed_from_registry()

    async def _bg_heal_and_seed():
        import asyncio as _a

        _loop = _a.get_event_loop()
        _prov_count = 0
        for proj in ps.list_all():
            try:
                created = await _loop.run_in_executor(None, ps.heal_epics, proj)
                _prov_count += len(created)
            except Exception as e:
                logger.warning("heal_epics failed for %s: %s", proj.id, e)
        if _prov_count:
            logger.warning(
                "heal_epics: created %d missions across all projects", _prov_count
            )

        # Scaffold all projects: ensure workspace + git + docker + docs + code exist
        from .projects.manager import heal_all_projects as _heal

        await _loop.run_in_executor(None, _heal)

        # Seed memory (global knowledge + project files)
        from .memory.seeder import seed_all as seed_memories

        try:
            n_mem = await _loop.run_in_executor(None, seed_memories)
            if n_mem:
                logger.info("Seeded %d memories", n_mem)
        except Exception as _e:
            logger.warning("Memory seeding skipped: %s", _e)

    _asyncio.create_task(_bg_heal_and_seed())

    # Seed org tree (Portfolio → ART → Team)
    from .agents.org import get_org_store

    get_org_store().seed_default()
    get_org_store().seed_additional_teams()

    # Demo mode: seed sample data when no LLM keys configured
    from .demo import seed_demo_data

    seed_demo_data()

    # Sync agent models+provider: ensure DB agents match the current DEFAULT_MODEL/PROVIDER
    from .agents.store import (
        DEFAULT_MODEL as _current_model,
        DEFAULT_PROVIDER as _current_provider,
    )

    try:
        from .db.migrations import get_db as _gdb_sync

        _sdb = _gdb_sync()
        # Only update agents that have a stale/wrong model or provider (not matching env)
        _stale_models = _sdb.execute(
            "SELECT COUNT(*) FROM agents WHERE (model != ? OR provider != ?) AND model NOT IN ('', 'demo-model')",
            (_current_model, _current_provider),
        ).fetchone()[0]
        if _stale_models:
            _sdb.execute(
                "UPDATE agents SET model = ?, provider = ? WHERE model NOT IN ('', 'demo-model')",
                (_current_model, _current_provider),
            )
            _sdb.commit()
            logger.warning(
                "Synced %d agents to DEFAULT_MODEL=%s provider=%s (from env/provider settings)",
                _stale_models,
                _current_model,
                _current_provider,
            )
        _sdb.close()
    except Exception as e:
        logger.warning("Failed to sync agent models: %s", e)

    # Mark orphaned "active" sessions as interrupted (no running task after restart)
    from .sessions.store import get_session_store

    _ss = get_session_store()
    _orphaned = _ss.mark_orphaned_sessions()
    if _orphaned:
        logger.info("Marked %d orphaned active sessions as interrupted", _orphaned)

    # Reset stale "running" epic_runs (orphaned after container restart)
    from .epics.store import get_epic_run_store

    _mrs = get_epic_run_store()
    try:
        from .db.migrations import get_db as _gdb

        _rdb = _gdb()
        _stale = _rdb.execute(
            "UPDATE epic_runs SET status='paused' WHERE status='running'"
        ).rowcount
        # Reset resume_attempts too — restart ≠ failure, don't burn backoff budget.
        # Wrapped separately so older DBs without the column don't break the status reset.
        try:
            _rdb.execute(
                "UPDATE epic_runs SET resume_attempts=0 WHERE status='paused' AND (resume_attempts IS NULL OR resume_attempts > 0)"
            )
        except Exception:
            pass
        # Also fix phases stuck at "running" inside phases_json
        _stuck_phases = 0
        _rows = _rdb.execute(
            "SELECT id, phases_json FROM epic_runs WHERE phases_json LIKE ?",
            ('%"running"%',),
        ).fetchall()
        for _row in _rows:
            import json as _json

            _phases = _json.loads(_row[1] or "[]")
            _fixed = False
            for _ph in _phases:
                if _ph.get("status") == "running":
                    _ph["status"] = "pending"
                    _ph["summary"] = (
                        _ph.get("summary") or ""
                    ) + " [auto-reset: was stuck running]"
                    _fixed = True
                    _stuck_phases += 1
            if _fixed:
                _rdb.execute(
                    "UPDATE epic_runs SET phases_json=? WHERE id=?",
                    (_json.dumps(_phases, default=str), _row[0]),
                )
        _rdb.commit()
        _rdb.close()
        if _stale or _stuck_phases:
            logger.warning(
                "Reset %d stale epic_runs to paused, fixed %d stuck running phases",
                _stale,
                _stuck_phases,
            )
    except Exception as e:
        logger.warning("Failed to reset stale missions: %s", e)

    # Auto-resume watchdog: handles paused/failed runs + launches unstarted continuous missions
    import asyncio as _asyncio
    from .services.auto_resume import auto_resume_epics as _auto_resume_epics

    if _mode != "ui":
        _asyncio.create_task(_auto_resume_epics())
        logger.warning("Auto-resume watchdog scheduled")

    # Start endurance watchdog (continuous auto-resume, session recovery, health)
    if _mode != "ui":
        try:
            from .ops.endurance_watchdog import watchdog_loop, ENABLED as _wd_enabled

            if _wd_enabled:
                _asyncio.create_task(watchdog_loop())
                logger.info("Endurance watchdog started as background task")
        except Exception as e:
            logger.warning("Failed to start endurance watchdog: %s", e)

    # Start evolution scheduler (nightly GA + RL retraining at 02:00 UTC)
    if _mode != "ui":
        try:
            from .agents.evolution_scheduler import (
                start_evolution_scheduler as _evo_sched,
            )

            _asyncio.create_task(_evo_sched())
            logger.info("Evolution scheduler started as background task")
        except Exception as e:
            logger.warning("Failed to start evolution scheduler: %s", e)

    # Redis pub/sub: connect bus and start cross-process listener
    _redis_url = os.environ.get("REDIS_URL")
    if _redis_url:
        import asyncio as _asyncio2
        from .a2a.bus import get_bus as _get_bus

        _bus = _get_bus()
        _asyncio2.create_task(_bus.connect_redis(_redis_url))
        if _mode in ("ui", "full"):
            # UI process subscribes to factory events via Redis
            _asyncio2.create_task(_bus.start_redis_listener(_redis_url))
            logger.info("Redis SSE listener scheduled")

    # PG NOTIFY/LISTEN: cross-node SSE fan-out (no Redis needed)
    import asyncio as _asyncio3
    from .a2a.bus import get_bus as _get_bus2

    _bus2 = _get_bus2()
    _asyncio3.create_task(_bus2.connect_pg_notify())
    _asyncio3.create_task(_bus2.start_pg_listen())
    logger.warning("PG NOTIFY/LISTEN cross-node bus scheduled")

    # Seed simulator if agent_scores is empty (cold start)
    async def _seed_simulator_if_empty():
        await _asyncio.sleep(5)  # wait for DB init
        try:
            from .db.migrations import get_db as _sdb

            _db = _sdb()
            _count = _db.execute("SELECT COUNT(*) FROM agent_scores").fetchone()[0]
            _db.close()
            if _count == 0:
                from .agents.simulator import MissionSimulator

                sim = MissionSimulator()
                results = sim.run_all(n_runs_per_workflow=50)
                logger.warning(
                    "Simulator cold-start: seeded %d agent_scores rows",
                    sum(results.values()),
                )
        except Exception as e:
            logger.warning("Simulator cold-start failed: %s", e)

    _asyncio.create_task(_seed_simulator_if_empty())

    # Seed Darwin team_fitness if empty (cold start / fresh deployment)
    async def _seed_darwin_if_empty():
        await _asyncio.sleep(10)  # wait for agents to be seeded first
        try:
            import random as _rand
            from .db.migrations import get_db as _ddb
            from .patterns.team_selector import (
                _get_agents_with_skill,
                _upsert_team_fitness,
                update_team_fitness,
            )

            def _do_seed():
                _db2 = _ddb()
                _cnt = _db2.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
                _has_new_feature = _db2.execute(
                    "SELECT COUNT(*) FROM team_fitness WHERE phase_type='new_feature'"
                ).fetchone()[0]
                if _cnt >= 50 and _has_new_feature >= 10:
                    _db2.close()
                    return 0
                _skills = ["developer", "tester", "security", "devops"]
                _patterns = [
                    "loop",
                    "sequential",
                    "parallel",
                    "hierarchical",
                    "aggregator",
                ]
                _phases = [
                    "new_feature",
                    "bugfix",
                    "refactoring",
                    "migration",
                    "review",
                    "testing",
                    "audit",
                    "design",
                    "docs",
                    "tdd",
                    "feature",
                    "sprint",
                    "deploy",
                    "exploitation",
                    "load",
                    "perf",
                ]
                _techs = ["generic", "python", "typescript", "java", "rust", "go"]
                _seeded = 0
                for _sk in _skills:
                    _agents = _get_agents_with_skill(_db2, _sk)
                    if not _agents:
                        continue
                    for _pt in _patterns[:4]:
                        for _ph in _phases:
                            for _tc in _techs[:3]:
                                for _aid in _agents[:6]:
                                    _upsert_team_fitness(_db2, _aid, _pt, _tc, _ph)
                                    _runs = _rand.randint(5, 15)
                                    _wins = int(_runs * _rand.uniform(0.4, 0.92))
                                    for _r in range(_runs):
                                        update_team_fitness(
                                            _db2,
                                            _aid,
                                            _pt,
                                            _tc,
                                            _ph,
                                            won=(_r < _wins),
                                            iterations=_rand.randint(1, 3),
                                        )
                                        _seeded += 1
                                if _seeded % 1000 == 0:
                                    _db2.commit()
                _db2.commit()
                _after = _db2.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
                _db2.close()
                return _after

            _after = await _asyncio.to_thread(_do_seed)
            if _after:
                logger.warning("Darwin cold-start: seeded %d team_fitness rows", _after)
        except Exception as e:
            logger.warning("Darwin cold-start failed: %s", e)

    _asyncio.create_task(_seed_darwin_if_empty())

    # Start unified MCP SF server (platform + LRM tools merged)
    _mcp_procs: dict[str, Any] = {}

    _mcp_sf_mod = (
        "macaron_platform.mcp_platform.server"
        if Path("/app/macaron_platform").exists()
        else "platform.mcp_platform.server"
    )

    def _kill_port(port: int) -> None:
        """Kill any process holding the given TCP port (best-effort)."""
        import signal as _sig
        import subprocess as _sp

        try:
            # lsof works on Linux/macOS; ss is Linux-only fallback
            result = _sp.run(
                ["lsof", "-t", "-i", f"TCP:{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for pid_str in result.stdout.strip().splitlines():
                try:
                    os.kill(int(pid_str), _sig.SIGTERM)
                    logger.info("Killed PID %s holding port %d", pid_str, port)
                except (ProcessLookupError, ValueError):
                    pass
        except Exception:
            pass  # lsof unavailable — proceed anyway

    def _start_mcp(name: str, module: str, port: int):
        """Kill any leftover process on port, then start an MCP server subprocess."""
        import subprocess as _sp

        _kill_port(port)
        log_file = Path(__file__).parent.parent / "data" / "logs" / f"mcp-{name}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log_file, "a")
        proc = _sp.Popen(
            [sys.executable, "-m", module],
            cwd=str(Path(__file__).parent.parent),
            start_new_session=True,
            stdout=fh,
            stderr=_sp.STDOUT,
        )
        logger.info("MCP %s started (PID %d, port %d)", name, proc.pid, port)
        return proc

    try:
        # Acquire exclusive non-blocking lock so only ONE slot (blue/green)
        # manages the MCP.  Prevents the two uvicorn processes on the same node
        # from killing each other's MCP subprocess.
        import fcntl as _fcntl

        _mcp_lock_path = Path("/tmp/mcp_sf_manager.lock")
        _mcp_lock_fd = None
        try:
            _mcp_lock_fd = open(_mcp_lock_path, "w")
            _fcntl.flock(_mcp_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            _mcp_lock_fd.write(str(os.getpid()))
            _mcp_lock_fd.flush()
            _is_mcp_manager = True
        except (BlockingIOError, OSError):
            _is_mcp_manager = False
            if _mcp_lock_fd:
                _mcp_lock_fd.close()
                _mcp_lock_fd = None

        if _is_mcp_manager:
            logger.info(
                "MCP manager lock acquired (PID %d), starting MCP SF", os.getpid()
            )
            _mcp_procs["sf"] = _start_mcp("sf", _mcp_sf_mod, 9501)
        else:
            logger.info("MCP manager lock held by another slot, skipping MCP startup")
    except Exception as exc:
        logger.warning("MCP SF Server failed to start: %s", exc)
        _is_mcp_manager = False
        _mcp_lock_fd = None

    async def _mcp_watchdog():
        """Auto-restart MCP server if it crashes (manager slot only).
        Re-checks the lock each iteration — if another slot took it over (restart race),
        this watchdog exits gracefully to avoid double-manager conflicts.
        """
        if not _is_mcp_manager:
            return
        while True:
            await asyncio.sleep(15)
            # Verify we still hold the exclusive lock
            if _mcp_lock_fd is not None:
                try:
                    _fcntl.flock(_mcp_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                except (BlockingIOError, OSError):
                    logger.warning(
                        "MCP manager lock lost, stopping watchdog (another slot took over)"
                    )
                    return
            proc = _mcp_procs.get("sf")
            if proc and proc.poll() is not None:
                logger.warning("MCP SF died (exit=%s), restarting...", proc.returncode)
                try:
                    _mcp_procs["sf"] = _start_mcp("sf", _mcp_sf_mod, 9501)
                except Exception as e:
                    logger.error("MCP SF restart failed: %s", e)

    import asyncio

    asyncio.create_task(_mcp_watchdog())

    # Auto-heal loop: scan incidents → create epics → launch TMA workflows
    try:
        from .ops.auto_heal import ENABLED as _ah_enabled
        from .ops.auto_heal import auto_heal_loop

        if _ah_enabled and _mode != "ui":
            asyncio.create_task(auto_heal_loop())
            logger.info("Auto-heal loop enabled")
        elif _mode == "ui":
            logger.info("Auto-heal loop SKIPPED (PLATFORM_MODE=ui)")
    except Exception as e:
        logger.warning("Auto-heal loop failed to start: %s", e)

    # Platform quality watchdog: detect false-positive completions → trigger quality-improvement
    try:
        from .ops.platform_watchdog import ENABLED as _pw_enabled
        from .ops.platform_watchdog import platform_watchdog_loop

        if _pw_enabled and _mode != "ui":
            asyncio.create_task(platform_watchdog_loop())
            logger.warning("Platform quality watchdog enabled")
        elif _mode == "ui":
            logger.warning("Platform watchdog SKIPPED (PLATFORM_MODE=ui)")
    except Exception as e:
        logger.warning("Platform watchdog failed to start: %s", e)

    # Traceability scheduler — periodic SAFe traceability audit on all projects
    try:
        from .ops.traceability_scheduler import ENABLED as _trace_enabled
        from .ops.traceability_scheduler import traceability_scheduler_loop

        if _trace_enabled and _mode != "ui":
            asyncio.create_task(traceability_scheduler_loop())
            logger.info("Traceability scheduler started")
        elif _mode == "ui":
            logger.info("Traceability scheduler SKIPPED (PLATFORM_MODE=ui)")
    except Exception as e:
        logger.warning("Traceability scheduler failed to start: %s", e)

    # Knowledge scheduler — nightly knowledge maintenance on all projects (04:00 UTC)
    try:
        from .ops.knowledge_scheduler import knowledge_scheduler_loop

        if _mode != "ui":
            asyncio.create_task(knowledge_scheduler_loop())
            logger.info("Knowledge scheduler started (nightly 04:00 UTC)")
        else:
            logger.info("Knowledge scheduler SKIPPED (PLATFORM_MODE=ui)")
    except Exception as e:
        logger.warning("Knowledge scheduler failed to start: %s", e)

    # Log paused missions (no auto-resume — paused missions stay paused until manually restarted)
    try:
        from .epics.store import get_epic_run_store

        _mrs = get_epic_run_store()
        _all_runs = _mrs.list_runs(limit=50)
        _paused = [m for m in _all_runs if m.status.value == "paused"]
        if _paused:
            logger.warning(
                "Found %d paused missions (restart manually if needed): %s",
                len(_paused),
                [m.id for m in _paused],
            )
    except Exception as exc:
        logger.warning("Mission check failed: %s", exc)

    # Load persisted browser push subscriptions
    try:
        from .web.routes.api.push import _get_db_subscriptions
        from .services.notification_service import get_notification_service as _get_ns

        _push_subs = _get_db_subscriptions()
        _get_ns().load_push_subscriptions(_push_subs)
        if _push_subs:
            logger.info("Loaded %d browser push subscriptions", len(_push_subs))
    except Exception as exc:
        logger.warning("Failed to load push subscriptions: %s", exc)

    # Node heartbeat: register this node in platform_nodes every 30s
    # Only "full" (master) nodes self-register — slave/ui/factory containers
    # are deployed apps and must not pollute the cluster node list.
    import os as _os_hb
    import socket as _socket_hb

    _hb_mode = os.environ.get("PLATFORM_MODE", "full").lower()
    _hb_role = "master" if _hb_mode == "full" else "slave"

    if _hb_mode != "full":
        logger.debug("Node heartbeat disabled (PLATFORM_MODE=%s)", _hb_mode)
    else:
        _hb_node_id = (
            _os_hb.environ.get("SF_NODE_ID")
            or _os_hb.environ.get("HOSTNAME")
            or _socket_hb.gethostname()
        )
        _hb_url = _os_hb.environ.get("SF_NODE_URL", "")
        try:
            import subprocess as _sp

            _hb_version = (
                _sp.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], stderr=_sp.DEVNULL
                )
                .decode()
                .strip()
            )
        except Exception:
            _hb_version = ""

        async def _node_heartbeat_loop():
            import asyncio as _aio
            import psutil as _psu
            from .db.migrations import get_db as _get_db

            while True:
                try:
                    _cpu = _psu.cpu_percent(interval=None)
                    _mem = _psu.virtual_memory().percent
                    _db = _get_db()
                    try:
                        _db.execute(
                            """
                            INSERT INTO platform_nodes (node_id, role, mode, url, last_seen, status, cpu_pct, mem_pct, version)
                            VALUES (?, ?, ?, ?, NOW(), 'online', ?, ?, ?)
                            ON CONFLICT(node_id) DO UPDATE SET
                                role=EXCLUDED.role, mode=EXCLUDED.mode, url=EXCLUDED.url,
                                last_seen=NOW(), status='online',
                                cpu_pct=EXCLUDED.cpu_pct, mem_pct=EXCLUDED.mem_pct, version=EXCLUDED.version
                        """,
                            (
                                _hb_node_id,
                                _hb_role,
                                _hb_mode,
                                _hb_url,
                                _cpu,
                                _mem,
                                _hb_version,
                            ),
                        )
                        _db.commit()
                        # Purge stale nodes (not seen in 5 min) every heartbeat cycle
                        try:
                            _db2 = _get_db()
                            _db2.execute(
                                "DELETE FROM platform_nodes WHERE last_seen < NOW() - INTERVAL '5 minutes'"
                            )
                            _db2.commit()
                            _db2.close()
                        except Exception:
                            pass
                    finally:
                        _db.close()
                except Exception as _e:
                    logger.debug("Node heartbeat failed: %s", _e)
                await _aio.sleep(
                    int(_os_hb.environ.get("SF_HEARTBEAT_INTERVAL_S", "10"))
                )

        asyncio.create_task(_node_heartbeat_loop())
        logger.info(
            "Node heartbeat started: %s (%s/%s)", _hb_node_id, _hb_role, _hb_mode
        )

    yield

    # Stop MCP servers
    import os as _os

    for name, proc in _mcp_procs.items():
        if proc and proc.poll() is None:
            try:
                _os.killpg(_os.getpgid(proc.pid), 15)
            except Exception:
                proc.terminate()
            logger.info("MCP %s stopped", name)

    # Cleanup LLM client
    try:
        from .llm.client import get_llm_client

        await get_llm_client().close()
    except Exception:
        pass

    logger.info("Platform shut down")


def _record_incident(path: str, status_code: int, detail: str = ""):
    """Record a platform incident with deduplication: one open incident per (error_type, error_detail)."""
    import uuid

    from .db.adapter import get_connection

    error_type = str(status_code)
    error_detail = detail or f"HTTP {status_code} on {path}"
    title = f"[Auto] {error_type} — {path}"

    try:
        conn = get_connection()
        # Deduplicate: increment existing open incident instead of creating a new one
        existing = conn.execute(
            "SELECT id FROM platform_incidents WHERE error_type=? AND error_detail=? AND status='open' LIMIT 1",
            (error_type, error_detail),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE platform_incidents SET count=count+1, last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                (existing[0],),
            )
        else:
            conn.execute(
                "INSERT INTO platform_incidents (id, title, severity, status, source, error_type, error_detail, count, last_seen_at) "
                "VALUES (?, ?, 'P3', 'open', 'auto', ?, ?, 1, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4())[:12], title, error_type, error_detail),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Software Factory",
        description="Multi-Agent Software Factory — 94 AI agents orchestrating the full product lifecycle with SAFe, TDD, and auto-heal.",
        version="1.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Security: Auth middleware (API key) ────────────────────────────────
    from .security import AuthMiddleware

    app.add_middleware(AuthMiddleware)

    # ── Security: CORS ──────────────────────────────────────────────────────
    from starlette.middleware.cors import CORSMiddleware

    _cors_origins = os.environ.get(
        "CORS_ORIGINS", "http://localhost:8090,http://4.233.64.30"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _cors_origins],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Trace-ID",
            "X-Requested-With",
        ],
        allow_credentials=True,
    )

    # ── Custom error pages ──────────────────────────────────────────────────
    from fastapi import Request as _Request
    from fastapi.responses import HTMLResponse as _HTMLResponse
    from starlette.exceptions import HTTPException as _StarletteHTTPException

    def _error_html(code: int, title: str, message: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{code} — Software Factory</title>
  <script>document.documentElement.setAttribute('data-theme', localStorage.getItem('macaron_theme') || 'dark')</script>
  <link rel="stylesheet" href="/static/css/main.css">
  <style>
    .err-wrap{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;gap:1.2rem;text-align:center;padding:2rem}}
    .err-code{{font-size:5rem;font-weight:800;color:var(--purple);line-height:1}}
    .err-title{{font-size:1.5rem;font-weight:600;color:var(--text-primary)}}
    .err-msg{{color:var(--text-secondary);max-width:36rem;line-height:1.6}}
    .err-actions{{display:flex;gap:0.75rem;flex-wrap:wrap;justify-content:center;margin-top:0.5rem}}
    .err-btn{{padding:0.5rem 1.2rem;border-radius:6px;font-size:0.9rem;cursor:pointer;border:none}}
    .err-btn-primary{{background:var(--purple);color:var(--text-on-accent)}}
    .err-btn-secondary{{background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border)}}
  </style>
</head>
<body>
  <div class="err-wrap">
    <div class="err-code">{code}</div>
    <div class="err-title">{title}</div>
    <div class="err-msg">{message}</div>
    <div class="err-actions">
      <button class="err-btn err-btn-primary" onclick="history.back()">← Go back</button>
      <button class="err-btn err-btn-secondary" onclick="location.href='/'">Home</button>
    </div>
  </div>
</body>
</html>"""

    @app.exception_handler(_StarletteHTTPException)
    async def http_exception_handler(request: _Request, exc: _StarletteHTTPException):
        # JSON API routes: return JSON
        if request.url.path.startswith(
            "/api/"
        ) or "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.status_code == 404:
            html = _error_html(
                404,
                "Page not found",
                "The page you're looking for doesn't exist or has been moved.",
            )
        else:
            html = _error_html(
                exc.status_code,
                "Unexpected error",
                "A temporary error occurred. We've been notified and are working on it — please try again in a few minutes.",
            )
        return _HTMLResponse(html, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: _Request, exc: Exception):
        if request.url.path.startswith(
            "/api/"
        ) or "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        html = _error_html(
            500,
            "Temporary error",
            "Something went wrong on our end. We've been notified and are working on it — please try again in a few minutes.",
        )
        return _HTMLResponse(html, status_code=500)

    # ── Security: Response headers ──────────────────────────────────────────
    @app.middleware("http")
    async def cache_headers(request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/"):
            # Versioned static assets: long cache (query string ?v= busts cache)
            if "v=" in str(request.url.query):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        path = request.url.path
        # Workspace pages need iframes (preview, dbgate, portainer)
        if path.startswith("/projects/") and path.endswith("/workspace"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://analytics.macaron-software.com; "
                "style-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' https://analytics.macaron-software.com; "
                "frame-src 'self' http://localhost:* http://127.0.0.1:* https:; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://analytics.macaron-software.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://api.dicebear.com https://avatars.githubusercontent.com https://i.pravatar.cc https://cdn.simpleicons.org; "
                "connect-src 'self' https://analytics.macaron-software.com; "
                "frame-ancestors 'none'"
            )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ── Rate limiting (API endpoints, 60 req/min per IP) ───────────────
    import time as _rl_time
    from collections import defaultdict as _dd

    _rate_buckets: dict[str, list[float]] = _dd(list)
    _RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "300"))  # per minute
    _RATE_WINDOW = 60.0
    # Lightweight UI-polling endpoints exempt from rate limiting
    _RATE_EXEMPT = {
        "/api/notifications/badge",
        "/api/autoheal/heartbeat",
        "/api/cto/chips",
        "/api/health",
    }

    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        if (
            request.url.path.startswith("/api/")
            and request.url.path not in _RATE_EXEMPT
            and os.environ.get("PLATFORM_ENV") != "test"
        ):
            client_ip = request.client.host if request.client else "unknown"
            now = _rl_time.time()
            bucket = _rate_buckets[client_ip]
            bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW]
            if len(bucket) >= _RATE_LIMIT:
                from starlette.responses import JSONResponse as _JR

                return _JR(
                    {"error": "rate_limit_exceeded", "retry_after": 60}, status_code=429
                )
            bucket.append(now)
        return await call_next(request)

    # ── Trace ID middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def trace_id_middleware(request, call_next):
        import uuid as _uuid

        from .log_config import trace_id_var

        tid = request.headers.get("X-Trace-ID", str(_uuid.uuid4())[:8])
        token = trace_id_var.set(tid)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = tid
        trace_id_var.reset(token)
        return response

    # ── Auth: setup wizard redirect + enforcement ──────────────────────
    _setup_checked = False

    @app.middleware("http")
    async def auth_middleware(request, call_next):
        """Enforce authentication: setup redirect + login required on all routes."""
        nonlocal _setup_checked
        path = request.url.path

        # ── Phase 1: Setup wizard redirect ──
        _is_test = os.environ.get("PLATFORM_ENV") == "test"
        if not _setup_checked and not _is_test:
            skip_setup = (
                path.startswith("/static")
                or path.startswith("/api/auth")
                or path
                in (
                    "/setup",
                    "/health",
                    "/favicon.ico",
                    "/manifest.json",
                    "/sw.js",
                    "/api/health",
                )
            )
            if not skip_setup:
                try:
                    from .auth.middleware import is_setup_needed

                    if is_setup_needed():
                        from starlette.responses import RedirectResponse

                        return RedirectResponse(url="/setup", status_code=302)
                    _setup_checked = True
                except Exception:
                    pass

        # ── Phase 2: Auth enforcement ──
        from .auth.middleware import is_public_path

        if path.startswith("/api/analytics") or path.startswith("/api/health"):
            return await call_next(request)

        # A2A endpoints — require auth (cookie) but not onboarding
        # The /.well-known path is fully public (no auth required)

        # Skip auth in test mode
        if os.environ.get("PLATFORM_ENV") == "test":
            return await call_next(request)

        if not is_public_path(path) and not path.startswith("/static"):
            from .auth.middleware import get_current_user

            user = await get_current_user(request)
            if user is None:
                if path.startswith("/api/"):
                    return JSONResponse(
                        {"detail": "Authentication required"}, status_code=401
                    )
                # HTMX partial requests return 401 + HX-Redirect (avoids HTMX inserting login page)
                if request.headers.get("HX-Request") == "true":
                    from starlette.responses import Response

                    return Response(
                        status_code=401,
                        headers={"HX-Redirect": f"/login?next={path}"},
                    )
                from starlette.responses import RedirectResponse

                return RedirectResponse(url=f"/login?next={path}", status_code=302)
            request.state.user = user

        return await call_next(request)

    # ── Onboarding redirect (first-time users) ──────────────────────────
    @app.middleware("http")
    async def onboarding_middleware(request, call_next):
        """Redirect to /onboarding if user hasn't completed it."""
        path = request.url.path
        skip = (
            path.startswith("/static")
            or path.startswith("/api/")
            or path.startswith("/auth/")
            or path.startswith("/.well-known")
            or path.startswith("/a2a/")
            or path.startswith("/projects/")
            and "/preview/" in path
            or path
            in (
                "/login",
                "/setup",
                "/onboarding",
                "/health",
                "/favicon.ico",
                "/manifest.json",
                "/sw.js",
                "/openapi.json",
                "/docs",
                "/redoc",
            )
        )
        # HTMX partial requests should never be redirected to onboarding
        is_htmx = request.headers.get("HX-Request") == "true"
        if (
            not skip
            and not is_htmx
            and not request.cookies.get("onboarding_done")
            and os.environ.get("PLATFORM_ENV") != "test"
        ):
            from starlette.responses import RedirectResponse

            return RedirectResponse(url="/onboarding", status_code=302)
        return await call_next(request)

    # ── Locale detection middleware ─────────────────────────────────────
    SUPPORTED_LOCALES = {"en", "fr", "es", "it", "de", "pt", "ja", "zh"}

    @app.middleware("http")
    async def locale_middleware(request, call_next):
        """Detect and set user locale from Accept-Language header or cookie."""
        import re as _locale_re

        # Priority: 1) Accept-Language header 2) Cookie fallback 3) Default 'en'
        # (Accept-Language always wins so the display follows the browser automatically)
        locale = None

        # Parse Accept-Language header first
        accept_lang = request.headers.get("Accept-Language", "")
        if accept_lang:
            langs = []
            for part in accept_lang.split(","):
                match = _locale_re.match(
                    r"([a-z]{2})(?:-[A-Z]{2})?(?:;q=([\d.]+))?", part.strip()
                )
                if match:
                    lang_code = match.group(1)
                    quality = float(match.group(2) or "1.0")
                    langs.append((quality, lang_code))
            langs.sort(reverse=True)
            for _, lang_code in langs:
                if lang_code in SUPPORTED_LOCALES:
                    locale = lang_code
                    break

        # Fallback: cookie (explicit user override) if no browser lang matched
        if not locale:
            cookie_lang = request.cookies.get("sf_lang")
            if cookie_lang and cookie_lang in SUPPORTED_LOCALES:
                locale = cookie_lang

        # Fallback to English
        if not locale:
            locale = "en"

        # Set in request state for templates
        request.state.lang = locale

        # Inject current user into request state for templates
        if not hasattr(request.state, "user"):
            try:
                from .auth.middleware import get_current_user as _get_user

                request.state.user = await _get_user(request)
            except Exception:
                request.state.user = None

        response = await call_next(request)

        # Don't persist cookie — browser language is the source of truth now.
        # Cookie is only set by explicit user action via the language selector JS.

        return response

    # ── SAFe perspective middleware ─────────────────────────────────────
    SAFE_PERSPECTIVES = {
        "overview",
        "dsi",
        "portfolio_manager",
        "rte",
        "product_owner",
        "scrum_master",
        "developer",
        "architect",
        "qa_security",
        "business_owner",
        "admin",
    }

    @app.middleware("http")
    async def perspective_middleware(request, call_next):
        """Read SAFe perspective from cookie and inject into request state."""
        perspective = request.cookies.get("safe_perspective", "")
        if perspective not in SAFE_PERSPECTIVES:
            perspective = "admin"  # default: see everything
        request.state.perspective = perspective
        return await call_next(request)

    # Metrics + incident middleware
    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        import time as _t

        _start = _t.time()
        try:
            response = await call_next(request)
            _dur = (_t.time() - _start) * 1000
            # Track request metrics
            try:
                from .metrics.collector import get_collector

                get_collector().track_request(
                    request.method,
                    request.url.path,
                    response.status_code,
                    _dur,
                )
            except Exception:
                pass
            # Record incidents for 500+
            if response.status_code >= 500:
                _record_incident(request.url.path, response.status_code)
            return response
        except Exception as e:
            _record_incident(request.url.path, 500, str(e))
            raise

    # Static files
    _mode = os.environ.get("PLATFORM_MODE", "full").lower()
    if _mode != "factory":
        if STATIC_DIR.exists():
            app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve manifest.json for PWA
    @app.get("/manifest.json")
    async def pwa_manifest():
        from fastapi.responses import FileResponse

        manifest_path = STATIC_DIR / "manifest.json"
        if manifest_path.exists():
            return FileResponse(
                str(manifest_path), media_type="application/manifest+json"
            )
        return {"error": "manifest not found"}

    @app.get("/sw.js")
    async def service_worker():
        from fastapi.responses import FileResponse

        sw_path = STATIC_DIR / "sw.js"
        if sw_path.exists():
            return FileResponse(
                str(sw_path),
                media_type="application/javascript",
                headers={"Service-Worker-Allowed": "/"},
            )

    # Serve favicon.ico
    @app.get("/favicon.ico")
    async def favicon():
        from fastapi.responses import FileResponse

        favicon_path = STATIC_DIR / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(str(favicon_path), media_type="image/x-icon")
        return FileResponse(str(favicon_path))  # 404 handled by FastAPI

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    # Add markdown filter for chat rendering (with LLM artifact stripping)
    import re as _re

    import markdown as _md_lib

    def _clean_llm(text: str) -> str:
        t = str(text or "")
        t = _re.sub(r"<think>[\s\S]*?</think>", "", t)
        t = _re.sub(r"<think>[\s\S]*$", "", t)
        t = _re.sub(r"\[TOOL_CALL\][\s\S]*?\[/TOOL_CALL\]", "", t)
        t = _re.sub(r"\[TOOL_CALL\][\s\S]*$", "", t)
        t = _re.sub(r"\[(DELEGATE|VETO|APPROVE|ASK|ESCALATE)[^\]]*\]", "", t)
        return t.strip()

    def _render_screenshots(html: str) -> str:
        """Convert [SCREENSHOT:path] markers to inline <img> tags."""

        def _shot_repl(m):
            p = m.group(1).strip().lstrip("./")
            src = f"/workspace/{p}"
            return (
                f'<div class="mc-screenshot">'
                f'<img src="{src}" alt="Screenshot" loading="lazy" '
                f'style="max-width:100%;border-radius:var(--radius-lg);margin:0.5rem 0;border:1px solid var(--border-subtle);cursor:pointer" '
                f'onclick="window.open(this.src)">'
                f'<div style="font-size:0.65rem;color:var(--text-tertiary);margin-top:2px">{p}</div>'
                f"</div>"
            )

        return _re.sub(r"\[SCREENSHOT:([^\]]+)\]", _shot_repl, html)

    def _markdown_filter(text):
        html = _md_lib.markdown(
            _clean_llm(text), extensions=["fenced_code", "tables", "nl2br"]
        )
        return _render_screenshots(html)

    templates.env.filters["markdown"] = _markdown_filter

    def _avatar_color(email: str) -> str:
        """Deterministic HSL color from email hash."""
        h = sum(ord(c) * (i + 1) for i, c in enumerate(str(email))) % 360
        return f"hsl({h},55%,42%)"

    def _relative_time(ts) -> str:
        """Human-readable relative time from ISO timestamp string."""
        from datetime import datetime, timezone

        if not ts:
            return "—"
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            diff = (datetime.now(timezone.utc) - dt).total_seconds()
            if diff < 60:
                return "just now"
            if diff < 3600:
                return f"{int(diff // 60)}m ago"
            if diff < 86400:
                return f"{int(diff // 3600)}h ago"
            if diff < 2592000:
                return f"{int(diff // 86400)}d ago"
            return str(ts)[:10]
        except Exception:
            return str(ts)[:10]

    templates.env.filters["avatar_color"] = _avatar_color
    templates.env.filters["relative_time"] = _relative_time

    def _ts_filter(value, fmt: str = "datetime") -> str:
        """Normalize datetime/string timestamp for safe display in templates.

        Handles both str (SQLite) and datetime objects (PostgreSQL psycopg2).
        Usage in templates:
          {{ obj.created_at | ts }}          → "2024-01-01 12:34"
          {{ obj.created_at | ts('date') }}  → "2024-01-01"
          {{ obj.created_at | ts('%d/%m') }} → "01/01"
        """
        if not value:
            return "—"
        from datetime import datetime, date

        if isinstance(value, (datetime, date)):
            if fmt == "date":
                return value.strftime("%Y-%m-%d")
            if fmt == "datetime":
                return value.strftime("%Y-%m-%d %H:%M")
            return value.strftime(fmt)
        s = str(value)
        if fmt == "date":
            return s[:10]
        if fmt == "datetime":
            return s[:16].replace("T", " ")
        # Custom strftime: parse then format
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
            return dt.strftime(fmt)
        except Exception:
            return s[:16]

    templates.env.filters["ts"] = _ts_filter

    # i18n — make _() available in all templates
    from .i18n import SUPPORTED_LANGS, _catalog
    from .i18n import get_lang as _get_lang
    from .i18n import t as _translate

    def _i18n_global(key: str, **kwargs):
        """Template global: {{ _('key', name='val') }}"""
        return _translate(key, lang=_i18n_global._current_lang, **kwargs)

    _i18n_global._current_lang = "en"

    def _i18n_catalog_global():
        """Return current lang's i18n catalog for JS injection."""
        return _catalog.get(_i18n_global._current_lang, _catalog.get("en", {}))

    templates.env.globals["_"] = _i18n_global
    templates.env.globals["i18n_catalog"] = _i18n_catalog_global()
    templates.env.globals["SUPPORTED_LANGS"] = SUPPORTED_LANGS

    # Version + git commit for header display
    import subprocess as _sp
    from pathlib import Path as _Path

    _ver_file = _Path(__file__).parent / "VERSION"
    if _ver_file.exists():
        _parts = _ver_file.read_text().strip().split(":")
        _tag, _sha = (
            (_parts[0], _parts[1]) if len(_parts) == 2 else (_parts[0], _parts[0])
        )
    else:
        try:
            _sha = (
                _sp.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], stderr=_sp.DEVNULL
                )
                .decode()
                .strip()
            )
            _tag = (
                _sp.check_output(
                    ["git", "describe", "--tags", "--abbrev=0"], stderr=_sp.DEVNULL
                )
                .decode()
                .strip()
            )
        except Exception:
            _sha, _tag = "unknown", ""
    templates.env.globals["app_commit"] = _sha
    templates.env.globals["app_version"] = _tag or _sha
    # Simple UI mode — stripped-down sidebar for single-project instances
    templates.env.globals["simple_ui"] = os.environ.get("PLATFORM_UI_SIMPLE", "").lower() in ("1", "true", "yes")
    templates.env.globals["instance_name"] = os.environ.get("PLATFORM_INSTANCE_NAME", "")
    templates.env.globals["instance_peer_url"] = os.environ.get("PLATFORM_INSTANCE_PEER_URL", "")

    # Middleware to set current language per-request
    from starlette.middleware.base import BaseHTTPMiddleware

    class I18nMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            lang = _get_lang(request)
            _i18n_global._current_lang = lang
            # Update JS catalog for current lang
            templates.env.globals["i18n_catalog"] = _catalog.get(
                lang, _catalog.get("en", {})
            )
            request.state.lang = lang
            response = await call_next(request)
            return response

    app.add_middleware(I18nMiddleware)

    # ── OpenTelemetry ASGI middleware (last = runs first) ────────────────────
    if _otel_provider is not None:
        try:
            from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

            app.add_middleware(OpenTelemetryMiddleware, tracer_provider=_otel_provider)
        except ImportError:
            pass

    # Mount Prometheus /metrics endpoint if meter provider initialized
    if _otel_meter_provider is not None:
        try:
            from .metrics.collector import get_collector as _get_collector
            from fastapi import Response as _Response

            @app.get("/api/metrics/prometheus", include_in_schema=False)
            async def prometheus_metrics():
                """Live Prometheus scrape endpoint — reads MetricsCollector snapshot."""
                snap = _get_collector().snapshot()
                lines = [
                    "# HELP macaron_http_requests_total Total HTTP requests",
                    "# TYPE macaron_http_requests_total gauge",
                    f"macaron_http_requests_total {snap['http']['total_requests']}",
                    "# HELP macaron_http_errors_total Total HTTP errors (4xx+5xx)",
                    "# TYPE macaron_http_errors_total gauge",
                    f"macaron_http_errors_total {snap['http']['total_errors']}",
                    "# HELP macaron_http_latency_avg_ms Average HTTP latency ms",
                    "# TYPE macaron_http_latency_avg_ms gauge",
                    f"macaron_http_latency_avg_ms {snap['http']['avg_ms']}",
                    "# HELP macaron_mcp_calls_total Total MCP tool calls",
                    "# TYPE macaron_mcp_calls_total gauge",
                    f"macaron_mcp_calls_total {snap['mcp']['total_calls']}",
                    "# HELP macaron_llm_cost_usd_total Cumulative LLM cost USD",
                    "# TYPE macaron_llm_cost_usd_total gauge",
                    f"macaron_llm_cost_usd_total {snap['llm_costs']['total_usd']}",
                    "# HELP macaron_db_queries_total Total DB queries",
                    "# TYPE macaron_db_queries_total gauge",
                    f"macaron_db_queries_total {snap['db_queries']['total']}",
                    "# HELP macaron_uptime_seconds Process uptime seconds",
                    "# TYPE macaron_uptime_seconds gauge",
                    f"macaron_uptime_seconds {snap['uptime_seconds']}",
                ]
                return _Response(
                    "\n".join(lines) + "\n", media_type="text/plain; version=0.0.4"
                )
        except Exception:
            pass

    app.state.templates = templates if _mode != "factory" else None

    # Routes — core (skipped in factory mode)
    from .web.routes.auth import router as auth_router
    from .web.ws import router as sse_router

    app.include_router(auth_router)
    from .web.routes.api.health import router as health_router

    app.include_router(health_router)

    # A2A (Agent-to-Agent) Protocol Server
    from .web.routes.a2a_server import router as a2a_router

    app.include_router(a2a_router)

    # slave mode: API-only, no IHM (web UI), no SSE write endpoints
    if _mode not in ("factory", "slave"):
        from .web.routes import router as web_router

        app.include_router(web_router)
    if _mode != "slave":
        app.include_router(sse_router, prefix="/sse")

    # Routes — optional (safe mode: import failures are logged, not fatal)
    _loaded_modules: list[str] = []
    _failed_modules: list[str] = []

    _OPTIONAL_ROUTERS: list[tuple[str, str, dict]] = [
        ("mercato", ".web.routes.mercato", {}),
        ("oauth", ".web.routes.oauth", {}),
        ("websocket", ".web.routes.websocket", {}),
        ("dag", ".web.routes.dag", {}),
        ("evolution", ".web.routes.evolution", {}),
        ("push", ".web.routes.api.push", {}),
        ("tasks", ".web.routes.api.tasks", {}),
        ("modules", ".web.routes.api.modules", {}),
        ("traceability", ".web.routes.api.traceability", {}),
        ("skill-eval", ".web.routes.api.skill_eval", {}),
        ("mkt_ideation", ".web.routes.mkt_ideation", {}),
        ("group_ideation", ".web.routes.group_ideation", {}),
    ]

    for _mod_name, _mod_path, _kwargs in _OPTIONAL_ROUTERS:
        try:
            import importlib as _imp

            _pkg = __name__.rsplit(".", 1)[0]
            _m = _imp.import_module(_mod_path, package=_pkg)
            app.include_router(_m.router, **_kwargs)
            _loaded_modules.append(_mod_name)
        except Exception as _exc:
            _failed_modules.append(_mod_name)
            logger.warning("Optional module '%s' failed to load: %s", _mod_name, _exc)

    # Store module load status on app state for /api/health/modules
    app.state.loaded_modules = _loaded_modules
    app.state.failed_modules = _failed_modules
    if _failed_modules:
        logger.warning(
            "Safe mode: %d module(s) skipped: %s", len(_failed_modules), _failed_modules
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "platform.server:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=cfg.server.reload,
    )
