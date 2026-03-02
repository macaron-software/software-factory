"""Backward compat shim — use platform.services.epic_orchestrator instead."""

from platform.services.epic_orchestrator import *  # noqa: F401, F403
from platform.services.epic_orchestrator import EpicOrchestrator as MissionOrchestrator  # noqa: F401
