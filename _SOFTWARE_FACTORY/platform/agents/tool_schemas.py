"""Tool schemas and role-based tool mapping for the agent executor.

Contains OpenAI-compatible function-calling tool definitions and
role-based access control mappings. Extracted from executor.py.
"""
from __future__ import annotations
from typing import Optional


# Tool JSON schemas for OpenAI function-calling API
_TOOL_SCHEMAS: Optional[list[dict]] = None


def _get_tool_schemas() -> list[dict]:
    """Build OpenAI-compatible tool definitions from the registry."""
    global _TOOL_SCHEMAS
    if _TOOL_SCHEMAS is not None:
        return _TOOL_SCHEMAS

    schemas = [
        {
            "type": "function",
            "function": {
                "name": "code_read",
                "description": "Read the contents of a file. Use this to explore project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative file path"},
                        "max_lines": {"type": "integer", "description": "Max lines to read (default 500)"},
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
                        "pattern": {"type": "string", "description": "Regex pattern to search for"},
                        "path": {"type": "string", "description": "Directory to search in (default: project root)"},
                        "glob": {"type": "string", "description": "File glob filter, e.g. '*.py'"},
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
                        "content": {"type": "string", "description": "Content to write"},
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
                        "old_str": {"type": "string", "description": "Exact string to find and replace"},
                        "new_str": {"type": "string", "description": "Replacement string"},
                    },
                    "required": ["path", "old_str", "new_str"],
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
                        "cwd": {"type": "string", "description": "Working directory (default: project root)"},
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
                        "limit": {"type": "integer", "description": "Number of commits (default 10)"},
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
                        "path": {"type": "string", "description": "Specific file to diff"},
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
                        "scope": {"type": "string", "description": "Memory scope: project | global", "enum": ["project", "global"]},
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
                        "key": {"type": "string", "description": "Short key/title for the memory"},
                        "value": {"type": "string", "description": "Content to store"},
                        "category": {"type": "string", "description": "Category: decision | fact | learning | context"},
                    },
                    "required": ["key", "value"],
                },
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
                        "path": {"type": "string", "description": "Directory path to list"},
                        "depth": {"type": "integer", "description": "Max depth (default 2)"},
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
                        "query": {"type": "string", "description": "The question or exploration goal — e.g. 'how is authentication implemented', 'find all REST endpoints', 'explain the data model'"},
                        "max_iterations": {"type": "integer", "description": "Max RLM iterations (default 3, max 3). Higher = deeper but slower."},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "docker_build",
                "description": "Build a Docker image from a project directory containing a Dockerfile.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Project directory containing the Dockerfile"},
                        "image_name": {"type": "string", "description": "Name for the Docker image (e.g. 'macaron-iot-dashboard')"},
                    },
                    "required": ["cwd", "image_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deploy_azure",
                "description": "Deploy a Docker image to the Azure VM (4.233.64.30). Saves the image, transfers via SCP, loads and runs on the VM. Returns the public URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_name": {"type": "string", "description": "Docker image name to deploy (must be built first)"},
                        "container_port": {"type": "integer", "description": "Port the app listens on inside the container (e.g. 8080)"},
                        "host_port": {"type": "integer", "description": "Port to expose on the VM (0 = auto-assign)"},
                    },
                    "required": ["image_name", "container_port"],
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
        # ── Phase orchestration tools (CDP Mission Control) ──
        {
            "type": "function",
            "function": {
                "name": "run_phase",
                "description": "Launch a phase of the product lifecycle mission. Runs a multi-agent pattern (network, hierarchical, loop, etc.) with the phase's team. Returns a summary of results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase_id": {"type": "string", "description": "Phase ID (e.g. 'ideation', 'dev-sprint', 'qa-campaign')"},
                        "brief": {"type": "string", "description": "Context/brief to pass to the phase agents"},
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
                        "phase_id": {"type": "string", "description": "Phase ID to check"},
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
                        "question": {"type": "string", "description": "Question to ask the human decision-maker"},
                        "options": {"type": "string", "description": "Available options, comma-separated (default: GO,NOGO,PIVOT)"},
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
        # ── Playwright test/screenshot tools ──
        {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "Take a browser screenshot of a URL using Playwright headless. Saves PNG to screenshots/ dir. Returns inline image with [SCREENSHOT:path] marker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to screenshot (e.g. http://localhost:3000)"},
                        "filename": {"type": "string", "description": "Output filename (default: auto-generated timestamp)"},
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
                        "device": {"type": "string", "description": "Device name or UUID (default: 'booted' = currently running)"},
                        "app_bundle": {"type": "string", "description": "Optional: app bundle ID to launch before capturing (e.g. com.example.MyApp)"},
                        "filename": {"type": "string", "description": "Output filename (default: auto-generated)"},
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
                        "spec": {"type": "string", "description": "Test spec file path (e.g. tests/e2e/smoke.spec.ts)"},
                    },
                    "required": ["spec"],
                },
            },
        },
        # ── MCP: LRM tools (project knowledge) ──
        {
            "type": "function",
            "function": {
                "name": "lrm_locate",
                "description": "Find files in the project matching a pattern or description via LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Pattern or description (e.g. 'auth middleware', '*.test.ts')"},
                        "scope": {"type": "string", "description": "Limit search scope (e.g. 'src/', 'tests/')"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_summarize",
                "description": "Get a summary of a file or directory from the LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File or directory path to summarize"},
                        "focus": {"type": "string", "description": "What to focus on (e.g. 'API endpoints', 'data model')"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_conventions",
                "description": "Get coding conventions for a domain (rust, typescript, svelte, python).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "Domain: rust, typescript, svelte, python, kotlin, swift"},
                    },
                    "required": ["domain"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_examples",
                "description": "Get code examples from the project (tests, implementations, API patterns).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Example type: test, implementation, api, model"},
                        "domain": {"type": "string", "description": "Domain filter (e.g. 'auth', 'api')"},
                    },
                    "required": ["type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_build",
                "description": "Run build, test, or lint commands via the LRM server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command type: build, test, lint, check"},
                        "domain": {"type": "string", "description": "Target domain (e.g. 'backend', 'frontend')"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lrm_context",
                "description": "Get project context via RAG: vision, architecture, data_model, api_surface, conventions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Context category: vision, architecture, data_model, api_surface, conventions, all"},
                    },
                    "required": ["category"],
                },
            },
        },
        # ── MCP: Figma (design system) ──
        {
            "type": "function",
            "function": {
                "name": "figma_get_node",
                "description": "Get a Figma component node with its properties, variants, and styles.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma file key"},
                        "node_id": {"type": "string", "description": "Node ID (e.g. '37:1201')"},
                    },
                    "required": ["file_key", "node_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "figma_get_styles",
                "description": "Get design tokens (colors, typography, spacing) from a Figma file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma file key"},
                    },
                    "required": ["file_key"],
                },
            },
        },
        # ── MCP: Solaris (WCAG/design system validation) ──
        {
            "type": "function",
            "function": {
                "name": "solaris_wcag",
                "description": "Get WCAG accessibility pattern for a component (accordion, button, tabs, checkbox, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "WCAG pattern: accordion, button, tabs, checkbox, dialog, radio-group, switch, link"},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "solaris_component",
                "description": "Get Figma component details: variants, properties, dimensions, colors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "component": {"type": "string", "description": "Component name (e.g. 'button', 'badge', 'accordion')"},
                    },
                    "required": ["component"],
                },
            },
        },
        # ── MCP: GitHub ──
        {
            "type": "function",
            "function": {
                "name": "github_issues",
                "description": "List or search issues in a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "state": {"type": "string", "description": "Filter: open, closed, all"},
                        "query": {"type": "string", "description": "Search query for issue titles/body"},
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_prs",
                "description": "List pull requests in a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "state": {"type": "string", "description": "Filter: open, closed, all"},
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_code_search",
                "description": "Search code across GitHub repositories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Code search query (e.g. 'function handleAuth language:typescript')"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "github_actions",
                "description": "List workflow runs and their status for a GitHub repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                        "status": {"type": "string", "description": "Filter: completed, in_progress, queued"},
                    },
                    "required": ["owner", "repo"],
                },
            },
        },
        # ── MCP: JIRA/Confluence (optional — needs ATLASSIAN_TOKEN) ──
        {
            "type": "function",
            "function": {
                "name": "jira_search",
                "description": "Search JIRA issues using JQL query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jql": {"type": "string", "description": "JQL query (e.g. 'project=PROJ AND status=Open')"},
                        "max_results": {"type": "integer", "description": "Max results (default 10)"},
                    },
                    "required": ["jql"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "jira_create",
                "description": "Create a JIRA issue (bug, story, task).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project key (e.g. 'PROJ')"},
                        "summary": {"type": "string", "description": "Issue title"},
                        "type": {"type": "string", "description": "Issue type: Bug, Story, Task"},
                        "description": {"type": "string", "description": "Issue description"},
                    },
                    "required": ["project", "summary", "type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confluence_read",
                "description": "Read a Confluence page content by title or ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space": {"type": "string", "description": "Confluence space key"},
                        "title": {"type": "string", "description": "Page title to search"},
                        "page_id": {"type": "string", "description": "Page ID (alternative to title)"},
                    },
                },
            },
        },
        # ── Build & Test tools ──
        {
            "type": "function",
            "function": {
                "name": "build",
                "description": "Run a build command in the project workspace. Use to compile, install dependencies, or run any build step. Returns stdout+stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Build command to run. Examples: 'pip install -r requirements.txt', 'npm install && npm run build', 'cargo build', 'make'"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "test",
                "description": "Run tests in the project workspace. Returns test output with pass/fail results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Test command to run. Examples: 'pytest -v', 'npm test', 'cargo test', 'python -m pytest tests/'"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "browser_screenshot",
                "description": "Take a real browser screenshot of a web page using Playwright headless. If no URL given, starts a local HTTP server on the workspace index.html. Use to verify UI rendering, check layout, detect visual bugs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to screenshot. Leave empty to auto-serve local index.html"},
                        "filename": {"type": "string", "description": "Screenshot filename (default: screenshot.png)"},
                        "wait_ms": {"type": "integer", "description": "Wait time in ms after page load (default: 2000)"},
                    },
                },
            },
        },
        # ── Fractal coding tool (sub-agent spawning) ──
        {
            "type": "function",
            "function": {
                "name": "fractal_code",
                "description": "Spawn a focused sub-agent to complete an atomic coding task. The sub-agent gets full tool access (code_write, code_read, code_edit, test, git_commit) and runs autonomously for up to 8 tool rounds. Use this to delegate specific implementation tasks: 'write the auth module with tests', 'create the API endpoint for users', 'add unit tests for calculator'. Returns a summary of files created/modified and test results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Detailed coding task. Be specific about: what files to create, what functions/classes, what tests. Example: 'Create src/auth.py with login(username, password) function and tests/test_auth.py with pytest tests for valid/invalid credentials'"},
                        "context": {"type": "string", "description": "Additional context: existing files, architecture decisions, tech stack, conventions"},
                    },
                    "required": ["task"],
                },
            },
        },
        # ── Security scanning tools ──
        {
            "type": "function",
            "function": {
                "name": "sast_scan",
                "description": "Run static application security testing (SAST) on workspace code. Uses semgrep/bandit to detect vulnerabilities, injection flaws, and insecure patterns. Returns findings with severity, file, and line number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Workspace root directory"},
                        "path": {"type": "string", "description": "Subdirectory or file to scan (default: whole workspace)"},
                    },
                    "required": ["cwd"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dependency_audit",
                "description": "Audit project dependencies for known CVEs. Auto-detects package.json (npm), requirements.txt (pip), Cargo.toml (cargo). Returns vulnerability list with severity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Project root directory with dependency files"},
                    },
                    "required": ["cwd"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "secrets_scan",
                "description": "Scan workspace for hardcoded secrets (API keys, tokens, passwords, private keys). Deterministic grep-based detection. Ignores test fixtures and examples.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Workspace root directory to scan"},
                    },
                    "required": ["cwd"],
                },
            },
        },
        # ── Chaos & Load testing tools ──
        {
            "type": "function",
            "function": {
                "name": "chaos_test",
                "description": "Run chaos engineering test against a staging URL. Injects failures (process kill, network latency, memory pressure) and verifies recovery. Returns recovery time and health status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Staging URL to test"},
                        "scenario": {"type": "string", "enum": ["kill_process", "network_latency", "memory_pressure", "cpu_stress"], "description": "Chaos scenario to run"},
                        "timeout": {"type": "integer", "description": "Max recovery time in seconds (default: 30)"},
                    },
                    "required": ["url", "scenario"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tmc_load_test",
                "description": "Run load test (TMC) against a URL using k6. Returns p50/p95/p99 latency, throughput (rps), error rate. Scenarios: baseline (5 VUs), ramp_10x (50 VUs), spike (100 VUs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to load test"},
                        "scenario": {"type": "string", "enum": ["baseline", "ramp_10x", "spike", "soak"], "description": "Load scenario"},
                        "duration": {"type": "integer", "description": "Test duration in seconds (default: 30)"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "infra_check",
                "description": "Verify infrastructure health: HTTP endpoints, Docker containers, port availability. Returns structured health report.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to check (for site check)"},
                        "checks": {"type": "array", "items": {"type": "string"}, "description": "Checks to run: site, docker, ports"},
                        "port": {"type": "integer", "description": "Port to check (for ports check)"},
                    },
                },
            },
        },
        # ── SI Blueprint tool ──
        {
            "type": "function",
            "function": {
                "name": "get_si_blueprint",
                "description": "Get the SI (Information System) blueprint for the project. Returns infrastructure specs: cloud provider, compute type, CI/CD, databases, monitoring, existing services, and deployment conventions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Project identifier"},
                    },
                },
            },
        },
        # ── Platform introspection tools (self-aware) ──
        {
            "type": "function",
            "function": {
                "name": "platform_agents",
                "description": "List all platform agents or get details of one (id, name, role, skills, persona).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent ID to get details. Omit to list all."},
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
                        "mission_id": {"type": "string", "description": "Mission ID. Omit to list all."},
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
                        "project_id": {"type": "string", "description": "Project/mission ID for project-specific memory"},
                        "category": {"type": "string", "description": "Filter: architecture, vision, team, process, backlog"},
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
                "description": "List recent sessions/ceremonies or get messages from a specific session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session ID to get messages. Omit to list recent sessions."},
                        "limit": {"type": "integer", "description": "Max messages (default 30)"},
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
        # ── Composition tools (dynamic workflow/team/mission) ──
        {
            "type": "function",
            "function": {
                "name": "compose_workflow",
                "description": "Create a dynamic workflow definition. Define phases, patterns, and agent assignments based on project analysis. Returns workflow ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Workflow ID (auto-generated if omitted)"},
                        "name": {"type": "string", "description": "Workflow name"},
                        "description": {"type": "string", "description": "What this workflow does"},
                        "phases": {
                            "type": "array",
                            "description": "List of phases: [{id, name, pattern, agents: [agent_ids], config, gate}]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "pattern": {"type": "string", "enum": ["solo", "sequential", "parallel", "loop", "hierarchical", "network", "router", "aggregator", "human-in-the-loop"]},
                                    "agents": {"type": "array", "items": {"type": "string"}},
                                    "config": {"type": "object"},
                                    "gate": {"type": "string", "enum": ["all_approved", "no_veto", "always"]},
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
                "name": "create_team",
                "description": "Create a feature team with specialized agents. Each agent gets a prompt tailored to the domain and stack.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string", "description": "Team name (e.g. 'Auth Team', 'Booking Team')"},
                        "domain": {"type": "string", "description": "Domain: auth, booking, payment, admin, infra, qa, proto"},
                        "stack": {"type": "string", "description": "Tech stack: 'Rust axum/sqlx', 'SvelteKit', 'Python FastAPI'"},
                        "roles": {
                            "type": "array",
                            "description": "Team members: [{id, name, role, skills: [], prompt}]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "role": {"type": "string"},
                                    "skills": {"type": "array", "items": {"type": "string"}},
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
                        "parent_mission_id": {"type": "string", "description": "Parent mission/epic ID"},
                        "name": {"type": "string", "description": "Feature name"},
                        "description": {"type": "string", "description": "Feature description"},
                        "goal": {"type": "string", "description": "Acceptance criteria"},
                        "project_id": {"type": "string", "description": "Project identifier"},
                        "type": {"type": "string", "description": "Mission type: feature|story", "enum": ["feature", "story"]},
                        "workflow_id": {"type": "string", "description": "Workflow to execute for this feature"},
                        "wsjf_score": {"type": "number", "description": "WSJF priority score"},
                        "config": {"type": "object", "description": "Extra config: team_ids, stack, ao_refs"},
                    },
                    "required": ["parent_mission_id", "name"],
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
                        "parent_mission_id": {"type": "string", "description": "Parent mission ID"},
                    },
                    "required": ["parent_mission_id"],
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
                        "mission_id": {"type": "string", "description": "Mission ID to update"},
                        "wip_limit": {"type": "integer", "description": "Max concurrent workers"},
                        "stack": {"type": "string", "description": "Required tech stack"},
                        "ao_refs": {"type": "array", "items": {"type": "string"}, "description": "AO reference IDs"},
                        "sprint_duration": {"type": "string", "description": "Sprint duration (e.g. '4h', '1d')"},
                        "max_workers": {"type": "integer", "description": "Max parallel workers"},
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
                        "workspace_path": {"type": "string", "description": "Path to Android project inside container (default: /workspace)"},
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
                        "workspace_path": {"type": "string", "description": "Path to Android project"},
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
                        "workspace_path": {"type": "string", "description": "Path to Android project"},
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
                        "workspace_path": {"type": "string", "description": "Path to Android project"},
                    },
                },
            },
        },
    ]
    _TOOL_SCHEMAS = schemas
    return schemas

