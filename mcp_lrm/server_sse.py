#!/usr/bin/env python3
"""
MCP LRM Server - SSE/HTTP Version (Single Daemon)
==================================================
One server instance serves all workers via Server-Sent Events.

Architecture:
    ┌─────────────────────────────────────────┐
    │     MCP LRM Server (this daemon)        │
    │     http://localhost:9500               │
    │                                         │
    │  /sse         - SSE endpoint for MCP    │
    │  /health      - Health check            │
    │  /tools       - List available tools    │
    └─────────────────────────────────────────┘
              ▲   ▲   ▲   ▲
              │   │   │   │
         Worker1  W2  W3 ... W50 (opencode)

Usage:
    # Start daemon
    python -m mcp_lrm.server_sse

    # Or via factory CLI
    factory mcp start
    factory mcp stop
    factory mcp status
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import signal
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from aiohttp import web
    from aiohttp_sse import sse_response
except ImportError:
    print("Installing required packages...")
    import subprocess

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "aiohttp", "aiohttp-sse"], check=True
    )
    from aiohttp import web
    from aiohttp_sse import sse_response

from mcp_lrm.exclusions import should_exclude_path


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_PORT = 9500
DEFAULT_HOST = "127.0.0.1"
PID_FILE = Path("/tmp/factory/mcp-lrm.pid")
LOG_FILE = Path(__file__).parent.parent / "data" / "logs" / "mcp-lrm.log"


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [MCP-LRM] [{level}] {msg}"
    print(line, file=sys.stderr)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _constrain_vitest(cmd: str) -> str:
    """Inject --pool=forks --poolOptions.forks.maxForks=1 into vitest commands.
    Prevents 4GB RAM per vitest worker process."""
    if "vitest" not in cmd:
        return cmd
    constraint = "--pool=forks --poolOptions.forks.maxForks=1"
    if constraint in cmd or "--pool=" in cmd:
        return cmd  # already constrained
    # Insert after 'vitest run' or 'vitest' keyword
    cmd = re.sub(
        r"(vitest\s+run)\b",
        rf"\1 {constraint}",
        cmd,
    )
    if constraint not in cmd:
        # Fallback: insert after 'vitest'
        cmd = re.sub(
            r"(vitest)\b",
            rf"\1 {constraint}",
            cmd,
            count=1,
        )
    log(f"Vitest constrained: {cmd[:120]}")
    return cmd


# ============================================================================
# MCP LRM SERVER (Shared Instance)
# ============================================================================


class MCPLRMServer:
    """
    Singleton MCP server that handles all tool calls.
    Shared across all SSE connections.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.projects: Dict[str, Any] = {}  # Cache of loaded projects
        self.task_store = None
        self.active_connections: Set[str] = set()

        self._load_task_store()
        log("MCP LRM Server initialized")

    def _load_task_store(self):
        """Load shared task store"""
        try:
            from core.task_store import TaskStore

            self.task_store = TaskStore()
            log("TaskStore connected")
        except Exception as e:
            log(f"TaskStore error: {e}", "WARN")

    def get_project(self, project_name: str):
        """Get or load project config (cached)"""
        if project_name not in self.projects:
            try:
                from core.project_registry import get_project

                self.projects[project_name] = get_project(project_name)
                log(f"Loaded project: {project_name}")
            except Exception as e:
                log(f"Failed to load project {project_name}: {e}", "ERROR")
                return None
        return self.projects[project_name]

    def get_tools(self) -> List[Dict]:
        """Return tool definitions for MCP"""
        return [
            {
                "name": "locate",
                "description": "Find files in project matching pattern or search query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (glob pattern or text)",
                        },
                        "project": {"type": "string", "description": "Project name"},
                        "scope": {
                            "type": "string",
                            "description": "Scope: 'all', domain, or path prefix",
                            "default": "all",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 20,
                        },
                    },
                    "required": ["query", "project"],
                },
            },
            {
                "name": "read",
                "description": "Read file content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path (relative to project root)",
                        },
                        "project": {"type": "string", "description": "Project name"},
                        "lines": {
                            "type": "integer",
                            "description": "Max lines to read",
                            "default": 500,
                        },
                    },
                    "required": ["path", "project"],
                },
            },
            {
                "name": "conventions",
                "description": "Get project conventions for a domain",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain: rust, typescript, python, etc.",
                        },
                        "project": {"type": "string", "description": "Project name"},
                    },
                    "required": ["domain", "project"],
                },
            },
            {
                "name": "task_read",
                "description": "Read task details by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID"},
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "task_update",
                "description": "Update task status",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID"},
                        "status": {"type": "string", "description": "New status"},
                    },
                    "required": ["task_id", "status"],
                },
            },
            {
                "name": "build",
                "description": "Run build or test command",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain: rust, typescript, etc.",
                        },
                        "project": {"type": "string", "description": "Project name"},
                        "command": {
                            "type": "string",
                            "description": "Command: build, test, lint",
                            "default": "build",
                        },
                    },
                    "required": ["domain", "project"],
                },
            },
            {
                "name": "confluence_search",
                "description": "Search Confluence wiki pages (full-text). Returns titles, excerpts, page IDs. Content is anonymized.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (keywords)",
                        },
                        "space": {
                            "type": "string",
                            "description": "Confluence space key",
                            "default": "IAN",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 10,
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh from Confluence API",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "confluence_read",
                "description": "Read a Confluence page by ID or title. Returns full content, anonymized.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Confluence page ID",
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title (alternative to page_id)",
                        },
                        "space": {
                            "type": "string",
                            "description": "Space key",
                            "default": "IAN",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Max chars to return",
                            "default": 8000,
                        },
                    },
                },
            },
            {
                "name": "jira_search",
                "description": "Search Jira issues via JQL or keywords. Returns issue keys, summaries, statuses. Content is anonymized.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "JQL query or plain text keywords",
                        },
                        "project": {
                            "type": "string",
                            "description": "Jira project key (optional filter)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 20,
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh from Jira API",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "component_gallery_list",
                "description": "List all 60 UI components from the Component Gallery knowledge base with descriptions. Cross-references 50+ Design Systems (Material, Carbon, Atlassian, Ant, etc.)",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "component_gallery_get",
                "description": "Get full documentation for a UI component: description, all aliases/names used across design systems, N implementations with DS name + URL + tech stack.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component slug (e.g. 'accordion', 'button', 'tabs', 'modal', 'toast')",
                        },
                        "tech": {
                            "type": "string",
                            "description": "Filter by tech: React, Vue, Angular, CSS, Web Components, etc.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max implementations (default 20)",
                            "default": 20,
                        },
                    },
                    "required": ["component"],
                },
            },
            {
                "name": "component_gallery_search",
                "description": "Full-text search across all 60 UI components and their aliases.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms (component name, concept, or alias)",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "component_gallery_ds",
                "description": "Show how a specific Design System names/implements its components.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ds_name": {
                            "type": "string",
                            "description": "Design system name (partial ok): Material, Carbon, Atlassian, Ant Design, Spectrum, Primer, Fluent...",
                        },
                    },
                    "required": ["ds_name"],
                },
            },
            # ── Guidelines (Architecture wiki) ──
            {
                "name": "guidelines_summary",
                "description": "Get the architecture/tech guidelines summary for a project. Returns compact constraints: tech stack required, forbidden libs/patterns, standards. Injected in agent system prompts automatically, but can also be queried explicitly.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project ID (e.g. 'bscc', 'greenfleet')",
                        },
                        "role": {
                            "type": "string",
                            "description": "Agent role for filtering: dev, architecture, security, frontend",
                            "default": "dev",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Max chars to return",
                            "default": 800,
                        },
                    },
                },
            },
            {
                "name": "guidelines_search",
                "description": "Full-text search across org/project architecture guidelines wiki. Use to find specific rules, decisions, or guidance on a topic.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms (e.g. 'auth', 'database', 'API standards', 'frontend framework')",
                        },
                        "project": {"type": "string", "description": "Project ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max results",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "guidelines_get",
                "description": "Get full content of a specific architecture guideline page (by title or page ID).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Page title (partial match ok)",
                        },
                        "project": {"type": "string", "description": "Project ID"},
                        "page_id": {
                            "type": "string",
                            "description": "Exact page ID (alternative to title)",
                        },
                    },
                },
            },
            {
                "name": "guidelines_stack",
                "description": "Get the required tech stack for a project (must_use items by topic: backend, frontend, database, auth, infra). Use before choosing technologies.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project ID"},
                        "topic": {
                            "type": "string",
                            "description": "Filter by topic: backend, frontend, database, auth, infra, security, quality",
                        },
                    },
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: Dict) -> Any:
        """Handle a tool call - accepts with or without lrm_ prefix"""
        # Strip any prefix variations
        clean_name = name.replace("lrm_lrm_", "").replace("lrm_", "")
        try:
            if clean_name == "locate":
                return await self._tool_locate(arguments)
            elif clean_name == "read":
                return await self._tool_read(arguments)
            elif clean_name == "conventions":
                return await self._tool_conventions(arguments)
            elif clean_name == "task_read":
                return await self._tool_task_read(arguments)
            elif clean_name == "task_update":
                return await self._tool_task_update(arguments)
            elif clean_name == "build":
                return await self._tool_build(arguments)
            elif clean_name == "confluence_search":
                return await self._tool_confluence_search(arguments)
            elif clean_name == "confluence_read":
                return await self._tool_confluence_read(arguments)
            elif clean_name == "jira_search":
                return await self._tool_jira_search(arguments)
            elif clean_name == "component_gallery_list":
                return await self._tool_component_gallery_list(arguments)
            elif clean_name == "component_gallery_get":
                return await self._tool_component_gallery_get(arguments)
            elif clean_name == "component_gallery_search":
                return await self._tool_component_gallery_search(arguments)
            elif clean_name == "component_gallery_ds":
                return await self._tool_component_gallery_ds(arguments)
            elif clean_name == "guidelines_summary":
                return await self._tool_guidelines_summary(arguments)
            elif clean_name == "guidelines_search":
                return await self._tool_guidelines_search(arguments)
            elif clean_name == "guidelines_get":
                return await self._tool_guidelines_get(arguments)
            elif clean_name == "guidelines_stack":
                return await self._tool_guidelines_stack(arguments)
            else:
                return {"error": f"Unknown tool: {name} (cleaned: {clean_name})"}
        except Exception as e:
            log(f"Tool {name} error: {e}", "ERROR")
            return {"error": str(e)}

    async def _tool_locate(self, args: Dict) -> Dict:
        """Find files matching pattern"""
        project = self.get_project(args.get("project"))
        if not project:
            return {"error": "Project not found"}

        query = args.get("query", "")
        limit = args.get("limit", 20)

        import glob
        import subprocess

        root = project.root_path
        results = []

        # Try glob first
        if "*" in query or "?" in query:
            pattern = str(root / query)
            for path in glob.glob(pattern, recursive=True)[:limit]:
                rel_path = str(Path(path).relative_to(root))
                if not should_exclude_path(rel_path):
                    results.append(rel_path)
        else:
            # Use ripgrep for content search
            try:
                proc = subprocess.run(
                    ["rg", "-l", "--max-count=1", query, str(root)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in proc.stdout.strip().split("\n")[:limit]:
                    if line:
                        rel_path = str(Path(line).relative_to(root))
                        if not should_exclude_path(rel_path):
                            results.append(rel_path)
            except Exception:
                pass

        return {"files": results, "count": len(results)}

    async def _tool_read(self, args: Dict) -> Dict:
        """Read file content"""
        project = self.get_project(args.get("project"))
        if not project:
            return {"error": "Project not found"}

        path = args.get("path", "")
        max_lines = args.get("lines", 500)

        full_path = project.root_path / path
        if not full_path.exists():
            return {"error": f"File not found: {path}"}

        try:
            content = full_path.read_text()
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n\n... (truncated, {len(lines)} total lines)"
            return {"content": content, "lines": len(lines)}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_conventions(self, args: Dict) -> Dict:
        """Get project conventions including stack versions and framework-specific rules"""
        project = self.get_project(args.get("project"))
        if not project:
            return {"error": "Project not found"}

        domain = args.get("domain", "")

        # Default conventions (baseline)
        default_conventions = {
            "rust": {
                "error_handling": "Use Result<T, E> and ? operator. Avoid .unwrap() in production.",
                "testing": "Use #[cfg(test)] mod tests { ... } with #[test] functions.",
                "naming": "snake_case for functions/variables, PascalCase for types.",
            },
            "typescript": {
                "error_handling": "Use try/catch with specific error types. No empty catch blocks.",
                "testing": "Use vitest with describe/it. Co-locate tests with source.",
                "naming": "camelCase for functions/variables, PascalCase for types/components.",
            },
            "python": {
                "error_handling": "Use specific exceptions. Document with docstrings.",
                "testing": "Use pytest with descriptive test names.",
                "naming": "snake_case for functions/variables, PascalCase for classes.",
            },
        }

        result = default_conventions.get(domain, {})

        # Merge project-specific conventions from YAML
        if project and hasattr(project, "config") and project.config:
            domains_config = project.config.get("domains", {})
            domain_config = domains_config.get(domain, {})

            # Add stack versions (CRITICAL for correct code generation)
            if "stack" in domain_config:
                result["stack"] = domain_config["stack"]

            # Add framework-specific conventions (e.g., axum 0.7 rules)
            if "conventions" in domain_config:
                result["framework_conventions"] = domain_config["conventions"]

            # Add build/test commands
            if "build_cmd" in domain_config:
                result["build_cmd"] = domain_config["build_cmd"]
            if "test_cmd" in domain_config:
                result["test_cmd"] = domain_config["test_cmd"]

        return {"conventions": result, "domain": domain}

    async def _tool_task_read(self, args: Dict) -> Dict:
        """Read task details"""
        if not self.task_store:
            return {"error": "TaskStore not available"}

        task_id = args.get("task_id")
        task = self.task_store.get_task(task_id)
        if not task:
            return {"error": f"Task not found: {task_id}"}

        return task.to_dict()

    async def _tool_task_update(self, args: Dict) -> Dict:
        """Update task status"""
        if not self.task_store:
            return {"error": "TaskStore not available"}

        task_id = args.get("task_id")
        status = args.get("status")

        success = self.task_store.transition(task_id, status, changed_by="mcp-lrm")
        return {"success": success, "task_id": task_id, "status": status}

    async def _tool_build(self, args: Dict) -> Dict:
        """Run build/test command"""
        project = self.get_project(args.get("project"))
        if not project:
            return {"error": "Project not found"}

        domain = args.get("domain", "")
        command = args.get("command", "build")

        if command == "build":
            cmd = project.get_build_cmd(domain)
        elif command == "test":
            cmd = project.get_test_cmd(domain)
        elif command == "lint":
            cmd = project.get_lint_cmd(domain)
        else:
            return {"error": f"Unknown command: {command}"}

        if not cmd:
            return {"error": f"No {command} command for domain {domain}"}

        # Vitest memory constraint: prevent 4GB per worker
        cmd = _constrain_vitest(cmd)

        import subprocess

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(project.root_path),
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:]
                if len(proc.stdout) > 2000
                else proc.stdout,
                "stderr": proc.stderr[-2000:]
                if len(proc.stderr) > 2000
                else proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out (300s)"}
        except Exception as e:
            return {"error": str(e)}

    # ── Confluence tools ──

    def _get_confluence_client(self):
        """Lazy-load Confluence client."""
        if not hasattr(self, "_confluence_client"):
            self._confluence_client = None
            try:
                import sys

                sys.path.insert(
                    0, str(Path(__file__).resolve().parents[0].parent / "platform")
                )
                from confluence.client import ConfluenceClient

                self._confluence_client = ConfluenceClient()
                log("Confluence client loaded")
            except Exception as e:
                log(f"Confluence client unavailable: {e}", "WARN")
        return self._confluence_client

    def _get_anonymizer(self):
        """Lazy-load anonymizer."""
        if not hasattr(self, "_anonymizer"):
            from .anonymizer import get_anonymizer

            self._anonymizer = get_anonymizer()
        return self._anonymizer

    def _get_cache(self):
        """Lazy-load RLM cache."""
        if not hasattr(self, "_rlm_cache"):
            from .rlm_cache import get_rlm_cache

            self._rlm_cache = get_rlm_cache()
        return self._rlm_cache

    async def _tool_confluence_search(self, args: Dict) -> Dict:
        """Search Confluence wiki pages."""
        query = args.get("query", "")
        space = args.get("space", "IAN")
        limit = args.get("limit", 10)
        refresh = args.get("refresh", False)

        cache = self._get_cache()
        anon = self._get_anonymizer()

        # Try cache first
        if not refresh:
            results = cache.search_confluence(query, limit)
            if results:
                return {
                    "results": [anon.anonymize_dict(r) for r in results],
                    "source": "cache",
                }

        # Fetch from Confluence API
        client = self._get_confluence_client()
        if not client:
            # Fallback to cache even if stale
            results = cache.search_confluence(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "cache",
                "note": "Confluence API unavailable",
            }

        try:
            import re as _re

            # Use CQL search
            cql = f'space="{space}" AND (title~"{query}" OR text~"{query}")'
            pages = client.search_cql(cql, limit=limit, expand="body.storage,ancestors")
            for p in pages:
                body_html = p.get("body", {}).get("storage", {}).get("value", "")
                # Strip HTML tags for plain text
                body_text = _re.sub(r"<[^>]+>", " ", body_html)
                body_text = _re.sub(r"\s+", " ", body_text).strip()
                ancestors = " > ".join(
                    a.get("title", "") for a in p.get("ancestors", [])
                )
                url = client.base_url + p.get("_links", {}).get("webui", "")
                cache.upsert_confluence_page(
                    page_id=str(p["id"]),
                    space_key=space,
                    title=p["title"],
                    body=body_text,
                    url=url,
                    ancestors=ancestors,
                )

            results = cache.search_confluence(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "api",
                "fetched": len(pages),
            }
        except Exception as e:
            log(f"Confluence search error: {e}", "ERROR")
            results = cache.search_confluence(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "cache",
                "error": str(e),
            }

    async def _tool_confluence_read(self, args: Dict) -> Dict:
        """Read a Confluence page by ID or title."""
        page_id = args.get("page_id", "")
        title = args.get("title", "")
        space = args.get("space", "IAN")
        max_chars = args.get("max_chars", 8000)

        cache = self._get_cache()
        anon = self._get_anonymizer()

        # Try cache first
        if page_id:
            cached = cache.get_confluence_page(page_id)
            if cached and not cached.get("stale"):
                cached["body"] = cached["body"][:max_chars]
                return anon.anonymize_dict(cached)

        # Fetch from API
        client = self._get_confluence_client()
        if not client:
            if page_id:
                cached = cache.get_confluence_page(page_id)
                if cached:
                    cached["body"] = cached["body"][:max_chars]
                    return anon.anonymize_dict(cached)
            return {"error": "Confluence API unavailable and page not in cache"}

        try:
            import re as _re

            if title and not page_id:
                # Find by title
                found = client.find_page(title, space)
                if found:
                    page_id = str(found["id"])
                else:
                    return {"error": f"Page '{title}' not found in space {space}"}

            page = client.get_page(page_id)
            if not page:
                return {"error": f"Page {page_id} not found"}

            body_html = page.get("body", {}).get("storage", {}).get("value", "")
            body_text = _re.sub(r"<[^>]+>", " ", body_html)
            body_text = _re.sub(r"\s+", " ", body_text).strip()
            ancestors = " > ".join(
                a.get("title", "") for a in page.get("ancestors", [])
            )
            url = client.base_url + page.get("_links", {}).get("webui", "")

            cache.upsert_confluence_page(
                page_id=page_id,
                space_key=space,
                title=page["title"],
                body=body_text,
                url=url,
                ancestors=ancestors,
            )

            result = {
                "page_id": page_id,
                "title": page["title"],
                "space_key": space,
                "body": body_text[:max_chars],
                "url": url,
                "ancestors": ancestors,
            }
            return anon.anonymize_dict(result)
        except Exception as e:
            log(f"Confluence read error: {e}", "ERROR")
            return {"error": str(e)}

    # ── Jira tools ──

    def _get_jira_config(self):
        """Load Jira configuration from tokens."""
        if not hasattr(self, "_jira_config"):
            self._jira_config = None
            # Try ~/.config/factory/jira.key
            key_file = Path.home() / ".config" / "factory" / "jira.key"
            if key_file.exists():
                token = key_file.read_text().strip()
            else:
                token = os.environ.get("ATLASSIAN_TOKEN", "")

            url = os.environ.get("ATLASSIAN_URL", "") or os.environ.get("JIRA_URL", "")
            if not url:
                # Try to infer from Confluence URL
                confluence_url = os.environ.get(
                    "CONFLUENCE_URL", "https://wiki.net.extra.laposte.fr/confluence"
                )
                # Jira is typically on same domain as Confluence
                url = confluence_url.replace("/confluence", "/jira").replace(
                    "wiki.", "jira."
                )

            if token and url:
                self._jira_config = {"url": url, "token": token}
                log(f"Jira configured: {url}")
            else:
                log("Jira not configured (no token/URL)", "WARN")
        return self._jira_config

    async def _tool_jira_search(self, args: Dict) -> Dict:
        """Search Jira issues."""
        query = args.get("query", "")
        project = args.get("project", "")
        limit = args.get("limit", 20)
        refresh = args.get("refresh", False)

        cache = self._get_cache()
        anon = self._get_anonymizer()

        # Try cache first
        if not refresh:
            results = cache.search_jira(query, limit)
            if results:
                return {
                    "results": [anon.anonymize_dict(r) for r in results],
                    "source": "cache",
                }

        # Fetch from Jira API
        jira = self._get_jira_config()
        if not jira:
            results = cache.search_jira(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "cache",
                "note": "Jira not configured",
            }

        try:
            import urllib.request
            import json

            # Build JQL
            if (
                query.upper().startswith("PROJECT")
                or "=" in query
                or " AND " in query.upper()
            ):
                jql = query  # Already JQL
            else:
                jql = f'text ~ "{query}"'
                if project:
                    jql = f'project = "{project}" AND {jql}'
            jql += " ORDER BY updated DESC"

            url = f"{jira['url']}/rest/api/2/search"
            data = json.dumps(
                {
                    "jql": jql,
                    "maxResults": limit,
                    "fields": [
                        "summary",
                        "description",
                        "status",
                        "assignee",
                        "priority",
                        "issuetype",
                        "labels",
                        "created",
                    ],
                }
            ).encode()

            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {jira['token']}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())

            issues = result.get("issues", [])
            for issue in issues:
                fields = issue.get("fields", {})
                cache.upsert_jira_issue(
                    issue_key=issue["key"],
                    project=issue["key"].split("-")[0],
                    summary=fields.get("summary", ""),
                    description=(fields.get("description") or "")[:5000],
                    status=(fields.get("status", {}) or {}).get("name", ""),
                    assignee=(fields.get("assignee", {}) or {}).get("displayName", ""),
                    priority=(fields.get("priority", {}) or {}).get("name", ""),
                    issue_type=(fields.get("issuetype", {}) or {}).get("name", ""),
                    labels=",".join(fields.get("labels", [])),
                    created_at=fields.get("created", ""),
                )

            results = cache.search_jira(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "api",
                "fetched": len(issues),
            }
        except Exception as e:
            log(f"Jira search error: {e}", "ERROR")
            results = cache.search_jira(query, limit)
            return {
                "results": [anon.anonymize_dict(r) for r in results],
                "source": "cache",
                "error": str(e),
            }

    # ── Architecture Guidelines ───────────────────────────────────────────────

    _GL_DB_PATH = Path(__file__).parent.parent / "data" / "guidelines.db"

    def _gl_db(self) -> Optional[sqlite3.Connection]:
        if not self._GL_DB_PATH.exists():
            return None
        conn = sqlite3.connect(str(self._GL_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    async def _tool_guidelines_summary(self, args: Dict) -> Dict:
        project = args.get("project", "default")
        role = args.get("role", "dev")
        max_chars = int(args.get("max_chars", 800))
        from .guidelines_scraper import build_guidelines_summary

        summary = build_guidelines_summary(project, role, max_chars)
        if not summary:
            return {
                "note": f"No guidelines found for project '{project}'. Run: python -m mcp_lrm.guidelines_scraper --source confluence --space BSCC --project {project}"
            }
        return {"project": project, "summary": summary}

    async def _tool_guidelines_search(self, args: Dict) -> Dict:
        query = args.get("query", "").strip()
        project = args.get("project", "default")
        limit = int(args.get("limit", 5))
        if not query:
            return {"error": "query is required"}
        conn = self._gl_db()
        if not conn:
            return {
                "error": "Guidelines DB not found. Run: python -m mcp_lrm.guidelines_scraper --help"
            }
        try:
            rows = conn.execute(
                "SELECT id, title, url, category, summary FROM guideline_pages "
                "WHERE project = ? AND (title LIKE ? OR content LIKE ? OR summary LIKE ?) LIMIT ?",
                (project, f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        except Exception:
            rows = []
        # Also try FTS
        if not rows:
            try:
                rows = conn.execute(
                    "SELECT p.id, p.title, p.url, p.category, p.summary "
                    "FROM guideline_fts f JOIN guideline_pages p ON f.rowid = p.rowid "
                    "WHERE f MATCH ? AND p.project = ? LIMIT ?",
                    (query, project, limit),
                ).fetchall()
            except Exception:
                pass
        conn.close()
        return {
            "query": query,
            "project": project,
            "count": len(rows),
            "results": [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "category": r["category"],
                    "url": r["url"],
                    "summary": r["summary"],
                }
                for r in rows
            ],
        }

    async def _tool_guidelines_get(self, args: Dict) -> Dict:
        project = args.get("project", "default")
        title = args.get("title", "").strip()
        page_id = args.get("page_id", "").strip()
        conn = self._gl_db()
        if not conn:
            return {"error": "Guidelines DB not found"}
        if page_id:
            row = conn.execute(
                "SELECT * FROM guideline_pages WHERE id = ? AND project = ?",
                (page_id, project),
            ).fetchone()
        elif title:
            row = conn.execute(
                "SELECT * FROM guideline_pages WHERE project = ? AND title LIKE ? LIMIT 1",
                (project, f"%{title}%"),
            ).fetchone()
        else:
            return {"error": "Provide title or page_id"}
        if not row:
            conn.close()
            return {
                "error": f"Page not found for title='{title}' page_id='{page_id}' project='{project}'"
            }
        items = conn.execute(
            "SELECT category, topic, constraint_text FROM guideline_items WHERE source_page_id = ?",
            (row["id"],),
        ).fetchall()
        conn.close()
        return {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "url": row["url"],
            "summary": row["summary"],
            "content": (row["content"] or "")[:3000],
            "extracted_items": [
                {
                    "category": i["category"],
                    "topic": i["topic"],
                    "constraint": i["constraint_text"],
                }
                for i in items
            ],
        }

    async def _tool_guidelines_stack(self, args: Dict) -> Dict:
        project = args.get("project", "default")
        topic_filter = args.get("topic", "").strip()
        conn = self._gl_db()
        if not conn:
            return {"error": "Guidelines DB not found"}
        q = "SELECT category, topic, constraint_text, source_title FROM guideline_items WHERE project = ? AND category IN ('must_use', 'forbidden', 'standard')"
        params: list = [project]
        if topic_filter:
            q += " AND topic LIKE ?"
            params.append(f"%{topic_filter}%")
        q += " ORDER BY category, topic"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        by_cat: dict = {}
        for r in rows:
            cat = r["category"]
            by_cat.setdefault(cat, []).append(
                {
                    "topic": r["topic"],
                    "constraint": r["constraint_text"],
                    "source": r["source_title"],
                }
            )
        return {
            "project": project,
            "topic_filter": topic_filter or "all",
            "items": by_cat,
            "total": len(rows),
        }

    # ── Component Gallery ──────────────────────────────────────────────────

    _CG_DB_PATH = Path(__file__).parent.parent / "data" / "component_gallery.db"

    def _cg_db(self):
        """Open component gallery SQLite connection."""
        import sqlite3

        if not self._CG_DB_PATH.exists():
            return None
        conn = sqlite3.connect(str(self._CG_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    async def _tool_component_gallery_list(self, args: Dict) -> Dict:
        conn = self._cg_db()
        if not conn:
            return {
                "error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"
            }
        rows = conn.execute(
            "SELECT slug, name, description, aliases, "
            "(SELECT COUNT(*) FROM implementations WHERE component_slug=slug) as impl_count "
            "FROM components ORDER BY slug"
        ).fetchall()
        conn.close()
        return {
            "count": len(rows),
            "source": "https://component.gallery",
            "components": [
                {
                    "slug": r["slug"],
                    "name": r["name"],
                    "description": (r["description"] or "")[:120],
                    "aliases": r["aliases"],
                    "implementations": r["impl_count"],
                }
                for r in rows
            ],
        }

    async def _tool_component_gallery_get(self, args: Dict) -> Dict:
        slug = args.get("component", "").lower().strip()
        tech_filter = args.get("tech", "").strip()
        limit = min(int(args.get("limit", 20)), 200)
        conn = self._cg_db()
        if not conn:
            return {
                "error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"
            }
        row = conn.execute(
            "SELECT * FROM components WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM components WHERE slug LIKE ? OR name LIKE ? LIMIT 1",
                (f"%{slug}%", f"%{slug}%"),
            ).fetchone()
        if not row:
            available = [
                r[0] for r in conn.execute("SELECT slug FROM components ORDER BY slug")
            ]
            conn.close()
            return {"error": f"Component '{slug}' not found", "available": available}
        real_slug = row["slug"]
        query = "SELECT component_name, ds_name, url, tech, features FROM implementations WHERE component_slug = ?"
        params: list = [real_slug]
        if tech_filter:
            query += " AND tech LIKE ?"
            params.append(f"%{tech_filter}%")
        query += f" ORDER BY ds_name LIMIT {limit}"
        impls = conn.execute(query, params).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM implementations WHERE component_slug = ?",
            (real_slug,),
        ).fetchone()[0]
        conn.close()
        return {
            "slug": real_slug,
            "name": row["name"],
            "description": row["description"],
            "aliases": row["aliases"],
            "source": f"https://component.gallery/components/{real_slug}/",
            "total_implementations": total,
            "implementations_returned": len(impls),
            "implementations": [
                {
                    "name_in_ds": i["component_name"],
                    "design_system": i["ds_name"],
                    "url": i["url"],
                    "tech": i["tech"],
                    "features": i["features"],
                }
                for i in impls
            ],
        }

    async def _tool_component_gallery_search(self, args: Dict) -> Dict:
        query = args.get("query", "").strip()
        if not query:
            return {"error": "query is required"}
        conn = self._cg_db()
        if not conn:
            return {
                "error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"
            }
        try:
            rows = conn.execute(
                "SELECT slug, name, description, aliases FROM components_fts WHERE components_fts MATCH ? LIMIT 10",
                (query,),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT slug, name, description, aliases FROM components "
                "WHERE slug LIKE ? OR name LIKE ? OR aliases LIKE ? OR description LIKE ? LIMIT 10",
                (f"%{query}%",) * 4,
            ).fetchall()
        conn.close()
        return {
            "query": query,
            "count": len(rows),
            "results": [
                {
                    "slug": r["slug"],
                    "name": r["name"],
                    "aliases": r["aliases"],
                    "description": (r["description"] or "")[:150],
                }
                for r in rows
            ],
        }

    async def _tool_component_gallery_ds(self, args: Dict) -> Dict:
        ds_name = args.get("ds_name", "").strip()
        if not ds_name:
            return {"error": "ds_name is required"}
        conn = self._cg_db()
        if not conn:
            return {
                "error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"
            }
        rows = conn.execute(
            "SELECT component_slug, component_name, url, tech FROM implementations WHERE ds_name LIKE ? ORDER BY component_slug",
            (f"%{ds_name}%",),
        ).fetchall()
        if not rows:
            ds_list = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT ds_name FROM implementations ORDER BY ds_name"
                )
            ]
            conn.close()
            return {
                "error": f"Design system '{ds_name}' not found",
                "available": ds_list,
            }
        actual_ds = conn.execute(
            "SELECT DISTINCT ds_name FROM implementations WHERE ds_name LIKE ? LIMIT 1",
            (f"%{ds_name}%",),
        ).fetchone()[0]
        conn.close()
        return {
            "design_system": actual_ds,
            "component_count": len(rows),
            "components": [
                {
                    "component": r["component_slug"],
                    "called": r["component_name"],
                    "url": r["url"],
                    "tech": r["tech"],
                }
                for r in rows
            ],
        }


# ============================================================================
# HTTP/SSE HANDLERS
# ============================================================================

mcp_server = MCPLRMServer()


async def handle_health(request):
    """Health check endpoint"""
    return web.json_response(
        {
            "status": "ok",
            "connections": len(mcp_server.active_connections),
            "projects_cached": len(mcp_server.projects),
        }
    )


async def handle_tools(request):
    """List available tools"""
    return web.json_response({"tools": mcp_server.get_tools()})


async def handle_sse(request):
    """
    SSE endpoint for MCP protocol.
    Each connection gets a unique session ID.
    Messages are JSON-RPC over SSE.
    """
    session_id = str(uuid.uuid4())[:8]
    mcp_server.active_connections.add(session_id)
    log(
        f"SSE connection opened: {session_id} (total: {len(mcp_server.active_connections)})"
    )

    try:
        async with sse_response(request) as resp:
            # Send initial connection message
            await resp.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "connection/ready",
                        "params": {"session_id": session_id},
                    }
                )
            )

            # Send tools list
            await resp.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "params": {"tools": mcp_server.get_tools()},
                    }
                )
            )

            # Keep connection alive and handle incoming messages
            while True:
                await asyncio.sleep(30)  # Heartbeat
                await resp.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "heartbeat",
                            "params": {"session_id": session_id},
                        }
                    )
                )

    except asyncio.CancelledError:
        pass
    finally:
        mcp_server.active_connections.discard(session_id)
        log(
            f"SSE connection closed: {session_id} (remaining: {len(mcp_server.active_connections)})"
        )

    return resp


