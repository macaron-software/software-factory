"""Backward compat shim — use platform.epics.store instead."""
# Ref: feat-mission-control

from platform.epics.store import *  # noqa: F401, F403
from platform.epics.store import (  # noqa: F401
    EpicStore as MissionStore,
    EpicRun as MissionRun,
    EpicStatus as MissionStatus,
    get_epic_store as get_mission_store,
    get_epic_run_store as get_mission_run_store,
)
