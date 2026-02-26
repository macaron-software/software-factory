"""Software Factory — FastAPI web server.

Serves the HTMX-based UI with SSE real-time updates.
Runs on port 8090 (separate from Factory dashboard on 8080).
"""

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
if os.environ.get("OTEL_ENABLED"):
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        _otel_resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "macaron-platform"),
                "service.version": "1.2.0",
                "deployment.environment": os.environ.get("PLATFORM_ENV", "production"),
            }
        )
        _otel_provider = TracerProvider(resource=_otel_resource)

        _otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            _http_ep = _otlp_endpoint.replace(":4317", ":4318")
            _traces_ep = _http_ep + "/v1/traces"
            _otel_provider.add_span_processor(
                SimpleSpanProcessor(OTLPSpanExporter(endpoint=_traces_ep))
            )
            logger.warning("OTEL: exporting traces to %s", _traces_ep)
        except ImportError:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            _otel_provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
            logger.warning("OTEL: OTLP exporter not available, using console")

        trace.set_tracer_provider(_otel_provider)

        import atexit

        atexit.register(_otel_provider.shutdown)

        logger.warning(
            "OpenTelemetry tracing enabled (service: %s)",
            _otel_resource.attributes.get("service.name"),
        )
    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    from .log_config import setup_logging

    setup_logging(level=os.environ.get("LOG_LEVEL", "WARNING"))

    cfg = get_config()
    logger.info("Starting Software Factory on port %s", cfg.server.port)
    init_db()

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

    # Seed projects from SF/MF registry into DB
    from .projects.manager import get_project_store

    ps = get_project_store()
    ps.seed_from_registry()

    # Auto-provision TMA/Security/Debt missions for projects missing them
    from .missions.store import MissionDef, get_mission_store

    ms = get_mission_store()
    all_missions = ms.list_missions(limit=500)
    _prov_count = 0
    for proj in ps.list_all():
        proj_missions = [m for m in all_missions if m.project_id == proj.id]
        has_tma = any(
            m.type == "program" or m.name.startswith("TMA") or "[TMA" in m.name
            for m in proj_missions
        )
        if not has_tma:
            try:
                ps.auto_provision(proj.id, proj.name)
                _prov_count += 1
            except Exception as e:
                logger.warning("auto_provision failed for %s: %s", proj.id, e)
        else:
            # Ensure security mission exists even if TMA already present
            has_secu = any(
                m.type == "security" or m.name.startswith("Sécu") for m in proj_missions
            )
            if not has_secu:
                try:
                    ms.create_mission(
                        MissionDef(
                            name=f"Sécurité — {proj.name}",
                            type="security",
                            status="active",
                            project_id=proj.id,
                            workflow_id="review-cycle",
                            wsjf_score=12,
                            created_by="devsecops",
                            config={"auto_provisioned": True, "schedule": "weekly"},
                            description=f"Audit sécurité périodique pour {proj.name}.",
                            goal="Score sécurité ≥ 80%, zéro CVE critique.",
                        )
                    )
                    _prov_count += 1
                except Exception as e:
                    logger.warning("security provision failed for %s: %s", proj.id, e)
    if _prov_count:
        logger.warning(
            "Auto-provisioned TMA/Security/Debt for %d projects", _prov_count
        )

    # Seed memory (global knowledge + project files)
    from .memory.seeder import seed_all as seed_memories

    n_mem = seed_memories()
    if n_mem:
        logger.info("Seeded %d memories", n_mem)

    # Seed org tree (Portfolio → ART → Team)
    from .agents.org import get_org_store

    get_org_store().seed_default()
    get_org_store().seed_additional_teams()

    # Demo mode: seed sample data when no LLM keys configured
    from .demo import seed_demo_data

    seed_demo_data()

    # Sync agent models: ensure DB agents match the current DEFAULT_MODEL
    from .agents.store import DEFAULT_MODEL as _current_model

    try:
        from .db.migrations import get_db as _gdb_sync

        _sdb = _gdb_sync()
        # Only update agents that have a stale/wrong model (not matching env)
        _stale_models = _sdb.execute(
            "SELECT COUNT(*) FROM agents WHERE model != ? AND model NOT IN ('', 'demo-model')",
            (_current_model,),
        ).fetchone()[0]
        if _stale_models:
            _sdb.execute(
                "UPDATE agents SET model = ? WHERE model != ? AND model NOT IN ('', 'demo-model')",
                (_current_model, _current_model),
            )
            _sdb.commit()
            logger.warning(
                "Synced %d agents to DEFAULT_MODEL=%s (from env/provider settings)",
                _stale_models,
                _current_model,
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

    # Reset stale "running" mission_runs (orphaned after container restart)
    from .missions.store import get_mission_run_store

    _mrs = get_mission_run_store()
    try:
        from .db.migrations import get_db as _gdb

        _rdb = _gdb()
        _stale = _rdb.execute(
            "UPDATE mission_runs SET status='paused' WHERE status='running'"
        ).rowcount
        # Also fix phases stuck at "running" inside phases_json
        _stuck_phases = 0
        _rows = _rdb.execute(
            "SELECT id, phases_json FROM mission_runs WHERE phases_json LIKE '%\"running\"%'"
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
                    "UPDATE mission_runs SET phases_json=? WHERE id=?",
                    (_json.dumps(_phases, default=str), _row[0]),
                )
        _rdb.commit()
        _rdb.close()
        if _stale or _stuck_phases:
            logger.warning(
                "Reset %d stale mission_runs to paused, fixed %d stuck running phases",
                _stale,
                _stuck_phases,
            )
    except Exception as e:
        logger.warning("Failed to reset stale missions: %s", e)

    # Auto-resume watchdog: handles paused/failed runs + launches unstarted continuous missions
    import asyncio as _asyncio
    from .services.auto_resume import auto_resume_missions as _auto_resume_missions

    _asyncio.create_task(_auto_resume_missions())
    logger.warning("Auto-resume watchdog scheduled")

    # Start endurance watchdog (continuous auto-resume, session recovery, health)
    try:
        from .ops.endurance_watchdog import watchdog_loop, ENABLED as _wd_enabled

        if _wd_enabled:
            _asyncio.create_task(watchdog_loop())
            logger.info("Endurance watchdog started as background task")
    except Exception as e:
        logger.warning("Failed to start endurance watchdog: %s", e)

    # Start evolution scheduler (nightly GA + RL retraining at 02:00 UTC)
    try:
        from .agents.evolution_scheduler import start_evolution_scheduler as _evo_sched

        _asyncio.create_task(_evo_sched())
        logger.info("Evolution scheduler started as background task")
    except Exception as e:
        logger.warning("Failed to start evolution scheduler: %s", e)

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

            _db2 = _ddb()
            _cnt = _db2.execute("SELECT COUNT(*) FROM team_fitness").fetchone()[0]
            _has_new_feature = _db2.execute(
                "SELECT COUNT(*) FROM team_fitness WHERE phase_type='new_feature'"
            ).fetchone()[0]
            if _cnt >= 50 and _has_new_feature >= 10:
                _db2.close()
                return
            _skills = ["developer", "tester", "security", "devops"]
            _patterns = ["loop", "sequential", "parallel", "hierarchical", "aggregator"]
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
                    for _ph in _phases:  # all phases
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
        _mcp_procs["sf"] = _start_mcp("sf", _mcp_sf_mod, 9501)
    except Exception as exc:
        logger.warning("MCP SF Server failed to start: %s", exc)

    async def _mcp_watchdog():
        """Auto-restart MCP server if it crashes."""
        while True:
            await asyncio.sleep(30)
            proc = _mcp_procs.get("sf")
            if proc and proc.poll() is not None:
                logger.warning("MCP SF died (exit=%s), restarting...", proc.returncode)
                await asyncio.sleep(3)  # wait for port to be released
                try:
                    _mcp_procs["sf"] = _start_mcp("sf", _mcp_sf_mod, 9501)
                except Exception as e:
                    logger.error("MCP SF restart failed: %s", e)

    import asyncio

    asyncio.create_task(_mcp_watchdog())

    # Periodic WAL checkpoint to prevent data loss on crash
    async def _wal_checkpoint_loop():
        import asyncio
        import sqlite3

        db_path = str(Path(__file__).parent.parent / "data" / "platform.db")
        while True:
            await asyncio.sleep(30)
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                conn.close()
            except Exception:
                pass

    import asyncio

    asyncio.create_task(_wal_checkpoint_loop())

    # Auto-heal loop: scan incidents → create epics → launch TMA workflows
    try:
        from .ops.auto_heal import ENABLED as _ah_enabled
        from .ops.auto_heal import auto_heal_loop

        if _ah_enabled:
            asyncio.create_task(auto_heal_loop())
            logger.info("Auto-heal loop enabled")
    except Exception as e:
        logger.warning("Auto-heal loop failed to start: %s", e)

    # Log paused missions (no auto-resume — paused missions stay paused until manually restarted)
    try:
        from .missions.store import get_mission_run_store

        _mrs = get_mission_run_store()
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
    """Record a platform incident with deduplication (5-minute window)."""
    import sqlite3
    import uuid

    from .config import DB_PATH

    error_type = str(status_code)
    error_detail = detail or f"HTTP {status_code} on {path}"
    title = f"[Auto] {error_type} — {path}"

    try:
        conn = sqlite3.connect(str(DB_PATH))
        # Deduplicate: skip if same error_type+error_detail in last 5 minutes
        dup = conn.execute(
            "SELECT 1 FROM platform_incidents "
            "WHERE error_type=? AND error_detail=? "
            "AND created_at > datetime('now', '-5 minutes')",
            (error_type, error_detail),
        ).fetchone()
        if dup:
            conn.close()
            return
        conn.execute(
            "INSERT INTO platform_incidents (id, title, severity, status, source, error_type, error_detail) "
            "VALUES (?, ?, 'P3', 'open', 'auto', ?, ?)",
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

    # ── Security: Response headers ──────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://api.dicebear.com https://avatars.githubusercontent.com; "
            "connect-src 'self'; "
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
    _RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "120"))  # per minute
    _RATE_WINDOW = 60.0

    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        if request.url.path.startswith("/api/"):
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
                or path in ("/setup", "/health", "/favicon.ico", "/api/health")
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
            or path in ("/login", "/setup", "/onboarding", "/health", "/favicon.ico")
        )
        if not skip and not request.cookies.get("onboarding_done"):
            from starlette.responses import RedirectResponse

            return RedirectResponse(url="/onboarding", status_code=302)
        return await call_next(request)

    # ── Locale detection middleware ─────────────────────────────────────
    SUPPORTED_LOCALES = {"en", "fr", "es", "it", "de", "pt", "ja", "zh"}

    @app.middleware("http")
    async def locale_middleware(request, call_next):
        """Detect and set user locale from Accept-Language header or cookie."""
        import re as _locale_re

        # Priority: 1) Cookie 2) Accept-Language header 3) Default to 'en'
        locale = None

        # Check cookie first
        cookie_lang = request.cookies.get("sf_lang")
        if cookie_lang and cookie_lang in SUPPORTED_LOCALES:
            locale = cookie_lang

        # Parse Accept-Language header if no cookie
        if not locale:
            accept_lang = request.headers.get("Accept-Language", "")
            # Parse: "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
            langs = []
            for part in accept_lang.split(","):
                match = _locale_re.match(
                    r"([a-z]{2})(?:-[A-Z]{2})?(?:;q=([\d.]+))?", part.strip()
                )
                if match:
                    lang_code = match.group(1)
                    quality = float(match.group(2) or "1.0")
                    langs.append((quality, lang_code))

            # Sort by quality score (descending)
            langs.sort(reverse=True)

            # Find first supported locale
            for _, lang_code in langs:
                if lang_code in SUPPORTED_LOCALES:
                    locale = lang_code
                    break

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

        # Set cookie if not present or different
        if not cookie_lang or cookie_lang != locale:
            response.set_cookie(
                key="sf_lang",
                value=locale,
                max_age=31536000,  # 1 year
                httponly=True,
                samesite="lax",
            )

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

    app.state.templates = templates

    # Routes
    from .web.routes import router as web_router
    from .web.routes.auth import router as auth_router
    from .web.routes.mercato import router as mercato_router
    from .web.routes.oauth import router as oauth_router
    from .web.ws import router as sse_router
    from .web.routes.websocket import router as ws_router
    from .web.routes.dag import router as dag_router
    from .web.routes.evolution import router as evolution_router

    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(mercato_router)
    app.include_router(ws_router)
    app.include_router(dag_router)
    app.include_router(evolution_router)
    app.include_router(web_router)
    app.include_router(sse_router, prefix="/sse")

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
