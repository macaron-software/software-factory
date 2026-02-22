"""Web routes package — assembles all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .helpers import _active_mission_tasks, serve_workspace_file

router = APIRouter()

# Import and include all sub-routers
from .agents import router as agents_router
from .api import router as api_router
from .cli import router as cli_router  # NEW: CLI API
from .ideation import router as ideation_router
from .missions import router as missions_router
from .pages import router as pages_router
from .projects import router as projects_router
from .sessions import router as sessions_router
from .sf_commands import router as sf_router  # NEW: SF native commands
from .workflows import router as workflows_router

router.include_router(pages_router)
router.include_router(projects_router)
router.include_router(missions_router)
router.include_router(agents_router)
router.include_router(sessions_router)
router.include_router(workflows_router)
router.include_router(ideation_router)
router.include_router(api_router)
router.include_router(cli_router)  # NEW: CLI routes
router.include_router(sf_router)  # NEW: SF commands

# Workspace file serving (needs to be on the main router)
router.add_api_route("/workspace/{path:path}", serve_workspace_file, methods=["GET"])

# Re-export for backward compatibility (server.py imports these)
from .missions import api_mission_run

__all__ = ["router", "api_mission_run", "_active_mission_tasks"]
