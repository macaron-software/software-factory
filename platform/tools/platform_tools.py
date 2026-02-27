"""
Platform Tools — Expose platform internals (agents, missions, memory, metrics)
as native executor tools. Same handlers as mcp_platform/server.py but in-process.
"""

from __future__ import annotations

import json
import logging

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


class PlatformAgentsTool(BaseTool):
    name = "platform_agents"
    description = "List all platform agents or get details of one. Returns id, name, role, skills, tools, persona."
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..agents.store import get_agent_store

        store = get_agent_store()
        agent_id = params.get("agent_id")
        if agent_id:
            a = store.get(agent_id)
            if not a:
                return json.dumps({"error": f"Agent {agent_id} not found"})
            return json.dumps(
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                    "model": a.model,
                    "provider": a.provider,
                    "skills": (a.skills or [])[:10],
                    "tools": (a.tools or [])[:10],
                    "persona": (a.persona or "")[:300],
                    "tagline": getattr(a, "tagline", ""),
                }
            )
        agents = store.list_all()
        return json.dumps(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "role": a.role,
                }
                for a in agents[:50]
            ]
        )


class PlatformMissionsTool(BaseTool):
    name = "platform_missions"
    description = (
        "List all missions/epics or get details of one, including phase statuses."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..missions.store import get_mission_run_store, get_mission_store

        mission_id = params.get("mission_id")
        if mission_id:
            store = get_mission_run_store()
            m = store.get(mission_id)
            if not m:
                return json.dumps({"error": f"Mission {mission_id} not found"})
            phases = []
            if m.phases:
                for p in m.phases:
                    phases.append(
                        {
                            "phase_id": p.phase_id,
                            "status": p.status.value
                            if hasattr(p.status, "value")
                            else str(p.status),
                            "result": (p.result or "")[:200]
                            if hasattr(p, "result")
                            else "",
                        }
                    )
            return json.dumps(
                {
                    "id": m.id,
                    "brief": (m.brief or "")[:500],
                    "status": m.status.value
                    if hasattr(m.status, "value")
                    else str(m.status),
                    "workspace": m.workspace_path,
                    "phases": phases,
                }
            )
        # List missions (not runs) with optional status/project filter
        mstore = get_mission_store()
        status_filter = params.get("status")
        project_filter = params.get("project_id")
        missions = mstore.list_missions(limit=int(params.get("limit", 100)))
        items = []
        for m in missions:
            s = (
                m.status
                if isinstance(m.status, str)
                else getattr(m.status, "value", str(m.status))
            )
            if status_filter and s != status_filter:
                continue
            if project_filter and getattr(m, "project_id", None) != project_filter:
                continue
            items.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "status": s,
                    "workflow_id": getattr(m, "workflow_id", ""),
                    "description": (m.description or "")[:150],
                    "project_id": getattr(m, "project_id", ""),
                }
            )
        return json.dumps({"total": len(items), "missions": items})


class PlatformMemoryTool(BaseTool):
    name = "platform_memory_search"
    description = "Search platform memory (project or global). FTS5 full-text search across all knowledge."
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..memory.manager import get_memory_manager

        mem = get_memory_manager()
        query = params.get("query", "")
        project_id = params.get("project_id")
        category = params.get("category")
        limit = int(params.get("limit", 20))
        if query:
            entries = mem.search(query, limit=limit)
        elif project_id:
            entries = mem.project_get(project_id, category=category, limit=limit)
        else:
            entries = mem.global_get(category=category, limit=limit)
        return json.dumps(entries[:limit], default=str)


class PlatformMetricsTool(BaseTool):
    name = "platform_metrics"
    description = (
        "Get platform statistics. Pass project_id to filter by project: "
        "mission_runs count, sessions, messages, agents involved."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..db.migrations import get_db

        db = get_db()
        project_id = params.get("project_id")
        counts = {}

        if project_id:
            # Project-specific metrics
            for table, col in (
                ("mission_runs", "project_id"),
                ("sessions", "project_id"),
            ):
                try:
                    counts[table] = db.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (project_id,)
                    ).fetchone()[0]
                except Exception:
                    counts[table] = 0
            # Messages via sessions of the project
            try:
                counts["messages"] = db.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE project_id=?)",
                    (project_id,),
                ).fetchone()[0]
            except Exception:
                counts["messages"] = 0
            # Agents involved via mission_runs
            try:
                counts["agents_involved"] = db.execute(
                    "SELECT COUNT(DISTINCT cdp_agent_id) FROM mission_runs WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            except Exception:
                counts["agents_involved"] = 0
            counts["project_id"] = project_id
        else:
            for table in ("agents", "missions", "mission_runs", "sessions", "messages"):
                try:
                    counts[table] = db.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                except Exception:
                    counts[table] = 0
        return json.dumps(counts)


class PlatformSessionsTool(BaseTool):
    name = "platform_sessions"
    description = "List recent sessions or get messages from a specific session."
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..sessions.store import get_session_store

        store = get_session_store()
        session_id = params.get("session_id")
        if session_id:
            limit = int(params.get("limit", 30))
            msgs = store.get_messages(session_id, limit=limit)
            return json.dumps(
                [
                    {
                        "from": m.from_agent,
                        "to": m.to_agent,
                        "content": (m.content or "")[:400],
                    }
                    for m in msgs
                ]
            )
        sessions = store.list_recent(limit=20)
        return json.dumps(
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "project_id": s.project_id,
                }
                for s in sessions
            ]
        )


