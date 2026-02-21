"""Compose Tools — dynamic workflow & team composition for strategic agents.

These tools let the Comité Stratégique and ART agents dynamically compose
workflows, create feature teams, and spawn sub-missions at runtime.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


class ComposeWorkflowTool(BaseTool):
    """Create a dynamic workflow definition from agent analysis."""
    name = "compose_workflow"
    description = (
        "Create a new workflow definition dynamically. Use after analyzing the project "
        "scope to define the execution plan: phases, patterns, and agent assignments. "
        "Returns the workflow ID for use with create_sub_mission."
    )
    category = "compose"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..workflows.store import get_workflow_store, WorkflowDef
            store = get_workflow_store()

            wf_id = params.get("id") or f"dyn-{uuid.uuid4().hex[:8]}"
            name = params.get("name", "Dynamic Workflow")
            description = params.get("description", "")
            phases = params.get("phases", [])

            if not phases:
                return "Error: 'phases' is required — list of {id, name, pattern, agents, config}"

            # Build WorkflowDef
            wf = WorkflowDef(
                id=wf_id,
                name=name,
                description=description,
                category="dynamic",
                phases=[],
                graph={"nodes": [], "edges": []},
            )

            nodes = []
            edges = []
            for i, phase in enumerate(phases):
                phase_id = phase.get("id", f"phase-{i+1}")
                phase_agents = phase.get("agents", [])
                wf.phases.append({
                    "id": phase_id,
                    "name": phase.get("name", f"Phase {i+1}"),
                    "pattern_id": phase.get("pattern", "sequential"),
                    "agents": phase_agents,
                    "config": phase.get("config", {}),
                    "gate": phase.get("gate", "all_approved"),
                })
                # Build graph nodes
                for aid in phase_agents:
                    nodes.append({"id": aid, "phase": phase_id})
                # Sequential edges between agents in phase
                for j in range(len(phase_agents) - 1):
                    edges.append({"from": phase_agents[j], "to": phase_agents[j+1], "phase": phase_id})

            wf.graph = {"nodes": nodes, "edges": edges}
            store.create(wf)

            return json.dumps({
                "status": "created",
                "workflow_id": wf_id,
                "name": name,
                "phases": len(phases),
                "total_agents": sum(len(p.get("agents", [])) for p in phases),
            })
        except Exception as e:
            logger.exception("compose_workflow failed")
            return f"Error: {e}"


class CreateTeamTool(BaseTool):
    """Create a feature team (group of specialized agents) at runtime."""
    name = "create_team"
    description = (
        "Create a feature team with specialized agents. Each agent gets a prompt "
        "tailored to the team's domain, stack, and responsibilities. Returns the "
        "list of created agent IDs."
    )
    category = "compose"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..agents.store import get_agent_store, AgentDef
            store = get_agent_store()

            team_name = params.get("team_name", "Feature Team")
            domain = params.get("domain", "general")
            stack = params.get("stack", "")
            roles = params.get("roles", [])

            if not roles:
                return "Error: 'roles' is required — list of {id, name, role, skills, prompt}"

            created = []
            for r in roles:
                agent_id = r.get("id", f"dyn-{domain}-{uuid.uuid4().hex[:4]}")
                agent_def = AgentDef(
                    id=agent_id,
                    name=r.get("name", f"Agent {domain}"),
                    role=r.get("role", "Développeur"),
                    prompt=r.get("prompt", f"Tu es un développeur spécialisé {domain}. Stack: {stack}."),
                    skills=r.get("skills", [domain]),
                    category="feature-team",
                    hierarchy_rank=5,
                    avatar=r.get("avatar", ""),
                    tagline=r.get("tagline", f"Feature Team {team_name}"),
                )
                store.create(agent_def)
                created.append(agent_id)

            return json.dumps({
                "status": "created",
                "team_name": team_name,
                "domain": domain,
                "agents": created,
                "count": len(created),
            })
        except Exception as e:
            logger.exception("create_team failed")
            return f"Error: {e}"


class CreateSubMissionTool(BaseTool):
    """Create a sub-mission (Feature) linked to a parent mission (Epic)."""
    name = "create_sub_mission"
    description = (
        "Create a child mission linked to the current epic. Each sub-mission "
        "represents a Feature in SAFe terms. Assign a workflow and team to it. "
        "Returns the sub-mission ID."
    )
    category = "compose"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..missions.store import get_mission_store, MissionDef
            store = get_mission_store()

            parent_id = params.get("parent_mission_id", "")
            if not parent_id:
                return "Error: 'parent_mission_id' is required"

            name = params.get("name", "Feature")
            mission = MissionDef(
                id=uuid.uuid4().hex[:8],
                project_id=params.get("project_id", ""),
                name=name,
                description=params.get("description", ""),
                goal=params.get("goal", ""),
                type=params.get("type", "feature"),
                workflow_id=params.get("workflow_id"),
                parent_mission_id=parent_id,
                wsjf_score=float(params.get("wsjf_score", 0)),
                kanban_status="backlog",
                created_by=agent.id if agent else "system",
                config=params.get("config", {}),
            )
            store.create_mission(mission)

            return json.dumps({
                "status": "created",
                "sub_mission_id": mission.id,
                "name": name,
                "parent_mission_id": parent_id,
                "workflow_id": mission.workflow_id,
                "type": mission.type,
            })
        except Exception as e:
            logger.exception("create_sub_mission failed")
            return f"Error: {e}"


class ListSubMissionsTool(BaseTool):
    """List sub-missions of a parent mission."""
    name = "list_sub_missions"
    description = (
        "List all sub-missions (Features) of a parent mission (Epic). "
        "Shows their status, team, and progress."
    )
    category = "compose"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..missions.store import get_mission_store
            store = get_mission_store()
            parent_id = params.get("parent_mission_id", "")
            if not parent_id:
                return "Error: 'parent_mission_id' is required"

            children = store.list_children(parent_id)
            return json.dumps({
                "parent_mission_id": parent_id,
                "count": len(children),
                "sub_missions": [
                    {"id": c.id, "name": c.name, "type": c.type,
                     "status": c.status, "wsjf": c.wsjf_score}
                    for c in children
                ],
            })
        except Exception as e:
            logger.exception("list_sub_missions failed")
            return f"Error: {e}"


class SetConstraintsTool(BaseTool):
    """Set execution constraints on a mission."""
    name = "set_constraints"
    description = (
        "Set constraints for a mission: WIP limits, stack rules, AO references, "
        "sprint duration. Stored in the mission config."
    )
    category = "compose"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..missions.store import get_mission_store
            store = get_mission_store()
            mission_id = params.get("mission_id", "")
            if not mission_id:
                return "Error: 'mission_id' is required"

            mission = store.get_mission(mission_id)
            if not mission:
                return f"Error: mission {mission_id} not found"

            constraints = {}
            for key in ("wip_limit", "stack", "ao_refs", "sprint_duration",
                         "max_workers", "build_queue", "pi_duration"):
                if key in params:
                    constraints[key] = params[key]

            mission.config = {**mission.config, "constraints": constraints}
            store.update_mission(mission)

            return json.dumps({
                "status": "updated",
                "mission_id": mission_id,
                "constraints": constraints,
            })
        except Exception as e:
            logger.exception("set_constraints failed")
            return f"Error: {e}"


def register_compose_tools(registry):
    """Register all composition tools."""
    registry.register(ComposeWorkflowTool())
    registry.register(CreateTeamTool())
    registry.register(CreateSubMissionTool())
    registry.register(ListSubMissionsTool())
    registry.register(SetConstraintsTool())
