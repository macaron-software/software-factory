#!/usr/bin/env python3
"""
Retro-engineering script — Populate SAFe traceability for the _sf project.

Creates: epics + features + user_stories + project_screens
for ALL Software Factory pages, with persona and RBAC per page.

SAFe hierarchy:
  Programme (org_portfolio) → Epic → Feature → Story → project_screen

Usage:
  python3 platform/scripts/retro_sf_safe.py
  DATABASE_URL="" python3 platform/scripts/retro_sf_safe.py  # force SQLite
"""
# Ref: feat-portfolio, feat-backlog

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from platform.db.migrations import get_db  # type: ignore

PROGRAMME_ID = "portfolio-sf-platform"
PROGRAMME_NAME = "Software Factory Platform"

# RBAC roles used in SF
ROLES = {
    "all": ["admin", "project_manager", "developer", "viewer"],
    "admin_only": ["admin"],
    "admin_pm": ["admin", "project_manager"],
    "dev_up": ["admin", "project_manager", "developer"],
    "no_viewer": ["admin", "project_manager", "developer"],
}

# Full SAFe map: programme → epic → feature → { pages, stories, persona, rbac }
SAFE_MAP = [
    # ── EPIC 1: Orchestration & Missions ───────────────────────────────────────
    {
        "id": "epic-orchestration",
        "name": "Orchestration & Missions",
        "description": "Cycle de vie des missions agent : démarrage, suivi, replay, contrôle temps réel.",
        "features": [
            {
                "id": "feat-cockpit",
                "name": "Dashboard / Cockpit",
                "description": "Vue temps réel : missions actives, KPIs plateforme, alertes.",
                "persona": "Tech Lead",
                "rbac": ROLES["all"],
                "pages": ["/", "/cockpit", "/dashboard"],
                "stories": [
                    "Voir les missions actives en temps réel sur le cockpit",
                    "Accéder aux métriques clés de la plateforme depuis la page d'accueil",
                    "Naviguer vers une mission depuis le cockpit en un clic",
                    "Consulter le nombre d'agents actifs et les erreurs récentes",
                ],
            },
            {
                "id": "feat-mission-control",
                "name": "Mission Control",
                "description": "Démarrage, suivi et contrôle des missions agent de bout en bout.",
                "persona": "Tech Lead",
                "rbac": ROLES["dev_up"],
                "pages": ["/mission-control", "/missions/start", "/missions"],
                "stories": [
                    "Lancer une mission avec un prompt libre",
                    "Surveiller l'avancement d'une mission en cours",
                    "Annuler ou interrompre une mission depuis l'interface",
                    "Consulter les détails d'une mission (logs, artefacts, durée)",
                    "Filtrer les missions par statut, projet ou agent",
                ],
            },
            {
                "id": "feat-mission-replay",
                "name": "Sessions & Replay",
                "description": "Replay de sessions agent, historique des conversations, nouvelle session.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/sessions", "/sessions/new", "/missions/{id}/replay"],
                "stories": [
                    "Rejouer une session agent précédente étape par étape",
                    "Consulter l'historique complet des messages d'une session",
                    "Créer une nouvelle session de travail collaboratif",
                    "Exporter les logs d'une session en markdown",
                ],
            },
            {
                "id": "feat-live",
                "name": "Sessions Live",
                "description": "Vue live des conversations agent et cérémonies temps réel.",
                "persona": "Scrum Master",
                "rbac": ROLES["all"],
                "pages": ["/live"],
                "stories": [
                    "Rejoindre une cérémonie live (PI Planning, sprint review)",
                    "Voir la conversation en cours d'un agent en temps réel",
                    "Envoyer un message dans une session live",
                ],
            },
            {
                "id": "feat-mission-detail",
                "name": "Détail Mission",
                "description": "Tableau de bord d'une mission individuelle : logs, artefacts, contrôle.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/missions/{id}", "/missions/{id}/control"],
                "stories": [
                    "Voir le graphe d'exécution d'une mission",
                    "Consulter les artefacts produits par une mission",
                    "Contrôler manuellement les étapes d'une mission",
                    "Lier une mission à un ticket du backlog",
                ],
            },
            {
                "id": "feat-art",
                "name": "ART — Agile Release Train",
                "description": "Gestion de l'ART : équipes, agents, rôles, capacité.",
                "persona": "Release Train Engineer",
                "rbac": ROLES["admin_pm"],
                "pages": ["/art"],
                "stories": [
                    "Visualiser la composition de l'ART (équipes, agents)",
                    "Assigner des rôles et capacités aux équipes",
                    "Suivre la vélocité de l'ART par PI",
                ],
            },
        ],
    },
    # ── EPIC 2: SAFe Backlog & Planning ────────────────────────────────────────
    {
        "id": "epic-backlog",
        "name": "SAFe Backlog & Planning",
        "description": "Portfolio, PI planning, product backlog et gestion de projet.",
        "features": [
            {
                "id": "feat-portfolio",
                "name": "Portfolio",
                "description": "Vue top-level : epics, budgets, thèmes stratégiques.",
                "persona": "Product Manager",
                "rbac": ROLES["admin_pm"],
                "pages": ["/portfolio"],
                "stories": [
                    "Visualiser les epics du portfolio avec leur statut et budget",
                    "Créer et prioriser un nouvel epic depuis le portfolio",
                    "Suivre l'avancement des programmes dans le portfolio",
                ],
            },
            {
                "id": "feat-backlog",
                "name": "Product Backlog",
                "description": "Backlog produit SAFe : features, stories, tasks, priorisation.",
                "persona": "Product Owner",
                "rbac": ROLES["dev_up"],
                "pages": ["/backlog"],
                "stories": [
                    "Créer une nouvelle user story depuis le backlog",
                    "Prioriser les items du backlog par drag-and-drop",
                    "Filtrer le backlog par epic, feature ou sprint",
                    "Affecter un story points à une user story",
                    "Lier une story à une feature SAFe",
                ],
            },
            {
                "id": "feat-pi-board",
                "name": "PI Board — Program Increment",
                "description": "Tableau de bord PI : objectifs, capacité, dépendances, risques.",
                "persona": "Release Train Engineer",
                "rbac": ROLES["dev_up"],
                "pages": ["/pi"],
                "stories": [
                    "Visualiser les objectifs du PI en cours",
                    "Identifier les dépendances inter-équipes sur le PI board",
                    "Suivre l'avancement des features du PI",
                    "Marquer un risque ou un impediment sur le PI board",
                ],
            },
            {
                "id": "feat-ceremonies",
                "name": "Cérémonies SAFe",
                "description": "Planification et suivi des cérémonies : sprint reviews, retros, PI planning.",
                "persona": "Scrum Master",
                "rbac": ROLES["all"],
                "pages": ["/ceremonies"],
                "stories": [
                    "Planifier une nouvelle cérémonie (sprint review, retro)",
                    "Consulter l'agenda des cérémonies de l'ART",
                    "Enregistrer les décisions d'une cérémonie",
                ],
            },
            {
                "id": "feat-projects",
                "name": "Projets",
                "description": "Liste et gestion des projets actifs sur la plateforme.",
                "persona": "Product Manager",
                "rbac": ROLES["all"],
                "pages": ["/projects"],
                "stories": [
                    "Créer un nouveau projet sur la plateforme",
                    "Accéder rapidement à un projet depuis la liste",
                    "Archiver un projet terminé",
                    "Assigner des membres à un projet",
                ],
            },
        ],
    },
    # ── EPIC 3: Agent Management ────────────────────────────────────────────────
    {
        "id": "epic-agents",
        "name": "Agent Management",
        "description": "Création, configuration et gestion des agents IA de la plateforme.",
        "features": [
            {
                "id": "feat-agents-list",
                "name": "Catalogue d'Agents",
                "description": "Liste, recherche et filtrage de tous les agents disponibles.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/agents"],
                "stories": [
                    "Parcourir la liste des agents disponibles",
                    "Filtrer les agents par rôle, compétence ou statut",
                    "Accéder au profil d'un agent depuis le catalogue",
                ],
            },
            {
                "id": "feat-agents-create",
                "name": "Création d'Agent",
                "description": "Création et édition d'un agent : nom, persona, skills, LLM.",
                "persona": "Développeur",
                "rbac": ROLES["no_viewer"],
                "pages": ["/agents/new", "/agents/{id}/edit"],
                "stories": [
                    "Créer un nouvel agent avec son persona et ses skills",
                    "Configurer le modèle LLM d'un agent",
                    "Définir les instructions système d'un agent",
                    "Tester un agent depuis l'interface d'édition",
                ],
            },
            {
                "id": "feat-agent-chat",
                "name": "Chat Agent",
                "description": "Interface de conversation directe avec un agent spécifique.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/agents/{id}/chat"],
                "stories": [
                    "Démarrer une conversation avec un agent depuis son profil",
                    "Envoyer un message et recevoir une réponse en streaming",
                    "Consulter l'historique de conversation avec un agent",
                ],
            },
            {
                "id": "feat-marketplace",
                "name": "Marketplace d'Agents",
                "description": "Bibliothèque d'agents prêts à l'emploi : import, partage, communauté.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/marketplace"],
                "stories": [
                    "Parcourir la marketplace d'agents communautaires",
                    "Importer un agent de la marketplace dans son catalogue",
                    "Publier un agent dans la marketplace",
                    "Évaluer et noter un agent de la marketplace",
                ],
            },
            {
                "id": "feat-skills",
                "name": "Skills & Compétences",
                "description": "Gestion des skills agent : création, assignation, versioning.",
                "persona": "Tech Lead",
                "rbac": ROLES["no_viewer"],
                "pages": ["/skills"],
                "stories": [
                    "Créer un nouveau skill agent (prompt, tool, workflow)",
                    "Assigner un skill à un ou plusieurs agents",
                    "Versionner et rollback un skill",
                ],
            },
        ],
    },
    # ── EPIC 4: Knowledge & Memory ─────────────────────────────────────────────
    {
        "id": "epic-knowledge",
        "name": "Knowledge & Memory",
        "description": "Mémoire des agents, base de connaissances, wiki et évaluations.",
        "features": [
            {
                "id": "feat-memory",
                "name": "Memory Agent",
                "description": "Visualisation et gestion de la mémoire des agents (globale, projet, session).",
                "persona": "Tech Lead",
                "rbac": ROLES["dev_up"],
                "pages": ["/memory"],
                "stories": [
                    "Consulter les entrées mémoire d'un agent",
                    "Effacer ou archiver des entrées mémoire",
                    "Filtrer la mémoire par scope (global, projet, session)",
                    "Ajouter manuellement une entrée en mémoire",
                ],
            },
            {
                "id": "feat-evals",
                "name": "Évaluations LLM",
                "description": "Évaluation de la qualité des réponses agent : benchmarks, scores, comparaisons.",
                "persona": "Data Scientist",
                "rbac": ROLES["dev_up"],
                "pages": ["/evals"],
                "stories": [
                    "Lancer un benchmark d'évaluation sur un agent",
                    "Comparer les scores de deux modèles LLM",
                    "Consulter l'historique des évaluations",
                    "Exporter les résultats d'évaluation en CSV",
                ],
            },
            {
                "id": "feat-wiki",
                "name": "Wiki SF",
                "description": "Base de connaissances interne : documentation, guides, architecture.",
                "persona": "Tech Lead",
                "rbac": ROLES["all"],
                "pages": ["/wiki"],
                "stories": [
                    "Consulter la documentation de la plateforme depuis le wiki",
                    "Créer ou éditer une page wiki",
                    "Rechercher dans le wiki par mot-clé",
                ],
            },
            {
                "id": "feat-jarvis",
                "name": "Jarvis — Assistant IA",
                "description": "Assistant conversationnel intégré pour aide contextuelle et génération de code.",
                "persona": "Développeur",
                "rbac": ROLES["all"],
                "pages": ["/generate"],
                "stories": [
                    "Poser une question à Jarvis sur la plateforme",
                    "Générer du code avec l'assistant IA",
                    "Obtenir des suggestions contextuelles depuis n'importe quelle page",
                ],
            },
        ],
    },
    # ── EPIC 5: Automation & Workflows ─────────────────────────────────────────
    {
        "id": "epic-automation",
        "name": "Automation & Workflows",
        "description": "Workflows d'automatisation, patterns d'orchestration, pipelines CI/CD.",
        "features": [
            {
                "id": "feat-workflows",
                "name": "Workflows",
                "description": "Création et gestion de workflows d'automatisation multi-agents.",
                "persona": "Tech Lead",
                "rbac": ROLES["dev_up"],
                "pages": [
                    "/workflows",
                    "/workflows/new",
                    "/workflows/list",
                    "/workflows/evolution",
                ],
                "stories": [
                    "Créer un nouveau workflow d'automatisation",
                    "Visualiser la liste des workflows actifs",
                    "Déclencher un workflow manuellement",
                    "Consulter l'historique des exécutions d'un workflow",
                    "Voir l'évolution des workflows dans le temps",
                ],
            },
            {
                "id": "feat-patterns",
                "name": "Patterns d'Orchestration",
                "description": "Bibliothèque des 15 patterns d'orchestration multi-agents.",
                "persona": "Architecte",
                "rbac": ROLES["dev_up"],
                "pages": ["/patterns", "/patterns/list", "/patterns/new"],
                "stories": [
                    "Parcourir la bibliothèque des patterns d'orchestration",
                    "Instancier un pattern dans un projet",
                    "Créer un nouveau pattern personnalisé",
                ],
            },
            {
                "id": "feat-tool-builder",
                "name": "Tool Builder",
                "description": "Construction et test d'outils personnalisés pour agents.",
                "persona": "Développeur",
                "rbac": ROLES["no_viewer"],
                "pages": ["/tool-builder"],
                "stories": [
                    "Créer un nouvel outil pour agent (fonction Python/API REST)",
                    "Tester un outil depuis l'interface builder",
                    "Documenter un outil avec sa spec OpenAPI",
                    "Versionner et déployer un outil",
                ],
            },
            {
                "id": "feat-mcps",
                "name": "MCP Servers",
                "description": "Gestion des serveurs MCP (Model Context Protocol) intégrés.",
                "persona": "Architecte",
                "rbac": ROLES["admin_pm"],
                "pages": ["/mcps"],
                "stories": [
                    "Lister les serveurs MCP disponibles",
                    "Activer ou désactiver un serveur MCP",
                    "Configurer les paramètres d'un serveur MCP",
                ],
            },
        ],
    },
    # ── EPIC 6: Observability & Ops ────────────────────────────────────────────
    {
        "id": "epic-observability",
        "name": "Observability & Ops",
        "description": "Monitoring, métriques, qualité, opérations et maintenance de la plateforme.",
        "features": [
            {
                "id": "feat-metrics",
                "name": "Métriques & Analytics",
                "description": "Tableaux de bord : DORA, LLM costs, qualité, monitoring, pipeline, tests.",
                "persona": "Data Scientist",
                "rbac": ROLES["dev_up"],
                "pages": [
                    "/metrics",
                    "/metrics/tab/analytics",
                    "/metrics/tab/dora",
                    "/metrics/tab/knowledge",
                    "/metrics/tab/llm",
                    "/metrics/tab/monitoring",
                    "/metrics/tab/ops",
                    "/metrics/tab/pipeline",
                    "/metrics/tab/quality",
                    "/metrics/tab/tests",
                    "/analytics",
                ],
                "stories": [
                    "Consulter les métriques DORA (lead time, MTTR, deployment frequency)",
                    "Visualiser les coûts LLM par agent et par projet",
                    "Suivre la qualité du code sur le dashboard qualité",
                    "Analyser les performances du pipeline CI/CD",
                    "Exporter les métriques en CSV ou JSON",
                ],
            },
            {
                "id": "feat-monitoring",
                "name": "Monitoring Temps Réel",
                "description": "Surveillance en temps réel de la plateforme : agents, queues, erreurs.",
                "persona": "Ops Engineer",
                "rbac": ROLES["dev_up"],
                "pages": ["/monitoring"],
                "stories": [
                    "Voir le statut de tous les agents en temps réel",
                    "Consulter les files d'attente et la charge du système",
                    "Recevoir des alertes en cas d'erreur critique",
                ],
            },
            {
                "id": "feat-ops",
                "name": "Opérations Plateforme",
                "description": "Auto-heal, chaos engineering, endurance tests, backup/restore.",
                "persona": "Ops Engineer",
                "rbac": ROLES["admin_pm"],
                "pages": ["/ops"],
                "stories": [
                    "Déclencher un auto-heal sur un service dégradé",
                    "Lancer un test de chaos engineering",
                    "Consulter les résultats des tests d'endurance",
                    "Effectuer un backup de la base de données",
                ],
            },
            {
                "id": "feat-quality",
                "name": "Qualité Code",
                "description": "Dashboard qualité : couverture, dette technique, code smells.",
                "persona": "Tech Lead",
                "rbac": ROLES["dev_up"],
                "pages": ["/quality"],
                "stories": [
                    "Consulter le score de qualité global du codebase",
                    "Identifier les fichiers avec le plus de dette technique",
                    "Suivre l'évolution de la couverture de tests",
                ],
            },
        ],
    },
    # ── EPIC 7: Configuration & Administration ─────────────────────────────────
    {
        "id": "epic-admin",
        "name": "Configuration & Administration",
        "description": "Paramètres plateforme, RBAC, utilisateurs, workspaces, intégrations.",
        "features": [
            {
                "id": "feat-settings",
                "name": "Paramètres Plateforme",
                "description": "Configuration globale : LLM, intégrations, notifications, clés API.",
                "persona": "Admin Plateforme",
                "rbac": ROLES["admin_only"],
                "pages": ["/settings", "/setup", "/login"],
                "stories": [
                    "Configurer le fournisseur LLM par défaut",
                    "Gérer les clés API des intégrations tierces",
                    "Activer ou désactiver les notifications Slack/Email",
                    "Configurer les limites de rate limiting",
                ],
            },
            {
                "id": "feat-rbac",
                "name": "RBAC — Gestion des Rôles",
                "description": "Contrôle d'accès : rôles, permissions, utilisateurs, projets.",
                "persona": "Admin Plateforme",
                "rbac": ROLES["admin_only"],
                "pages": ["/rbac", "/admin/users"],
                "stories": [
                    "Assigner un rôle à un utilisateur",
                    "Créer un rôle personnalisé avec des permissions spécifiques",
                    "Gérer les accès par projet",
                    "Consulter le journal d'audit des actions utilisateurs",
                ],
            },
            {
                "id": "feat-workspaces",
                "name": "Workspaces",
                "description": "Gestion des espaces de travail isolés pour les équipes.",
                "persona": "Admin Plateforme",
                "rbac": ROLES["admin_pm"],
                "pages": ["/workspaces"],
                "stories": [
                    "Créer un nouveau workspace pour une équipe",
                    "Configurer les ressources allouées à un workspace",
                    "Inviter des membres dans un workspace",
                    "Archiver un workspace inactif",
                ],
            },
            {
                "id": "feat-org",
                "name": "Organisation & Équipes",
                "description": "Gestion des équipes, groupes, organigramme et SAFe Trains.",
                "persona": "Admin Plateforme",
                "rbac": ROLES["admin_pm"],
                "pages": ["/org", "/teams", "/world"],
                "stories": [
                    "Créer une nouvelle équipe dans l'organisation",
                    "Assigner des agents et utilisateurs à une équipe",
                    "Visualiser l'organigramme de l'organisation",
                    "Gérer les groupes utilisateurs",
                ],
            },
        ],
    },
    # ── EPIC 8: Idéation & Innovation ──────────────────────────────────────────
    {
        "id": "epic-ideation",
        "name": "Idéation & Innovation",
        "description": "Outils d'idéation, génération de projet, design system et métier.",
        "features": [
            {
                "id": "feat-ideation",
                "name": "Idéation Projet",
                "description": "Générateur de projets IA : brief, specs, backlog initial.",
                "persona": "Product Manager",
                "rbac": ROLES["dev_up"],
                "pages": ["/ideation", "/ideation/history"],
                "stories": [
                    "Décrire une idée de projet et obtenir un brief structuré",
                    "Générer automatiquement un backlog initial depuis une idée",
                    "Consulter l'historique des idéations précédentes",
                    "Exporter une idéation en PDF",
                ],
            },
            {
                "id": "feat-mkt-ideation",
                "name": "Idéation Marketing",
                "description": "Idéation marketing : personas, user journeys, campagnes.",
                "persona": "Marketing Manager",
                "rbac": ROLES["dev_up"],
                "pages": ["/mkt-ideation"],
                "stories": [
                    "Générer des personas utilisateurs depuis un brief produit",
                    "Créer un user journey map assisté par IA",
                    "Générer des idées de campagnes marketing",
                ],
            },
            {
                "id": "feat-metier",
                "name": "Domaine Métier",
                "description": "Cartographie métier : processus, règles, domaines fonctionnels.",
                "persona": "Business Analyst",
                "rbac": ROLES["dev_up"],
                "pages": ["/metier"],
                "stories": [
                    "Cartographier un processus métier avec les agents",
                    "Définir les règles métier d'un domaine",
                    "Importer un référentiel métier existant",
                ],
            },
            {
                "id": "feat-product-line",
                "name": "Product Line",
                "description": "Gestion de la ligne de produits : catalogue, roadmap, variantes.",
                "persona": "Product Manager",
                "rbac": ROLES["dev_up"],
                "pages": ["/product-line", "/product"],
                "stories": [
                    "Créer une nouvelle ligne de produit",
                    "Définir les variantes d'un produit",
                    "Visualiser la roadmap produit",
                ],
            },
            {
                "id": "feat-design-system",
                "name": "Design System",
                "description": "Bibliothèque de composants UI, tokens, guidelines.",
                "persona": "Designer",
                "rbac": ROLES["all"],
                "pages": ["/design-system"],
                "stories": [
                    "Parcourir la bibliothèque de composants du design system",
                    "Consulter les tokens de couleur et typographie",
                    "Télécharger les assets du design system",
                ],
            },
        ],
    },
    # ── EPIC 9: Intégrations Externes ──────────────────────────────────────────
    {
        "id": "epic-integrations",
        "name": "Intégrations & Partenaires",
        "description": "Connexion avec les outils externes : DSI, CTO, Mercato, World.",
        "features": [
            {
                "id": "feat-dsi",
                "name": "Vue DSI",
                "description": "Dashboard DSI : coûts, conformité, sécurité, gouvernance.",
                "persona": "DSI",
                "rbac": ROLES["admin_pm"],
                "pages": ["/dsi"],
                "stories": [
                    "Consulter le tableau de bord de gouvernance DSI",
                    "Suivre les coûts d'infrastructure et LLM",
                    "Vérifier la conformité sécurité de la plateforme",
                ],
            },
            {
                "id": "feat-cto",
                "name": "Vue CTO",
                "description": "Dashboard CTO : dette technique, vélocité, innovation.",
                "persona": "CTO",
                "rbac": ROLES["admin_pm"],
                "pages": ["/cto"],
                "stories": [
                    "Consulter le tableau de bord technique du CTO",
                    "Suivre la vélocité d'innovation de l'équipe",
                    "Analyser la dette technique globale",
                ],
            },
            {
                "id": "feat-mercato",
                "name": "Mercato Agents",
                "description": "Marché d'échange d'agents entre équipes et organisations.",
                "persona": "Tech Lead",
                "rbac": ROLES["dev_up"],
                "pages": ["/mercato"],
                "stories": [
                    "Proposer un agent sur le mercato",
                    "Trouver et acquérir un agent depuis le mercato",
                    "Négocier les conditions d'utilisation d'un agent",
                ],
            },
            {
                "id": "feat-toolbox",
                "name": "Toolbox",
                "description": "Boîte à outils partagée : utilitaires, scripts, ressources.",
                "persona": "Développeur",
                "rbac": ROLES["dev_up"],
                "pages": ["/toolbox"],
                "stories": [
                    "Accéder aux utilitaires partagés de la plateforme",
                    "Partager un outil avec l'équipe",
                ],
            },
            {
                "id": "feat-onboarding",
                "name": "Onboarding",
                "description": "Parcours d'onboarding guidé pour les nouveaux utilisateurs.",
                "persona": "Nouveau Utilisateur",
                "rbac": ROLES["all"],
                "pages": ["/onboarding"],
                "stories": [
                    "Suivre le tutoriel d'onboarding pas à pas",
                    "Créer son premier projet lors de l'onboarding",
                    "Configurer son profil lors de l'onboarding",
                ],
            },
        ],
    },
    # ── EPIC 10: Annotation & Traceability ─────────────────────────────────────
    {
        "id": "epic-annotation",
        "name": "Annotation & Traceability",
        "description": "Studio d'annotation visuelle, traceability SAFe, feedback et wireframe mode.",
        "features": [
            {
                "id": "feat-annotate",
                "name": "Annotation Studio",
                "description": "Click-to-annotate, création de tickets TMA, gestion des annotations.",
                "persona": "Product Owner",
                "rbac": ROLES["all"],
                "pages": ["/annotate/{project_id}"],
                "stories": [
                    "Annoter un élément UI en cliquant dessus",
                    "Créer un ticket TMA depuis une annotation",
                    "Consulter toutes les annotations d'un projet",
                    "Exporter les annotations en markdown",
                    "Filtrer les annotations par type (bug, feature, question)",
                ],
            },
        ],
    },
]


