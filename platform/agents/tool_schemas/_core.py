"""Tool schema definitions — sub-module of platform/agents/tool_schemas/.

WHY: tool_schemas.py grew to 3313L containing 6 large schema functions.
Split into sub-modules by category for readability without breaking any callers
(package __init__.py re-exports all public symbols).
"""
from __future__ import annotations
def _core_schemas() -> list[dict]:
    """Core file/code/git/shell/communication tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "code_read",
                "description": "Read the contents of a file. Use this to explore project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative file path",
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Max lines to read (default 500)",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_search",
                "description": "Search for a pattern in project files using ripgrep.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to search for",
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search in (default: project root)",
                        },
                        "glob": {
                            "type": "string",
                            "description": "File glob filter, e.g. '*.py'",
                        },
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_write",
                "description": "Write content to a file (creates backup of existing).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_edit",
                "description": "Replace a specific string in a file (surgical edit).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "old_str": {
                            "type": "string",
                            "description": "Exact string to find and replace",
                        },
                        "new_str": {
                            "type": "string",
                            "description": "Replacement string",
                        },
                    },
                    "required": ["path", "old_str", "new_str"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_create_branch",
                "description": "Create and checkout a named git branch. Use before starting feature work to ensure delivery lands on a clean named branch (e.g. 'feature/sav-parcours').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "branch": {
                            "type": "string",
                            "description": "Branch name to create (required), e.g. 'feature/sav-parcours'",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Workspace path (default: project root)",
                        },
                        "from_branch": {
                            "type": "string",
                            "description": "Base branch to branch from (default: current HEAD)",
                        },
                    },
                    "required": ["branch"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_clone",
                "description": "Clone a remote git repository into a local workspace. Use to onboard existing projects.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "HTTPS or SSH git remote URL (required)",
                        },
                        "dest": {
                            "type": "string",
                            "description": "Local destination path (default: auto-derived from repo name in workspace/)",
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch or tag to checkout (default: default branch)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Show git status of the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Working directory (default: project root)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_log",
                "description": "Show recent git commits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "limit": {
                            "type": "integer",
                            "description": "Number of commits (default 10)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff",
                "description": "Show git diff of changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "path": {
                            "type": "string",
                            "description": "Specific file to diff",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_search",
                "description": "Search project memory for stored knowledge, facts, and context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "scope": {
                            "type": "string",
                            "description": "Memory scope: project | global",
                            "enum": ["project", "global"],
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_store",
                "description": "Store a fact or learning in project memory for future reference.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Short key/title for the memory",
                        },
                        "value": {"type": "string", "description": "Content to store"},
                        "category": {
                            "type": "string",
                            "description": "Category: decision | fact | learning | context",
                        },
                    },
                    "required": ["key", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_retrieve",
                "description": "Retrieve a specific memory entry by exact key. Use when you know the exact key of a stored decision, fact, or learning.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Exact key to retrieve"},
                    },
                    "required": ["key"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_prune",
                "description": "Delete memory entries that are no longer relevant. Use to keep project memory clean and focused.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Exact key to delete (optional)"},
                        "category": {"type": "string", "description": "Delete all entries in this category (optional)"},
                        "older_than_days": {"type": "integer", "description": "Delete entries older than N days (optional)"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plan_create",
                "description": "Create an execution plan before tackling a complex task. Use this to break down multi-step work into trackable steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short plan title"},
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ordered list of steps to execute",
                        },
                    },
                    "required": ["title", "steps"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plan_update",
                "description": "Update a step status in the current plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "step": {
                            "type": "integer",
                            "description": "Step number (1-based)",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["in_progress", "done", "blocked", "skipped"],
                            "description": "New status for the step",
                        },
                        "result": {
                            "type": "string",
                            "description": "Optional short result/note",
                        },
                    },
                    "required": ["step", "status"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "plan_get",
                "description": "Get the current plan and progress.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Max depth (default 2)",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deep_search",
                "description": "RLM Deep Search (MIT CSAIL arXiv:2512.24601). Recursive Language Model that iteratively explores the entire project codebase using a WRITE-EXECUTE-OBSERVE-DECIDE loop with parallel sub-agents. Use for complex questions like 'how does authentication work', 'find all API routes and their guards', 'explain the database schema'. Returns a comprehensive, factual analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question or exploration goal — e.g. 'how is authentication implemented', 'find all REST endpoints', 'explain the data model'",
                        },
                        "max_iterations": {
                            "type": "integer",
                            "description": "Max RLM iterations (default 3, max 3). Higher = deeper but slower.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "docker_deploy",
                "description": "Build and run the workspace project as a Docker container. Auto-generates Dockerfile if missing, installs deps, builds image, starts container, health-checks. Returns live URL. Use this to ACTUALLY deploy generated code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "Project workspace directory containing the code to deploy",
                        },
                        "mission_id": {
                            "type": "string",
                            "description": "Mission ID (used for container naming and tracking)",
                        },
                    },
                    "required": ["cwd"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "docker_stop",
                "description": "Stop and remove a deployed container.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_id": {
                            "type": "string",
                            "description": "Mission ID of the container to stop",
                        },
                        "container": {
                            "type": "string",
                            "description": "Container name (alternative to mission_id)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "docker_status",
                "description": "Check status of a deployed container (running/stopped, URL, recent logs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_id": {
                            "type": "string",
                            "description": "Mission ID to check",
                        },
                        "container": {
                            "type": "string",
                            "description": "Container name (alternative to mission_id)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_commit",
                "description": "Stage all changes and commit to git.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "message": {"type": "string", "description": "Commit message"},
                    },
                    "required": ["message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_create_pr",
                "description": "Create a GitHub Pull Request from current branch. Fires a Slack/webhook notification and auto-triggers a code review.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "PR title"},
                        "body": {
                            "type": "string",
                            "description": "PR description (markdown)",
                        },
                        "base": {
                            "type": "string",
                            "description": "Base branch (default: main)",
                        },
                        "cwd": {"type": "string", "description": "Working directory"},
                    },
                    "required": ["title"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_get_pr_diff",
                "description": "Fetch the diff and metadata of a GitHub Pull Request for code review.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pr": {
                            "type": "string",
                            "description": "PR number or full GitHub URL",
                        },
                        "cwd": {"type": "string", "description": "Working directory"},
                    },
                    "required": ["pr"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_post_pr_review",
                "description": "Post a structured code review on a GitHub PR (APPROVE, REQUEST_CHANGES, or COMMENT).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pr": {
                            "type": "string",
                            "description": "PR number or GitHub URL",
                        },
                        "body": {
                            "type": "string",
                            "description": "Review body (markdown)",
                        },
                        "event": {
                            "type": "string",
                            "enum": ["APPROVE", "REQUEST_CHANGES", "COMMENT"],
                            "description": "Review type (default: COMMENT)",
                        },
                        "cwd": {"type": "string", "description": "Working directory"},
                    },
                    "required": ["pr", "body"],
                },
            },
        },
    ]


def _phase_schemas() -> list[dict]:
    """Phase orchestration tool schemas."""
    return [
        # ── Phase orchestration tools (CDP Mission Control) ──
        {
            "type": "function",
            "function": {
                "name": "run_phase",
                "description": "Launch a phase of the product lifecycle mission. Runs a multi-agent pattern (network, hierarchical, loop, etc.) with the phase's team. Returns a summary of results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase_id": {
                            "type": "string",
                            "description": "Phase ID (e.g. 'ideation', 'dev-sprint', 'qa-campaign')",
                        },
                        "brief": {
                            "type": "string",
                            "description": "Context/brief to pass to the phase agents",
                        },
                    },
                    "required": ["phase_id", "brief"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_phase_status",
                "description": "Get the current status of a specific phase.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase_id": {
                            "type": "string",
                            "description": "Phase ID to check",
                        },
                    },
                    "required": ["phase_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_phases",
                "description": "List all phases of the current mission with their status, pattern, and agents.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_validation",
                "description": "Request human validation at a checkpoint. Sends a question and waits for GO/NOGO.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Question to ask the human decision-maker",
                        },
                        "options": {
                            "type": "string",
                            "description": "Available options, comma-separated (default: GO,NOGO,PIVOT)",
                        },
                    },
                    "required": ["question"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_project_context",
                "description": "Get full project context (vision, architecture, current state, memory).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]


def _web_schemas() -> list[dict]:
    """Web/Playwright/screenshot tool schemas."""
    return [
        # ── Playwright test/screenshot tools ──
        {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "Take a browser screenshot of a URL using Playwright headless. Saves PNG to screenshots/ dir. Returns inline image with [SCREENSHOT:path] marker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to screenshot (e.g. http://localhost:3000)",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (default: auto-generated timestamp)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "simulator_screenshot",
                "description": "Take a screenshot of the running iOS/macOS Simulator (xcrun simctl). The simulator must be booted. Returns inline image with [SCREENSHOT:path] marker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {
                            "type": "string",
                            "description": "Device name or UUID (default: 'booted' = currently running)",
                        },
                        "app_bundle": {
                            "type": "string",
                            "description": "Optional: app bundle ID to launch before capturing (e.g. com.example.MyApp)",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (default: auto-generated)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "playwright_test",
                "description": "Run Playwright E2E tests. Executes a test spec file, captures results and failure screenshots. Returns pass/fail with [SCREENSHOT:path] markers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "string",
                            "description": "Test spec file path (e.g. tests/e2e/smoke.spec.ts)",
                        },
                    },
                    "required": ["spec"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "browse",
                "description": "Open a URL in the browser for visual testing. Call this BEFORE take_screenshot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to open (e.g. http://localhost:3000)",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "take_screenshot",
                "description": "Take a PNG screenshot of the current browser page. Call browse(url) first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Screenshot name (e.g. homepage, login-page)",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_page",
                "description": "Get the accessibility tree of the current browser page for assertions.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_e2e_tests",
                "description": "Run full E2E test suite automatically: installs dependencies, starts dev server, takes browser screenshots, runs unit tests, returns full report. Call this for complete QA validation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "port": {
                            "type": "integer",
                            "description": "Port for dev server (default 3000)",
                        },
                    },
                },
            },
        },
    ]


