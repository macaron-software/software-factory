"""Phase Tools — mission control orchestration tools for the CDP agent.

These tools let the CDP agent pilot the product lifecycle by running phases,
checking status, and requesting human validation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


class RunPhaseTool(BaseTool):
    name = "run_phase"
    description = (
        "Launch a phase of the product lifecycle. Each phase runs a multi-agent "
        "pattern (network, sequential, hierarchical, etc.) with its own team. "
        "Returns a summary of the phase results."
    )
    category = "mission"
    allowed_roles = ["chef_de_programme"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        # Executed in executor._execute_tool via special handling
        return "Error: run_phase must be called via executor"


class GetPhaseStatusTool(BaseTool):
    name = "get_phase_status"
    description = "Get the current status of a specific phase in the running mission."
    category = "mission"
    allowed_roles = ["chef_de_programme"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: get_phase_status must be called via executor"


class ListPhasesTool(BaseTool):
    name = "list_phases"
    description = (
        "List all phases in the current mission with their status. "
        "Returns phase IDs, names, patterns, and current status."
    )
    category = "mission"
    allowed_roles = ["chef_de_programme"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: list_phases must be called via executor"


class RequestValidationTool(BaseTool):
    name = "request_validation"
    description = (
        "Request human validation at a checkpoint. Sends a question to the user "
        "and waits for GO/NOGO/PIVOT decision. Use at strategic gates."
    )
    category = "mission"
    allowed_roles = ["chef_de_programme"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: request_validation must be called via executor"


class GetProjectContextTool(BaseTool):
    name = "get_project_context"
    description = (
        "Get full project context including vision, architecture, and current state. "
        "Useful to understand what the project is about before launching phases."
    )
    category = "mission"
    allowed_roles = ["chef_de_programme"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: get_project_context must be called via executor"


def register_phase_tools(registry):
    """Register all phase orchestration tools."""
    registry.register(RunPhaseTool())
    registry.register(GetPhaseStatusTool())
    registry.register(ListPhasesTool())
    registry.register(RequestValidationTool())
    registry.register(GetProjectContextTool())
