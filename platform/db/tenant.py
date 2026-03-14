"""Multi-tenant project isolation — all projects use shared PostgreSQL database."""
# Ref: feat-workspaces

from __future__ import annotations

import logging

from .adapter import get_connection

logger = logging.getLogger(__name__)


def get_platform_db():
    """Get connection to the platform database."""
    return get_connection()


def get_project_db(project_id: str):
    """Get connection for a project (uses shared PostgreSQL database)."""
    return get_connection()


def list_project_dbs() -> list[dict]:
    """List all project databases."""
    return []


def delete_project_db(project_id: str) -> bool:
    """Delete a project database."""
    return False
