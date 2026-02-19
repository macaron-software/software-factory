"""Agent Executor — runs an agent: receive message → think (LLM) → act → respond.

This is the runtime loop that makes agents actually work. It:
1. Builds the prompt (system + skills + memory + conversation)
2. Calls the LLM with tools definitions
3. If LLM returns tool_calls → execute tools → feed results back → repeat
4. When LLM returns text (no tool_calls) → done
5. Sends response back via MessageBus or returns it
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from ..llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall, get_llm_client
from ..agents.store import AgentDef

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5

# Regex to strip raw MiniMax/internal tool-call tokens from LLM output
_RAW_TOKEN_RE = re.compile(
    r'<\|(?:tool_calls_section_begin|tool_calls_section_end|tool_call_begin|tool_call_end|'
    r'tool_call_argument_begin|tool_call_argument_end|tool_sep|im_end|im_start)\|>'
)

def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if '<|' not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub('', text)
    # Also remove raw function call lines like "functions.code_read:0"
    cleaned = re.sub(r'^functions\.\w+:\d+$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _get_tool_registry():
    """Lazy import to avoid circular imports."""
    from ..tools.registry import ToolRegistry
    from ..tools.code_tools import register_code_tools
    from ..tools.git_tools import register_git_tools
    from ..tools.build_tools import register_build_tools
    reg = ToolRegistry()
    register_code_tools(reg)
    register_git_tools(reg)
    register_build_tools(reg)
    try:
        from ..tools.mcp_bridge import register_mcp_tools
        register_mcp_tools(reg)
    except Exception:
        pass
    # Memory tools
    try:
        from ..tools.memory_tools import register_memory_tools
        register_memory_tools(reg)
    except Exception:
        pass
    # Web research tools
    try:
        from ..tools.web_tools import register_web_tools
        register_web_tools(reg)
    except Exception:
        pass
    # Deploy tools (docker build + Azure VM)
    try:
        from ..tools.deploy_tools import register_deploy_tools
        register_deploy_tools(reg)
    except Exception:
        pass
    # Phase orchestration tools (mission control)
    try:
        from ..tools.phase_tools import register_phase_tools
        register_phase_tools(reg)
    except Exception:
        pass
    # Playwright test/screenshot tools
    try:
        from ..tools.test_tools import register_test_tools
        register_test_tools(reg)
    except Exception:
        pass
    return reg


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
                "description": "Take a browser screenshot of a URL using Playwright headless. Saves PNG to screenshots/ dir. Returns file path with [SCREENSHOT:path] marker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to screenshot (e.g. http://localhost:3000)"},
                        "filename": {"type": "string", "description": "Output filename (default: screenshot.png)"},
                    },
                    "required": ["url"],
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
    ]
    _TOOL_SCHEMAS = schemas
    return schemas


# ── Role-based tool mapping ────────────────────────────────────

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
        "list_files", "deep_search",
        "memory_search", "memory_store", "get_project_context",
        "docker_build", "screenshot",
        "lrm_locate", "lrm_conventions", "lrm_build", "lrm_examples",
        "github_prs", "github_code_search",
    ],
    "qa": [
        "code_read", "code_search", "list_files",
        "screenshot", "playwright_test",
        "memory_search", "memory_store", "get_project_context",
        "git_diff", "git_log",
        "github_issues", "github_prs",
        "jira_search", "jira_create",
    ],
    "devops": [
        "code_read", "code_write", "code_edit", "code_search",
        "git_status", "git_log", "git_diff", "git_commit",
        "list_files", "docker_build", "deploy_azure",
        "memory_search", "memory_store", "get_project_context",
        "lrm_build",
        "github_actions", "github_prs",
    ],
    "security": [
        "code_read", "code_search", "list_files", "deep_search",
        "memory_search", "memory_store", "get_project_context",
        "git_log", "git_diff",
        "github_code_search", "github_issues",
    ],
    "cdp": [
        "memory_search", "memory_store", "get_project_context",
        "list_files",
        "run_phase", "get_phase_status", "list_phases", "request_validation",
        "github_issues", "github_prs",
        "jira_search",
    ],
}


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


@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""
    agent: AgentDef
    session_id: str
    project_id: Optional[str] = None
    project_path: Optional[str] = None  # filesystem path for tools
    # Conversation history (recent messages for context window)
    history: list[dict] = field(default_factory=list)
    # Project memory snippets
    project_context: str = ""
    # Project memory files (CLAUDE.md, copilot-instructions.md, etc.)
    project_memory: str = ""
    # Skills content (injected into system prompt)
    skills_prompt: str = ""
    # Vision document (if project has one)
    vision: str = ""
    # Enable tool-calling (default True)
    tools_enabled: bool = True
    # Filter tools by name — only these tools are available to the agent (None = all)
    allowed_tools: Optional[list[str]] = None
    # Callback for SSE tool events
    on_tool_call: Optional[object] = None  # async callable(tool_name, args, result)
    # Mission run ID (for CDP phase tools)
    mission_run_id: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of running an agent on a message."""
    content: str
    agent_id: str
    model: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    delegations: list[dict] = field(default_factory=list)
    error: Optional[str] = None


