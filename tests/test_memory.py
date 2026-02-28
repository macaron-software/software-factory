"""Memory system tests — store, search, inject, compact, health.

Tests all 4 layers: pattern, project, global, and the compactor.
Run: pytest tests/test_memory.py -v
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["PLATFORM_ENV"] = "test"


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mem():
    from platform.memory.manager import get_memory_manager
    return get_memory_manager()


@pytest.fixture(scope="module")
def client():
    from platform.server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


PROJECT_ID = "test-memory-proj-001"
SESSION_ID = "test-session-001"


# ── Layer 3: Project Memory ───────────────────────────────────────

class TestProjectMemory:
    def test_store_and_get(self, mem):
        mem.project_store(PROJECT_ID, "stack", "FastAPI + React", category="architecture", confidence=0.9)
        entries = mem.project_get(PROJECT_ID, category="architecture")
        keys = [e["key"] for e in entries]
        assert "stack" in keys

    def test_upsert_updates_value(self, mem):
        mem.project_store(PROJECT_ID, "stack", "FastAPI v1", category="architecture", confidence=0.8)
        mem.project_store(PROJECT_ID, "stack", "FastAPI v2", category="architecture", confidence=0.9)
        entries = mem.project_get(PROJECT_ID, category="architecture")
        stack_entry = next(e for e in entries if e["key"] == "stack")
        assert "v2" in stack_entry["value"]

    def test_agent_role_isolation(self, mem):
        mem.project_store(PROJECT_ID, "pref", "use TypeScript", category="convention", agent_role="ux", confidence=0.8)
        mem.project_store(PROJECT_ID, "pref", "use Python", category="convention", agent_role="dev", confidence=0.8)

        ux_entries = mem.project_get(PROJECT_ID, category="convention", agent_role="ux")
        dev_entries = mem.project_get(PROJECT_ID, category="convention", agent_role="dev")

        ux_vals = [e["value"] for e in ux_entries if e["key"] == "pref"]
        dev_vals = [e["value"] for e in dev_entries if e["key"] == "pref"]

        assert any("TypeScript" in v for v in ux_vals)
        assert any("Python" in v for v in dev_vals)

    def test_role_get_includes_generic(self, mem):
        """Role-scoped get should also return entries with no role (generic)."""
        mem.project_store(PROJECT_ID, "shared-fact", "all teams use Git", category="convention", agent_role="", confidence=0.9)
        entries = mem.project_get(PROJECT_ID, category="convention", agent_role="dev_frontend")
        keys = [e["key"] for e in entries]
        assert "shared-fact" in keys

    def test_search_returns_results(self, mem):
        mem.project_store(PROJECT_ID, "auth-strategy", "JWT with refresh tokens", category="architecture", confidence=0.85)
        results = mem.project_search(PROJECT_ID, "JWT")
        assert len(results) >= 1
        assert any("JWT" in r.get("value", "") for r in results)


# ── Layer 4: Global Memory ────────────────────────────────────────

class TestGlobalMemory:
    def test_store_and_get(self, mem):
        mem.global_store("test-pattern", "use Repository pattern for DB access", category="architecture", confidence=0.85)
        entries = mem.global_get(category="architecture")
        keys = [e["key"] for e in entries]
        assert "test-pattern" in keys

    def test_occurrence_increments(self, mem):
        mem.global_store("repeated-key", "value v1", category="pattern", confidence=0.6, project_id="proj-a")
        mem.global_store("repeated-key", "value v2", category="pattern", confidence=0.7, project_id="proj-b")
        entries = mem.global_get(category="pattern")
        entry = next((e for e in entries if e["key"] == "repeated-key"), None)
        assert entry is not None
        assert entry["occurrences"] >= 2

    def test_confidence_boosts_with_occurrences(self, mem):
        # Multiple stores of same key should boost confidence
        initial = mem.global_get(category="pattern")
        entry = next((e for e in initial if e["key"] == "repeated-key"), None)
        assert entry is not None
        assert entry["confidence"] > 0.6  # was boosted

    def test_search(self, mem):
        mem.global_store("search-test", "Repository pattern reduces coupling", category="architecture", confidence=0.9)
        results = mem.global_search("Repository")
        assert len(results) >= 1


# ── Layer 2: Pattern Memory ───────────────────────────────────────

class TestPatternMemory:
    def test_store_and_get(self, mem):
        mem.pattern_store(SESSION_ID, "decision", "use async everywhere", category="architecture", author="lead_dev")
        entries = mem.pattern_get(SESSION_ID)
        assert len(entries) >= 1
        assert any(e["key"] == "decision" for e in entries)

    def test_search_by_author(self, mem):
        entries = mem.pattern_get(SESSION_ID, author="lead_dev")
        assert all(e["author_agent"] == "lead_dev" for e in entries)

    def test_pattern_search(self, mem):
        results = mem.pattern_search(SESSION_ID, "async")
        assert len(results) >= 1


# ── Compactor ────────────────────────────────────────────────────

class TestCompactor:
    def test_run_compaction_no_crash(self):
        from platform.memory.compactor import run_compaction
        stats = run_compaction()
        assert stats.errors == []

    def test_health_snapshot(self):
        from platform.memory.compactor import get_memory_health
        health = get_memory_health()
        assert "project" in health
        assert "global" in health
        assert "pattern" in health
        assert isinstance(health["project"]["total"], int)
        assert isinstance(health["global"]["total"], int)

    def test_compaction_prunes_stale_pattern(self, mem):
        from platform.memory.compactor import run_compaction, MAX_PATTERN_AGE_DAYS
        from platform.db.migrations import get_db

        # Insert an artificially old pattern entry
        conn = get_db()
        conn.execute(
            "INSERT INTO memory_pattern (session_id, key, value, type, author_agent, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now', ?))",
            ("old-session", "old-key", "old-value", "context", "test-agent",
             f"-{MAX_PATTERN_AGE_DAYS + 1} days"),
        )
        conn.commit()
        conn.close()

        stats = run_compaction()
        assert stats.pattern_pruned >= 1

    def test_compaction_compresses_oversized(self, mem):
        from platform.memory.compactor import run_compaction, MAX_VALUE_LEN

        oversized_value = "x" * (MAX_VALUE_LEN + 200)
        mem.project_store(PROJECT_ID, "oversized-key", oversized_value, category="test", confidence=0.9)

        stats = run_compaction()
        assert stats.project_compressed >= 1

        # Verify the value was truncated in DB
        from platform.db.migrations import get_db
        conn = get_db()
        entry = conn.execute(
            "SELECT value FROM memory_project WHERE project_id=? AND key=?",
            (PROJECT_ID, "oversized-key"),
        ).fetchone()
        conn.close()
        assert entry is not None
        assert len(entry["value"]) <= MAX_VALUE_LEN

    def test_compaction_deduplicates_global(self, mem):
        from platform.memory.compactor import run_compaction
        from platform.db.migrations import get_db

        # Insert two global entries with the same key (bypassing upsert)
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO memory_global (category, key, value, confidence, occurrences, projects_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("test-cat", "dupe-key", "value A", 0.7, 1, '["proj-x"]'),
        )
        conn.execute(
            "INSERT INTO memory_global (category, key, value, confidence, occurrences, projects_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("test-cat-2", "dupe-key", "value B", 0.6, 1, '["proj-y"]'),
        )
        conn.commit()
        conn.close()

        stats = run_compaction()
        assert stats.global_deduped >= 1

        # Should be only 1 entry with this key now
        conn = get_db()
        count = conn.execute(
            "SELECT count(*) as n FROM memory_global WHERE key='dupe-key'"
        ).fetchone()["n"]
        conn.close()
        assert count == 1


# ── API Endpoints ─────────────────────────────────────────────────

class TestMemoryAPI:
    def test_health_endpoint(self, client):
        r = client.get("/api/memory/health")
        assert r.status_code == 200
        data = r.json()
        assert "project" in data
        assert "global" in data
        assert "thresholds" in data

    def test_compact_endpoint(self, client):
        r = client.post("/api/memory/compact")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "pattern_pruned" in data
        assert "errors" in data

    def test_project_memory_api(self, client):
        r = client.get(f"/api/memory/project/{PROJECT_ID}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_project_memory_role_filter(self, client):
        r = client.get(f"/api/memory/project/{PROJECT_ID}?role=dev_frontend")
        assert r.status_code == 200

    def test_global_memory_api(self, client):
        r = client.get("/api/memory/global")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats_endpoint(self, client):
        r = client.get("/api/memory/stats")
        assert r.status_code == 200


# ── Prompt injection ─────────────────────────────────────────────

class TestPromptInjection:
    """Verify that memory is correctly injected into agent prompts."""

    def test_executor_gets_role_memory(self, mem):
        """Role-scoped memory appears in _build_system_prompt for executors."""
        from platform.agents.prompt_builder import _build_system_prompt
        from platform.agents.store import AgentDef
        from platform.agents.executor import ExecutionContext

        mem.project_store(
            PROJECT_ID, "test-inject-key", "inject-value-xyz",
            # Use classified role (same as prompt_builder retrieval)
            category="architecture", agent_role="dev", confidence=0.9
        )

        agent = AgentDef(id="dev-be-001", name="Dev Backend", role="dev_backend", skills=[])

        ctx = ExecutionContext(
            agent=agent,
            session_id="test-session",
            project_id=PROJECT_ID,
            project_path="",
            capability_grade="executor",
        )

        prompt = _build_system_prompt(ctx)
        assert "inject-value-xyz" in prompt, "Role-scoped memory should be injected in executor prompt"

    def test_organizer_gets_full_memory(self, mem):
        """Organizers get project_memory injected if available."""
        from platform.agents.prompt_builder import _build_system_prompt
        from platform.agents.store import AgentDef
        from platform.agents.executor import ExecutionContext

        agent = AgentDef(id="po-001", name="Product Owner", role="product_owner", skills=[])

        ctx = ExecutionContext(
            agent=agent,
            session_id="test-session",
            project_id=PROJECT_ID,
            project_path="",
            capability_grade="organizer",
            project_memory="Vision: build great software",
        )

        prompt = _build_system_prompt(ctx)
        assert "Vision: build great software" in prompt
