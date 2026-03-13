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
        "List SAFe epics (missions) or get details of one, including phase statuses."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..epics.store import get_epic_run_store, get_epic_store

        mission_id = params.get("mission_id")
        if mission_id:
            store = get_epic_run_store()
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
        epic_store = get_epic_store()
        status_filter = params.get("status")
        project_filter = params.get("project_id")
        missions = epic_store.list_missions(limit=int(params.get("limit", 100)))
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
        return json.dumps({"total": len(items), "epics": items})


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
        "Get platform SAFe portfolio statistics. Pass project_id to filter by project. "
        "Returns epics, features, tasks, agents, sessions, messages counts."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..db.migrations import get_db

        db = get_db()
        project_id = params.get("project_id")
        counts = {}

        if project_id:
            for table, col, key in (
                ("epics", "project_id", "epics"),
                ("features", "epic_id", None),  # features join via epics
                ("epic_runs", "project_id", "epic_runs"),
                ("sessions", "project_id", "sessions"),
            ):
                try:
                    if table == "features":
                        counts["features"] = db.execute(
                            "SELECT COUNT(*) FROM features WHERE epic_id IN "
                            "(SELECT id FROM epics WHERE project_id=?)",
                            (project_id,),
                        ).fetchone()[0]
                    else:
                        counts[key] = db.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (project_id,)
                        ).fetchone()[0]
                except Exception:
                    counts[key or table] = 0
            try:
                counts["tasks"] = db.execute(
                    "SELECT COUNT(*) FROM tasks WHERE feature_id IN ("
                    "SELECT id FROM features WHERE epic_id IN ("
                    "SELECT id FROM epics WHERE project_id=?))",
                    (project_id,),
                ).fetchone()[0]
            except Exception:
                counts["tasks"] = 0
            try:
                counts["messages"] = db.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE project_id=?)",
                    (project_id,),
                ).fetchone()[0]
            except Exception:
                counts["messages"] = 0
            try:
                counts["agents_involved"] = db.execute(
                    "SELECT COUNT(DISTINCT cdp_agent_id) FROM epic_runs WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            except Exception:
                counts["agents_involved"] = 0
            counts["project_id"] = project_id
        else:
            # Global portfolio stats — SAFe labels
            def _count(table):
                try:
                    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except Exception:
                    return 0

            counts["projects"] = _count("projects")
            counts["epics"] = _count("epics")
            counts["features"] = _count("features")
            counts["tasks"] = _count("tasks")
            counts["agents"] = _count("agents")
            counts["epic_runs"] = _count("epic_runs")
            counts["sessions"] = _count("sessions")
            counts["messages"] = _count("messages")
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


class PlatformGuideTool(BaseTool):
    """Context-aware guidance on what to do next.

    Inspired by BMAD /bmad-help (MIT) — adapted for SF autonomous agent platform.
    Source: https://github.com/bmad-code-org/BMAD-METHOD
    Reads current state (missions, projects) and recommends next steps.
    Available to Jarvis (strat-cto) and all orchestrator agents.
    """

    name = "platform_guide"
    description = (
        "Context-aware guidance: reads current platform state (running missions, projects) "
        "and recommends what to do next. Accepts optional context hint. "
        "Inspired by BMAD /bmad-help pattern."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..epics.store import get_epic_store
        from ..projects.manager import get_project_store

        context = params.get("context", "")
        try:
            projects = get_project_store().list_all()
            missions = get_epic_store().list_missions(limit=50)

            running = [m for m in missions if m.status in ["running", "in_progress"]]
            pending = [m for m in missions if m.status == "pending"]
            done = [m for m in missions if m.status in ["completed", "done"]]

            guide: dict = {
                "state": {
                    "projects": len(projects),
                    "missions_running": len(running),
                    "missions_pending": len(pending),
                    "missions_done": len(done),
                },
                "running_missions": [
                    {
                        "id": m.id,
                        "name": getattr(m, "name", getattr(m, "title", "untitled")),
                        "status": m.status,
                    }
                    for m in running[:5]
                ],
                "recommendations": [],
            }

            recs = guide["recommendations"]
            if not projects:
                recs.append("Create a project: Projects → New Project")
                recs.append("Pick a workflow: browse 46 workflows")
            elif not missions:
                recs.append(
                    "Launch first mission via ideation-to-prod or feature-sprint workflow"
                )
                recs.append(
                    "Use complexity=simple for quick tasks, complexity=enterprise for large projects"
                )
            elif running:
                recs.append("Monitor running missions: platform_missions tool")
                recs.append(
                    "Check human-in-the-loop checkpoints if any mission is blocked"
                )
            else:
                recs.append("Review completed missions for follow-up actions")
                recs.append("Run skill-eval workflow to verify skill quality")
                recs.append(
                    "Consider skill-evolution workflow to improve underperforming agents"
                )

            if context:
                guide["context"] = context
                kw = context.lower()
                if any(w in kw for w in ["architect", "design", "system"]):
                    recs.append(
                        "Architecture → feature-sprint workflow (phase: solutioning) + architecte agent"
                    )
                elif any(w in kw for w in ["test", "qa", "quality", "eval"]):
                    recs.append(
                        "QA → test-campaign or skill-eval workflow + qa agent + tdd.md skill"
                    )
                elif any(w in kw for w in ["deploy", "prod", "release", "ship"]):
                    recs.append(
                        "Deploy → canary-deployment workflow (1%→10%→50%→100% + HITL)"
                    )
                elif any(w in kw for w in ["security", "audit", "pentest"]):
                    recs.append(
                        "Security → security-hacking workflow (8 phases) + security-audit.md skill"
                    )
                elif any(w in kw for w in ["simple", "quick", "small", "bug", "fix"]):
                    recs.append(
                        "Simple task → launch workflow with complexity=simple (enterprise phases auto-skipped)"
                    )
                elif any(w in kw for w in ["enterprise", "large", "big", "complex"]):
                    recs.append(
                        "Large project → launch workflow with complexity=enterprise (all phases included)"
                    )

            return json.dumps(guide, ensure_ascii=False)
        except Exception as e:
            logger.exception("Error in platform_guide tool")
            return json.dumps({"error": str(e)})


class PlatformCreateFeatureTool(BaseTool):
    name = "create_feature"
    description = (
        "Create a feature in the product backlog. Links to an epic (mission_id). "
        "Use to persist PM decomposition: each feature gets a REQ-ID for AO traceability."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..epics.product import FeatureDef, ProductBacklog

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
        from ..epics.product import ProductBacklog, UserStoryDef

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


class PlatformCreateSprintTool(BaseTool):
    name = "create_sprint"
    description = (
        "Create a sprint record for an epic (mission). "
        "Params: epic_id (required), name, goal, type (inception|infra|tdd|adversarial|qa|deploy), "
        "number (sprint number), planned_sp (story points planned), team_agents (list of agent ids). "
        "Returns sprint_id and number."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import json as _json
        from ..epics.store import get_epic_run_store, SprintDef

        epic_id = params.get("epic_id", "")
        if not epic_id:
            return _json.dumps({"error": "epic_id is required"})
        store = get_epic_run_store()
        # Auto-compute sprint number
        existing = store.list_sprints(epic_id)
        number = params.get("number", len(existing) + 1)
        team = params.get("team_agents", [])
        sprint = SprintDef(
            mission_id=epic_id,
            number=number,
            name=params.get("name", f"Sprint {number}"),
            goal=params.get("goal", ""),
            type=params.get("type", "tdd"),
            planned_sp=params.get("planned_sp", 0),
            team_agents=_json.dumps(team) if isinstance(team, list) else team,
            status="active",
        )
        sprint = store.create_sprint(sprint)
        return _json.dumps(
            {"ok": True, "sprint_id": sprint.id, "number": sprint.number}
        )


class PlatformLaunchEpicRunTool(BaseTool):
    name = "launch_epic_run"
    description = (
        "Launch a workflow execution for an epic. Creates a session and starts the workflow. "
        "Params: epic_id (required), workflow_id (optional, uses epic's default if omitted). "
        "Returns session_id, workflow_id, run status. "
        "Use this to start or restart an epic run autonomously."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import json as _json

        epic_id = params.get("epic_id", "")
        if not epic_id:
            return _json.dumps({"error": "epic_id is required"})
        workflow_id = params.get("workflow_id", "")

        try:
            from ..epics.store import get_epic_store, get_epic_run_store
            from ..workflows.store import get_workflow_store
            from ..models import EpicRun, PhaseRun, PhaseStatus
            from ..sessions.store import SessionDef, MessageDef, get_session_store
            import uuid

            epic_store = get_epic_store()
            mission = epic_store.get_mission(epic_id)
            if not mission:
                return _json.dumps({"error": f"Epic '{epic_id}' not found"})

            wf_id = workflow_id or mission.workflow_id
            if not wf_id:
                return _json.dumps({"error": "No workflow_id for this epic"})

            wf = get_workflow_store().get(wf_id)
            if not wf:
                return _json.dumps({"error": f"Workflow '{wf_id}' not found"})

            # Build phase runs
            phases = wf.phases_json if isinstance(wf.phases_json, list) else []
            phase_runs = [
                PhaseRun(
                    phase_id=p["id"],
                    phase_name=p.get("name", p["id"]),
                    pattern_id=p.get("pattern_id", "sequential"),
                    status=PhaseStatus.PENDING,
                )
                for p in phases
            ]

            run_id = str(uuid.uuid4())[:8]
            session_id = run_id
            run = EpicRun(
                id=run_id,
                session_id=session_id,
                workflow_id=wf_id,
                workflow_name=wf.name,
                project_id=mission.project_id,
                parent_epic_id=epic_id,
                status="paused",
                phases_json=phase_runs,
            )
            run_store = get_epic_run_store()
            run_store.create_run(run)

            # Create session
            ss = get_session_store()
            s = SessionDef(
                id=session_id,
                project_id=mission.project_id,
                title=f"{mission.name} — {wf.name}",
                messages=[
                    MessageDef(
                        role="user",
                        content=f"Execute workflow '{wf.name}' for epic '{mission.name}'.",
                    )
                ],
            )
            ss.create_session(s)

            # Resume immediately
            from ..workflows.store import run_workflow
            import asyncio

            loop = asyncio.get_event_loop()
            loop.create_task(
                asyncio.to_thread(
                    run_workflow, wf, session_id, mission.name, mission.project_id
                )
            )

            return _json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "session_id": session_id,
                    "workflow_id": wf_id,
                    "epic_id": epic_id,
                    "phases": [p["id"] for p in phases],
                }
            )
        except Exception as e:
            return _json.dumps({"error": str(e)})


class PlatformResumeRunTool(BaseTool):
    name = "resume_run"
    description = (
        "Resume a paused or stuck epic run. "
        "Params: run_id or session_id (required). "
        "Returns status. Use to unblock stuck workflows."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import json as _json

        run_id = params.get("run_id") or params.get("session_id", "")
        if not run_id:
            return _json.dumps({"error": "run_id or session_id required"})

        try:
            from ..epics.store import get_epic_run_store

            run_store = get_epic_run_store()
            run = run_store.get(run_id)
            if not run:
                return _json.dumps({"error": f"Run '{run_id}' not found"})
            if run.status == "cancelled":
                return _json.dumps({"error": "Run is cancelled, cannot resume"})

            from ..workflows.store import get_workflow_store, run_workflow
            import asyncio

            wf = get_workflow_store().get(run.workflow_id)
            if not wf:
                return _json.dumps({"error": f"Workflow '{run.workflow_id}' not found"})

            run_store.update_run_status(run_id, "running")
            loop = asyncio.get_event_loop()
            loop.create_task(
                asyncio.to_thread(
                    run_workflow, wf, run_id, run.workflow_name or "", run.project_id
                )
            )
            return _json.dumps({"ok": True, "run_id": run_id, "status": "resuming"})
        except Exception as e:
            return _json.dumps({"error": str(e)})


class PlatformCheckRunTool(BaseTool):
    name = "check_run_status"
    description = (
        "Check status of an epic run (workflow execution). "
        "Params: run_id or session_id. Or project_id to list all runs for a project. "
        "Returns status, current_phase, phases progress, sprint count."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import json as _json

        run_id = params.get("run_id") or params.get("session_id", "")
        project_id = params.get("project_id", "")

        try:
            from ..epics.store import get_epic_run_store

            store = get_epic_run_store()
            if run_id:
                run = store.get(run_id)
                if not run:
                    return _json.dumps({"error": f"Run '{run_id}' not found"})
                phases = run.phases_json if isinstance(run.phases_json, list) else []
                sprints = store.list_sprints(run.parent_epic_id or run_id)
                return _json.dumps(
                    {
                        "run_id": run.id,
                        "status": run.status,
                        "current_phase": run.current_phase,
                        "workflow_id": run.workflow_id,
                        "project_id": run.project_id,
                        "phases": [
                            {"id": p.phase_id, "status": p.status} for p in phases
                        ]
                        if phases
                        else [],
                        "sprint_count": len(sprints),
                        "resume_attempts": getattr(run, "resume_attempts", 0),
                    }
                )
            elif project_id:
                runs = store.list_runs(project_id=project_id, limit=10)
                return _json.dumps(
                    [
                        {
                            "run_id": r.id,
                            "status": r.status,
                            "current_phase": r.current_phase,
                            "workflow_id": r.workflow_id,
                        }
                        for r in runs
                    ]
                )
            else:
                return _json.dumps({"error": "run_id or project_id required"})
        except Exception as e:
            return _json.dumps({"error": str(e)})


class PlatformCreateProjectTool(BaseTool):
    name = "create_project"
    description = (
        "Create a new project on the platform. "
        "If git_url is provided, clones the existing repository as the workspace. "
        "Otherwise scaffolds a new project (git init, Dockerfile, README, docs/spec.md). "
        "Standard missions (TMA/MCO, Security, Tech Debt + Legal) are always provisioned. "
        "Params: name (required), git_url (existing repo URL to clone), description, vision, "
        "stack (tech stack string), factory_type ('software'|'data'|'security'|'standalone'). "
        "Returns the created project id, name, workspace path, scaffold actions, and mission ids."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import subprocess as _sp
        from ..projects.manager import get_project_store, Project, scaffold_project

        name = params.get("name", "").strip()
        if not name:
            return json.dumps({"error": "name is required"})
        import uuid
        import datetime

        git_url = (params.get("git_url") or "").strip()

        store = get_project_store()
        proj = Project(
            id=str(uuid.uuid4())[:8],
            name=name,
            path="",
            description=params.get("description", ""),
            vision=params.get("vision", params.get("description", "")),
            factory_type=params.get("factory_type", "software"),
            git_url=git_url,
            created_at=datetime.datetime.utcnow().isoformat(),
        )
        proj = store.create(proj)

        scaffold_result = {}
        if git_url:
            # Clone existing repo into workspace
            import os as _os

            workspace_root = (
                _os.path.dirname(proj.path)
                if proj.path
                else _os.path.join(_os.getcwd(), "workspace")
            )
            dest = proj.path or _os.path.join(workspace_root, proj.id)
            try:
                r = _sp.run(
                    ["git", "clone", git_url, dest],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if r.returncode == 0:
                    # Update project path to the cloned directory
                    proj.path = dest
                    store.update(proj)
                    scaffold_result = {"actions": [f"cloned {git_url} → {dest}"]}
                else:
                    scaffold_result = {
                        "error": r.stderr.strip() or "clone failed",
                        "actions": [],
                    }
            except Exception as _e:
                scaffold_result = {"error": str(_e), "actions": []}
        else:
            # Scaffold workspace: git init + Dockerfile + docker-compose + README + docs/spec.md + src/
            try:
                scaffold_result = scaffold_project(proj)
            except Exception as _e:
                scaffold_result = {"error": str(_e)}

        # List missions provisioned by store.create() → heal_epics()
        missions_created = []
        try:
            from ..epics.store import get_epic_store

            m_store = get_epic_store()
            missions_created = [
                {
                    "mission_id": m.id,
                    "name": m.name,
                    "workflow": m.workflow_id,
                    "status": m.status,
                }
                for m in m_store.list_missions(project_id=proj.id, limit=20)
            ]
        except Exception:
            pass

        return json.dumps(
            {
                "ok": True,
                "project_id": proj.id,
                "name": proj.name,
                "workspace": proj.path,
                "scaffold": scaffold_result.get("actions", []),
                "epics": missions_created,
            }
        )


async def _bootstrap_standard_missions(project_id: str, project_name: str) -> list:
    """Create the 3 standard missions for every new project: TMA, Security, Tech Debt + Legal.

    Idempotent: skips any mission whose workflow_id already exists for this project.
    """
    from ..epics.store import get_epic_store, MissionDef, get_epic_run_store
    from ..models import EpicRun, EpicStatus
    import uuid

    m_store = get_epic_store()
    run_store = get_epic_run_store()
    created = []

    # Idempotency: collect already-existing workflow_ids for this project
    existing_workflows = {
        getattr(m, "workflow_id", "")
        for m in m_store.list_missions(project_id=project_id, limit=50)
    }

    standard = [
        {
            "name": f"TMA/MCO — {project_name}",
            "description": "Tierce Maintenance Applicative — monitoring, incidents, corrections, SLA.",
            "goal": "Maintenir le projet en conditions opérationnelles. Triage incidents, diagnostic root-cause, correctifs TDD, déploiements hotfix.",
            "workflow_id": "tma-maintenance",
        },
        {
            "name": f"Sécurité — {project_name}",
            "description": "Audit sécurité offensif + défensif : pentest, CVE, SAST, remédiation.",
            "goal": "Identifier et corriger toutes les vulnérabilités. Score OWASP Top 10, aucune CVE critique.",
            "workflow_id": "security-hacking",
        },
        {
            "name": f"Dette Tech & Légalité — {project_name}",
            "description": "Réduction de la dette technique + conformité légale : RGPD, licences open-source, accessibilité a11y.",
            "goal": "Dette technique < seuil, 100% conformité licences (license-compliance), RGPD validé, a11y WCAG AA.",
            "workflow_id": "tech-debt-reduction",
        },
    ]

    for m_def in standard:
        if m_def["workflow_id"] in existing_workflows:
            continue  # Already exists — skip
        try:
            mission = MissionDef(
                name=m_def["name"],
                description=m_def["description"],
                goal=m_def["goal"],
                project_id=project_id,
                workflow_id=m_def["workflow_id"],
                status="active",
            )
            mission = m_store.create_mission(mission)
            run = EpicRun(
                id=str(uuid.uuid4())[:8],
                mission_id=mission.id,
                status=EpicStatus.PENDING,
                project_id=project_id,
            )
            run = run_store.create(run)
            created.append(
                {
                    "mission_id": mission.id,
                    "name": mission.name,
                    "workflow": m_def["workflow_id"],
                    "run_id": run.id,
                }
            )
        except Exception as _e:
            created.append({"name": m_def["name"], "error": str(_e)})

    return created


async def _ensure_project_for_mission(
    mission_name: str, description: str
) -> tuple[str, str]:
    """Auto-create a project for a mission that has no project_id.

    Derives project name from mission name by stripping common prefixes.
    Returns (project_id, project_name). Reuses existing project if name matches.
    """
    import re
    import uuid
    import datetime
    from ..projects.manager import get_project_store, Project, scaffold_project

    # Derive project name: strip common mission type prefixes
    proj_name = re.sub(
        r"^(TMA/MCO|TMA|MCO|Sécu(?:rité)?|Security|Hacking|"
        r"Dette\s+Tech(?:nique)?|Tech\s+Debt|Debt|Dev(?:eloppement)?|"
        r"Développement|Refactoring|Refacto|Deploy(?:ment)?|"
        r"Déploiement|Migration|Audit)\s*[—\-–:]\s*",
        "",
        mission_name,
        flags=re.IGNORECASE,
    ).strip()
    if not proj_name:
        proj_name = mission_name

    store = get_project_store()

    # Reuse existing project if name matches (case-insensitive)
    for p in store.list_all():
        if p.name.lower().strip() == proj_name.lower().strip():
            return p.id, p.name

    # Create a new project with full scaffold
    proj = Project(
        id=str(uuid.uuid4())[:8],
        name=proj_name,
        path="",  # store.create() auto-assigns workspace path
        description=description or f"Projet auto-créé pour la mission : {mission_name}",
        vision=description or "",
        factory_type="software",
        created_at=datetime.datetime.utcnow().isoformat(),
    )
    proj = store.create(proj)

    # Full scaffold: workspace, git init, README, docs/spec.md, Dockerfile, docker-compose
    # NOTE: store.create() already calls heal_epics() which provisions standard missions.
    try:
        scaffold_project(proj)
    except Exception as _e:
        logger.warning("scaffold failed for auto-project %s: %s", proj.id, _e)

    logger.info(
        "Auto-created project '%s' (%s) for orphan mission '%s'",
        proj.name,
        proj.id,
        mission_name,
    )
    return proj.id, proj.name


class PlatformCreateMissionTool(BaseTool):
    name = "create_mission"
    description = (
        "Create a new mission (epic) on the platform and launch it. "
        "If project_id is omitted, a project is auto-created with full scaffold "
        "(workspace, git, README, docs/spec.md, Dockerfile, docker-compose) "
        "and standard missions (TMA/MCO, Security, Tech Debt). "
        "Params: name (required), goal/description, project_id, workflow_id (optional), "
        "target_branch (optional — git branch where agents will deliver code, e.g. 'feature/sav-parcours'; "
        "auto-created in the project workspace if it doesn't exist). "
        "Returns the mission id and auto-created project_id if applicable."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..epics.store import get_epic_store, MissionDef

        name = params.get("name", "").strip()
        if not name:
            return json.dumps({"error": "name is required"})

        project_id = params.get("project_id", "").strip()
        target_branch = (params.get("target_branch") or "").strip()
        auto_project: dict = {}

        # Rule: mission without project → auto-create project + scaffold
        if not project_id:
            description = params.get("description", params.get("goal", ""))
            project_id, proj_name = await _ensure_project_for_mission(name, description)
            auto_project = {
                "auto_created_project_id": project_id,
                "auto_created_project_name": proj_name,
            }

        # Resolve workspace_path from project
        workspace_path = ""
        try:
            from ..projects.manager import get_project_store

            proj = get_project_store().get(project_id)
            if proj and proj.path:
                workspace_path = proj.path
        except Exception:
            pass

        store = get_epic_store()
        mission = MissionDef(
            name=name,
            description=params.get("description", params.get("goal", "")),
            goal=params.get("goal", params.get("description", name)),
            project_id=project_id,
            workflow_id=params.get("workflow_id", ""),
            status="active",
        )
        mission = store.create_mission(mission)

        # Create target branch in workspace if requested
        branch_info = {}
        if target_branch and workspace_path:
            import subprocess as _sp
            import os as _os

            if _os.path.isdir(_os.path.join(workspace_path, ".git")):
                try:
                    existing = _sp.run(
                        ["git", "rev-parse", "--verify", target_branch],
                        cwd=workspace_path,
                        capture_output=True,
                        timeout=10,
                    )
                    if existing.returncode == 0:
                        branch_info = {
                            "target_branch": target_branch,
                            "branch_action": "exists",
                        }
                    else:
                        r = _sp.run(
                            ["git", "checkout", "-b", target_branch],
                            cwd=workspace_path,
                            capture_output=True,
                            text=True,
                            timeout=15,
                        )
                        if r.returncode == 0:
                            branch_info = {
                                "target_branch": target_branch,
                                "branch_action": "created",
                            }
                        else:
                            branch_info = {"target_branch_error": r.stderr.strip()}
                except Exception as _e:
                    branch_info = {"target_branch_error": str(_e)}

        # Auto-launch orchestrator (create epic_run + start execution)
        run_info = {}
        try:
            from ..epics.store import get_epic_run_store
            from ..models import EpicRun, EpicStatus
            import uuid
            import asyncio

            run_store = get_epic_run_store()
            run = EpicRun(
                id=str(uuid.uuid4())[:8],
                mission_id=mission.id,
                status=EpicStatus.PENDING,
                project_id=mission.project_id or "",
                workspace_path=workspace_path,
                context={"target_branch": target_branch} if target_branch else {},
            )
            run = run_store.create(run)
            run_info = {"epic_run_id": run.id}

            # Schedule launch in background (don't block tool response)
            async def _launch():
                try:
                    from ..services.epic_orchestrator import EpicOrchestrator

                    orch = EpicOrchestrator()
                    await orch.run(run.id)
                except Exception:
                    pass

            asyncio.get_event_loop().create_task(_launch())
        except Exception as _e:
            run_info = {"launch_warning": str(_e)}

        return json.dumps(
            {
                "ok": True,
                "mission_id": mission.id,
                "name": mission.name,
                "workspace_path": workspace_path or None,
                **auto_project,
                **run_info,
                **branch_info,
            }
        )


class LaunchIdeationTool(BaseTool):
    name = "launch_ideation"
    description = (
        "Launch a multi-agent business/project ideation session (5 specialist agents: "
        "Business Analyst, Solution Architect, UX Designer, Product Manager, Tech Lead). "
        "Runs asynchronously — returns session_id immediately. "
        "Use to explore a product idea, architecture direction, or strategic question."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import uuid
        import asyncio
        from ..sessions.store import get_session_store, SessionDef, MessageDef
        from ..patterns.engine import run_pattern
        from ..patterns.store import PatternDef

        prompt = (params.get("prompt") or params.get("question") or "").strip()
        if not prompt:
            return json.dumps({"error": "prompt is required"})

        session_id = str(uuid.uuid4())[:8]
        store = get_session_store()
        session = store.create(
            SessionDef(
                id=session_id,
                name=f"Idéation: {prompt[:60]}",
                goal=prompt,
                status="active",
                config={"type": "ideation", "pattern": "network"},
            )
        )
        store.add_message(
            MessageDef(
                session_id=session_id,
                from_agent="user",
                message_type="user",
                content=prompt,
            )
        )

        from ..web.routes.ideation import _IDEATION_AGENTS

        pattern = PatternDef(
            id="ideation-network",
            name="Ideation Network",
            pattern_type="network",
            agents=[a["id"] for a in _IDEATION_AGENTS],
        )

        async def _run():
            try:
                await run_pattern(pattern, session.id, prompt, max_rounds=3)
            except Exception as _e:
                logger.warning("launch_ideation background error: %s", _e)

        asyncio.ensure_future(_run())
        return json.dumps(
            {
                "ok": True,
                "session_id": session_id,
                "url": f"/ideation?session_id={session_id}",
                "message": f"Idéation lancée avec 5 agents. Résultats sur /ideation?session_id={session_id}",
            }
        )


class LaunchMktIdeationTool(BaseTool):
    name = "launch_mkt_ideation"
    description = (
        "Launch a marketing ideation session (CMO, Content Strategist, Growth Hacker, Brand Strategist, "
        "Community Manager). Returns session_id immediately. "
        "Use to brainstorm marketing campaigns, go-to-market strategies, brand positioning."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import uuid
        import asyncio
        from ..sessions.store import get_session_store, SessionDef, MessageDef
        from ..patterns.engine import run_pattern
        from ..patterns.store import PatternDef

        prompt = (params.get("prompt") or params.get("question") or "").strip()
        if not prompt:
            return json.dumps({"error": "prompt is required"})

        session_id = str(uuid.uuid4())[:8]
        store = get_session_store()
        session = store.create(
            SessionDef(
                id=session_id,
                name=f"Mkt Idéation: {prompt[:60]}",
                goal=prompt,
                status="active",
                config={"type": "mkt_ideation", "pattern": "network"},
            )
        )
        store.add_message(
            MessageDef(
                session_id=session_id,
                from_agent="user",
                message_type="user",
                content=prompt,
            )
        )

        from ..web.routes.mkt_ideation import _MKT_AGENTS

        pattern = PatternDef(
            id="mkt-ideation-network",
            name="Marketing Ideation Network",
            pattern_type="network",
            agents=[a["id"] for a in _MKT_AGENTS],
        )

        async def _run():
            try:
                await run_pattern(pattern, session.id, prompt, max_rounds=3)
            except Exception as _e:
                logger.warning("launch_mkt_ideation background error: %s", _e)

        asyncio.ensure_future(_run())
        return json.dumps(
            {
                "ok": True,
                "session_id": session_id,
                "url": f"/mkt-ideation?session_id={session_id}",
                "message": f"Idéation marketing lancée. Résultats sur /mkt-ideation?session_id={session_id}",
            }
        )


class LaunchGroupIdeationTool(BaseTool):
    name = "launch_group_ideation"
    description = (
        "Launch a specialized community ideation with a predefined group of expert agents. "
        "Available groups: 'knowledge' (Knowledge & Recherche), 'archi' (Architecture & Design), "
        "'security' (Sécurité & Conformité), 'data-ai' (Data & IA), 'pi-planning' (PI Planning & SAFe). "
        "Returns session_id immediately."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import uuid
        import asyncio
        from ..sessions.store import get_session_store, SessionDef, MessageDef
        from ..patterns.engine import run_pattern
        from ..patterns.store import PatternDef
        from ..web.routes.group_ideation import GROUP_CONFIGS

        group_id = (params.get("group_id") or "").strip()
        prompt = (params.get("prompt") or params.get("question") or "").strip()

        if not group_id:
            return json.dumps(
                {
                    "error": "group_id is required",
                    "available_groups": list(GROUP_CONFIGS.keys()),
                }
            )
        if group_id not in GROUP_CONFIGS:
            return json.dumps(
                {
                    "error": f"Unknown group '{group_id}'",
                    "available_groups": list(GROUP_CONFIGS.keys()),
                }
            )
        if not prompt:
            return json.dumps({"error": "prompt is required"})

        group = GROUP_CONFIGS[group_id]
        session_id = str(uuid.uuid4())[:8]
        store = get_session_store()
        session = store.create(
            SessionDef(
                id=session_id,
                name=f"{group['name']}: {prompt[:60]}",
                goal=prompt,
                status="active",
                config={"type": f"group_{group_id}", "pattern": "network"},
            )
        )
        store.add_message(
            MessageDef(
                session_id=session_id,
                from_agent="user",
                message_type="user",
                content=prompt,
            )
        )

        pattern = PatternDef(
            id=f"group-{group_id}-network",
            name=f"{group['name']} Network",
            type="network",
            agents=[a["id"] for a in group["agents"]],
        )

        async def _run():
            try:
                await run_pattern(pattern, session.id, prompt, max_rounds=3)
            except Exception as _e:
                logger.warning("launch_group_ideation background error: %s", _e)

        asyncio.ensure_future(_run())
        return json.dumps(
            {
                "ok": True,
                "session_id": session_id,
                "group": group_id,
                "group_name": group["name"],
                "url": f"/group/{group_id}?session_id={session_id}",
                "message": f"Communauté '{group['name']}' lancée. Résultats sur /group/{group_id}?session_id={session_id}",
            }
        )


class PlatformCreateDomainTool(BaseTool):
    name = "create_domain"
    description = (
        "Create a new technical domain (a grouping project) with its own workspace, "
        "standard missions (TMA/MCO, Security, Tech Debt), and optional sub-projects. "
        "Params: name (required), description, vision, sub_projects (list of {name, description} dicts). "
        "A domain is a top-level structural grouping — use it for 'Frontend', 'Backend', 'Data Platform', etc. "
        "Returns domain_id, name, workspace, missions, and created sub-project ids."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import uuid
        import datetime
        from ..projects.manager import get_project_store, Project, scaffold_project

        name = params.get("name", "").strip()
        if not name:
            return json.dumps({"error": "name is required"})

        store = get_project_store()
        domain = Project(
            id=str(uuid.uuid4())[:8],
            name=name,
            path="",
            description=params.get("description", f"Domain: {name}"),
            vision=params.get("vision", params.get("description", "")),
            factory_type="domain",
            domains=[name.lower()],
            created_at=datetime.datetime.utcnow().isoformat(),
        )
        domain = store.create(domain)

        scaffold_result = {}
        try:
            scaffold_result = scaffold_project(domain)
        except Exception as _e:
            scaffold_result = {"error": str(_e)}

        missions_created = []
        try:
            from ..epics.store import get_epic_store

            m_store = get_epic_store()
            missions_created = [
                {
                    "mission_id": m.id,
                    "name": m.name,
                    "workflow": m.workflow_id,
                    "status": m.status,
                }
                for m in m_store.list_missions(project_id=domain.id, limit=20)
            ]
        except Exception:
            pass

        # Optionally create sub-projects
        sub_projects_created = []
        for sp in params.get("sub_projects", []):
            sp_name = (sp.get("name") or "").strip()
            if not sp_name:
                continue
            try:
                sub = Project(
                    id=str(uuid.uuid4())[:8],
                    name=sp_name,
                    path="",
                    description=sp.get("description", ""),
                    vision=sp.get("description", ""),
                    factory_type="software",
                    created_at=datetime.datetime.utcnow().isoformat(),
                )
                sub = store.create(sub)
                sub_projects_created.append({"project_id": sub.id, "name": sub.name})
            except Exception as _e:
                sub_projects_created.append({"name": sp_name, "error": str(_e)})

        return json.dumps(
            {
                "ok": True,
                "domain_id": domain.id,
                "name": domain.name,
                "workspace": domain.path,
                "scaffold": scaffold_result.get("actions", []),
                "epics": missions_created,
                "sub_projects": sub_projects_created,
            }
        )


class PlatformTmaTool(BaseTool):
    name = "platform_tma"
    description = (
        "Query TMA (Tierce Maintenance Applicative) status: open incidents, support tickets, "
        "and TMA mission health across projects. "
        "Params: project_id (optional, filter by project), severity (optional: P1/P2/P3/P4), "
        "status (optional: open/resolved/in_progress, default=open), limit (default=20). "
        "Returns incidents, tickets, and TMA mission summaries with counts."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..db.migrations import get_db

        db = get_db()
        project_id = params.get("project_id")
        severity = params.get("severity")
        status_filter = params.get("status", "open")
        limit = int(params.get("limit", 20))

        # Query platform_incidents
        inc_where = ["1=1"]
        inc_args = []
        if status_filter:
            inc_where.append("status = ?")
            inc_args.append(status_filter)
        if severity:
            inc_where.append("severity = ?")
            inc_args.append(severity)
        if project_id:
            inc_where.append(
                "mission_id IN (SELECT id FROM epics WHERE project_id = ?)"
            )
            inc_args.append(project_id)

        try:
            incidents = db.execute(
                f"SELECT id, title, severity, status, source, error_type, error_detail, created_at "
                f"FROM platform_incidents WHERE {' AND '.join(inc_where)} "
                f"ORDER BY created_at DESC LIMIT ?",
                inc_args + [limit],
            ).fetchall()
        except Exception:
            incidents = []

        # Query support_tickets
        tkt_where = ["1=1"]
        tkt_args = []
        if status_filter:
            tkt_where.append("status = ?")
            tkt_args.append(status_filter)
        if severity:
            tkt_where.append("severity = ?")
            tkt_args.append(severity)
        if project_id:
            tkt_where.append(
                "mission_id IN (SELECT id FROM epics WHERE project_id = ?)"
            )
            tkt_args.append(project_id)

        try:
            tickets = db.execute(
                f"SELECT id, title, severity, status, category, reporter, assignee, created_at "
                f"FROM support_tickets WHERE {' AND '.join(tkt_where)} "
                f"ORDER BY created_at DESC LIMIT ?",
                tkt_args + [limit],
            ).fetchall()
        except Exception:
            tickets = []

        # TMA missions summary
        tma_missions = []
        try:
            from ..epics.store import get_epic_store

            m_store = get_epic_store()
            all_missions = m_store.list_missions(limit=200)
            for m in all_missions:
                wf = getattr(m, "workflow_id", "") or ""
                if "tma" not in wf.lower() and "tma" not in (m.name or "").lower():
                    continue
                if project_id and getattr(m, "project_id", None) != project_id:
                    continue
                s = (
                    m.status
                    if isinstance(m.status, str)
                    else getattr(m.status, "value", str(m.status))
                )
                tma_missions.append(
                    {
                        "mission_id": m.id,
                        "name": m.name,
                        "project_id": getattr(m, "project_id", ""),
                        "status": s,
                        "workflow_id": wf,
                    }
                )
        except Exception:
            pass

        def _row(r):
            return dict(r) if hasattr(r, "keys") else dict(zip(r.keys(), r))

        return json.dumps(
            {
                "incidents": [_row(r) for r in incidents],
                "tickets": [_row(r) for r in tickets],
                "tma_missions": tma_missions,
                "summary": {
                    "open_incidents": len(incidents),
                    "open_tickets": len(tickets),
                    "tma_missions": len(tma_missions),
                },
            }
        )


class PlatformClusterTool(BaseTool):
    name = "platform_cluster"
    description = (
        "List all cluster nodes with their status (online/stale), role (master/slave), "
        "mode, URL, CPU%, MEM%, last_seen age, and version. "
        "Use this to check cluster health, see which nodes are active, and report on load distribution."
    )
    category = "platform"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from datetime import datetime

        from ..db.migrations import get_db

        db = get_db()
        try:
            rows = db.execute(
                "SELECT node_id, role, mode, url, last_seen, status, cpu_pct, mem_pct, version "
                "FROM platform_nodes ORDER BY role DESC, node_id"
            ).fetchall()
        except Exception as e:
            return json.dumps({"error": str(e), "nodes": []})
        finally:
            db.close()

        now = datetime.utcnow()
        nodes = []
        for r in rows:
            try:
                last_seen_dt = datetime.fromisoformat(
                    str(r["last_seen"]).replace("Z", "").split(".")[0]
                )
                age_s = int((now - last_seen_dt).total_seconds())
            except Exception:
                age_s = 9999
            nodes.append(
                {
                    "node_id": r["node_id"],
                    "role": r["role"],
                    "mode": r["mode"],
                    "url": r["url"] or "",
                    "status": "online" if age_s < 60 else "stale",
                    "age_seconds": age_s,
                    "cpu_pct": round(r["cpu_pct"] or 0, 1),
                    "mem_pct": round(r["mem_pct"] or 0, 1),
                    "version": r["version"] or "unknown",
                }
            )

        online = sum(1 for n in nodes if n["status"] == "online")
        return json.dumps(
            {
                "nodes": nodes,
                "summary": {
                    "total": len(nodes),
                    "online": online,
                    "stale": len(nodes) - online,
                },
            }
        )


class ConfluenceWritePageTool(BaseTool):
    name = "confluence_write_page"
    description = (
        "Create or update a Confluence page with markdown content. "
        "Params: title (required), content (markdown, required), "
        "space (Confluence space key, default from CONFLUENCE_SPACE env), "
        "parent_title (optional parent page title for hierarchy). "
        "Returns the page URL and ID."
    )
    category = "platform"
    allowed_roles = []

    async def execute(self, params: dict, agent=None) -> str:
        import json as _json

        title = (params.get("title") or "").strip()
        content = (params.get("content") or "").strip()
        if not title or not content:
            return _json.dumps({"error": "title and content are required"})

        space = (params.get("space") or "").strip() or None
        parent_title = (params.get("parent_title") or "").strip() or None

        try:
            from ..confluence.client import get_confluence_client
            from ..confluence.converter import md_to_confluence

            client = get_confluence_client()
            if space:
                client.space_key = space

            parent_id = None
            if parent_title:
                parent_page = client.find_page(parent_title, space_key=space)
                if parent_page:
                    parent_id = parent_page["id"]

            body_xhtml = md_to_confluence(content)
            page = client.create_or_update(
                title=title,
                body_xhtml=body_xhtml,
                parent_id=parent_id,
            )
            url = f"{client.base_url}/pages/{page.get('id', '')}"
            return _json.dumps(
                {"ok": True, "page_id": page.get("id"), "title": title, "url": url}
            )
        except Exception as e:
            return _json.dumps({"error": str(e)})


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
    registry.register(PlatformCreateSprintTool())
    registry.register(PlatformLaunchEpicRunTool())
    registry.register(PlatformResumeRunTool())
    registry.register(PlatformCheckRunTool())
    registry.register(PlatformCreateProjectTool())
    registry.register(PlatformCreateDomainTool())
    registry.register(PlatformCreateMissionTool())
    registry.register(PlatformTmaTool())
    registry.register(LaunchIdeationTool())
    registry.register(LaunchMktIdeationTool())
    registry.register(LaunchGroupIdeationTool())
    registry.register(PlatformClusterTool())
    registry.register(ConfluenceWritePageTool())
