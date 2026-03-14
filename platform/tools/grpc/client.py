"""
SF gRPC ToolService — client for agent executor.

Drop-in replacement for in-process tool calls.
Connects to the ToolService gRPC server and executes tools via binary HTTP/2.

Usage:
    from platform.tools.grpc.client import ToolServiceClient

    with ToolServiceClient() as client:
        result = client.execute("code_read", {"path": "src/main.py"}, session_id="s1")
        print(result["result"])

    # Async variant:
    async with AsyncToolServiceClient() as client:
        result = await client.execute(...)

Environment:
    SF_GRPC_ADDR=localhost:50051  (default)
"""
# Ref: feat-grpc-tools

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import AsyncIterator

import grpc
from grpc import aio

from . import tool_service_pb2 as pb2
from . import tool_service_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)

DEFAULT_ADDR = os.environ.get("SF_GRPC_ADDR", "localhost:50051")


def _make_request(
    name: str,
    args: dict,
    session_id: str = "",
    agent_id: str = "",
    project_id: str = "",
    project_path: str = "",
    epic_run_id: str = "",
    call_id: str = "",
) -> pb2.ToolRequest:
    return pb2.ToolRequest(
        call_id=call_id or str(uuid.uuid4()),
        name=name,
        args=json.dumps(args).encode(),
        ctx=pb2.ToolContext(
            session_id=session_id,
            agent_id=agent_id,
            project_id=project_id or "",
            project_path=project_path or "",
            epic_run_id=epic_run_id or "",
        ),
    )


def _parse_response(resp: pb2.ToolResponse) -> dict:
    return {
        "call_id": resp.call_id,
        "success": resp.success,
        "result": resp.result.decode() if resp.result else "",
        "error": resp.error,
        "duration_ms": resp.duration_ms,
    }


# ──────────────────────────────────────────────────────────────────
# Sync client (for use in sync contexts or thread pool executors)
# ──────────────────────────────────────────────────────────────────

class ToolServiceClient:
    """Synchronous gRPC client for the SF ToolService."""

    def __init__(self, addr: str = DEFAULT_ADDR):
        self._channel = grpc.insecure_channel(
            addr,
            options=[
                ("grpc.max_send_message_length", 16 * 1024 * 1024),   # 16MB
                ("grpc.max_receive_message_length", 16 * 1024 * 1024),
            ],
        )
        self._stub = pb2_grpc.ToolServiceStub(self._channel)
        logger.debug("ToolServiceClient connected to %s", addr)

    def execute(
        self,
        name: str,
        args: dict,
        session_id: str = "",
        agent_id: str = "",
        project_id: str = "",
        project_path: str = "",
        epic_run_id: str = "",
    ) -> dict:
        """Execute a tool synchronously. Returns dict with success/result/error/duration_ms."""
        req = _make_request(name, args, session_id, agent_id, project_id, project_path, epic_run_id)
        try:
            resp = self._stub.Execute(req)
            return _parse_response(resp)
        except grpc.RpcError as exc:
            logger.warning("gRPC Execute %s failed: %s", name, exc)
            return {"call_id": req.call_id, "success": False, "result": "", "error": str(exc), "duration_ms": 0}

    def execute_stream(
        self,
        name: str,
        args: dict,
        session_id: str = "",
        agent_id: str = "",
        project_id: str = "",
        project_path: str = "",
    ) -> Iterator[bytes]:
        """Execute a tool and yield output chunks (for streaming tools)."""
        req = _make_request(name, args, session_id, agent_id, project_id, project_path)
        try:
            for chunk in self._stub.ExecuteStream(req):
                yield chunk.data
                if chunk.done:
                    break
        except grpc.RpcError as exc:
            logger.warning("gRPC ExecuteStream %s failed: %s", name, exc)

    def get_schemas(self, agent_id: str = "", allowed_tools: list[str] | None = None) -> list[dict]:
        """Return OpenAI-compatible tool schemas."""
        req = pb2.GetSchemasRequest(agent_id=agent_id, allowed_tools=allowed_tools or [])
        try:
            resp = self._stub.GetSchemas(req)
            return json.loads(resp.schemas) if resp.schemas else []
        except grpc.RpcError as exc:
            logger.warning("gRPC GetSchemas failed: %s", exc)
            return []

    def close(self) -> None:
        self._channel.close()

    def __enter__(self) -> ToolServiceClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()


# ──────────────────────────────────────────────────────────────────
# Async client (for use in async agent executor)
# ──────────────────────────────────────────────────────────────────

class AsyncToolServiceClient:
    """Async gRPC client — use inside asyncio event loops (executor, agent loop)."""

    def __init__(self, addr: str = DEFAULT_ADDR):
        self._addr = addr
        self._channel: aio.Channel | None = None
        self._stub: pb2_grpc.ToolServiceStub | None = None

    async def _ensure_connected(self) -> None:
        if self._channel is None:
            self._channel = aio.insecure_channel(
                self._addr,
                options=[
                    ("grpc.max_send_message_length", 16 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 16 * 1024 * 1024),
                ],
            )
            self._stub = pb2_grpc.ToolServiceStub(self._channel)

    async def execute(
        self,
        name: str,
        args: dict,
        session_id: str = "",
        agent_id: str = "",
        project_id: str = "",
        project_path: str = "",
        epic_run_id: str = "",
    ) -> dict:
        await self._ensure_connected()
        req = _make_request(name, args, session_id, agent_id, project_id, project_path, epic_run_id)
        try:
            resp = await self._stub.Execute(req)
            return _parse_response(resp)
        except grpc.RpcError as exc:
            logger.warning("async gRPC Execute %s failed: %s", name, exc)
            return {"call_id": req.call_id, "success": False, "result": "", "error": str(exc), "duration_ms": 0}

    async def execute_stream(
        self,
        name: str,
        args: dict,
        session_id: str = "",
        agent_id: str = "",
        project_id: str = "",
        project_path: str = "",
    ) -> AsyncIterator[bytes]:
        await self._ensure_connected()
        req = _make_request(name, args, session_id, agent_id, project_id, project_path)
        try:
            async for chunk in self._stub.ExecuteStream(req):
                yield chunk.data
                if chunk.done:
                    break
        except grpc.RpcError as exc:
            logger.warning("async gRPC ExecuteStream %s failed: %s", name, exc)

    async def get_schemas(self, agent_id: str = "", allowed_tools: list[str] | None = None) -> list[dict]:
        await self._ensure_connected()
        req = pb2.GetSchemasRequest(agent_id=agent_id, allowed_tools=allowed_tools or [])
        try:
            resp = await self._stub.GetSchemas(req)
            return json.loads(resp.schemas) if resp.schemas else []
        except grpc.RpcError as exc:
            logger.warning("async gRPC GetSchemas failed: %s", exc)
            return []

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()

    async def __aenter__(self) -> AsyncToolServiceClient:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()


# ──────────────────────────────────────────────────────────────────
# Singleton for executor use (lazy init, shared channel)
# ──────────────────────────────────────────────────────────────────

_default_client: AsyncToolServiceClient | None = None


def get_grpc_client(addr: str = DEFAULT_ADDR) -> AsyncToolServiceClient:
    """Get or create the shared async gRPC client (singleton per process)."""
    global _default_client
    if _default_client is None:
        _default_client = AsyncToolServiceClient(addr)
    return _default_client
