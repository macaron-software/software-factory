"""
SF gRPC ToolService package.

Quick start:

    # Start server (separate process):
    python -m platform.tools.grpc.server --port 50051

    # Use client from executor:
    from platform.tools.grpc.client import get_grpc_client

    client = get_grpc_client()  # singleton, reuses channel
    result = await client.execute(
        "code_read",
        {"path": "src/main.py"},
        session_id=ctx.session_id,
        agent_id=ctx.agent.id,
        project_path=ctx.project_path,
    )

Environment variables:
    SF_GRPC_ADDR=localhost:50051    (default)
    SF_GRPC_ENABLED=1              (opt-in to route tool calls through gRPC)
"""
import os
import sys

# grpc_tools generates stubs with bare module imports; expose package dir so they resolve.
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

from .client import AsyncToolServiceClient, ToolServiceClient, get_grpc_client
from .server import ToolServicer, serve, serve_async

__all__ = [
    "ToolServicer",
    "serve",
    "serve_async",
    "ToolServiceClient",
    "AsyncToolServiceClient",
    "get_grpc_client",
]


__all__ = [
    "ToolServicer",
    "serve",
    "serve_async",
    "ToolServiceClient",
    "AsyncToolServiceClient",
    "get_grpc_client",
]
