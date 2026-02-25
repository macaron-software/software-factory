"""Plugin SDK — extend the platform with custom agents, tools, and MCP servers.

A plugin is a directory with a manifest.yaml:

    plugins/my-plugin/
      manifest.yaml      # Plugin metadata + declarations
      agents/             # Optional: YAML agent definitions
        analyst.yaml
      tools.py            # Optional: BaseTool subclasses
      mcps.yaml           # Optional: MCP server declarations

manifest.yaml format:
    id: my-plugin
    name: My Plugin
    version: 1.0.0
    description: Adds custom analysis agents
    author: team@example.com
    agents:              # References to agent YAML files
      - agents/analyst.yaml
    tools:               # References to tool classes in tools.py
      - AnalystTool
    mcps:                # MCP server declarations
      - id: my-mcp
        command: python3 -m my_mcp_server
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform.db"
_PLUGINS_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"


@dataclass
class PluginManifest:
    """Parsed plugin manifest."""

    id: str = ""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    agents: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    mcps: list[dict] = field(default_factory=list)
    path: Path = field(default_factory=Path)
    enabled: bool = True


def load_manifest(plugin_dir: Path) -> PluginManifest | None:
    """Load and validate a plugin manifest from a directory."""
    manifest_path = plugin_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning("No manifest.yaml in %s", plugin_dir)
        return None

    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("Failed to parse %s: %s", manifest_path, exc)
        return None

    if not data.get("id"):
        logger.error("Plugin manifest missing 'id' in %s", manifest_path)
        return None

    return PluginManifest(
        id=data["id"],
        name=data.get("name", data["id"]),
        version=data.get("version", "1.0.0"),
        description=data.get("description", ""),
        author=data.get("author", ""),
        agents=data.get("agents", []),
        tools=data.get("tools", []),
        mcps=data.get("mcps", []),
        path=plugin_dir,
        enabled=data.get("enabled", True),
    )


def load_plugin_agents(manifest: PluginManifest) -> list[dict]:
    """Load agent definitions from a plugin."""
    agents = []
    for agent_path in manifest.agents:
        full_path = manifest.path / agent_path
        if not full_path.exists():
            logger.warning("Agent file not found: %s", full_path)
            continue
        try:
            with open(full_path) as f:
                agent_data = yaml.safe_load(f)
            if agent_data:
                agent_data["_plugin"] = manifest.id
                agents.append(agent_data)
        except Exception as exc:
            logger.error("Failed to load agent %s: %s", full_path, exc)
    return agents


def load_plugin_tools(manifest: PluginManifest) -> list:
    """Load tool classes from a plugin's tools.py."""
    tools_path = manifest.path / "tools.py"
    if not tools_path.exists():
        return []

    try:
        spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}_tools", tools_path)
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        loaded = []
        for tool_name in manifest.tools:
            cls = getattr(module, tool_name, None)
            if cls is not None:
                loaded.append(cls)
            else:
                logger.warning("Tool class %s not found in %s", tool_name, tools_path)
        return loaded
    except Exception as exc:
        logger.error("Failed to load tools from %s: %s", tools_path, exc)
        return []


def _ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            version     TEXT DEFAULT '1.0.0',
            description TEXT DEFAULT '',
            author      TEXT DEFAULT '',
            path        TEXT NOT NULL,
            enabled     INTEGER DEFAULT 1,
            agents_count INTEGER DEFAULT 0,
            tools_count  INTEGER DEFAULT 0,
            mcps_count   INTEGER DEFAULT 0,
            installed_at TEXT DEFAULT (datetime('now'))
        )
    """)


def register_plugin(manifest: PluginManifest, db_path: Path | str | None = None) -> bool:
    """Register a plugin in the database."""
    db = sqlite3.connect(str(db_path or _DB_PATH))
    try:
        _ensure_table(db)
        db.execute(
            """INSERT OR REPLACE INTO plugins
               (id, name, version, description, author, path, enabled, agents_count, tools_count, mcps_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                manifest.id,
                manifest.name,
                manifest.version,
                manifest.description,
                manifest.author,
                str(manifest.path),
                1 if manifest.enabled else 0,
                len(manifest.agents),
                len(manifest.tools),
                len(manifest.mcps),
            ),
        )
        db.commit()
        return True
    except Exception as exc:
        logger.error("Failed to register plugin %s: %s", manifest.id, exc)
        return False
    finally:
        db.close()


def list_plugins(db_path: Path | str | None = None) -> list[dict]:
    """List all registered plugins."""
    db = sqlite3.connect(str(db_path or _DB_PATH))
    db.row_factory = sqlite3.Row
    try:
        _ensure_table(db)
        rows = db.execute("SELECT * FROM plugins ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def discover_plugins(plugins_dir: Path | None = None) -> list[PluginManifest]:
    """Discover all plugins in the plugins directory."""
    base = plugins_dir or _PLUGINS_DIR
    if not base.exists():
        return []

    manifests = []
    for item in sorted(base.iterdir()):
        if item.is_dir() and (item / "manifest.yaml").exists():
            manifest = load_manifest(item)
            if manifest:
                manifests.append(manifest)
    return manifests


def load_all_plugins(plugins_dir: Path | None = None, db_path: Path | str | None = None) -> dict:
    """Discover, load, and register all plugins. Returns summary."""
    manifests = discover_plugins(plugins_dir)
    summary = {"loaded": 0, "agents": 0, "tools": 0, "mcps": 0, "errors": []}

    for manifest in manifests:
        if not manifest.enabled:
            continue

        agents = load_plugin_agents(manifest)
        tools = load_plugin_tools(manifest)
        register_plugin(manifest, db_path)

        summary["loaded"] += 1
        summary["agents"] += len(agents)
        summary["tools"] += len(tools)
        summary["mcps"] += len(manifest.mcps)

        logger.info(
            "Plugin %s v%s loaded: %d agents, %d tools, %d MCPs",
            manifest.id,
            manifest.version,
            len(agents),
            len(tools),
            len(manifest.mcps),
        )

    return summary