class PlatformWorkflowsTool(BaseTool):
    name = "platform_workflows"
    description = "List available ceremony templates (workflows) with their phases, patterns, and agents."
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..workflows.store import get_workflow_store

        store = get_workflow_store()
        workflows = store.list_all()
        return json.dumps(
            [
                {
                    "id": w.id,
                    "name": w.name,
                    "phases": len(w.phases) if w.phases else 0,
                }
                for w in (workflows or [])[:20]
            ]
        )


class PlatformCreateFeatureTool(BaseTool):
    name = "create_feature"
    description = (
        "Create a feature in the product backlog. Links to an epic (mission_id). "
        "Use to persist PM decomposition: each feature gets a REQ-ID for AO traceability."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..missions.product import FeatureDef, ProductBacklog

        epic_id = params.get("epic_id", "")
        name = params.get("name", "")
        if not name:
            return json.dumps({"error": "name is required"})
        backlog = ProductBacklog()
        feat = FeatureDef(
            epic_id=epic_id,
            name=name,
            description=params.get("description", ""),
            acceptance_criteria=params.get("acceptance_criteria", ""),
            priority=params.get("priority", 5),
            status=params.get("status", "backlog"),
            story_points=params.get("story_points", 0),
            assigned_to=params.get("assigned_to", ""),
        )
        feat = backlog.create_feature(feat)
        return json.dumps({"ok": True, "feature_id": feat.id, "name": feat.name})


class PlatformCreateStoryTool(BaseTool):
    name = "create_story"
    description = (
        "Create a user story under a feature. Includes title, acceptance criteria, "
        "story points, priority, and optional sprint assignment."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..missions.product import ProductBacklog, UserStoryDef

        feature_id = params.get("feature_id", "")
        title = params.get("title", "")
        if not title:
            return json.dumps({"error": "title is required"})
        backlog = ProductBacklog()
        story = UserStoryDef(
            feature_id=feature_id,
            title=title,
            description=params.get("description", ""),
            acceptance_criteria=params.get("acceptance_criteria", ""),
            story_points=params.get("story_points", 0),
            priority=params.get("priority", 5),
            status=params.get("status", "backlog"),
            sprint_id=params.get("sprint_id", ""),
            assigned_to=params.get("assigned_to", ""),
        )
        story = backlog.create_story(story)
        return json.dumps({"ok": True, "story_id": story.id, "title": story.title})


class PlatformCreateProjectTool(BaseTool):
    name = "create_project"
    description = (
        "Create a new project on the platform. "
        "Params: name (required), description, stack (tech stack string), factory_type ('software'|'data'|'security'). "
        "Returns the created project id and name."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..projects.manager import get_project_store, Project

        name = params.get("name", "").strip()
        if not name:
            return json.dumps({"error": "name is required"})
        import uuid
        import datetime

        store = get_project_store()
        proj = Project(
            id=str(uuid.uuid4())[:8],
            name=name,
            path="",
            description=params.get("description", ""),
            factory_type=params.get("factory_type", "software"),
            created_at=datetime.datetime.utcnow().isoformat(),
        )
        proj = store.create(proj)
        return json.dumps({"ok": True, "project_id": proj.id, "name": proj.name})


class PlatformCreateMissionTool(BaseTool):
    name = "create_mission"
    description = (
        "Create a new mission (epic) on the platform and launch it. "
        "Params: name (required), goal/description, project_id, workflow_id (optional). "
        "Returns the mission id."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..missions.store import get_mission_store, MissionDef

        name = params.get("name", "").strip()
        if not name:
            return json.dumps({"error": "name is required"})
        store = get_mission_store()
        mission = MissionDef(
            name=name,
            description=params.get("description", params.get("goal", "")),
            goal=params.get("goal", params.get("description", name)),
            project_id=params.get("project_id", ""),
            workflow_id=params.get("workflow_id", ""),
            status="active",
        )
        mission = store.create_mission(mission)

        # Auto-launch orchestrator (create mission_run + start execution)
        run_info = {}
        try:
            from ..missions.store import get_mission_run_store
            from ..models import MissionRun, MissionStatus
            import uuid
            import asyncio

            run_store = get_mission_run_store()
            run = MissionRun(
                id=str(uuid.uuid4())[:8],
                mission_id=mission.id,
                status=MissionStatus.PAUSED,
                project_id=mission.project_id or "",
            )
            run = run_store.create(run)
            run_info = {"mission_run_id": run.id}

            # Schedule launch in background (don't block tool response)
            async def _launch():
                try:
                    from ..services.mission_orchestrator import MissionOrchestrator

                    orch = MissionOrchestrator()
                    await orch.run(run.id)
                except Exception:
                    pass

            asyncio.get_event_loop().create_task(_launch())
        except Exception as _e:
            run_info = {"launch_warning": str(_e)}

        return json.dumps(
            {"ok": True, "mission_id": mission.id, "name": mission.name, **run_info}
        )


def register_platform_tools(registry):
    """Register all platform introspection tools."""
    registry.register(PlatformAgentsTool())
    registry.register(PlatformMissionsTool())
    registry.register(PlatformMemoryTool())
    registry.register(PlatformMetricsTool())
    registry.register(PlatformSessionsTool())
    registry.register(PlatformWorkflowsTool())
    registry.register(PlatformCreateFeatureTool())
    registry.register(PlatformCreateStoryTool())
    registry.register(PlatformCreateProjectTool())
    registry.register(PlatformCreateMissionTool())
