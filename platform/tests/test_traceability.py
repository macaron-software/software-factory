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

import json
import sqlite3
import uuid

import pytest

# Never `import platform` at top level — shadows stdlib.
from platform.traceability.artifacts import (
    AcceptanceCriteriaStore,
    AcceptanceCriterion,
    JourneyStore,
    UserJourney,
    is_prefixed_uuid,
    make_id,
    make_trace_uuid,
)
from platform.traceability.chain import (
    NFTTest,
    NFTStore,
    Persona,
    export_project_traceability_sqlite,
    get_nft_store,
    get_persona_store,
    get_project_chain_report,
    list_project_trace_artifacts,
    record_trace_artifact,
    update_feature_coverage,
    validate_project_chain,
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
    project_id    TEXT DEFAULT '',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, link_type)
);
CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    name        TEXT DEFAULT '',
    description TEXT DEFAULT '',
    goal        TEXT DEFAULT '',
    status      TEXT DEFAULT 'planning',
    workflow_id TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS epics (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    name        TEXT DEFAULT '',
    description TEXT DEFAULT '',
    goal        TEXT DEFAULT '',
    status      TEXT DEFAULT 'planning',
    workflow_id TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS features (
    id          TEXT PRIMARY KEY,
    epic_id     TEXT NOT NULL,
    name        TEXT DEFAULT '',
    description TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    priority    INTEGER DEFAULT 5,
    status      TEXT DEFAULT 'backlog',
    story_points INTEGER DEFAULT 0,
    assigned_to TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS user_stories (
    id          TEXT PRIMARY KEY,
    title       TEXT DEFAULT '',
    feature_id  TEXT NOT NULL,
    description TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    story_points INTEGER DEFAULT 0,
    priority    INTEGER DEFAULT 5,
    status      TEXT DEFAULT 'backlog',
    sprint_id   TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS project_screens (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    page_url   TEXT DEFAULT '',
    svg_path   TEXT DEFAULT '',
    feature_id TEXT DEFAULT '',
    mission_id TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    monkeypatch.setattr("platform.traceability.chain.get_db", _get_db)
    monkeypatch.setattr("platform.traceability.store.get_db", _get_db)


def _sqlite_conn(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = _dict_factory
    return conn


# ── make_id ───────────────────────────────────────────────────────────────────


class TestMakeId:
    @pytest.mark.parametrize("prefix", ["ac", "feat", "us", "jour", "li"])
    def test_generates_proper_prefix(self, prefix):
        result = make_id(prefix)
        assert is_prefixed_uuid(result, prefix)
        uuid.UUID(result[len(prefix) + 1 :])

    def test_unique_ids(self):
        ids = {make_id("ac") for _ in range(50)}
        assert len(ids) == 50

    def test_make_trace_uuid_is_stable(self):
        left = make_trace_uuid("feature", "proj-alpha", "feat-1")
        right = make_trace_uuid("feature", "proj-alpha", "feat-1")
        other = make_trace_uuid("feature", "proj-alpha", "feat-2")
        assert left == right
        assert left != other
        uuid.UUID(left)


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


class TestProjectTraceabilityChain:
    def test_record_trace_artifact_reuses_uuid(self):
        artifact = record_trace_artifact(
            project_id="proj-trace",
            epic_id="mission-1",
            feature_id="feat-1",
            layer="code",
            artifact_key="src/auth.py",
            artifact_name="Auth handler",
            notes="initial",
        )
        updated = record_trace_artifact(
            project_id="proj-trace",
            epic_id="mission-1",
            feature_id="feat-1",
            layer="code",
            artifact_key="src/auth.py",
            artifact_name="Auth handler v2",
            notes="updated",
        )

        assert artifact.id == updated.id
        assert is_prefixed_uuid(artifact.id, "code")
        items = list_project_trace_artifacts("proj-trace", "code")
        assert len(items) == 1
        assert items[0].artifact_name == "Auth handler v2"
        assert items[0].notes == "updated"

    def test_project_chain_report_and_validate(self, db_path):
        conn = _sqlite_conn(db_path)
        conn.execute(
            "INSERT INTO missions (id, project_id, name, status) VALUES (?,?,?,?)",
            ("mission-a", "proj-alpha", "Alpha epic", "in_progress"),
        )
        conn.execute(
            "INSERT INTO missions (id, project_id, name, status) VALUES (?,?,?,?)",
            ("mission-b", "proj-alpha", "Beta epic", "planning"),
        )
        conn.execute(
            "INSERT INTO features (id, epic_id) VALUES (?,?)",
            ("feat-a", "mission-a"),
        )
        conn.execute(
            "INSERT INTO features (id, epic_id) VALUES (?,?)",
            ("feat-b", "mission-b"),
        )
        conn.execute(
            "INSERT INTO user_stories (id, title, feature_id) VALUES (?,?,?)",
            ("us-a", "Story A", "feat-a"),
        )
        conn.execute(
            "INSERT INTO user_stories (id, title, feature_id) VALUES (?,?,?)",
            ("us-b", "Story B", "feat-b"),
        )
        conn.execute(
            """INSERT INTO project_screens
               (id, project_id, name, feature_id, mission_id)
               VALUES (?,?,?,?,?)""",
            ("scr-a", "proj-alpha", "Screen A", "feat-a", "mission-a"),
        )
        conn.commit()
        conn.close()

        ac_store = AcceptanceCriteriaStore()
        ac_store.create(
            AcceptanceCriterion(
                feature_id="feat-a",
                story_id="us-a",
                title="AC A",
                given_text="given",
                when_text="when",
                then_text="then",
            )
        )
        ac_store.create(
            AcceptanceCriterion(
                feature_id="feat-b",
                story_id="us-b",
                title="AC B",
                given_text="given",
                when_text="when",
                then_text="then",
            )
        )

        persona = get_persona_store().create(
            Persona(project_id="proj-alpha", epic_id="mission-a", name="Admin", role="admin")
        )
        nft = get_nft_store().create(
            NFTTest(
                project_id="proj-alpha",
                epic_id="mission-a",
                feature_id="feat-a",
                nft_type="perf",
                name="Perf A",
                criterion="p95 < 200ms",
                result="pass",
            )
        )
        migration_store.create_link(
            persona.id,
            "persona",
            "feat-a",
            "feature",
            "persona",
            project_id="proj-alpha",
        )
        migration_store.create_link(
            "feat-a",
            "feature",
            nft.id,
            "nft_test",
            "nft",
            project_id="proj-alpha",
        )

        for layer, key, label in [
            ("ihm", "routes:/alpha", "Alpha route"),
            ("code", "src/alpha.py", "Alpha impl"),
            ("test_tu", "tests/test_alpha.py", "Alpha TU"),
            ("test_e2e", "playwright/alpha.spec.ts", "Alpha E2E"),
            ("crud", "GET /api/alpha", "Alpha CRUD"),
            ("rbac", "role:alpha-admin", "Alpha RBAC"),
        ]:
            art = record_trace_artifact(
                project_id="proj-alpha",
                epic_id="mission-a",
                feature_id="feat-a",
                layer=layer,
                artifact_key=key,
                artifact_name=label,
            )
            migration_store.create_link(
                "feat-a",
                "feature",
                art.id,
                layer,
                layer,
                project_id="proj-alpha",
            )

        art_b = record_trace_artifact(
            project_id="proj-alpha",
            epic_id="mission-b",
            feature_id="feat-b",
            layer="code",
            artifact_key="src/beta.py",
            artifact_name="Beta impl",
        )
        migration_store.create_link(
            "feat-b",
            "feature",
            art_b.id,
            "code",
            "code",
            project_id="proj-alpha",
        )

        update_feature_coverage("feat-a")
        update_feature_coverage("feat-b")

        report = get_project_chain_report("proj-alpha")
        assert report["project_id"] == "proj-alpha"
        assert report["epic_count"] == 2
        assert report["feature_count"] == 2
        assert report["persona_count"] == 1
        assert report["artifact_count"] >= 7
        assert report["gap_count"] == 1
        assert report["layer_coverage"]["code"] == 100
        assert report["layer_gap_counts"]["persona"] == 1

        feat_a = next(f for f in report["features"] if f["id"] == "feat-a")
        feat_b = next(f for f in report["features"] if f["id"] == "feat-b")
        uuid.UUID(feat_a["trace_uuid"])
        assert feat_a["coverage_pct"] == 100.0
        assert feat_a["missing"] == []
        assert feat_b["layers"]["code"] is True
        assert "persona" in feat_b["missing"]

        fail_check = validate_project_chain("proj-alpha", threshold=80)
        assert fail_check["verdict"] == "FAIL"
        assert fail_check["fully_covered_count"] == 1
        assert fail_check["fully_covered_pct"] == 50
        assert fail_check["gap_count"] == 1
        assert fail_check["gaps_truncated"] is False
        assert fail_check["layer_gap_counts"]["persona"] == 1

        pass_check = validate_project_chain("proj-alpha", threshold=50)
        assert pass_check["verdict"] == "PASS"
        assert pass_check["gaps"][0]["trace_uuid"]

    def test_validate_project_chain_counts_high_coverage_gap_as_gap(self, db_path):
        conn = _sqlite_conn(db_path)
        conn.execute(
            "INSERT INTO missions (id, project_id, name, status) VALUES (?,?,?,?)",
            ("mission-gap", "proj-gap", "Gap epic", "in_progress"),
        )
        conn.execute(
            "INSERT INTO features (id, epic_id, name) VALUES (?,?,?)",
            ("feat-gap", "mission-gap", "Gap feature"),
        )
        conn.execute(
            "INSERT INTO user_stories (id, title, feature_id) VALUES (?,?,?)",
            ("us-gap", "Gap story", "feat-gap"),
        )
        conn.execute(
            """INSERT INTO project_screens
               (id, project_id, name, feature_id, mission_id)
               VALUES (?,?,?,?,?)""",
            ("scr-gap", "proj-gap", "Gap screen", "feat-gap", "mission-gap"),
        )
        conn.commit()
        conn.close()

        AcceptanceCriteriaStore().create(
            AcceptanceCriterion(
                feature_id="feat-gap",
                story_id="us-gap",
                title="Gap AC",
                given_text="given",
                when_text="when",
                then_text="then",
            )
        )
        nft = NFTStore().create(
            NFTTest(
                project_id="proj-gap",
                epic_id="mission-gap",
                feature_id="feat-gap",
                nft_type="perf",
                name="Perf gap",
                criterion="p95 < 200ms",
                result="pass",
            )
        )
        migration_store.create_link(
            "feat-gap",
            "feature",
            nft.id,
            "nft_test",
            "nft",
            project_id="proj-gap",
        )
        for layer, key, label in [
            ("ihm", "routes:/gap", "Gap route"),
            ("code", "src/gap.py", "Gap impl"),
            ("test_tu", "tests/test_gap.py", "Gap TU"),
            ("test_e2e", "playwright/gap.spec.ts", "Gap E2E"),
            ("crud", "GET /api/gap", "Gap CRUD"),
            ("rbac", "role:gap-admin", "Gap RBAC"),
        ]:
            art = record_trace_artifact(
                project_id="proj-gap",
                epic_id="mission-gap",
                feature_id="feat-gap",
                layer=layer,
                artifact_key=key,
                artifact_name=label,
            )
            migration_store.create_link(
                "feat-gap",
                "feature",
                art.id,
                layer,
                layer,
                project_id="proj-gap",
            )

        update_feature_coverage("feat-gap")

        report = get_project_chain_report("proj-gap")
        feature = report["features"][0]
        assert feature["coverage_pct"] == 95.0
        assert feature["missing"] == ["persona"]
        assert report["gap_count"] == 1
        assert report["layer_gap_counts"]["persona"] == 1

        check = validate_project_chain("proj-gap", threshold=100)
        assert check["verdict"] == "FAIL"
        assert check["fully_covered_count"] == 0
        assert check["fully_covered_pct"] == 0
        assert check["gap_count"] == 1
        assert check["layer_gap_counts"]["persona"] == 1
        assert check["gaps"][0]["feature_id"] == "feat-gap"
        assert check["gaps"][0]["missing"] == ["persona"]

    def test_project_chain_report_uses_epics_table_on_pg(self, db_path, monkeypatch):
        monkeypatch.setattr("platform.traceability.chain._epic_table_name", lambda: "epics")
        AcceptanceCriteriaStore()

        conn = _sqlite_conn(db_path)
        conn.execute(
            "INSERT INTO epics (id, project_id, name, status) VALUES (?,?,?,?)",
            ("epic-pg", "proj-pg", "PG epic", "in_progress"),
        )
        conn.execute(
            "INSERT INTO features (id, epic_id, name) VALUES (?,?,?)",
            ("feat-pg", "epic-pg", "PG feature"),
        )
        conn.commit()
        conn.close()

        report = get_project_chain_report("proj-pg")

        assert report["project_id"] == "proj-pg"
        assert report["epic_count"] == 1
        assert report["feature_count"] == 1
        assert report["epics"][0]["id"] == "epic-pg"
        assert report["features"][0]["id"] == "feat-pg"

    def test_export_project_traceability_sqlite(self, db_path, tmp_path):
        conn = _sqlite_conn(db_path)
        conn.execute(
            "INSERT INTO missions (id, project_id, name, status) VALUES (?,?,?,?)",
            ("mission-export", "proj-export", "Export epic", "done"),
        )
        conn.execute(
            "INSERT INTO features (id, epic_id) VALUES (?,?)",
            ("feat-export", "mission-export"),
        )
        conn.execute(
            "INSERT INTO user_stories (id, title, feature_id) VALUES (?,?,?)",
            ("us-export", "Export story", "feat-export"),
        )
        conn.commit()
        conn.close()

        AcceptanceCriteriaStore().create(
            AcceptanceCriterion(
                feature_id="feat-export",
                story_id="us-export",
                title="Export AC",
                given_text="given",
                when_text="when",
                then_text="then",
            )
        )
        art = record_trace_artifact(
            project_id="proj-export",
            epic_id="mission-export",
            feature_id="feat-export",
            layer="code",
            artifact_key="src/export.py",
            artifact_name="Export impl",
        )
        migration_store.create_link(
            "feat-export",
            "feature",
            art.id,
            "code",
            "code",
            project_id="proj-export",
        )
        update_feature_coverage("feat-export")

        out = tmp_path / "proj-export-trace.sqlite"
        result = export_project_traceability_sqlite("proj-export", str(out))

        assert result["path"] == str(out)
        assert out.exists()
        assert result["gap_count"] == 1

        export_db = sqlite3.connect(out)
        try:
            meta = export_db.execute(
                "SELECT project_id, feature_count, e2e_verdict, uuid_policy FROM export_meta"
            ).fetchone()
            assert meta[0] == "proj-export"
            assert meta[1] == 1
            assert meta[3] == "canonical-v5 + source-id"

            feature_rows = export_db.execute(
                "SELECT COUNT(*) FROM feature_traceability_status"
            ).fetchone()[0]
            artifact_rows = export_db.execute(
                "SELECT COUNT(*) FROM traceability_artifacts"
            ).fetchone()[0]
            feature_uuid = export_db.execute(
                "SELECT trace_uuid FROM features WHERE id='feat-export'"
            ).fetchone()[0]
            registry_rows = export_db.execute(
                "SELECT COUNT(*) FROM uuid_registry"
            ).fetchone()[0]
            link_uuid = export_db.execute(
                "SELECT source_trace_uuid, target_trace_uuid FROM traceability_links LIMIT 1"
            ).fetchone()
            missing_json = export_db.execute(
                "SELECT missing_json FROM feature_traceability_status WHERE feature_id='feat-export'"
            ).fetchone()[0]
            assert feature_rows == 1
            assert artifact_rows == 1
            assert registry_rows >= 4
            assert "persona" in json.loads(missing_json)
            uuid.UUID(feature_uuid)
            uuid.UUID(link_uuid[0])
            uuid.UUID(link_uuid[1])
        finally:
            export_db.close()

    def test_semantic_source_ids_are_preserved_in_report_and_export(self, db_path, tmp_path):
        project_id = "software-factory"
        epic_id = "sf-epic-platform"
        feature_id = "sf-f-web-01"
        story_id = "sf-us-web-01"

        conn = _sqlite_conn(db_path)
        conn.execute(
            "INSERT INTO missions (id, project_id, name, status) VALUES (?,?,?,?)",
            (epic_id, project_id, "Plateforme Web SF", "in_progress"),
        )
        conn.execute(
            """INSERT INTO features
               (id, epic_id, name, description, acceptance_criteria)
               VALUES (?,?,?,?,?)""",
            (
                feature_id,
                epic_id,
                "Onboarding & configuration initiale",
                "Premier démarrage du produit SF.",
                "Le wizard fonctionne de bout en bout.",
            ),
        )
        conn.execute(
            "INSERT INTO user_stories (id, title, feature_id) VALUES (?,?,?)",
            (story_id, "Configurer la plateforme", feature_id),
        )
        conn.commit()
        conn.close()

        AcceptanceCriteriaStore().create(
            AcceptanceCriterion(
                feature_id=feature_id,
                story_id=story_id,
                title="Bootstrap SF",
                given_text="un administrateur SF",
                when_text="il lance le wizard",
                then_text="la plateforme est configurée",
            )
        )
        artifact = record_trace_artifact(
            project_id=project_id,
            epic_id=epic_id,
            feature_id=feature_id,
            layer="code",
            artifact_key="platform/web/routes/projects.py",
            artifact_name="Projects route",
        )
        migration_store.create_link(
            feature_id,
            "feature",
            artifact.id,
            "code",
            "code",
            project_id=project_id,
        )

        conn = _sqlite_conn(db_path)
        conn.execute(
            """UPDATE traceability_links
               SET project_id = ''
               WHERE source_id = ? AND target_id = ? AND link_type = 'code'""",
            (feature_id, artifact.id),
        )
        conn.commit()
        conn.close()

        update_feature_coverage(feature_id)

        report = get_project_chain_report(project_id)
        feature = next(item for item in report["features"] if item["id"] == feature_id)
        epic = next(item for item in report["epics"] if item["id"] == epic_id)
        expected_feature_uuid = make_trace_uuid("feature", project_id, feature_id)
        expected_epic_uuid = make_trace_uuid("epic", project_id, epic_id)

        assert report["uuid_policy"] == "canonical-v5 + source-id"
        assert feature["id"] == feature_id
        assert feature["trace_uuid"] == expected_feature_uuid
        assert feature["epic_id"] == epic_id
        assert feature["epic_trace_uuid"] == expected_epic_uuid
        assert epic["trace_uuid"] == expected_epic_uuid

        out = tmp_path / "software-factory-trace.sqlite"
        export_project_traceability_sqlite(project_id, str(out))

        export_db = sqlite3.connect(out)
        try:
            exported_feature = export_db.execute(
                "SELECT id, trace_uuid FROM features WHERE id=?",
                (feature_id,),
            ).fetchone()
            exported_epic = export_db.execute(
                "SELECT id, trace_uuid FROM epics WHERE id=?",
                (epic_id,),
            ).fetchone()
            feature_registry = export_db.execute(
                """SELECT source_id, display_id, trace_uuid
                   FROM uuid_registry
                   WHERE artifact_type='feature' AND source_id=? AND project_id=?""",
                (feature_id, project_id),
            ).fetchone()
            epic_registry = export_db.execute(
                """SELECT source_id, display_id, trace_uuid
                   FROM uuid_registry
                   WHERE artifact_type='epic' AND source_id=? AND project_id=?""",
                (epic_id, project_id),
            ).fetchone()
            exported_link = export_db.execute(
                """SELECT source_id, source_trace_uuid
                   FROM traceability_links
                   WHERE source_id=? AND target_id=? AND link_type='code'""",
                (feature_id, artifact.id),
            ).fetchone()

            assert exported_feature == (feature_id, expected_feature_uuid)
            assert exported_epic == (epic_id, expected_epic_uuid)
            assert feature_registry == (feature_id, feature_id, expected_feature_uuid)
            assert epic_registry == (epic_id, epic_id, expected_epic_uuid)
            assert exported_link == (feature_id, expected_feature_uuid)
        finally:
            export_db.close()
