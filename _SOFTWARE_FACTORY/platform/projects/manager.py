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
        from ..agents.store import get_agent_store, AgentDef
        registry = get_project_registry()
        agent_store = get_agent_store()

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
            # Auto-load vision from file or workflow config
            if p.exists:
                p.vision = p.load_vision_from_file()
            if not p.vision:
                p.vision = self._load_vision_from_workflow(info.id)

            # Create a dedicated project agent
            agent_id = f"agent-{info.id}"
            if not agent_store.get(agent_id):
                agent = AgentDef(
                    id=agent_id,
                    name=info.name,
                    role="project-agent",
                    description=f"Conversational agent for {info.name}. Knows the codebase, can search files, read code, and answer questions.",
                    provider="minimax", model="MiniMax-M2.5",
                    temperature=0.5, max_tokens=4096,
                    icon="bot", color=_project_color(info.id),
                    avatar="bot", tagline=info.description[:60] if info.description else f"Your guide to {info.name}",
                    is_builtin=True,
                    tags=["project", info.factory_type or "general"],
                    system_prompt=f"You are the project agent for {info.name}.\n"
                    f"Project path: {info.path}\n"
                    f"Type: {info.factory_type or 'general'}\n"
                    "You help the team understand the codebase, find files, explain architecture, "
                    "and answer questions. You can trigger deep search (RLM) for complex queries. "
                    "Be concise, precise, and helpful.",
                )
                agent_store.create(agent)

            p.lead_agent_id = agent_id

            if p.factory_type == "sf":
                p.values = ["quality", "feedback", "tdd", "zero-skip", "kaizen"]
            elif p.factory_type == "mf":
                p.values = ["quality", "feedback", "zero-skip"]
            else:
                p.values = ["quality", "feedback"]

            self.create(p)
            logger.info("Seeded project %s (%s) with agent %s", p.id, p.factory_type, agent_id)

        # Auto-create sessions for projects with linked workflows
        self._seed_workflow_sessions()

        # Seed DSI project (Macaron Platform itself)
        self._seed_dsi_project()

    def _seed_dsi_project(self):
        """Seed the Software Factory as a DSI project pointing to its own codebase."""
        if self.get("software-factory"):
            return
        from ..config import PLATFORM_ROOT
        plat_path = str(PLATFORM_ROOT)
        p = Project(
            id="software-factory",
            name="Software Factory",
            path=plat_path,
            description="Plateforme multi-agent SAFe. FastAPI + HTMX + SSE + SQLite. Self-improving: les agents lisent et écrivent dans leur propre codebase.",
            factory_type="standalone",
            domains=["backend", "frontend", "agents", "patterns", "infra"],
            vision=(
                "Macaron Agent Platform — Real Agentic ≠ Workflow Automation.\n"
                "Agents collaborent (débat/véto/délégation) pour produire du code.\n"
                "128 agents SAFe, 23 patterns, 12 workflows, 1222 skills.\n"
                "Stack: FastAPI + Jinja2 + HTMX + SSE + SQLite (WAL + FTS5).\n"
                "Dark purple theme. Zero emoji. SVG Feather icons.\n\n"
                "2 Epics:\n"
                "1. NEW FEATURES — Discovery → Comité Strat → Arch → Dev Sprint → QA → Deploy → Retro\n"
                "2. TMA — Détection → Triage P0-P4 → Diagnostic → Fix TDD → Non-Régression → Hotfix Deploy"
            ),
            values=["quality", "feedback", "no-waste", "kaizen", "flow", "tdd"],
            lead_agent_id="dsi",
            agents=[
                "dsi", "strat-cpo", "strat-cto", "strat-portfolio", "architecte",
                "plat-lead-dev", "plat-dev-backend", "plat-dev-frontend",
                "plat-dev-agents", "plat-dev-patterns", "plat-dev-infra", "plat-product",
                "plat-tma-lead", "plat-tma-dev-back", "plat-tma-dev-front",
                "plat-tma-dev-agents", "plat-tma-qa",
                "qa_lead", "securite", "devops", "sre", "scrum_master", "ux_designer",
                "performance_engineer", "pipeline_engineer", "devsecops", "test_automation",
                "tech_writer", "lean_portfolio_manager",
            ],
            status="active",
        )
        self.create(p)
        logger.info("Seeded DSI project: software-factory → %s", plat_path)

    def _load_vision_from_workflow(self, project_id: str) -> str:
        """Load vision from linked workflow config."""
        try:
            from ..workflows.store import get_workflow_store
            wf_store = get_workflow_store()
            for wf in wf_store.list_all():
                cfg = wf.config or {}
                if cfg.get("project_ref") == project_id:
                    if wf.description:
                        return wf.description
        except Exception:
            pass
        return ""

    def _seed_workflow_sessions(self):
        """Create sessions linking projects to their workflows."""
        try:
            from ..workflows.store import get_workflow_store
            from ..sessions.store import get_session_store, SessionDef
            wf_store = get_workflow_store()
            sess_store = get_session_store()
            existing = sess_store.list_all()

            for wf in wf_store.list_all():
                cfg = wf.config or {}
                project_ref = cfg.get("project_ref")
                if not project_ref:
                    continue
                # Check if session already exists for this project+workflow
                already = any(
                    s.project_id == project_ref
                    and (s.config or {}).get("workflow_id") == wf.id
                    for s in existing
                )
                if already:
                    continue
                # Determine lead agent from workflow config
                lead = ""
                graph = cfg.get("graph", {})
                nodes = graph.get("nodes", [])
                if nodes:
                    lead = nodes[0].get("agent_id", "")
                session = SessionDef(
                    name=wf.name,
                    goal=wf.description or "",
                    project_id=project_ref,
                    status="active",
                    config={"workflow_id": wf.id, "lead_agent": lead},
                )
                session = sess_store.create(session)
                logger.info("Auto-created session %s for project %s (workflow %s)",
                           session.id, project_ref, wf.id)
        except Exception as e:
            logger.warning("Failed to seed workflow sessions: %s", e)

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


def _project_color(project_id: str) -> str:
    """Assign a distinct color per project."""
    colors = {
        "factory": "#bc8cff", "fervenza": "#f0883e", "veligo": "#58a6ff",
        "ppz": "#3fb950", "psy": "#a371f7", "yolonow": "#f85149",
        "solaris": "#d29922", "sharelook": "#79c0ff", "finary": "#56d364",
        "lpd": "#db6d28", "logs-facteur": "#8b949e",
        "software-factory": "#c084fc",
    }
    return colors.get(project_id, "#8b949e")


# Singleton
_store: Optional[ProjectStore] = None


def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
