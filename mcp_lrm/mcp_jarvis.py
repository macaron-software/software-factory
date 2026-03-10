#!/usr/bin/env python3
"""
MCP Jarvis — stdio MCP server bridging Claude/Copilot/OpenCode → Jarvis A2A
=============================================================================
Exposes Jarvis (strat-cto, Software Factory) as MCP tools.
Any MCP client (Claude Code, GitHub Copilot, OpenCode) can delegate tasks
to Jarvis via the A2A REST API at https://sf.macaron-software.com

Tools:
  jarvis_ask(message)          → submit task, stream result
  jarvis_status(task_id)       → get task status/result
  jarvis_task_list()           → list recent tasks

Auth: SF session cookie auto-refreshed via /api/auth/demo endpoint.
"""

import json
import sys
import time
import urllib.request
import urllib.error
import http.cookiejar
from typing import Optional, Dict

# ── Config ────────────────────────────────────────────────────────────────────
SF_BASE = "https://sf.macaron-software.com"
# Cookie jar persisted for session re-use
_cookiejar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookiejar))
_authed = False


# ── Auth ──────────────────────────────────────────────────────────────────────


def _ensure_auth():
    global _authed
    if _authed:
        return
    try:
        req = urllib.request.Request(
            f"{SF_BASE}/api/auth/demo",
            data=b"",
            method="POST",
        )
        _opener.open(req, timeout=10)
        _authed = True
    except Exception as e:
        sys.stderr.write(f"[mcp-jarvis] auth failed: {e}\n")


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _post(path: str, body: dict) -> dict:
    _ensure_auth()
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SF_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _opener.open(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "status": e.code}
    except Exception as e:
        return {"error": str(e)}


def _get(path: str) -> dict:
    _ensure_auth()
    req = urllib.request.Request(f"{SF_BASE}{path}")
    try:
        with _opener.open(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "status": e.code}
    except Exception as e:
        return {"error": str(e)}


def _submit_and_wait(message: str, timeout_s: int = 120) -> str:
    """Submit task to Jarvis and poll until completed."""
    task = _post(
        "/a2a/tasks", {"input": {"parts": [{"kind": "text", "text": message}]}}
    )
    if "error" in task and "id" not in task:
        return f"Error submitting task: {task.get('error')}"

    task_id = task.get("id", "")
    if not task_id:
        return f"No task ID returned: {json.dumps(task)}"

    # Poll for completion
    deadline = time.time() + timeout_s
    last_state = "submitted"
    while time.time() < deadline:
        result = _get(f"/a2a/tasks/{task_id}")
        state = result.get("status", {}).get("state", "unknown")
        if state != last_state:
            last_state = state
        if state in ("completed", "failed", "canceled"):
            output_parts = (result.get("output") or {}).get("parts") or []
            text = next(
                (p.get("text", "") for p in output_parts if p.get("kind") == "text"), ""
            )
            meta = result.get("metadata") or {}
            footer = ""
            if meta.get("model"):
                footer = f"\n\n---\n*model: {meta['model']} · provider: {meta.get('provider', '')} · {meta.get('tokens_out', 0)} tokens out*"
            if state == "failed":
                return f"❌ Task failed: {text or 'No output'}"
            return (text or "✅ Done (no text output)") + footer
        time.sleep(2)

    return f"⏳ Task {task_id[:8]}… still running after {timeout_s}s. Check status with jarvis_status('{task_id}')"


# ── MCP Protocol (JSON-RPC 2.0 over stdio) ───────────────────────────────────

TOOLS = [
    {
        "name": "jarvis_ask",
        "description": (
            "Delegate any task to Jarvis, the CTO AI agent of the Software Factory. "
            "Jarvis can create projects, missions, epics, sprints, teams, and monitor delivery. "
            "Blocks until Jarvis completes (up to 2 min). For long tasks, use jarvis_status to poll."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your instruction to Jarvis in natural language (French or English).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait for response (default: 120)",
                    "default": 120,
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "jarvis_status",
        "description": "Get the status and result of a previously submitted Jarvis task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "A2A task ID returned by jarvis_ask",
                }
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "jarvis_task_list",
        "description": "List recent tasks submitted to Jarvis (last 10).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "jarvis_agent_card",
        "description": "Get Jarvis A2A agent card (capabilities, skills, endpoints).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def _handle_tool_call(name: str, args: dict) -> str:
    if name == "jarvis_ask":
        msg = args.get("message", "").strip()
        if not msg:
            return "Error: message is required"
        timeout = int(args.get("timeout", 120))
        return _submit_and_wait(msg, timeout)

    elif name == "jarvis_status":
        task_id = args.get("task_id", "").strip()
        if not task_id:
            return "Error: task_id is required"
        result = _get(f"/a2a/tasks/{task_id}")
        if "error" in result:
            return f"Error: {result['error']}"
        state = result.get("status", {}).get("state", "?")
        output_parts = (result.get("output") or {}).get("parts") or []
        text = next(
            (p.get("text", "") for p in output_parts if p.get("kind") == "text"), ""
        )
        return (
            f"**Task {task_id[:8]}…** — state: `{state}`\n\n{text or '(no output yet)'}"
        )

    elif name == "jarvis_task_list":
        result = _get("/a2a/tasks")
        tasks = (result.get("tasks") or [])[-10:]
        if not tasks:
            return "No tasks yet."
        lines = []
        for t in reversed(tasks):
            tid = t.get("id", "")[:8]
            state = t.get("status", {}).get("state", "?")
            text = next(
                (
                    p.get("text", "")[:80]
                    for p in (t.get("input") or {}).get("parts", [])
                    if p.get("kind") == "text"
                ),
                "?",
            )
            lines.append(f"- `{tid}…` [{state}] {text}")
        return "\n".join(lines)

    elif name == "jarvis_agent_card":
        card = _get("/.well-known/agent.json")
        return json.dumps(card, indent=2, ensure_ascii=False)

    return f"Unknown tool: {name}"


def read_msg() -> Optional[Dict]:
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        # JSON-RPC can be framed with Content-Length header (LSP style) or raw
        if line.strip().startswith("Content-Length:"):
            length = int(line.split(":")[1].strip())
            sys.stdin.readline()  # blank line
            data = sys.stdin.read(length)
            return json.loads(data)
        return json.loads(line.strip())
    except Exception:
        return None


def send_msg(msg: dict):
    data = json.dumps(msg)
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def main():
    while True:
        msg = read_msg()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            send_msg(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "mcp-jarvis", "version": "1.0.0"},
                    },
                }
            )

        elif method == "initialized":
            pass  # notification, no response needed

        elif method == "tools/list":
            send_msg({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            try:
                result_text = _handle_tool_call(tool_name, tool_args)
            except Exception as e:
                result_text = f"Tool error: {e}"
            send_msg(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                        "isError": False,
                    },
                }
            )

        elif msg_id is not None:
            send_msg(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )


if __name__ == "__main__":
    main()
