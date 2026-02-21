"""Macaron Agent Platform — FastAPI web server.

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
    logger.info("Starting Macaron Agent Platform on port %s", cfg.server.port)
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
    get_project_store().seed_from_registry()

    # Seed memory (global knowledge + project files)
    from .memory.seeder import seed_all as seed_memories
    n_mem = seed_memories()
    if n_mem:
        logger.info("Seeded %d memories", n_mem)

    # Seed org tree (Portfolio → ART → Team)
    from .agents.org import get_org_store
    get_org_store().seed_default()
    get_org_store().seed_additional_teams()

    # Mark orphaned "active" sessions as interrupted (no running task after restart)
    from .sessions.store import get_session_store
    _ss = get_session_store()
    _orphaned = _ss.mark_orphaned_sessions()
    if _orphaned:
        logger.info("Marked %d orphaned active sessions as interrupted", _orphaned)

    # Start MCP servers with auto-restart watchdog
    _mcp_procs: dict[str, Any] = {}

    # Detect module names based on container vs local layout
    _mcp_platform_mod = "macaron_platform.mcp_platform.server" if Path("/app/macaron_platform").exists() else "platform.mcp_platform.server"
    _mcp_lrm_mod = "mcp_lrm.server_sse"

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
        _mcp_procs["platform"] = _start_mcp("platform", _mcp_platform_mod, 9501)
    except Exception as exc:
        logger.warning("MCP Platform Server failed to start: %s", exc)

    try:
        _mcp_procs["lrm"] = _start_mcp("lrm", _mcp_lrm_mod, 9500)
    except Exception as exc:
        logger.warning("MCP LRM Server failed to start: %s", exc)

    async def _mcp_watchdog():
        """Auto-restart MCP servers if they crash."""
        while True:
            await asyncio.sleep(30)
            for name, info in [("platform", (_mcp_platform_mod, 9501)),
                               ("lrm", (_mcp_lrm_mod, 9500))]:
                proc = _mcp_procs.get(name)
                if proc and proc.poll() is not None:
                    logger.warning("MCP %s died (exit=%s), restarting...", name, proc.returncode)
                    try:
                        _mcp_procs[name] = _start_mcp(name, info[0], info[1])
                    except Exception as e:
                        logger.error("MCP %s restart failed: %s", name, e)

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

    # Auto-resume stuck missions (status=running but no asyncio task after restart)
    try:
        from .missions.store import get_mission_run_store
        _mrs = get_mission_run_store()
        _all_runs = _mrs.list_runs(limit=50)
        _stuck = [m for m in _all_runs if m.status.value == "running"]
        if _stuck:
            logger.warning("Found %d stuck missions to auto-resume: %s",
                           len(_stuck), [m.id for m in _stuck])

            async def _auto_resume():
                """Resume stuck missions by directly calling the run endpoint handler."""
                import asyncio
                await asyncio.sleep(3)
                from .web.routes import api_mission_run, _active_mission_tasks
                from starlette.requests import Request
                from starlette.datastructures import Headers
                # Create a minimal fake request
                scope = {"type": "http", "method": "POST", "path": "/",
                         "headers": [], "query_string": b""}
                fake_req = Request(scope)
                for m in _stuck:
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
        title="Macaron Agent Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Security: CORS ──────────────────────────────────────────────────────
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8090", "http://4.233.64.30"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
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
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

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
