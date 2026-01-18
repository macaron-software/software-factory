#!/usr/bin/env python3
"""
MCP Figma Proxy - Stdio-to-HTTP bridge for Figma MCP
=====================================================
Forwards MCP requests to Figma's MCP server (desktop or remote).

Usage in opencode config:
  "figma": {
    "type": "local",
    "command": ["python3", ".../mcp_lrm/proxy_figma.py"]
  }
"""

import json
import sys
import urllib.request
import urllib.error
import os
from typing import Optional, Dict, Any

# Figma MCP endpoints
FIGMA_DESKTOP_URL = "http://127.0.0.1:3845/mcp"
FIGMA_REMOTE_URL = "https://mcp.figma.com/mcp"

# Get Figma token from env (for remote server)
FIGMA_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")


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


def check_desktop_server() -> bool:
    """Check if Figma desktop MCP server is running"""
    try:
        req = urllib.request.Request(
            FIGMA_DESKTOP_URL,
            method='POST',
            headers={"Content-Type": "application/json"},
            data=json.dumps({"jsonrpc": "2.0", "method": "initialize", "id": 0}).encode()
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except:
        return False


def call_figma_server(method: str, params: Dict = None) -> Dict:
    """Call Figma MCP server (desktop first, fallback to remote)"""
    
    # Prefer desktop server (no auth needed)
    use_desktop = check_desktop_server()
    
    url = FIGMA_DESKTOP_URL if use_desktop else FIGMA_REMOTE_URL
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Add auth for remote server
    if not use_desktop and FIGMA_TOKEN:
        headers["Authorization"] = f"Bearer {FIGMA_TOKEN}"
    
    try:
        req = urllib.request.Request(
            url,
            method='POST',
            headers=headers,
            data=json.dumps(payload).encode()
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": f"HTTP {e.code}: {e.reason}"}}
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)}}


def handle_initialize(msg_id: Any) -> Dict:
    """Handle MCP initialize request"""
    return make_response(msg_id, {
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": "figma-proxy",
            "version": "1.0.0"
        },
        "capabilities": {
            "tools": {}
        }
    })


def handle_tools_list(msg_id: Any) -> Dict:
    """Forward tools/list to Figma server"""
    result = call_figma_server("tools/list")
    
    if "error" in result:
        # Return empty tools if server unavailable
        return make_response(msg_id, {"tools": []})
    
    return make_response(msg_id, result.get("result", {"tools": []}))


def handle_tools_call(msg_id: Any, params: Dict) -> Dict:
    """Forward tools/call to Figma server"""
    result = call_figma_server("tools/call", params)
    
    if "error" in result:
        return make_error(msg_id, result["error"].get("code", -1), result["error"].get("message", "Unknown error"))
    
    return make_response(msg_id, result.get("result", {}))


def main():
    """Main proxy loop"""
    while True:
        msg = read_message()
        if msg is None:
            break
        
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})
        
        if method == "initialize":
            response = handle_initialize(msg_id)
        elif method == "initialized":
            continue  # No response needed
        elif method == "tools/list":
            response = handle_tools_list(msg_id)
        elif method == "tools/call":
            response = handle_tools_call(msg_id, params)
        else:
            response = make_error(msg_id, -32601, f"Method not found: {method}")
        
        write_message(response)


if __name__ == "__main__":
    main()
