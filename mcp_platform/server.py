#!/usr/bin/env python3
"""
MCP Platform Server - Software Factory Platform Control
=======================================================
Provides AI agents with full control over the Software Factory platform:
- Agents: list, get, create, update
- Projects: list, get, create, health, phase
- Missions: list, get, create, delete
- Sessions: list, get, create (run a task)
- Workflows: list
- Platform: status, metrics, reload agents
- ARTs: list teams and members

Connects directly to the local SQLite DB for reads (fast, no auth needed).
Calls the REST API for writes (proper validation + business logic).

Usage:
    python -m mcp_platform.server

    # With custom API URL
    SF_PLATFORM_URL=http://localhost:8099 python -m mcp_platform.server
"""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Config ───────────────────────────────────────────────────────────────────

PLATFORM_URL = os.environ.get("SF_PLATFORM_URL", "http://127.0.0.1:8099")
PLATFORM_API_KEY = os.environ.get("SF_PLATFORM_API_KEY", "")

# Direct DB path — same logic as platform/config.py
_FACTORY_ROOT = Path(
    os.environ.get(
        "FACTORY_ROOT", Path.home() / "_MACARON-SOFTWARE" / "_SOFTWARE_FACTORY"
    )
)
DB_PATH = _FACTORY_ROOT / "data" / "platform.db"
if not DB_PATH.exists():
    # Fallback: look for data/ next to mcp_platform/
    _alt = Path(__file__).parent.parent / "_SOFTWARE_FACTORY" / "data" / "platform.db"
    if _alt.exists():
        DB_PATH = _alt


# ─── JSON-RPC helpers ─────────────────────────────────────────────────────────


async def read_message() -> Optional[Dict]:
    try:
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return json.loads(line.strip())
    except (json.JSONDecodeError, OSError):
        return None


def write_message(msg: Dict):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def ok(id: Any, result: Any) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def err(id: Any, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


# ─── DB helpers ───────────────────────────────────────────────────────────────


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params=()) -> List[Dict]:
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return [{"error": str(e)}]


def _one(conn: sqlite3.Connection, sql: str, params=()) -> Optional[Dict]:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


# ─── HTTP helper for writes ────────────────────────────────────────────────────


async def _api(method: str, path: str, body: Dict = None) -> Dict:
    """Call the platform REST API."""
    try:
        import httpx

        headers = {"Content-Type": "application/json"}
        if PLATFORM_API_KEY:
            headers["X-API-Key"] = PLATFORM_API_KEY
        url = f"{PLATFORM_URL}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            if method == "GET":
                r = await client.get(url, headers=headers)
            elif method == "POST":
                r = await client.post(url, json=body or {}, headers=headers)
            elif method == "DELETE":
                r = await client.delete(url, headers=headers)
            elif method == "PATCH":
                r = await client.patch(url, json=body or {}, headers=headers)
            else:
                return {"error": f"Unknown method: {method}"}
            if r.status_code >= 400:
                return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
            try:
                return r.json()
            except Exception:
                return {"ok": True, "status": r.status_code}
    except Exception as e:
        return {"error": str(e)}


# ─── Tool implementations ─────────────────────────────────────────────────────


async def tool_platform_status(_: Dict) -> Dict:
    """Get overall platform status: counts, running missions, health."""
    conn = _db()
    try:
        agents = _one(conn, "SELECT COUNT(*) as n FROM agents")
        projects = _one(conn, "SELECT COUNT(*) as n FROM projects")
        missions_total = _one(conn, "SELECT COUNT(*) as n FROM missions")
        missions_running = _one(
            conn,
            "SELECT COUNT(*) as n FROM missions WHERE status IN ('active','running','pending')",
        )
        sessions = _one(
            conn,
            "SELECT COUNT(*) as n FROM sessions WHERE created_at > datetime('now','-24 hours')",
        )
        recent_missions = _rows(
            conn,
            "SELECT id, name as title, status, project_id, created_at FROM missions "
            "WHERE status IN ('active','running','pending') ORDER BY created_at DESC LIMIT 10",
        )
        return {
            "platform_url": PLATFORM_URL,
            "db_path": str(DB_PATH),
            "agents_total": agents["n"] if agents else 0,
            "projects_total": projects["n"] if projects else 0,
            "missions_total": missions_total["n"] if missions_total else 0,
            "missions_active": missions_running["n"] if missions_running else 0,
            "sessions_last_24h": sessions["n"] if sessions else 0,
            "active_missions": recent_missions,
        }
    finally:
        conn.close()


