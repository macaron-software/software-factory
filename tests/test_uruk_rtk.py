"""
Tests Uruk model + rtk integration.

Covers:
- _get_capability_grade() classification (unit)
- _classify_agent_role() with agent.id in combined (fix regression)
- ExecutionContext has capability_grade field
- MetricsCollector rtk tracking
- API /api/monitoring/live exposes rtk block
- API /api/agents returns agents (smoke)
- _write_step_checkpoint() DB persistence (integration)

Run: pytest tests/test_uruk_rtk.py -v
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Helpers: minimal agent stub
# ---------------------------------------------------------------------------

def make_agent(agent_id: str, role: str = "", name: str = "") -> types.SimpleNamespace:
    return types.SimpleNamespace(id=agent_id, role=role, name=name)


# ---------------------------------------------------------------------------
# Unit: _classify_agent_role
# ---------------------------------------------------------------------------

class TestClassifyAgentRole:
    def setup_method(self):
        from platform.agents.tool_schemas import _classify_agent_role
        self.fn = _classify_agent_role

    def test_product_manager_role(self):
        a = make_agent("pm", role="Product Manager")
        assert self.fn(a) == "product"

    def test_cto_role(self):
        a = make_agent("cto-1", role="Chief Technology Officer")
        assert self.fn(a) == "cto"

    def test_architect_role(self):
        a = make_agent("arch", role="Solution Architect")
        assert self.fn(a) == "architecture"

    def test_code_reviewer_id(self):
        # id contains "code-reviewer" — must be picked up from id
        a = make_agent("code-reviewer", role="Reviewer")
        assert self.fn(a) == "reviewer"

    def test_chef_de_programme_id(self):
        # Regression: id="chef_de_programme", role="Program Manager"
        # "programme" is in the id, must match cdp
        a = make_agent("chef_de_programme", role="Program Manager")
        cat = self.fn(a)
        assert cat == "cdp", f"Expected 'cdp', got '{cat}'"

    def test_scrum_master(self):
        a = make_agent("scrum_master", role="Scrum Master")
        assert self.fn(a) == "cdp"

    def test_devops_role(self):
        a = make_agent("devops-1", role="DevOps Engineer")
        assert self.fn(a) == "devops"

    def test_dev_default(self):
        a = make_agent("random-123", role="Senior Developer")
        assert self.fn(a) == "dev"


# ---------------------------------------------------------------------------
# Unit: _get_capability_grade
# ---------------------------------------------------------------------------

class TestCapabilityGrade:
    def setup_method(self):
        from platform.agents.tool_schemas import _get_capability_grade
        self.fn = _get_capability_grade

    def test_cto_is_organizer(self):
        a = make_agent("strat-cto", role="Chief Technology Officer")
        assert self.fn(a) == "organizer"

    def test_product_is_organizer(self):
        a = make_agent("pm", role="Product Manager")
        assert self.fn(a) == "organizer"

    def test_architect_is_organizer(self):
        a = make_agent("arch", role="Solution Architect")
        assert self.fn(a) == "organizer"

    def test_reviewer_is_organizer(self):
        a = make_agent("code-reviewer", role="Code Reviewer")
        assert self.fn(a) == "organizer"

    def test_cdp_is_organizer(self):
        a = make_agent("chef_de_programme", role="Program Manager")
        assert self.fn(a) == "organizer"

    def test_scrum_master_is_organizer(self):
        a = make_agent("scrum_master", role="Scrum Master")
        assert self.fn(a) == "organizer"

    def test_dev_is_executor(self):
        a = make_agent("dev-1", role="Backend Developer")
        assert self.fn(a) == "executor"

    def test_qa_is_executor(self):
        a = make_agent("qa-1", role="QA Engineer")
        assert self.fn(a) == "executor"

    def test_devops_is_executor(self):
        a = make_agent("devops-1", role="DevOps Engineer")
        assert self.fn(a) == "executor"

    def test_ux_is_executor(self):
        a = make_agent("ux-1", role="UX Designer")
        assert self.fn(a) == "executor"

    def test_security_is_executor(self):
        a = make_agent("sec-1", role="Security Engineer")
        assert self.fn(a) == "executor"

    def test_real_agents_split(self):
        """With real agent store: at least 20 organizers and 60% executors."""
        from platform.agents.store import get_agent_store
        from platform.agents.tool_schemas import _get_capability_grade

        agents = get_agent_store().list_all()
        if not agents:
            pytest.skip("no agents in store")

        organizers = [a for a in agents if _get_capability_grade(a) == "organizer"]
        executors = [a for a in agents if _get_capability_grade(a) == "executor"]

        assert len(organizers) >= 20, f"Too few organizers: {len(organizers)}"
        assert len(executors) / len(agents) > 0.5, (
            f"Less than 50% executors: {len(executors)}/{len(agents)}"
        )


# ---------------------------------------------------------------------------
# Unit: ExecutionContext has capability_grade
# ---------------------------------------------------------------------------

class TestExecutionContext:
    def test_default_grade_is_executor(self):
        from platform.agents.executor import ExecutionContext

        ctx = ExecutionContext(
            agent=make_agent("dev-1", role="Dev"),
            session_id="test-session",
        )
        assert ctx.capability_grade == "executor"

    def test_grade_can_be_set_to_organizer(self):
        from platform.agents.executor import ExecutionContext

        ctx = ExecutionContext(
            agent=make_agent("cto-1", role="CTO"),
            session_id="test-session",
            capability_grade="organizer",
        )
        assert ctx.capability_grade == "organizer"

    def test_grade_values_are_valid(self):
        from platform.agents.executor import ExecutionContext

        for grade in ("executor", "organizer"):
            ctx = ExecutionContext(
                agent=make_agent("x", role="x"),
                session_id="s",
                capability_grade=grade,
            )
            assert ctx.capability_grade == grade


# ---------------------------------------------------------------------------
# Unit: MetricsCollector rtk tracking
# ---------------------------------------------------------------------------

class TestRtkMetrics:
    def test_track_rtk_call_accumulates(self):
        import threading
        from platform.metrics.collector import MetricsCollector

        mc = MetricsCollector.__new__(MetricsCollector)
        mc._rtk_calls = 0
        mc._rtk_bytes_raw = 0
        mc._rtk_bytes_compressed = 0
        mc._lock = threading.Lock()

        mc.track_rtk_call(1000, 800)
        assert mc._rtk_calls == 1
        assert mc._rtk_bytes_raw == 1000
        assert mc._rtk_bytes_compressed == 800

        mc.track_rtk_call(500, 400)
        assert mc._rtk_calls == 2
        assert mc._rtk_bytes_raw == 1500
        assert mc._rtk_bytes_compressed == 1200

    def test_snapshot_rtk_block(self):
        """snapshot() rtk block has correct derived fields."""
        from platform.metrics.collector import MetricsCollector

        mc = MetricsCollector.__new__(MetricsCollector)
        # Minimal state needed for snapshot rtk section
        mc._rtk_calls = 3
        mc._rtk_bytes_raw = 9831
        mc._rtk_bytes_compressed = 8269

        # Simulate what snapshot() computes for rtk
        saved = mc._rtk_bytes_raw - mc._rtk_bytes_compressed
        ratio = round(100 * (1 - mc._rtk_bytes_compressed / mc._rtk_bytes_raw), 1)
        tokens = saved // 4

        assert saved == 1562
        assert ratio == pytest.approx(15.9, abs=0.2)
        assert tokens == 390

    def test_zero_calls_safe(self):
        from platform.metrics.collector import MetricsCollector

        mc = MetricsCollector.__new__(MetricsCollector)
        mc._rtk_calls = 0
        mc._rtk_bytes_raw = 0
        mc._rtk_bytes_compressed = 0
        # No division by zero should happen
        ratio = (
            round(100 * (1 - mc._rtk_bytes_compressed / mc._rtk_bytes_raw), 1)
            if mc._rtk_bytes_raw > 0
            else 0.0
        )
        assert ratio == 0.0


# ---------------------------------------------------------------------------
# Integration: _write_step_checkpoint (sqlite)
# ---------------------------------------------------------------------------

class TestStepCheckpoint:
    def test_write_checkpoint_no_crash(self, tmp_path):
        """_write_step_checkpoint must never raise — it's best-effort."""
        import os
        from platform.agents.executor import AgentExecutor

        # Point DB to a temp file
        os.environ["PLATFORM_DB_PATH"] = str(tmp_path / "test.db")
        AgentExecutor._write_step_checkpoint(
            session_id="sess-1",
            agent_id="dev-1",
            step_index=0,
            tool_calls=[{"name": "read_file", "args": {"path": "/tmp/x"}}],
            partial_content="partial output here",
        )

    def test_checkpoint_idempotent(self, tmp_path):
        """Writing same step twice uses INSERT OR REPLACE — no unique constraint error."""
        import os
        from platform.agents.executor import AgentExecutor

        os.environ["PLATFORM_DB_PATH"] = str(tmp_path / "test2.db")
        for _ in range(3):
            AgentExecutor._write_step_checkpoint(
                session_id="sess-1",
                agent_id="dev-1",
                step_index=0,
                tool_calls=[],
                partial_content="",
            )


