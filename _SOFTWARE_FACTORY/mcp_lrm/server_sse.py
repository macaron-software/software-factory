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
    subprocess.run([sys.executable, "-m", "pip", "install", "aiohttp", "aiohttp-sse"], check=True)
    from aiohttp import web
    from aiohttp_sse import sse_response

from mcp_lrm.exclusions import should_exclude_path, filter_paths, get_included_extensions


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
    except:
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
        r'(vitest\s+run)\b',
        rf'\1 {constraint}',
        cmd,
    )
    if constraint not in cmd:
        # Fallback: insert after 'vitest'
        cmd = re.sub(
            r'(vitest)\b',
            rf'\1 {constraint}',
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
        log(f"MCP LRM Server initialized")

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
                "name": "lrm_locate",
                "description": "Find files in project matching pattern or search query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (glob pattern or text)"},
                        "project": {"type": "string", "description": "Project name"},
                        "scope": {"type": "string", "description": "Scope: 'all', domain, or path prefix", "default": "all"},
                        "limit": {"type": "integer", "description": "Max results", "default": 20},
                    },
                    "required": ["query", "project"],
                },
            },
            {
                "name": "lrm_read",
                "description": "Read file content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path (relative to project root)"},
                        "project": {"type": "string", "description": "Project name"},
                        "lines": {"type": "integer", "description": "Max lines to read", "default": 500},
                    },
                    "required": ["path", "project"],
                },
            },
            {
                "name": "lrm_conventions",
                "description": "Get project conventions for a domain",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "Domain: rust, typescript, python, etc."},
                        "project": {"type": "string", "description": "Project name"},
                    },
                    "required": ["domain", "project"],
                },
            },
            {
                "name": "lrm_task_read",
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
                "name": "lrm_task_update",
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
                "name": "lrm_build",
                "description": "Run build or test command",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "Domain: rust, typescript, etc."},
                        "project": {"type": "string", "description": "Project name"},
                        "command": {"type": "string", "description": "Command: build, test, lint", "default": "build"},
                    },
                    "required": ["domain", "project"],
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: Dict) -> Any:
        """Handle a tool call"""
        try:
            if name == "lrm_locate":
                return await self._tool_locate(arguments)
            elif name == "lrm_read":
                return await self._tool_read(arguments)
            elif name == "lrm_conventions":
                return await self._tool_conventions(arguments)
            elif name == "lrm_task_read":
                return await self._tool_task_read(arguments)
            elif name == "lrm_task_update":
                return await self._tool_task_update(arguments)
            elif name == "lrm_build":
                return await self._tool_build(arguments)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            log(f"Tool {name} error: {e}", "ERROR")
            return {"error": str(e)}

    async def _tool_locate(self, args: Dict) -> Dict:
        """Find files matching pattern"""
        project = self.get_project(args.get("project"))
        if not project:
            return {"error": "Project not found"}

        query = args.get("query", "")
        scope = args.get("scope", "all")
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
                    capture_output=True, text=True, timeout=10
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
        if project and hasattr(project, 'config') and project.config:
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
                cmd, shell=True, cwd=str(project.root_path),
                capture_output=True, text=True, timeout=300
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout,
                "stderr": proc.stderr[-2000:] if len(proc.stderr) > 2000 else proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out (300s)"}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# HTTP/SSE HANDLERS
# ============================================================================

mcp_server = MCPLRMServer()


async def handle_health(request):
    """Health check endpoint"""
    return web.json_response({
        "status": "ok",
        "connections": len(mcp_server.active_connections),
        "projects_cached": len(mcp_server.projects),
    })


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
    log(f"SSE connection opened: {session_id} (total: {len(mcp_server.active_connections)})")

    try:
        async with sse_response(request) as resp:
            # Send initial connection message
            await resp.send(json.dumps({
                "jsonrpc": "2.0",
                "method": "connection/ready",
                "params": {"session_id": session_id}
            }))

            # Send tools list
            await resp.send(json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {"tools": mcp_server.get_tools()}
            }))

            # Keep connection alive and handle incoming messages
            while True:
                await asyncio.sleep(30)  # Heartbeat
                await resp.send(json.dumps({
                    "jsonrpc": "2.0",
                    "method": "heartbeat",
                    "params": {"session_id": session_id}
                }))

    except asyncio.CancelledError:
        pass
    finally:
        mcp_server.active_connections.discard(session_id)
        log(f"SSE connection closed: {session_id} (remaining: {len(mcp_server.active_connections)})")

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
    sys.stdin = open(os.devnull, 'r')
    sys.stdout = open(LOG_FILE, 'a')
    sys.stderr = open(LOG_FILE, 'a')


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
            with urllib.request.urlopen(f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/health", timeout=2) as resp:
                data = json.loads(resp.read())
                print(f"  Connections: {data.get('connections', 0)}")
                print(f"  Projects cached: {data.get('projects_cached', 0)}")
        except:
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
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "start", "stop", "status"],
                        help="Command: run (foreground), start (daemon), stop, status")
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
