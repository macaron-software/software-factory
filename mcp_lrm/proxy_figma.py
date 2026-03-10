#!/usr/bin/env python3
"""
MCP Figma Proxy - Stdio-to-HTTP bridge for Figma MCP
=====================================================
Forwards MCP requests to Figma's MCP server (desktop or remote).

Figma MCP uses SSE (Server-Sent Events) for responses.

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
import re
from typing import Optional, Dict, Any

# Figma MCP endpoints
FIGMA_DESKTOP_URL = "http://127.0.0.1:3845/mcp"
FIGMA_REMOTE_URL = "https://mcp.figma.com/mcp"

# Get Figma token from env (for remote server)
FIGMA_TOKEN = os.environ.get("FIGMA_ACCESS_TOKEN", "")

# Session ID for Figma MCP (set after initialize)
SESSION_ID = None


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
    """Check if Figma desktop MCP server is running by trying a simple GET"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 3845))
        sock.close()
        return result == 0
    except:
        return False


def call_figma_server(method: str, params: Dict = None, msg_id: Any = 1) -> Dict:
    """Call Figma MCP server (desktop first, fallback to remote)"""
    global SESSION_ID
    
    # Prefer desktop server (no auth needed)
    use_desktop = check_desktop_server()
    
    url = FIGMA_DESKTOP_URL if use_desktop else FIGMA_REMOTE_URL
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": msg_id
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Add session ID if we have one
    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID
    
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
            # Extract session ID from response headers
            new_session = resp.headers.get("mcp-session-id")
            if new_session:
                SESSION_ID = new_session
            
            # Parse SSE response
            content = resp.read().decode()
            
            # Extract JSON from SSE format: "data: {...}"
            for line in content.split('\n'):
                if line.startswith('data: '):
                    json_str = line[6:]  # Remove "data: " prefix
                    return json.loads(json_str)
            
            # Fallback: try parsing as plain JSON
            return json.loads(content)
            
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": f"HTTP {e.code}: {e.reason}"}}
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)}}


def handle_initialize(msg_id: Any) -> Dict:
    """Handle MCP initialize request - forward to Figma"""
    result = call_figma_server("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "factory-proxy", "version": "1.0"}
    }, msg_id)
    
    if "error" in result:
        return make_error(msg_id, result["error"].get("code", -1), result["error"].get("message", "Init failed"))
    
    return make_response(msg_id, result.get("result", {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "figma-proxy", "version": "1.0.0"},
        "capabilities": {"tools": {}}
    }))


def handle_tools_list(msg_id: Any) -> Dict:
    """Forward tools/list to Figma server"""
    result = call_figma_server("tools/list", {}, msg_id)
    
    if "error" in result:
        # Return empty tools if server unavailable
        return make_response(msg_id, {"tools": []})
    
    return make_response(msg_id, result.get("result", {"tools": []}))


def handle_tools_call(msg_id: Any, params: Dict) -> Dict:
    """Forward tools/call to Figma server"""
    result = call_figma_server("tools/call", params, msg_id)
    
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