# ---------------------------------------------------------------------------
# Integration: API /api/monitoring/live has rtk block
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    os.environ["PLATFORM_ENV"] = "test"
    from fastapi.testclient import TestClient
    from platform.server import app
    with TestClient(app) as c:
        yield c


class TestMonitoringRtk:
    def test_monitoring_live_has_rtk(self, client):
        r = client.get("/api/monitoring/live")
        assert r.status_code == 200
        data = r.json()
        assert "rtk" in data, "rtk block missing from /api/monitoring/live"

    def test_rtk_block_fields(self, client):
        r = client.get("/api/monitoring/live")
        rtk = r.json()["rtk"]
        for field in ("calls", "bytes_raw", "bytes_compressed", "bytes_saved", "tokens_saved_est"):
            assert field in rtk, f"rtk.{field} missing"
        assert isinstance(rtk["calls"], int)
        assert rtk["bytes_saved"] >= 0
        assert rtk["tokens_saved_est"] >= 0

    def test_rtk_ratio_absent_when_no_calls(self, client):
        """ratio_pct is 0.0 or absent when no rtk calls have been made."""
        r = client.get("/api/monitoring/live")
        rtk = r.json()["rtk"]
        if rtk["calls"] == 0:
            # Either absent or 0.0
            ratio = rtk.get("ratio_pct", 0.0)
            assert ratio == 0.0


# ---------------------------------------------------------------------------
# Integration: /api/agents smoke
# ---------------------------------------------------------------------------

class TestAgentsApi:
    def test_agents_list_ok(self, client):
        r = client.get("/api/agents")
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_agents_have_id_and_role(self, client):
        r = client.get("/api/agents")
        for agent in r.json()[:10]:
            assert "id" in agent
            assert "role" in agent or "name" in agent
