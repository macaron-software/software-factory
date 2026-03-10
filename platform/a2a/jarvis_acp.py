#!/usr/bin/env python3
"""Jarvis ACP Server
===================
Exposes the SF Platform's Jarvis (project CTO agent) as an ACP-compatible
agent. Communicates via JSON-RPC 2.0 over stdin/stdout (ACP local agent spec).

Usage in opencode (~/.opencode/opencode.json):
  {
    "agents": {
      "jarvis-factory": {
        "name": "Jarvis — SF CTO",
        "command": "python3",
        "args": ["/path/to/platform/a2a/jarvis_acp.py", "--project", "factory"]
      }
    }
  }

Usage in Claude Code / Copilot (MCP alternative):
  Start with --mcp flag for OpenAI-compatible chat endpoint instead.

Environment:
  SF_API_URL   — SF platform base URL (default: http://localhost:8090)
  SF_EMAIL     — Login email (default: admin@demo.local)
  SF_PASSWORD  — Login password
  SF_TOKEN     — Pre-existing JWT token (skips login)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from typing import Generator

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

SF_API_URL = os.environ.get("SF_API_URL", "http://localhost:8090")
SF_EMAIL = os.environ.get("SF_EMAIL", "admin@demo.local")
SF_PASSWORD = os.environ.get("SF_PASSWORD", "")
SF_TOKEN = os.environ.get("SF_TOKEN", "")

# ── Auth ──────────────────────────────────────────────────────────────────────

_token: str = SF_TOKEN


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


# ── Sessions store (in-memory) ────────────────────────────────────────────────

_sessions: dict[str, dict] = {}


def _new_session_id() -> str:
    return "jarvis_" + uuid.uuid4().hex[:16]


# ── Jarvis API call ───────────────────────────────────────────────────────────


def _stream_jarvis(
    project_id: str, message: str, session_id: str
) -> Generator[str, None, None]:
    """Stream text chunks from the Jarvis chat endpoint (SSE)."""
    url = f"{SF_API_URL}/api/projects/{project_id}/chat/stream"
    payload = {"message": message, "session_id": session_id}

    for attempt in range(2):
        try:
            with httpx.stream(
                "POST",
                url,
                json=payload,
                headers={
                    "Cookie": f"access_token={_login()}",
                    "Accept": "text/event-stream",
                },
                timeout=120,
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
                            evt_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        text = evt_data.get("text", "")
                        if text:
                            yield text
            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and attempt == 0:
                _token = ""  # type: ignore[assignment]
                continue
            raise


# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

_write_lock = threading.Lock()


def _send(obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with _write_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


def _result(req_id, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _notify(method: str, params: dict) -> None:
    _send({"jsonrpc": "2.0", "method": method, "params": params})


# ── ACP method handlers ───────────────────────────────────────────────────────

PROJECT_ID = "factory"  # overridden by --project arg


def handle_initialize(req_id, params: dict) -> None:
    _result(
        req_id,
        {
            "protocolVersion": 1,
            "agentInfo": {
                "name": f"Jarvis — {PROJECT_ID.capitalize()} CTO",
                "version": "1.0.0",
            },
            "agentCapabilities": {
                "loadSession": True,
                "sessionCapabilities": {
                    "fork": {},
                    "list": {},
                    "resume": {},
                },
                "promptCapabilities": {
                    "embeddedContext": False,
                    "image": False,
                },
                "mcpCapabilities": {},
            },
            "authMethods": [],
        },
    )


def handle_session_list(req_id, params: dict) -> None:
    sessions = [
        {
            "sessionId": sid,
            "cwd": os.getcwd(),
            "title": info.get("title", "Jarvis conversation"),
            "updatedAt": info.get("updated_at", ""),
        }
        for sid, info in _sessions.items()
    ]
    _result(req_id, {"sessions": sessions})


def handle_session_resume(req_id, params: dict) -> None:
    session_id = params.get("sessionId", "")
    if not session_id or session_id not in _sessions:
        _error(req_id, -32602, f"Session not found: {session_id}")
        return
    _notify(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "available_commands_update",
                "availableCommands": [],
            },
        },
    )
    _result(
        req_id,
        {
            "sessionId": session_id,
            "models": {
                "currentModelId": "jarvis/cto",
                "availableModels": [
                    {"modelId": "jarvis/cto", "name": f"Jarvis CTO — {PROJECT_ID}"},
                ],
            },
        },
    )


def handle_session_fork(req_id, params: dict, project_id: str) -> None:
    """Create a new session and stream Jarvis response for the given parts."""
    parts = params.get("parts", [])
    message = " ".join(
        p.get("text", "") for p in parts if p.get("type") == "text"
    ).strip()

    if not message:
        _error(req_id, -32602, "No text message in parts")
        return

    session_id = _new_session_id()
    _sessions[session_id] = {
        "title": message[:60],
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project_id": project_id,
    }

    _notify(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "available_commands_update",
                "availableCommands": [],
            },
        },
    )
    _result(
        req_id,
        {
            "sessionId": session_id,
            "models": {
                "currentModelId": "jarvis/cto",
                "availableModels": [
                    {"modelId": "jarvis/cto", "name": f"Jarvis CTO — {project_id}"},
                ],
            },
        },
    )

    # Stream Jarvis response in background thread
    def _stream() -> None:
        msg_id = "msg_" + uuid.uuid4().hex[:12]
        full_text = ""
        try:
            for chunk in _stream_jarvis(project_id, message, session_id):
                full_text += chunk
                _notify(
                    "message/part",
                    {
                        "sessionId": session_id,
                        "part": {
                            "id": msg_id,
                            "type": "text",
                            "text": chunk,
                        },
                    },
                )
        except Exception as exc:
            _notify(
                "message/part",
                {
                    "sessionId": session_id,
                    "part": {
                        "id": msg_id + "_err",
                        "type": "text",
                        "text": f"\n\n[Jarvis error: {exc}]",
                    },
                },
            )
        finally:
            _notify(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "message_completed",
                        "messageId": msg_id,
                    },
                },
            )

    threading.Thread(target=_stream, daemon=True).start()


# ── Main loop ─────────────────────────────────────────────────────────────────


def main() -> None:
    global PROJECT_ID

    parser = argparse.ArgumentParser(description="Jarvis ACP server")
    parser.add_argument("--project", default="factory", help="SF project ID")
    args, _ = parser.parse_known_args()
    PROJECT_ID = args.project

    # Pre-login to fail fast
    try:
        _login()
    except Exception as e:
        sys.stderr.write(f"[jarvis-acp] auth failed: {e}\n")
        sys.stderr.flush()
        # Continue anyway — will retry on first request

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"[jarvis-acp] JSON parse error: {e}\n")
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if method == "initialize":
            handle_initialize(req_id, params)
        elif method == "session/list":
            handle_session_list(req_id, params)
        elif method == "session/resume":
            handle_session_resume(req_id, params)
        elif method == "session/fork":
            handle_session_fork(req_id, params, PROJECT_ID)
        elif req_id is not None:
            _error(req_id, -32601, f'"Method not found": {method}')


if __name__ == "__main__":
    main()
