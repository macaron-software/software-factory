"""
MCP Manager — Launch, stop, and proxy to stdio-based MCP servers.
==================================================================
Each MCP server runs as a subprocess with JSON-RPC over stdin/stdout.
The manager maintains a process pool and routes tool calls to the right server.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Optional

from .store import MCPServer, get_mcp_store

logger = logging.getLogger(__name__)

# JSON-RPC message IDs
_msg_counter = 0


def _next_id() -> int:
    global _msg_counter
    _msg_counter += 1
    return _msg_counter


class MCPProcess:
    """A running MCP server subprocess communicating via stdio JSON-RPC."""

    def __init__(self, mcp: MCPServer):
        self.mcp = mcp
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._read_buffer = b""

    async def start(self) -> bool:
        """Start the MCP server subprocess."""
        cmd = self.mcp.command
        args = self.mcp.args or []

        # Resolve command path
        resolved = shutil.which(cmd)
        if not resolved:
            # Try common paths
            for prefix in ["/app/.local/bin/", "/usr/local/bin/", "/usr/bin/"]:
                if os.path.isfile(prefix + cmd):
                    resolved = prefix + cmd
                    break
        if not resolved:
            logger.error("MCP %s: command '%s' not found", self.mcp.id, cmd)
            return False

        env = dict(os.environ)
        env.update(self.mcp.env or {})

        try:
            self.proc = await asyncio.create_subprocess_exec(
                resolved, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            logger.info("MCP %s started (PID %d): %s %s",
                        self.mcp.id, self.proc.pid, resolved, " ".join(args))

            # Send initialize request
            init_result = await self._send_jsonrpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "macaron-platform", "version": "1.0.0"},
            })
            if init_result:
                # Send initialized notification
                await self._send_notification("notifications/initialized", {})
                logger.info("MCP %s initialized OK", self.mcp.id)
                return True
            else:
                logger.warning("MCP %s: initialize failed, server may not support JSON-RPC",
                               self.mcp.id)
                return True  # Some servers work without init
        except Exception as e:
            logger.error("MCP %s failed to start: %s", self.mcp.id, e)
            return False

    async def stop(self):
        """Stop the MCP server subprocess."""
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.proc.kill()
            except Exception:
                pass
            logger.info("MCP %s stopped", self.mcp.id)

    async def call_tool(self, tool_name: str, arguments: dict, timeout: float = 30) -> str:
        """Call a tool on the MCP server via JSON-RPC."""
        if not self.proc or self.proc.returncode is not None:
            return f"MCP {self.mcp.id} not running"

        result = await self._send_jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        }, timeout=timeout)

        if result is None:
            return f"MCP {self.mcp.id}: no response for {tool_name}"

        # Extract text content from MCP response
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))
                    elif isinstance(item, dict) and item.get("type") == "image":
                        texts.append(f"[image: {item.get('mimeType', 'image/png')}]")
                    else:
                        texts.append(str(item))
                return "\n".join(texts) if texts else str(result)
            return str(result)
        return str(result)

    async def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        if not self.proc or self.proc.returncode is not None:
            return []
        result = await self._send_jsonrpc("tools/list", {})
        if isinstance(result, dict):
            return result.get("tools", [])
        return []

    async def _send_jsonrpc(self, method: str, params: dict,
                            timeout: float = 10) -> Optional[dict]:
        """Send JSON-RPC request and wait for response."""
        async with self._lock:
            if not self.proc or not self.proc.stdin or not self.proc.stdout:
                return None

            msg_id = _next_id()
            request = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": method,
                "params": params,
            }

            try:
                line = json.dumps(request) + "\n"
                self.proc.stdin.write(line.encode())
                await self.proc.stdin.drain()

                # Read response with timeout
                response_line = await asyncio.wait_for(
                    self.proc.stdout.readline(), timeout=timeout)

                if not response_line:
                    return None

                response = json.loads(response_line.decode().strip())
                if "error" in response:
                    err = response["error"]
                    logger.warning("MCP %s RPC error: %s", self.mcp.id, err)
                    return None
                return response.get("result")

            except asyncio.TimeoutError:
                logger.warning("MCP %s: timeout for %s", self.mcp.id, method)
                return None
            except json.JSONDecodeError as e:
                logger.warning("MCP %s: invalid JSON response: %s", self.mcp.id, e)
                return None
            except Exception as e:
                logger.warning("MCP %s: RPC error: %s", self.mcp.id, e)
                return None

    async def _send_notification(self, method: str, params: dict):
        """Send JSON-RPC notification (no response expected)."""
        if not self.proc or not self.proc.stdin:
            return
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        try:
            line = json.dumps(msg) + "\n"
            self.proc.stdin.write(line.encode())
            await self.proc.stdin.drain()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None


class MCPManager:
    """Manages all MCP server subprocesses."""

    def __init__(self):
        self._processes: dict[str, MCPProcess] = {}

    async def start(self, mcp_id: str) -> tuple[bool, str]:
        """Start an MCP server by ID."""
        store = get_mcp_store()
        mcp = store.get(mcp_id)
        if not mcp:
            return False, f"MCP '{mcp_id}' not found"

        # Stop if already running
        if mcp_id in self._processes and self._processes[mcp_id].is_running:
            await self._processes[mcp_id].stop()

        proc = MCPProcess(mcp)
        ok = await proc.start()
        if ok:
            self._processes[mcp_id] = proc
            store.update_status(mcp_id, "running")

            # Discover tools
            try:
                tools = await proc.list_tools()
                if tools:
                    store.update_tools(mcp_id, tools)
                    logger.info("MCP %s: discovered %d tools", mcp_id, len(tools))
            except Exception:
                pass

            return True, f"MCP {mcp.name} started (PID {proc.proc.pid})"
        else:
            store.update_status(mcp_id, "error")
            return False, f"MCP {mcp.name} failed to start"

    async def stop(self, mcp_id: str) -> tuple[bool, str]:
        """Stop an MCP server."""
        if mcp_id in self._processes:
            await self._processes[mcp_id].stop()
            del self._processes[mcp_id]
        store = get_mcp_store()
        store.update_status(mcp_id, "stopped")
        return True, f"MCP {mcp_id} stopped"

    async def call_tool(self, mcp_id: str, tool_name: str,
                        arguments: dict, timeout: float = 30) -> str:
        """Call a tool on a running MCP server."""
        proc = self._processes.get(mcp_id)
        if not proc or not proc.is_running:
            return f"MCP {mcp_id} not running. Start it first."
        return await proc.call_tool(tool_name, arguments, timeout=timeout)

    async def test(self, mcp_id: str) -> dict:
        """Test an MCP server — start, list tools, run a test call, stop."""
        store = get_mcp_store()
        mcp = store.get(mcp_id)
        if not mcp:
            return {"ok": False, "error": f"MCP '{mcp_id}' not found"}

        result = {"id": mcp_id, "name": mcp.name, "ok": False}

        # Start
        ok, msg = await self.start(mcp_id)
        result["start"] = msg
        if not ok:
            return result

        # List tools
        proc = self._processes.get(mcp_id)
        if proc:
            tools = await proc.list_tools()
            result["tools_discovered"] = len(tools)
            result["tool_names"] = [t.get("name", "?") for t in tools]

            # Quick test call for fetch
            if mcp_id == "mcp-fetch" and tools:
                test_result = await proc.call_tool("fetch", {
                    "url": "https://example.com", "max_length": 500,
                })
                result["test_call"] = test_result[:200] if test_result else "no response"
                result["ok"] = bool(test_result and "Example" in test_result)
            elif mcp_id == "mcp-memory" and tools:
                test_result = await proc.call_tool("read_graph", {})
                result["test_call"] = test_result[:200] if test_result else "no response"
                result["ok"] = True
            else:
                result["ok"] = len(tools) > 0

        return result

    def status(self) -> list[dict]:
        """Get status of all MCP servers."""
        store = get_mcp_store()
        mcps = store.list()
        statuses = []
        for mcp in mcps:
            proc = self._processes.get(mcp.id)
            running = proc.is_running if proc else False
            pid = proc.proc.pid if proc and proc.proc else None
            statuses.append({
                "id": mcp.id,
                "name": mcp.name,
                "status": "running" if running else mcp.status,
                "pid": pid,
                "tools_count": len(mcp.tools),
                "is_builtin": mcp.is_builtin,
            })
        return statuses

    async def stop_all(self):
        """Stop all running MCP servers."""
        for mcp_id in list(self._processes.keys()):
            await self.stop(mcp_id)

    def get_running_ids(self) -> list[str]:
        """Get list of running MCP server IDs."""
        return [k for k, v in self._processes.items() if v.is_running]


# ── Singleton ────────────────────────────────────────────────────

_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager
