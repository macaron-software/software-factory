"""Builtin workflow definitions — loaded from YAML files.

All 39 builtin workflows live in platform/workflows/definitions/*.yaml.
This module loads them into WorkflowDef objects at startup.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .store import WorkflowDef, WorkflowPhase

logger = logging.getLogger(__name__)

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def get_builtin_workflows() -> list[WorkflowDef]:
    """Load all builtin WorkflowDef from YAML definitions."""
    builtins: list[WorkflowDef] = []

    if not _DEFINITIONS_DIR.exists():
        logger.warning("Workflow definitions directory not found: %s", _DEFINITIONS_DIR)
        return builtins

    for fp in sorted(_DEFINITIONS_DIR.glob("*.yaml")):
        try:
            with open(fp) as f:
                raw = yaml.safe_load(f)
            if not raw or not isinstance(raw, dict):
                continue

            phases = []
            for p in raw.get("phases", []):
                phases.append(WorkflowPhase(
                    id=p.get("id", ""),
                    pattern_id=p.get("pattern_id", ""),
                    name=p.get("name", ""),
                    description=p.get("description", ""),
                    gate=p.get("gate", ""),
                    config=p.get("config", {}),
                    retry_count=p.get("retry_count", 1),
                    skip_on_failure=p.get("skip_on_failure", False),
                    timeout=p.get("timeout", 0),
                ))

            wf = WorkflowDef(
                id=raw["id"],
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                phases=phases,
                config=raw.get("config", {}),
                icon=raw.get("icon", "workflow"),
                is_builtin=True,
            )
            builtins.append(wf)
        except Exception as e:
            logger.warning("Failed to load workflow %s: %s", fp.name, e)

    logger.info("Loaded %d builtin workflows from YAML", len(builtins))
    return builtins
