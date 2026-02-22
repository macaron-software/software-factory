"""Tests for the sf CLI — DB mode (offline, no server needed)."""
import json
import os
import subprocess
import sys
import pytest

SF = os.path.join(os.path.dirname(__file__), "..", "cli", "sf.py")
DB = os.path.join(os.path.dirname(__file__), "..", "data", "platform.db")

def sf(*args, json_out=False):
    """Run sf CLI and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, SF, "--db", "--db-path", DB, "--no-color"]
    if json_out:
        cmd.append("--json")
    cmd.extend(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return r.returncode, r.stdout, r.stderr


class TestStatus:
    def test_status(self):
        rc, out, _ = sf("status")
        assert rc == 0
        assert "ok" in out or "offline" in out

    def test_status_json(self):
        rc, out, _ = sf("status", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert data["status"] == "ok"
        assert "offline" in data["mode"]


class TestProjects:
    def test_list(self):
        rc, out, _ = sf("projects", "list")
        assert rc == 0
        assert "NAME" in out  # table header

    def test_list_json(self):
        rc, out, _ = sf("projects", "list", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "name" in data[0]

    def test_show(self):
        # Get first project id
        _, out, _ = sf("projects", "list", json_out=True)
        pid = json.loads(out)[0]["id"]
        rc, out, _ = sf("projects", "show", pid)
        assert rc == 0
        assert pid in out

    def test_show_not_found(self):
        rc, out, err = sf("projects", "show", "nonexistent-xxxx")
        assert "not found" in (out + err).lower()

    def test_vision(self):
        _, out, _ = sf("projects", "list", json_out=True)
        pid = json.loads(out)[0]["id"]
        rc, out, _ = sf("projects", "vision", pid)
        assert rc == 0


class TestMissions:
    def test_list(self):
        rc, out, _ = sf("missions", "list")
        assert rc == 0
        assert "NAME" in out

    def test_list_json(self):
        rc, out, _ = sf("missions", "list", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)

    def test_list_filter_status(self):
        rc, out, _ = sf("missions", "list", "--status", "active", json_out=True)
        assert rc == 0
        data = json.loads(out)
        for m in data:
            assert m["status"] == "active"

    def test_show(self):
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        if missions:
            mid = missions[0]["id"]
            rc, out, _ = sf("missions", "show", mid)
            assert rc == 0

    def test_children(self):
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        if missions:
            mid = missions[0]["id"]
            rc, out, _ = sf("missions", "children", mid)
            assert rc == 0

    def test_wsjf(self):
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        if missions:
            mid = missions[0]["id"]
            rc, out, _ = sf("missions", "wsjf", mid,
                           "--bv", "8", "--tc", "5", "--rr", "3", "--jd", "2")
            assert rc == 0
            assert "wsjf_score" in out

    def test_start_offline_error(self):
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        if missions:
            mid = missions[0]["id"]
            rc, out, err = sf("missions", "start", mid)
            assert "offline" in (out + err).lower() or "server" in (out + err).lower()

    def test_run_offline_error(self):
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        if missions:
            mid = missions[0]["id"]
            rc, out, err = sf("missions", "run", mid)
            assert "offline" in (out + err).lower() or "server" in (out + err).lower()


class TestAgents:
    def test_list(self):
        rc, out, _ = sf("agents", "list")
        assert rc == 0
        assert "NAME" in out

    def test_list_json(self):
        rc, out, _ = sf("agents", "list", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) > 10  # should have many agents

    def test_show(self):
        _, out, _ = sf("agents", "list", json_out=True)
        agents = json.loads(out)
        aid = agents[0]["id"]
        rc, out, _ = sf("agents", "show", aid)
        assert rc == 0
        assert aid in out

    def test_show_not_found(self):
        rc, out, err = sf("agents", "show", "fake-agent-xxx")
        assert "not found" in (out + err).lower()


class TestSessions:
    def test_list(self):
        rc, out, _ = sf("sessions", "list")
        assert rc == 0

    def test_list_json(self):
        rc, out, _ = sf("sessions", "list", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)

    def test_show(self):
        _, out, _ = sf("sessions", "list", json_out=True)
        sessions = json.loads(out)
        if sessions:
            sid = sessions[0]["id"]
            rc, out, _ = sf("sessions", "show", sid)
            assert rc == 0

    def test_create_offline_error(self):
        rc, out, err = sf("sessions", "create")
        assert "offline" in (out + err).lower() or "server" in (out + err).lower()


class TestFeatures:
    def test_list(self):
        # Get an epic id
        _, out, _ = sf("missions", "list", json_out=True)
        missions = json.loads(out)
        epics = [m for m in missions if m.get("type") == "epic"]
        if epics:
            rc, out, _ = sf("features", "list", epics[0]["id"])
            assert rc == 0


class TestIdeation:
    def test_list(self):
        rc, out, _ = sf("ideation", "list")
        assert rc == 0

    def test_start_offline_error(self):
        rc, out, err = sf("ideation", "start", "test prompt")
        assert "offline" in (out + err).lower() or "server" in (out + err).lower() or "api" in (out + err).lower()


class TestMetrics:
    def test_dora(self):
        rc, out, _ = sf("metrics", "dora")
        assert rc == 0

    def test_velocity(self):
        rc, out, _ = sf("metrics", "velocity")
        assert rc == 0

    def test_burndown(self):
        rc, out, _ = sf("metrics", "burndown")
        assert rc == 0

    def test_cycle_time(self):
        rc, out, _ = sf("metrics", "cycle-time")
        assert rc == 0


class TestLLM:
    def test_stats(self):
        rc, out, _ = sf("llm", "stats")
        assert rc == 0

    def test_usage(self):
        rc, out, _ = sf("llm", "usage")
        assert rc == 0

    def test_traces(self):
        rc, out, _ = sf("llm", "traces", "--limit", "5")
        assert rc == 0


class TestMemory:
    def test_global(self):
        rc, out, _ = sf("memory", "global")
        assert rc == 0

    def test_search(self):
        rc, out, _ = sf("memory", "search", "test")
        assert rc == 0


class TestIncidents:
    def test_list(self):
        rc, out, _ = sf("incidents", "list")
        assert rc == 0

    def test_list_json(self):
        rc, out, _ = sf("incidents", "list", json_out=True)
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)


class TestChaos:
    def test_history(self):
        rc, out, _ = sf("chaos", "history")
        assert rc == 0

    def test_trigger_offline_error(self):
        rc, out, err = sf("chaos", "trigger")
        assert "offline" in (out + err).lower()


class TestWatchdog:
    def test_metrics(self):
        rc, out, _ = sf("watchdog", "metrics")
        assert rc == 0


class TestAutoheal:
    def test_stats(self):
        rc, out, _ = sf("autoheal", "stats")
        assert rc == 0

    def test_trigger_offline_error(self):
        rc, out, err = sf("autoheal", "trigger")
        assert "offline" in (out + err).lower()


class TestSearch:
    def test_search(self):
        rc, out, _ = sf("search", "test")
        assert rc == 0


class TestExport:
    def test_export_epics(self):
        rc, out, _ = sf("export", "epics")
        assert rc == 0

    def test_export_features(self):
        rc, out, _ = sf("export", "features")
        assert rc == 0


class TestReleases:
    def test_releases(self):
        _, out, _ = sf("projects", "list", json_out=True)
        pid = json.loads(out)[0]["id"]
        rc, out, _ = sf("releases", pid)
        assert rc == 0


class TestNotifications:
    def test_status(self):
        rc, out, _ = sf("notifications", "status")
        assert rc == 0

    def test_test_offline_error(self):
        rc, out, err = sf("notifications", "test")
        assert "offline" in (out + err).lower()


class TestRuns:
    def test_list(self):
        rc, out, _ = sf("runs", "list")
        assert rc == 0

    def test_show_not_found(self):
        rc, out, err = sf("runs", "show", "fake-run-999")
        assert rc != 0 or "not found" in (out + err).lower()


class TestHelp:
    def test_main_help(self):
        rc, out, _ = sf("--help")
        assert rc == 0
        assert "ideation" in out
        assert "missions" in out
        assert "projects" in out

    def test_subcommand_help(self):
        for cmd in ["projects", "missions", "agents", "sessions", "ideation",
                     "features", "sprints", "metrics", "llm", "memory",
                     "chaos", "incidents", "autoheal"]:
            rc, out, _ = sf(cmd, "--help")
            assert rc == 0, f"{cmd} --help failed"
