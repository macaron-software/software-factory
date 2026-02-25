"""Missions package — combines all mission sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .backlog import router as backlog_router
from .crud import router as crud_router
from .execution import router as execution_router
from .integrations import router as integrations_router
from .internal import (
    _auto_retrospective,
    _build_phase_prompt,
    _detect_project_platform,
    _extract_features_from_phase,
    _run_post_phase_hooks,
)
from .partials import router as partials_router
from .sprints import router as sprints_router

router = APIRouter()

router.include_router(crud_router)
router.include_router(execution_router)
router.include_router(sprints_router)
router.include_router(backlog_router)
router.include_router(partials_router)
router.include_router(integrations_router)

__all__ = [
    "router",
    "_auto_retrospective",
    "_build_phase_prompt",
    "_detect_project_platform",
    "_extract_features_from_phase",
    "_run_post_phase_hooks",
]
