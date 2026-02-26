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
    git_url: str = ""             # GitHub/GitLab remote URL for PR creation
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
                git_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add git_url if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if "git_url" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN git_url TEXT DEFAULT ''")
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
        import os
        if os.environ.get("AZURE_DEPLOY", ""):
            from .registry import _PERSONAL_IDS
            projects = [p for p in projects if p.id not in _PERSONAL_IDS]
        cache_put("projects:all", projects, ttl=60)
        return projects

    def get(self, project_id: str) -> Optional[Project]:
        conn = get_db()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        conn.close()
        return self._row_to_project(row) if row else None

    def create(self, p: Project) -> Project:
        from ..cache import invalidate
        if not p.id:
            p.id = p.name.lower().replace(" ", "-").replace("_", "-")[:30]
        # Auto-create workspace directory if path not provided
        if not p.path:
            import os
            _default_ws = "/app/workspace" if os.path.isdir("/app") else os.path.join(os.getcwd(), "workspace")
            workspace = os.path.join(os.environ.get("WORKSPACE_ROOT", _default_ws), p.id)
            os.makedirs(workspace, exist_ok=True)
            p.path = workspace
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO projects
            (id, name, path, description, factory_type, domains_json,
             vision, values_json, lead_agent_id, agents_json, active_pattern_id, status, git_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (p.id, p.name, p.path, p.description, p.factory_type,
              json.dumps(p.domains), p.vision, json.dumps(p.values),
              p.lead_agent_id, json.dumps(p.agents), p.active_pattern_id, p.status,
              p.git_url or ""))
        conn.commit()
        conn.close()
        invalidate("projects:all")
        return p

    def auto_provision(self, project_id: str, project_name: str):
        """Auto-create TMA, Security, and Tech Debt missions for a new project."""
        from ..missions.store import MissionDef, get_mission_store
        ms = get_mission_store()
        provisions = [
            MissionDef(
                name=f"TMA — {project_name}",
                description=f"Maintenance applicative permanente pour {project_name}. Triage incidents → diagnostic → fix TDD → validation.",
                goal="Assurer la stabilité et la disponibilité en continu.",
                status="active", type="program",
                project_id=project_id, workflow_id="tma-maintenance",
                wsjf_score=8, created_by="responsable_tma",
                config={"auto_provisioned": True, "permanent": True},
            ),
            MissionDef(
                name=f"Sécurité — {project_name}",
                description=f"Audit sécurité périodique pour {project_name}. Scan OWASP, CVE watch, revue code sécurité.",
                goal="Maintenir un score sécurité ≥ 80% et zéro CVE critique non corrigée.",
                status="active", type="security",
                project_id=project_id, workflow_id="review-cycle",
                wsjf_score=12, created_by="devsecops",
                config={"auto_provisioned": True, "schedule": "weekly"},
            ),
            MissionDef(
                name=f"Dette Technique — {project_name}",
                description=f"Suivi et réduction de la dette technique pour {project_name}. Audit → priorisation WSJF → sprint correctif.",
                goal="Réduire la dette technique de 20% par PI. Complexité cyclomatique < 15, couverture > 80%.",
                status="planning", type="debt",
                project_id=project_id, workflow_id="tech-debt-reduction",
                wsjf_score=5, created_by="enterprise_architect",
                config={"auto_provisioned": True, "schedule": "monthly"},
            ),
            MissionDef(
                name=f"Self-Healing — {project_name}",
                description=f"Auto-détection et auto-correction des incidents pour {project_name}. Monitoring → incident → diagnostic → fix → validation automatique.",
                goal="MTTR < 15 min. Résolution automatique des incidents P3/P4. Escalade P1/P2 avec diagnostic pré-rempli.",
                status="active", type="program",
                project_id=project_id, workflow_id="tma-autoheal",
                wsjf_score=10, created_by="sre",
                config={"auto_provisioned": True, "permanent": True, "auto_heal": True},
            ),
        ]
        created = []
        for m in provisions:
            try:
                created.append(ms.create_mission(m))
                logger.warning("Auto-provisioned %s for project %s", m.type, project_id)
            except Exception as e:
                logger.warning("Failed to auto-provision %s for %s: %s", m.type, project_id, e)
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
        if any(d in dl for d in ("node", "typescript", "svelte", "react", "vue", "next")):
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

            # Always ensure project agent is a Product Manager with proper tools
            agent_id = f"agent-{info.id}"
            pm = _PROJECT_PM.get(info.id, {})
            pm_name = pm.get("name", f"PM {info.name}")
            pm_avatar = pm.get("avatar", "user")
            pm_tagline = pm.get("tagline", info.description[:60] if info.description else f"Product Manager — {info.name}")
            pm_tools = [
                "code_read", "code_search", "list_files", "deep_search",
                "memory_search", "memory_store", "get_project_context",
                "git_status", "git_log", "git_diff",
                "lrm_locate", "lrm_summarize", "lrm_context", "lrm_conventions",
                "github_issues", "github_prs", "github_code_search",
                "jira_search", "confluence_read",
                "screenshot",
                "platform_agents", "platform_missions", "platform_memory_search",
                "platform_metrics", "platform_sessions", "platform_workflows",
            ]
            agent = AgentDef(
                id=agent_id,
                name=pm_name,
                role="product-manager",
                description=f"Product Manager pour {info.name}. Connaît le code, la vision, le backlog, les docs et les tickets.",
                provider="azure-openai", model="gpt-5-mini",
                temperature=0.5, max_tokens=8192,
                icon="user", color=_project_color(info.id),
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
                    conn.execute("UPDATE projects SET lead_agent_id = ? WHERE id = ?", (agent_id, existing.id))
                    conn.commit()
                    conn.close()
                continue  # Don't overwrite user customizations for project itself

            # New project — create it
            p = Project(
                id=info.id, name=info.name, path=info.path,
                description=info.description, factory_type=info.factory_type,
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
        keys = row.keys() if hasattr(row, "keys") else []
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
            git_url=row["git_url"] if "git_url" in keys else "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )


_PROJECT_PM: dict[str, dict] = {
    "lpd": {"name": "Nathalie Renaud", "avatar": "user", "tagline": "Product Manager — LPD Data Platform"},
    "logs-facteur": {"name": "Thomas Girard", "avatar": "user", "tagline": "Product Manager — Logs Facteur Support N1"},
    "sharelook": {"name": "Claire Dubois", "avatar": "user", "tagline": "Product Manager — Sharelook Platform"},
    "software-factory": {"name": "Émilie Laurent", "avatar": "user", "tagline": "Product Manager — Software Factory"},
    "factory": {"name": "Émilie Laurent", "avatar": "user", "tagline": "Product Manager — Software Factory (Self)"},
    "solaris": {"name": "Julie Martin", "avatar": "user", "tagline": "Product Manager — Solaris Design System"},
    "veligo": {"name": "Antoine Lefèvre", "avatar": "user", "tagline": "Product Manager — Veligo Platform"},
    "fervenza": {"name": "Lucas Morel", "avatar": "user", "tagline": "Product Manager — Fervenza IoT"},
    "finary": {"name": "Sophie Blanc", "avatar": "user", "tagline": "Product Manager — Finary"},
    "popinz": {"name": "Hugo Petit", "avatar": "user", "tagline": "Product Manager — Popinz SaaS"},
    "psy": {"name": "Camille Roux", "avatar": "user", "tagline": "Product Manager — PSY Platform"},
    "yolonow": {"name": "Léa Fournier", "avatar": "user", "tagline": "Product Manager — YoloNow"},
    "sharelook-2": {"name": "Claire Dubois", "avatar": "user", "tagline": "Product Manager — Sharelook 2.0"},
    # Demo projects
    "neobank-api": {"name": "Alexandre Morin", "avatar": "user", "tagline": "Product Manager — NeoBank API Platform"},
    "mediboard": {"name": "Isabelle Faure", "avatar": "user", "tagline": "Product Manager — MediBoard Hospital"},
    "greenfleet": {"name": "Mathieu Garnier", "avatar": "user", "tagline": "Product Manager — GreenFleet EV"},
    "eduspark": {"name": "Sarah Lemaire", "avatar": "user", "tagline": "Product Manager — EduSpark E-Learning"},
    "payflow": {"name": "Vincent Carpentier", "avatar": "user", "tagline": "Product Manager — PayFlow Payments"},
    "dataforge": {"name": "Nadia Bensalem", "avatar": "user", "tagline": "Product Manager — DataForge Pipeline"},
    "urbanpulse": {"name": "Raphaël Nguyen", "avatar": "user", "tagline": "Product Manager — UrbanPulse Mobility"},
}


def _project_color(project_id: str) -> str:
    """Assign a distinct color per project."""
    colors = {
        "factory": "#bc8cff", "fervenza": "#f0883e", "veligo": "#58a6ff",
        "ppz": "#3fb950", "psy": "#a371f7", "yolonow": "#f85149",
        "solaris": "#d29922", "sharelook": "#79c0ff", "finary": "#56d364",
        "lpd": "#db6d28", "logs-facteur": "#8b949e",
        "software-factory": "#c084fc",
        "neobank-api": "#f778ba", "mediboard": "#2ea043", "greenfleet": "#1f883d",
        "eduspark": "#bf8700", "payflow": "#da3633", "dataforge": "#388bfd",
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
