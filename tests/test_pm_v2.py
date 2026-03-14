"""Tests for PM v2 dynamic phase orchestrator.

Unit tests: pure functions (_build_dynamic_phase, _build_evidence)
Integration tests: mock LLM → _pm_checkpoint → verify phase decisions
"""
# Ref: feat-backlog
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from platform.workflows.store import (
    _build_dynamic_phase,
    _build_evidence,
    _build_agent_catalog,
    _PATTERN_CATALOG,
    _PHASE_TEMPLATES,
    _FEEDBACK_TYPES,
    _GATE_TYPES,
    WorkflowPhase,
)
from platform.patterns.store import PatternDef


# ── Unit Tests: _build_dynamic_phase ─────────────────────────────


class TestBuildDynamicPhase:
    """Test dynamic phase construction from PM JSON block."""

    def test_basic_phase_creation(self):
        block = {
            "decision": "phase",
            "phase": {
                "name": "QA Acceptance",
                "pattern": "loop",
                "team": ["qa-lead", "ac-adversarial"],
                "gate": "all_approved",
                "feedback": ["adversarial"],
                "max_iterations": 3,
                "task": "Validate AC for US-01",
            },
        }
        wphase, pdef = _build_dynamic_phase(block)

        assert isinstance(wphase, WorkflowPhase)
        assert isinstance(pdef, PatternDef)
        assert wphase.name == "QA Acceptance"
        assert wphase.gate == "all_approved"
        assert pdef.type == "loop"
        assert len(pdef.agents) == 2
        assert pdef.agents[0]["agent_id"] == "qa-lead"
        assert pdef.agents[1]["agent_id"] == "ac-adversarial"
        assert pdef.config["max_iterations"] == 3
        assert pdef.config["adversarial_guard"] is True

    def test_phase_id_auto_generated(self):
        block = {"phase": {"name": "Test Phase", "pattern": "solo", "team": ["dev"]}}
        wphase, pdef = _build_dynamic_phase(block)
        assert wphase.id.startswith("pm-")
        assert pdef.id.startswith("pm-pat-")

    def test_custom_phase_id(self):
        block = {"phase": {"id": "my-qa", "name": "QA", "pattern": "solo", "team": ["qa"]}}
        wphase, pdef = _build_dynamic_phase(block)
        assert wphase.id == "my-qa"
        assert pdef.id == "pm-pat-my-qa"

    def test_invalid_pattern_falls_back_to_sequential(self):
        block = {"phase": {"name": "Bad", "pattern": "nonexistent", "team": ["dev"]}}
        wphase, pdef = _build_dynamic_phase(block)
        assert pdef.type == "sequential"

    def test_empty_team_gets_fallback_agent(self):
        block = {"phase": {"name": "Solo", "pattern": "solo", "team": []}}
        wphase, pdef = _build_dynamic_phase(block)
        assert len(pdef.agents) == 1
        assert pdef.agents[0]["agent_id"] == "dev_fullstack"

    def test_no_team_key_gets_fallback(self):
        block = {"phase": {"name": "Solo", "pattern": "solo"}}
        wphase, pdef = _build_dynamic_phase(block)
        assert pdef.agents[0]["agent_id"] == "dev_fullstack"

    def test_feedback_adversarial_flag(self):
        block = {"phase": {"name": "X", "pattern": "loop", "team": ["qa"],
                           "feedback": ["adversarial"]}}
        _, pdef = _build_dynamic_phase(block)
        assert pdef.config.get("adversarial_guard") is True
        assert pdef.config.get("require_tool_validation") is None

    def test_feedback_tools_flag(self):
        block = {"phase": {"name": "X", "pattern": "solo", "team": ["dev"],
                           "feedback": ["tools"]}}
        _, pdef = _build_dynamic_phase(block)
        assert pdef.config.get("require_tool_validation") is True
        assert pdef.config.get("adversarial_guard") is None

    def test_feedback_both_flags(self):
        block = {"phase": {"name": "X", "pattern": "loop", "team": ["qa"],
                           "feedback": ["adversarial", "tools"]}}
        _, pdef = _build_dynamic_phase(block)
        assert pdef.config["adversarial_guard"] is True
        assert pdef.config["require_tool_validation"] is True

    def test_timeout_propagated(self):
        block = {"phase": {"name": "X", "pattern": "solo", "team": ["dev"],
                           "timeout": 300}}
        wphase, _ = _build_dynamic_phase(block)
        assert wphase.timeout == 300

    def test_all_catalog_patterns_accepted(self):
        for ptype in _PATTERN_CATALOG:
            block = {"phase": {"name": f"Test-{ptype}", "pattern": ptype, "team": ["dev"]}}
            _, pdef = _build_dynamic_phase(block)
            assert pdef.type == ptype, f"Pattern {ptype} not accepted"

    def test_wphase_pattern_id_matches_pdef_id(self):
        block = {"phase": {"name": "X", "pattern": "solo", "team": ["dev"]}}
        wphase, pdef = _build_dynamic_phase(block)
        assert wphase.pattern_id == pdef.id

    def test_config_agents_in_wphase(self):
        block = {"phase": {"name": "X", "pattern": "parallel",
                           "team": ["a1", "a2", "a3"]}}
        wphase, _ = _build_dynamic_phase(block)
        assert wphase.config["agents"] == ["a1", "a2", "a3"]


