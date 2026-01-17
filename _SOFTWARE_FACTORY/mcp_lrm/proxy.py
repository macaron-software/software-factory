#!/usr/bin/env python3
"""
MCP LRM Proxy - Lightweight stdio-to-HTTP bridge
=================================================
Tiny process that forwards MCP requests to the SSE server.

This solves the "50 servers" problem:
- opencode spawns this tiny proxy (stdio)
- proxy forwards requests to single SSE server (HTTP)
- SSE server does all the heavy work

Memory footprint: ~10MB per proxy vs ~50MB per full server
"""

import json
import sys
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

SERVER_URL = "http://127.0.0.1:9500"


def read_message() -> Optional[Dict]:
    """Read JSON-RPC from stdin"""
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except:
        return None


def write_message(msg: Dict):
    """Write JSON-RPC to stdout"""
    json.dump(msg, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def make_response(id: Any, result: Any) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id: Any, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def call_server(name: str, arguments: Dict) -> Dict:
    """Forward tool call to SSE server"""
    try:
        data = json.dumps({"name": name, "arguments": arguments}).encode()
        req = urllib.request.Request(
            f"{SERVER_URL}/call",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Server unavailable: {e}"}
    except Exception as e:
        return {"error": str(e)}


def get_tools() -> list:
    """Get tools from server"""
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/tools", timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("tools", [])
    except:
        return []


def main():
    """Main proxy loop"""
    while True:
        msg = read_message()
        if msg is None:
            break

        msg_id = msg.get("id")
        method = msg.get("method", "")

        # Handle MCP protocol messages
        if method == "initialize":
            write_message(make_response(msg_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "mcp-lrm-proxy", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }))

        elif method == "tools/list":
            tools = get_tools()
            write_message(make_response(msg_id, {"tools": tools}))

        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = call_server(name, arguments)

            if "error" in result:
                write_message(make_response(msg_id, {
                    "content": [{"type": "text", "text": f"Error: {result['error']}"}],
                    "isError": True
                }))
            else:
                write_message(make_response(msg_id, {
                    "content": [{"type": "text", "text": json.dumps(result.get("result", result), indent=2)}]
                }))

        elif method == "notifications/initialized":
            # Acknowledge initialization
            pass

        elif method == "ping":
            write_message(make_response(msg_id, {}))

        else:
            write_message(make_error(msg_id, -32601, f"Unknown method: {method}"))


if __name__ == "__main__":
    main()
