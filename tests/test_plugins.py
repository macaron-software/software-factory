"""Tests for the plugin SDK."""
import pytest
from pathlib import Path

from platform.plugins import (
    PluginManifest,
    load_manifest,
    load_plugin_agents,
    load_plugin_tools,
    register_plugin,
    list_plugins,
    discover_plugins,
    load_all_plugins,
)


EXAMPLE_PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "example"


class TestManifest:
    def test_load_manifest(self):
        m = load_manifest(EXAMPLE_PLUGIN)
        assert m is not None
        assert m.id == "example"
        assert m.version == "1.0.0"
        assert len(m.agents) == 1
        assert len(m.tools) == 1

    def test_load_missing_dir(self, tmp_path):
        m = load_manifest(tmp_path / "nonexistent")
        assert m is None

    def test_load_no_id(self, tmp_path):
        (tmp_path / "manifest.yaml").write_text("name: test\n")
        m = load_manifest(tmp_path)
        assert m is None


class TestAgents:
    def test_load_agents(self):
        m = load_manifest(EXAMPLE_PLUGIN)
        agents = load_plugin_agents(m)
        assert len(agents) == 1
        assert agents[0]["id"] == "data-analyst"
        assert agents[0]["_plugin"] == "example"

    def test_missing_agent_file(self, tmp_path):
        m = PluginManifest(id="test", agents=["nonexistent.yaml"], path=tmp_path)
        agents = load_plugin_agents(m)
        assert agents == []


class TestTools:
    def test_load_tools(self):
        m = load_manifest(EXAMPLE_PLUGIN)
        tools = load_plugin_tools(m)
        assert len(tools) == 1
        assert tools[0].name == "data_format"

    def test_missing_tool_class(self, tmp_path):
        (tmp_path / "tools.py").write_text("class Foo: pass\n")
        m = PluginManifest(id="test", tools=["NonExistent"], path=tmp_path)
        tools = load_plugin_tools(m)
        assert tools == []


class TestRegistry:
    def test_register_and_list(self, tmp_path):
        db_path = tmp_path / "test.db"
        m = PluginManifest(id="test-plugin", name="Test", path=tmp_path)
        assert register_plugin(m, db_path) is True
        plugins = list_plugins(db_path)
        assert len(plugins) == 1
        assert plugins[0]["id"] == "test-plugin"


class TestDiscovery:
    def test_discover_example(self):
        plugins_dir = EXAMPLE_PLUGIN.parent
        manifests = discover_plugins(plugins_dir)
        assert len(manifests) >= 1
        ids = [m.id for m in manifests]
        assert "example" in ids

    def test_discover_empty(self, tmp_path):
        assert discover_plugins(tmp_path) == []

    def test_load_all(self, tmp_path):
        db_path = tmp_path / "test.db"
        plugins_dir = EXAMPLE_PLUGIN.parent
        summary = load_all_plugins(plugins_dir, db_path)
        assert summary["loaded"] >= 1
        assert summary["agents"] >= 1
        assert summary["tools"] >= 1