# ── Unit Tests: _build_evidence ──────────────────────────────────


class TestBuildEvidence:
    """Test evidence string construction from tool calls."""

    def test_no_tool_calls(self):
        ev = _build_evidence("success=True", None)
        assert "Result: success=True" in ev

    def test_empty_tool_calls(self):
        ev = _build_evidence("ok", [])
        assert "Result: ok" in ev

    def test_source_files_extracted(self):
        tc = [
            {"name": "code_write", "args": {"path": "/workspace/src/main.py"}},
            {"name": "code_write", "args": {"path": "/workspace/src/utils.py"}},
        ]
        ev = _build_evidence("ok", tc)
        assert "Files created (2)" in ev
        assert "main.py" in ev
        assert "utils.py" in ev

    def test_build_results_extracted(self):
        tc = [{"name": "build", "args": {"command": "npm run build"},
               "result": "Build successful"}]
        ev = _build_evidence("ok", tc)
        assert "Build:" in ev
        assert "npm run build" in ev

    def test_test_results_extracted(self):
        tc = [{"name": "test", "args": {"command": "pytest"},
               "result": "5 passed"}]
        ev = _build_evidence("ok", tc)
        assert "Tests:" in ev
        assert "5 passed" in ev

    def test_no_files_shows_none(self):
        tc = [{"name": "build", "args": {"command": "make"}, "result": "ok"}]
        ev = _build_evidence("ok", tc)
        assert "Files: NONE" in ev

    def test_no_build_shows_not_executed(self):
        tc = [{"name": "code_write", "args": {"path": "x.py"}}]
        ev = _build_evidence("ok", tc)
        assert "Build: NOT EXECUTED" in ev

    def test_no_tests_shows_not_executed(self):
        tc = [{"name": "code_write", "args": {"path": "x.py"}}]
        ev = _build_evidence("ok", tc)
        assert "Tests: NOT EXECUTED" in ev


# ── Unit Tests: Catalogs ─────────────────────────────────────────


class TestCatalogs:
    """Test catalog constants are well-formed."""

    def test_pattern_catalog_has_expected_entries(self):
        assert len(_PATTERN_CATALOG) >= 20

    def test_all_pattern_types_present(self):
        required = {"solo", "sequential", "parallel", "loop", "hierarchical",
                    "network", "router", "aggregator", "wave",
                    "human-in-the-loop", "composite", "blackboard", "map_reduce"}
        assert required.issubset(set(_PATTERN_CATALOG.keys()))

    def test_phase_templates_have_required_keys(self):
        for t in _PHASE_TEMPLATES:
            assert "id" in t
            assert "name" in t
            assert "pattern" in t
            assert t["pattern"] in _PATTERN_CATALOG
            assert "team_roles" in t
            assert "gate" in t
            assert t["gate"] in _GATE_TYPES

    def test_feedback_types_non_empty(self):
        assert len(_FEEDBACK_TYPES) >= 4

    def test_gate_types_non_empty(self):
        assert len(_GATE_TYPES) >= 4


# ── Integration Tests: _pm_checkpoint ────────────────────────────