def slug(url: str) -> str:
    return url.replace("/", "-").lstrip("-") or "home"


def run():
    db = get_db()

    # ── Ensure new columns exist ────────────────────────────────────────────────
    for attempt in range(2):
        try:
            db.execute("ALTER TABLE features ADD COLUMN persona TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE features ADD COLUMN rbac_roles TEXT DEFAULT '[]'")
        except Exception:
            pass
        try:
            db.execute(
                "ALTER TABLE project_screens ADD COLUMN rbac_roles TEXT DEFAULT '[]'"
            )
        except Exception:
            pass

    # ── Programme ───────────────────────────────────────────────────────────────
    db.execute(
        "INSERT OR REPLACE INTO org_portfolios (id, name, description) VALUES (?,?,?)",
        (
            PROGRAMME_ID,
            PROGRAMME_NAME,
            "Plateforme d'orchestration d'agents IA — Software Factory",
        ),
    )
    print(f"[ok] Programme: {PROGRAMME_NAME}")

    total_features = total_stories = total_screens = 0

    for epic_def in SAFE_MAP:
        # ── Epic ────────────────────────────────────────────────────────────────
        db.execute(
            "INSERT OR REPLACE INTO epics (id, programme_id, name, description, status) VALUES (?,?,?,?,?)",
            (
                epic_def["id"],
                PROGRAMME_ID,
                epic_def["name"],
                epic_def["description"],
                "in_progress",
            ),
        )
        print(f"\n  Epic: {epic_def['name']}")

        for feat_def in epic_def["features"]:
            # ── Feature ─────────────────────────────────────────────────────────
            rbac_json = json.dumps(feat_def.get("rbac", []))
            db.execute(
                "INSERT OR REPLACE INTO features "
                "(id, epic_id, name, description, status, priority, persona, rbac_roles) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    feat_def["id"],
                    epic_def["id"],
                    feat_def["name"],
                    feat_def["description"],
                    "in_progress",
                    5,
                    feat_def.get("persona", ""),
                    rbac_json,
                ),
            )
            total_features += 1

            # ── User Stories ─────────────────────────────────────────────────────
            for i, story in enumerate(feat_def.get("stories", [])):
                story_id = f"{feat_def['id']}-s{i + 1:02d}"
                db.execute(
                    "INSERT OR REPLACE INTO user_stories (id, feature_id, title, status, priority) VALUES (?,?,?,?,?)",
                    (
                        story_id,
                        feat_def["id"],
                        story,
                        "backlog",
                        len(feat_def["stories"]) - i,
                    ),
                )
                total_stories += 1

            # ── Project Screens ──────────────────────────────────────────────────
            for page_url in feat_def.get("pages", []):
                # Skip parametrized URLs for screen linking
                if "{" in page_url:
                    continue
                screen_id = slug(page_url)
                screen_name = (
                    page_url.strip("/").replace("-", " ").replace("/", " — ").title()
                    or "Home"
                )
                db.execute(
                    "INSERT OR REPLACE INTO project_screens "
                    "(id, project_id, name, page_url, feature_id, rbac_roles) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        screen_id,
                        "_sf",
                        screen_name,
                        page_url,
                        feat_def["id"],
                        rbac_json,
                    ),
                )
                total_screens += 1

            print(
                f"    Feature: {feat_def['name']} | persona={feat_def.get('persona', '')} | {len(feat_def.get('pages', []))} pages | {len(feat_def.get('stories', []))} stories | rbac={feat_def.get('rbac', [])}"
            )

    try:
        db.commit()
    except Exception:
        pass

    print(
        f"\nDone: {len(SAFE_MAP)} epics | {total_features} features | {total_stories} stories | {total_screens} screens"
    )


if __name__ == "__main__":
    run()