async def tool_list_agents(args: Dict) -> Dict:
    """List agents. Filters: role, art, safe_level, limit."""
    conn = _db()
    try:
        wheres, params = [], []
        if args.get("role"):
            wheres.append("role LIKE ?")
            params.append(f"%{args['role']}%")
        if args.get("art"):
            wheres.append("(tags LIKE ? OR name LIKE ?)")
            params.extend([f"%{args['art']}%", f"%{args['art']}%"])
        if args.get("safe_level"):
            wheres.append("hierarchy_rank=?")
            params.append(args["safe_level"])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        limit = min(int(args.get("limit", 50)), 200)
        rows = _rows(
            conn,
            f"SELECT id, name, role, hierarchy_rank as safe_level, tags_json as tags, color, model, created_at FROM agents {where_clause} ORDER BY name LIMIT ?",
            params + [limit],
        )
        return {"count": len(rows), "agents": rows}
    finally:
        conn.close()


async def tool_get_agent(args: Dict) -> Dict:
    """Get full details for one agent by id or name."""
    conn = _db()
    try:
        agent_id = args.get("agent_id", "")
        row = _one(conn, "SELECT * FROM agents WHERE id=?", (agent_id,))
        if not row:
            row = _one(
                conn,
                "SELECT * FROM agents WHERE name LIKE ? LIMIT 1",
                (f"%{agent_id}%",),
            )
        if not row:
            return {"error": f"Agent '{agent_id}' not found"}
        # Recent sessions
        sessions = _rows(
            conn,
            "SELECT id, title, status, created_at FROM sessions WHERE agent_id=? ORDER BY created_at DESC LIMIT 5",
            (row["id"],),
        )
        return {**row, "recent_sessions": sessions}
    finally:
        conn.close()


async def tool_create_agent(args: Dict) -> Dict:
    """Create a new agent. Required: name, role. Optional: safe_level, tags, color, model, tagline."""
    required = ["name", "role"]
    for f in required:
        if not args.get(f):
            return {"error": f"Missing required field: {f}"}
    body = {
        "name": args["name"],
        "role": args["role"],
        "safe_level": args.get("safe_level", "team"),
        "tags": args.get("tags", ""),
        "color": args.get("color", "#8b5cf6"),
        "model": args.get("model", ""),
        "tagline": args.get("tagline", ""),
    }
    return await _api("POST", "/api/agents", body)


async def tool_list_projects(args: Dict) -> Dict:
    """List projects. Optional filter: status."""
    conn = _db()
    try:
        status = args.get("status")
        if status:
            rows = _rows(
                conn,
                "SELECT id, name, description, factory_type as type, status, created_at FROM projects WHERE status=? ORDER BY name",
                (status,),
            )
        else:
            rows = _rows(
                conn,
                "SELECT id, name, description, factory_type as type, status, created_at FROM projects ORDER BY name",
            )
        return {"count": len(rows), "projects": rows}
    finally:
        conn.close()


