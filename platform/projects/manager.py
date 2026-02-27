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
    {
        "id": "quality",
        "label": "Qualité > Vitesse",
        "desc": "Review obligatoire, adversarial activé",
    },
    {"id": "feedback", "label": "Feedback rapide", "desc": "Loops courtes, fail fast"},
    {
        "id": "no-waste",
        "label": "Éliminer le waste",
        "desc": "KISS, pas de code inutile",
    },
    {
        "id": "respect",
        "label": "Respect des personnes",
        "desc": "Collaboration, négociation > veto",
    },
    {
        "id": "kaizen",
        "label": "Amélioration continue",
        "desc": "Retrospective auto, XP agent",
    },
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
    vision: str = ""  # VISION.md content or custom text
    values: list[str] = field(default_factory=list)  # Lean value IDs
    lead_agent_id: str = ""  # Default agent for this project
    agents: list[str] = field(default_factory=list)  # Assigned agent IDs
    active_pattern_id: str = ""  # Currently active pattern
    status: str = "active"  # active | paused | archived
    git_url: str = ""  # GitHub/GitLab remote URL for PR creation
    current_phase: str = ""  # ex: "discovery", "mvp", "v1", "run", "maintenance"
    phases: list[dict] = field(
        default_factory=list
    )  # [{id, name, icon, mission_types_active[]}]
    created_at: str = ""
    updated_at: str = ""

    # Default phase templates (used when no phases defined)
    DEFAULT_PHASES: list[dict] = field(
        default_factory=lambda: [
            {
                "id": "discovery",
                "name": "Discovery",
                "icon": "🔍",
                "mission_types_active": [],
            },
            {
                "id": "mvp",
                "name": "MVP",
                "icon": "🚀",
                "mission_types_active": ["feature"],
            },
            {
                "id": "v1",
                "name": "V1 Prod",
                "icon": "✅",
                "mission_types_active": ["program", "security", "debt", "feature"],
            },
            {
                "id": "run",
                "name": "Run",
                "icon": "⚙️",
                "mission_types_active": ["program", "security", "debt", "hacking"],
            },
            {
                "id": "maintenance",
                "name": "Maintenance",
                "icon": "🔧",
                "mission_types_active": ["program", "security", "debt"],
            },
        ]
    )

    @property
    def exists(self) -> bool:
        return Path(self.path).is_dir()

    @property
    def has_git(self) -> bool:
        p = Path(self.path)
        if (p / ".git").exists():
            return True
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=5,
            )
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


def _detect_git_url(path: str) -> str:
    """Auto-detect git remote URL from a workspace path."""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            url = r.stdout.strip()
            # Normalize SSH → HTTPS for PR creation
            if url.startswith("git@github.com:"):
                url = "https://github.com/" + url[
                    len("git@github.com:") :
                ].removesuffix(".git")
            return url
    except Exception:
        pass
    return ""


_DOCKERFILE_TEMPLATE = """\
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

_DOCKER_COMPOSE_TEMPLATE = """\
version: "3.9"
services:
  app:
    build: .
    ports:
      - "{port}:8000"
    environment:
      - ENV=development
