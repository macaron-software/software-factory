"""Web routes package — assembles all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .agents import router as agents_router
from .analytics import router as analytics_router
from .cto import router as cto_router
from .evals import router as evals_router
from .tool_builder import router as tool_builder_router
from .api import router as api_router
from .cli import router as cli_router
from .helpers import _active_mission_tasks, serve_workspace_file
from .ideation import router as ideation_router
from .missions import router as missions_router
from .pages import router as pages_router
from .projects import router as projects_router
from .sessions import router as sessions_router
from .sf_commands import router as sf_router
from .notifications import router as notifications_router
from .tma import router as tma_router
from .wiki import router as wiki_router
from .workflows import router as workflows_router

router = APIRouter()

router.include_router(pages_router)
router.include_router(projects_router)
router.include_router(missions_router)
router.include_router(agents_router)
router.include_router(sessions_router)
router.include_router(workflows_router)
router.include_router(ideation_router)
router.include_router(api_router)
router.include_router(cli_router)
router.include_router(sf_router)
router.include_router(notifications_router)
router.include_router(tma_router)
router.include_router(wiki_router)
router.include_router(analytics_router)
router.include_router(cto_router)
router.include_router(evals_router)
router.include_router(tool_builder_router)

# Workspace file serving (needs to be on the main router)
router.add_api_route("/workspace/{path:path}", serve_workspace_file, methods=["GET"])

# Re-export for backward compatibility
__all__ = ["router", "api_mission_run", "_active_mission_tasks"]
