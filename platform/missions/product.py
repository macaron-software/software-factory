"""Backward-compat shim — use platform.epics.product instead."""

# ruff: noqa: F401, F403
from platform.epics.product import *  # noqa
from platform.epics.product import (
    FeatureDef,
    UserStoryDef,
    ProductBacklog,
    get_product_backlog,
)
