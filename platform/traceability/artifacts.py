"""Acceptance Criteria & User Journey stores — UUID-tagged traceability artifacts.

Fills the traceability gaps: AC and Journeys were previously stored as plain text
or JSON blobs without individual UUIDs. Now every artifact in the chain has a
proper ID: pers-{uuid-v4}, feat-{uuid-v4}, us-{uuid-v4}, ac-{uuid-v4},
jour-{uuid-v4}.

Tables created on first use (no manual migration needed).
"""
from __future__ import annotations
# Ref: feat-annotate, feat-quality

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


# ── UUID helper ──────────────────────────────────────────────────

def make_id(prefix: str) -> str:
    """Generate a standardized identifier: {prefix}-{uuid-v4}."""
    return f"{prefix}-{uuid.uuid4()}"


def is_prefixed_uuid(value: str, prefix: str) -> bool:
    """Return True when value matches {prefix}-{uuid-v4}."""
    expected_prefix = f"{prefix}-"
    if not value.startswith(expected_prefix):
        return False
    try:
        uuid.UUID(value[len(expected_prefix) :])
    except ValueError:
        return False
    return True


def make_trace_uuid(artifact_type: str, project_id: str, source_id: str) -> str:
    """Generate a stable canonical UUID for exported traceability entities."""
    seed = f"traceability::{artifact_type}::{project_id}::{source_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


# ── Acceptance Criteria ──────────────────────────────────────────

_AC_SCHEMA = """
CREATE TABLE IF NOT EXISTS acceptance_criteria (
    id          TEXT PRIMARY KEY,
    feature_id  TEXT NOT NULL,
    story_id    TEXT DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    given_text  TEXT NOT NULL DEFAULT '',
    when_text   TEXT NOT NULL DEFAULT '',
    then_text   TEXT NOT NULL DEFAULT '',
    and_text    TEXT DEFAULT '',
    status      TEXT DEFAULT 'pending',
    verified_by TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ac_feature ON acceptance_criteria(feature_id);
CREATE INDEX IF NOT EXISTS idx_ac_story   ON acceptance_criteria(story_id);
CREATE INDEX IF NOT EXISTS idx_ac_status  ON acceptance_criteria(status);
"""


@dataclass
class AcceptanceCriterion:
    id: str = ""
    feature_id: str = ""
    story_id: str = ""
    title: str = ""
    given_text: str = ""
    when_text: str = ""
    then_text: str = ""
    and_text: str = ""
    status: str = "pending"       # pending | pass | fail | skip
    verified_by: str = ""         # agent_id or "manual"
    created_at: str = ""
    updated_at: str = ""


class AcceptanceCriteriaStore:
    """CRUD for acceptance criteria linked to features and stories."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = get_db()
        try:
            for stmt in _AC_SCHEMA.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def create(self, ac: AcceptanceCriterion) -> AcceptanceCriterion:
        if not ac.id:
            ac.id = make_id("ac")
        now = datetime.now(timezone.utc).isoformat()
        if not ac.created_at:
            ac.created_at = now
        ac.updated_at = now
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO acceptance_criteria
                   (id, feature_id, story_id, title, given_text, when_text, then_text,
                    and_text, status, verified_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ac.id, ac.feature_id, ac.story_id, ac.title,
                 ac.given_text, ac.when_text, ac.then_text, ac.and_text,
                 ac.status, ac.verified_by, ac.created_at, ac.updated_at),
            )
            conn.commit()
        finally:
            conn.close()
        return ac

    def get(self, ac_id: str) -> AcceptanceCriterion | None:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM acceptance_criteria WHERE id = ?", (ac_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_ac(row) if row else None

    def list_by_feature(self, feature_id: str) -> list[AcceptanceCriterion]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM acceptance_criteria WHERE feature_id = ? ORDER BY created_at",
                (feature_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_ac(r) for r in rows]

    def list_by_story(self, story_id: str) -> list[AcceptanceCriterion]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM acceptance_criteria WHERE story_id = ? ORDER BY created_at",
                (story_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_ac(r) for r in rows]

    def update_status(self, ac_id: str, status: str, verified_by: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        try:
            cur = conn.execute(
                "UPDATE acceptance_criteria SET status=?, verified_by=?, updated_at=? WHERE id=?",
                (status, verified_by, now, ac_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete(self, ac_id: str) -> bool:
        conn = get_db()
        try:
            cur = conn.execute("DELETE FROM acceptance_criteria WHERE id=?", (ac_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def coverage_by_feature(self, feature_id: str) -> dict:
        """Return AC coverage stats for a feature."""
        acs = self.list_by_feature(feature_id)
        total = len(acs)
        passed = sum(1 for a in acs if a.status == "pass")
        failed = sum(1 for a in acs if a.status == "fail")
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pending": total - passed - failed,
            "coverage_pct": round(passed / max(total, 1) * 100),
        }

    def coverage_summary(self, feature_ids: list[str]) -> dict:
        """Aggregate AC coverage across multiple features."""
        total = passed = failed = 0
        for fid in feature_ids:
            cov = self.coverage_by_feature(fid)
            total += cov["total"]
            passed += cov["passed"]
            failed += cov["failed"]
        return {
            "total_ac": total,
            "passed": passed,
            "failed": failed,
            "pending": total - passed - failed,
            "coverage_pct": round(passed / max(total, 1) * 100),
        }


def _row_to_ac(row) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        id=row["id"],
        feature_id=row["feature_id"],
        story_id=row["story_id"] or "",
        title=row["title"] or "",
        given_text=row["given_text"] or "",
        when_text=row["when_text"] or "",
        then_text=row["then_text"] or "",
        and_text=row["and_text"] or "",
        status=row["status"] or "pending",
        verified_by=row["verified_by"] or "",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


# ── User Journeys ───────────────────────────────────────────────

_JOURNEY_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_journeys (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    persona_id  TEXT DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    steps_json  TEXT DEFAULT '[]',
    pain_points TEXT DEFAULT '',
    opportunities TEXT DEFAULT '',
    status      TEXT DEFAULT 'draft',
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_journey_project ON user_journeys(project_id);
CREATE INDEX IF NOT EXISTS idx_journey_persona ON user_journeys(persona_id);
"""