class AgentExecutor:
    """Executes agent logic: prompt → LLM → tool loop → response."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self._llm = llm or get_llm_client()
        self._registry = _get_tool_registry()

    async def run(self, ctx: ExecutionContext, user_message: str) -> ExecutionResult:
        """Run the agent with tool-calling loop."""
        t0 = time.monotonic()
        agent = ctx.agent
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        try:
            system = self._build_system_prompt(ctx)
            messages = self._build_messages(ctx, user_message)
            tools = _filter_schemas(_get_tool_schemas(), ctx.allowed_tools) if ctx.tools_enabled else None

            # Tool-calling loop
            deep_search_used = False
            for round_num in range(MAX_TOOL_ROUNDS):
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=agent.provider,
                    model=agent.model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out

                # Parse XML tool calls from content (MiniMax sometimes returns these)
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = self._parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="", model=llm_resp.model, provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in, tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms, finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → final response
                if not llm_resp.tool_calls:
                    content = llm_resp.content
                    break

                # Process tool calls
                # Add assistant message with tool_calls to conversation
                tc_msg_data = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)},
                } for tc in llm_resp.tool_calls]

                messages.append(LLMMessage(
                    role="assistant",
                    content=llm_resp.content or "",
                    tool_calls=tc_msg_data,
                ))

                for tc in llm_resp.tool_calls:
                    result = await self._execute_tool(tc, ctx)
                    all_tool_calls.append({
                        "name": tc.function_name,
                        "args": tc.arguments,
                        "result": result[:500],  # truncate for storage
                    })

                    if tc.function_name == "deep_search":
                        deep_search_used = True

                    # Track code changes as artifacts
                    if tc.function_name in ("code_write", "code_edit") and not result.startswith("Error"):
                        try:
                            self._record_artifact(ctx, tc, result)
                        except Exception:
                            pass

                    # Notify UI via callback
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(tc.function_name, tc.arguments, result)
                        except Exception:
                            pass

                    # Add tool result to conversation
                    messages.append(LLMMessage(
                        role="tool",
                        content=result[:4000],
                        tool_call_id=tc.id,
                        name=tc.function_name,
                    ))

                # After deep_search, disable tools to force synthesis
                if deep_search_used:
                    tools = None
                    # Notify: agent is now synthesizing
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call("deep_search", {"status": "Generating response…"}, "")
                        except Exception:
                            pass

                logger.info("Agent %s tool round %d: %d calls", agent.id, round_num + 1,
                            len(llm_resp.tool_calls))

                # On penultimate round, disable tools to force synthesis next iteration
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    tools = None
                    messages.append(LLMMessage(
                        role="system",
                        content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                    ))
            else:
                content = llm_resp.content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            # Strip raw MiniMax tool-call tokens that leak into content
            content = _strip_raw_tokens(content)
            delegations = self._parse_delegations(content)

            return ExecutionResult(
                content=content,
                agent_id=agent.id,
                model=llm_resp.model,
                provider=llm_resp.provider,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=elapsed,
                tool_calls=all_tool_calls,
                delegations=delegations,
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s execution failed: %s", agent.id, exc, exc_info=True)
            return ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            )

    async def run_streaming(
        self, ctx: ExecutionContext, user_message: str
    ) -> AsyncIterator[tuple[str, str | ExecutionResult]]:
        """Run agent with streaming — yields ("delta", text) chunks then ("result", ExecutionResult).

        For agents without tools: streams the entire response token-by-token.
        For agents with tools: runs tool rounds non-streaming, then streams final response.
        """
        t0 = time.monotonic()
        agent = ctx.agent
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        try:
            system = self._build_system_prompt(ctx)
            messages = self._build_messages(ctx, user_message)
            tools = _filter_schemas(_get_tool_schemas(), ctx.allowed_tools) if ctx.tools_enabled else None

            # Tool-calling rounds (non-streaming) — same as run()
            deep_search_used = False
            final_content = ""

            for round_num in range(MAX_TOOL_ROUNDS):
                is_last_possible = (round_num >= MAX_TOOL_ROUNDS - 1) or tools is None

                # On last round or no tools: use streaming
                if is_last_possible or not ctx.tools_enabled:
                    # Stream the final response
                    accumulated = ""
                    async for chunk in self._llm.stream(
                        messages=messages,
                        provider=agent.provider,
                        model=agent.model,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        system_prompt=system if round_num == 0 else "",
                    ):
                        if chunk.delta:
                            accumulated += chunk.delta
                            yield ("delta", chunk.delta)
                        if chunk.done:
                            break
                    final_content = accumulated
                    break

                # Non-streaming tool round
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=agent.provider,
                    model=agent.model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out

                # Parse XML tool calls
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = self._parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="", model=llm_resp.model, provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in, tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms, finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → stream remaining content
                if not llm_resp.tool_calls:
                    final_content = llm_resp.content
                    # Emit any content from this non-streamed response as a single delta
                    if final_content:
                        yield ("delta", final_content)
                    break

                # Process tool calls (same as run())
                tc_msg_data = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)},
                } for tc in llm_resp.tool_calls]

                messages.append(LLMMessage(
                    role="assistant",
                    content=llm_resp.content or "",
                    tool_calls=tc_msg_data,
                ))

                for tc in llm_resp.tool_calls:
                    result = await self._execute_tool(tc, ctx)
                    all_tool_calls.append({
                        "name": tc.function_name,
                        "args": tc.arguments,
                        "result": result[:500],
                    })
                    if tc.function_name == "deep_search":
                        deep_search_used = True
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(tc.function_name, tc.arguments, result)
                        except Exception:
                            pass
                    messages.append(LLMMessage(
                        role="tool",
                        content=result[:4000],
                        tool_call_id=tc.id,
                        name=tc.function_name,
                    ))

                if deep_search_used:
                    tools = None
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    tools = None
                    messages.append(LLMMessage(
                        role="system",
                        content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                    ))
            else:
                final_content = final_content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            final_content = _strip_raw_tokens(final_content)
            delegations = self._parse_delegations(final_content)

            yield ("result", ExecutionResult(
                content=final_content,
                agent_id=agent.id,
                model=agent.model,
                provider=agent.provider,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=elapsed,
                tool_calls=all_tool_calls,
                delegations=delegations,
            ))

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s streaming failed: %s", agent.id, exc, exc_info=True)
            yield ("result", ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            ))

    @staticmethod
    def _parse_xml_tool_calls(content: str) -> list:
        """Parse MiniMax XML-format tool calls from content."""
        from ..llm.client import LLMToolCall as _TC
        import uuid as _uuid

        calls = []
        # Match <invoke name="tool_name"><parameter name="key">value</parameter>...</invoke>
        invoke_re = re.compile(
            r'<invoke\s+name="([^"]+)">(.*?)</invoke>', re.DOTALL
        )
        param_re = re.compile(
            r'<parameter\s+name="([^"]+)">(.*?)</parameter>', re.DOTALL
        )
        for m in invoke_re.finditer(content):
            fn_name = m.group(1)
            body = m.group(2)
            args = {}
            for pm in param_re.finditer(body):
                args[pm.group(1)] = pm.group(2).strip()
            calls.append(_TC(
                id=f"call_{_uuid.uuid4().hex[:12]}",
                function_name=fn_name,
                arguments=args,
            ))
        return calls

    async def _execute_tool(self, tc: LLMToolCall, ctx: ExecutionContext) -> str:
        """Execute a single tool call and return string result."""
        name = tc.function_name
        args = dict(tc.arguments)

        # ── Resolve paths: project_path is the default for all file/git tools ──
        if ctx.project_path:
            # Git/build/deploy/test tools: inject cwd
            if name in ("git_status", "git_log", "git_diff", "git_commit", "build", "test", "lint", "docker_build", "screenshot", "playwright_test"):
                if "cwd" not in args or args["cwd"] in (".", "", "./"):
                    args["cwd"] = ctx.project_path
            # File tools: resolve relative paths to project root
            if name in ("code_read", "code_search", "code_write", "code_edit", "list_files"):
                path = args.get("path", "")
                if not path or path == ".":
                    args["path"] = ctx.project_path
                elif not os.path.isabs(path):
                    args["path"] = os.path.join(ctx.project_path, path)

        # Handle built-in tools that don't go through registry
        if name == "list_files":
            return await self._tool_list_files(args)
        if name == "memory_search":
            return await self._tool_memory_search(args, ctx)
        if name == "memory_store":
            return await self._tool_memory_store(args, ctx)
        if name == "deep_search":
            return await self._tool_deep_search(args, ctx)
        # Phase orchestration tools (mission control)
        if name == "run_phase":
            return await self._tool_run_phase(args, ctx)
        if name == "get_phase_status":
            return await self._tool_get_phase_status(args, ctx)
        if name == "list_phases":
            return await self._tool_list_phases(args, ctx)
        if name == "request_validation":
            return await self._tool_request_validation(args, ctx)
        if name == "get_project_context":
            return await self._tool_get_project_context(args, ctx)

        # ── MCP tools: proxy to external servers ──
        if name.startswith("lrm_"):
            return await self._tool_mcp_lrm(name, args, ctx)
        if name.startswith("figma_"):
            return await self._tool_mcp_figma(name, args, ctx)
        if name.startswith("solaris_"):
            return await self._tool_mcp_solaris(name, args, ctx)
        if name.startswith("github_"):
            return await self._tool_mcp_github(name, args, ctx)
        if name.startswith("jira_") or name == "confluence_read":
            return await self._tool_mcp_jira(name, args, ctx)

        # Registry tools
        tool = self._registry.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"

        try:
            return await tool.execute(args)
        except Exception as e:
            return f"Tool '{name}' error: {e}"

    async def _tool_list_files(self, args: dict) -> str:
        """List directory contents."""
        import os
        path = args.get("path", ".")
        depth = int(args.get("depth", 2))
        if not os.path.isdir(path):
            return f"Error: not a directory: {path}"
        lines = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, "").count(os.sep)
            if level >= depth:
                dirs.clear()
                continue
            indent = "  " * level
            lines.append(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for f in sorted(files)[:50]:
                lines.append(f"{subindent}{f}")
            dirs[:] = sorted(dirs)[:20]
        return "\n".join(lines[:200]) or "Empty directory"

    async def _tool_memory_search(self, args: dict, ctx: ExecutionContext) -> str:
        """Search project/global memory."""
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        query = args.get("query", "")
        scope = args.get("scope", "project")
        try:
            if scope == "project" and ctx.project_id:
                results = mem.project_search(ctx.project_id, query, limit=10)
            else:
                results = mem.global_search(query, limit=10)
            if not results:
                return "No memory entries found."
            return "\n".join(f"[{r.get('key','')}] {r.get('value','')[:300]}" for r in results)
        except Exception as e:
            return f"Memory search error: {e}"

    async def _tool_memory_store(self, args: dict, ctx: ExecutionContext) -> str:
        """Store a fact in project memory."""
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        key = args.get("key", "")
        value = args.get("value", "")
        category = args.get("category", "fact")
        if not key or not value:
            return "Error: key and value required"
        try:
            if ctx.project_id:
                mem.project_store(ctx.project_id, key, value, category=category, author=ctx.agent.id)
                return f"Stored in project memory: [{key}]"
            return "Error: no project context"
        except Exception as e:
            return f"Memory store error: {e}"

    async def _tool_deep_search(self, args: dict, ctx: ExecutionContext) -> str:
        """RLM: Deep recursive search (MIT CSAIL arXiv:2512.24601)."""
        from .rlm import get_project_rlm
        query = args.get("query", "")
        if not query:
            return "Error: query is required"
        if not ctx.project_id:
            return "Error: no project context for RLM"

        print(f"[EXECUTOR] deep_search called: {query[:80]}", flush=True)
        rlm = get_project_rlm(ctx.project_id)
        if not rlm:
            return f"Error: could not initialize RLM for project {ctx.project_id}"

        max_iter = int(args.get("max_iterations", 3))

        # Forward progress to the tool_call callback
        async def rlm_progress(label: str):
            if ctx.on_tool_call:
                try:
                    await ctx.on_tool_call("deep_search", {"status": label}, label)
                except Exception:
                    pass

        result = await rlm.search(
            query=query,
            context=ctx.project_context or "",
            max_iterations=min(max_iter, 3),
            on_progress=rlm_progress,
        )

        print(f"[EXECUTOR] deep_search done: {result.iterations} iters, {result.total_queries} queries, {len(result.answer)} chars", flush=True)
        header = f"RLM Deep Search ({result.iterations} iterations, {result.total_queries} queries)\n\n"
        return header + result.answer

        print(f"[EXECUTOR] deep_search done: {result.iterations} iters, {result.total_queries} queries, {len(result.answer)} chars", flush=True)
        header = f"RLM Deep Search ({result.iterations} iterations, {result.total_queries} queries)\n\n"
        return header + result.answer

    # ── Phase orchestration tools (Mission Control) ──

    async def _tool_run_phase(self, args: dict, ctx: ExecutionContext) -> str:
        """Run a mission phase via pattern engine."""
        from ..missions.store import get_mission_run_store
        from ..workflows.store import get_workflow_store
        from ..patterns.store import get_pattern_store
        from ..patterns.engine import run_pattern
        from ..models import PhaseStatus
        from datetime import datetime

        phase_id = args.get("phase_id", "")
        brief = args.get("brief", "")
        if not phase_id:
            return "Error: phase_id is required"

        run_store = get_mission_run_store()
        mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
        if not mission:
            return "Error: no active mission. Start a mission first."

        # Find the phase
        phase_run = None
        for p in mission.phases:
            if p.phase_id == phase_id:
                phase_run = p
                break
        if not phase_run:
            return f"Error: phase '{phase_id}' not found in mission"

        if phase_run.status == PhaseStatus.RUNNING:
            return f"Phase '{phase_id}' is already running"

        # Get workflow to find phase config
        wf_store = get_workflow_store()
        workflow = wf_store.get(mission.workflow_id)
        if not workflow:
            return f"Error: workflow '{mission.workflow_id}' not found"

        wf_phase = None
        for wp in workflow.phases:
            if wp.id == phase_id:
                wf_phase = wp
                break
        if not wf_phase:
            return f"Error: phase '{phase_id}' not in workflow"

        # Build pattern from phase config
        pat_store = get_pattern_store()
        base_pattern = pat_store.get(wf_phase.pattern_id)
        if not base_pattern:
            return f"Error: pattern '{wf_phase.pattern_id}' not found"

        # Build agents list from phase config
        agent_ids = wf_phase.config.get("agents", [])
        agents = [{"id": f"ph-{i}", "agent_id": aid, "label": aid} for i, aid in enumerate(agent_ids)]
        # Build edges based on pattern type
        edges = self._build_phase_edges(base_pattern.type, agents)

        from ..patterns.store import PatternDef
        phase_pattern = PatternDef(
            id=f"mission-{mission.id}-{phase_id}",
            name=f"{wf_phase.name}",
            type=base_pattern.type,
            agents=agents,
            edges=edges,
            config=wf_phase.config,
        )

        # Update phase status
        phase_run.status = PhaseStatus.RUNNING
        phase_run.started_at = datetime.utcnow()
        phase_run.iteration += 1
        phase_run.agent_count = len(agent_ids)
        mission.current_phase = phase_id
        mission.status = "running"
        run_store.update(mission)

        # Push SSE event
        await self._push_mission_sse(ctx.session_id, {
            "type": "phase_started",
            "mission_id": mission.id,
            "phase_id": phase_id,
            "phase_name": wf_phase.name,
            "pattern": base_pattern.type,
            "agents": agent_ids,
        })

        try:
            print(f"[MISSION] Running phase '{phase_id}' ({base_pattern.type}) with {len(agent_ids)} agents", flush=True)
            pattern_run = await run_pattern(
                phase_pattern,
                session_id=ctx.session_id,
                initial_task=brief,
                project_id=ctx.project_id or "",
            )

            # Gather results from node outputs
            summaries = []
            for nid, node in pattern_run.nodes.items():
                if node.output:
                    agent_label = node.agent.name if node.agent else nid
                    summaries.append(f"**{agent_label}**: {node.output[:500]}")

            phase_run.status = PhaseStatus.DONE if pattern_run.success else PhaseStatus.FAILED
            phase_run.completed_at = datetime.utcnow()
            phase_run.summary = "\n\n".join(summaries)[:3000]
            if not pattern_run.success:
                phase_run.error = "Phase ended with vetoes or failures"
            run_store.update(mission)

            await self._push_mission_sse(ctx.session_id, {
                "type": "phase_completed" if pattern_run.success else "phase_failed",
                "mission_id": mission.id,
                "phase_id": phase_id,
                "success": pattern_run.success,
            })

            status = "DONE" if pattern_run.success else "FAILED"
            return f"Phase '{wf_phase.name}' {status}\n\n{phase_run.summary[:2000]}"

        except Exception as e:
            phase_run.status = PhaseStatus.FAILED
            phase_run.error = str(e)
            run_store.update(mission)
            return f"Phase '{phase_id}' error: {e}"

    def _build_phase_edges(self, pattern_type: str, agents: list[dict]) -> list[dict]:
        """Build edges for a phase pattern based on type."""
        edges = []
        ids = [a["id"] for a in agents]
        if not ids:
            return edges
        if pattern_type in ("sequential",):
            for i in range(len(ids) - 1):
                edges.append({"from": ids[i], "to": ids[i + 1], "type": "then"})
        elif pattern_type in ("hierarchical",):
            for worker in ids[1:]:
                edges.append({"from": ids[0], "to": worker, "type": "delegate"})
        elif pattern_type in ("parallel", "aggregator"):
            for worker in ids[:-1]:
                edges.append({"from": worker, "to": ids[-1], "type": "aggregate"})
        elif pattern_type in ("loop",):
            if len(ids) >= 2:
                edges.append({"from": ids[0], "to": ids[1], "type": "review"})
                edges.append({"from": ids[1], "to": ids[0], "type": "feedback"})
        elif pattern_type in ("network",):
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    edges.append({"from": a, "to": b, "type": "discuss"})
        elif pattern_type in ("router",):
            for specialist in ids[1:]:
                edges.append({"from": ids[0], "to": specialist, "type": "route"})
        elif pattern_type in ("human-in-the-loop",):
            for i in range(len(ids) - 1):
                edges.append({"from": ids[i], "to": ids[i + 1], "type": "then"})
        return edges

    async def _tool_get_phase_status(self, args: dict, ctx: ExecutionContext) -> str:
        """Get status of a specific phase."""
        from ..missions.store import get_mission_run_store

        phase_id = args.get("phase_id", "")
        run_store = get_mission_run_store()
        mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
        if not mission:
            return "Error: no active mission"

        for p in mission.phases:
            if p.phase_id == phase_id:
                lines = [
                    f"Phase: {p.phase_name} ({p.phase_id})",
                    f"Status: {p.status.value}",
                    f"Pattern: {p.pattern_id}",
                    f"Agents: {p.agent_count}",
                    f"Iteration: {p.iteration}",
                ]
                if p.summary:
                    lines.append(f"Summary: {p.summary[:500]}")
                if p.error:
                    lines.append(f"Error: {p.error}")
                return "\n".join(lines)
        return f"Phase '{phase_id}' not found"

    async def _tool_list_phases(self, args: dict, ctx: ExecutionContext) -> str:
        """List all phases with status."""
        from ..missions.store import get_mission_run_store

        run_store = get_mission_run_store()
        mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
        if not mission:
            return "Error: no active mission"

        lines = [f"Mission: {mission.workflow_name} ({mission.status.value})\n"]
        status_icons = {
            "pending": "·", "running": "~", "done": "✓",
            "failed": "✗", "skipped": "-", "waiting_validation": "?",
        }
        for i, p in enumerate(mission.phases, 1):
            icon = status_icons.get(p.status.value, "•")
            current = " ← CURRENT" if p.phase_id == mission.current_phase else ""
            lines.append(f"{i}. {icon} {p.phase_name} [{p.pattern_id}] — {p.status.value}{current}")
        return "\n".join(lines)

    async def _tool_request_validation(self, args: dict, ctx: ExecutionContext) -> str:
        """Request human validation — emit SSE checkpoint event."""
        from ..missions.store import get_mission_run_store
        from ..sessions.store import get_session_store, MessageDef
        from ..models import PhaseStatus

        question = args.get("question", "Proceed?")
        options = args.get("options", "GO,NOGO,PIVOT")

        run_store = get_mission_run_store()
        mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None

        # Update current phase to waiting
        if mission and mission.current_phase:
            for p in mission.phases:
                if p.phase_id == mission.current_phase:
                    p.status = PhaseStatus.WAITING_VALIDATION
            run_store.update(mission)

        # Store as system message
        store = get_session_store()
        store.add_message(MessageDef(
            session_id=ctx.session_id,
            from_agent=ctx.agent.id,
            to_agent="human",
            message_type="system",
            content=f"**CHECKPOINT** — {question}\n\nOptions: {options}",
        ))

        # SSE event for Mission Control UI
        await self._push_mission_sse(ctx.session_id, {
            "type": "checkpoint",
            "mission_id": mission.id if mission else "",
            "phase_id": mission.current_phase if mission else "",
            "question": question,
            "options": options.split(","),
            "requires_input": True,
        })

        return f"CHECKPOINT: Waiting for human validation.\nQuestion: {question}\nOptions: {options}\n\n(The user will respond via Mission Control UI)"

    async def _tool_get_project_context(self, args: dict, ctx: ExecutionContext) -> str:
        """Get project context for the CDP."""
        parts = []
        if ctx.vision:
            parts.append(f"## Vision\n{ctx.vision[:2000]}")
        if ctx.project_context:
            parts.append(f"## Project Context\n{ctx.project_context[:2000]}")
        if ctx.project_memory:
            parts.append(f"## Project Memory\n{ctx.project_memory[:1000]}")
        if not parts:
            return "No project context available. This mission is running without a project."
        return "\n\n".join(parts)

    async def _push_mission_sse(self, session_id: str, data: dict):
        """Push a mission control SSE event via the A2A bus SSE listeners."""
        from ..a2a.bus import get_bus
        data["session_id"] = session_id
        bus = get_bus()
        dead = []
        for q in bus._sse_listeners:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            bus._sse_listeners.remove(q)

    def _record_artifact(self, ctx: ExecutionContext, tc: LLMToolCall, result: str):
        """Record a code_write/code_edit as an artifact in the DB."""
        import uuid
        from ..db.migrations import get_db
        path = tc.arguments.get("path", "unknown")
        art_type = "edit" if tc.function_name == "code_edit" else "create"
        content = tc.arguments.get("content", "") or f"Edit: {tc.arguments.get('old_str', '')[:100]} → {tc.arguments.get('new_str', '')[:100]}"
        lang = os.path.splitext(path)[1].lstrip(".")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO artifacts (id, session_id, type, name, content, language, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4())[:8], ctx.session_id, art_type, f"[{art_type.upper()}] {path}", content[:2000], lang, ctx.agent.id),
            )
            db.commit()
        except Exception as e:
            logger.warning("Failed to record artifact: %s", e)
        finally:
            db.close()

    def _build_system_prompt(self, ctx: ExecutionContext) -> str:
        """Compose the full system prompt from agent config + skills + context."""
        parts = []
        agent = ctx.agent

        if agent.system_prompt:
            parts.append(agent.system_prompt)

        if agent.persona:
            parts.append(f"\n## Persona & Character\n{agent.persona}")

        parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
        if agent.description:
            parts.append(f"Description: {agent.description}")

        if ctx.tools_enabled:
            parts.append("\nYou have access to tools. Use them to read files, search code, check git status, and access project memory. Call tools when you need concrete information rather than guessing.")
        else:
            parts.append("\nYou do NOT have tools. Do NOT write [TOOL_CALL] or attempt to use tools. Focus on analysis, synthesis, and delegation to your team.")

        if ctx.skills_prompt:
            parts.append(f"\n## Skills\n{ctx.skills_prompt}")

        if ctx.vision:
            parts.append(f"\n## Project Vision\n{ctx.vision[:3000]}")

        if ctx.project_context:
            parts.append(f"\n## Project Context\n{ctx.project_context[:2000]}")

        if ctx.project_memory:
            parts.append(f"\n## Project Memory (auto-loaded instructions)\n{ctx.project_memory[:4000]}")

        if ctx.project_path:
            parts.append(f"\n## Project Path\n{ctx.project_path}")

        perms = agent.permissions or {}
        if perms.get("can_delegate"):
            parts.append("""
