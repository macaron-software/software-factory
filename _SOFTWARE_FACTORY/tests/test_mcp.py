"""Tests for MCP platform tools — direct handler calls (no server needed)."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from platform.mcp_platform.server import handle_tool, TOOLS


class TestToolDefinitions:
    def test_all_tools_have_name(self):
        for t in TOOLS:
            assert "name" in t
            assert "description" in t
            assert "inputSchema" in t

    def test_minimum_tool_count(self):
        assert len(TOOLS) >= 14

    def test_tool_names_unique(self):
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names))


class TestPlatformAgents:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_agents", {})
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 10
        assert "id" in data[0]

    @pytest.mark.asyncio
    async def test_show(self):
        all_agents = json.loads(await handle_tool("platform_agents", {}))
        aid = all_agents[0]["id"]
        result = await handle_tool("platform_agents", {"agent_id": aid})
        data = json.loads(result)
        assert data["id"] == aid

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await handle_tool("platform_agents", {"agent_id": "fake-xxx"})
        data = json.loads(result)
        assert "error" in data


class TestPlatformProjects:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_projects", {})
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]

    @pytest.mark.asyncio
    async def test_show(self):
        projects = json.loads(await handle_tool("platform_projects", {}))
        pid = projects[0]["id"]
        result = await handle_tool("platform_projects", {"project_id": pid})
        data = json.loads(result)
        assert data["id"] == pid

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await handle_tool("platform_projects", {"project_id": "fake-xxx"})
        data = json.loads(result)
        assert "error" in data


class TestPlatformMissions:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_missions", {})
        data = json.loads(result)
        assert isinstance(data, list)


class TestPlatformFeatures:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_features", {"epic_id": "nonexistent"})
        data = json.loads(result)
        assert isinstance(data, list)


class TestPlatformSprints:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_sprints", {"mission_id": "nonexistent"})
        data = json.loads(result)
        assert isinstance(data, list)


class TestPlatformIncidents:
    @pytest.mark.asyncio
    async def test_list(self):
        result = await handle_tool("platform_incidents", {})
        data = json.loads(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_has_fields(self):
        result = await handle_tool("platform_incidents", {})
        data = json.loads(result)
        if data:
            assert "id" in data[0]
            assert "severity" in data[0]


class TestPlatformLLM:
    @pytest.mark.asyncio
    async def test_stats(self):
        result = await handle_tool("platform_llm", {})
        data = json.loads(result)
        assert "total_calls" in data or "error" in data


class TestPlatformSearch:
    @pytest.mark.asyncio
    async def test_search(self):
        result = await handle_tool("platform_search", {"query": "factory"})
        data = json.loads(result)
        assert "projects" in data
        assert "missions" in data

    @pytest.mark.asyncio
    async def test_empty_search(self):
        result = await handle_tool("platform_search", {"query": "xyznonexistent999"})
        data = json.loads(result)
        assert isinstance(data["projects"], list)


class TestPlatformMemory:
    @pytest.mark.asyncio
    async def test_global(self):
        result = await handle_tool("platform_memory", {})
        data = json.loads(result)
        assert isinstance(data, list)


class TestPlatformMetrics:
    @pytest.mark.asyncio
    async def test_metrics(self):
        result = await handle_tool("platform_metrics", {})
        data = json.loads(result)
        assert "agents" in data


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown(self):
        result = await handle_tool("nonexistent_tool", {})
        data = json.loads(result)
        assert "error" in data