async def tool_get_project(args: Dict) -> Dict:
    """Get project details including recent missions and health."""
    conn = _db()
    try:
        pid = args.get("project_id", "")
        row = _one(conn, "SELECT * FROM projects WHERE id=?", (pid,))
        if not row:
            row = _one(
                conn, "SELECT * FROM projects WHERE name LIKE ? LIMIT 1", (f"%{pid}%",)
            )
        if not row:
            return {"error": f"Project '{pid}' not found"}
        missions = _rows(
            conn,
            "SELECT id, name as title, status, created_at FROM missions WHERE project_id=? ORDER BY created_at DESC LIMIT 10",
            (row["id"],),
        )
        return {**row, "recent_missions": missions, "mission_count": len(missions)}
    finally:
        conn.close()


async def tool_create_project(args: Dict) -> Dict:
    """Create a new project. Required: name. Optional: description, art, domain."""
    if not args.get("name"):
        return {"error": "Missing required field: name"}
    body = {
        "name": args["name"],
        "description": args.get("description", ""),
        "art": args.get("art", ""),
        "domain": args.get("domain", ""),
    }
    return await _api("POST", "/api/projects", body)


async def tool_get_project_health(args: Dict) -> Dict:
    """Get project health metrics: phase gates, mission completion rates."""
    pid = args.get("project_id", "")
    result = await _api("GET", f"/api/projects/{pid}/health")
    if "error" not in result:
        return result
    # Fallback: direct DB query
    conn = _db()
    try:
        row = _one(
            conn,
            "SELECT id, name, factory_type as type, status FROM projects WHERE id=?",
            (pid,),
        )
        if not row:
            return {"error": f"Project '{pid}' not found"}
        mission_stats = _rows(
            conn,
            "SELECT status, COUNT(*) as cnt FROM missions WHERE project_id=? GROUP BY status",
            (pid,),
        )
        return {**row, "mission_stats": mission_stats}
    finally:
        conn.close()


