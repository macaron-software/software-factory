"""Macaron Agent Platform — FastAPI web server.

Serves the HTMX-based UI with SSE real-time updates.
Runs on port 8090 (separate from Factory dashboard on 8080).
"""
from __future__ import annotations

import logging
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

    # Mark orphaned "active" sessions as interrupted (no running task after restart)
    from .sessions.store import get_session_store
    _ss = get_session_store()
    _orphaned = _ss.mark_orphaned_sessions()
    if _orphaned:
        logger.info("Marked %d orphaned active sessions as interrupted", _orphaned)

    yield

    # Cleanup LLM client
    try:
        from .llm.client import get_llm_client
        await get_llm_client().close()
    except Exception:
        pass

    logger.info("Platform shut down")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Macaron Agent Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    # Add markdown filter for chat rendering
    import markdown as _md_lib
    templates.env.filters["markdown"] = lambda text: _md_lib.markdown(
        str(text or ""), extensions=["fenced_code", "tables", "nl2br"]
    )
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