# Tools available to each agent role category
ROLE_TOOL_MAP: dict[str, list[str]] = {
    "product": [
        "code_read", "code_search", "list_files", "memory_search", "memory_store",
        "get_project_context", "screenshot",
        "github_issues", "github_prs",
        "jira_search", "jira_create", "confluence_read",
    ],
    "architecture": [
        "code_read", "code_search", "list_files", "deep_search",
        "memory_search", "memory_store", "get_project_context",
        "git_log", "git_diff",
        "lrm_conventions", "lrm_context", "lrm_summarize",
        "github_code_search",
        "get_si_blueprint",
        "compose_workflow", "create_team", "create_sub_mission", "list_sub_missions", "set_constraints",
    ],
    "ux": [
        "code_read", "code_search", "list_files", "screenshot",
        "memory_search", "memory_store", "get_project_context",
        "figma_get_node", "figma_get_styles",
        "solaris_wcag", "solaris_component",
    ],
    "dev": [
        "code_read", "code_write", "code_edit", "code_search",
        "git_status", "git_log", "git_diff", "git_commit",
        "list_files", "deep_search", "fractal_code",
        "memory_search", "memory_store", "get_project_context",
        "build", "test",
        "docker_build", "screenshot", "simulator_screenshot",
        "lrm_locate", "lrm_conventions", "lrm_build", "lrm_examples",
        "github_prs", "github_code_search",
        "android_build", "android_test", "android_lint",
    ],
    "qa": [
        "code_read", "code_write", "code_search", "list_files",
        "screenshot", "simulator_screenshot", "playwright_test",
        "build", "test", "browser_screenshot",
        "memory_search", "memory_store", "get_project_context",
        "git_diff", "git_log",
        "github_issues", "github_prs",
        "jira_search", "jira_create",
        "chaos_test", "tmc_load_test",
        "android_build", "android_test", "android_lint", "android_emulator_test",
    ],
    "devops": [
        "code_read", "code_write", "code_edit", "code_search",
        "git_status", "git_log", "git_diff", "git_commit",
        "list_files", "docker_build", "deploy_azure",
        "build", "test", "browser_screenshot",
        "memory_search", "memory_store", "get_project_context",
        "lrm_build",
        "github_actions", "github_prs",
        "infra_check", "chaos_test", "tmc_load_test",
        "get_si_blueprint",
    ],
    "security": [
        "code_read", "code_search", "list_files", "deep_search",
        "memory_search", "memory_store", "get_project_context",
        "git_log", "git_diff",
        "github_code_search", "github_issues",
        "sast_scan", "dependency_audit", "secrets_scan",
        "get_si_blueprint",
    ],
    "cdp": [
        "memory_search", "memory_store", "get_project_context",
        "list_files",
        "run_phase", "get_phase_status", "list_phases", "request_validation",
        "compose_workflow", "create_team", "create_sub_mission", "list_sub_missions", "set_constraints",
        "github_issues", "github_prs",
        "jira_search",
    ],
}

