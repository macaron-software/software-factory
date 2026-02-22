"""Product Backlog — Epic → Feature → User Story hierarchy."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from ..db.migrations import get_db
from ..rbac import check_agent_permission, check_human_permission

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS features (
    id TEXT PRIMARY KEY,
    epic_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'backlog',
    story_points INTEGER DEFAULT 0,
    assigned_to TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS user_stories (
    id TEXT PRIMARY KEY,
    feature_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    story_points INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'backlog',
    sprint_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
"""


@dataclass
class FeatureDef:
    id: str = ""
    epic_id: str = ""      # FK → missions.id
    name: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    priority: int = 5
    status: str = "backlog"  # backlog|ready|in_progress|done|blocked
    story_points: int = 0
    assigned_to: str = ""
    created_at: str = ""
    completed_at: str | None = None


@dataclass
class UserStoryDef:
    id: str = ""
    feature_id: str = ""   # FK → features.id
    title: str = ""        # "En tant que... je veux... afin de..."
    description: str = ""
    acceptance_criteria: str = ""  # Gherkin Given/When/Then
    story_points: int = 0
    priority: int = 5
    status: str = "backlog"
    sprint_id: str = ""
    assigned_to: str = ""
    created_at: str = ""
    completed_at: str | None = None


class ProductBacklog:
    """CRUD for Features and User Stories linked to Epics (missions)."""

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        db = get_db()
        try:
            db.executescript(_SCHEMA)
            db.commit()
        finally:
            db.close()

    # ── Features ─────────────────────────────────────────────────

    def create_feature(self, feat: FeatureDef) -> FeatureDef:
        if not feat.id:
            feat.id = f"feat-{uuid.uuid4().hex[:6]}"
        if not feat.created_at:
            feat.created_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT INTO features (id, epic_id, name, description, acceptance_criteria,
                   priority, status, story_points, assigned_to, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (feat.id, feat.epic_id, feat.name, feat.description,
                 feat.acceptance_criteria, feat.priority, feat.status,
                 feat.story_points, feat.assigned_to, feat.created_at),
            )
            db.commit()
        finally:
            db.close()
        return feat

    def list_features(self, epic_id: str) -> list[FeatureDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM features WHERE epic_id=? ORDER BY priority DESC, created_at",
                (epic_id,),
            ).fetchall()
            return [self._row_to_feature(r) for r in rows]
        finally:
            db.close()

    def get_feature(self, feature_id: str) -> FeatureDef | None:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM features WHERE id=?", (feature_id,)).fetchone()
            return self._row_to_feature(row) if row else None
        finally:
            db.close()

    def update_feature_status(self, feature_id: str, status: str):
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status == "done" else None
            db.execute(
                "UPDATE features SET status=?, completed_at=? WHERE id=?",
                (status, completed, feature_id),
            )
            db.commit()
        finally:
            db.close()

    # ── User Stories ─────────────────────────────────────────────

    def create_story(self, story: UserStoryDef) -> UserStoryDef:
        if not story.id:
            story.id = f"us-{uuid.uuid4().hex[:6]}"
        if not story.created_at:
            story.created_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT INTO user_stories (id, feature_id, title, description,
                   acceptance_criteria, story_points, priority, status, sprint_id,
                   assigned_to, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (story.id, story.feature_id, story.title, story.description,
                 story.acceptance_criteria, story.story_points, story.priority,
                 story.status, story.sprint_id, story.assigned_to, story.created_at),
            )
            db.commit()
        finally:
            db.close()
        return story

    def list_stories(self, feature_id: str) -> list[UserStoryDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM user_stories WHERE feature_id=? ORDER BY priority DESC, created_at",
                (feature_id,),
            ).fetchall()
            return [self._row_to_story(r) for r in rows]
        finally:
            db.close()

    def stories_for_sprint(self, sprint_id: str) -> list[UserStoryDef]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM user_stories WHERE sprint_id=? ORDER BY priority DESC",
                (sprint_id,),
            ).fetchall()
            return [self._row_to_story(r) for r in rows]
        finally:
            db.close()

    def update_story_status(self, story_id: str, status: str):
        db = get_db()
        try:
            completed = datetime.utcnow().isoformat() if status == "done" else None
            db.execute(
                "UPDATE user_stories SET status=?, completed_at=? WHERE id=?",
                (status, completed, story_id),
            )
            db.commit()
        finally:
            db.close()

    def assign_story_to_sprint(self, story_id: str, sprint_id: str):
        db = get_db()
        try:
            db.execute(
                "UPDATE user_stories SET sprint_id=? WHERE id=?",
                (sprint_id, story_id),
            )
            db.commit()
        finally:
            db.close()

    # ── RBAC-checked operations ──────────────────────────────────

    def create_feature_as(self, feat: FeatureDef, actor_id: str, actor_type: str = "agent") -> FeatureDef:
        """Create feature with RBAC check."""
        self._check(actor_id, actor_type, "feature", "create")
        return self.create_feature(feat)

    def create_story_as(self, story: UserStoryDef, actor_id: str, actor_type: str = "agent") -> UserStoryDef:
        """Create user story with RBAC check."""
        self._check(actor_id, actor_type, "user_story", "create")
        return self.create_story(story)

    def update_feature_status_as(self, feature_id: str, status: str, actor_id: str, actor_type: str = "agent"):
        """Update feature status with RBAC check."""
        self._check(actor_id, actor_type, "feature", "update")
        self.update_feature_status(feature_id, status)

    def update_story_status_as(self, story_id: str, status: str, actor_id: str, actor_type: str = "agent"):
        """Update story status with RBAC check."""
        self._check(actor_id, actor_type, "user_story", "update")
        self.update_story_status(story_id, status)

    def _check(self, actor_id: str, actor_type: str, artifact: str, action: str):
        if actor_type == "agent":
            ok, reason = check_agent_permission(actor_id, artifact, action)
        else:
            ok, reason = check_human_permission(actor_id, artifact, action)
        if not ok:
            raise PermissionError(reason)

    # ── Stats ────────────────────────────────────────────────────

    def epic_progress(self, epic_id: str) -> dict:
        """Feature + story counts and progress for an epic."""
        db = get_db()
        try:
            features = db.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done FROM features WHERE epic_id=?",
                (epic_id,),
            ).fetchone()
            stories = db.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN us.status='done' THEN 1 ELSE 0 END) as done,
                          SUM(us.story_points) as total_points,
                          SUM(CASE WHEN us.status='done' THEN us.story_points ELSE 0 END) as done_points
                   FROM user_stories us
                   JOIN features f ON us.feature_id=f.id
                   WHERE f.epic_id=?""",
                (epic_id,),
            ).fetchone()
            return {
                "features_total": features["total"] or 0,
                "features_done": features["done"] or 0,
                "stories_total": stories["total"] or 0,
                "stories_done": stories["done"] or 0,
                "story_points_total": stories["total_points"] or 0,
                "story_points_done": stories["done_points"] or 0,
            }
        finally:
            db.close()

    # ── Internal ─────────────────────────────────────────────────

    def _row_to_feature(self, row) -> FeatureDef:
        return FeatureDef(
            id=row["id"], epic_id=row["epic_id"], name=row["name"],
            description=row["description"], acceptance_criteria=row["acceptance_criteria"],
            priority=row["priority"], status=row["status"],
            story_points=row["story_points"], assigned_to=row["assigned_to"],
            created_at=row["created_at"], completed_at=row["completed_at"],
        )

    def _row_to_story(self, row) -> UserStoryDef:
        return UserStoryDef(
            id=row["id"], feature_id=row["feature_id"], title=row["title"],
            description=row["description"], acceptance_criteria=row["acceptance_criteria"],
            story_points=row["story_points"], priority=row["priority"],
            status=row["status"], sprint_id=row["sprint_id"],
            assigned_to=row["assigned_to"], created_at=row["created_at"],
            completed_at=row["completed_at"],
        )


def get_product_backlog() -> ProductBacklog:
    return ProductBacklog()
