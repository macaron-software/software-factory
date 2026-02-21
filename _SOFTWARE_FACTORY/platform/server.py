"""Macaron Agent Platform — FastAPI web server.

Serves the HTMX-based UI with SSE real-time updates.
Runs on port 8090 (separate from Factory dashboard on 8080).
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

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

    # Start MCP Platform Server (background, port 9501)
    _mcp_proc = None
    try:
        import subprocess as _sp
        _mcp_proc = _sp.Popen(
            [sys.executable, "-m", "platform.mcp_platform.server"],
            cwd=str(Path(__file__).parent.parent),
            start_new_session=True,
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
        logger.info("MCP Platform Server started (PID %d, port 9501)", _mcp_proc.pid)
    except Exception as exc:
        logger.warning("MCP Platform Server failed to start: %s", exc)

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

    # Stop MCP Platform Server
    if _mcp_proc and _mcp_proc.poll() is None:
        import os as _os
        try:
            _os.killpg(_os.getpgid(_mcp_proc.pid), 15)
        except Exception:
            _mcp_proc.terminate()

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
