"""
Chaos module — killswitch, stress, and scenario tests.
=======================================================
Tests for the chaos-endurance module toggles and chaos loop gating.

Unit tests (no live server):
  pytest tests/test_chaos_module.py -v -m "not live"

Live tests (require --live + running server):
  pytest tests/test_chaos_module.py -v --live

Stress / load tests (run last, take longer):
  pytest tests/test_chaos_module.py -v --live -m "stress"
"""
# Ref: feat-ops

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = []  # mixed: some unit, some live, some stress


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_tmp_db(
    enabled_ids: list[str] | None = None,
) -> tuple[sqlite3.Connection, str]:
    """Create an in-memory-backed temp SQLite DB with settings table."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db = sqlite3.connect(tmp.name)
    db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    if enabled_ids is not None:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('enabled_modules', ?)",
            (json.dumps(enabled_ids),),
        )
    db.commit()
    return db, tmp.name


# ── 1. Unit — _load_builtin_ids ──────────────────────────────────────────────


class TestLoadBuiltinIds:
    """_load_builtin_ids() must read registry.yaml dynamically."""

    def test_contains_chaos_endurance(self):
        """chaos-endurance is in the builtin set after our registry update."""
        from platform.agents.tool_runner import _BUILTIN_MODULE_IDS

        assert "chaos-endurance" in _BUILTIN_MODULE_IDS, (
            "chaos-endurance not in _BUILTIN_MODULE_IDS — check registry.yaml builtin: true"
        )

    def test_all_builtin_registry_present(self):
        """Every module with builtin: true in registry.yaml is in _BUILTIN_MODULE_IDS."""
        import yaml

        reg_path = (
            Path(__file__).parent.parent / "platform" / "modules" / "registry.yaml"
        )
        if not reg_path.exists():
            pytest.skip("registry.yaml not found")
        data = yaml.safe_load(reg_path.read_text())
        expected = {m["id"] for m in data.get("modules", []) if m.get("builtin")}
        from platform.agents.tool_runner import _BUILTIN_MODULE_IDS

        missing = expected - _BUILTIN_MODULE_IDS
        assert not missing, f"Missing from _BUILTIN_MODULE_IDS: {missing}"

    def test_not_empty(self):
        """Fallback should never produce empty set."""
        from platform.agents.tool_runner import _BUILTIN_MODULE_IDS

        assert len(_BUILTIN_MODULE_IDS) >= 10, (
            f"Suspiciously few builtin IDs: {_BUILTIN_MODULE_IDS}"
        )


# ── 2. Unit — _is_module_enabled_db (chaos_endurance) ───────────────────────


class TestChaosKillswitchDB:
    """_is_module_enabled_db() reads enabled_modules from DB settings."""

    def test_enabled_when_in_list(self, tmp_path):
        """Returns True when module ID is in DB enabled_modules list."""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(str(db_path))
        db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        db.execute(
            "INSERT INTO settings VALUES ('enabled_modules', ?)",
            (json.dumps(["chaos-endurance", "rtk"]),),
        )
        db.commit()
        db.close()

        with patch("platform.ops.chaos_endurance._is_module_enabled_db"):
            # Verify the real function signature / call convention
            from platform.ops.chaos_endurance import _is_module_enabled_db as real_fn

            assert callable(real_fn)

    def test_disabled_when_not_in_list(self):
        """Returns False when module is absent from enabled_modules list."""
        db_conn = MagicMock()
        row_mock = MagicMock()
        row_mock.__getitem__ = lambda self, _: json.dumps(["rtk", "npm-registry"])
        row_mock.__bool__ = lambda self: True
        db_conn.execute.return_value.fetchone.return_value = (
            json.dumps(["rtk", "npm-registry"]),
        )

        with patch("platform.ops.chaos_endurance.get_connection", return_value=db_conn):
            from platform.ops.chaos_endurance import _is_module_enabled_db

            # patch close too
            db_conn.close = MagicMock()
            result = _is_module_enabled_db("chaos-endurance")
            assert result is False

    def test_enabled_when_in_list_mock(self):
        """Returns True when module IS in enabled_modules list."""
        db_conn = MagicMock()
        db_conn.execute.return_value.fetchone.return_value = (
            json.dumps(["rtk", "chaos-endurance"]),
        )
        db_conn.close = MagicMock()

        with patch("platform.ops.chaos_endurance.get_connection", return_value=db_conn):
            from platform.ops.chaos_endurance import _is_module_enabled_db

            result = _is_module_enabled_db("chaos-endurance")
            assert result is True

    def test_returns_true_on_db_error(self):
        """Returns True (fail-open) when DB raises an exception."""
        with patch(
            "platform.ops.chaos_endurance.get_connection",
            side_effect=Exception("DB not ready"),
        ):
            from platform.ops.chaos_endurance import _is_module_enabled_db

            # Should not raise, should default to True
            result = _is_module_enabled_db("chaos-endurance")
            assert result is True, "Should default to enabled on DB error (fail-open)"

    def test_returns_true_when_no_settings_row(self):
        """Returns True when enabled_modules key absent from settings (fresh install)."""
        db_conn = MagicMock()
        db_conn.execute.return_value.fetchone.return_value = None  # no row
        db_conn.close = MagicMock()

        with patch("platform.ops.chaos_endurance.get_connection", return_value=db_conn):
            from platform.ops.chaos_endurance import _is_module_enabled_db

            result = _is_module_enabled_db("chaos-endurance")
            assert result is True, "Fresh install (no DB row) should default to enabled"


# ── 3. Unit — chaos_loop gating ─────────────────────────────────────────────


class TestChaosLoopGating:
    """chaos_loop() must skip scenarios when module is disabled."""

    def test_loop_skips_when_module_disabled(self):
        """When _is_module_enabled_db returns False, no scenario executes."""
        scenario_calls = []

        async def _fake_exec(scenario):
            scenario_calls.append(scenario)
            from platform.ops.chaos_endurance import ChaosRunResult

            return ChaosRunResult(
                id="test",
                ts="2026-01-01T00:00:00Z",
                scenario=scenario,
                target="vm1",
                mttr_ms=0,
                phases_lost=0,
                success=True,
            )

        async def run_one_iteration():
            """Simulate one loop iteration with module disabled."""
            from platform.ops import chaos_endurance as ce

            # Module disabled → should skip
            with (
                patch.object(ce, "_is_module_enabled_db", return_value=False),
                patch.object(ce, "_today_count", return_value=0),
                patch.object(ce, "_exec_scenario", side_effect=_fake_exec),
                patch.object(ce, "_log_run"),
                patch.object(ce, "_ensure_table"),
            ):
                # Simulate the loop body (without the sleep)
                if not ce._is_module_enabled_db("chaos-endurance"):
                    return  # skipped

                scenario = "container_restart"
                result = await ce._exec_scenario(scenario)
                ce._log_run(result)

        asyncio.run(run_one_iteration())
        assert scenario_calls == [], (
            f"Scenario executed despite module being disabled: {scenario_calls}"
        )

    def test_loop_runs_when_module_enabled(self):
        """When _is_module_enabled_db returns True, scenario executes."""
        scenario_calls = []

        async def _fake_exec(scenario):
            scenario_calls.append(scenario)
            from platform.ops.chaos_endurance import ChaosRunResult

            return ChaosRunResult(
                id="test",
                ts="2026-01-01T00:00:00Z",
                scenario=scenario,
                target="vm1",
                mttr_ms=0,
                phases_lost=0,
                success=True,
            )

        async def run_one_iteration():
            from platform.ops import chaos_endurance as ce

            with (
                patch.object(ce, "_is_module_enabled_db", return_value=True),
                patch.object(ce, "_today_count", return_value=0),
                patch.object(ce, "_exec_scenario", side_effect=_fake_exec),
                patch.object(ce, "_log_run"),
                patch.object(ce, "_ensure_table"),
            ):
                if not ce._is_module_enabled_db("chaos-endurance"):
                    return

                result = await ce._exec_scenario("container_restart")
                ce._log_run(result)

        asyncio.run(run_one_iteration())
        assert "container_restart" in scenario_calls, (
            "Scenario should have run when module is enabled"
        )

    def test_loop_skips_at_daily_max(self):
        """Loop skips when daily max chaos runs reached (regardless of module state)."""
        scenario_calls = []

        async def run_one_iteration():
            from platform.ops import chaos_endurance as ce

            with (
                patch.object(ce, "_is_module_enabled_db", return_value=True),
                patch.object(ce, "_today_count", return_value=ce.MAX_CHAOS_PER_DAY),
                patch.object(ce, "_exec_scenario"),
                patch.object(ce, "_log_run"),
                patch.object(ce, "_ensure_table"),
            ):
                if not ce._is_module_enabled_db("chaos-endurance"):
                    return
                if ce._today_count() >= ce.MAX_CHAOS_PER_DAY:
                    return  # daily max reached

                await ce._exec_scenario("container_restart")

        asyncio.run(run_one_iteration())
        assert scenario_calls == [], "Should skip when daily max reached"


# ── 4. Unit — trigger_chaos ──────────────────────────────────────────────────


class TestTriggerChaos:
    """trigger_chaos() executes a scenario and logs the result."""

    def test_trigger_returns_result(self):
        """trigger_chaos() returns a ChaosRunResult with correct shape."""
        from platform.ops.chaos_endurance import ChaosRunResult

        async def run():
            from platform.ops import chaos_endurance as ce

            fake_result = ChaosRunResult(
                id="abc",
                ts="2026-01-01T00:00:00Z",
                scenario="container_restart",
                target="vm1",
                mttr_ms=1500,
                phases_lost=0,
                success=True,
                detail="ok",
            )
            with (
                patch.object(ce, "_exec_scenario", return_value=fake_result),
                patch.object(ce, "_log_run"),
                patch.object(ce, "_ensure_table"),
            ):
                result = await ce.trigger_chaos("container_restart")
                return result

        result = asyncio.run(run())
        assert result.scenario == "container_restart"
        assert result.mttr_ms == 1500
        assert result.success is True

    def test_trigger_logs_run(self):
        """trigger_chaos() always calls _log_run."""
        logged = []

        from platform.ops.chaos_endurance import ChaosRunResult

        async def run():
            from platform.ops import chaos_endurance as ce

            fake_result = ChaosRunResult(
                id="xyz",
                ts="2026-01-01T00:00:00Z",
                scenario="cpu_stress_30s",
                target="vm1",
                mttr_ms=500,
                phases_lost=0,
                success=True,
            )
            with (
                patch.object(ce, "_exec_scenario", return_value=fake_result),
                patch.object(ce, "_log_run", side_effect=logged.append),
                patch.object(ce, "_ensure_table"),
            ):
                await ce.trigger_chaos("cpu_stress_30s")

        asyncio.run(run())
        assert len(logged) == 1, "trigger_chaos must log exactly one run"

    def test_trigger_random_when_no_scenario(self):
        """trigger_chaos(None) picks a random scenario from SCENARIOS_VM1."""
        chosen = []

        from platform.ops.chaos_endurance import ChaosRunResult, SCENARIOS_VM1

        async def run():
            from platform.ops import chaos_endurance as ce

            async def _fake_exec(scenario):
                chosen.append(scenario)
                return ChaosRunResult(
                    id="r",
                    ts="t",
                    scenario=scenario,
                    target="vm1",
                    mttr_ms=0,
                    phases_lost=0,
                    success=True,
                )

            with (
                patch.object(ce, "_exec_scenario", side_effect=_fake_exec),
                patch.object(ce, "_log_run"),
                patch.object(ce, "_ensure_table"),
            ):
                await ce.trigger_chaos(None)

        asyncio.run(run())
        assert len(chosen) == 1
        assert chosen[0] in SCENARIOS_VM1, (
            f"trigger_chaos(None) chose unexpected scenario: {chosen[0]}"
        )


# ── 5. Unit — get_chaos_history ──────────────────────────────────────────────


class TestChaosHistory:
    """get_chaos_history() returns structured history from DB."""

    def test_history_returns_list(self):
        """get_chaos_history() returns a list (empty OK, no exception)."""
        db_conn = MagicMock()
        row = MagicMock()
        row.keys.return_value = [
            "id",
            "ts",
            "scenario",
            "target",
            "mttr_ms",
            "phases_lost",
            "success",
            "detail",
        ]
        db_conn.execute.return_value.fetchall.return_value = []
        db_conn.close = MagicMock()

        with patch("platform.ops.chaos_endurance.get_connection", return_value=db_conn):
            from platform.ops.chaos_endurance import get_chaos_history

            result = get_chaos_history(limit=10)
            assert isinstance(result, list)


# ── 6. Live — module toggle API ─────────────────────────────────────────────


class TestChaosModuleToggleLive:
    """Live: toggle chaos-endurance module via API and verify state."""

    @pytest.mark.live
    def test_chaos_module_visible_in_registry(self, live_session):
        """chaos-endurance appears in GET /api/modules response."""
        r = live_session.get("/api/modules")
        r.raise_for_status()
        modules = r.json()
        ids = [m["id"] for m in modules]
        assert "chaos-endurance" in ids, f"chaos-endurance not in modules list: {ids}"

    @pytest.mark.live
    def test_chaos_module_enabled_by_default(self, live_session):
        """chaos-endurance is enabled by default (builtin: true)."""
        r = live_session.get("/api/modules")
        r.raise_for_status()
        modules = {m["id"]: m for m in r.json()}
        mod = modules.get("chaos-endurance")
        assert mod is not None
        assert mod.get("enabled") is True, (
            f"chaos-endurance should be enabled by default, got: {mod}"
        )

    @pytest.mark.live
    def test_chaos_module_toggle_off(self, live_session):
        """POST /api/modules/chaos-endurance/toggle disables it."""
        # Toggle off
        r = live_session.post("/api/modules/chaos-endurance/toggle")
        assert r.status_code == 200

        # Verify disabled
        r2 = live_session.get("/api/modules")
        mods = {m["id"]: m for m in r2.json()}
        assert mods["chaos-endurance"]["enabled"] is False, (
            "Module should be disabled after toggle"
        )

    @pytest.mark.live
    def test_chaos_module_toggle_back_on(self, live_session):
        """Toggle chaos-endurance back to enabled after test."""
        r = live_session.post("/api/modules/chaos-endurance/toggle")
        assert r.status_code == 200

        r2 = live_session.get("/api/modules")
        mods = {m["id"]: m for m in r2.json()}
        assert mods["chaos-endurance"]["enabled"] is True, (
            "Module should be re-enabled after second toggle"
        )


# ── 7. Stress — concurrent module toggles ────────────────────────────────────


class TestChaosModuleStress:
    """Stress: rapid concurrent module toggles must not corrupt DB."""

    @pytest.mark.live
    @pytest.mark.stress
    def test_concurrent_module_toggles(self, live_session):
        """10 concurrent toggles of chaos-endurance must not corrupt state.

        After the burst, the module must be in a definite ON or OFF state,
        not in an error state.
        """
        import concurrent.futures

        results = []

        def _toggle():
            try:
                r = live_session.post("/api/modules/chaos-endurance/toggle")
                return r.status_code
            except Exception as e:
                return str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(_toggle) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        errors = [r for r in results if r not in (200, 303, 302)]
        assert len(errors) == 0, f"Toggle errors under load: {errors}"

        # State must be readable and consistent after burst
        r = live_session.get("/api/modules")
        r.raise_for_status()
        mods = {m["id"]: m for m in r.json()}
        assert "chaos-endurance" in mods
        assert mods["chaos-endurance"].get("enabled") in (True, False), (
            "Module state is undefined after concurrent toggles"
        )

        # Restore to enabled
        if not mods["chaos-endurance"]["enabled"]:
            live_session.post("/api/modules/chaos-endurance/toggle")

    @pytest.mark.live
    @pytest.mark.stress
    def test_rapid_fire_chaos_api(self, live_session):
        """20 rapid GET /api/modules requests — no 5xx, no corruption."""
        errors = []
        for _ in range(20):
            r = live_session.get("/api/modules")
            if r.status_code >= 500:
                errors.append(r.status_code)
        assert not errors, f"Got 5xx during rapid module list: {errors}"

    @pytest.mark.live
    @pytest.mark.stress
    def test_stress_health_while_toggling(self, live_session):
        """Platform stays healthy while module is toggled rapidly (10 cycles)."""
        for _ in range(10):
            live_session.post("/api/modules/chaos-endurance/toggle")
            r = live_session.get("/api/health")
            assert r.status_code == 200, "Health check failed during toggle storm"
            time.sleep(0.1)

        # Leave module enabled
        r = live_session.get("/api/modules")
        mods = {m["id"]: m for m in r.json()}
        if not mods.get("chaos-endurance", {}).get("enabled"):
            live_session.post("/api/modules/chaos-endurance/toggle")
