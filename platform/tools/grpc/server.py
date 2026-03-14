"""
SF gRPC ToolService — async server wrapping the platform tool runner.

Usage:
    python -m platform.tools.grpc.server           # port 50051
    python -m platform.tools.grpc.server --port 50052
    uvicorn-compatible: import and call serve()

The server receives binary ToolRequest messages, reconstructs a minimal
ExecutionContext, calls the existing async _execute_tool(), and returns
a binary ToolResponse.

Why gRPC?
- Binary protobuf framing: 30–50% smaller than JSON-over-HTTP
- HTTP/2 multiplexing: concurrent tool calls without connection overhead
- Streaming: ExecuteStream for build/test/deploy output
- Language-agnostic: future Rust/Go tools can call this service
- Isolation: tools run in a separate process from the LLM loop
"""
# Ref: feat-grpc-tools

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncIterator

import grpc
from grpc import aio

from . import tool_service_pb2 as pb2
from . import tool_service_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)

DEFAULT_PORT = 50051
DEFAULT_ADDR = f"[::]:{DEFAULT_PORT}"


class ToolServicer(pb2_grpc.ToolServiceServicer):
    """Async gRPC servicer wrapping the SF tool runner."""

    # ------------------------------------------------------------------
    # Execute (unary)
    # ------------------------------------------------------------------

    async def Execute(
        self,
        request: pb2.ToolRequest,
        context: aio.ServicerContext,
    ) -> pb2.ToolResponse:
        """Execute a single tool call; binary round-trip."""
        start = time.monotonic()
        call_id = request.call_id or str(uuid.uuid4())

        try:
            ctx = await self._build_ctx(request.ctx)
            tc = self._build_tc(call_id, request.name, request.args)

            from ...agents.tool_runner import _execute_tool

            result_str = await _execute_tool(tc, ctx, None)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.debug("grpc Execute %s → %s (%dms)", request.name, "ok", duration_ms)
            return pb2.ToolResponse(
                call_id=call_id,
                success=True,
                result=result_str.encode() if isinstance(result_str, str) else result_str,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning("grpc Execute %s failed: %s (%dms)", request.name, exc, duration_ms)
            return pb2.ToolResponse(
                call_id=call_id,
                success=False,
                result=b"",
                error=str(exc),
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------
    # ExecuteStream (server-streaming)
    # ------------------------------------------------------------------

    async def ExecuteStream(
        self,
        request: pb2.ToolRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[pb2.ToolChunk]:
        """Stream tool output in chunks (useful for build/test/deploy)."""
        call_id = request.call_id or str(uuid.uuid4())

        try:
            ctx = await self._build_ctx(request.ctx)
            tc = self._build_tc(call_id, request.name, request.args)

            from ...agents.tool_runner import _execute_tool

            # Execute and yield result as single final chunk
            # (Full streaming would require tool-level coroutine support)
            result_str = await _execute_tool(tc, ctx, None)
            data = result_str.encode() if isinstance(result_str, str) else result_str

            # Stream in 4KB chunks for large outputs
            chunk_size = 4096
            for i in range(0, max(1, len(data)), chunk_size):
                chunk = data[i : i + chunk_size]
                is_last = (i + chunk_size) >= len(data)
                yield pb2.ToolChunk(
                    call_id=call_id,
                    data=chunk,
                    done=is_last,
                    success=is_last,
                )

        except Exception as exc:
            logger.warning("grpc ExecuteStream %s failed: %s", request.name, exc)
            yield pb2.ToolChunk(
                call_id=call_id,
                data=b"",
                done=True,
                success=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # GetSchemas (unary)
    # ------------------------------------------------------------------

    async def GetSchemas(
        self,
        request: pb2.GetSchemasRequest,
        context: aio.ServicerContext,
    ) -> pb2.GetSchemasResponse:
        """Return OpenAI-compatible tool schemas as binary JSON."""
        try:
            from ...agents.tool_schemas import _filter_schemas, _get_tool_schemas

            all_schemas = _get_tool_schemas()
            if request.allowed_tools:
                allowed = set(request.allowed_tools)
                schemas = [s for s in all_schemas if s.get("function", {}).get("name") in allowed]
            else:
                schemas = all_schemas

            return pb2.GetSchemasResponse(schemas=json.dumps(schemas).encode())

        except Exception as exc:
            logger.warning("grpc GetSchemas failed: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return pb2.GetSchemasResponse(schemas=b"[]")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _build_ctx(grpc_ctx: pb2.ToolContext):
        """Reconstruct a minimal ExecutionContext from gRPC ToolContext."""
        from ...agents.executor import ExecutionContext
        from ...agents.store import get_agent_store

        agent_id = grpc_ctx.agent_id
        agent_def = None
        if agent_id:
            try:
                agent_def = get_agent_store().get(agent_id)
            except Exception:
                pass

        # Minimal context — tools only need session_id, project_path, epic_run_id
        return ExecutionContext(
            agent=agent_def,
            session_id=grpc_ctx.session_id or "",
            project_id=grpc_ctx.project_id or None,
            project_path=grpc_ctx.project_path or None,
            epic_run_id=grpc_ctx.epic_run_id or None,
        )

    @staticmethod
    def _build_tc(call_id: str, name: str, args_bytes: bytes):
        """Build LLMToolCall from gRPC request fields."""
        from ...llm.client import LLMToolCall

        try:
            args = json.loads(args_bytes) if args_bytes else {}
        except json.JSONDecodeError:
            args = {}

        return LLMToolCall(id=call_id, function_name=name, arguments=args)


# ──────────────────────────────────────────────────────────────────
# Server lifecycle
# ──────────────────────────────────────────────────────────────────

async def serve_async(
    addr: str = DEFAULT_ADDR,
    max_concurrent_rpcs: int | None = None,
) -> aio.Server:
    """Start the async gRPC server and return it (caller must await server.wait_for_termination())."""
    server = aio.server(maximum_concurrent_rpcs=max_concurrent_rpcs)
    pb2_grpc.add_ToolServiceServicer_to_server(ToolServicer(), server)
    server.add_insecure_port(addr)
    await server.start()
    logger.info("SF gRPC ToolService listening on %s", addr)
    return server


def serve(port: int = DEFAULT_PORT, max_concurrent_rpcs: int | None = None) -> None:
    """Blocking entry point. Use as __main__ or subprocess."""
    import argparse

    parser = argparse.ArgumentParser(description="SF gRPC ToolService")
    parser.add_argument("--port", type=int, default=port)
    parser.add_argument("--max-rpcs", type=int, default=max_concurrent_rpcs)
    args = parser.parse_args()

    addr = f"[::]:{args.port}"

    async def _run():
        server = await serve_async(addr, args.max_rpcs)
        await server.wait_for_termination()

    asyncio.run(_run())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve()
