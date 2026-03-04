"""API routes package — assembles all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .modules import router as modules_router
from .analytics import router as analytics_router
from .cockpit import router as cockpit_router
from .screens import router as screens_router
from .api_keys import router as api_keys_router
from .dashboard import router as dashboard_router
from .deploy_targets import router as deploy_targets_router
from .events import router as events_router
from .health import router as health_router
from .incidents import router as incidents_router
from .integrations import router as integrations_router
from .llm import router as llm_router
from .memory import router as memory_router
from .rbac import router as rbac_router
from .search import router as search_router
from .settings import router as settings_router
from .simplify import router as simplify_router
from .teams import router as teams_router

router = APIRouter()

# Literal path routers first, then routers with {param} paths
router.include_router(health_router)
router.include_router(llm_router)
router.include_router(api_keys_router)
router.include_router(memory_router)
router.include_router(rbac_router)
router.include_router(incidents_router)
router.include_router(integrations_router)
router.include_router(deploy_targets_router)
router.include_router(dashboard_router)
router.include_router(analytics_router)
router.include_router(search_router)
router.include_router(events_router)
router.include_router(settings_router)
router.include_router(simplify_router)
router.include_router(teams_router)
router.include_router(modules_router)
router.include_router(cockpit_router)
router.include_router(screens_router)
