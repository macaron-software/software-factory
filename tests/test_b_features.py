"""Tests for WebSocket, Multi-tenant, and DAG modules."""
import pytest
import json
import sqlite3


# ─── Multi-tenant tests ──────────────────────────────────────────────

class TestTenant:
    def test_get_project_db_creates(self, tmp_path, monkeypatch):
        import platform.db.tenant as tenant
        monkeypatch.setattr(tenant, "_PROJECTS_DIR", tmp_path / "projects")
        db = tenant.get_project_db("proj-1")
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        db.close()
        assert "missions" in tables
        assert "events" in tables
        assert "sprints" in tables

    def test_get_project_db_idempotent(self, tmp_path, monkeypatch):
        import platform.db.tenant as tenant
        monkeypatch.setattr(tenant, "_PROJECTS_DIR", tmp_path / "projects")
        db1 = tenant.get_project_db("proj-1")
        db1.execute("INSERT INTO missions (id, name) VALUES ('m1', 'Test')")
        db1.commit()
        db1.close()
        db2 = tenant.get_project_db("proj-1")
        row = db2.execute("SELECT name FROM missions WHERE id = 'm1'").fetchone()
        db2.close()
        assert row[0] == "Test"

    def test_list_project_dbs(self, tmp_path, monkeypatch):
        import platform.db.tenant as tenant
        monkeypatch.setattr(tenant, "_PROJECTS_DIR", tmp_path / "projects")
        tenant.get_project_db("alpha")
        tenant.get_project_db("beta")
        dbs = tenant.list_project_dbs()
        ids = [d["project_id"] for d in dbs]
        assert "alpha" in ids
        assert "beta" in ids

    def test_delete_project_db(self, tmp_path, monkeypatch):
        import platform.db.tenant as tenant
        monkeypatch.setattr(tenant, "_PROJECTS_DIR", tmp_path / "projects")
        tenant.get_project_db("to-delete")
        assert tenant.delete_project_db("to-delete") is True
        assert tenant.delete_project_db("to-delete") is False

    def test_safe_id_sanitization(self, tmp_path, monkeypatch):
        import platform.db.tenant as tenant
        monkeypatch.setattr(tenant, "_PROJECTS_DIR", tmp_path / "projects")
        db = tenant.get_project_db("../evil;DROP TABLE")
        db.close()
        files = list((tmp_path / "projects").glob("*.db"))
        assert len(files) == 1
        assert ".." not in files[0].name
        assert ";" not in files[0].name


# ─── DAG visualization tests ─────────────────────────────────────────

class TestDAG:
    def test_empty_workflow(self):
        from platform.web.routes.dag import _workflow_to_dag
        dag = _workflow_to_dag({"id": "w1", "phases": []})
        assert dag["nodes"] == []
        assert dag["edges"] == []

    def test_single_phase(self):
        from platform.web.routes.dag import _workflow_to_dag
        dag = _workflow_to_dag({
            "id": "w1",
            "name": "Test",
            "phases": [{"id": "p1", "name": "Init", "type": "task", "agent": "dev-agent"}]
        })
        assert len(dag["nodes"]) == 1
        assert dag["nodes"][0]["id"] == "p1"
        assert dag["nodes"][0]["agent"] == "dev-agent"
        assert dag["edges"] == []

    def test_sequential_edges(self):
        from platform.web.routes.dag import _workflow_to_dag
        dag = _workflow_to_dag({
            "id": "w1",
            "name": "Pipeline",
            "phases": [
                {"id": "build", "name": "Build"},
                {"id": "test", "name": "Test"},
                {"id": "deploy", "name": "Deploy"},
            ]
        })
        assert len(dag["edges"]) == 2
        assert dag["edges"][0] == {"from": "build", "to": "test", "type": "sequence"}
        assert dag["edges"][1] == {"from": "test", "to": "deploy", "type": "sequence"}

    def test_dependency_edges(self):
        from platform.web.routes.dag import _workflow_to_dag
        dag = _workflow_to_dag({
            "id": "w1",
            "name": "Complex",
            "phases": [
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B", "depends_on": ["a"]},
            ]
        })
        dep_edges = [e for e in dag["edges"] if e["type"] == "dependency"]
        assert len(dep_edges) == 1
        assert dep_edges[0]["from"] == "a"

    def test_condition_edges(self):
        from platform.web.routes.dag import _workflow_to_dag
        dag = _workflow_to_dag({
            "id": "w1",
            "name": "Branching",
            "phases": [
                {"id": "check", "name": "Check", "conditions": {"on_success": "deploy", "on_failure": "rollback"}},
                {"id": "deploy", "name": "Deploy"},
                {"id": "rollback", "name": "Rollback"},
            ]
        })
        success_edges = [e for e in dag["edges"] if e["type"] == "success"]
        failure_edges = [e for e in dag["edges"] if e["type"] == "failure"]
        assert len(success_edges) == 1
        assert len(failure_edges) == 1

    def test_ascii_rendering(self):
        from platform.web.routes.dag import _workflow_to_dag, _dag_to_ascii
        dag = _workflow_to_dag({
            "id": "w1",
            "name": "Pipeline",
            "phases": [
                {"id": "build", "name": "Build", "agent": "builder"},
                {"id": "test", "name": "Test"},
            ]
        })
        ascii_art = _dag_to_ascii(dag)
        assert "Build" in ascii_art
        assert "Test" in ascii_art
        assert "[builder]" in ascii_art


# ─── WebSocket ConnectionManager tests ───────────────────────────────

class TestConnectionManager:
    def test_stats_initial(self):
        from platform.web.routes.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.stats["connected"] == 0
        assert mgr.stats["messages_sent"] == 0

    def test_subscribe_unsubscribe(self):
        from platform.web.routes.websocket import ConnectionManager
        mgr = ConnectionManager()
        mgr._connections["c1"] = None  # mock
        mgr.subscribe("c1", "mission:m-1")
        assert "c1" in mgr._subscriptions["mission:m-1"]
        mgr.unsubscribe("c1", "mission:m-1")
        assert "c1" not in mgr._subscriptions.get("mission:m-1", set())

    def test_disconnect_cleans_subs(self):
        from platform.web.routes.websocket import ConnectionManager
        mgr = ConnectionManager()
        mgr._connections["c1"] = None
        mgr.subscribe("c1", "t1")
        mgr.subscribe("c1", "t2")
        mgr.disconnect("c1")
        assert "c1" not in mgr._connections
        assert "c1" not in mgr._subscriptions.get("t1", set())
        assert "c1" not in mgr._subscriptions.get("t2", set())
