"""Tool schema definitions — sub-module of platform/agents/tool_schemas/.

WHY: tool_schemas.py grew to 3313L containing 6 large schema functions.
Split into sub-modules by category for readability without breaking any callers
(package __init__.py re-exports all public symbols).
"""
from __future__ import annotations
# Ref: feat-agents-list
def _platform_schemas() -> list[dict]:
    """Platform introspection and lifecycle tool schemas."""
    return [
        # ── Platform introspection tools (self-aware) ──
        {
            "type": "function",
            "function": {
                "name": "platform_agents",
                "description": "List all platform agents or get details of one (id, name, role, skills, persona).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID to get details. Omit to list all.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_missions",
                "description": "List all missions/epics or get details including phase statuses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_id": {
                            "type": "string",
                            "description": "Mission ID. Omit to list all.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_memory_search",
                "description": "Search platform memory (project or global). FTS5 full-text search across all knowledge entries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "project_id": {
                            "type": "string",
                            "description": "Project/mission ID for project-specific memory",
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter: architecture, vision, team, process, backlog",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_metrics",
                "description": "Get platform statistics: agent count, missions, sessions, messages.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_sessions",
                "description": "List recent sessions or get messages from a specific session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to get messages. Omit to list recent sessions.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max messages (default 30)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_workflows",
                "description": "List available ceremony templates (workflows) with their phases and patterns.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        # ── Project lifecycle tools (Architecture First) ──
        {
            "type": "function",
            "function": {
                "name": "get_project_health",
                "description": "Get a project's health: missions by category, current phase, docs status (spec/schema/workflows/conventions/security).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Project ID"},
                    },
                    "required": ["project_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_phase_gate",
                "description": "Check if a project can transition to a target phase. Returns allowed=true/false and blockers. Always call before set_project_phase.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "target_phase": {
                            "type": "string",
                            "enum": [
                                "discovery",
                                "mvp",
                                "v1",
                                "run",
                                "maintenance",
                                "scale",
                            ],
                        },
                    },
                    "required": ["project_id", "target_phase"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_project_phase",
                "description": "Transition a project to a new lifecycle phase. Blocked if gate not satisfied. Call get_phase_gate first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "phase": {
                            "type": "string",
                            "enum": [
                                "discovery",
                                "mvp",
                                "v1",
                                "run",
                                "maintenance",
                                "scale",
                            ],
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Bypass gate check — only if user explicitly authorized",
                            "default": False,
                        },
                    },
                    "required": ["project_id", "phase"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_next_missions",
                "description": "Suggest next missions to create or activate based on project phase and health.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                    },
                    "required": ["project_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_doc",
                "description": "Read an architecture doc from project's docs/ folder (spec.md, schema.md, workflows.md, conventions.md, security.md).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "filename": {
                            "type": "string",
                            "enum": [
                                "spec.md",
                                "schema.md",
                                "workflows.md",
                                "conventions.md",
                                "security.md",
                            ],
                        },
                    },
                    "required": ["project_id", "filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_project_doc",
                "description": "Write or update an architecture doc in project's docs/ folder. Use to fill spec, schema, workflows, conventions or security docs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "filename": {
                            "type": "string",
                            "enum": [
                                "spec.md",
                                "schema.md",
                                "workflows.md",
                                "conventions.md",
                                "security.md",
                            ],
                        },
                        "content": {
                            "type": "string",
                            "description": "Full markdown content to write",
                        },
                    },
                    "required": ["project_id", "filename", "content"],
                },
            },
        },
        # ── Platform creation tools (CTO Jarvis: create projects + missions) ──
        {
            "type": "function",
            "function": {
                "name": "create_project",
                "description": "Create a new project on the platform. If git_url is provided, clones the existing repo as workspace. Otherwise scaffolds from scratch. Returns the project id and workspace path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Project name (required)",
                        },
                        "git_url": {
                            "type": "string",
                            "description": "HTTPS or SSH URL of existing repo to clone as workspace (optional — leave empty to scaffold new project)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Project description",
                        },
                        "vision": {
                            "type": "string",
                            "description": "Project vision / long-term goal",
                        },
                        "factory_type": {
                            "type": "string",
                            "enum": ["software", "data", "security", "standalone"],
                            "description": "Type of project",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_mission",
                "description": "Create a new mission (epic) on the platform. Returns the mission id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Mission name (required)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Mission description",
                        },
                        "goal": {
                            "type": "string",
                            "description": "Mission goal / acceptance criteria",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Parent project ID",
                        },
                        "workflow_id": {
                            "type": "string",
                            "description": "Workflow template ID (optional)",
                        },
                        "target_branch": {
                            "type": "string",
                            "description": "Git branch where agents will deliver code (e.g. 'feature/sav-parcours'). Auto-created in the project workspace.",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        # ── Backlog tools (create features/stories for AO traceability) ──
        {
            "type": "function",
            "function": {
                "name": "create_feature",
                "description": "Create a feature in the product backlog linked to an epic. Each feature gets a REQ-ID for AO traceability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "epic_id": {
                            "type": "string",
                            "description": "Parent epic/mission ID",
                        },
                        "name": {"type": "string", "description": "Feature name"},
                        "description": {
                            "type": "string",
                            "description": "Feature description",
                        },
                        "acceptance_criteria": {
                            "type": "string",
                            "description": "Acceptance criteria",
                        },
                        "priority": {
                            "type": "integer",
                            "description": "Priority (1=highest, 10=lowest)",
                        },
                        "story_points": {
                            "type": "integer",
                            "description": "Story points estimate",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_story",
                "description": "Create a user story under a feature. Links to a feature for backlog traceability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "feature_id": {
                            "type": "string",
                            "description": "Parent feature ID",
                        },
                        "title": {
                            "type": "string",
                            "description": "User story title (e.g. US-E1-01: Intégration FC)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Story description",
                        },
                        "acceptance_criteria": {
                            "type": "string",
                            "description": "Acceptance criteria",
                        },
                        "story_points": {
                            "type": "integer",
                            "description": "Story points estimate",
                        },
                        "priority": {
                            "type": "integer",
                            "description": "Priority (1=highest)",
                        },
                    },
                    "required": ["title"],
                },
            },
        },
        # ── Composition tools (dynamic workflow/team/mission) ──
        {
            "type": "function",
            "function": {
                "name": "compose_workflow",
                "description": "Create a dynamic workflow definition. Define phases, patterns, and agent assignments based on project analysis. Returns workflow ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Workflow ID (auto-generated if omitted)",
                        },
                        "name": {"type": "string", "description": "Workflow name"},
                        "description": {
                            "type": "string",
                            "description": "What this workflow does",
                        },
                        "phases": {
                            "type": "array",
                            "description": "List of phases: [{id, name, pattern, agents: [agent_ids], config, gate}]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "pattern": {
                                        "type": "string",
                                        "enum": [
                                            "solo",
                                            "sequential",
                                            "parallel",
                                            "loop",
                                            "hierarchical",
                                            "network",
                                            "router",
                                            "aggregator",
                                            "human-in-the-loop",
                                        ],
                                    },
                                    "agents": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "config": {"type": "object"},
                                    "gate": {
                                        "type": "string",
                                        "enum": ["all_approved", "no_veto", "always"],
                                    },
                                },
                            },
                        },
                    },
                    "required": ["name", "phases"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "launch_epic_run",
                "description": "Launch the autonomous execution of an epic/mission. Creates a workflow run and starts phase execution in the background. Returns run_id and session_id. This is the ESSENTIAL step to start a mission after create_mission.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "epic_id": {
                            "type": "string",
                            "description": "The mission/epic ID returned by create_mission",
                        },
                        "workflow_id": {
                            "type": "string",
                            "description": "Optional: workflow ID (uses mission's default if omitted)",
                        },
                    },
                    "required": ["epic_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_run_status",
                "description": "Check the status of a running epic/mission. Returns phase progress, current phase, success/failure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "run_id": {
                            "type": "string",
                            "description": "The run_id or session_id from launch_epic_run",
                        },
                    },
                    "required": ["run_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_team",
                "description": "Create a feature team with specialized agents. Each agent gets a prompt tailored to the domain and stack.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "team_name": {
                            "type": "string",
                            "description": "Team name (e.g. 'Auth Team', 'Booking Team')",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Domain: auth, booking, payment, admin, infra, qa, proto",
                        },
                        "stack": {
                            "type": "string",
                            "description": "Tech stack: 'Rust axum/sqlx', 'SvelteKit', 'Python FastAPI'",
                        },
                        "roles": {
                            "type": "array",
                            "description": "Team members: [{id, name, role, skills: [], prompt}]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "role": {"type": "string"},
                                    "skills": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "prompt": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["team_name", "domain", "roles"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_sub_mission",
                "description": "Create a sub-mission (Feature) linked to the parent epic. Assign a workflow and team.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_epic_id": {
                            "type": "string",
                            "description": "Parent mission/epic ID",
                        },
                        "name": {"type": "string", "description": "Feature name"},
                        "description": {
                            "type": "string",
                            "description": "Feature description",
                        },
                        "goal": {
                            "type": "string",
                            "description": "Acceptance criteria",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier",
                        },
                        "type": {
                            "type": "string",
                            "description": "Mission type: feature|story",
                            "enum": ["feature", "story"],
                        },
                        "workflow_id": {
                            "type": "string",
                            "description": "Workflow to execute for this feature",
                        },
                        "wsjf_score": {
                            "type": "number",
                            "description": "WSJF priority score",
                        },
                        "config": {
                            "type": "object",
                            "description": "Extra config: team_ids, stack, ao_refs",
                        },
                    },
                    "required": ["parent_epic_id", "name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_sub_missions",
                "description": "List all sub-missions (Features) of a parent mission (Epic).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_epic_id": {
                            "type": "string",
                            "description": "Parent mission ID",
                        },
                    },
                    "required": ["parent_epic_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_constraints",
                "description": "Set execution constraints on a mission: WIP limits, stack rules, AO refs, sprint duration.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_id": {
                            "type": "string",
                            "description": "Mission ID to update",
                        },
                        "wip_limit": {
                            "type": "integer",
                            "description": "Max concurrent workers",
                        },
                        "stack": {
                            "type": "string",
                            "description": "Required tech stack",
                        },
                        "ao_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "AO reference IDs",
                        },
                        "sprint_duration": {
                            "type": "string",
                            "description": "Sprint duration (e.g. '4h', '1d')",
                        },
                        "max_workers": {
                            "type": "integer",
                            "description": "Max parallel workers",
                        },
                    },
                    "required": ["mission_id"],
                },
            },
        },
        # Android build tools
        {
            "type": "function",
            "function": {
                "name": "android_build",
                "description": "Build Android project (assembleDebug) via Gradle in the android-builder container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_path": {
                            "type": "string",
                            "description": "Path to Android project inside container (default: /workspace)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "android_test",
                "description": "Run Android unit tests (testDebugUnitTest) via Gradle.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_path": {
                            "type": "string",
                            "description": "Path to Android project",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "android_lint",
                "description": "Run Android Lint checks via Gradle.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_path": {
                            "type": "string",
                            "description": "Path to Android project",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "android_emulator_test",
                "description": "Start headless Android emulator and run instrumented tests. Takes 2-5 min.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_path": {
                            "type": "string",
                            "description": "Path to Android project",
                        },
                    },
                },
            },
        },
        # ── MCP Dynamic Tools ──────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "mcp_fetch_fetch",
                "description": "Fetch a URL and return its content as markdown. Use for web research, API calls, documentation lookup.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "max_length": {
                            "type": "integer",
                            "description": "Max response chars (default 5000)",
                        },
                        "raw": {
                            "type": "boolean",
                            "description": "Return raw HTML instead of markdown",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_memory_create_entities",
                "description": "Create entities in the knowledge graph memory. Store concepts, decisions, architecture choices.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "entityType": {"type": "string"},
                                    "observations": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                            "description": "Entities to create [{name, entityType, observations}]",
                        },
                    },
                    "required": ["entities"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_memory_search_nodes",
                "description": "Search the knowledge graph memory by query string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_memory_create_relations",
                "description": "Create relations between entities in the knowledge graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "from": {"type": "string"},
                                    "to": {"type": "string"},
                                    "relationType": {"type": "string"},
                                },
                            },
                            "description": "Relations [{from, to, relationType}]",
                        },
                    },
                    "required": ["relations"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_playwright_browser_navigate",
                "description": "Navigate browser to URL for E2E testing. Returns page snapshot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to navigate to"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_playwright_browser_snapshot",
                "description": "Take accessibility snapshot of current browser page for E2E assertions.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_playwright_browser_click",
                "description": "Click an element on the page by CSS selector or text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "Human-readable element description from snapshot",
                        },
                        "ref": {
                            "type": "string",
                            "description": "Exact target element reference from snapshot",
                        },
                    },
                    "required": ["element", "ref"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_playwright_browser_take_screenshot",
                "description": "Take a PNG screenshot of the current browser page. Use after browser_navigate to capture visual state for QA evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Screenshot name (e.g. 'homepage', 'login-form')",
                        },
                        "selector": {
                            "type": "string",
                            "description": "Optional CSS selector to screenshot a specific element",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_playwright_browser_type",
                "description": "Type text into an input field on the page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "Human-readable element description",
                        },
                        "ref": {
                            "type": "string",
                            "description": "Exact target element reference from snapshot",
                        },
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["element", "ref", "text"],
                },
            },
        },
        # ── Ideation & Community Launch tools (Jarvis / CTO delegation) ──
        {
            "type": "function",
            "function": {
                "name": "launch_ideation",
                "description": (
                    "Launch a multi-agent ideation session (Business Analyst, Solution Architect, "
                    "UX Designer, Product Manager, Tech Lead). Returns session_id and URL. "
                    "Use to explore product ideas, architecture questions, strategic directions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The question or topic to explore with the ideation team",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "launch_mkt_ideation",
                "description": (
                    "Launch a marketing ideation session (CMO, Content Strategist, Growth Hacker, "
                    "Brand Strategist, Community Manager). Returns session_id and URL. "
                    "Use for campaigns, go-to-market, brand positioning, growth strategies."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The marketing topic or campaign to ideate on",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "launch_group_ideation",
                "description": (
                    "Launch a specialized community ideation with domain experts. "
                    "Available groups: 'knowledge' (Knowledge & Recherche), "
                    "'archi' (Architecture & Design), 'security' (Sécurité & Conformité), "
                    "'data-ai' (Data & IA), 'pi-planning' (PI Planning & SAFe). "
                    "Returns session_id and URL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "string",
                            "enum": [
                                "knowledge",
                                "archi",
                                "security",
                                "data-ai",
                                "pi-planning",
                            ],
                            "description": "The expert community to engage",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "The question or topic for the expert community",
                        },
                    },
                    "required": ["group_id", "prompt"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confluence_write_page",
                "description": "Create or update a Confluence wiki page with markdown content. Use to publish documentation, architecture notes, project wiki, onboarding guides.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Page title (required)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Page content in Markdown (required)",
                        },
                        "space": {
                            "type": "string",
                            "description": "Confluence space key (default: MYPROJECT)",
                        },
                        "parent_title": {
                            "type": "string",
                            "description": "Title of parent page for hierarchy (optional)",
                        },
                    },
                    "required": ["title", "content"],
                },
            },
        },
    ]


