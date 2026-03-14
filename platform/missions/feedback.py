"""Backward-compat shim — use platform.epics.feedback instead."""
# Ref: feat-mission-control

# ruff: noqa: F401, F403
from platform.epics.feedback import *  # noqa
from platform.epics.feedback import (
    emit_reaction,
    on_deploy_completed,
    on_tma_incident_fixed,
    create_platform_incident,
    on_phase_failed,
    on_deploy_failed,
    on_security_alert,
)
