#!/usr/bin/env python3
"""
MCP LRM Server - Model Context Protocol for Software Factory
============================================================
Provides project context access to LLM agents.

Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"
Instead of REPL access, agents get full project file access via MCP tools.

Tools:
- lrm_locate: Find files matching pattern or query
- lrm_summarize: Get summarized view of files
- lrm_conventions: Get project conventions for domain
- lrm_examples: Get example code (tests, implementations)
- lrm_task_read: Read task details
- lrm_task_update: Update task status
- lrm_subtask_create: Create sub-task (FRACTAL)
- lrm_build: Run build/test commands

Usage:
    # Run as MCP server (stdio)
    python -m mcp_lrm.server

    # Or with specific project
    FACTORY_PROJECT=ppz python -m mcp_lrm.server
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_lrm.exclusions import should_exclude_path, get_included_extensions


# ============================================================================
# MCP PROTOCOL HELPERS
# ============================================================================


async def read_message() -> Optional[Dict]:
    """Read a JSON-RPC message from stdin"""
    try:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def write_message(msg: Dict):
    """Write a JSON-RPC message to stdout"""
    json.dump(msg, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def make_response(id: Any, result: Any) -> Dict:
    """Create JSON-RPC response"""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id: Any, code: int, message: str) -> Dict:
    """Create JSON-RPC error response"""
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


# ============================================================================
# MCP LRM SERVER
# ============================================================================


class MCPLRMServer:
    """
    MCP server for LRM project context access.
    """

    def __init__(self, project_name: str = None):
        self.project_name = project_name or os.environ.get("FACTORY_PROJECT")
        self.project_config = None
        self.project_root: Optional[Path] = None
        self.task_store = None

        self._load_project()

    def _load_project(self):
        """Load project configuration"""
        try:
            from core.project_registry import get_project

            self.project_config = get_project(self.project_name)
            self.project_root = self.project_config.root_path
        except Exception as e:
            # Use current directory as fallback
            self.project_root = Path.cwd()
            print(f"Warning: Could not load project config: {e}", file=sys.stderr)

        try:
            from core.task_store import TaskStore

            self.task_store = TaskStore()
        except Exception as e:
            print(f"Warning: Could not initialize task store: {e}", file=sys.stderr)

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
                            "description": "Search query (glob pattern or text to find)",
                        },
                        "scope": {
                            "type": "string",
                            "description": "Scope: 'all', domain name, or path prefix",
                            "default": "all",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "summarize",
                "description": "Get summarized view of files with focus goal",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths to summarize",
                        },
                        "goal": {
                            "type": "string",
                            "description": "What to focus on in summary",
                        },
                    },
                    "required": ["files"],
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
                    },
                    "required": ["domain"],
                },
            },
            {
                "name": "examples",
                "description": "Get example code from project",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Type: 'test', 'implementation', 'api'",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Domain to get examples from",
                        },
                    },
                    "required": ["type", "domain"],
                },
            },
            {
                "name": "task_read",
                "description": "Read task details by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task ID to read",
                        },
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
                        "task_id": {
                            "type": "string",
                            "description": "Task ID to update",
                        },
                        "status": {
                            "type": "string",
                            "description": "New status: pending, tdd_in_progress, tdd_success, etc.",
                        },
                        "result": {
                            "type": "string",
                            "description": "Optional result/summary",
                        },
                    },
                    "required": ["task_id", "status"],
                },
            },
            {
                "name": "subtask_create",
                "description": "Create sub-task (FRACTAL decomposition)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "parent_id": {
                            "type": "string",
                            "description": "Parent task ID",
                        },
                        "description": {
                            "type": "string",
                            "description": "Sub-task description",
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files for sub-task",
                        },
                    },
                    "required": ["parent_id", "description"],
                },
            },
            {
                "name": "build",
                "description": "Run build or test command for domain",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain: rust, typescript, etc.",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command type: build, test, lint",
                            "default": "build",
                        },
                    },
                    "required": ["domain"],
                },
            },
            {
                "name": "component_gallery_list",
                "description": "List all 60 UI components from the Component Gallery knowledge base with descriptions. Cross-references 50+ Design Systems (Material, Carbon, Atlassian, Ant, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "component_gallery_get",
                "description": "Get full documentation for a UI component: description, all aliases/names used across design systems, N implementations with DS name + URL + tech stack. Also includes static markup/ARIA/CSS doc when available.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Component slug (e.g. 'accordion', 'button', 'tabs', 'modal', 'toast', 'tooltip', 'skeleton')",
                        },
                        "tech": {
                            "type": "string",
                            "description": "Filter implementations by tech stack: React, Vue, Angular, CSS, Web Components, etc.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max implementations to return (default 20, max 200)",
                            "default": 20,
                        },
                    },
                    "required": ["component"],
                },
            },
            {
                "name": "component_gallery_search",
                "description": "Full-text search across all 60 UI components and their aliases. Use to find which components relate to a concept (e.g. 'loading', 'navigation', 'form')",
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
                "description": "Show how a specific Design System names/implements its components. Useful to understand a DS vocabulary.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ds_name": {
                            "type": "string",
                            "description": "Design system name (partial match ok), e.g. 'Material', 'Carbon', 'Atlassian', 'Ant Design', 'Spectrum'",
                        },
                    },
                    "required": ["ds_name"],
                },
            },
            {
                "name": "context",
                "description": "Get project context from RAG (vision, architecture, requirements, conventions)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category: vision, architecture, data_model, api_surface, conventions, state, history, all",
                            "default": "all",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Max chars to return",
                            "default": 8000,
                        },
                    },
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: Dict) -> Any:
        """Handle a tool call"""
        handlers = {
            "locate": self._tool_locate,
            "summarize": self._tool_summarize,
            "conventions": self._tool_conventions,
            "examples": self._tool_examples,
            "task_read": self._tool_task_read,
            "task_update": self._tool_task_update,
            "subtask_create": self._tool_subtask_create,
            "build": self._tool_build,
            "context": self._tool_context,
            "component_gallery_list": self._tool_component_gallery_list,
            "component_gallery_get": self._tool_component_gallery_get,
            "component_gallery_search": self._tool_component_gallery_search,
            "component_gallery_ds": self._tool_component_gallery_ds,
        }

        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            return await handler(arguments)
        except Exception as e:
            return {"error": str(e)}

    async def _tool_locate(self, args: Dict) -> Dict:
        """Find files matching query"""
        import subprocess

        query = args.get("query", "")
        scope = args.get("scope", "all")
        limit = args.get("limit", 20)

        if not self.project_root:
            return {"error": "No project root configured"}

        # Determine search path
        search_path = self.project_root
        if scope != "all" and self.project_config:
            domain = self.project_config.get_domain(scope)
            if domain and domain.get("paths"):
                search_path = self.project_root / domain["paths"][0]

        results = []

        # Check if query is a glob pattern
        if "*" in query:
            for path in search_path.rglob(query):
                if not should_exclude_path(path):
                    results.append(str(path.relative_to(self.project_root)))
                    if len(results) >= limit:
                        break
        else:
            # Use ripgrep for text search
            try:
                proc = subprocess.run(
                    ["rg", "-l", "--max-count=1", query, str(search_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                for line in proc.stdout.strip().split("\n"):
                    if line:
                        path = Path(line)
                        if not should_exclude_path(path):
                            try:
                                results.append(str(path.relative_to(self.project_root)))
                            except ValueError:
                                results.append(line)
                            if len(results) >= limit:
                                break
            except FileNotFoundError:
                # Fallback to Python search
                extensions = get_included_extensions()
                for path in search_path.rglob("*"):
                    if path.is_file() and path.suffix in extensions:
                        if not should_exclude_path(path):
                            try:
                                content = path.read_text(errors="ignore")
                                if query.lower() in content.lower():
                                    results.append(
                                        str(path.relative_to(self.project_root))
                                    )
                                    if len(results) >= limit:
                                        break
                            except Exception:
                                continue

        return {"files": results, "count": len(results)}

    async def _tool_summarize(self, args: Dict) -> Dict:
        """Summarize files with focus"""
        files = args.get("files", [])
        goal = args.get("goal", "general understanding")

        if not self.project_root:
            return {"error": "No project root configured"}

        summaries = []
        for file_path in files[:10]:  # Limit to 10 files
            full_path = self.project_root / file_path
            if not full_path.exists():
                summaries.append({"file": file_path, "error": "not found"})
                continue

            try:
                content = full_path.read_text()
                lines = content.split("\n")

                # Extract key information
                imports = [
                    l
                    for l in lines[:50]
                    if l.strip().startswith(("import ", "use ", "from "))
                ]
                functions = [
                    l
                    for l in lines
                    if l.strip().startswith(
                        ("fn ", "def ", "function ", "async ", "pub fn")
                    )
                ]
                classes = [
                    l
                    for l in lines
                    if l.strip().startswith(
                        ("class ", "struct ", "enum ", "interface ")
                    )
                ]

                summaries.append(
                    {
                        "file": file_path,
                        "lines": len(lines),
                        "imports": imports[:10],
                        "functions": [f.strip()[:80] for f in functions[:10]],
                        "classes": [c.strip()[:80] for c in classes[:10]],
                    }
                )
            except Exception as e:
                summaries.append({"file": file_path, "error": str(e)})

        return {"summaries": summaries, "goal": goal}

    async def _tool_conventions(self, args: Dict) -> Dict:
        """Get project conventions for domain including stack versions and framework rules"""
        domain = args.get("domain", "")

        # Default conventions (baseline)
        conventions = {
            "rust": {
                "error_handling": "Use Result<T, E> with ? operator, avoid .unwrap()",
                "testing": "#[cfg(test)] mod tests { ... }",
                "naming": "snake_case for functions/variables, CamelCase for types",
                "modules": "mod.rs for directory modules",
            },
            "typescript": {
                "error_handling": "Use try/catch or Result pattern, avoid bare throws",
                "testing": "describe('...', () => { it('...', () => { ... }) })",
                "naming": "camelCase for functions/variables, PascalCase for types",
                "imports": "Use named imports, avoid default exports",
            },
            "python": {
                "error_handling": "Use try/except with specific exceptions",
                "testing": "pytest with test_ prefix functions",
                "naming": "snake_case for functions/variables, CamelCase for classes",
                "typing": "Use type hints for function signatures",
            },
        }

        domain_conventions = conventions.get(domain, {})

        # Add project-specific conventions from YAML
        if self.project_config and self.project_config.get_domain(domain):
            domain_config = self.project_config.get_domain(domain)
            domain_conventions["build_cmd"] = domain_config.get("build_cmd")
            domain_conventions["test_cmd"] = domain_config.get("test_cmd")

            # Add stack versions (CRITICAL for correct code generation)
            if "stack" in domain_config:
                domain_conventions["stack"] = domain_config["stack"]

            # Add framework-specific conventions (e.g., axum 0.7 rules)
            if "conventions" in domain_config:
                domain_conventions["framework_conventions"] = domain_config[
                    "conventions"
                ]

        return {"domain": domain, "conventions": domain_conventions}

    async def _tool_examples(self, args: Dict) -> Dict:
        """Get example code from project"""
        example_type = args.get("type", "test")
        domain = args.get("domain", "")

        if not self.project_root:
            return {"error": "No project root configured"}

        # Determine file patterns
        patterns = {
            "test": {
                "rust": "**/*_test.rs",
                "typescript": "**/*.test.ts",
                "python": "**/test_*.py",
            },
            "implementation": {
                "rust": "**/*.rs",
                "typescript": "**/*.ts",
                "python": "**/*.py",
            },
        }

        pattern = patterns.get(example_type, {}).get(domain, f"**/*.{domain}")

        examples = []
        for path in self.project_root.rglob(pattern):
            if should_exclude_path(path):
                continue

            try:
                content = path.read_text()
                # Get first 100 lines as example
                lines = content.split("\n")[:100]
                examples.append(
                    {
                        "file": str(path.relative_to(self.project_root)),
                        "content": "\n".join(lines),
                    }
                )
                if len(examples) >= 3:
                    break
            except Exception:
                continue

        return {"type": example_type, "domain": domain, "examples": examples}

    async def _tool_task_read(self, args: Dict) -> Dict:
        """Read task by ID"""
        task_id = args.get("task_id", "")

        if not self.task_store:
            return {"error": "Task store not available"}

        try:
            task = self.task_store.get_task(task_id)
            if task:
                return {"task": task.to_dict()}
            return {"error": f"Task {task_id} not found"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_task_update(self, args: Dict) -> Dict:
        """Update task status"""
        task_id = args.get("task_id", "")
        status = args.get("status", "")
        result = args.get("result")

        if not self.task_store:
            return {"error": "Task store not available"}

        try:
            success = self.task_store.transition(task_id, status)
            return {"success": success, "task_id": task_id, "new_status": status}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_subtask_create(self, args: Dict) -> Dict:
        """Create sub-task"""
        parent_id = args.get("parent_id", "")
        description = args.get("description", "")
        files = args.get("files", [])

        if not self.task_store:
            return {"error": "Task store not available"}

        try:
            # Get parent task to inherit properties
            parent = self.task_store.get_task(parent_id)
            if not parent:
                return {"error": f"Parent task {parent_id} not found"}

            # Create sub-task
            subtask_id = self.task_store.create_task(
                project_id=parent.project_id,
                task_type=parent.type,
                domain=parent.domain,
                description=description,
                files=files,
                parent_id=parent_id,
            )

            return {"success": True, "subtask_id": subtask_id, "parent_id": parent_id}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_build(self, args: Dict) -> Dict:
        """Run build command via global build queue (prevents CPU saturation)"""
        import subprocess

        domain = args.get("domain", "")
        command_type = args.get("command", "build")

        if not self.project_config:
            return {"error": "No project config available"}

        domain_config = self.project_config.get_domain(domain)
        if not domain_config:
            return {"error": f"Domain {domain} not found"}

        cmd_map = {
            "build": domain_config.get("build_cmd"),
            "test": domain_config.get("test_cmd"),
            "lint": domain_config.get("lint_cmd"),
        }

        cmd = cmd_map.get(command_type)
        if not cmd:
            return {"error": f"No {command_type} command configured for {domain}"}

        # Use global build queue to prevent CPU saturation (1 build at a time)
        try:
            from core.build_queue import GlobalBuildQueue

            queue = GlobalBuildQueue.instance()

            # Enqueue and wait for completion
            job_id = queue.enqueue(
                project=self.project_name or "unknown",
                cmd=cmd,
                cwd=str(self.project_root),
                timeout=300,
                priority=5,  # Lower priority than deploy builds
            )

            # Wait for job completion (async)
            import asyncio

            job = await queue.wait_for(job_id)

            return {
                "command": cmd,
                "returncode": 0 if job.status.value == "success" else 1,
                "stdout": (job.stdout or "")[:5000],
                "stderr": (job.stderr or "")[:2000],
                "queued": True,
                "job_id": job_id,
            }
        except (ImportError, Exception):
            # Fallback if build_queue not available - direct execution
            try:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return {
                    "command": cmd,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[:5000],
                    "stderr": proc.stderr[:2000],
                    "queued": False,
                }
            except subprocess.TimeoutExpired:
                return {"error": "Command timed out (300s)"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_context(self, args: Dict) -> Dict:
        """Get project context from RAG (ProjectContext)

        Returns vision, architecture, requirements, conventions, etc.
        Used by agents to understand project scope and avoid slop.
        """
        category = args.get("category", "all")
        max_chars = args.get("max_chars", 8000)

        if not self.project_config:
            return {"error": "No project config available"}

        try:
            from core.project_context import ProjectContext

            ctx = ProjectContext(self.project_name)

            # Refresh if stale
            if ctx.is_stale():
                ctx.refresh()

            if category == "all":
                # Return full summary
                summary = ctx.get_summary(max_chars=max_chars)
                return {
                    "project": self.project_name,
                    "context": summary,
                    "categories": [
                        "vision",
                        "architecture",
                        "data_model",
                        "api_surface",
                        "conventions",
                        "state",
                        "history",
                        "domain",
                    ],
                }
            else:
                # Return specific category
                cat_data = getattr(ctx, category, None)
                if cat_data:
                    return {
                        "project": self.project_name,
                        "category": category,
                        "content": cat_data.content[:max_chars]
                        if hasattr(cat_data, "content")
                        else str(cat_data)[:max_chars],
                        "keywords": cat_data.keywords
                        if hasattr(cat_data, "keywords")
                        else [],
                    }
                else:
                    return {"error": f"Category '{category}' not found"}
        except ImportError:
            return {"error": "ProjectContext not available"}
        except Exception as e:
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # Component Gallery tools (SQLite DB — 60 components, 2600+ implementations)
    # -------------------------------------------------------------------------
    _CG_DB_PATH = Path(__file__).parent.parent / "data" / "component_gallery.db"
    _CG_MD_DIR = (
        Path(__file__).parent.parent
        / "skills" / "knowledge" / "component-gallery"
        / "src" / "content" / "componentContent"
    )

    def _cg_db(self):
        """Open component gallery SQLite connection."""
        import sqlite3
        if not self._CG_DB_PATH.exists():
            return None
        conn = sqlite3.connect(str(self._CG_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    async def _tool_component_gallery_list(self, args: Dict) -> Dict:
        """List all 60 components from DB."""
        conn = self._cg_db()
        if not conn:
            return {"error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"}
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
                    "description": r["description"][:120] + "..." if len(r["description"] or "") > 120 else r["description"],
                    "aliases": r["aliases"],
                    "implementations": r["impl_count"],
                }
                for r in rows
            ],
        }

    async def _tool_component_gallery_get(self, args: Dict) -> Dict:
        """Get full component data from DB + optional static MD doc."""
        slug = args.get("component", "").lower().strip()
        tech_filter = args.get("tech", "").strip()
        limit = min(int(args.get("limit", 20)), 200)

        conn = self._cg_db()
        if not conn:
            return {"error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"}

        # Fuzzy slug match
        row = conn.execute("SELECT * FROM components WHERE slug = ?", (slug,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM components WHERE slug LIKE ? OR name LIKE ? LIMIT 1",
                (f"%{slug}%", f"%{slug}%")
            ).fetchone()
        if not row:
            available = [r[0] for r in conn.execute("SELECT slug FROM components ORDER BY slug")]
            conn.close()
            return {"error": f"Component '{slug}' not found", "available": available}

        real_slug = row["slug"]

        # Get implementations
        query = "SELECT component_name, ds_name, url, tech, features FROM implementations WHERE component_slug = ?"
        params: list = [real_slug]
        if tech_filter:
            query += " AND tech LIKE ?"
            params.append(f"%{tech_filter}%")
        query += f" ORDER BY ds_name LIMIT {limit}"
        impls = conn.execute(query, params).fetchall()
        total_impls = conn.execute(
            "SELECT COUNT(*) FROM implementations WHERE component_slug = ?", (real_slug,)
        ).fetchone()[0]
        conn.close()

        result: Dict = {
            "slug": real_slug,
            "name": row["name"],
            "description": row["description"],
            "aliases": row["aliases"],
            "source": f"https://component.gallery/components/{real_slug}/",
            "total_implementations": total_impls,
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

        # Append static MD doc if available
        md_file = self._CG_MD_DIR / f"{real_slug}.md"
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:].strip()
            result["docs"] = content

        return result

    async def _tool_component_gallery_search(self, args: Dict) -> Dict:
        """Full-text search across components."""
        query = args.get("query", "").strip()
        if not query:
            return {"error": "query is required"}

        conn = self._cg_db()
        if not conn:
            return {"error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"}

        try:
            rows = conn.execute(
                "SELECT slug, name, description, aliases FROM components_fts WHERE components_fts MATCH ? LIMIT 10",
                (query,)
            ).fetchall()
        except Exception:
            # Fallback to LIKE search
            rows = conn.execute(
                "SELECT slug, name, description, aliases FROM components "
                "WHERE slug LIKE ? OR name LIKE ? OR aliases LIKE ? OR description LIKE ? LIMIT 10",
                (f"%{query}%",) * 4
            ).fetchall()
        conn.close()

        return {
            "query": query,
            "count": len(rows),
            "results": [
                {"slug": r["slug"], "name": r["name"], "aliases": r["aliases"],
                 "description": (r["description"] or "")[:150]}
                for r in rows
            ],
        }

    async def _tool_component_gallery_ds(self, args: Dict) -> Dict:
        """Get all components from a specific Design System."""
        ds_name = args.get("ds_name", "").strip()
        if not ds_name:
            return {"error": "ds_name is required"}

        conn = self._cg_db()
        if not conn:
            return {"error": "Component Gallery DB not found. Run: python -m mcp_lrm.component_gallery_scraper"}

        rows = conn.execute(
            "SELECT component_slug, component_name, url, tech, features "
            "FROM implementations WHERE ds_name LIKE ? ORDER BY component_slug",
            (f"%{ds_name}%",)
        ).fetchall()

        if not rows:
            # List available DS names
            ds_list = [r[0] for r in conn.execute(
                "SELECT DISTINCT ds_name FROM implementations ORDER BY ds_name"
            ).fetchall()]
            conn.close()
            return {"error": f"Design system '{ds_name}' not found", "available_design_systems": ds_list}

        # Get actual DS name from first result
        actual_ds = conn.execute(
            "SELECT DISTINCT ds_name FROM implementations WHERE ds_name LIKE ? LIMIT 1",
            (f"%{ds_name}%",)
        ).fetchone()[0]
        conn.close()

        return {
            "design_system": actual_ds,
            "component_count": len(rows),
            "components": [
                {"component": r["component_slug"], "called": r["component_name"],
                 "url": r["url"], "tech": r["tech"]}
                for r in rows
            ],
        }

    async def run(self):
        """Run MCP server (stdio)"""
        print(
            f"MCP LRM Server starting (project: {self.project_name})", file=sys.stderr
        )

        while True:
            msg = await read_message()
            if msg is None:
                break

            method = msg.get("method")
            msg_id = msg.get("id")
            params = msg.get("params", {})

            if method == "initialize":
                write_message(
                    make_response(
                        msg_id,
                        {
                            "protocolVersion": "2024-11-05",
                            "serverInfo": {"name": "mcp-lrm", "version": "1.0.0"},
                            "capabilities": {"tools": {}},
                        },
                    )
                )

            elif method == "tools/list":
                write_message(make_response(msg_id, {"tools": self.get_tools()}))

            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self.handle_tool_call(name, arguments)
                write_message(
                    make_response(
                        msg_id,
                        {"content": [{"type": "text", "text": json.dumps(result)}]},
                    )
                )

            elif method == "notifications/initialized":
                pass  # No response needed

            else:
                if msg_id:
                    write_message(
                        make_error(msg_id, -32601, f"Method not found: {method}")
                    )


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP LRM Server")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--test", action="store_true", help="Run test")

    args = parser.parse_args()

    if args.test:
        # Test mode - run a sample tool call
        server = MCPLRMServer(args.project)
        result = asyncio.run(server._tool_conventions({"domain": "rust"}))
        print(json.dumps(result, indent=2))
    else:
        # Run as MCP server
        server = MCPLRMServer(args.project)
        asyncio.run(server.run())


if __name__ == "__main__":
    main()
