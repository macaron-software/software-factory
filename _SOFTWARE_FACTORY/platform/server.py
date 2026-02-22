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

from .config import get_config
from .db.migrations import init_db

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    from .log_config import setup_logging
    setup_logging(level=os.environ.get("LOG_LEVEL", "WARNING"))

    # OpenTelemetry tracing (opt-in via OTEL_ENABLED=1)
    if os.environ.get("OTEL_ENABLED"):
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            provider = TracerProvider()
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            FastAPIInstrumentor.instrument_app(app)
            logger.info("OpenTelemetry tracing enabled")
        except ImportError:
            logger.warning("OpenTelemetry packages not installed, tracing disabled")

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
    from .missions.store import get_mission_store, MissionDef
    ms = get_mission_store()
    all_missions = ms.list_missions(limit=500)
    _prov_count = 0
    for proj in ps.list_all():
        proj_missions = [m for m in all_missions if m.project_id == proj.id]
        has_tma = any(m.type == 'program' or m.name.startswith('TMA') or '[TMA' in m.name for m in proj_missions)
        if not has_tma:
            try:
                ps.auto_provision(proj.id, proj.name)
                _prov_count += 1
            except Exception as e:
                logger.warning("auto_provision failed for %s: %s", proj.id, e)
        else:
            # Ensure security mission exists even if TMA already present
            has_secu = any(m.type == 'security' or m.name.startswith('Sécu') for m in proj_missions)
            if not has_secu:
                try:
                    ms.create_mission(MissionDef(
                        name=f"Sécurité — {proj.name}", type="security", status="active",
                        project_id=proj.id, workflow_id="review-cycle", wsjf_score=12,
                        created_by="devsecops", config={"auto_provisioned": True, "schedule": "weekly"},
                        description=f"Audit sécurité périodique pour {proj.name}.",
                        goal="Score sécurité ≥ 80%, zéro CVE critique.",
                    ))
                    _prov_count += 1
                except Exception as e:
                    logger.warning("security provision failed for %s: %s", proj.id, e)
    if _prov_count:
        logger.warning("Auto-provisioned TMA/Security/Debt for %d projects", _prov_count)

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
        _rdb.commit()
        _rdb.close()
        if _stale:
            logger.warning("Reset %d stale running mission_runs to paused (container restart)", _stale)
    except Exception as e:
        logger.warning("Failed to reset stale missions: %s", e)

    # Start unified MCP SF server (platform + LRM tools merged)
    _mcp_procs: dict[str, Any] = {}

    _mcp_sf_mod = "macaron_platform.mcp_platform.server" if Path("/app/macaron_platform").exists() else "platform.mcp_platform.server"

    def _start_mcp(name: str, module: str, port: int):
        """Start an MCP server subprocess, return Popen."""
        import subprocess as _sp
        log_file = Path(__file__).parent.parent / "data" / "logs" / f"mcp-{name}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log_file, "a")
        proc = _sp.Popen(
            [sys.executable, "-m", module],
            cwd=str(Path(__file__).parent.parent),
            start_new_session=True,
            stdout=fh, stderr=_sp.STDOUT,
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
                try:
                    _mcp_procs["sf"] = _start_mcp("sf", _mcp_sf_mod, 9501)
                except Exception as e:
                    logger.error("MCP SF restart failed: %s", e)

    import asyncio
    asyncio.create_task(_mcp_watchdog())

    # Periodic WAL checkpoint to prevent data loss on crash
    async def _wal_checkpoint_loop():
        import asyncio, sqlite3
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
        from .ops.auto_heal import auto_heal_loop, ENABLED as _ah_enabled
        if _ah_enabled:
            asyncio.create_task(auto_heal_loop())
            logger.info("Auto-heal loop enabled")
    except Exception as e:
        logger.warning("Auto-heal loop failed to start: %s", e)

    # Auto-resume missions after restart (running OR paused with phases remaining)
    try:
        from .missions.store import get_mission_run_store
        _mrs = get_mission_run_store()
        _all_runs = _mrs.list_runs(limit=50)
        _resumable = [m for m in _all_runs if m.status.value in ("running", "paused")]
        if _resumable:
            logger.warning("Found %d resumable missions after restart: %s",
                           len(_resumable), [m.id for m in _resumable])

            async def _auto_resume():
                """Resume ALL resumable missions — semaphore serializes them."""
                import asyncio
                await asyncio.sleep(15)
                from .web.routes import api_mission_run
                from starlette.requests import Request
                scope = {"type": "http", "method": "POST", "path": "/",
                         "headers": [], "query_string": b""}
                fake_req = Request(scope)
                for m in _resumable:
                    try:
                        resp = await api_mission_run(fake_req, m.id)
                        logger.warning("Auto-resumed mission %s: %s", m.id,
                                       getattr(resp, 'body', b'')[:100])
                    except Exception as exc:
                        logger.warning("Failed to auto-resume mission %s: %s", m.id, exc)

            import asyncio
            asyncio.create_task(_auto_resume())
    except Exception as exc:
        logger.warning("Auto-resume check failed: %s", exc)

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
    _cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8090,http://4.233.64.30").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _cors_origins],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Trace-ID", "X-Requested-With"],
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
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
                return _JR({"error": "rate_limit_exceeded", "retry_after": 60}, status_code=429)
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
                    request.method, request.url.path,
                    response.status_code, _dur,
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

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    # Add markdown filter for chat rendering (with LLM artifact stripping)
    import markdown as _md_lib
    import re as _re
    def _clean_llm(text: str) -> str:
        t = str(text or "")
        t = _re.sub(r'<think>[\s\S]*?</think>', '', t)
        t = _re.sub(r'<think>[\s\S]*$', '', t)
        t = _re.sub(r'\[TOOL_CALL\][\s\S]*?\[/TOOL_CALL\]', '', t)
        t = _re.sub(r'\[TOOL_CALL\][\s\S]*$', '', t)
        t = _re.sub(r'\[(DELEGATE|VETO|APPROVE|ASK|ESCALATE)[^\]]*\]', '', t)
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
                f'</div>'
            )
        return _re.sub(r'\[SCREENSHOT:([^\]]+)\]', _shot_repl, html)

    def _markdown_filter(text):
        html = _md_lib.markdown(
            _clean_llm(text), extensions=["fenced_code", "tables", "nl2br"]
        )
        return _render_screenshots(html)

    templates.env.filters["markdown"] = _markdown_filter

    # i18n — make _() available in all templates
    from .i18n import t as _translate, get_lang as _get_lang, SUPPORTED_LANGS

    def _i18n_global(key: str, **kwargs):
        """Template global: {{ _('key', name='val') }}"""
        return _translate(key, lang=_i18n_global._current_lang, **kwargs)
    _i18n_global._current_lang = "en"

    templates.env.globals["_"] = _i18n_global
    templates.env.globals["SUPPORTED_LANGS"] = SUPPORTED_LANGS

    # Middleware to set current language per-request
    from starlette.middleware.base import BaseHTTPMiddleware

    class I18nMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            lang = _get_lang(request)
            _i18n_global._current_lang = lang
            request.state.lang = lang
            response = await call_next(request)
            return response

    app.add_middleware(I18nMiddleware)

    app.state.templates = templates

    # Routes
    from .web.routes import router as web_router
    from .web.ws import router as sse_router

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
