"""Tests for platform.traceability module.

Covers:
  - make_id() prefix generation
  - AcceptanceCriteriaStore full CRUD + coverage
  - JourneyStore full CRUD + migrate_from_config
  - migration_store functions (legacy items, links, reports, matrix)
  - WhyLogStore (log_artifact, get_why, get_session_why)

Uses a temporary SQLite database — no PG, no real DB.
"""
# Ref: feat-quality
from __future__ import annotations

import sqlite3

import pytest

# Never `import platform` at top level — shadows stdlib.
from platform.traceability.artifacts import (
    AcceptanceCriteriaStore,
    AcceptanceCriterion,
    JourneyStore,
    UserJourney,
    make_id,
)
from platform.traceability import migration_store
from platform.traceability.store import get_session_why, get_why, log_artifact


# ── SQLite adapter (PG-compat wrapper) ────────────────────────────────────────


def _dict_factory(cursor, row):
    """Row factory that returns dicts (supports .get() unlike sqlite3.Row)."""
    return {col[0]: value for col, value in zip(cursor.description, row)}


class _PgCompatConnection:
    """Thin wrapper around sqlite3.Connection.

    Translates PG-style SQL to SQLite:
      %s → ?  |  TIMESTAMPTZ → TEXT  |  NOW() → CURRENT_TIMESTAMP
    """

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = _dict_factory

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        sql = sql.replace("TIMESTAMPTZ", "TEXT")
        sql = sql.replace("NOW()", "CURRENT_TIMESTAMP")
        if params is not None:
            return self._conn.execute(sql, tuple(params))
        return self._conn.execute(sql)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


# ── Schemas for tables not auto-created by the modules ────────────────────────

_EXTRA_SCHEMAS = """
CREATE TABLE IF NOT EXISTS legacy_items (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    item_type     TEXT NOT NULL,
    name          TEXT NOT NULL,
    parent_id     TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    source_file   TEXT DEFAULT '',
    source_line   INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'identified',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS traceability_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    link_type     TEXT NOT NULL,
    coverage_pct  INTEGER DEFAULT 0,
    notes         TEXT DEFAULT '',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, link_type)
);
CREATE TABLE IF NOT EXISTS epics (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS features (
    id      TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_stories (
    id         TEXT PRIMARY KEY,
    title      TEXT DEFAULT '',
    feature_id TEXT NOT NULL
);
"""


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_path(tmp_path):
    """Create a fresh temporary SQLite DB with migration_store schemas."""
    path = str(tmp_path / "test_traceability.db")
    conn = sqlite3.connect(path)
    for stmt in _EXTRA_SCHEMAS.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _patch_get_db(db_path, monkeypatch):
    """Redirect get_db() in all traceability modules to the temp SQLite DB."""

    def _get_db():
        return _PgCompatConnection(db_path)

    monkeypatch.setattr("platform.traceability.artifacts.get_db", _get_db)
    monkeypatch.setattr("platform.traceability.migration_store.get_db", _get_db)
    monkeypatch.setattr("platform.traceability.store.get_db", _get_db)


# ── make_id ───────────────────────────────────────────────────────────────────


class TestMakeId:
    @pytest.mark.parametrize("prefix", ["ac", "feat", "us", "jour", "li"])
    def test_generates_proper_prefix(self, prefix):
        result = make_id(prefix)
        assert result.startswith(f"{prefix}-")
        suffix = result[len(prefix) + 1 :]
        assert len(suffix) == 8
        int(suffix, 16)  # must be valid hex

    def test_unique_ids(self):
        ids = {make_id("ac") for _ in range(50)}
        assert len(ids) == 50


# ── AcceptanceCriteriaStore ───────────────────────────────────────────────────


