"""Workspace middleware — injects workspace context into request.state."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


class WorkspaceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        workspace_id = (
            request.headers.get("X-Workspace-ID")
            or request.cookies.get("workspace_id")
            or "default"
        )
        request.state.workspace_id = workspace_id
        # Lazy lookup name/color for template rendering
        request.state.workspace_name = "Default"
        request.state.workspace_color = "#6366f1"
        try:
            from ...db.migrations import get_db

            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT name, color FROM workspaces WHERE id = ?", (workspace_id,)
                ).fetchone()
                if row:
                    request.state.workspace_name = row[0] or "Default"
                    request.state.workspace_color = row[1] or "#6366f1"
            finally:
                conn.close()
        except Exception:
            pass
        response = await call_next(request)
        return response