# Platform introspection tools — available to ALL agent roles
_PLATFORM_TOOLS = [
    "platform_agents", "platform_missions", "platform_memory_search",
    "platform_metrics", "platform_sessions", "platform_workflows",
]
for _role_key in ROLE_TOOL_MAP:
    ROLE_TOOL_MAP[_role_key].extend(_PLATFORM_TOOLS)


def _classify_agent_role(agent: "AgentDef") -> str:
    """Classify an agent into a tool-mapping role category."""
    role = (agent.role or "").lower()
    name = (agent.name or "").lower()
    combined = f"{role} {name}"

    if any(k in combined for k in ("product", "business", "analyste", "ba ", "fonctionnel")):
        return "product"
    if any(k in combined for k in ("archi", "architect")):
        return "architecture"
    if any(k in combined for k in ("ux", "ui", "design", "ergon")):
        return "ux"
    if any(k in combined for k in ("qa", "test", "qualit")):
        return "qa"
    if any(k in combined for k in ("devops", "sre", "pipeline", "infra", "deploy")):
        return "devops"
    if any(k in combined for k in ("secur", "secu", "cyber")):
        return "security"
    if any(k in combined for k in ("programme", "projet", "cdp", "scrum", "coach", "pm ")):
        return "cdp"
    if any(k in combined for k in ("dev", "lead", "engineer", "backend", "frontend", "fullstack")):
        return "dev"
    return "dev"  # default to dev (most permissive set)


def _get_tools_for_agent(agent: "AgentDef") -> Optional[list[str]]:
    """Return the list of allowed tool names for this agent, or None for all."""
    role_cat = _classify_agent_role(agent)
    return ROLE_TOOL_MAP.get(role_cat)


def _filter_schemas(schemas: list[dict], allowed: Optional[list[str]]) -> list[dict]:
    """Filter tool schemas to only include allowed tool names."""
    if allowed is None:
        return schemas
    allowed_set = set(allowed)
    return [s for s in schemas if s.get("function", {}).get("name") in allowed_set]
