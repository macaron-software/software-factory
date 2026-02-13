"""Project Manager — CRUD for projects with Vision, Values, Agent Lead, Memory.

Extends the ProjectRegistry (read-only discovery) with write operations:
- Create new projects (or register existing dirs)
- Set Vision document
- Set Lean values
- Assign Agent Lead
- Track project-level memory
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# Default Lean values available
LEAN_VALUES = [
    {"id": "quality", "label": "Qualité > Vitesse", "desc": "Review obligatoire, adversarial activé"},
    {"id": "feedback", "label": "Feedback rapide", "desc": "Loops courtes, fail fast"},
    {"id": "no-waste", "label": "Éliminer le waste", "desc": "KISS, pas de code inutile"},
    {"id": "respect", "label": "Respect des personnes", "desc": "Collaboration, négociation > veto"},
    {"id": "kaizen", "label": "Amélioration continue", "desc": "Retrospective auto, XP agent"},
    {"id": "flow", "label": "Flux continu", "desc": "WIP limits, pas de blocage"},
    {"id": "zero-skip", "label": "Zero Skip", "desc": "JAMAIS de skip, FIX > SKIP"},
    {"id": "tdd", "label": "TDD First", "desc": "Red-Green-Refactor obligatoire"},
]


@dataclass
class Project:
    """A project with vision, values, and agent configuration."""
    id: str
    name: str
    path: str
    description: str = ""
    factory_type: str = "standalone"  # sf | mf | standalone
    domains: list[str] = field(default_factory=list)
    # New fields
    vision: str = ""              # VISION.md content or custom text
    values: list[str] = field(default_factory=list)  # Lean value IDs
    lead_agent_id: str = ""       # Default agent for this project
    agents: list[str] = field(default_factory=list)  # Assigned agent IDs
    active_pattern_id: str = ""   # Currently active pattern
    status: str = "active"        # active | paused | archived
    created_at: str = ""
    updated_at: str = ""

    @property
    def exists(self) -> bool:
        return Path(self.path).is_dir()

    @property
    def has_git(self) -> bool:
        p = Path(self.path)
        if (p / ".git").exists():
            return True
        try:
            r = subprocess.run(["git", "rev-parse", "--git-dir"],
                               cwd=self.path, capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    @property
    def vision_preview(self) -> str:
        """First 200 chars of vision for cards."""
        return (self.vision[:200] + "...") if len(self.vision) > 200 else self.vision

    def load_vision_from_file(self) -> str:
        """Try to load VISION.md from project root (NOT README.md — that's memory)."""
        for name in ("VISION.md", "vision.md"):
            p = Path(self.path) / name
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8")[:10000]
                except Exception:
                    pass
        return ""


class ProjectStore:
    """CRUD for projects in SQLite."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                factory_type TEXT DEFAULT 'standalone',
                domains_json TEXT DEFAULT '[]',
                vision TEXT DEFAULT '',
                values_json TEXT DEFAULT '[]',
                lead_agent_id TEXT DEFAULT '',
                agents_json TEXT DEFAULT '[]',
                active_pattern_id TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def list_all(self) -> list[Project]:
        conn = get_db()
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        conn.close()
        return [self._row_to_project(r) for r in rows]

    def get(self, project_id: str) -> Optional[Project]:
        conn = get_db()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        conn.close()
        return self._row_to_project(row) if row else None

    def create(self, p: Project) -> Project:
        if not p.id:
            p.id = p.name.lower().replace(" ", "-").replace("_", "-")[:30]
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO projects
            (id, name, path, description, factory_type, domains_json,
             vision, values_json, lead_agent_id, agents_json, active_pattern_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (p.id, p.name, p.path, p.description, p.factory_type,
              json.dumps(p.domains), p.vision, json.dumps(p.values),
              p.lead_agent_id, json.dumps(p.agents), p.active_pattern_id, p.status))
        conn.commit()
        conn.close()
        return p

    def update(self, p: Project) -> Project:
        conn = get_db()
        conn.execute("""
            UPDATE projects SET
                name=?, path=?, description=?, factory_type=?, domains_json=?,
                vision=?, values_json=?, lead_agent_id=?, agents_json=?,
                active_pattern_id=?, status=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (p.name, p.path, p.description, p.factory_type,
              json.dumps(p.domains), p.vision, json.dumps(p.values),
              p.lead_agent_id, json.dumps(p.agents), p.active_pattern_id,
              p.status, p.id))
        conn.commit()
        conn.close()
        return p

    def update_vision(self, project_id: str, vision: str):
        conn = get_db()
        conn.execute("UPDATE projects SET vision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                      (vision, project_id))
        conn.commit()
        conn.close()

    def delete(self, project_id: str):
        conn = get_db()
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.commit()
        conn.close()

    def seed_from_registry(self):
        """Import projects from ProjectRegistry (SF/MF yaml discovery) into DB."""
        from .registry import get_project_registry
        registry = get_project_registry()

        for info in registry.all():
            existing = self.get(info.id)
            if existing:
                continue  # Don't overwrite user customizations

            p = Project(
                id=info.id,
                name=info.name,
                path=info.path,
                description=info.description,
                factory_type=info.factory_type,
                domains=info.domains,
            )
            # Auto-load vision from file
            if p.exists:
                p.vision = p.load_vision_from_file()

            # Default values for SF projects
            if p.factory_type == "sf":
                p.values = ["quality", "feedback", "tdd", "zero-skip", "kaizen"]
                p.lead_agent_id = "brain"
            elif p.factory_type == "mf":
                p.values = ["quality", "feedback", "zero-skip"]
                p.lead_agent_id = "brain"
            else:
                p.values = ["quality", "feedback"]
                p.lead_agent_id = "lead-dev"

            self.create(p)
            logger.info("Seeded project %s (%s)", p.id, p.factory_type)

    def _row_to_project(self, row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            description=row["description"] or "",
            factory_type=row["factory_type"] or "standalone",
            domains=json.loads(row["domains_json"] or "[]"),
            vision=row["vision"] or "",
            values=json.loads(row["values_json"] or "[]"),
            lead_agent_id=row["lead_agent_id"] or "",
            agents=json.loads(row["agents_json"] or "[]"),
            active_pattern_id=row["active_pattern_id"] or "",
            status=row["status"] or "active",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )


# Singleton
_store: Optional[ProjectStore] = None


def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