@dataclass
class UserJourney:
    id: str = ""
    project_id: str = ""
    persona_id: str = ""
    title: str = ""
    description: str = ""
    steps: list[dict] = field(default_factory=list)  # [{order, action, channel, emotion, pain}]
    pain_points: str = ""
    opportunities: str = ""
    status: str = "draft"         # draft | validated | tested
    created_at: str = ""
    updated_at: str = ""


class JourneyStore:
    """CRUD for user journeys linked to projects and personas."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = get_db()
        try:
            for stmt in _JOURNEY_SCHEMA.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def create(self, j: UserJourney) -> UserJourney:
        if not j.id:
            j.id = make_id("jour")
        now = datetime.now(timezone.utc).isoformat()
        if not j.created_at:
            j.created_at = now
        j.updated_at = now
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO user_journeys
                   (id, project_id, persona_id, title, description, steps_json,
                    pain_points, opportunities, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (j.id, j.project_id, j.persona_id, j.title, j.description,
                 json.dumps(j.steps, ensure_ascii=False),
                 j.pain_points, j.opportunities, j.status,
                 j.created_at, j.updated_at),
            )
            conn.commit()
        finally:
            conn.close()
        return j

    def get(self, journey_id: str) -> UserJourney | None:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM user_journeys WHERE id = ?", (journey_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_journey(row) if row else None

    def list_by_project(self, project_id: str) -> list[UserJourney]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM user_journeys WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_journey(r) for r in rows]

    def list_by_persona(self, persona_id: str) -> list[UserJourney]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM user_journeys WHERE persona_id = ? ORDER BY created_at",
                (persona_id,),
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_journey(r) for r in rows]

    def update(self, j: UserJourney) -> bool:
        j.updated_at = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        try:
            cur = conn.execute(
                """UPDATE user_journeys SET title=?, description=?, persona_id=?,
                   steps_json=?, pain_points=?, opportunities=?, status=?, updated_at=?
                   WHERE id=?""",
                (j.title, j.description, j.persona_id,
                 json.dumps(j.steps, ensure_ascii=False),
                 j.pain_points, j.opportunities, j.status,
                 j.updated_at, j.id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete(self, journey_id: str) -> bool:
        conn = get_db()
        try:
            cur = conn.execute("DELETE FROM user_journeys WHERE id=?", (journey_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def migrate_from_config(self, project_id: str, journeys_list: list[dict]) -> int:
        """Migrate journeys from project.config JSON to proper table rows."""
        count = 0
        for j_data in journeys_list:
            j = UserJourney(
                project_id=project_id,
                persona_id=j_data.get("persona_id", j_data.get("persona", "")),
                title=j_data.get("title", j_data.get("name", "")),
                description=j_data.get("description", ""),
                steps=j_data.get("steps", []),
                pain_points=j_data.get("pain_points", ""),
                opportunities=j_data.get("opportunities", ""),
                status=j_data.get("status", "draft"),
            )
            self.create(j)
            count += 1
        return count


def _row_to_journey(row) -> UserJourney:
    return UserJourney(
        id=row["id"],
        project_id=row["project_id"],
        persona_id=row["persona_id"] or "",
        title=row["title"] or "",
        description=row["description"] or "",
        steps=json.loads(row["steps_json"] or "[]"),
        pain_points=row["pain_points"] or "",
        opportunities=row["opportunities"] or "",
        status=row["status"] or "draft",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


# ── Singletons ───────────────────────────────────────────────────

def get_ac_store() -> AcceptanceCriteriaStore:
    return AcceptanceCriteriaStore()


def get_journey_store() -> JourneyStore:
    return JourneyStore()
