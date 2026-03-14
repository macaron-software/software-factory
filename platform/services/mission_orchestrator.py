"""Backward compat shim — use platform.services.epic_orchestrator instead."""
# Ref: feat-mission-control

from platform.services.epic_orchestrator import *  # noqa: F401, F403
from platform.services.epic_orchestrator import EpicOrchestrator as MissionOrchestrator  # noqa: F401
