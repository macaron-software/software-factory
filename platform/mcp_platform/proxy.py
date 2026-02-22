#!/usr/bin/env python3
"""
MCP Platform Proxy — stdio↔HTTP bridge for MCP clients.
Translates stdio JSON-RPC to HTTP calls to the platform server.

Usage in opencode config:
    "mcp": {"platform": {"type": "local", "command": ["python3", ".../proxy.py"]}}
"""

import json
import sys
import urllib.request

SERVER_URL = "http://127.0.0.1:9501"


def send_request(method: str, params: dict = None, req_id=None):
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }).encode()
    req = urllib.request.Request(
        f"{SERVER_URL}/message",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": str(e)}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})

        if method == "notifications/initialized":
            continue

        response = send_request(method, params, req_id)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