## Delegation (IMPORTANT)
You MUST delegate tasks to your team using this exact format on separate lines:
[DELEGATE:agent_id] clear task description

Example:
[DELEGATE:strat-cpo] Analyser la vision produit et valider les objectifs business
[DELEGATE:strat-cto] Évaluer la faisabilité technique et recommander le stack

As a leader, your job is to DELEGATE to team members, then SYNTHESIZE their responses.
Do NOT try to do everything yourself — leverage your team.""")
        if perms.get("can_veto"):
            parts.append("\nYou CAN veto decisions by writing: [VETO] reason")
        if perms.get("can_approve"):
            parts.append("\nYou CAN approve work by writing: [APPROVE] reason")

        return "\n".join(parts)

    def _build_messages(self, ctx: ExecutionContext, user_message: str) -> list[LLMMessage]:
        """Build the message list from conversation history."""
        messages = []
        for h in ctx.history[-20:]:
            role = "assistant" if h.get("from_agent") != "user" else "user"
            name = h.get("from_agent")
            messages.append(LLMMessage(
                role=role,
                content=h.get("content", ""),
                name=name if name != "user" else None,
            ))
        messages.append(LLMMessage(role="user", content=user_message))
        return messages

    # ── MCP Tool Handlers ─────────────────────────────────────────

    async def _tool_mcp_lrm(self, name: str, args: dict, ctx: ExecutionContext) -> str:
        """Proxy to LRM MCP server (localhost:9500)."""
        import aiohttp
        tool_name = name.replace("lrm_", "")
        if ctx.project_id:
            args.setdefault("project", ctx.project_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:9500/tools/{tool_name}",
                    json=args, timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return str(data.get("result", data))[:8000]
                    return f"LRM error {resp.status}"
        except Exception as e:
            return f"LRM server unavailable: {e}"

    async def _tool_mcp_figma(self, name: str, args: dict, ctx: ExecutionContext) -> str:
        """Proxy to Figma MCP (desktop or remote)."""
        import aiohttp
        endpoints = ["http://127.0.0.1:3845/mcp", "https://mcp.figma.com/mcp"]
        tool_name = name.replace("figma_", "")
        payload = {"method": tool_name, "params": args}
        for endpoint in endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return str(data.get("result", data))[:8000]
            except Exception:
                continue
        return "Figma MCP unavailable (desktop + remote)"

    async def _tool_mcp_solaris(self, name: str, args: dict, ctx: ExecutionContext) -> str:
        """Proxy to Solaris design system tools."""
        tool_name = name.replace("solaris_", "")
        try:
            if tool_name == "wcag":
                from solaris_solaris_wcag import solaris_wcag  # type: ignore
                return str(solaris_wcag(args.get("pattern", "")))[:8000]
            if tool_name == "component":
                from solaris_solaris_component import solaris_component  # type: ignore
                return str(solaris_component(args.get("component", "")))[:8000]
        except ImportError:
            pass
        # Fallback: try MCP bridge
        return await self._tool_mcp_lrm(f"lrm_{tool_name}", args, ctx)

    async def _tool_mcp_github(self, name: str, args: dict, ctx: ExecutionContext) -> str:
        """Execute GitHub operations via gh CLI."""
        import asyncio as _aio
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        try:
            if name == "github_issues":
                state = args.get("state", "open")
                query = args.get("query", "")
                cmd = f"gh issue list --repo {owner}/{repo} --state {state} --limit 20"
                if query:
                    cmd += f" --search '{query}'"
                proc = await _aio.create_subprocess_shell(
                    cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE)
                out, err = await proc.communicate()
                return (out or err).decode()[:6000]
            if name == "github_prs":
                state = args.get("state", "open")
                cmd = f"gh pr list --repo {owner}/{repo} --state {state} --limit 20"
                proc = await _aio.create_subprocess_shell(
                    cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE)
                out, err = await proc.communicate()
                return (out or err).decode()[:6000]
            if name == "github_code_search":
                query = args.get("query", "")
                cmd = f"gh search code '{query}' --limit 20"
                proc = await _aio.create_subprocess_shell(
                    cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE)
                out, err = await proc.communicate()
                return (out or err).decode()[:6000]
            if name == "github_actions":
                cmd = f"gh run list --repo {owner}/{repo} --limit 10"
                status = args.get("status")
                if status:
                    cmd += f" --status {status}"
                proc = await _aio.create_subprocess_shell(
                    cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE)
                out, err = await proc.communicate()
                return (out or err).decode()[:6000]
        except Exception as e:
            return f"GitHub CLI error: {e}"
        return f"Unknown GitHub tool: {name}"

    async def _tool_mcp_jira(self, name: str, args: dict, ctx: ExecutionContext) -> str:
        """JIRA/Confluence integration (needs ATLASSIAN_TOKEN env var)."""
        import os
        token = os.environ.get("ATLASSIAN_TOKEN")
        base_url = os.environ.get("ATLASSIAN_URL", "")
        if not token or not base_url:
            return "JIRA/Confluence not configured. Set ATLASSIAN_TOKEN and ATLASSIAN_URL env vars."
        import aiohttp
        headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                if name == "jira_search":
                    jql = args.get("jql", "")
                    max_r = args.get("max_results", 10)
                    async with session.get(
                        f"{base_url}/rest/api/3/search?jql={jql}&maxResults={max_r}",
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        data = await resp.json()
                        issues = data.get("issues", [])
                        return "\n".join(
                            f"[{i['key']}] {i['fields'].get('summary','')} ({i['fields'].get('status',{}).get('name','')})"
                            for i in issues
                        ) or "No issues found."
                if name == "jira_create":
                    payload = {"fields": {
                        "project": {"key": args["project"]},
                        "summary": args["summary"],
                        "issuetype": {"name": args["type"]},
                        "description": {"type": "doc", "version": 1, "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": args.get("description", "")}]}
                        ]},
                    }}
                    async with session.post(
                        f"{base_url}/rest/api/3/issue",
                        json=payload, timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        data = await resp.json()
                        return f"Created: {data.get('key', 'unknown')} — {data.get('self', '')}"
                if name == "confluence_read":
                    title = args.get("title", "")
                    space = args.get("space", "")
                    page_id = args.get("page_id", "")
                    if page_id:
                        url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage"
                    else:
                        url = f"{base_url}/wiki/rest/api/content?title={title}&spaceKey={space}&expand=body.storage"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        data = await resp.json()
                        if "results" in data:
                            pages = data["results"]
                        else:
                            pages = [data]
                        parts = []
                        for p in pages[:3]:
                            parts.append(f"# {p.get('title','')}\n{p.get('body',{}).get('storage',{}).get('value','')[:3000]}")
                        return "\n\n".join(parts) or "No page found."
        except Exception as e:
            return f"JIRA/Confluence error: {e}"
        return f"Unknown JIRA tool: {name}"

    def _parse_delegations(self, content: str) -> list[dict]:
        """Parse [DELEGATE:agent_id] markers from response."""
        delegations = []
        for line in content.split("\n"):
            if "[DELEGATE:" in line:
                try:
                    start = line.index("[DELEGATE:") + len("[DELEGATE:")
                    end = line.index("]", start)
                    agent_id = line[start:end]
                    task = line[end + 1:].strip()
                    delegations.append({"to_agent": agent_id, "task": task})
                except (ValueError, IndexError):
                    pass
        return delegations


# Singleton
_executor: Optional[AgentExecutor] = None


def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
