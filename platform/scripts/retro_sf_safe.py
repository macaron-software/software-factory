#!/usr/bin/env python3
"""
Retro-engineering script — Populate SAFe traceability for the _sf project.

Creates: epics table (if missing) + epics + features + user_stories + project_screens
for all known Software Factory pages, organized in the SAFe hierarchy:
  Programme (org_portfolio) → Epic → Feature → Story → project_screen

Usage:
  python3 -m platform.scripts.retro_sf_safe
  # or: python3 platform/scripts/retro_sf_safe.py
"""

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from platform.db.migrations import get_db  # type: ignore

PROGRAMME_ID = "portfolio-sf-platform"
PROGRAMME_NAME = "Software Factory Platform"

# SAFe mapping: epic_key → { name, description, features: [{ name, desc, pages, stories }] }
SAFE_MAP = [
    {
        "id": "epic-orchestration",
        "name": "Orchestration & Missions",
        "description": "Agent orchestration, mission lifecycle, live sessions and ART cockpit.",
        "features": [
            {
                "id": "feat-cockpit",
                "name": "Dashboard / Cockpit",
                "description": "Real-time overview of running missions, agent activity, platform KPIs.",
                "persona": "Tech Lead",
                "pages": ["/", "/cockpit", "/dashboard"],
                "stories": [
                    "Voir les missions actives en temps réel sur le cockpit",
                    "Accéder aux métriques de la plateforme depuis la page d'accueil",
                    "Naviguer vers une mission depuis le cockpit en un clic",
                ],
            },
            {
                "id": "feat-mission-control",
                "name": "Mission Control",
                "description": "Start, monitor and control agent missions end-to-end.",
                "persona": "Tech Lead",
                "pages": ["/mission-control", "/mission-start", "/mission-replay"],
                "stories": [
                    "Lancer une mission avec un prompt libre",
                    "Surveiller l'avancement d'une mission en cours",
                    "Rejouer ou annuler une mission depuis l'interface",
                    "Consulter les détails d'une mission (logs, artefacts, durée)",
                ],
            },
            {
                "id": "feat-live",
                "name": "Sessions Live",
                "description": "Live view of agent conversations and real-time ceremony sessions.",
                "persona": "Scrum Master",
                "pages": ["/live", "/sessions", "/new-session"],
                "stories": [
                    "Rejoindre une cérémonie live (PI Planning, sprint review)",
                    "Voir la conversation en cours d'un agent en temps réel",
                    "Créer une nouvelle session de travail collaboratif",
                ],
            },
            {
                "id": "feat-art",
                "name": "ART — Agile Release Train",
                "description": "Manage the Agile Release Train: teams, agents, roles and capacity.",
                "persona": "Release Train Engineer",
                "pages": ["/art"],
                "stories": [
                    "Visualiser la composition de l'ART (équipes, agents)",
                    "Assigner des rôles et capacités aux équipes",
                    "Suivre la vélocité de l'ART par PI",
                ],
            },
        ],
    },
    {
        "id": "epic-backlog",
        "name": "SAFe Backlog & Planning",
        "description": "Portfolio, PI planning, product backlog and project management.",
        "features": [
            {
                "id": "feat-portfolio",
                "name": "Portfolio",
                "description": "Top-level portfolio view: epics, budgets, strategic themes.",
                "persona": "Product Manager",
                "pages": ["/portfolio"],
                "stories": [
                    "Visualiser les epics du portfolio avec leur statut et budget",
                    "Créer et prioriser un nouvel epic depuis le portfolio",
                    "Suivre l'avancement des programmes dans le portfolio",
                ],
            },
            {
                "id": "feat-pi-planning",
                "name": "PI Planning Board",
                "description": "Program Increment planning: features, iterations, dependencies.",
                "persona": "Product Manager",
                "pages": ["/pi"],
                "stories": [
                    "Planifier les features par itération sur le board PI",
                    "Gérer les dépendances inter-équipes sur le PI Board",
                    "Générer automatiquement un PI Plan via un agent",
                ],
            },
            {
                "id": "feat-backlog",
                "name": "Product Backlog",
                "description": "Prioritized backlog: features, user stories, tasks.",
                "persona": "Product Owner",
                "pages": ["/backlog"],
                "stories": [
                    "Prioriser les user stories par drag & drop",
                    "Affiner le backlog avec l'aide d'un agent IA",
                    "Filtrer le backlog par epic, statut, sprint",
                ],
            },
            {
                "id": "feat-projects",
                "name": "Projects Hub",
                "description": "Project management: kanban boards, overviews, workspaces.",
                "persona": "Product Owner",
                "pages": [
                    "/projects",
                    "/project-board",
                    "/project-hub",
                    "/project-overview",
                    "/project-workspace",
                ],
                "stories": [
                    "Créer un nouveau projet et l'assigner à une équipe",
                    "Suivre l'avancement d'un projet via le kanban board",
                    "Accéder à l'espace de travail d'un projet",
                ],
            },
        ],
    },
    {
        "id": "epic-agent-factory",
        "name": "Agent Factory",
        "description": "Design, configure and manage AI agents, skills, workflows and patterns.",
        "features": [
            {
                "id": "feat-agents",
                "name": "Agent Designer",
                "description": "Create, edit and test AI agents with roles, personas and tools.",
                "persona": "Tech Lead",
                "pages": ["/agents", "/agent-world"],
                "stories": [
                    "Créer un agent avec rôle, persona et outils",
                    "Tester un agent en conversation directe",
                    "Visualiser les agents sur la carte monde",
                ],
            },
            {
                "id": "feat-skills",
                "name": "Skills & Toolbox",
                "description": "Manage agent skills: prompts, templates, tool configurations.",
                "persona": "Tech Lead",
                "pages": ["/skills", "/toolbox"],
                "stories": [
                    "Créer un skill réutilisable pour les agents",
                    "Parcourir la bibliothèque de skills existants",
                    "Associer des skills à un agent",
                ],
            },
            {
                "id": "feat-workflows",
                "name": "Workflows",
                "description": "Define and execute multi-step agent workflows.",
                "persona": "Tech Lead",
                "pages": ["/workflows"],
                "stories": [
                    "Créer un workflow multi-étapes avec des agents",
                    "Visualiser le graphe d'un workflow",
                    "Lancer un workflow depuis le catalogue",
                ],
            },
            {
                "id": "feat-patterns",
                "name": "Orchestration Patterns",
                "description": "15 built-in orchestration patterns for agent coordination.",
                "persona": "Tech Lead",
                "pages": ["/patterns"],
                "stories": [
                    "Choisir un pattern d'orchestration adapté à mon besoin",
                    "Personnaliser un pattern existant",
                    "Associer un pattern à une mission",
                ],
            },
        ],
    },
    {
        "id": "epic-monitoring",
        "name": "Monitoring & Quality",
        "description": "Platform observability: metrics, analytics, DORA, quality gates, memory.",
        "features": [
            {
                "id": "feat-monitoring",
                "name": "Platform Monitoring",
                "description": "Real-time platform health: LLM costs, latency, error rates.",
                "persona": "DevOps Engineer",
                "pages": ["/monitoring"],
                "stories": [
                    "Consulter les métriques LLM (coût, latence, taux d'erreur)",
                    "Configurer des alertes sur les seuils de coût",
                    "Voir l'historique de santé de la plateforme",
                ],
            },
            {
                "id": "feat-analytics",
                "name": "Analytics & DORA",
                "description": "DORA metrics, team performance, throughput and lead time.",
                "persona": "Engineering Manager",
                "pages": ["/analytics"],
                "stories": [
                    "Consulter les 4 métriques DORA de mon équipe",
                    "Comparer la vélocité entre sprints",
                    "Exporter un rapport analytics en PDF",
                ],
            },
            {
                "id": "feat-quality",
                "name": "Quality Gates & Evals",
                "description": "Quality reports, LLM evaluations, code quality metrics.",
                "persona": "QA Engineer",
                "pages": ["/quality", "/evals"],
                "stories": [
                    "Configurer les quality gates d'un projet",
                    "Lancer une évaluation LLM sur un dataset",
                    "Consulter le rapport qualité d'un sprint",
                ],
            },
            {
                "id": "feat-memory",
                "name": "Agent Memory",
                "description": "Global and project-scoped memory: knowledge base for agents.",
                "persona": "Tech Lead",
                "pages": ["/memory"],
                "stories": [
                    "Consulter la mémoire globale de la plateforme",
                    "Ajouter un fait en mémoire projet",
                    "Rechercher dans la base de connaissance",
                ],
            },
            {
                "id": "feat-ops",
                "name": "Ops & Auto-Heal",
                "description": "Platform operations: incident management, chaos, auto-heal.",
                "persona": "DevOps Engineer",
                "pages": ["/ops"],
                "stories": [
                    "Déclencher un test de chaos controlé",
                    "Consulter les incidents de la plateforme",
                    "Configurer l'auto-heal sur les agents défaillants",
                ],
            },
        ],
    },
    {
        "id": "epic-discovery",
        "name": "Product Discovery",
        "description": "AI-assisted ideation, product roadmap and market analysis.",
        "features": [
            {
                "id": "feat-ideation",
                "name": "Ideation Studio",
                "description": "AI-assisted ideation sessions: individual, group and marketing.",
                "persona": "Product Manager",
                "pages": ["/ideation", "/group-ideation"],
                "stories": [
                    "Lancer une session d'idéation avec un agent",
                    "Organiser une session de groupe avec plusieurs participants",
                    "Exporter les idées générées vers le backlog",
                ],
            },
            {
                "id": "feat-product-line",
                "name": "Product Line & Roadmap",
                "description": "Product line management: features, releases, value streams.",
                "persona": "Product Manager",
                "pages": ["/product-line", "/product"],
                "stories": [
                    "Définir les lignes produit de mon ART",
                    "Visualiser la roadmap produit par trimestre",
                    "Aligner les features sur la stratégie produit",
                ],
            },
            {
                "id": "feat-generate",
                "name": "Generate",
                "description": "AI code and content generation: scaffolding, specs, tests.",
                "persona": "Developer",
                "pages": ["/generate"],
                "stories": [
                    "Générer un scaffold de projet depuis une spec",
                    "Générer des tests unitaires pour mon code",
                    "Créer un document de spécification depuis un prompt",
                ],
            },
        ],
    },
    {
        "id": "epic-integrations",
        "name": "Integrations & Marketplace",
        "description": "External tool integrations: GitHub, Jira, Confluence, MCPs and more.",
        "features": [
            {
                "id": "feat-marketplace",
                "name": "Agent Marketplace",
                "description": "Browse and install pre-built agents from the marketplace.",
                "persona": "Tech Lead",
                "pages": ["/marketplace"],
                "stories": [
                    "Parcourir le catalogue d'agents disponibles",
                    "Installer un agent depuis le marketplace",
                    "Publier un agent dans le marketplace",
                ],
            },
            {
                "id": "feat-mcps",
                "name": "MCP Servers",
                "description": "Model Context Protocol servers: Playwright, Fetch, Memory, custom.",
                "persona": "Tech Lead",
                "pages": ["/mcps"],
                "stories": [
                    "Configurer un serveur MCP pour un agent",
                    "Démarrer/arrêter un serveur MCP depuis l'interface",
                    "Tester la connectivité d'un MCP",
                ],
            },
            {
                "id": "feat-metier",
                "name": "Métier & Domaines",
                "description": "Business domain configuration: industries, use cases, personas.",
                "persona": "Product Manager",
                "pages": ["/metier"],
                "stories": [
                    "Configurer le domaine métier de la plateforme",
                    "Définir les personas par domaine",
                    "Associer des workflows métier à un domaine",
                ],
            },
        ],
    },
    {
        "id": "epic-admin",
        "name": "Platform Administration",
        "description": "Settings, user management, RBAC, organisation and notifications.",
        "features": [
            {
                "id": "feat-settings",
                "name": "Settings",
                "description": "Platform-wide settings: LLM providers, integrations, modules, deploy.",
                "persona": "Admin",
                "pages": ["/settings"],
                "stories": [
                    "Configurer le provider LLM de la plateforme",
                    "Activer/désactiver les modules de la plateforme",
                    "Configurer les intégrations externes (GitHub, Jira...)",
                    "Configurer les deploy targets (Azure, OVH...)",
                ],
            },
            {
                "id": "feat-admin-users",
                "name": "User Management & RBAC",
                "description": "User accounts, roles, permissions and access control.",
                "persona": "Admin",
                "pages": ["/admin/users", "/rbac"],
                "stories": [
                    "Créer un utilisateur et lui assigner un rôle",
                    "Configurer les permissions par rôle",
                    "Révoquer l'accès d'un utilisateur",
                ],
            },
            {
                "id": "feat-org",
                "name": "Organisation & Teams",
                "description": "Org chart, teams, workspaces and SAFe structure.",
                "persona": "Release Train Engineer",
                "pages": ["/org", "/teams", "/workspaces", "/workspace"],
                "stories": [
                    "Créer une équipe et l'associer à un ART",
                    "Définir l'organigramme de l'organisation",
                    "Gérer les espaces de travail par équipe",
                ],
            },
            {
                "id": "feat-notifications",
                "name": "Notifications",
                "description": "Push, Slack and email notifications for platform events.",
                "persona": "Admin",
                "pages": ["/notifications"],
                "stories": [
                    "Configurer les notifications Slack pour les missions",
                    "S'abonner aux alertes de qualité par email",
                    "Voir l'historique des notifications envoyées",
                ],
            },
        ],
    },
    {
        "id": "epic-ux-annotation",
        "name": "UX & Annotation Studio",
        "description": "Visual annotation, design system, wireframe mode and spec traceability.",
        "features": [
            {
                "id": "feat-annotation",
                "name": "Annotation Studio",
                "description": "Visual annotation overlay: comment, mark bugs, request features on any page.",
                "persona": "Product Designer",
                "pages": ["/annotate/_sf", "/annotate"],
                "stories": [
                    "Annoter une page de la SF avec un commentaire ou un bug",
                    "Générer un ticket depuis une annotation",
                    "Voir la liste de toutes les annotations d'un projet",
                    "Lier une page à une feature SAFe via le studio",
                    "Activer le mode wireframe pour inspecter la structure",
                ],
            },
            {
                "id": "feat-design-system",
                "name": "Design System",
                "description": "SF design system: components, tokens, guidelines.",
                "persona": "Product Designer",
                "pages": ["/design-system"],
                "stories": [
                    "Consulter les composants du design system",
                    "Tester les tokens de couleur en light/dark mode",
                    "Exporter les guidelines du design system",
                ],
            },
        ],
    },
]