class TestPMCheckpointIntegration:
    """Test PM checkpoint with mocked LLM responses."""

    @pytest.fixture
    def mock_agent_store(self):
        mock_store = MagicMock()
        mock_agent = MagicMock()
        mock_agent.id = "product"
        mock_agent.role = "product"
        mock_agent.skills = ["product-management"]
        mock_agent.tools = []
        mock_store.get.return_value = mock_agent
        mock_store.list_all.return_value = [mock_agent]
        return mock_store

    def _make_llm_response(self, decision_json: dict) -> MagicMock:
        resp = MagicMock()
        resp.content = json.dumps(decision_json)
        return resp

    @pytest.mark.asyncio
    async def test_pm_returns_next(self, mock_agent_store):
        from platform.workflows.store import _pm_checkpoint

        decision_json = {"decision": "next", "reason": "continue"}
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=self._make_llm_response(decision_json))

        with patch("platform.agents.store.get_agent_store", return_value=mock_agent_store), \
             patch("platform.llm.client.get_llm_client", return_value=mock_llm):
            result = await _pm_checkpoint(
                MagicMock(), "sess-1", "proj-1", "feature-design",
                "success=True", ["phase1 done"], ["phase1", "phase2"], "Build app"
            )
        assert result["decision"] == "next"

    @pytest.mark.asyncio
    async def test_pm_returns_phase_decision(self, mock_agent_store):
        from platform.workflows.store import _pm_checkpoint

        decision_json = {
            "decision": "phase",
            "phase": {
                "name": "QA Check",
                "pattern": "loop",
                "team": ["qa-lead"],
                "gate": "all_approved",
                "feedback": ["adversarial"],
                "max_iterations": 3,
                "task": "Verify all AC",
            },
            "reason": "Need QA before deploy",
        }
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=self._make_llm_response(decision_json))

        with patch("platform.agents.store.get_agent_store", return_value=mock_agent_store), \
             patch("platform.llm.client.get_llm_client", return_value=mock_llm):
            result = await _pm_checkpoint(
                MagicMock(), "sess-1", "proj-1", "dev-sprint",
                "success=True", ["dev done"], ["dev-sprint", "deploy"], "Build app"
            )
        assert result["decision"] == "phase"
        assert result["phase"]["pattern"] == "loop"
        assert result["phase"]["team"] == ["qa-lead"]

    @pytest.mark.asyncio
    async def test_pm_returns_done(self, mock_agent_store):
        from platform.workflows.store import _pm_checkpoint

        decision_json = {"decision": "done", "reason": "All AC met", "findings": "100% pass"}
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=self._make_llm_response(decision_json))

        with patch("platform.agents.store.get_agent_store", return_value=mock_agent_store), \
             patch("platform.llm.client.get_llm_client", return_value=mock_llm):
            result = await _pm_checkpoint(
                MagicMock(), "sess-1", "proj-1", "qa",
                "success=True", [], [], "Build app"
            )
        assert result["decision"] == "done"

    @pytest.mark.asyncio
    async def test_pm_handles_markdown_fences(self, mock_agent_store):
        from platform.workflows.store import _pm_checkpoint

        raw_resp = MagicMock()
        raw_resp.content = '```json\n{"decision": "loop", "phase_id": "dev", "reason": "fix"}\n```'
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=raw_resp)

        with patch("platform.agents.store.get_agent_store", return_value=mock_agent_store), \
             patch("platform.llm.client.get_llm_client", return_value=mock_llm):
            result = await _pm_checkpoint(
                MagicMock(), "s", "p", "qa", "fail", [], [], "goal"
            )
        assert result["decision"] == "loop"
        assert result["phase_id"] == "dev"

    @pytest.mark.asyncio
    async def test_pm_error_defaults_to_next(self, mock_agent_store):
        from platform.workflows.store import _pm_checkpoint

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM down"))

        with patch("platform.agents.store.get_agent_store", return_value=mock_agent_store), \
             patch("platform.llm.client.get_llm_client", return_value=mock_llm):
            result = await _pm_checkpoint(
                MagicMock(), "s", "p", "phase", "ok", [], [], "goal"
            )
        assert result["decision"] == "next"
        assert "error" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_pm_agent_defaults_to_next(self):
        from platform.workflows.store import _pm_checkpoint

        mock_store = MagicMock()
        mock_store.get.return_value = None

        with patch("platform.agents.store.get_agent_store", return_value=mock_store):
            result = await _pm_checkpoint(
                MagicMock(), "s", "p", "phase", "ok", [], [], "goal"
            )
        assert result["decision"] == "next"
        assert "no PM agent" in result["reason"]


# ── Integration Test: Dynamic phase in workflow queue ────────────


class TestDynamicPhaseWorkflowIntegration:
    """Test that a 'phase' PM decision results in proper queue manipulation."""

    def test_dynamic_phase_roundtrip(self):
        """Simulate: PM returns phase → build → insert in queue → lookup pattern."""
        pm_decision = {
            "decision": "phase",
            "phase": {
                "name": "Security Audit",
                "pattern": "network",
                "team": ["security-lead", "dev-senior", "critic"],
                "gate": "all_approved",
                "feedback": ["adversarial", "tools"],
                "max_iterations": 2,
                "task": "Audit all endpoints for OWASP Top 10",
            },
            "reason": "Pre-deploy security check",
        }

        wphase, pdef = _build_dynamic_phase(pm_decision)

        # Simulate workflow state
        _phase_queue = [WorkflowPhase(id="deploy", name="Deploy")]
        _phase_catalog = {"deploy": _phase_queue[0]}
        _dynamic_patterns = {}

        # Insert dynamic phase (as the finally block does)
        _dynamic_patterns[wphase.id] = pdef
        _phase_catalog[wphase.id] = wphase
        _phase_queue.insert(0, wphase)  # insert before deploy

        # Verify queue
        assert len(_phase_queue) == 2
        assert _phase_queue[0].name == "Security Audit"
        assert _phase_queue[1].id == "deploy"

        # Verify pattern lookup (as run_workflow does)
        lookup = _dynamic_patterns.get(wphase.id)
        assert lookup is not None
        assert lookup.type == "network"
        assert len(lookup.agents) == 3
        assert lookup.config["adversarial_guard"] is True
        assert lookup.config["require_tool_validation"] is True
        assert lookup.config["max_iterations"] == 2