# ── Traceability tools ──

TRACEABILITY_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "legacy_scan",
            "description": (
                "Scan project source code to auto-discover legacy items "
                "(tables, classes, endpoints, configs). Creates legacy_items entries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID to scan",
                    },
                    "scope": {
                        "type": "string",
                        "description": "What to scan: 'all', 'db' (tables/columns/FK), 'code' (classes/methods), 'api' (endpoints)",
                        "enum": ["all", "db", "code", "api"],
                    },
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to scan (relative to project root). Omit for full project.",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_link",
            "description": (
                "Create or list bidirectional traceability links between items "
                "(legacy_item↔story↔code↔test). Link types: migrates_from, implements, "
                "tests, depends_on, covers, maps_to, replaces, references."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["create", "list"],
                    },
                    "source_id": {
                        "type": "string",
                        "description": "Source item ID (e.g. li-abc123, feat-xyz, us-456)",
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Source type",
                        "enum": ["legacy_item", "feature", "story", "code", "test", "epic"],
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Target item ID (for create)",
                    },
                    "target_type": {
                        "type": "string",
                        "description": "Target type (for create)",
                        "enum": ["legacy_item", "feature", "story", "code", "test", "epic"],
                    },
                    "link_type": {
                        "type": "string",
                        "description": "Type of link (for create/filter)",
                        "enum": [
                            "migrates_from", "implements", "tests",
                            "depends_on", "covers", "maps_to", "replaces", "references",
                        ],
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the link",
                    },
                },
                "required": ["action", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_coverage",
            "description": (
                "Get traceability coverage report for a project: % of legacy items "
                "linked to stories/code/tests, plus orphan detection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID",
                    },
                    "include_orphans": {
                        "type": "boolean",
                        "description": "Include list of orphaned items (unlinked). Default true.",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_validate",
            "description": (
                "Validate traceability completeness with full matrix view: "
                "legacy_item → story → code → test chain per item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID",
                    },
                    "item_type": {
                        "type": "string",
                        "description": "Filter by legacy item type (table, class, endpoint...)",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_record",
            "description": (
                "Record a traceability artifact for a feature across the 13-layer chain: "
                "persona, ihm, code, test_tu, test_e2e, crud, rbac, screen, nft. "
                "Call this after writing code, tests, screens, CRUD endpoints, RBAC rules, or NFTs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_id": {"type": "string", "description": "Feature UUID (feat-XXXXXXXX)"},
                    "epic_id": {"type": "string", "description": "Epic/run ID"},
                    "project_id": {"type": "string", "description": "Project ID"},
                    "layer": {
                        "type": "string",
                        "enum": ["code", "ihm", "test_tu", "tu", "test_e2e", "e2e", "crud", "rbac", "screen", "nft", "persona"],
                        "description": "Which traceability layer this artifact covers (tu=alias for test_tu, e2e=alias for test_e2e)",
                    },
                    "artifact_id": {"type": "string", "description": "File path, test name, endpoint, role name, or external key"},
                    "artifact_name": {"type": "string", "description": "Human-readable label"},
                    "notes": {"type": "string", "description": "Optional context"},
                    "persona_name": {"type": "string", "description": "Persona name (layer=persona only)"},
                    "persona_role": {"type": "string", "description": "Persona role (layer=persona only)"},
                    "nft_type": {
                        "type": "string",
                        "enum": ["perf", "security", "a11y", "i18n", "load", "compliance"],
                        "description": "NFT category (layer=nft only)",
                    },
                    "criterion": {"type": "string", "description": "NFT success criterion, e.g. 'p95 < 200ms'"},
                },
                "required": ["feature_id", "layer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_chain_report",
            "description": (
                "Get the full 13-layer traceability chain report for an epic. "
                "Shows per-feature coverage: persona, ihm, code, tu, e2e, crud, rbac, screens, nft."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "epic_id": {"type": "string", "description": "Epic/run ID"},
                },
                "required": ["epic_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceability_check_e2e",
            "description": (
                "Validate the full E2E traceability chain for an epic. "
                "Returns PASS/FAIL with per-layer coverage % and gap list. "
                "Use at the end of a sprint or phase to confirm all layers are covered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "epic_id": {"type": "string", "description": "Epic/run ID"},
                    "threshold": {
                        "type": "integer",
                        "description": "Min % of features that must be fully covered (default 80)",
                    },
                },
                "required": ["epic_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_traceability_report",
            "description": (
                "Get the full 13-layer traceability chain report for an entire project. "
                "Aggregates all epics/features and reports coverage for persona, ihm, "
                "code, tu, e2e, crud, rbac, screens, nft."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_traceability_check_e2e",
            "description": (
                "Validate the full project-wide traceability chain. "
                "Returns PASS/FAIL with per-layer coverage % and gap list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "threshold": {
                        "type": "integer",
                        "description": "Min % of features that must be fully covered (default 80)",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_traceability_export_sqlite",
            "description": (
                "Export a standalone SQLite DB containing the full project traceability graph: "
                "epics, personas, features, stories, ACs, artifacts, links, screens, NFTs, "
                "and per-feature coverage status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID"},
                    "output_path": {
                        "type": "string",
                        "description": "Output .sqlite path (optional; defaults to /tmp/{project_id}_traceability.sqlite)",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
]