"""

_GITIGNORE_TEMPLATE = """\
__pycache__/
*.pyc
*.pyo
.env
.venv/
venv/
node_modules/
dist/
build/
.DS_Store
*.log
"""


def scaffold_project(p: "Project") -> dict:
    """Ensure every project has workspace + git + docker + docs + minimal code.

    Idempotent: only creates missing pieces, never overwrites existing files.
    Returns a dict of actions taken.
    """
    root = Path(p.path)
    actions: list[str] = []

    # 1. Workspace directory
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        actions.append("created workspace dir")

    # 2. Git init
    if not (root / ".git").exists():
        try:
            subprocess.run(
                ["git", "init"], cwd=str(root), capture_output=True, timeout=10
            )
            subprocess.run(
                ["git", "config", "user.email", "factory@macaron-software.com"],
                cwd=str(root),
                capture_output=True,
                timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.name", "Software Factory"],
                cwd=str(root),
                capture_output=True,
                timeout=5,
            )
            actions.append("git init")
        except Exception as e:
            logger.warning("scaffold git init failed for %s: %s", p.id, e)

    # 3. README.md
    readme = root / "README.md"
    if not readme.exists():
        vision = p.vision or p.description or ""
        readme.write_text(
            f"# {p.name}\n\n{vision}\n\n---\n*Generated by Software Factory*\n",
            encoding="utf-8",
        )
        actions.append("created README.md")

    # 4. Dockerfile
    if not (root / "Dockerfile").exists():
        (root / "Dockerfile").write_text(_DOCKERFILE_TEMPLATE, encoding="utf-8")
        actions.append("created Dockerfile")

    # 5. docker-compose.yml — unique host port per project (10000-19999 range)
    if not (root / "docker-compose.yml").exists():
        import hashlib

        _port = 10000 + (int(hashlib.md5(p.id.encode()).hexdigest(), 16) % 10000)
        (root / "docker-compose.yml").write_text(
            _DOCKER_COMPOSE_TEMPLATE.format(port=_port), encoding="utf-8"
        )
        actions.append("created docker-compose.yml")

    # 6. .gitignore
    if not (root / ".gitignore").exists():
        (root / ".gitignore").write_text(_GITIGNORE_TEMPLATE, encoding="utf-8")
        actions.append("created .gitignore")

    # 7. src/ placeholder (minimal code structure)
    src = root / "src"
    if not src.exists():
        src.mkdir(exist_ok=True)
        (src / "__init__.py").write_text(f'"""{p.name} package."""\n', encoding="utf-8")
        actions.append("created src/__init__.py")

    # 8. Initial git commit if repo is empty
    if actions:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                subprocess.run(
                    ["git", "add", "-A"], cwd=str(root), capture_output=True, timeout=10
                )
                subprocess.run(
                    ["git", "commit", "-m", f"chore: scaffold {p.name}"],
                    cwd=str(root),
                    capture_output=True,
                    timeout=10,
                )
                actions.append("initial git commit")
        except Exception:
            pass

    if actions:
        logger.info("scaffold_project %s: %s", p.id, ", ".join(actions))
    return {"project_id": p.id, "actions": actions}


def heal_all_projects() -> dict:
    """Scan all projects and scaffold any missing pieces. Called at startup."""
    store = get_project_store()
    results = []
    for p in store.list_all():
        try:
            r = scaffold_project(p)
            if r["actions"]:
                results.append(r)
        except Exception as e:
            logger.warning("heal_all: error on %s: %s", p.id, e)
    if results:
        logger.info("heal_all_projects: fixed %d projects", len(results))
    return {"fixed": len(results), "details": results}


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
                git_url TEXT DEFAULT '',
                current_phase TEXT DEFAULT '',
                phases_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrations: add missing columns
        cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        for col, default in [
            ("git_url", "''"),
            ("current_phase", "''"),
            ("phases_json", "'[]'"),
        ]:
            if col not in cols:
                conn.execute(
                    f"ALTER TABLE projects ADD COLUMN {col} TEXT DEFAULT {default}"
                )
        conn.commit()
        conn.close()

    def list_all(self) -> list[Project]:
        from ..cache import get as cache_get, put as cache_put

        cached = cache_get("projects:all")
        if cached is not None:
            return cached
        conn = get_db()
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        conn.close()
        projects = [self._row_to_project(r) for r in rows]
        if os.environ.get("AZURE_DEPLOY", ""):
            from .registry import _PERSONAL_IDS

            projects = [p for p in projects if p.id not in _PERSONAL_IDS]
        cache_put("projects:all", projects, ttl=60)
        return projects

    def search(
        self,
        q: str = "",
        factory_type: str = "",
        has_workspace: str = "",
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """Search projects by name/description/vision/domains. Returns (projects, total)."""
        conn = get_db()
        try:
            conditions = []
            params: list = []
            if q:
                like = f"%{q}%"
                conditions.append(
                    "(p.name LIKE ? OR p.description LIKE ? OR p.vision LIKE ? OR p.domains_json LIKE ?)"
                )
                params += [like, like, like, like]
            if factory_type:
                conditions.append("p.factory_type = ?")
                params.append(factory_type)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            total = conn.execute(
                f"SELECT COUNT(*) FROM projects p {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT p.* FROM projects p {where} ORDER BY p.name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            projects = [self._row_to_project(r) for r in rows]
            if os.environ.get("AZURE_DEPLOY", ""):
                from .registry import _PERSONAL_IDS

                projects = [p for p in projects if p.id not in _PERSONAL_IDS]
            # Post-filter by workspace existence (can't do in SQL)
            if has_workspace == "1":
                projects = [p for p in projects if p.exists]
                total = len(projects)
            elif has_workspace == "0":
                projects = [p for p in projects if not p.exists]
                total = len(projects)
            return projects, total
        finally:
            conn.close()

    def get(self, project_id: str) -> Optional[Project]:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        conn.close()
        return self._row_to_project(row) if row else None

    def create(self, p: Project) -> Project:
        from ..cache import invalidate

        if not p.id:
            p.id = p.name.lower().replace(" ", "-").replace("_", "-")[:30]
        # Auto-create workspace directory if path not provided
        if not p.path:
            import os

            _default_ws = (
                "/app/workspace"
                if os.path.isdir("/app")
                else os.path.join(os.getcwd(), "workspace")
            )
            workspace = os.path.join(
                os.environ.get("WORKSPACE_ROOT", _default_ws), p.id
            )
            os.makedirs(workspace, exist_ok=True)
            p.path = workspace
        # Auto-detect git_url from workspace remote if not provided
        if not p.git_url and p.path:
            p.git_url = _detect_git_url(p.path)
        conn = get_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO projects
            (id, name, path, description, factory_type, domains_json,
             vision, values_json, lead_agent_id, agents_json, active_pattern_id, status, git_url,
             current_phase, phases_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                p.id,
                p.name,
                p.path,
                p.description,
                p.factory_type,
                json.dumps(p.domains),
                p.vision,
                json.dumps(p.values),
                p.lead_agent_id,
                json.dumps(p.agents),
                p.active_pattern_id,
                p.status,
                p.git_url or "",
                p.current_phase or "",
                json.dumps(p.phases),
            ),
        )
        conn.commit()
        conn.close()
        invalidate("projects:all")
        # Scaffold workspace (idempotent — safe to call even if partially exists)
        try:
            scaffold_project(p)
        except Exception as e:
            logger.warning("scaffold_project failed for %s: %s", p.id, e)
        # Provision baseline missions (TMA + Security + Debt + MVP if applicable)
        try:
            self.heal_missions(p)
        except Exception as e:
            logger.warning("heal_missions failed for %s: %s", p.id, e)
        return p

    def set_phase(self, project_id: str, phase_id: str) -> "Project | None":
        """Set the current phase of a project and update mission statuses."""
        from ..cache import invalidate

        conn = get_db()
        conn.execute(
            "UPDATE projects SET current_phase = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (phase_id, project_id),
        )
        conn.commit()
        conn.close()
        invalidate("projects:all")
        proj = self.get(project_id)
        if proj:
            # Recompute mission statuses for new phase
            try:
                self.heal_missions(proj)
            except Exception as e:
                logger.warning(
                    "heal_missions after set_phase failed for %s: %s", project_id, e
                )
        return proj

    def auto_provision(self, project_id: str, project_name: str):
        """Auto-create TMA, Security, and Tech Debt missions for a new project."""
        from ..missions.store import MissionDef, get_mission_store

        ms = get_mission_store()
        provisions = [
            MissionDef(
                name=f"TMA — {project_name}",
                description=f"Maintenance applicative permanente pour {project_name}. Triage incidents → diagnostic → fix TDD → validation.",
                goal="Assurer la stabilité et la disponibilité en continu.",
                status="active",
                type="program",
                project_id=project_id,
                workflow_id="tma-maintenance",
                wsjf_score=8,
                created_by="responsable_tma",
                config={"auto_provisioned": True, "permanent": True},
            ),
            MissionDef(
                name=f"Sécurité — {project_name}",
                description=f"Audit sécurité périodique pour {project_name}. Scan OWASP, CVE watch, revue code sécurité.",
                goal="Maintenir un score sécurité ≥ 80% et zéro CVE critique non corrigée.",
                status="active",
                type="security",
                project_id=project_id,
                workflow_id="review-cycle",
                wsjf_score=12,
                created_by="devsecops",
                config={"auto_provisioned": True, "schedule": "weekly"},
            ),
            MissionDef(
                name=f"Dette Technique — {project_name}",
                description=f"Suivi et réduction de la dette technique pour {project_name}. Audit → priorisation WSJF → sprint correctif.",
                goal="Réduire la dette technique de 20% par PI. Complexité cyclomatique < 15, couverture > 80%.",
                status="planning",
                type="debt",
                project_id=project_id,
                workflow_id="tech-debt-reduction",
                wsjf_score=5,
                created_by="enterprise_architect",
                config={"auto_provisioned": True, "schedule": "monthly"},
            ),
            MissionDef(
                name=f"Self-Healing — {project_name}",
                description=f"Auto-détection et auto-correction des incidents pour {project_name}. Monitoring → incident → diagnostic → fix → validation automatique.",
                goal="MTTR < 15 min. Résolution automatique des incidents P3/P4. Escalade P1/P2 avec diagnostic pré-rempli.",
                status="active",
                type="program",
                project_id=project_id,
                workflow_id="tma-autoheal",
                wsjf_score=10,
                created_by="sre",
                config={"auto_provisioned": True, "permanent": True, "auto_heal": True},
            ),
        ]
        created = []
        for m in provisions:
            try:
                created.append(ms.create_mission(m))
                logger.warning("Auto-provisioned %s for project %s", m.type, project_id)
            except Exception as e:
                logger.warning(
                    "Failed to auto-provision %s for %s: %s", m.type, project_id, e
                )
        return created

    def heal_missions(self, proj: "Project") -> list[str]:
        """Ensure every project has TMA + Security + Debt missions (phase-aware).
        MVP/ideation projects also get a MVP Réalisation mission.
        System mission statuses are adjusted based on current_phase.
        Returns list of mission names created or updated."""
        from ..missions.store import MissionDef, get_mission_store

        ms = get_mission_store()
        existing = ms.list_missions(limit=2000)
        proj_m = [m for m in existing if m.project_id == proj.id]
        proj_types = {m.type: m for m in proj_m}  # type → mission

        created = []

        phase = proj.current_phase or ""
        is_early_phase = phase in ("", "discovery")
        is_mvp_phase = phase in ("mvp",)
        is_prod_phase = phase in ("v1", "run", "maintenance", "scale")

        is_mvp_project = (
            proj.factory_type in ("mvp", "ideation")
            or "mvp" in proj.name.lower()
            or proj.status in ("ideation", "mvp", "discovery")
            or is_mvp_phase
        )

        # Compute status for system missions based on phase:
        # - no phase / discovery → TMA + Dette = planning (system dormant), Sécu = planning
        # - mvp → Sécu = active, TMA + Dette = planning
        # - v1+ → all system = active
        tma_status = "planning" if (is_early_phase or is_mvp_phase) else "active"
        secu_status = "planning" if is_early_phase else "active"
        debt_status = "planning" if (is_early_phase or is_mvp_phase) else "active"

        needed = [
            MissionDef(
                name=f"TMA — {proj.name}",
                description=f"Maintenance applicative permanente pour {proj.name}. Triage incidents → diagnostic → fix TDD → validation.",
                goal="Assurer la stabilité et la disponibilité en continu.",
                status=tma_status,
                type="program",
                project_id=proj.id,
                workflow_id="tma-maintenance",
                wsjf_score=8,
                created_by="responsable_tma",
                category="system",
                active_phases=["v1", "run", "maintenance", "scale"],
                config={"auto_provisioned": True, "permanent": True},
            ),
            MissionDef(
                name=f"Sécurité — {proj.name}",
                description=f"Audit sécurité pour {proj.name}. Scan OWASP, CVE watch, revue code sécurité.",
                goal="Score sécurité ≥ 80%, zéro CVE critique non corrigée.",
                status=secu_status,
                type="security",
                project_id=proj.id,
                workflow_id="review-cycle",
                wsjf_score=12,
                created_by="devsecops",
                category="system",
                active_phases=["mvp", "v1", "run", "maintenance", "scale"],
                config={"auto_provisioned": True, "schedule": "weekly"},
            ),
            MissionDef(
                name=f"Dette Technique — {proj.name}",
                description=f"Réduction de la dette technique pour {proj.name}. Audit → priorisation WSJF → sprint correctif.",
                goal="Réduire la dette technique de 20% par PI. Complexité < 15, couverture > 80%.",
                status=debt_status,
                type="debt",
                project_id=proj.id,
                workflow_id="tech-debt-reduction",
                wsjf_score=5,
                created_by="enterprise_architect",
                category="system",
                active_phases=["v1", "run", "maintenance", "scale"],
                config={"auto_provisioned": True, "schedule": "monthly"},
            ),
        ]
        if is_mvp_project:
            mvp_status = "completed" if is_prod_phase else "active"
            needed.append(
                MissionDef(
                    name=f"MVP — {proj.name}",
                    description=f"Réalisation du MVP pour {proj.name}. Discovery → design → dev → validation utilisateurs → go/no-go.",
                    goal="Livrer un MVP validé par au moins 5 utilisateurs cibles en moins de 6 sprints.",
                    status=mvp_status,
                    type="feature",
                    project_id=proj.id,
                    workflow_id="full-project",
                    wsjf_score=20,
                    created_by="product_owner",
                    category="functional",
                    active_phases=["discovery", "mvp"],
                    config={"auto_provisioned": True, "is_mvp": True},
                )
            )

        for m in needed:
            existing_m = (
                proj_types.get(m.type) if m.type not in ("feature", "epic") else None
            )
            if m.type in ("feature", "epic"):
                existing_m = next((pm for pm in proj_m if pm.name == m.name), None)

            if not existing_m:
                # Create missing mission
                try:
                    ms.create_mission(m)
                    created.append(f"+{m.name}")
                    logger.info("heal_missions: created '%s' for %s", m.name, proj.id)
                except Exception as e:
                    logger.warning(
                        "heal_missions: failed '%s' for %s: %s", m.name, proj.id, e
                    )
            else:
                # Update status if phase changed and mission is system-managed
                if (
                    existing_m.category == "system"
                    and existing_m.status != m.status
                    and existing_m.config.get("auto_provisioned")
                ):
                    try:
                        ms.update_mission_status(existing_m.id, m.status)
                        created.append(f"~{m.name}→{m.status}")
                    except Exception:
                        pass

        return created

    @staticmethod
    def generate_cicd(project_path: str, domains: list[str]) -> str | None:
        """Generate a CI/CD pipeline file based on project stack."""
        proj_dir = Path(project_path)
        if not proj_dir.is_dir():
            return None
        gh_dir = proj_dir / ".github" / "workflows"
        gh_dir.mkdir(parents=True, exist_ok=True)
        ci_path = gh_dir / "ci.yml"
        if ci_path.exists():
            return str(ci_path)

        # Detect stack from domains
        dl = [d.lower() for d in domains]
        steps = []
        if any(d in dl for d in ("rust", "cargo")):
            steps.append(_CICD_RUST)
        if any(d in dl for d in ("python", "django", "fastapi", "flask")):
            steps.append(_CICD_PYTHON)
        if any(
            d in dl for d in ("node", "typescript", "svelte", "react", "vue", "next")
        ):
            steps.append(_CICD_NODE)
        if any(d in dl for d in ("swift", "ios", "swiftui")):
            steps.append(_CICD_SWIFT)
        if any(d in dl for d in ("kotlin", "android", "java")):
            steps.append(_CICD_KOTLIN)
        if not steps:
            steps.append(_CICD_GENERIC)

        content = _CICD_HEADER + "\n".join(steps) + "\n"
        ci_path.write_text(content, encoding="utf-8")
        logger.info("Generated CI/CD pipeline at %s", ci_path)
        return str(ci_path)

    def update(self, p: Project) -> Project:
        conn = get_db()
        conn.execute(
            """
            UPDATE projects SET
                name=?, path=?, description=?, factory_type=?, domains_json=?,
                vision=?, values_json=?, lead_agent_id=?, agents_json=?,
                active_pattern_id=?, status=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """,
            (
                p.name,
                p.path,
                p.description,
                p.factory_type,
                json.dumps(p.domains),
                p.vision,
                json.dumps(p.values),
                p.lead_agent_id,
                json.dumps(p.agents),
                p.active_pattern_id,
                p.status,
                p.id,
            ),
        )
        conn.commit()
        conn.close()
        return p

    def update_vision(self, project_id: str, vision: str):
        conn = get_db()
        conn.execute(
            "UPDATE projects SET vision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (vision, project_id),
        )
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

            # Always ensure project agent is a Product Manager with proper tools
            agent_id = f"agent-{info.id}"
            pm = _PROJECT_PM.get(info.id, {})
            pm_name = pm.get("name", f"PM {info.name}")
            pm_avatar = pm.get("avatar", "user")
            pm_tagline = pm.get(
                "tagline",
                info.description[:60]
                if info.description
                else f"Product Manager — {info.name}",
            )
            pm_tools = [
                "code_read",
                "code_search",
                "list_files",
                "deep_search",
                "memory_search",
                "memory_store",
                "get_project_context",
                "git_status",
                "git_log",
                "git_diff",
                "lrm_locate",
                "lrm_summarize",
                "lrm_context",
                "lrm_conventions",
                "github_issues",
                "github_prs",
                "github_code_search",
                "jira_search",
                "confluence_read",
                "screenshot",
                "platform_agents",
                "platform_missions",
                "platform_memory_search",
                "platform_metrics",
                "platform_sessions",
                "platform_workflows",
            ]
            agent = AgentDef(
                id=agent_id,
                name=pm_name,
                role="product-manager",
                description=f"Product Manager pour {info.name}. Connaît le code, la vision, le backlog, les docs et les tickets.",
                provider="azure-openai",
                model="gpt-5-mini",
                temperature=0.5,
                max_tokens=8192,
                icon="user",
                color=_project_color(info.id),
                avatar=pm_avatar,
                tagline=pm_tagline,
                is_builtin=True,
                tags=["project", "product", info.factory_type or "general"],
                tools=pm_tools,
                mcps=["lrm", "platform"],
                system_prompt=f"Tu es {pm_name}, Product Manager du projet {info.name}.\n"
                f"Chemin projet: {info.path}\n"
                f"Type: {info.factory_type or 'general'}\n\n"
                "Tu connais le code, l'architecture, la vision, le backlog, les docs et le wiki.\n"
                "Tu utilises tes outils (code_read, deep_search, memory, git, lrm) pour répondre avec précision.\n"
                "Tu peux consulter Jira, Confluence, GitHub si configurés.\n"
                "Sois concis, factuel, et proactif. Propose des actions concrètes.",
            )
            existing_agent = agent_store.get(agent_id)
            if existing_agent:
                agent_store.update(agent)
            else:
                agent_store.create(agent)

            if existing:
                # Only set lead_agent_id if truly empty (don't overwrite user customizations)
                if not existing.lead_agent_id:
                    from ..db.migrations import get_db

                    conn = get_db()
                    conn.execute(
                        "UPDATE projects SET lead_agent_id = ? WHERE id = ?",
                        (agent_id, existing.id),
                    )
                    conn.commit()
                    conn.close()
                continue  # Don't overwrite user customizations for project itself

            # New project — create it
            p = Project(
                id=info.id,
                name=info.name,
                path=info.path,
                description=info.description,
                factory_type=info.factory_type,
                domains=info.domains,
            )
            if p.exists:
                p.vision = p.load_vision_from_file()
            if not p.vision:
                p.vision = self._load_vision_from_workflow(info.id)

            p.lead_agent_id = agent_id

            if p.factory_type == "sf":
                p.values = ["quality", "feedback", "tdd", "zero-skip", "kaizen"]
            elif p.factory_type == "mf":
                p.values = ["quality", "feedback", "zero-skip"]
            else:
                p.values = ["quality", "feedback"]

            self.create(p)
            logger.info(
                "Seeded project %s (%s) with agent %s", p.id, p.factory_type, agent_id
            )

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
                "Software Factory — Real Agentic ≠ Workflow Automation.\n"
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
                "dsi",
                "strat-cpo",
                "strat-cto",
                "strat-portfolio",
                "architecte",
                "plat-lead-dev",
                "plat-dev-backend",
                "plat-dev-frontend",
                "plat-dev-agents",
                "plat-dev-patterns",
                "plat-dev-infra",
                "plat-product",
                "plat-tma-lead",
                "plat-tma-dev-back",
                "plat-tma-dev-front",
                "plat-tma-dev-agents",
                "plat-tma-qa",
                "qa_lead",
                "securite",
                "devops",
                "sre",
                "scrum_master",
                "ux_designer",
                "performance_engineer",
                "pipeline_engineer",
                "devsecops",
                "test_automation",
                "tech_writer",
                "lean_portfolio_manager",
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
                logger.info(
                    "Auto-created session %s for project %s (workflow %s)",
                    session.id,
                    project_ref,
                    wf.id,
                )
        except Exception as e:
            logger.warning("Failed to seed workflow sessions: %s", e)

    def _row_to_project(self, row) -> Project:
        keys = row.keys() if hasattr(row, "keys") else []
        return Project(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            description=row["description"] or "",
            factory_type=row["factory_type"] or "standalone",
            domains=(
                _d
                if isinstance(_d := json.loads(row["domains_json"] or "[]"), list)
                else []
            ),
            vision=row["vision"] or "",
            values=json.loads(row["values_json"] or "[]"),
            lead_agent_id=row["lead_agent_id"] or "",
            agents=json.loads(row["agents_json"] or "[]"),
            active_pattern_id=row["active_pattern_id"] or "",
            status=row["status"] or "active",
            git_url=row["git_url"] if "git_url" in keys else "",
            current_phase=row["current_phase"] if "current_phase" in keys else "",
            phases=json.loads(row["phases_json"] if "phases_json" in keys else "[]")
            or [],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )


_PROJECT_PM: dict[str, dict] = {
    "lpd": {
        "name": "Nathalie Renaud",
        "avatar": "user",
        "tagline": "Product Manager — LPD Data Platform",
    },
    "logs-facteur": {
        "name": "Thomas Girard",
        "avatar": "user",
        "tagline": "Product Manager — Logs Facteur Support N1",
    },
    "sharelook": {
        "name": "Claire Dubois",
        "avatar": "user",
        "tagline": "Product Manager — Sharelook Platform",
    },
    "software-factory": {
        "name": "Émilie Laurent",
        "avatar": "user",
        "tagline": "Product Manager — Software Factory",
    },
    "factory": {
        "name": "Émilie Laurent",
        "avatar": "user",
        "tagline": "Product Manager — Software Factory (Self)",
    },
    "solaris": {
        "name": "Julie Martin",
        "avatar": "user",
        "tagline": "Product Manager — Solaris Design System",
    },
    "veligo": {
        "name": "Antoine Lefèvre",
        "avatar": "user",
        "tagline": "Product Manager — Veligo Platform",
    },
    "fervenza": {
        "name": "Lucas Morel",
        "avatar": "user",
        "tagline": "Product Manager — Fervenza IoT",
    },
    "finary": {
        "name": "Sophie Blanc",
        "avatar": "user",
        "tagline": "Product Manager — Finary",
    },
    "popinz": {
        "name": "Hugo Petit",
        "avatar": "user",
        "tagline": "Product Manager — Popinz SaaS",
    },
    "psy": {
        "name": "Camille Roux",
        "avatar": "user",
        "tagline": "Product Manager — PSY Platform",
    },
    "yolonow": {
        "name": "Léa Fournier",
        "avatar": "user",
        "tagline": "Product Manager — YoloNow",
    },
    "sharelook-2": {
        "name": "Claire Dubois",
        "avatar": "user",
        "tagline": "Product Manager — Sharelook 2.0",
    },
    # Demo projects
    "neobank-api": {
        "name": "Alexandre Morin",
        "avatar": "user",
        "tagline": "Product Manager — NeoBank API Platform",
    },
    "mediboard": {
        "name": "Isabelle Faure",
        "avatar": "user",
        "tagline": "Product Manager — MediBoard Hospital",
    },
    "greenfleet": {
        "name": "Mathieu Garnier",
        "avatar": "user",
        "tagline": "Product Manager — GreenFleet EV",
    },
    "eduspark": {
        "name": "Sarah Lemaire",
        "avatar": "user",
        "tagline": "Product Manager — EduSpark E-Learning",
    },
    "payflow": {
        "name": "Vincent Carpentier",
        "avatar": "user",
        "tagline": "Product Manager — PayFlow Payments",
    },
    "dataforge": {
        "name": "Nadia Bensalem",
        "avatar": "user",
        "tagline": "Product Manager — DataForge Pipeline",
    },
    "urbanpulse": {
        "name": "Raphaël Nguyen",
        "avatar": "user",
        "tagline": "Product Manager — UrbanPulse Mobility",
    },
}


def _project_color(project_id: str) -> str:
    """Assign a distinct color per project."""
    colors = {
        "factory": "#bc8cff",
        "fervenza": "#f0883e",
        "veligo": "#58a6ff",
        "ppz": "#3fb950",
        "psy": "#a371f7",
        "yolonow": "#f85149",
        "solaris": "#d29922",
        "sharelook": "#79c0ff",
        "finary": "#56d364",
        "lpd": "#db6d28",
        "logs-facteur": "#8b949e",
        "software-factory": "#c084fc",
        "neobank-api": "#f778ba",
        "mediboard": "#2ea043",
        "greenfleet": "#1f883d",
        "eduspark": "#bf8700",
        "payflow": "#da3633",
        "dataforge": "#388bfd",
        "urbanpulse": "#a5d6ff",
    }
    return colors.get(project_id, "#8b949e")


# Singleton
_store: Optional[ProjectStore] = None


def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


# ── CI/CD Pipeline Templates ──

_CICD_HEADER = """name: CI/CD Pipeline
on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

_CICD_RUST = """
      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
      - name: Build
        run: cargo build --workspace
      - name: Test
        run: cargo test --workspace
      - name: Clippy
        run: cargo clippy --workspace -- -D warnings
"""

_CICD_PYTHON = """
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install deps
        run: pip install -r requirements.txt || pip install -e .
      - name: Lint
        run: python -m ruff check . || true
      - name: Test
        run: python -m pytest tests/ -v
"""

_CICD_NODE = """
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install deps
        run: npm ci || npm install
      - name: Lint
        run: npm run lint || true
      - name: Build
        run: npm run build
      - name: Test
        run: npm test || npm run test
"""

_CICD_SWIFT = """
      - name: Build iOS
        run: xcodebuild -scheme App -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 15' build
      - name: Test iOS
        run: xcodebuild -scheme App -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 15' test
"""

_CICD_KOTLIN = """
      - name: Setup JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'
      - name: Build
        run: ./gradlew build
      - name: Test
        run: ./gradlew test
"""

_CICD_GENERIC = """
      - name: Check files
        run: ls -la && echo "Add your build/test steps here"
"""
