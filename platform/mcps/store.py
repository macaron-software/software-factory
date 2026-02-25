"""
MCP Store — CRUD for external MCP server registry.
====================================================
Persists in `mcps` table. Each MCP has:
- command (python3 -m mcp_server_fetch, npx @playwright/mcp, etc.)
- args, env overrides
- tools list (discovered at runtime)
- status: stopped | running | error
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    id: str
    name: str
    description: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    status: str = "stopped"
    is_builtin: bool = False
    created_at: str = ""
    updated_at: str = ""


def _row_to_mcp(row: sqlite3.Row) -> MCPServer:
    return MCPServer(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        command=row["command"],
        args=json.loads(row["args_json"] or "[]"),
        env=json.loads(row["env_json"] or "{}"),
        tools=json.loads(row["tools_json"] or "[]"),
        status=row["status"] or "stopped",
        is_builtin=bool(row["is_builtin"]),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


class MCPStore:
    """SQLite CRUD for MCP server registry."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def list(self) -> list[MCPServer]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM mcps ORDER BY name").fetchall()
            return [_row_to_mcp(r) for r in rows]

    def get(self, mcp_id: str) -> Optional[MCPServer]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM mcps WHERE id=?", (mcp_id,)).fetchone()
            return _row_to_mcp(row) if row else None

    def create(self, mcp: MCPServer) -> MCPServer:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO mcps
                   (id, name, description, command, args_json, env_json, tools_json, status, is_builtin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mcp.id, mcp.name, mcp.description, mcp.command,
                 json.dumps(mcp.args), json.dumps(mcp.env), json.dumps(mcp.tools),
                 mcp.status, int(mcp.is_builtin)),
            )
            conn.commit()
        return mcp

    def update_status(self, mcp_id: str, status: str):
        with self._conn() as conn:
            conn.execute("UPDATE mcps SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (status, mcp_id))
            conn.commit()

    def update_tools(self, mcp_id: str, tools: list[dict]):
        with self._conn() as conn:
            conn.execute("UPDATE mcps SET tools_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (json.dumps(tools), mcp_id))
            conn.commit()

    def delete(self, mcp_id: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM mcps WHERE id=?", (mcp_id,))
            conn.commit()


# ── Builtin MCP definitions ─────────────────────────────────────

BUILTIN_MCPS = [
    MCPServer(
        id="mcp-fetch",
        name="Web Fetch",
        description="Fetch web pages, APIs, documentation. Converts HTML to markdown.",
        command="mcp-server-fetch",
        args=["--ignore-robots-txt"],
        tools=[
            {"name": "fetch", "description": "Fetch a URL and return content as markdown",
             "params": {"url": "string (required)", "max_length": "int (default 5000)",
                        "start_index": "int (default 0)", "raw": "bool (default false)"}},
        ],
        status="stopped",
        is_builtin=True,
    ),
    MCPServer(
        id="mcp-memory",
        name="Memory (KG)",
        description="Persistent knowledge graph memory. Store entities, relations, observations.",
        command="npx",
        args=["@modelcontextprotocol/server-memory"],
        tools=[
            {"name": "create_entities", "description": "Create named entities with type and observations",
             "params": {"entities": "list of {name, entityType, observations}"}},
            {"name": "create_relations", "description": "Create relations between entities",
             "params": {"relations": "list of {from, to, relationType}"}},
            {"name": "add_observations", "description": "Add observations to existing entities",
             "params": {"observations": "list of {entityName, contents}"}},
            {"name": "search_nodes", "description": "Search entities by query",
             "params": {"query": "string"}},
            {"name": "read_graph", "description": "Read entire knowledge graph", "params": {}},
            {"name": "open_nodes", "description": "Get specific entities by name",
             "params": {"names": "list of strings"}},
        ],
        status="stopped",
        is_builtin=True,
    ),
    MCPServer(
        id="mcp-playwright",
        name="Playwright Browser",
        description="Browser automation via MCP: navigate, click, fill, screenshot, accessibility snapshot. For E2E testing and QA evidence.",
        command="npx",
        args=["@playwright/mcp@latest", "--headless", "--no-sandbox", "--executable-path", "/opt/pw-browsers/chromium-1208/chrome-linux/chrome"],
        env={"PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers"},
        tools=[
            {"name": "browser_navigate", "description": "Navigate to URL",
             "params": {"url": "string"}},
            {"name": "browser_take_screenshot", "description": "Take PNG screenshot of current page",
             "params": {"name": "string", "selector": "string (optional)"}},
            {"name": "browser_click", "description": "Click element",
             "params": {"element": "string (description)", "ref": "string (element ref)"}},
            {"name": "browser_type", "description": "Type text into element",
             "params": {"element": "string", "ref": "string", "text": "string"}},
            {"name": "browser_snapshot", "description": "Get page accessibility snapshot",
             "params": {}},
        ],
        status="stopped",
        is_builtin=True,
    ),
    MCPServer(
        id="mcp-github",
        name="GitHub",
        description="GitHub issues, PRs, code search, actions via gh CLI.",
        command="gh",
        args=[],
        tools=[
            {"name": "github_issues", "description": "List/search issues",
             "params": {"owner": "string", "repo": "string", "state": "open|closed", "query": "string"}},
            {"name": "github_prs", "description": "List pull requests",
             "params": {"owner": "string", "repo": "string", "state": "open|closed"}},
            {"name": "github_code_search", "description": "Search code across repos",
             "params": {"query": "string"}},
            {"name": "github_actions", "description": "List workflow runs",
             "params": {"owner": "string", "repo": "string", "status": "string"}},
        ],
        status="available",
        is_builtin=True,
    ),
    MCPServer(
        id="mcp-solaris",
        name="Solaris Design System",
        description="Design System La Poste (Solaris) — Figma components, variants, WCAG patterns, design tokens, validation reports.",
        command="python3",
        args=["-m", "mcp_solaris.server"],
        tools=[
            {"name": "solaris_component", "description": "Get Figma component details: all variants, properties, component sets",
             "params": {"component": "string (required)", "summary_only": "bool (default true)"}},
            {"name": "solaris_variant", "description": "Get specific variant with exact Figma styles (borderRadius, padding, dimensions, colors)",
             "params": {"component": "string (required)", "properties": "object (optional filter)"}},
            {"name": "solaris_wcag", "description": "Get WCAG accessibility pattern for a component type",
             "params": {"pattern": "string (accordion|button|tabs|checkbox|combobox|dialog|radio-group|switch|breadcrumb|focus-visible|link|listbox|loader)"}},
            {"name": "solaris_knowledge", "description": "Query knowledge base: semantic HTML, WCAG patterns, DS best practices",
             "params": {"category": "string (1-semantic-html|2-wcag-patterns|3-ds-best-practices|4-interactive-behaviors)", "topic": "string (optional)"}},
            {"name": "solaris_validation", "description": "Get validation status for a component from latest report",
             "params": {"component": "string (optional)"}},
            {"name": "solaris_grep", "description": "Search in generated CSS/HTML/SCSS files",
             "params": {"pattern": "string (regex)", "file_type": "string (css|html|scss|all)"}},
            {"name": "solaris_list_components", "description": "List all 41 Figma components/families",
             "params": {}},
            {"name": "solaris_stats", "description": "Get overall Solaris statistics",
             "params": {}},
        ],
        status="available",
        is_builtin=True,
    ),
]


def seed_builtins(store: MCPStore):
    """Insert builtin MCPs if not already present."""
    existing = {m.id for m in store.list()}
    for mcp in BUILTIN_MCPS:
        if mcp.id not in existing:
            store.create(mcp)
            logger.info("Seeded builtin MCP: %s", mcp.id)


_store: Optional[MCPStore] = None


def get_mcp_store() -> MCPStore:
    global _store
    if _store is None:
        _store = MCPStore()
        seed_builtins(_store)
    return _store
