#!/usr/bin/env python3
"""
MCP Platform Server — Internal Platform Tools via SSE
=====================================================
Exposes platform stores (agents, sessions, missions, memory, git)
as MCP tools for any MCP-compatible client.

Port: 9501 (next to LRM on 9500)

Tools:
  platform_agents        — list/get agents with status
  platform_phases        — list/get mission phases
  platform_missions      — list/get missions
  platform_messages      — get agent conversations
  platform_memory        — search project/global memory
  platform_git           — log/status/diff on workspace
  platform_code          — read/search files in workspace
  platform_metrics       — DB stats (tasks, agents, phases)

Usage:
    python -m platform.mcp_platform.server
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from aiohttp import web
    from aiohttp_sse import sse_response
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "aiohttp", "aiohttp-sse"], check=True)
    from aiohttp import web
    from aiohttp_sse import sse_response

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("MCP_PLATFORM_PORT", "9501"))
HOST = "127.0.0.1"
PID_FILE = Path("/tmp/factory/mcp-platform.pid")
FACTORY_ROOT = Path(__file__).parent.parent.parent
DB_PATH = FACTORY_ROOT / "data" / "platform.db"

_log_file = FACTORY_ROOT / "data" / "logs" / "mcp-platform.log"


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [MCP-PLATFORM] [{level}] {msg}"
    print(line, file=sys.stderr)
    try:
        _log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_log_file, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Lazy store accessors (import platform modules only when needed)
# ---------------------------------------------------------------------------
_stores: dict = {}


def _agent_store():
    if "agent" not in _stores:
        from platform.agents.store import get_agent_store
        _stores["agent"] = get_agent_store()
    return _stores["agent"]


def _session_store():
    if "session" not in _stores:
        from platform.sessions.store import get_session_store
        _stores["session"] = get_session_store()
    return _stores["session"]


def _mission_store():
    if "mission" not in _stores:
        from platform.missions.store import get_mission_run_store
        _stores["mission"] = get_mission_run_store()
    return _stores["mission"]


def _memory_manager():
    if "memory" not in _stores:
        from platform.memory.manager import get_memory_manager
        _stores["memory"] = get_memory_manager()
    return _stores["memory"]


def _workflow_store():
    if "workflow" not in _stores:
        from platform.workflows.store import get_workflow_store
        _stores["workflow"] = get_workflow_store()
    return _stores["workflow"]


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI-compatible function schemas)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "platform_agents",
        "description": "List all agents or get details of one agent. Returns id, name, role, status, model, skills, tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Optional agent ID to get details. Omit to list all."},
            },
        },
    },
    {
        "name": "platform_missions",
        "description": "List all missions or get details of one mission including phase statuses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mission_id": {"type": "string", "description": "Optional mission ID. Omit to list all."},
            },
        },
    },
    {
        "name": "platform_phases",
        "description": "Get phase statuses for a mission. Returns phase_id, status, pattern, agents involved.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mission_id": {"type": "string", "description": "Mission ID (required)"},
            },
            "required": ["mission_id"],
        },
    },
    {
        "name": "platform_messages",
        "description": "Get agent conversations from a session. Returns from_agent, to_agent, content, timestamp.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID (required)"},
                "limit": {"type": "integer", "description": "Max messages (default 30)"},
                "from_agent": {"type": "string", "description": "Filter by sender agent ID"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "platform_memory",
        "description": "Search platform memory (project or global). Returns key, value, category, confidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (FTS5)"},
                "project_id": {"type": "string", "description": "Project/mission ID. Omit for global memory."},
                "category": {"type": "string", "description": "Filter by category (architecture, vision, team, process, backlog)"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "platform_git",
        "description": "Run git commands on a workspace (log, status, diff, show).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "enum": ["log", "status", "diff", "show", "branch"], "description": "Git subcommand"},
                "workspace": {"type": "string", "description": "Workspace path (required)"},
                "args": {"type": "string", "description": "Extra args (e.g. '--oneline -20' for log, commit SHA for show)"},
            },
            "required": ["command", "workspace"],
        },
    },
    {
        "name": "platform_code",
        "description": "Read or search code files in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "search", "list"], "description": "read=file content, search=grep, list=directory listing"},
                "workspace": {"type": "string", "description": "Workspace root path (required)"},
                "path": {"type": "string", "description": "File path (for read) or subdir (for list)"},
                "pattern": {"type": "string", "description": "Search pattern (for search)"},
                "glob": {"type": "string", "description": "File glob filter for search (e.g. '*.swift')"},
            },
            "required": ["action", "workspace"],
        },
    },
    {
        "name": "platform_metrics",
        "description": "Get platform metrics: agent count, mission count, phase success rate, memory entries, message count.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def handle_tool(name: str, args: dict) -> str:
    try:
        if name == "platform_agents":
            return _handle_agents(args)
        elif name == "platform_missions":
            return _handle_missions(args)
        elif name == "platform_phases":
            return _handle_phases(args)
        elif name == "platform_messages":
            return _handle_messages(args)
        elif name == "platform_memory":
            return _handle_memory(args)
        elif name == "platform_git":
            return await _handle_git(args)
        elif name == "platform_code":
            return await _handle_code(args)
        elif name == "platform_metrics":
            return _handle_metrics(args)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:
        log(f"Tool {name} error: {exc}", "ERROR")
        return json.dumps({"error": str(exc)[:500]})


def _handle_agents(args: dict) -> str:
    store = _agent_store()
    agent_id = args.get("agent_id")
    if agent_id:
        a = store.get(agent_id)
        if not a:
            return json.dumps({"error": f"Agent {agent_id} not found"})
        return json.dumps({
            "id": a.id, "name": a.name, "role": a.role,
            "model": a.model, "provider": a.provider,
            "skills": a.skills[:10] if a.skills else [],
            "tools": a.tools[:10] if a.tools else [],
            "persona": (a.persona or "")[:300],
            "tagline": getattr(a, "tagline", ""),
            "motivation": getattr(a, "motivation", ""),
        })
    agents = store.list_all()
    return json.dumps([{
        "id": a.id, "name": a.name, "role": a.role,
        "model": a.model, "provider": a.provider,
        "skills_count": len(a.skills) if a.skills else 0,
        "tools_count": len(a.tools) if a.tools else 0,
    } for a in agents])


def _handle_missions(args: dict) -> str:
    store = _mission_store()
    mission_id = args.get("mission_id")
    if mission_id:
        m = store.get(mission_id)
        if not m:
            return json.dumps({"error": f"Mission {mission_id} not found"})
        phases = []
        if m.phases:
            for p in m.phases:
                phases.append({
                    "phase_id": p.phase_id,
                    "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                    "result": (p.result or "")[:200] if hasattr(p, "result") else "",
                })
        return json.dumps({
            "id": m.id, "brief": (m.brief or "")[:500],
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "workflow_id": m.workflow_id,
            "session_id": m.session_id,
            "workspace_path": m.workspace_path,
            "phases": phases,
        })
    # List all — query DB directly for efficiency
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id, brief, status, workflow_id, session_id FROM mission_runs ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return json.dumps([{
        "id": r[0], "brief": (r[1] or "")[:100], "status": r[2],
        "workflow_id": r[3], "session_id": r[4],
    } for r in rows])


def _handle_phases(args: dict) -> str:
    store = _mission_store()
    mission_id = args.get("mission_id", "")
    m = store.get(mission_id)
    if not m:
        return json.dumps({"error": f"Mission {mission_id} not found"})
    phases = []
    if m.phases:
        for p in m.phases:
            phases.append({
                "phase_id": p.phase_id,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "pattern": getattr(p, "pattern_id", ""),
                "result": (p.result or "")[:300] if hasattr(p, "result") else "",
            })
    return json.dumps({"mission_id": mission_id, "phases": phases})


def _handle_messages(args: dict) -> str:
    store = _session_store()
    session_id = args.get("session_id", "")
    limit = int(args.get("limit", 30))
    from_agent = args.get("from_agent")

    msgs = store.get_messages(session_id, limit=limit)
    result = []
    for m in msgs:
        if from_agent and m.from_agent != from_agent:
            continue
        result.append({
            "from": m.from_agent, "to": m.to_agent,
            "type": m.message_type,
            "content": (m.content or "")[:500],
            "created_at": m.created_at if hasattr(m, "created_at") else "",
        })
    return json.dumps(result)


def _handle_memory(args: dict) -> str:
    mem = _memory_manager()
    query = args.get("query", "")
    project_id = args.get("project_id")
    category = args.get("category")
    limit = int(args.get("limit", 20))

    if query:
        entries = mem.search(query, limit=limit)
    elif project_id:
        entries = mem.project_get(project_id, category=category, limit=limit)
    else:
        entries = mem.global_get(category=category, limit=limit)

    return json.dumps(entries[:limit], default=str)


async def _handle_git(args: dict) -> str:
    workspace = args.get("workspace", "")
    if not workspace or not Path(workspace).is_dir():
        return json.dumps({"error": f"Workspace not found: {workspace}"})

    cmd_map = {
        "log": "git --no-pager log --oneline -20",
        "status": "git --no-pager status --short",
        "diff": "git --no-pager diff --stat",
        "show": "git --no-pager show --stat",
        "branch": "git --no-pager branch -a",
    }
    command = args.get("command", "status")
    base_cmd = cmd_map.get(command, f"git --no-pager {command}")
    extra = args.get("args", "")
    if extra:
        base_cmd += f" {extra}"

    try:
        proc = await asyncio.create_subprocess_shell(
            base_cmd, cwd=workspace,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode(errors="replace")[:3000]
        if proc.returncode != 0:
            output += "\n" + stderr.decode(errors="replace")[:500]
        return output
    except asyncio.TimeoutError:
        return json.dumps({"error": "git command timed out"})


async def _handle_code(args: dict) -> str:
    workspace = args.get("workspace", "")
    if not workspace or not Path(workspace).is_dir():
        return json.dumps({"error": f"Workspace not found: {workspace}"})

    action = args.get("action", "list")
    ws = Path(workspace)

    if action == "read":
        fpath = args.get("path", "")
        target = ws / fpath if fpath else ws
        if not target.is_file():
            return json.dumps({"error": f"File not found: {fpath}"})
        try:
            content = target.read_text(errors="replace")[:5000]
            return content
        except Exception as e:
            return json.dumps({"error": str(e)})

    elif action == "search":
        pattern = args.get("pattern", "")
        glob_filter = args.get("glob", "")
        cmd = f"rg --no-heading -n '{pattern}' --max-count 5"
        if glob_filter:
            cmd += f" --glob '{glob_filter}'"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, cwd=workspace,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return stdout.decode(errors="replace")[:3000] or "(no matches)"
        except asyncio.TimeoutError:
            return "(search timed out)"

    elif action == "list":
        subdir = args.get("path", "")
        target = ws / subdir if subdir else ws
        if not target.is_dir():
            return json.dumps({"error": f"Not a directory: {subdir}"})
        entries = []
        for p in sorted(target.iterdir()):
            if p.name.startswith("."):
                continue
            entries.append({
                "name": p.name,
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return json.dumps(entries[:100])

    return json.dumps({"error": f"Unknown action: {action}"})


def _handle_metrics(args: dict) -> str:
    import sqlite3
    if not DB_PATH.exists():
        return json.dumps({"error": "platform.db not found"})
    conn = sqlite3.connect(str(DB_PATH))
    try:
        agents_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    except Exception:
        agents_count = 0
    try:
        missions_count = conn.execute("SELECT COUNT(*) FROM mission_runs").fetchone()[0]
    except Exception:
        missions_count = 0
    try:
        sessions_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    except Exception:
        sessions_count = 0
    try:
        messages_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    except Exception:
        messages_count = 0
    try:
        memory_count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    except Exception:
        memory_count = 0
    conn.close()
    return json.dumps({
        "agents": agents_count,
        "missions": missions_count,
        "sessions": sessions_count,
        "messages": messages_count,
        "memory_entries": memory_count,
    })


# ---------------------------------------------------------------------------
# MCP SSE transport (same pattern as mcp_lrm/server_sse.py)
# ---------------------------------------------------------------------------
_sessions: dict[str, asyncio.Queue] = {}


async def handle_sse(request: web.Request):
    """SSE endpoint — MCP session."""
    session_id = str(uuid.uuid4())[:8]
    queue: asyncio.Queue = asyncio.Queue()
    _sessions[session_id] = queue
    log(f"SSE session {session_id} connected")

    async with sse_response(request) as resp:
        # Send session init with endpoint URI
        await resp.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "session/init",
            "params": {"sessionId": session_id, "endpoint": f"/message?session_id={session_id}"},
        }))
        try:
            while True:
                msg = await asyncio.wait_for(queue.get(), timeout=300)
                await resp.send(msg)
        except (asyncio.TimeoutError, asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            _sessions.pop(session_id, None)
            log(f"SSE session {session_id} disconnected")

    return resp


async def handle_message(request: web.Request):
    """Handle JSON-RPC messages from MCP client."""
    session_id = request.query.get("session_id", "")
    queue = _sessions.get(session_id)

    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        response = {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mcp-platform", "version": "1.0.0"},
            },
        }
    elif method == "tools/list":
        response = {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": TOOLS},
        }
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        log(f"Tool call: {tool_name}({json.dumps(tool_args)[:200]})")
        result = await handle_tool(tool_name, tool_args)
        response = {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": result}]},
        }
    elif method == "notifications/initialized":
        return web.Response(status=200)
    else:
        response = {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

    # If SSE session, push via queue; else return directly
    if queue:
        await queue.put(json.dumps(response))
        return web.Response(status=202)
    else:
        return web.json_response(response)


async def handle_health(request: web.Request):
    return web.json_response({"status": "ok", "tools": len(TOOLS), "sessions": len(_sessions)})


async def handle_tools_list(request: web.Request):
    """REST endpoint for quick tool listing."""
    return web.json_response({"tools": [t["name"] for t in TOOLS]})


async def handle_tool_call(request: web.Request):
    """REST endpoint for direct tool calls (no SSE needed)."""
    body = await request.json()
    name = body.get("name", "")
    args = body.get("arguments", body.get("args", {}))
    result = await handle_tool(name, args)
    try:
        parsed = json.loads(result)
        return web.json_response(parsed)
    except (json.JSONDecodeError, TypeError):
        return web.json_response({"result": result})


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/sse", handle_sse)
    app.router.add_post("/message", handle_message)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/tools", handle_tools_list)
    app.router.add_post("/tool", handle_tool_call)
    return app


def main():
    log(f"Starting MCP Platform Server on {HOST}:{PORT}")
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    app = create_app()
    try:
        web.run_app(app, host=HOST, port=PORT, print=lambda msg: log(msg))
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