async def tool_list_missions(args: Dict) -> Dict:
    """List missions. Filters: project_id, status, limit."""
    conn = _db()
    try:
        wheres, params = [], []
        if args.get("project_id"):
            wheres.append("project_id=?")
            params.append(args["project_id"])
        if args.get("status"):
            wheres.append("status=?")
            params.append(args["status"])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        limit = min(int(args.get("limit", 20)), 100)
        rows = _rows(
            conn,
            f"SELECT id, name as title, status, project_id, workflow_id, created_at FROM missions {where_clause} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        return {"count": len(rows), "missions": rows}
    finally:
        conn.close()


async def tool_get_mission(args: Dict) -> Dict:
    """Get mission details including phases and recent runs."""
    conn = _db()
    try:
        mid = args.get("mission_id", "")
        row = _one(conn, "SELECT * FROM missions WHERE id=?", (mid,))
        if not row:
            return {"error": f"Mission '{mid}' not found"}
        runs = _rows(
            conn,
            "SELECT id, workflow_id, status, current_phase, phases_json, created_at, completed_at FROM mission_runs WHERE parent_mission_id=? ORDER BY created_at DESC LIMIT 5",
            (mid,),
        )
        return {**row, "runs": runs}
    finally:
        conn.close()


async def tool_create_mission(args: Dict) -> Dict:
    """Create a new mission. Required: title, project_id. Optional: workflow_id, description, agent_ids."""
    required = ["title", "project_id"]
    for f in required:
        if not args.get(f):
            return {"error": f"Missing required field: {f}"}
    body = {
        "title": args["title"],
        "project_id": args["project_id"],
        "workflow_id": args.get("workflow_id", ""),
        "description": args.get("description", ""),
        "agent_ids": args.get("agent_ids", []),
    }
    return await _api("POST", "/api/missions", body)


async def tool_delete_mission(args: Dict) -> Dict:
    """Delete a mission by id."""
    mid = args.get("mission_id", "")
    if not mid:
        return {"error": "Missing mission_id"}
    return await _api("DELETE", f"/api/missions/{mid}")


async def tool_list_sessions(args: Dict) -> Dict:
    """List agent sessions. Filters: agent_id, status, project_id, limit."""
    conn = _db()
    try:
        wheres, params = [], []
        if args.get("agent_id"):
            wheres.append("config_json LIKE ?")
            params.append(f"%{args['agent_id']}%")
        if args.get("status"):
            wheres.append("status=?")
            params.append(args["status"])
        if args.get("project_id"):
            wheres.append("project_id=?")
            params.append(args["project_id"])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        limit = min(int(args.get("limit", 20)), 100)
        rows = _rows(
            conn,
            f"SELECT id, name as title, status, project_id, created_at FROM sessions {where_clause} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        return {"count": len(rows), "sessions": rows}
    finally:
        conn.close()


async def tool_get_session(args: Dict) -> Dict:
    """Get session details including messages."""
    conn = _db()
    try:
        sid = args.get("session_id", "")
        row = _one(conn, "SELECT * FROM sessions WHERE id=?", (sid,))
        if not row:
            return {"error": f"Session '{sid}' not found"}
        messages = _rows(
            conn,
            "SELECT message_type as role, content, from_agent, timestamp as created_at FROM messages WHERE session_id=? ORDER BY timestamp LIMIT 50",
            (sid,),
        )
        return {**row, "messages": messages}
    finally:
        conn.close()


async def tool_create_session(args: Dict) -> Dict:
    """Create and start an agent session (run a task). Required: agent_id, message. Optional: project_id, title."""
    required = ["agent_id", "message"]
    for f in required:
        if not args.get(f):
            return {"error": f"Missing required field: {f}"}
    body = {
        "agent_id": args["agent_id"],
        "message": args["message"],
        "project_id": args.get("project_id", ""),
        "title": args.get("title", args["message"][:60]),
    }
    return await _api("POST", "/api/sessions", body)


async def tool_list_workflows(args: Dict) -> Dict:
    """List available workflows. Optional filter: category."""
    conn = _db()
    try:
        rows = _rows(
            conn,
            "SELECT id, name, description, phases_json as phases FROM workflows ORDER BY name",
        )
        return {"count": len(rows), "workflows": rows}
    finally:
        conn.close()


async def tool_list_arts(args: Dict) -> Dict:
    """List ARTs (Agile Release Trains) and their agent teams."""
    conn = _db()
    try:
        # ARTs are stored as tags/safe_level on agents
        arts = _rows(
            conn,
            "SELECT DISTINCT factory_type as art FROM projects WHERE factory_type IS NOT NULL ORDER BY factory_type",
        )
        result = []
        for art_row in arts:
            art = art_row["art"]
            members = _rows(
                conn,
                "SELECT id, name, role, hierarchy_rank as safe_level FROM agents WHERE tags_json LIKE ? ORDER BY safe_level, name",
                (f"%{art}%",),
            )
            proj_count = _one(
                conn, "SELECT COUNT(*) as n FROM projects WHERE factory_type=?", (art,)
            )
            result.append(
                {
                    "art": art,
                    "project_count": proj_count["n"] if proj_count else 0,
                    "agent_count": len(members),
                    "agents": members[:20],
                }
            )
        # Also return agents by safe_level as a proxy for team structure
        safe_levels = _rows(
            conn,
            "SELECT hierarchy_rank as safe_level, COUNT(*) as cnt FROM agents GROUP BY hierarchy_rank ORDER BY cnt DESC",
        )
        return {"arts": result, "agents_by_safe_level": safe_levels}
    finally:
        conn.close()


async def tool_get_metrics(args: Dict) -> Dict:
    """Get LLM usage metrics. Optional: hours (default 24)."""
    hours = int(args.get("hours", 24))
    result = await _api("GET", f"/api/metrics/llm?hours={hours}")
    if "error" not in result:
        return result
    # Fallback: direct DB
    conn = _db()
    try:
        stats = _rows(
            conn,
            "SELECT provider, model, COUNT(*) as calls, SUM(tokens_in+tokens_out) as total_tokens, "
            "SUM(cost_usd) as total_cost FROM llm_traces "
            "WHERE created_at > datetime('now', ?) GROUP BY provider, model ORDER BY total_cost DESC",
            (f"-{hours} hours",),
        )
        return {"period_hours": hours, "provider_stats": stats}
    finally:
        conn.close()


async def tool_reload_agents(_: Dict) -> Dict:
    """Hot-reload agents from YAML definitions without restarting the server."""
    return await _api("POST", "/api/admin/reload-agents")


async def tool_search(args: Dict) -> Dict:
    """Full-text search across agents, projects, missions by keyword."""
    q = args.get("query", "")
    if not q:
        return {"error": "Missing query"}
    conn = _db()
    try:
        like = f"%{q}%"
        agents = _rows(
            conn,
            "SELECT id, name, role, 'agent' as type FROM agents WHERE name LIKE ? OR role LIKE ? OR tags LIKE ? LIMIT 10",
            (like, like, like),
        )
        projects = _rows(
            conn,
            "SELECT id, name, description, 'project' as type FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 10",
            (like, like),
        )
        missions = _rows(
            conn,
            "SELECT id, title, status, 'mission' as type FROM missions WHERE title LIKE ? LIMIT 10",
            (like,),
        )
        return {
            "query": q,
            "agents": agents,
            "projects": projects,
            "missions": missions,
            "total": len(agents) + len(projects) + len(missions),
        }
    finally:
        conn.close()


# ─── Tool registry ────────────────────────────────────────────────────────────

TOOLS = {
    "sf_platform_status": tool_platform_status,
    "sf_list_agents": tool_list_agents,
    "sf_get_agent": tool_get_agent,
    "sf_create_agent": tool_create_agent,
    "sf_list_projects": tool_list_projects,
    "sf_get_project": tool_get_project,
    "sf_create_project": tool_create_project,
    "sf_get_project_health": tool_get_project_health,
    "sf_list_missions": tool_list_missions,
    "sf_get_mission": tool_get_mission,
    "sf_create_mission": tool_create_mission,
    "sf_delete_mission": tool_delete_mission,
    "sf_list_sessions": tool_list_sessions,
    "sf_get_session": tool_get_session,
    "sf_create_session": tool_create_session,
    "sf_list_workflows": tool_list_workflows,
    "sf_list_arts": tool_list_arts,
    "sf_get_metrics": tool_get_metrics,
    "sf_reload_agents": tool_reload_agents,
    "sf_search": tool_search,
}

TOOL_SCHEMAS = [
    {
        "name": "sf_platform_status",
        "description": "Get overall Software Factory status: agent count, active missions, sessions in last 24h.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sf_list_agents",
        "description": "List agents with optional filters. Returns id, name, role, safe_level, tags, color.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "Filter by role (partial match)",
                },
                "art": {"type": "string", "description": "Filter by ART/team name"},
                "safe_level": {
                    "type": "string",
                    "description": "Filter: epic, capability, feature, story, task, team",
                },
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
        },
    },
    {
        "name": "sf_get_agent",
        "description": "Get full details for one agent including recent sessions. Pass id or partial name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent id or partial name",
                }
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "sf_create_agent",
        "description": "Create a new agent in the platform.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "safe_level": {
                    "type": "string",
                    "description": "epic|capability|feature|story|task|team",
                },
                "tags": {"type": "string", "description": "Comma-separated tags"},
                "color": {"type": "string", "description": "Hex color e.g. #8b5cf6"},
                "model": {"type": "string"},
                "tagline": {"type": "string"},
            },
            "required": ["name", "role"],
        },
    },
    {
        "name": "sf_list_projects",
        "description": "List all projects. Optional status filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter: active, paused, completed, archived",
                }
            },
        },
    },
    {
        "name": "sf_get_project",
        "description": "Get project details including recent missions. Pass id or partial name.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "sf_create_project",
        "description": "Create a new project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "art": {
                    "type": "string",
                    "description": "ART name (Agile Release Train)",
                },
                "domain": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "sf_get_project_health",
        "description": "Get project health: phase gate status and mission completion rates.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "sf_list_missions",
        "description": "List missions with filters. Status: running, pending, completed, paused, failed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "sf_get_mission",
        "description": "Get mission details: phases, runs, cost, tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {"mission_id": {"type": "string"}},
            "required": ["mission_id"],
        },
    },
    {
        "name": "sf_create_mission",
        "description": "Create a new mission for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "project_id": {"type": "string"},
                "workflow_id": {"type": "string"},
                "description": {"type": "string"},
                "agent_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "project_id"],
        },
    },
    {
        "name": "sf_delete_mission",
        "description": "Delete a mission by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"mission_id": {"type": "string"}},
            "required": ["mission_id"],
        },
    },
    {
        "name": "sf_list_sessions",
        "description": "List agent chat sessions. Filter by agent, status, or project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "status": {"type": "string"},
                "project_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "sf_get_session",
        "description": "Get session details and messages (up to 50 last messages).",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    {
        "name": "sf_create_session",
        "description": "Create and start an agent session — run a task/question with a specific agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "message": {
                    "type": "string",
                    "description": "The task or question to send to the agent",
                },
                "project_id": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["agent_id", "message"],
        },
    },
    {
        "name": "sf_list_workflows",
        "description": "List available automation workflows. Optional category filter.",
        "inputSchema": {
            "type": "object",
            "properties": {"category": {"type": "string"}},
        },
    },
    {
        "name": "sf_list_arts",
        "description": "List Agile Release Trains and their agent members, grouped by project and safe_level.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sf_get_metrics",
        "description": "Get LLM usage metrics: calls, tokens, cost per provider/model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Look-back period in hours (default 24)",
                }
            },
        },
    },
    {
        "name": "sf_reload_agents",
        "description": "Hot-reload agents from YAML skill definitions without restarting the server.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sf_search",
        "description": "Full-text search across agents, projects and missions by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


# ─── MCP Server ───────────────────────────────────────────────────────────────


async def run():
    print("MCP Platform Server starting", file=sys.stderr)
    print(f"  DB: {DB_PATH}", file=sys.stderr)
    print(f"  API: {PLATFORM_URL}", file=sys.stderr)
    print(f"  Tools: {len(TOOLS)}", file=sys.stderr)

    while True:
        msg = await read_message()
        if msg is None:
            break

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            write_message(
                ok(
                    msg_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "mcp-platform", "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    },
                )
            )

        elif method == "tools/list":
            write_message(ok(msg_id, {"tools": TOOL_SCHEMAS}))

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            handler = TOOLS.get(name)
            if handler is None:
                write_message(err(msg_id, -32601, f"Unknown tool: {name}"))
            else:
                try:
                    result = await handler(arguments)
                    write_message(
                        ok(
                            msg_id,
                            {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            result, default=str, indent=2
                                        ),
                                    }
                                ]
                            },
                        )
                    )
                except Exception as e:
                    write_message(
                        ok(
                            msg_id,
                            {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps({"error": str(e)}),
                                    }
                                ]
                            },
                        )
                    )

        elif method == "notifications/initialized":
            pass  # No response needed


def main():
    if "--test" in sys.argv:

        async def _test():
            print("=== sf_platform_status ===")
            r = await tool_platform_status({})
            print(json.dumps(r, default=str, indent=2))
            print("\n=== sf_list_agents (limit=5) ===")
            r = await tool_list_agents({"limit": 5})
            print(json.dumps(r, default=str, indent=2))
            print("\n=== sf_list_workflows ===")
            r = await tool_list_workflows({})
            print(json.dumps(r, default=str, indent=2)[:800])

        asyncio.run(_test())
    else:
        asyncio.run(run())


if __name__ == "__main__":
    main()