class TestAcceptanceCriteriaStore:
    def test_create_and_get(self):
        store = AcceptanceCriteriaStore()
        ac = AcceptanceCriterion(
            feature_id="feat-001",
            story_id="us-001",
            title="Login AC",
            given_text="a registered user",
            when_text="they enter valid credentials",
            then_text="they are logged in",
        )
        created = store.create(ac)
        assert created.id.startswith("ac-")

        fetched = store.get(created.id)
        assert fetched is not None
        assert fetched.title == "Login AC"
        assert fetched.feature_id == "feat-001"
        assert fetched.given_text == "a registered user"

    def test_get_nonexistent_returns_none(self):
        store = AcceptanceCriteriaStore()
        assert store.get("ac-nonexistent") is None

    def test_list_by_feature(self):
        store = AcceptanceCriteriaStore()
        for i in range(3):
            store.create(AcceptanceCriterion(feature_id="feat-100", title=f"AC {i}"))
        store.create(AcceptanceCriterion(feature_id="feat-200", title="Other"))

        results = store.list_by_feature("feat-100")
        assert len(results) == 3
        assert all(r.feature_id == "feat-100" for r in results)

    def test_list_by_story(self):
        store = AcceptanceCriteriaStore()
        store.create(AcceptanceCriterion(feature_id="f1", story_id="us-10", title="A"))
        store.create(AcceptanceCriterion(feature_id="f1", story_id="us-10", title="B"))
        store.create(AcceptanceCriterion(feature_id="f1", story_id="us-20", title="C"))

        results = store.list_by_story("us-10")
        assert len(results) == 2

    def test_update_status(self):
        store = AcceptanceCriteriaStore()
        ac = store.create(AcceptanceCriterion(feature_id="f1", title="X"))
        assert store.update_status(ac.id, "pass", "qa-agent") is True

        updated = store.get(ac.id)
        assert updated.status == "pass"
        assert updated.verified_by == "qa-agent"

    def test_update_status_nonexistent(self):
        store = AcceptanceCriteriaStore()
        assert store.update_status("ac-ghost", "pass") is False

    def test_delete(self):
        store = AcceptanceCriteriaStore()
        ac = store.create(AcceptanceCriterion(feature_id="f1", title="Del"))
        assert store.delete(ac.id) is True
        assert store.get(ac.id) is None
        assert store.delete(ac.id) is False

    def test_coverage_by_feature(self):
        store = AcceptanceCriteriaStore()
        for status in ("pass", "pass", "fail", "pending"):
            store.create(
                AcceptanceCriterion(
                    feature_id="feat-cov", title=f"AC-{status}", status=status
                )
            )

        cov = store.coverage_by_feature("feat-cov")
        assert cov["total"] == 4
        assert cov["passed"] == 2
        assert cov["failed"] == 1
        assert cov["pending"] == 1
        assert cov["coverage_pct"] == 50

    def test_coverage_by_feature_empty(self):
        store = AcceptanceCriteriaStore()
        cov = store.coverage_by_feature("feat-empty")
        assert cov["total"] == 0
        assert cov["coverage_pct"] == 0

    def test_coverage_summary(self):
        store = AcceptanceCriteriaStore()
        store.create(AcceptanceCriterion(feature_id="f-a", status="pass"))
        store.create(AcceptanceCriterion(feature_id="f-a", status="fail"))
        store.create(AcceptanceCriterion(feature_id="f-b", status="pass"))

        summary = store.coverage_summary(["f-a", "f-b"])
        assert summary["total_ac"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pending"] == 0
        assert summary["coverage_pct"] == 67


# ── JourneyStore ──────────────────────────────────────────────────────────────


class TestJourneyStore:
    def test_create_and_get(self):
        store = JourneyStore()
        j = UserJourney(
            project_id="proj-1",
            persona_id="pers-admin",
            title="Admin onboarding",
            description="Full admin onboarding journey",
            steps=[{"order": 1, "action": "login", "channel": "web"}],
            pain_points="Too many steps",
            opportunities="Simplify",
        )
        created = store.create(j)
        assert created.id.startswith("jour-")

        fetched = store.get(created.id)
        assert fetched is not None
        assert fetched.title == "Admin onboarding"
        assert fetched.steps[0]["action"] == "login"

    def test_get_nonexistent_returns_none(self):
        store = JourneyStore()
        assert store.get("jour-ghost") is None

    def test_list_by_project(self):
        store = JourneyStore()
        store.create(UserJourney(project_id="p1", title="J1"))
        store.create(UserJourney(project_id="p1", title="J2"))
        store.create(UserJourney(project_id="p2", title="J3"))

        results = store.list_by_project("p1")
        assert len(results) == 2

    def test_list_by_persona(self):
        store = JourneyStore()
        store.create(UserJourney(project_id="p1", persona_id="pers-a", title="J1"))
        store.create(UserJourney(project_id="p1", persona_id="pers-a", title="J2"))
        store.create(UserJourney(project_id="p1", persona_id="pers-b", title="J3"))

        results = store.list_by_persona("pers-a")
        assert len(results) == 2

    def test_update(self):
        store = JourneyStore()
        j = store.create(UserJourney(project_id="p1", title="Original"))
        j.title = "Updated"
        j.status = "validated"
        assert store.update(j) is True

        fetched = store.get(j.id)
        assert fetched.title == "Updated"
        assert fetched.status == "validated"

    def test_delete(self):
        store = JourneyStore()
        j = store.create(UserJourney(project_id="p1", title="ToDelete"))
        assert store.delete(j.id) is True
        assert store.get(j.id) is None
        assert store.delete(j.id) is False

    def test_migrate_from_config(self):
        store = JourneyStore()
        config_journeys = [
            {
                "title": "Signup Flow",
                "persona_id": "pers-user",
                "description": "New user signup",
                "steps": [{"order": 1, "action": "fill form"}],
                "pain_points": "Complex form",
            },
            {
                "name": "Payment Flow",
                "persona": "pers-buyer",
                "steps": [],
            },
        ]
        count = store.migrate_from_config("proj-x", config_journeys)
        assert count == 2

        journeys = store.list_by_project("proj-x")
        assert len(journeys) == 2
        titles = {j.title for j in journeys}
        assert "Signup Flow" in titles
        assert "Payment Flow" in titles


# ── migration_store ───────────────────────────────────────────────────────────


class TestMigrationStore:
    def test_create_legacy_item(self):
        item_id = migration_store.create_legacy_item(
            project_id="proj-1",
            item_type="table",
            name="users",
            description="Main users table",
            metadata={"columns": 12},
            source_file="schema.sql",
            source_line=42,
        )
        assert item_id.startswith("li-")

        item = migration_store.get_legacy_item(item_id)
        assert item is not None
        assert item.name == "users"
        assert item.item_type == "table"
        assert item.metadata == {"columns": 12}
        assert item.source_file == "schema.sql"
        assert item.source_line == 42

    def test_list_legacy_items_with_filters(self):
        for name in ("tbl_a", "tbl_b"):
            migration_store.create_legacy_item("proj-f", "table", name)
        migration_store.create_legacy_item("proj-f", "endpoint", "/api/users")
        migration_store.create_legacy_item("proj-other", "table", "tbl_c")

        all_proj = migration_store.list_legacy_items("proj-f")
        assert len(all_proj) == 3

        tables_only = migration_store.list_legacy_items("proj-f", item_type="table")
        assert len(tables_only) == 2

    def test_count_legacy_items(self):
        migration_store.create_legacy_item("proj-c", "table", "t1")
        migration_store.create_legacy_item("proj-c", "table", "t2")
        migration_store.create_legacy_item("proj-c", "endpoint", "e1")

        counts = migration_store.count_legacy_items("proj-c")
        assert counts["table"] == 2
        assert counts["endpoint"] == 1

    def test_create_link(self):
        item_id = migration_store.create_legacy_item("p1", "table", "orders")
        link_id = migration_store.create_link(
            source_id=item_id,
            source_type="legacy_item",
            target_id="us-0001",
            target_type="story",
            link_type="covers",
            coverage_pct=80,
            notes="Partial coverage",
        )
        assert link_id > 0

        links = migration_store.get_links(item_id, direction="outgoing")
        assert len(links) == 1
        assert links[0].target_id == "us-0001"
        assert links[0].coverage_pct == 80

    def test_coverage_report(self):
        id1 = migration_store.create_legacy_item("proj-cov", "table", "t1")
        id2 = migration_store.create_legacy_item("proj-cov", "table", "t2")
        migration_store.create_legacy_item("proj-cov", "table", "t3")

        migration_store.create_link(id1, "legacy_item", "us-a", "story", "covers")
        migration_store.create_link(id2, "legacy_item", "us-b", "story", "covers")

        report = migration_store.coverage_report("proj-cov")
        assert "table" in report
        assert report["table"]["total"] == 3
        assert report["table"]["covered"] == 2
        assert report["_overall"]["total"] == 3
        assert report["_overall"]["covered"] == 2

    def test_orphan_report(self):
        id1 = migration_store.create_legacy_item("proj-orp", "table", "linked_tbl")
        id2 = migration_store.create_legacy_item("proj-orp", "table", "orphan_tbl")
        migration_store.create_link(id1, "legacy_item", "us-x", "story", "covers")

        report = migration_store.orphan_report("proj-orp")
        assert report["legacy_orphan_count"] == 1
        orphan_ids = [o["id"] for o in report["legacy_no_story"]]
        assert id2 in orphan_ids

    def test_traceability_matrix(self):
        item_id = migration_store.create_legacy_item("proj-mx", "table", "products")
        migration_store.create_link(
            item_id, "legacy_item", "feat-p1", "feature", "covers", 100
        )
        migration_store.create_link(
            item_id, "legacy_item", "src/products.py", "code", "migrates_from"
        )
        migration_store.create_link(
            item_id, "legacy_item", "test_products.py", "test", "tests"
        )

        matrix = migration_store.traceability_matrix("proj-mx")
        assert len(matrix) == 1
        entry = matrix[0]
        assert entry["legacy_id"] == item_id
        assert entry["name"] == "products"
        assert len(entry["stories"]) == 1
        assert len(entry["code"]) == 1
        assert len(entry["tests"]) == 1
        assert entry["fully_traced"] is True

    def test_traceability_matrix_not_fully_traced(self):
        item_id = migration_store.create_legacy_item("proj-mx2", "endpoint", "/api")
        migration_store.create_link(
            item_id, "legacy_item", "feat-x", "story", "covers"
        )

        matrix = migration_store.traceability_matrix("proj-mx2")
        assert len(matrix) == 1
        assert matrix[0]["fully_traced"] is False


# ── WhyLogStore (store.py) ────────────────────────────────────────────────────


class TestWhyLogStore:
    def test_log_artifact(self):
        row_id = log_artifact(
            session_id="sess-001",
            artifact_type="code",
            artifact_ref="src/auth.py",
            lineage=["vision", "epic-001", "feat-001", "us-001"],
            rationale="Implements login feature",
        )
        assert row_id is not None
        assert row_id > 0

    def test_get_why(self):
        log_artifact("sess-x", "test", "test_auth.py", ["feat-001", "ac-001"],
                     "Verifies login AC")
        log_artifact("sess-x", "code", "auth_handler.py", ["feat-001"],
                     "Auth handler")

        results = get_why("test_auth.py")
        assert len(results) == 1
        assert results[0].artifact_type == "test"
        assert results[0].lineage == ["feat-001", "ac-001"]
        assert results[0].rationale == "Verifies login AC"

    def test_get_why_partial_match(self):
        log_artifact("s1", "code", "src/models/user.py", ["feat-002"])
        results = get_why("user.py")
        assert len(results) >= 1

    def test_get_session_why(self):
        sid = "sess-full-chain"
        log_artifact(sid, "story", "us-100", ["epic-10"], "Story from epic")
        log_artifact(sid, "code", "users.py", ["us-100"], "Implements story")
        log_artifact(sid, "test", "test_users.py", ["us-100", "ac-100"], "Tests AC")

        entries = get_session_why(sid)
        assert len(entries) == 3
        assert entries[0].artifact_type == "story"
        assert entries[1].artifact_type == "code"
        assert entries[2].artifact_type == "test"

    def test_lineage_chain_property(self):
        log_artifact("s-lc", "code", "main.py", ["vision", "epic", "feat", "us"])
        entries = get_session_why("s-lc")
        assert entries[0].lineage_chain == "vision → epic → feat → us"

    def test_empty_results(self):
        assert get_why("nonexistent_file_xyz.py") == []
        assert get_session_why("sess-nonexistent") == []