def run():
    db = get_db()

    # Ensure epics table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS epics (
            id TEXT PRIMARY KEY,
            programme_id TEXT DEFAULT '',
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_epics_programme ON epics(programme_id)")

    # Ensure project_screens has feature_id
    ps_cols = {
        r[1] for r in db.execute("PRAGMA table_info(project_screens)").fetchall()
    }
    if ps_cols and "feature_id" not in ps_cols:
        db.execute("ALTER TABLE project_screens ADD COLUMN feature_id TEXT DEFAULT ''")
    if ps_cols and "mission_id" not in ps_cols:
        db.execute("ALTER TABLE project_screens ADD COLUMN mission_id TEXT DEFAULT ''")

    # Ensure project_screens table exists (if not yet created)
    db.execute("""
        CREATE TABLE IF NOT EXISTS project_screens (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            page_url TEXT DEFAULT '',
            svg_path TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            mission_id TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_screens_project ON project_screens(project_id)"
    )

    # Ensure org_portfolios has programme
    prog = db.execute(
        "SELECT id FROM org_portfolios WHERE id=?", (PROGRAMME_ID,)
    ).fetchone()
    if not prog:
        db.execute(
            "INSERT OR IGNORE INTO org_portfolios (id, name, description) VALUES (?,?,?)",
            (
                PROGRAMME_ID,
                PROGRAMME_NAME,
                "Plateforme multi-agents SAFe — orchestration IA, backlog, monitoring, UX.",
            ),
        )

    total_screens = 0
    total_features = 0
    total_stories = 0

    for epic_def in SAFE_MAP:
        # Upsert Epic
        db.execute(
            "INSERT OR REPLACE INTO epics (id, programme_id, name, description, status) VALUES (?,?,?,?,?)",
            (
                epic_def["id"],
                PROGRAMME_ID,
                epic_def["name"],
                epic_def["description"],
                "active",
            ),
        )

        for feat_def in epic_def["features"]:
            # Upsert Feature
            db.execute(
                """INSERT OR REPLACE INTO features
                   (id, epic_id, name, description, status, priority, story_points)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    feat_def["id"],
                    epic_def["id"],
                    feat_def["name"],
                    feat_def["description"],
                    "active",
                    5,
                    len(feat_def["stories"]) * 3,
                ),
            )
            total_features += 1

            # Upsert User Stories
            for i, story_title in enumerate(feat_def["stories"]):
                story_id = f"story-{feat_def['id']}-{i}"
                db.execute(
                    """INSERT OR REPLACE INTO user_stories
                       (id, feature_id, title, description, status, priority)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        story_id,
                        feat_def["id"],
                        story_title,
                        "",
                        "backlog",
                        len(feat_def["stories"]) - i,
                    ),
                )
                total_stories += 1

            # Upsert project_screens for each page
            for page_url in feat_def["pages"]:
                screen_id = page_url.replace("/", "-").lstrip("-") or "home"
                screen_name = feat_def["name"] + " — " + page_url
                db.execute(
                    """INSERT OR REPLACE INTO project_screens
                       (id, project_id, name, page_url, feature_id)
                       VALUES (?,?,?,?,?)""",
                    (screen_id, "_sf", screen_name, page_url, feat_def["id"]),
                )
                total_screens += 1

    db.commit()
    print("✅ Retro-engineering _sf SAFe completed:")
    print(f"   • {len(SAFE_MAP)} epics")
    print(f"   • {total_features} features")
    print(f"   • {total_stories} user stories")
    print(f"   • {total_screens} screens linked")


if __name__ == "__main__":
    run()
