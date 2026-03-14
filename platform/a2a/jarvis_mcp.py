#!/usr/bin/env python3
"""Jarvis MCP Server
====================
Exposes the SF Platform agents as MCP tools (stdio JSON-RPC 2.0).
Compatible with Copilot CLI, Claude Code, Cursor, and any MCP client.

- jarvis_chat        : SF CTO (Jarvis / strat-cto) — project agnostic, global view
- jarvis_memory_search: search SF memory
- pm_chat            : Project PM (Alexandre Moreau or custom per project) — project-centric

Usage in ~/.copilot/mcp-config.json:
  {
    "mcpServers": {
      "jarvis": {
        "type": "stdio",
        "command": "python3",
        "args": ["/path/to/platform/a2a/jarvis_mcp.py"]
      }
    }
  }

Environment:
  SF_API_URL   — SF platform base URL (default: http://40.89.174.75)
  SF_EMAIL     — login email (default: admin@demo.local)
  SF_PASSWORD  — login password
  SF_TOKEN     — pre-existing JWT token (skips login)
"""
# Ref: feat-agents-list

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

SF_API_URL = os.environ.get("SF_API_URL", "http://40.89.174.75")
SF_EMAIL = os.environ.get("SF_EMAIL", "admin@demo.local")
SF_PASSWORD = os.environ.get("SF_PASSWORD", "demo-admin-2026")
_token: str = os.environ.get("SF_TOKEN", "")

PROJECT_ID = "software-factory"  # Jarvis = SF CTO, project agnostic


# ── Auth ──────────────────────────────────────────────────────────────────────


def _login() -> str:
    global _token
    if _token:
        return _token
    resp = httpx.post(
        f"{SF_API_URL}/api/auth/login",
        json={"email": SF_EMAIL, "password": SF_PASSWORD},
        timeout=20,
    )
    resp.raise_for_status()
    tok = resp.cookies.get("access_token", "")
    if not tok:
        raise RuntimeError("Login failed: no access_token cookie")
    _token = tok
    return _token


# ── Jarvis API ────────────────────────────────────────────────────────────────


def _chat_jarvis(project_id: str, message: str) -> str:
    """Send a message to Jarvis and collect full streamed response."""
    url = f"{SF_API_URL}/api/projects/{project_id}/chat/stream"
    full_text = ""

    for attempt in range(2):
        try:
            with httpx.stream(
                "POST",
                url,
                json={"message": message},
                headers={
                    "Cookie": f"access_token={_login()}",
                    "Accept": "text/event-stream",
                },
                timeout=httpx.Timeout(connect=15, read=180, write=15, pool=5),
            ) as resp:
                if resp.status_code == 401 and attempt == 0:
                    global _token
                    _token = ""
                    continue
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            evt = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        text = evt.get("text", "")
                        if text:
                            full_text += text
            return full_text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and attempt == 0:
                _token = ""
                continue
            raise

    return full_text


# ── MCP JSON-RPC helpers ──────────────────────────────────────────────────────


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _respond(req_id: Any, result: Any) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


# ── Tool definitions ──────────────────────────────────────────────────────────


def _get_tools() -> list:
    return [
        {
            "name": "jarvis_chat",
            "description": (
                "Chat with Jarvis, the AI CTO agent for the Software Factory (SF). "
                "Jarvis is project-agnostic: he has a global view of all SF projects, ARTs, teams, "
                "epics, and technical decisions. Use for architecture advice, cross-project strategy, "
                "SF roadmap, team/mission creation, or any CTO-level question. "
                "For project-specific questions (Véligo, PSY, Finary...), use pm_chat instead."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Your question or instruction for Jarvis (SF CTO)",
                    }
                },
                "required": ["message"],
            },
        },
        {
            "name": "jarvis_memory_search",
            "description": (
                "Search the SF platform memory (AO docs, specs, architecture notes, "
                "past decisions). Returns relevant stored knowledge."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for SF memory",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "pm_chat",
            "description": (
                "Chat with the Program Manager (Alexandre Moreau) of a specific SF project. "
                "Project-centric: knows the project's backlog, Jira stories, specs, tech stack, "
                "and team. Use for project-level questions: feature status, sprint, CARE 360, etc. "
                "Examples of project_id: 'acme', 'psy', 'finary'."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "SF project ID (e.g. 'acme', 'psy', 'finary')",
                    },
                    "message": {
                        "type": "string",
                        "description": "Your question for the project PM",
                    },
                },
                "required": ["project_id", "message"],
            },
        },
    ]


# ── Tool handlers ─────────────────────────────────────────────────────────────


def _call_tool(name: str, arguments: dict) -> dict:
    if name == "jarvis_chat":
        message = arguments.get("message", "")
        if not message:
            return {"content": [{"type": "text", "text": "Error: message is required"}], "isError": True}
        try:
            response = _chat_jarvis(PROJECT_ID, message)
            return {"content": [{"type": "text", "text": response or "(no response)"}]}
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"Jarvis error: {exc}"}], "isError": True}

    elif name == "jarvis_memory_search":
        query = arguments.get("query", "")
        if not query:
            return {"content": [{"type": "text", "text": "Error: query is required"}], "isError": True}
        try:
            response = _chat_jarvis(
                PROJECT_ID,
                f"Recherche dans la mémoire SF: {query}\n"
                "Réponds avec les éléments pertinents trouvés dans la mémoire.",
            )
            return {"content": [{"type": "text", "text": response or "(no results)"}]}
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"Memory search error: {exc}"}], "isError": True}

    elif name == "pm_chat":
        project_id = arguments.get("project_id", "").strip()
        message = arguments.get("message", "").strip()
        if not project_id or not message:
            return {"content": [{"type": "text", "text": "Error: project_id and message are required"}], "isError": True}
        try:
            response = _chat_jarvis(project_id, message)
            return {"content": [{"type": "text", "text": response or "(no response)"}]}
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"PM chat error ({project_id}): {exc}"}], "isError": True}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}


# ── Main loop ─────────────────────────────────────────────────────────────────


def main() -> None:
    global PROJECT_ID

    parser = argparse.ArgumentParser(description="Jarvis MCP server")
    parser.add_argument("--project", default="software-factory", help="SF CTO project ID (default: software-factory)")
    args, _ = parser.parse_known_args()
    PROJECT_ID = args.project

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        req_id: Any = msg.get("id")
        method: str = msg.get("method", "")
        params: dict = msg.get("params") or {}

        if method == "initialize":
            _respond(req_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": f"jarvis-{PROJECT_ID}",
                    "version": "1.0.0",
                },
                "capabilities": {"tools": {}},
            })

        elif method == "tools/list":
            _respond(req_id, {"tools": _get_tools()})

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = _call_tool(name, arguments)
            _respond(req_id, result)

        elif method in ("notifications/initialized", "ping"):
            if req_id is not None:
                _respond(req_id, {})

        elif req_id is not None:
            _error(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