async def handle_tool_call(request):
    """
    HTTP POST endpoint for tool calls.
    Used when SSE is not available or for one-shot calls.
    """
    try:
        data = await request.json()
        name = data.get("name")
        arguments = data.get("arguments", {})

        result = await mcp_server.handle_tool_call(name, arguments)
        return web.json_response({"result": result})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ============================================================================
# SERVER LIFECYCLE
# ============================================================================


async def on_startup(app):
    """Server startup hook"""
    log(f"MCP LRM Server starting on {DEFAULT_HOST}:{DEFAULT_PORT}")
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


async def on_cleanup(app):
    """Server cleanup hook"""
    log("MCP LRM Server stopping")
    if PID_FILE.exists():
        PID_FILE.unlink()


def create_app() -> web.Application:
    """Create aiohttp application"""
    app = web.Application()

    app.router.add_get("/health", handle_health)
    app.router.add_get("/tools", handle_tools)
    app.router.add_get("/sse", handle_sse)
    app.router.add_post("/call", handle_tool_call)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Run the MCP server"""
    app = create_app()
    web.run_app(app, host=host, port=port, print=lambda x: log(x))


# ============================================================================
# DAEMON MODE
# ============================================================================


def daemonize():
    """Double-fork to become a daemon"""
    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.setsid()

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect stdio
    sys.stdin = open(os.devnull, "r")
    sys.stdout = open(LOG_FILE, "a")
    sys.stderr = open(LOG_FILE, "a")


def start_daemon():
    """Start as daemon"""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"MCP LRM Server already running (PID {pid})")
            return
        except OSError:
            PID_FILE.unlink()

    print(f"Starting MCP LRM Server daemon on {DEFAULT_HOST}:{DEFAULT_PORT}")
    daemonize()
    run_server()


def stop_daemon():
    """Stop daemon"""
    if not PID_FILE.exists():
        print("MCP LRM Server not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped MCP LRM Server (PID {pid})")
    except OSError:
        print(f"Process {pid} not found")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def status_daemon():
    """Check daemon status"""
    if not PID_FILE.exists():
        print("MCP LRM Server: not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        print(f"MCP LRM Server: running (PID {pid})")

        # Try to get health
        import urllib.request

        try:
            with urllib.request.urlopen(
                f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/health", timeout=2
            ) as resp:
                data = json.loads(resp.read())
                print(f"  Connections: {data.get('connections', 0)}")
                print(f"  Projects cached: {data.get('projects_cached', 0)}")
        except Exception:
            print("  (health check failed)")

    except OSError:
        print(f"MCP LRM Server: dead (stale PID {pid})")
        PID_FILE.unlink()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP LRM Server (SSE/HTTP)")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "start", "stop", "status"],
        help="Command: run (foreground), start (daemon), stop, status",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind")

    args = parser.parse_args()

    if args.command == "run":
        run_server(args.host, args.port)
    elif args.command == "start":
        start_daemon()
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        status_daemon()
