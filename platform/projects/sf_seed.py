"""Default backlog seed for the Software Factory project.

Populated at every startup (idempotent — ON CONFLICT DO NOTHING).
Covers the SF web platform + macOS native app + agents/patterns ecosystem.
PostgreSQL only — uses TEXT PRIMARY KEY, TIMESTAMP DEFAULT CURRENT_TIMESTAMP.
"""
# Ref: feat-projects

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Personas ──────────────────────────────────────────────────────────────────
# 7 user archetypes for the SF product. Stored in the `personas` table.

SF_PERSONAS: list[dict] = [
    {
        "id": "sf-p01-admin-cto",
        "project_id": "software-factory",
        "name": "Sylvain — Admin / CTO",
        "role": "admin",
        "goals": (
            "Piloter l'ensemble de la plateforme. "
            "Configurer les LLMs, les instances SF (local/OVH/AZ) et le RBAC. "
            "Surveiller les KPIs en temps réel. "
            "Déclencher des déploiements canary sans downtime."
        ),
        "pain_points": (
            "Trop d'onglets ouverts entre l'app macOS, le cockpit web et le terminal. "
            "Secrets dispersés entre .env, Infisical et Azure Key Vault. "
            "Latence LLM lors des pics de charge multi-missions."
        ),
        "technical_level": "expert",
    },
    {
        "id": "sf-p02-tech-lead",
        "project_id": "software-factory",
        "name": "Thomas — Tech Lead ART",
        "role": "lead",
        "goals": (
            "Piloter les missions SAFe (épics, features, stories, WSJF). "
            "Sélectionner le bon pattern d'orchestration pour chaque sprint. "
            "Reviewer l'architecture et valider les PR des agents. "
            "Maintenir la qualité du code (zero-skip, TDD)."
        ),
        "pain_points": (
            "Difficile de suivre 5 missions en parallèle sans vue globale. "
            "Le guard adversarial rejette parfois des outputs corrects. "
            "Pas de diff visuel entre deux runs de mission."
        ),
        "technical_level": "expert",
    },
    {
        "id": "sf-p03-analyst",
        "project_id": "software-factory",
        "name": "Chloé — Analyste BI & Data",
        "role": "member",
        "goals": (
            "Lancer des sessions agents pour analyser des datasets. "
            "Faire des recherches deep search dans la mémoire projet. "
            "Consulter le tableau analytics (team fitness, leaderboard WSJF). "
            "Travailler offline avec SF Inside (train, avion)."
        ),
        "pain_points": (
            "Les sessions longues (deep search) ne reprennent pas après déconnexion. "
            "Pas d'export CSV des résultats d'analytics. "
            "L'interface web est peu lisible sur petit écran."
        ),
        "technical_level": "medium",
    },
    {
        "id": "sf-p04-product-owner",
        "project_id": "software-factory",
        "name": "Inès — Product Owner",
        "role": "member",
        "goals": (
            "Gérer le backlog SAFe (épics/features/stories) avec WSJF. "
            "Piloter le PI Board avec drag-drop des stories. "
            "Lancer des sessions d'idéation multi-agents. "
            "Générer des personas et user journeys depuis un brief produit."
        ),
        "pain_points": (
            "La saisie WSJF avec 4 sliders est fastidieuse sur le web. "
            "Pas de vue Kanban des stories par sprint. "
            "L'idéation ne sauvegarde pas les findings automatiquement."
        ),
        "technical_level": "low",
    },
    {
        "id": "sf-p05-sre-devops",
        "project_id": "software-factory",
        "name": "Karim — DevOps / SRE",
        "role": "member",
        "goals": (
            "Gérer les incidents TMA P0-P4 avec SLA et escalade. "
            "Déclencher des hotfix via le pattern Fix TDD. "
            "Surveiller l'observabilité (health checks, logs, métriques). "
            "Déployer sur OVH (2 nœuds HA) et Azure VM sans downtime."
        ),
        "pain_points": (
            "Le drain graceful coupe parfois des sessions SSE en cours. "
            "Rollback manuel trop lent si le canary échoue. "
            "Pas d'alerte automatique quand un nœud passe offline."
        ),
        "technical_level": "expert",
    },
    {
        "id": "sf-p06-mobile-lead",
        "project_id": "software-factory",
        "name": "Lin Wei — Mobile / macOS Lead",
        "role": "lead",
        "goals": (
            "Utiliser l'app macOS SwiftUI native comme interface principale. "
            "Piloter plusieurs instances SF (Inside + OVH + AZ) depuis l'app. "
            "Gérer les équipes iOS/Android dans l'org SAFe. "
            "Détecter automatiquement les modèles MLX/Ollama sur le Mac."
        ),
        "pain_points": (
            "L'onboarding macOS ne détecte pas toujours Ollama (port non standard). "
            "Switch d'instance sans reconnexion SSE. "
            "L'app ne persiste pas les sessions après redémarrage."
        ),
        "technical_level": "expert",
    },
    {
        "id": "sf-p07-platform-lead",
        "project_id": "software-factory",
        "name": "Marc — Platform Lead / OSS",
        "role": "lead",
        "goals": (
            "Maintenir et améliorer le cœur de la plateforme (patterns, moteur, API). "
            "Contribuer à l'auto-amélioration : les agents lisent et écrivent leur propre code. "
            "Publier les agents et skills dans le Mercato. "
            "Benchmarker l'évolution Thompson Sampling des équipes Darwin."
        ),
        "pain_points": (
            "Le cache tool schemas (_TOOL_SCHEMAS) se désynchronise sans redémarrage. "
            "Les migrations SQLite ne sont pas versionnées explicitement. "
            "Difficile de tester les patterns en isolation sans lancer le serveur."
        ),
        "technical_level": "expert",
    },
]

# ── Epics (missions) ──────────────────────────────────────────────────────────
# 5 epics couvrant la totalité du produit SF.

SF_EPICS: list[dict] = [
    {
        "id": "sf-epic-platform",
        "project_id": "software-factory",
        "name": "Plateforme Web SF",
        "description": (
            "Cœur web de la Software Factory : FastAPI + HTMX + SSE. "
            "Couvre toutes les routes, templates, sessions, missions, backlog, "
            "idéation, analytics, TMA et sécurité."
        ),
        "type": "feature",
        "status": "in_progress",
        "wsjf_score": 9.2,
    },
    {
        "id": "sf-epic-macos",
        "project_id": "software-factory",
        "name": "App macOS Native SF Swift",
        "description": (
            "Application macOS 100% native SwiftUI (zero HTML). "
            "SF Inside embarqué + multi-instances (OVH/AZ HA). "
            "Onboarding LLM, org SAFe, sessions chat, backlog PI, analytics, TMA."
        ),
        "type": "feature",
        "status": "in_progress",
        "wsjf_score": 8.5,
    },
    {
        "id": "sf-epic-agents",
        "project_id": "software-factory",
        "name": "Agents, Patterns & Skills",
        "description": (
            "133+ agents SAFe, 12 patterns d'orchestration, 23 workflows, 1271 skills. "
            "Mercato (catalogue), évolution darwinienne (Thompson Sampling), "
            "MCP Servers, RLM deep search."
        ),
        "type": "feature",
        "status": "in_progress",
        "wsjf_score": 9.0,
    },
    {
        "id": "sf-epic-tma",
        "project_id": "software-factory",
        "name": "TMA & Maintien en Condition Opérationnelle",
        "description": (
            "Détection → Triage P0-P4 → Diagnostic → Fix TDD → "
            "Non-régression → Hotfix Deploy → Postmortem. "
            "SLA automatisé, escalade, wiki runbooks."
        ),
        "type": "tma",
        "status": "active",
        "wsjf_score": 8.8,
    },
    {
        "id": "sf-epic-security",
        "project_id": "software-factory",
        "name": "Sécurité & RBAC",
        "description": (
            "RBAC rôles (admin/lead/member/viewer), audit log, "
            "scan TruffleHog, OWASP top-10, dévsecops pipeline, "
            "gestion secrets Infisical."
        ),
        "type": "security",
        "status": "active",
        "wsjf_score": 8.0,
    },
]

# ── Features ──────────────────────────────────────────────────────────────────
# 30 features réparties sur les 5 épics.

SF_FEATURES: list[dict] = [
    # ── Epic: Plateforme Web (F-WEB-01..10) ───────────────────────────────
    {
        "id": "sf-f-web-01",
        "epic_id": "sf-epic-platform",
        "name": "Onboarding & configuration initiale",
        "description": "Premier démarrage : saisie des clés LLM, configuration des fournisseurs (Azure/OpenAI/MiniMax), setup instances SF distantes avec token OAuth.",
        "acceptance_criteria": "L'admin peut compléter le wizard en < 3 minutes. Les clés LLM sont validées avant sauvegarde. La page d'accueil s'affiche après onboarding.",
        "priority": 10,
        "story_points": 8,
    },
    {
        "id": "sf-f-web-02",
        "epic_id": "sf-epic-platform",
        "name": "Organisation SAFe multi-niveaux",
        "description": "Navigation Portfolio → ART → Team → Agent. Création/édition/suppression. WIP limits par équipe. Affichage Thompson Sampling scores.",
        "acceptance_criteria": "Hiérarchie complète visible en < 2 clics. WIP limit met à jour le badge en temps réel. Mercato accessible depuis la vue agent.",
        "priority": 9,
        "story_points": 13,
    },
    {
        "id": "sf-f-web-03",
        "epic_id": "sf-epic-platform",
        "name": "Sessions agents interactives",
        "description": "Chat multi-agents avec streaming SSE. Affichage tool calls en temps réel. Historique et recherche fulltext. Export transcript. Patterns sélectionnables.",
        "acceptance_criteria": "Réponse agent < 2s après envoi (TTFB). Tool calls visibles dans la timeline. Export JSON/TXT disponible. Recherche FTS5 sur tout l'historique.",
        "priority": 10,
        "story_points": 13,
    },
    {
        "id": "sf-f-web-04",
        "epic_id": "sf-epic-platform",
        "name": "Missions & exécution SAFe",
        "description": "Création de missions (type: feature/tma/security/debt). Sélection de workflow. Suivi des phases (Discovery/Arch/Dev/QA/Deploy/Retro). Adversarial guard. Pause/résume/stop.",
        "acceptance_criteria": "Mission démarre en < 5s. Phases visibles avec % avancement. L'admin peut interrompre à tout moment. Le guard adversarial log les rejets.",
        "priority": 10,
        "story_points": 21,
    },
    {
        "id": "sf-f-web-05",
        "epic_id": "sf-epic-platform",
        "name": "Backlog PI — Epics / Features / Stories / WSJF",
        "description": "CRUD complet Épics → Features → User Stories. Calcul WSJF automatique (BV/TC/RR/JD). Assignation sprint. Traceabilité code. Vue PI Board.",
        "acceptance_criteria": "WSJF recalculé dès modification d'un slider. Stories drag-droppables entre sprints. Traceabilité affiche les fichiers modifiés par story.",
        "priority": 9,
        "story_points": 13,
    },
    {
        "id": "sf-f-web-06",
        "epic_id": "sf-epic-platform",
        "name": "Idéation & Discovery",
        "description": "Sessions d'idéation multi-agents (brainstorm, personas, JTBD, prioritisation MoSCoW). Sauvegarde auto des findings. Export rapport PDF.",
        "acceptance_criteria": "Session démarre avec 3+ agents en < 10s. Findings sauvegardés toutes les 30s. Export PDF généré en < 5s.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-web-07",
        "epic_id": "sf-epic-platform",
        "name": "Mémoire & Deep Search (RLM)",
        "description": "4 couches mémoire (pattern/project/global/session). Recherche sémantique FTS5. RLM WRITE-EXECUTE-OBSERVE-DECIDE. Persistance inter-sessions.",
        "acceptance_criteria": "Deep search retourne des résultats pertinents en < 10s. Mémoire projet survit au redémarrage. RLM log chaque itération.",
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-web-08",
        "epic_id": "sf-epic-platform",
        "name": "TMA — Incidents & Wiki",
        "description": "Création incidents P0-P4. Dashboard TMA avec SLA. Escalade automatique. Wiki runbooks/postmortems avec Markdown + recherche FTS5.",
        "acceptance_criteria": "Incident P0 déclenche une alerte immédiate. SLA visible avec RAG (vert/orange/rouge). Wiki pleinement navigable et éditable.",
        "priority": 9,
        "story_points": 8,
    },
    {
        "id": "sf-f-web-09",
        "epic_id": "sf-epic-platform",
        "name": "Analytics & Cockpit",
        "description": "KPIs globaux (agents actifs, sessions, missions, tasks). Leaderboard WSJF. Team fitness graph. Évolution darwinienne. Export CSV.",
        "acceptance_criteria": "Cockpit se charge en < 1s. Graphiques réactifs (HTMX polling 30s). Export CSV inclut toutes les colonnes visibles.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-web-10",
        "epic_id": "sf-epic-platform",
        "name": "Notifications & événements temps réel",
        "description": "Centre de notifications (mission terminée, incident créé, agent online). Badge compteur. Préférences notification par type. SSE event bus.",
        "acceptance_criteria": "Notification arrivée en < 2s après l'événement. Badge mis à jour sans reload. Préférences persistées par utilisateur.",
        "priority": 6,
        "story_points": 5,
    },
    # ── Epic: App macOS Native (F-MAC-01..10) ──────────────────────────────
    {
        "id": "sf-f-mac-01",
        "epic_id": "sf-epic-macos",
        "name": "Installation & Onboarding natif macOS",
        "description": "Wizard 4 étapes : Welcome → Config LLMs (MLX/Ollama/OpenAI/Azure) → Instances SF → Terminé. Détection automatique modèles. Persistance UserDefaults.",
        "acceptance_criteria": "Onboarding complet en < 2 minutes. Modèles MLX et Ollama détectés via ping en < 5s. Config sauvegardée après redémarrage.",
        "priority": 10,
        "story_points": 13,
    },
    {
        "id": "sf-f-mac-02",
        "epic_id": "sf-epic-macos",
        "name": "SF Inside — moteur embarqué in-process",
        "description": "Moteur SF sans HTTP, intégré dans l'app Swift. Toujours disponible (InstanceKind.inside). Sessions agents offline via LLM local (MLX/Ollama). Pas de serveur externe requis.",
        "acceptance_criteria": "Session SF Inside démarre sans réseau. LLM local répond en streaming. SF Inside ne peut pas être supprimé de la liste des instances.",
        "priority": 10,
        "story_points": 21,
    },
    {
        "id": "sf-f-mac-03",
        "epic_id": "sf-epic-macos",
        "name": "Multi-instances — pilotage SF distantes",
        "description": "Switch en 1 clic entre : SF Inside, SF Local Dev (:8090), SF OVH Demo, SF AZ Prod (nœud-1/nœud-2 HA). Statut online/offline en temps réel. Ajout instance avec token OAuth.",
        "acceptance_criteria": "Switch < 500ms. Statut mis à jour toutes les 30s. Token OAuth stocké dans le Keychain macOS. Nœuds HA affichés séparément.",
        "priority": 9,
        "story_points": 13,
    },
    {
        "id": "sf-f-mac-04",
        "epic_id": "sf-epic-macos",
        "name": "Organisation SAFe native SwiftUI",
        "description": "Navigation Portfolio → ART → Team → Agent en NavigationSplitView. WIP badges. Fiches agent avec skills et score Thompson. Création/édition in-app.",
        "acceptance_criteria": "Navigation tri-colonne fonctionnelle sur macOS 13+. WIP badge rouge si dépassé. Fiche agent affiche 10+ skills. Édition persiste via API.",
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-mac-05",
        "epic_id": "sf-epic-macos",
        "name": "Sessions chat natif avec streaming",
        "description": "Interface chat SwiftUI avec SSE natif (URLSession). Streaming token-par-token. Affichage tool calls inline. Indicateur de frappe. Copier/partager message.",
        "acceptance_criteria": "Premier token affiché en < 1s. Tool calls visibles en temps réel. Copier message au format Markdown. Session persistée localement.",
        "priority": 10,
        "story_points": 13,
    },
    {
        "id": "sf-f-mac-06",
        "epic_id": "sf-epic-macos",
        "name": "Backlog PI natif — Epics, Features, Stories",
        "description": "CRUD complet SwiftUI pour Épics/Features/Stories. Sliders WSJF (BV/TC/RR/JD 1-10). PI Board avec colonnes par sprint. Score WSJF calculé en direct.",
        "acceptance_criteria": "WSJF recalculé à chaque modification de slider. PI Board navigable. Création story < 3 tappes. Synchronisation bidirectionnelle avec l'instance active.",
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-mac-07",
        "epic_id": "sf-epic-macos",
        "name": "Mercato & Évolution Darwin",
        "description": "Catalogue Mercato des agents avec filtres (ART, skill, score). Scores Thompson Sampling et fitness darwinienne. Vue évolution temporelle par agent.",
        "acceptance_criteria": "Liste Mercato chargée en < 2s. Filtres combinables. Graphique fitness sur 10 derniers runs. Export catalogue CSV.",
        "priority": 6,
        "story_points": 8,
    },
    {
        "id": "sf-f-mac-08",
        "epic_id": "sf-epic-macos",
        "name": "Analytics & Cockpit macOS",
        "description": "Tableau de bord KPIs temps réel : agents actifs, sessions, missions en cours, taux succès adversarial. Charts natifs SwiftUI Charts. Export rapport.",
        "acceptance_criteria": "Cockpit se rafraîchit toutes les 30s. Charts SwiftUI avec animation. Export PDF via PrintKit. Mode plein écran disponible.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-mac-09",
        "epic_id": "sf-epic-macos",
        "name": "Settings & gestion des LLMs",
        "description": "Panneau Settings macOS natif : LLMs (endpoint/modèle/clé/détection), instances SF, thème, raccourcis clavier. Import/export config JSON.",
        "acceptance_criteria": "Détection modèles en 1 clic dans Settings. Import/export JSON validé. Raccourcis clavier configurable. Settings accessibles via Cmd+,.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-mac-10",
        "epic_id": "sf-epic-macos",
        "name": "Notifications & intégration macOS",
        "description": "Notifications natives macOS (UserNotifications) pour incidents P0, missions terminées, agents offline. Badge app dock. Menu bar item (optionnel).",
        "acceptance_criteria": "Notification P0 reçue en < 5s. Badge dock mis à jour. Permission notifications demandée au premier lancement. Menu bar toggle configurable.",
        "priority": 5,
        "story_points": 5,
    },
    # ── Epic: Agents, Patterns & Skills (F-AGT-01..06) ────────────────────
    {
        "id": "sf-f-agt-01",
        "epic_id": "sf-epic-agents",
        "name": "8 patterns d'orchestration",
        "description": "Patterns : Waterfall, Parallel, Debate, Veto, Leader, Pipeline, Adversarial, Recursive. Sélection par mission. Visualisation graphe en temps réel.",
        "acceptance_criteria": "Chaque pattern disponible dans le sélecteur de mission. Graphe de progression affiché pendant l'exécution. Log de chaque étape accessible.",
        "priority": 10,
        "story_points": 13,
    },
    {
        "id": "sf-f-agt-02",
        "epic_id": "sf-epic-agents",
        "name": "Mercato — catalogue agents & publication",
        "description": "Catalogue public des agents avec score, catégorie, tags, ART. Publication d'un agent depuis l'interface. Notation et commentaires. Import depuis YAML.",
        "acceptance_criteria": "Agent publié visible dans le Mercato en < 10s. Filtres par ART/skill fonctionnels. Import YAML idempotent. Notation 1-5 étoiles.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-agt-03",
        "epic_id": "sf-epic-agents",
        "name": "Évolution darwinienne — Thompson Sampling",
        "description": "Sélection bayésienne des meilleurs agents par mission type. Score Beta(α,β) mis à jour après chaque run. Historique team fitness. Darwin Teams auto-rebalancés.",
        "acceptance_criteria": "Score Thompson mis à jour après chaque run. Graphique évolution visible sur 30 jours. Rebalancement automatique sans interruption des missions.",
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-agt-04",
        "epic_id": "sf-epic-agents",
        "name": "Skills — catalogue 1271 et exécution",
        "description": "1271 skills répartis en 95 domaines. Recherche fulltext. Import depuis GitHub. Exécution contextuelle par agent. Versioning des skills.",
        "acceptance_criteria": "Recherche skill retourne résultats en < 500ms. Import GitHub via URL repo. Chaque skill affiche son domaine et sa description. Version visible.",
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-agt-05",
        "epic_id": "sf-epic-agents",
        "name": "MCP Servers — configuration et tool calls",
        "description": "Configuration des MCP servers (platform/lrm/custom) par agent. Affichage des tool calls MCP dans les logs de session. Test de connexion MCP.",
        "acceptance_criteria": "MCP server ajouté en < 1 minute. Tool calls MCP visibles dans la timeline. Test ping MCP retourne statut en < 3s.",
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-agt-06",
        "epic_id": "sf-epic-agents",
        "name": "Workflows — création et exécution de graphes",
        "description": "Éditeur de workflow avec nodes/edges (agents + patterns). Lancement et suivi en temps réel. Sessions auto-créées par nœud. Import/export YAML.",
        "acceptance_criteria": "Workflow de 5 nœuds crée automatiquement 5 sessions. Graphe d'état mis à jour en temps réel. Export YAML réimportable.",
        "priority": 7,
        "story_points": 8,
    },
    # ── Epic: TMA (F-TMA-01..04) ──────────────────────────────────────────
    {
        "id": "sf-f-tma-01",
        "epic_id": "sf-epic-tma",
        "name": "Détection & triage incidents P0-P4",
        "description": "Création manuelle ou auto (watchdog) des incidents. Priorité P0-P4 avec SLA. Dashboard TMA avec RAG status. Assignation à un agent/équipe.",
        "acceptance_criteria": "Incident P0 déclenche alerte immédiate. SLA affiché en secondes restantes. Assignation en 1 clic. Watchdog détecte les missions bloquées en < 60s.",
        "priority": 10,
        "story_points": 8,
    },
    {
        "id": "sf-f-tma-02",
        "epic_id": "sf-epic-tma",
        "name": "Pattern Fix TDD — diagnostic et correction",
        "description": "Pattern TMA : red (test qui échoue) → diagnostic LLM → green (fix minimal) → refactor → non-régression. Adversarial guard sur chaque étape.",
        "acceptance_criteria": "Pattern Fix TDD disponible pour tout incident. Tests de non-régression exécutés automatiquement. Adversarial guard log les tentatives de fake fix.",
        "priority": 9,
        "story_points": 13,
    },
    {
        "id": "sf-f-tma-03",
        "epic_id": "sf-epic-tma",
        "name": "Hotfix Deploy — déploiement sans downtime",
        "description": "Déploiement hotfix sur OVH HA (nœud-1/nœud-2) et Azure VM. Drain graceful avant maintenance. Health check post-déploiement. Rollback automatique si KO.",
        "acceptance_criteria": "Hotfix déployé en < 5 minutes. Drain graceful ne coupe pas les SSE actives. Rollback déclenché si /api/ready retourne 503 après 60s.",
        "priority": 9,
        "story_points": 8,
    },
    {
        "id": "sf-f-tma-04",
        "epic_id": "sf-epic-tma",
        "name": "Postmortem & Wiki runbooks",
        "description": "Création de pages wiki Markdown liées aux incidents. Templates postmortem (chronologie/cause/impact/actions). Recherche FTS5. Export PDF.",
        "acceptance_criteria": "Page wiki créée depuis l'incident en 1 clic. Template postmortem pré-rempli avec données incident. FTS5 retourne résultats en < 1s.",
        "priority": 7,
        "story_points": 5,
    },
    # ── Epic: Sécurité & RBAC (F-SEC-01..02) ─────────────────────────────
    {
        "id": "sf-f-sec-01",
        "epic_id": "sf-epic-security",
        "name": "RBAC — rôles et permissions par projet",
        "description": "4 rôles : admin (tout), lead (missions+agents), member (sessions+backlog), viewer (lecture). Permissions granulaires par endpoint. JWT + refresh tokens.",
        "acceptance_criteria": "Un viewer ne peut pas créer de mission (403). JWT expiré redirige vers login. Changement de rôle effectif en < 5s. Audit log de chaque permission check.",
        "priority": 9,
        "story_points": 13,
    },
    {
        "id": "sf-f-sec-02",
        "epic_id": "sf-epic-security",
        "name": "Audit, secrets et conformité",
        "description": "Journal d'audit de toutes les actions sensibles. Scan TruffleHog sur push. Infisical pour la rotation des secrets. OWASP top-10 checklist automatisée.",
        "acceptance_criteria": "Chaque action admin tracée dans l'audit log. TruffleHog bloque le push si secret détecté. Infisical sync < 5s après rotation. OWASP rapport généré.",
        "priority": 8,
        "story_points": 8,
    },
]

# ── User Stories ──────────────────────────────────────────────────────────────
# 60 user stories en format "En tant que <persona>, je veux <action> afin de <bénéfice>".
# Avec critères d'acceptance Gherkin (Given/When/Then).

SF_STORIES: list[dict] = [
    # F-WEB-01: Onboarding
    {
        "id": "sf-us-001",
        "feature_id": "sf-f-web-01",
        "title": "En tant qu'admin, je veux configurer le LLM fournisseur au premier démarrage afin de commencer à utiliser la SF sans toucher à des fichiers .env.",
        "acceptance_criteria": "Given: première connexion / When: wizard ouvert / Then: formulaire LLM pré-rempli avec Azure + validation clé API en temps réel.",
        "story_points": 3,
        "priority": 10,
    },
    {
        "id": "sf-us-002",
        "feature_id": "sf-f-web-01",
        "title": "En tant qu'admin, je veux ajouter une instance SF distante (OVH/AZ) avec un token OAuth afin de piloter plusieurs SF depuis une seule interface.",
        "acceptance_criteria": "Given: page instances / When: URL + token saisi / Then: ping vérifie la connectivité et le token, statut affiché en < 3s.",
        "story_points": 3,
        "priority": 9,
    },
    # F-WEB-02: Organisation SAFe
    {
        "id": "sf-us-003",
        "feature_id": "sf-f-web-02",
        "title": "En tant que Tech Lead, je veux visualiser la hiérarchie Portfolio > ART > Team > Agent en un seul écran afin d'avoir une vue globale de l'organisation.",
        "acceptance_criteria": "Given: page Org / When: navigation breadcrumb / Then: arbre complet visible avec badges WIP par team.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-004",
        "feature_id": "sf-f-web-02",
        "title": "En tant que PO, je veux créer une équipe avec WIP limit et assigner des agents afin de structurer un nouvel ART.",
        "acceptance_criteria": "Given: formulaire team / When: WIP limit saisi + agents sélectionnés / Then: team créée, badge WIP visible sur l'ART.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-005",
        "feature_id": "sf-f-web-02",
        "title": "En tant qu'admin, je veux voir les scores Thompson Sampling de chaque agent sur la page org afin d'identifier les meilleurs performers.",
        "acceptance_criteria": "Given: fiche agent / When: onglet Évolution / Then: graphique Beta(α,β) sur 30 derniers runs affiché.",
        "story_points": 3,
        "priority": 7,
    },
    # F-WEB-03: Sessions
    {
        "id": "sf-us-006",
        "feature_id": "sf-f-web-03",
        "title": "En tant que Tech Lead, je veux démarrer une session avec un pattern spécifique (Debate/Parallel) afin d'adapter l'orchestration au besoin.",
        "acceptance_criteria": "Given: nouvelle session / When: pattern sélectionné dans le dropdown / Then: session démarre avec les agents du pattern configurés.",
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-007",
        "feature_id": "sf-f-web-03",
        "title": "En tant qu'analyste, je veux rechercher dans l'historique de toutes mes sessions via FTS5 afin de retrouver un résultat passé.",
        "acceptance_criteria": "Given: barre de recherche sessions / When: requête tapée / Then: résultats FTS5 en < 500ms avec snippet mis en évidence.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-008",
        "feature_id": "sf-f-web-03",
        "title": "En tant qu'utilisateur, je veux exporter le transcript d'une session en Markdown afin de le partager ou l'archiver.",
        "acceptance_criteria": "Given: session terminée / When: clic Export / Then: fichier .md téléchargé avec tous les messages et tool calls.",
        "story_points": 2,
        "priority": 6,
    },
    # F-WEB-04: Missions
    {
        "id": "sf-us-009",
        "feature_id": "sf-f-web-04",
        "title": "En tant que PO, je veux créer une mission avec type (feature/tma/security/debt) et la lier à un projet afin de lancer l'exécution SAFe.",
        "acceptance_criteria": "Given: formulaire mission / When: type + projet sélectionnés / Then: mission créée, workflow auto-assigné selon le type.",
        "story_points": 3,
        "priority": 10,
    },
    {
        "id": "sf-us-010",
        "feature_id": "sf-f-web-04",
        "title": "En tant que Tech Lead, je veux suivre les phases d'exécution d'une mission en temps réel (Discovery/Dev/QA/Deploy) afin de détecter les blocages.",
        "acceptance_criteria": "Given: mission en cours / When: page mission / Then: stepper de phases avec statut coloré (en cours/terminé/bloqué) et % avancement.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-011",
        "feature_id": "sf-f-web-04",
        "title": "En tant qu'admin, je veux mettre en pause ou arrêter une mission en cours afin d'intervenir manuellement si nécessaire.",
        "acceptance_criteria": "Given: mission running / When: clic Pause/Stop / Then: mission passe en statut paused/stopped, agents interrompus proprement.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-012",
        "feature_id": "sf-f-web-04",
        "title": "En tant que Tech Lead, je veux voir le journal de l'adversarial guard (rejets/passages) afin de comprendre les décisions de qualité.",
        "acceptance_criteria": "Given: run de mission / When: onglet Guard / Then: liste des checks L0/L1 avec score, raison et output tronqué.",
        "story_points": 3,
        "priority": 7,
    },
    # F-WEB-05: Backlog PI
    {
        "id": "sf-us-013",
        "feature_id": "sf-f-web-05",
        "title": "En tant que PO, je veux créer une feature avec description et acceptance criteria afin de la lier à un épic existant.",
        "acceptance_criteria": "Given: page épic / When: + Feature / Then: formulaire CRUD avec champ acceptance_criteria obligatoire.",
        "story_points": 2,
        "priority": 9,
    },
    {
        "id": "sf-us-014",
        "feature_id": "sf-f-web-05",
        "title": "En tant que PO, je veux scorer une feature avec les 4 sliders WSJF (Business Value, Time Criticality, Risk Reduction, Job Duration) afin de prioriser le backlog.",
        "acceptance_criteria": "Given: fiche feature / When: sliders [1-10] ajustés / Then: score WSJF = (BV+TC+RR)/JD recalculé instantanément.",
        "story_points": 3,
        "priority": 10,
    },
    {
        "id": "sf-us-015",
        "feature_id": "sf-f-web-05",
        "title": "En tant que PO, je veux assigner une user story à un sprint afin d'organiser le PI planning.",
        "acceptance_criteria": "Given: user story backlog / When: sprint assigné / Then: story apparaît dans le bon sprint du PI Board, WSJF recalculé.",
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-016",
        "feature_id": "sf-f-web-05",
        "title": "En tant que Tech Lead, je veux voir la traceabilité des fichiers modifiés par user story afin de valider la couverture des critères d'acceptance.",
        "acceptance_criteria": "Given: user story / When: onglet Traceabilité / Then: liste des fichiers avec diff et référence au run qui les a modifiés.",
        "story_points": 5,
        "priority": 7,
    },
    # F-WEB-06: Idéation
    {
        "id": "sf-us-017",
        "feature_id": "sf-f-web-06",
        "title": "En tant que PO, je veux lancer une session d'idéation multi-agents sur un thème afin de générer des features candidats en < 5 minutes.",
        "acceptance_criteria": "Given: page Idéation / When: thème saisi et session lancée / Then: 3+ agents répondent en streaming, findings sauvegardés automatiquement.",
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-018",
        "feature_id": "sf-f-web-06",
        "title": "En tant que CMO, je veux générer des personas utilisateurs et des user journeys depuis un brief produit afin d'alimenter le backlog.",
        "acceptance_criteria": "Given: brief produit / When: agent Customer Insights activé / Then: 3+ personas avec goals/pain points et 2+ journeys générés.",
        "story_points": 3,
        "priority": 6,
    },
    # F-WEB-07: Mémoire
    {
        "id": "sf-us-019",
        "feature_id": "sf-f-web-07",
        "title": "En tant qu'analyste, je veux faire une recherche sémantique dans toute la mémoire projet afin de retrouver des insights d'anciennes sessions.",
        "acceptance_criteria": "Given: barre recherche mémoire / When: requête saisie / Then: résultats FTS5 + semantic ranking en < 1s, snippet affiché.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-020",
        "feature_id": "sf-f-web-07",
        "title": "En tant qu'agent (via RLM), je veux stocker un insight en mémoire projet afin qu'il soit disponible dans les sessions futures.",
        "acceptance_criteria": "Given: tool memory_store appelé / When: insight sauvegardé / Then: disponible dans memory_search dès la prochaine session.",
        "story_points": 2,
        "priority": 8,
    },
    # F-WEB-08: TMA
    {
        "id": "sf-us-021",
        "feature_id": "sf-f-web-08",
        "title": "En tant que SRE, je veux créer un incident avec priorité P0-P4 et l'assigner à une équipe afin de déclencher le processus TMA.",
        "acceptance_criteria": "Given: dashboard TMA / When: + Incident rempli / Then: incident créé, SLA calculé, équipe notifiée.",
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-022",
        "feature_id": "sf-f-web-08",
        "title": "En tant que SRE, je veux consulter le wiki des runbooks afin de suivre la procédure d'un incident connu.",
        "acceptance_criteria": "Given: incident actif / When: lien wiki cliqué / Then: page wiki correspondante ouverte, tags incidents visibles.",
        "story_points": 2,
        "priority": 7,
    },
    # F-WEB-09: Analytics
    {
        "id": "sf-us-023",
        "feature_id": "sf-f-web-09",
        "title": "En tant qu'admin, je veux voir les KPIs globaux (agents actifs, sessions, missions, tâches) en temps réel sur le cockpit afin de surveiller l'activité.",
        "acceptance_criteria": "Given: page Cockpit / When: chargement / Then: KPIs rafraîchis toutes les 30s via polling HTMX, sans reload.",
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-024",
        "feature_id": "sf-f-web-09",
        "title": "En tant que Tech Lead, je veux exporter le leaderboard WSJF en CSV afin de le partager avec le management.",
        "acceptance_criteria": "Given: vue Analytics / When: Export CSV / Then: fichier CSV avec colonnes feature, score_wsjf, status, assignee téléchargé.",
        "story_points": 2,
        "priority": 5,
    },
    # F-WEB-10: Notifications
    {
        "id": "sf-us-025",
        "feature_id": "sf-f-web-10",
        "title": "En tant qu'admin, je veux recevoir une notification dans l'interface quand une mission se termine afin d'être informé sans surveiller l'écran.",
        "acceptance_criteria": "Given: mission en cours / When: mission completed / Then: notification SSE reçue en < 2s, badge incrémenté.",
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-026",
        "feature_id": "sf-f-web-10",
        "title": "En tant qu'admin, je veux configurer mes préférences de notification (par type d'événement) afin de ne recevoir que ce qui m'intéresse.",
        "acceptance_criteria": "Given: Settings notifications / When: toggle désactivé pour 'task.created' / Then: ce type d'événement ne génère plus de notification.",
        "story_points": 2,
        "priority": 4,
    },
    # F-MAC-01: Onboarding macOS
    {
        "id": "sf-us-027",
        "feature_id": "sf-f-mac-01",
        "title": "En tant qu'admin macOS, je veux configurer MLX/Qwen et Ollama lors du premier lancement afin de démarrer sans connexion réseau.",
        "acceptance_criteria": "Given: premier lancement / When: étape LLMs / Then: 2 sections (MLX + Ollama) avec champ endpoint et bouton Détecter.",
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-028",
        "feature_id": "sf-f-mac-01",
        "title": "En tant qu'admin macOS, je veux que l'app détecte automatiquement les modèles Ollama disponibles via ping afin d'éviter la saisie manuelle.",
        "acceptance_criteria": "Given: endpoint Ollama configuré / When: bouton Détecter / Then: ping /api/tags, liste des modèles affichée dans un Picker en < 5s.",
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-029",
        "feature_id": "sf-f-mac-01",
        "title": "En tant qu'admin macOS, je veux que la config LLM soit sauvegardée et rechargée après redémarrage de l'app.",
        "acceptance_criteria": "Given: config sauvegardée / When: redémarrage / Then: endpoints et modèles sélectionnés retrouvés, pas de re-onboarding.",
        "story_points": 2,
        "priority": 9,
    },
    # F-MAC-02: SF Inside
    {
        "id": "sf-us-030",
        "feature_id": "sf-f-mac-02",
        "title": "En tant qu'utilisateur offline, je veux lancer une session SF Inside sans réseau afin de travailler en train ou en avion.",
        "acceptance_criteria": "Given: aucune connexion réseau / When: session SF Inside créée / Then: session démarre, LLM local (MLX/Ollama) répond en streaming.",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-us-031",
        "feature_id": "sf-f-mac-02",
        "title": "En tant qu'admin macOS, je veux que SF Inside soit toujours présent dans la liste des instances et ne puisse pas être supprimé.",
        "acceptance_criteria": "Given: liste instances / When: tentative de suppression de SF Inside / Then: action bloquée, SF Inside reste en tête de liste.",
        "story_points": 2,
        "priority": 10,
    },
    # F-MAC-03: Multi-instances
    {
        "id": "sf-us-032",
        "feature_id": "sf-f-mac-03",
        "title": "En tant qu'admin macOS, je veux switcher en 1 clic entre SF Inside, SF OVH et SF AZ afin de piloter l'environnement approprié.",
        "acceptance_criteria": "Given: sidebar instances / When: clic sur une instance / Then: switch < 500ms, statut online/offline actualisé, contenu rechargé.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-033",
        "feature_id": "sf-f-mac-03",
        "title": "En tant qu'admin macOS, je veux voir le statut (online/offline) de chaque nœud HA afin de détecter une panne immédiatement.",
        "acceptance_criteria": "Given: instances OVH 2-nœuds / When: nœud-2 offline / Then: badge rouge sur nœud-2, badge orange sur l'instance parente.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-034",
        "feature_id": "sf-f-mac-03",
        "title": "En tant qu'admin macOS, je veux ajouter une instance SF distante avec un token OAuth stocké dans le Keychain afin de sécuriser les accès.",
        "acceptance_criteria": "Given: formulaire ajout instance / When: URL + token saisis / Then: token stocké dans macOS Keychain, ping de validation < 3s.",
        "story_points": 3,
        "priority": 7,
    },
    # F-MAC-04: Org SAFe native
    {
        "id": "sf-us-035",
        "feature_id": "sf-f-mac-04",
        "title": "En tant que Tech Lead macOS, je veux naviguer Portfolio > ART > Team > Agent en NavigationSplitView afin d'avoir une vue tri-colonne native.",
        "acceptance_criteria": "Given: onglet Org / When: ART sélectionné / Then: teams affichées en colonne 2, agents en colonne 3 — navigation sans rechargement.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-036",
        "feature_id": "sf-f-mac-04",
        "title": "En tant que PO macOS, je veux voir le badge WIP d'une team passer au rouge quand la limite est dépassée afin d'agir immédiatement.",
        "acceptance_criteria": "Given: team avec WIP limit 3 / When: 4ème tâche assignée / Then: badge WIP rouge et compteur mis à jour en temps réel.",
        "story_points": 2,
        "priority": 7,
    },
    # F-MAC-05: Sessions natif
    {
        "id": "sf-us-037",
        "feature_id": "sf-f-mac-05",
        "title": "En tant qu'utilisateur macOS, je veux que les réponses de l'agent s'affichent token-par-token en streaming afin de voir la progression en temps réel.",
        "acceptance_criteria": "Given: message envoyé / When: LLM répond / Then: texte affiché progressivement, TTFB < 1s, indicateur de frappe visible.",
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-038",
        "feature_id": "sf-f-mac-05",
        "title": "En tant que Tech Lead macOS, je veux voir les tool calls de l'agent inline dans la conversation afin de comprendre son raisonnement.",
        "acceptance_criteria": "Given: agent exécute un tool / When: tool_call reçu / Then: carte outil affichée avec nom, paramètres et résultat tronqué.",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-039",
        "feature_id": "sf-f-mac-05",
        "title": "En tant qu'utilisateur macOS, je veux copier un message de l'agent au format Markdown afin de le coller dans un PR ou un wiki.",
        "acceptance_criteria": "Given: message reçu / When: clic Copier / Then: contenu Markdown dans le presse-papier, notification macOS confirmant la copie.",
        "story_points": 1,
        "priority": 6,
    },
    # F-MAC-06: Backlog natif
    {
        "id": "sf-us-040",
        "feature_id": "sf-f-mac-06",
        "title": "En tant que PO macOS, je veux créer une feature avec les sliders WSJF depuis l'app native afin d'éviter l'interface web.",
        "acceptance_criteria": "Given: onglet Backlog / When: + Feature / Then: formulaire SwiftUI avec 4 sliders, score WSJF affiché en direct.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-041",
        "feature_id": "sf-f-mac-06",
        "title": "En tant que PO macOS, je veux voir le PI Board avec les stories organisées par sprint afin de planifier l'itération courante.",
        "acceptance_criteria": "Given: vue PI Board / When: sprint courant sélectionné / Then: stories affichées en colonnes (backlog/in_progress/done) par sprint.",
        "story_points": 5,
        "priority": 7,
    },
    # F-MAC-07: Mercato & Darwin
    {
        "id": "sf-us-042",
        "feature_id": "sf-f-mac-07",
        "title": "En tant qu'admin macOS, je veux visualiser les scores Thompson Sampling de chaque équipe Darwin afin d'identifier les teams les plus efficaces.",
        "acceptance_criteria": "Given: onglet Évolution / When: team sélectionnée / Then: graphique Beta(α,β) sur 30 runs, comparaison inter-teams.",
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-043",
        "feature_id": "sf-f-mac-07",
        "title": "En tant que PO macOS, je veux consulter le catalogue Mercato et filtrer par skill afin de trouver l'agent adapté à ma mission.",
        "acceptance_criteria": "Given: onglet Mercato / When: filtre skill saisi / Then: liste filtrée en < 500ms, score Thompson visible sur chaque carte.",
        "story_points": 3,
        "priority": 5,
    },
    # F-MAC-08: Analytics macOS
    {
        "id": "sf-us-044",
        "feature_id": "sf-f-mac-08",
        "title": "En tant qu'admin macOS, je veux voir le cockpit KPI sur l'instance active afin de surveiller la plateforme sans ouvrir un navigateur.",
        "acceptance_criteria": "Given: onglet Cockpit / When: instance active / Then: KPIs chargés en < 1s, charts SwiftUI animés, rafraîchissement toutes les 30s.",
        "story_points": 5,
        "priority": 7,
    },
    # F-MAC-09: Settings
    {
        "id": "sf-us-045",
        "feature_id": "sf-f-mac-09",
        "title": "En tant qu'admin macOS, je veux modifier l'endpoint et le modèle Ollama depuis Settings sans relancer l'onboarding.",
        "acceptance_criteria": "Given: Settings > LLMs > Ollama / When: endpoint modifié / Then: nouveau ping déclenché, modèles re-détectés, config sauvegardée.",
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-046",
        "feature_id": "sf-f-mac-09",
        "title": "En tant qu'admin macOS, je veux importer/exporter la configuration complète (LLMs + instances) en JSON afin de la partager avec un collègue.",
        "acceptance_criteria": "Given: Settings > Export / When: clic Export / Then: fichier JSON généré avec tous les champs (sauf tokens Keychain). Import valide le format.",
        "story_points": 2,
        "priority": 5,
    },
    # F-MAC-10: Notifications macOS
    {
        "id": "sf-us-047",
        "feature_id": "sf-f-mac-10",
        "title": "En tant qu'admin macOS, je veux recevoir une notification native quand un incident P0 est créé afin de réagir immédiatement.",
        "acceptance_criteria": "Given: SF Inside ou instance distante active / When: incident P0 créé / Then: notification macOS en < 5s, clic ouvre le TMA.",
        "story_points": 3,
        "priority": 5,
    },
    # F-AGT-01: Patterns
    {
        "id": "sf-us-048",
        "feature_id": "sf-f-agt-01",
        "title": "En tant que Tech Lead, je veux sélectionner le pattern Debate pour une mission afin de faire débattre deux agents sur la meilleure approche.",
        "acceptance_criteria": "Given: création mission / When: pattern=Debate / Then: 2 agents pro/con structurés, arbitre final, output mémorisé.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-049",
        "feature_id": "sf-f-agt-01",
        "title": "En tant qu'admin, je veux voir le graphe d'exécution d'un pattern en temps réel (nodes colorés) afin de suivre la progression.",
        "acceptance_criteria": "Given: mission avec pattern Parallel / When: en cours / Then: graphe SVG avec nodes verts (done)/oranges (running)/gris (pending).",
        "story_points": 5,
        "priority": 8,
    },
    # F-AGT-02: Mercato
    {
        "id": "sf-us-050",
        "feature_id": "sf-f-agt-02",
        "title": "En tant que Platform Lead, je veux publier un agent dans le Mercato avec sa fiche (skills, score, ART) afin de le rendre disponible à tous.",
        "acceptance_criteria": "Given: fiche agent / When: Publier dans Mercato / Then: agent visible dans le catalogue avec statut 'published' et timestamp.",
        "story_points": 3,
        "priority": 7,
    },
    # F-AGT-03: Thompson Sampling
    {
        "id": "sf-us-051",
        "feature_id": "sf-f-agt-03",
        "title": "En tant qu'admin, je veux que le système sélectionne automatiquement le meilleur agent par type de mission via Thompson Sampling afin d'optimiser la qualité.",
        "acceptance_criteria": "Given: mission type=feature / When: run / Then: agent avec Beta(α,β) le plus élevé sélectionné, α++ si succès, β++ si échec.",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-us-052",
        "feature_id": "sf-f-agt-03",
        "title": "En tant que Tech Lead, je veux voir l'évolution du score de confiance de chaque agent sur les 30 derniers runs afin de détecter la régression.",
        "acceptance_criteria": "Given: fiche agent / When: onglet Évolution / Then: graphique temporal Beta(α,β) avec marqueurs succès/échec.",
        "story_points": 3,
        "priority": 6,
    },
    # F-AGT-04: Skills
    {
        "id": "sf-us-053",
        "feature_id": "sf-f-agt-04",
        "title": "En tant qu'admin, je veux importer des skills depuis un repo GitHub afin d'enrichir le catalogue sans saisie manuelle.",
        "acceptance_criteria": "Given: Settings > Skills > Import GitHub / When: URL repo saisie / Then: skills importés, doublons ignorés (idempotent).",
        "story_points": 5,
        "priority": 7,
    },
    # F-AGT-05: MCP
    {
        "id": "sf-us-054",
        "feature_id": "sf-f-agt-05",
        "title": "En tant qu'admin, je veux configurer un MCP server custom pour un agent afin d'étendre ses capacités avec des outils propriétaires.",
        "acceptance_criteria": "Given: fiche agent / When: + MCP server saisi / Then: agent utilise les tools MCP dans ses sessions, logs disponibles.",
        "story_points": 5,
        "priority": 7,
    },
    # F-AGT-06: Workflows
    {
        "id": "sf-us-055",
        "feature_id": "sf-f-agt-06",
        "title": "En tant que Tech Lead, je veux créer un workflow avec 5 nœuds (agents + pattern) et le lancer afin d'automatiser un pipeline de traitement.",
        "acceptance_criteria": "Given: éditeur workflow / When: 5 nodes définis et lancé / Then: 5 sessions créées, graphe de statut mis à jour en temps réel.",
        "story_points": 8,
        "priority": 7,
    },
    # F-TMA-01: Incidents
    {
        "id": "sf-us-056",
        "feature_id": "sf-f-tma-01",
        "title": "En tant que SRE, je veux que le watchdog détecte automatiquement les missions bloquées depuis > 60s et crée un incident P2 afin d'éviter le monitoring manuel.",
        "acceptance_criteria": "Given: mission bloquée 60s / When: watchdog tick / Then: incident P2 créé automatiquement avec lien vers la mission et reason.",
        "story_points": 5,
        "priority": 9,
    },
    # F-TMA-02: Fix TDD
    {
        "id": "sf-us-057",
        "feature_id": "sf-f-tma-02",
        "title": "En tant que dev TMA, je veux lancer le pattern Fix TDD (red → green → refactor) sur un incident afin d'appliquer un fix minimal TDD.",
        "acceptance_criteria": "Given: incident assigné / When: pattern Fix TDD lancé / Then: 3 phases (red/green/refactor), adversarial guard actif, diff affiché.",
        "story_points": 8,
        "priority": 9,
    },
    # F-TMA-03: Hotfix Deploy
    {
        "id": "sf-us-058",
        "feature_id": "sf-f-tma-03",
        "title": "En tant que SRE, je veux déclencher un hotfix deploy sur OVH HA (nœud-1 + nœud-2) avec drain graceful afin d'éviter toute interruption de service.",
        "acceptance_criteria": "Given: hotfix validé / When: Deploy Hotfix / Then: drain nœud-1, déploiement, health check ok, puis nœud-2 — total < 5 min.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-059",
        "feature_id": "sf-f-tma-03",
        "title": "En tant que SRE, je veux un rollback automatique si le health check /api/ready retourne 503 après déploiement afin de limiter le blast radius.",
        "acceptance_criteria": "Given: deploy en cours / When: /api/ready retourne 503 pendant 60s / Then: rollback automatique, alerte créée, nœud-2 inchangé.",
        "story_points": 5,
        "priority": 8,
    },
    # F-TMA-04: Postmortem
    {
        "id": "sf-us-060",
        "feature_id": "sf-f-tma-04",
        "title": "En tant que SRE, je veux créer une page wiki de postmortem pré-remplie depuis l'incident afin de capitaliser sur l'événement.",
        "acceptance_criteria": "Given: incident clôturé / When: Créer Postmortem / Then: page wiki créée avec template (chronologie, cause racine, actions), lien dans l'incident.",
        "story_points": 3,
        "priority": 7,
    },
    # F-SEC-01: RBAC
    {
        "id": "sf-us-061",
        "feature_id": "sf-f-sec-01",
        "title": "En tant qu'admin, je veux définir un rôle 'viewer' sur un projet afin qu'un utilisateur externe puisse consulter sans modifier.",
        "acceptance_criteria": "Given: projet / When: rôle viewer assigné / Then: endpoints mutation retournent 403, lecture autorisée — testé par les tests RBAC.",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-062",
        "feature_id": "sf-f-sec-01",
        "title": "En tant que Tech Lead, je veux que chaque action de permission soit tracée dans l'audit log afin de prouver la conformité.",
        "acceptance_criteria": "Given: action RBAC / When: permission check / Then: entrée audit_log avec user, action, resource, résultat (allowed/denied), timestamp.",
        "story_points": 3,
        "priority": 8,
    },
    # F-SEC-02: Audit & secrets
    {
        "id": "sf-us-063",
        "feature_id": "sf-f-sec-02",
        "title": "En tant que RSSI, je veux lancer un scan TruffleHog sur tout le codebase SF depuis l'interface afin de détecter les secrets exposés.",
        "acceptance_criteria": "Given: page Sécurité / When: Lancer Scan / Then: résultat TruffleHog affiché (fichier, ligne, type secret), alerte si findings.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-064",
        "feature_id": "sf-f-sec-02",
        "title": "En tant qu'admin, je veux que les secrets soient synchronisés depuis Infisical au démarrage afin d'éviter les .env en clair sur les serveurs.",
        "acceptance_criteria": "Given: INFISICAL_TOKEN configuré / When: démarrage / Then: secrets chargés en < 3s, fallback .env si Infisical KO, log d'avertissement.",
        "story_points": 3,
        "priority": 7,
    },
]

# ── Personas schema (table DDL) ───────────────────────────────────────────────

PERSONAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS personas (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    goals TEXT DEFAULT '',
    pain_points TEXT DEFAULT '',
    technical_level TEXT DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_personas_project ON personas(project_id);
"""

# ═══════════════════════════════════════════════════════════════════════════════
# V2 — Nouvelles données : Auth & Accès · Intégrations & DevOps · Observabilité
# ═══════════════════════════════════════════════════════════════════════════════

# ── Epics V2 ──────────────────────────────────────────────────────────────────

SF_EPICS_V2: list[dict] = [
    {
        "id": "sf-epic-v2-auth",
        "project_id": "software-factory",
        "name": "Auth & Accès",
        "description": (
            "Authentification OAuth2 / JWT, gestion des utilisateurs et des rôles RBAC, "
            "clés API par projet/agent, push notifications PWA. "
            "Couvre les routes /auth/*, /api/users, /api/api-keys, /api/push."
        ),
        "type": "feature",
        "status": "planning",
        "wsjf_score": 8.5,
    },
    {
        "id": "sf-epic-v2-devops",
        "project_id": "software-factory",
        "name": "Intégrations & DevOps",
        "description": (
            "Cibles de déploiement multi-cloud (OVH/Azure/custom), webhooks entrants/sortants, "
            "CLI SF (sf run/status/deploy), DAG de dépendances, protocol A2A inter-agents, "
            "gestion multi-providers LLM avec suivi des coûts, constructeur d'outils custom, "
            "hooks lifecycle pre/post-mission."
        ),
        "type": "feature",
        "status": "planning",
        "wsjf_score": 7.8,
    },
    {
        "id": "sf-epic-v2-obs",
        "project_id": "software-factory",
        "name": "Observabilité & Qualite",
        "description": (
            "DORA metrics, évaluations LLM et skills, recherche globale FTS5, journal d'événements, "
            "wiki projet, vue CTO / portfolio, gestion des sprints et vélocité, "
            "instincts agents et modules extensions."
        ),
        "type": "feature",
        "status": "planning",
        "wsjf_score": 7.2,
    },
]

# ── Features V2 ───────────────────────────────────────────────────────────────

SF_FEATURES_V2: list[dict] = [
    # ── Epic: Auth & Accès ──────────────────────────────────────────────────
    {
        "id": "sf-f-v2-auth-01",
        "epic_id": "sf-epic-v2-auth",
        "name": "Authentification OAuth2 et JWT",
        "description": (
            "Connexion via OAuth2 (GitHub, Google, Azure AD) et formulaire classique. "
            "Emission de JWT à durée configurable. Refresh token silencieux. "
            "Logout avec révocation du token côté serveur. "
            "Routes : /auth/login, /auth/logout, /auth/oauth/callback."
        ),
        "acceptance_criteria": (
            "Un utilisateur peut se connecter via OAuth GitHub en < 5s. "
            "Le JWT expire selon la durée configurée. "
            "Après logout, le token est invalidé et toute requête retourne 401."
        ),
        "priority": 10,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-auth-02",
        "epic_id": "sf-epic-v2-auth",
        "name": "Gestion des cles API par projet et agent",
        "description": (
            "CRUD de clés API scoped (lecture/écriture/admin) par projet ou par agent. "
            "Rotation automatique avec TTL configurable. Révocation immédiate. "
            "Audit log de chaque utilisation. "
            "Routes : /api/api-keys."
        ),
        "acceptance_criteria": (
            "Une clé API générée permet d'appeler /api/* avec le scope accordé. "
            "Après révocation, la clé retourne 403 immédiatement. "
            "Le journal d'audit affiche chaque appel avec timestamp et IP."
        ),
        "priority": 9,
        "story_points": 5,
    },
    {
        "id": "sf-f-v2-auth-03",
        "epic_id": "sf-epic-v2-auth",
        "name": "RBAC et gestion des utilisateurs",
        "description": (
            "Rôles admin/lead/member/viewer par projet. "
            "Invitation par e-mail avec lien temporaire. "
            "Tableau de bord des utilisateurs actifs, suspension, suppression. "
            "Routes : /api/users."
        ),
        "acceptance_criteria": (
            "Un membre ne peut pas accéder aux pages admin. "
            "L'invitation expire après 48h si non acceptée. "
            "La suspension coupe l'accès en < 1s sans déconnexion des autres utilisateurs."
        ),
        "priority": 9,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-auth-04",
        "epic_id": "sf-epic-v2-auth",
        "name": "Push notifications PWA et mobile",
        "description": (
            "Abonnement Web Push (VAPID) pour les navigateurs modernes. "
            "Notifications temps réel : fin de mission, incident P0, alerte sécurité. "
            "Centre de gestion des abonnements. "
            "Routes : /api/push."
        ),
        "acceptance_criteria": (
            "Un navigateur abonné reçoit la notification < 3s après l'événement. "
            "L'utilisateur peut se désabonner depuis les préférences. "
            "Les notifications respectent le paramètre silencieux du navigateur."
        ),
        "priority": 6,
        "story_points": 5,
    },
    # ── Epic: Intégrations & DevOps ─────────────────────────────────────────
    {
        "id": "sf-f-v2-dev-01",
        "epic_id": "sf-epic-v2-devops",
        "name": "Cibles de deploiement multi-cloud",
        "description": (
            "CRUD des cibles de déploiement : OVH (SSH + systemd), Azure VM (rsync + docker), "
            "endpoint custom (webhook HTTP). "
            "Test de connectivité, statut en temps réel, logs de déploiement. "
            "Routes : /api/deploy-targets."
        ),
        "acceptance_criteria": (
            "L'admin peut ajouter une cible OVH et tester la connexion SSH en < 10s. "
            "Un déploiement échoué affiche les logs d'erreur dans l'interface. "
            "Les cibles sont filtrables par type (OVH/Azure/custom)."
        ),
        "priority": 9,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-dev-02",
        "epic_id": "sf-epic-v2-devops",
        "name": "Webhooks entrants et sortants",
        "description": (
            "Réception de webhooks GitHub/GitLab (push, PR, issue) pour déclencher des missions. "
            "Émission de webhooks sortants (fin de mission, alerte). "
            "Signature HMAC-SHA256. Rejouer un webhook. "
            "Routes : /api/webhooks."
        ),
        "acceptance_criteria": (
            "Un push GitHub déclenche la mission associée en < 5s. "
            "Un webhook avec signature invalide retourne 401. "
            "Le rejouer relivrance l'événement avec les mêmes paramètres."
        ),
        "priority": 8,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-dev-03",
        "epic_id": "sf-epic-v2-devops",
        "name": "CLI SF — sf run / status / deploy",
        "description": (
            "Interface en ligne de commande : sf run <mission>, sf status, sf deploy <target>. "
            "Authentification par clé API. Sortie colorée. Mode --json pour scripts CI. "
            "Routes : /api/sf-commands."
        ),
        "acceptance_criteria": (
            "sf run <id> démarre la mission et stream les logs dans le terminal. "
            "sf status retourne JSON valide avec --json. "
            "sf deploy échoue avec code 1 si la cible est injoignable."
        ),
        "priority": 7,
        "story_points": 5,
    },
    {
        "id": "sf-f-v2-dev-04",
        "epic_id": "sf-epic-v2-devops",
        "name": "DAG de dependances entre missions",
        "description": (
            "Définition de dépendances entre missions (bloquante/informative). "
            "Visualisation graphe acyclique orienté. "
            "Détection de cycle. Blocage automatique si mission amont non terminée. "
            "Routes : /dag."
        ),
        "acceptance_criteria": (
            "Un cycle détecté bloque la sauvegarde et affiche l'erreur. "
            "Une mission bloquée passe en état 'waiting' jusqu'à résolution de la dépendance. "
            "Le graphe DAG s'affiche en < 2s pour 50 missions."
        ),
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-dev-05",
        "epic_id": "sf-epic-v2-devops",
        "name": "Protocol A2A inter-agents",
        "description": (
            "Bus de messages inter-agents : veto, debate, delegate, escalate. "
            "Hiérarchie de veto configurable par ART. "
            "Journal des messages A2A. Replay d'un message. "
            "Routes : /a2a."
        ),
        "acceptance_criteria": (
            "Un agent peut poser un veto sur une décision dans < 500ms. "
            "Le journal A2A affiche expéditeur, destinataire, type, timestamp. "
            "Le replay remet le message dans la file sans dupliquer l'état."
        ),
        "priority": 8,
        "story_points": 13,
    },
    {
        "id": "sf-f-v2-dev-06",
        "epic_id": "sf-epic-v2-devops",
        "name": "Gestion multi-providers LLM et suivi des couts",
        "description": (
            "Configuration de tous les providers (Azure OpenAI, OpenAI, MiniMax, Ollama, MLX). "
            "Test de latence et de disponibilité. "
            "Tableau de bord des coûts par provider/projet/mois. "
            "Routes : /api/llm."
        ),
        "acceptance_criteria": (
            "Un provider désactivé est exclu du fallback chain en temps réel. "
            "Le tableau des coûts affiche tokens_in, tokens_out, coût USD avec filtre mois. "
            "Le ping de disponibilité s'exécute toutes les 60s et met à jour le badge."
        ),
        "priority": 9,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-dev-07",
        "epic_id": "sf-epic-v2-devops",
        "name": "Constructeur d'outils custom pour agents",
        "description": (
            "Éditeur visuel de tools OpenAI (JSON Schema + code Python). "
            "Test unitaire intégré. Assignation d'un outil à un ou plusieurs agents. "
            "Versioning des outils. "
            "Routes : /tool-builder."
        ),
        "acceptance_criteria": (
            "Un outil créé est disponible dans la liste des tools d'un agent en < 5s. "
            "Le test unitaire affiche stdout/stderr dans l'éditeur. "
            "La suppression d'un outil désassigné est irréversible avec confirmation."
        ),
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-dev-08",
        "epic_id": "sf-epic-v2-devops",
        "name": "Hooks lifecycle pre/post mission et sprint",
        "description": (
            "Configuration de hooks Python/HTTP déclenchés avant/après mission et sprint. "
            "Paramètres injectés : mission_id, project_id, phase, status. "
            "Timeout configurable. Log d'exécution. "
            "Routes : /api/hooks."
        ),
        "acceptance_criteria": (
            "Un hook pre-mission peut annuler le démarrage en retournant {cancel: true}. "
            "L'exécution du hook est loggée avec durée et code de retour. "
            "Un hook en timeout est tué et l'événement loggé comme warning."
        ),
        "priority": 6,
        "story_points": 5,
    },
    # ── Epic: Observabilité & Qualité ───────────────────────────────────────
    {
        "id": "sf-f-v2-obs-01",
        "epic_id": "sf-epic-v2-obs",
        "name": "DORA Metrics et Analytics DevOps",
        "description": (
            "Calcul et affichage des 4 métriques DORA : fréquence de déploiement, "
            "lead time for changes, MTTR, change failure rate. "
            "Graphiques par période. Benchmark Elite/High/Medium/Low. "
            "Routes : /analytics, /api/analytics."
        ),
        "acceptance_criteria": (
            "Les métriques DORA sont recalculées à chaque nouveau déploiement. "
            "Un badge Elite/High/Medium/Low s'affiche selon le benchmark DORA 2023. "
            "L'export CSV des métriques contient toutes les colonnes attendues."
        ),
        "priority": 8,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-obs-02",
        "epic_id": "sf-epic-v2-obs",
        "name": "Evaluations LLM et skill eval",
        "description": (
            "Benchmarks automatiques sur des jeux de données de référence. "
            "Score de qualité (précision, cohérence, hallucination rate). "
            "Comparaison inter-agents et inter-providers. "
            "Routes : /evals, /api/skill-eval."
        ),
        "acceptance_criteria": (
            "Un benchmark produit un score entre 0 et 100 avec breakdown par critère. "
            "Le comparatif inter-agents affiche un tableau côte à côte. "
            "Les résultats sont persistés et consultables dans l'historique."
        ),
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-obs-03",
        "epic_id": "sf-epic-v2-obs",
        "name": "Recherche globale FTS5 cross-entites",
        "description": (
            "Recherche plein texte sur agents, missions, stories, sessions, wiki, mémoire. "
            "Résultats groupés par type. Highlighting des termes. Raccourci clavier Cmd+K. "
            "Routes : /api/search."
        ),
        "acceptance_criteria": (
            "La recherche retourne des résultats en < 200ms pour un corpus de 10 000 entrées. "
            "Les termes cherchés sont mis en surbrillance dans les extraits. "
            "Le raccourci Cmd+K ouvre la palette de recherche depuis n'importe quelle page."
        ),
        "priority": 8,
        "story_points": 5,
    },
    {
        "id": "sf-f-v2-obs-04",
        "epic_id": "sf-epic-v2-obs",
        "name": "Journal d'evenements global et hooks",
        "description": (
            "Flux temps réel de tous les événements système (mission, sprint, agent, sécurité). "
            "Filtres par type, sévérité, projet, période. "
            "Webhook sortant configurable sur sous-ensemble d'événements. "
            "Routes : /api/events."
        ),
        "acceptance_criteria": (
            "Un événement apparaît dans le journal < 1s après sa production. "
            "Le filtre par sévérité ERROR n'affiche que les événements d'erreur. "
            "Le webhook sortant reçoit le payload JSON < 3s après l'événement."
        ),
        "priority": 7,
        "story_points": 5,
    },
    {
        "id": "sf-f-v2-obs-05",
        "epic_id": "sf-epic-v2-obs",
        "name": "Wiki projet et gestion des connaissances",
        "description": (
            "Wiki Markdown par projet : pages hiérarchiques, tags, recherche FTS. "
            "Historique des modifications. Import/export Markdown. "
            "Guidelines et conventions (knowledge base) consommées par les agents. "
            "Routes : /wiki, /api/knowledge."
        ),
        "acceptance_criteria": (
            "Une page wiki est créée, éditée et versionnée. "
            "La recherche FTS dans le wiki retourne des résultats en < 300ms. "
            "Les guidelines d'un projet sont injectées dans le prompt système de l'agent."
        ),
        "priority": 7,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-obs-06",
        "epic_id": "sf-epic-v2-obs",
        "name": "Vue CTO et portfolio roadmap",
        "description": (
            "Tableau de bord CTO : santé du portfolio, vélocité ART, budget LLM, DORA. "
            "Timeline roadmap des épics par trimestre. "
            "Alertes de dérive (missions en retard, budget dépassé). "
            "Routes : /cto."
        ),
        "acceptance_criteria": (
            "Le CTO voit l'état de tous les projets en une page sans navigation. "
            "La timeline roadmap affiche les épics glissant sur 4 trimestres. "
            "Une alerte rouge apparaît si une mission dépasse son délai estimé de > 20%."
        ),
        "priority": 8,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-obs-07",
        "epic_id": "sf-epic-v2-obs",
        "name": "Gestion des sprints et velocite ART",
        "description": (
            "CRUD sprints avec dates, capacité, vélocité planifiée vs réelle. "
            "Burndown chart. Déplacement de stories entre sprints (drag-drop). "
            "Calcul automatique de la vélocité moyenne sur N sprints. "
            "Routes : /epics/sprints."
        ),
        "acceptance_criteria": (
            "Le burndown chart se met à jour en temps réel quand une story passe Done. "
            "La vélocité moyenne est recalculée automatiquement sur les 3 derniers sprints. "
            "Un sprint clos ne peut plus recevoir de nouvelles stories."
        ),
        "priority": 8,
        "story_points": 8,
    },
    {
        "id": "sf-f-v2-obs-08",
        "epic_id": "sf-epic-v2-obs",
        "name": "Instincts agents et modules extensions",
        "description": (
            "Configuration d'instincts comportementaux par agent (heuristiques pré-LLM). "
            "Activation/désactivation de modules additionnels (extensions). "
            "Marketplace interne pour partager instincts et modules entre projets. "
            "Routes : /api/instincts, /api/modules."
        ),
        "acceptance_criteria": (
            "Un instinct activé modifie le comportement de l'agent sans redémarrage. "
            "Un module désactivé n'est pas chargé au démarrage (lazy load). "
            "Le marketplace affiche la note et le nombre d'installations de chaque extension."
        ),
        "priority": 6,
        "story_points": 8,
    },
]

# ── User Stories V2 ───────────────────────────────────────────────────────────

SF_STORIES_V2: list[dict] = [
    # ── sf-f-v2-auth-01 : Authentification OAuth2 et JWT ───────────────────
    {
        "id": "sf-us-v2-001",
        "feature_id": "sf-f-v2-auth-01",
        "title": (
            "En tant qu'admin, je veux me connecter via OAuth GitHub "
            "afin d'eviter de gerer un mot de passe supplementaire."
        ),
        "acceptance_criteria": (
            "Given: page de login / "
            "When: clic sur 'Connexion GitHub' / "
            "Then: redirection OAuth, token JWT emis, session active en < 5s."
        ),
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-v2-002",
        "feature_id": "sf-f-v2-auth-01",
        "title": (
            "En tant qu'admin, je veux que le JWT soit renouvelé silencieusement "
            "afin de ne pas etre deconnecte pendant une session longue."
        ),
        "acceptance_criteria": (
            "Given: JWT expirant dans 60s / "
            "When: requete API detecte le refresh window / "
            "Then: nouveau JWT emis, ancienne session preservee, sans rechargement de page."
        ),
        "story_points": 3,
        "priority": 9,
    },
    # ── sf-f-v2-auth-02 : Gestion des cles API ─────────────────────────────
    {
        "id": "sf-us-v2-003",
        "feature_id": "sf-f-v2-auth-02",
        "title": (
            "En tant que Tech Lead, je veux generer une cle API en lecture seule "
            "pour un agent CI afin d'interroger le statut des missions sans risque."
        ),
        "acceptance_criteria": (
            "Given: page API Keys d'un projet / "
            "When: creation avec scope=read / "
            "Then: cle generee, copiable une seule fois, scope affiche dans la liste."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v2-004",
        "feature_id": "sf-f-v2-auth-02",
        "title": (
            "En tant qu'admin, je veux revoquer immediatement une cle API compromise "
            "afin de stopper tout acces non autorise."
        ),
        "acceptance_criteria": (
            "Given: cle API active / "
            "When: clic Revoquer confirme / "
            "Then: la cle retourne HTTP 403 en < 1s, entree ajoutee dans l'audit log."
        ),
        "story_points": 2,
        "priority": 10,
    },
    # ── sf-f-v2-auth-03 : RBAC et gestion des utilisateurs ─────────────────
    {
        "id": "sf-us-v2-005",
        "feature_id": "sf-f-v2-auth-03",
        "title": (
            "En tant qu'admin, je veux inviter un collaborateur par e-mail "
            "afin qu'il rejoigne le projet avec le role membre."
        ),
        "acceptance_criteria": (
            "Given: page Utilisateurs / "
            "When: saisie e-mail et role, envoi invitation / "
            "Then: e-mail envoye, lien valide 48h, utilisateur visible avec statut 'invite'."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v2-006",
        "feature_id": "sf-f-v2-auth-03",
        "title": (
            "En tant qu'admin, je veux suspendre un utilisateur "
            "afin de bloquer son acces sans supprimer son historique."
        ),
        "acceptance_criteria": (
            "Given: utilisateur actif / "
            "When: action Suspendre confirmee / "
            "Then: toutes ses sessions sont invalidees en < 1s, statut passe a 'suspendu'."
        ),
        "story_points": 2,
        "priority": 8,
    },
    # ── sf-f-v2-auth-04 : Push notifications PWA ───────────────────────────
    {
        "id": "sf-us-v2-007",
        "feature_id": "sf-f-v2-auth-04",
        "title": (
            "En tant qu'admin, je veux recevoir une push notification quand une mission P0 echoue "
            "afin d'etre alerte meme si l'onglet est ferme."
        ),
        "acceptance_criteria": (
            "Given: navigateur abonne et onglet SF ferme / "
            "When: mission P0 passe en erreur / "
            "Then: notification push recue en < 3s avec titre et lien direct."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-008",
        "feature_id": "sf-f-v2-auth-04",
        "title": (
            "En tant que membre, je veux gerer mes abonnements push par type d'evenement "
            "afin de ne recevoir que les notifications pertinentes."
        ),
        "acceptance_criteria": (
            "Given: page Preferences notifications / "
            "When: toggle desactive pour 'sprint.started' / "
            "Then: ce type d'evenement ne genere plus de push pour cet utilisateur."
        ),
        "story_points": 2,
        "priority": 5,
    },
    # ── sf-f-v2-dev-01 : Cibles de deploiement ─────────────────────────────
    {
        "id": "sf-us-v2-009",
        "feature_id": "sf-f-v2-dev-01",
        "title": (
            "En tant que DevOps, je veux ajouter une cible OVH SSH "
            "afin de deployer l'application depuis la plateforme sans terminal."
        ),
        "acceptance_criteria": (
            "Given: formulaire nouvelle cible / "
            "When: type=OVH, host+user+cle SSH saisis, Test connexion / "
            "Then: connexion SSH validee en < 10s, cible active dans la liste."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v2-010",
        "feature_id": "sf-f-v2-dev-01",
        "title": (
            "En tant que DevOps, je veux consulter les logs d'un deploiement echoue "
            "afin de diagnostiquer la cause sans se connecter en SSH."
        ),
        "acceptance_criteria": (
            "Given: deploiement en echec / "
            "When: clic sur Voir logs / "
            "Then: stdout+stderr du deploy affiches, code de sortie visible, telechargeable en TXT."
        ),
        "story_points": 3,
        "priority": 8,
    },
    # ── sf-f-v2-dev-02 : Webhooks ──────────────────────────────────────────
    {
        "id": "sf-us-v2-011",
        "feature_id": "sf-f-v2-dev-02",
        "title": (
            "En tant que Tech Lead, je veux qu'un push sur main declenche automatiquement "
            "la mission de deploiement associee afin d'automatiser la livraison continue."
        ),
        "acceptance_criteria": (
            "Given: webhook GitHub configure sur le projet / "
            "When: push sur la branche main / "
            "Then: mission de deploiement demarree en < 5s, lien dans le statut du commit GitHub."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v2-012",
        "feature_id": "sf-f-v2-dev-02",
        "title": (
            "En tant qu'admin, je veux rejouer un webhook recu "
            "afin de re-tester un traitement sans nouveau push."
        ),
        "acceptance_criteria": (
            "Given: webhook dans le journal / "
            "When: bouton Rejouer / "
            "Then: payload original rejoue, nouvelle entree dans le journal avec source='replay'."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # ── sf-f-v2-dev-03 : CLI SF ────────────────────────────────────────────
    {
        "id": "sf-us-v2-013",
        "feature_id": "sf-f-v2-dev-03",
        "title": (
            "En tant que DevOps, je veux lancer une mission depuis le terminal avec sf run "
            "afin d'integrer SF dans un pipeline CI/CD existant."
        ),
        "acceptance_criteria": (
            "Given: sf configure avec une cle API valide / "
            "When: sf run <mission-id> / "
            "Then: logs streames dans le terminal, code de sortie 0 si succes, 1 si echec."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-014",
        "feature_id": "sf-f-v2-dev-03",
        "title": (
            "En tant que Tech Lead, je veux obtenir le statut de toutes les missions actives "
            "avec sf status --json afin de l'integrer dans un dashboard externe."
        ),
        "acceptance_criteria": (
            "Given: missions en cours / "
            "When: sf status --json / "
            "Then: JSON valide avec liste missions, champs id/name/status/phase/progress."
        ),
        "story_points": 2,
        "priority": 7,
    },
    # ── sf-f-v2-dev-04 : DAG de dependances ───────────────────────────────
    {
        "id": "sf-us-v2-015",
        "feature_id": "sf-f-v2-dev-04",
        "title": (
            "En tant que Tech Lead, je veux definir qu'une mission de deploiement "
            "depend de la mission QA afin d'empecher le deploiement si les tests echouent."
        ),
        "acceptance_criteria": (
            "Given: deux missions QA et Deploy / "
            "When: dependance Deploy -> QA creee / "
            "Then: Deploy passe en 'waiting' si QA non terminee, se debloque automatiquement apres."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-016",
        "feature_id": "sf-f-v2-dev-04",
        "title": (
            "En tant qu'admin, je veux etre averti si je cree une dependance cyclique "
            "afin d'eviter un blocage infini."
        ),
        "acceptance_criteria": (
            "Given: DAG existant A -> B -> C / "
            "When: tentative de creation C -> A / "
            "Then: erreur 'cycle detecte' affichee, sauvegarde bloquee, DAG inchange."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # ── sf-f-v2-dev-05 : Protocol A2A ─────────────────────────────────────
    {
        "id": "sf-us-v2-017",
        "feature_id": "sf-f-v2-dev-05",
        "title": (
            "En tant que Tech Lead, je veux consulter le journal A2A d'une mission "
            "afin de comprendre pourquoi un agent a emis un veto."
        ),
        "acceptance_criteria": (
            "Given: mission avec message de veto / "
            "When: onglet A2A de la mission / "
            "Then: liste des messages avec expediteur, destinataire, type, horodatage et contenu."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-018",
        "feature_id": "sf-f-v2-dev-05",
        "title": (
            "En tant qu'admin, je veux configurer la hierarchie de veto par ART "
            "afin de definir quels agents peuvent bloquer quelles decisions."
        ),
        "acceptance_criteria": (
            "Given: page parametres ART / "
            "When: ordre de veto defini et sauvegarde / "
            "Then: les messages A2A respectent la priorite configuree lors du prochain sprint."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # ── sf-f-v2-dev-06 : Gestion multi-providers LLM ──────────────────────
    {
        "id": "sf-us-v2-019",
        "feature_id": "sf-f-v2-dev-06",
        "title": (
            "En tant qu'admin, je veux voir le cout mensuel par provider LLM "
            "afin de controler le budget et ajuster le fallback chain."
        ),
        "acceptance_criteria": (
            "Given: page LLM Providers / "
            "When: filtre mois courant / "
            "Then: tableau avec provider, tokens_in, tokens_out, cout USD, tri par cout."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v2-020",
        "feature_id": "sf-f-v2-dev-06",
        "title": (
            "En tant qu'admin, je veux desactiver un provider en un clic "
            "afin de l'exclure du fallback chain sans redemarrage du serveur."
        ),
        "acceptance_criteria": (
            "Given: provider Azure actif / "
            "When: toggle desactiver / "
            "Then: provider exclu du fallback en < 1s, badge 'inactif' affiche, aucune requete envoyee."
        ),
        "story_points": 2,
        "priority": 8,
    },
    # ── sf-f-v2-dev-07 : Tool Builder ─────────────────────────────────────
    {
        "id": "sf-us-v2-021",
        "feature_id": "sf-f-v2-dev-07",
        "title": (
            "En tant que Tech Lead, je veux creer un outil custom avec un editeur JSON Schema "
            "afin d'etendre les capacites d'un agent sans modifier le code source."
        ),
        "acceptance_criteria": (
            "Given: page Tool Builder / "
            "When: schema JSON + code Python saisis et sauvegardes / "
            "Then: outil disponible dans la liste des tools assignables a un agent en < 5s."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-022",
        "feature_id": "sf-f-v2-dev-07",
        "title": (
            "En tant que Tech Lead, je veux tester un outil depuis l'editeur "
            "afin de valider son comportement avant de l'assigner a un agent en production."
        ),
        "acceptance_criteria": (
            "Given: outil defini dans l'editeur / "
            "When: Lancer le test avec des parametres d'exemple / "
            "Then: stdout, stderr et valeur de retour affiches dans l'editeur en < 10s."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # ── sf-f-v2-dev-08 : Hooks lifecycle ──────────────────────────────────
    {
        "id": "sf-us-v2-023",
        "feature_id": "sf-f-v2-dev-08",
        "title": (
            "En tant que DevOps, je veux configurer un hook post-mission "
            "qui envoie un payload JSON a un endpoint Slack "
            "afin d'automatiser les notifications d'equipe."
        ),
        "acceptance_criteria": (
            "Given: hook HTTP post-mission configure / "
            "When: mission se termine / "
            "Then: payload JSON envoye en < 3s, log d'execution affiche avec code HTTP recu."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-024",
        "feature_id": "sf-f-v2-dev-08",
        "title": (
            "En tant que Tech Lead, je veux qu'un hook pre-mission puisse annuler le demarrage "
            "afin de valider des pre-conditions metier avant execution."
        ),
        "acceptance_criteria": (
            "Given: hook pre-mission retournant {cancel: true} / "
            "When: tentative de demarrage de la mission / "
            "Then: mission non demarree, raison du hook affichee, statut passe a 'annule'."
        ),
        "story_points": 3,
        "priority": 6,
    },
    # ── sf-f-v2-obs-01 : DORA Metrics ─────────────────────────────────────
    {
        "id": "sf-us-v2-025",
        "feature_id": "sf-f-v2-obs-01",
        "title": (
            "En tant que CTO, je veux voir les 4 metriques DORA sur un tableau de bord "
            "afin d'evaluer la maturite DevOps de mon equipe."
        ),
        "acceptance_criteria": (
            "Given: page Analytics DevOps / "
            "When: chargement / "
            "Then: 4 tuiles DORA avec valeur, tendance et badge Elite/High/Medium/Low."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-026",
        "feature_id": "sf-f-v2-obs-01",
        "title": (
            "En tant qu'analyste BI, je veux exporter les metriques DORA en CSV "
            "afin de les integrer dans mon outil de reporting."
        ),
        "acceptance_criteria": (
            "Given: page Analytics avec filtre trimestre / "
            "When: Export CSV / "
            "Then: fichier CSV avec colonnes date, deploy_freq, lead_time, mttr, change_fail_rate."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # ── sf-f-v2-obs-02 : Evaluations LLM ──────────────────────────────────
    {
        "id": "sf-us-v2-027",
        "feature_id": "sf-f-v2-obs-02",
        "title": (
            "En tant que Tech Lead, je veux lancer un benchmark LLM sur un jeu de donnees "
            "afin de comparer les providers avant de changer le provider principal."
        ),
        "acceptance_criteria": (
            "Given: jeu de donnees de reference charge / "
            "When: benchmark lance sur Azure et MiniMax / "
            "Then: rapport avec score global, precision, coherence, hallucination_rate par provider."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-028",
        "feature_id": "sf-f-v2-obs-02",
        "title": (
            "En tant que Tech Lead, je veux evaluer les skills d'un agent sur un scenario de test "
            "afin de valider une mise a jour de skill avant mise en production."
        ),
        "acceptance_criteria": (
            "Given: scenario de test defini pour la skill code_write / "
            "When: evaluation lancee / "
            "Then: score 0-100, details par critere, comparaison avec la version precedente."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # ── sf-f-v2-obs-03 : Recherche globale FTS5 ───────────────────────────
    {
        "id": "sf-us-v2-029",
        "feature_id": "sf-f-v2-obs-03",
        "title": (
            "En tant que membre, je veux utiliser Cmd+K pour rechercher dans tous les projets "
            "afin de retrouver une mission, une story ou une page wiki sans naviguer."
        ),
        "acceptance_criteria": (
            "Given: n'importe quelle page de la plateforme / "
            "When: Cmd+K puis saisie d'une requete / "
            "Then: resultats FTS5 groupes par type affiches en < 200ms avec highlight."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-030",
        "feature_id": "sf-f-v2-obs-03",
        "title": (
            "En tant qu'admin, je veux filtrer la recherche globale par type d'entite "
            "afin de limiter les resultats aux agents uniquement."
        ),
        "acceptance_criteria": (
            "Given: palette recherche ouverte / "
            "When: filtre type=agent applique / "
            "Then: seuls les agents apparaissent dans les resultats, badge de filtre visible."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # ── sf-f-v2-obs-04 : Journal d'evenements ─────────────────────────────
    {
        "id": "sf-us-v2-031",
        "feature_id": "sf-f-v2-obs-04",
        "title": (
            "En tant que DevOps, je veux voir le flux d'evenements en temps reel "
            "afin de surveiller l'activite de la plateforme sans recharger la page."
        ),
        "acceptance_criteria": (
            "Given: page Journal d'evenements / "
            "When: evenement emis / "
            "Then: nouvel evenement insere en haut de la liste en < 1s via SSE."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-032",
        "feature_id": "sf-f-v2-obs-04",
        "title": (
            "En tant qu'admin, je veux filtrer le journal par severite ERROR "
            "afin de ne voir que les anomalies et ne pas etre noye par les info."
        ),
        "acceptance_criteria": (
            "Given: journal avec evenements mixtes / "
            "When: filtre severite=ERROR / "
            "Then: seuls les evenements ERROR/CRITICAL affiches, compteur mis a jour."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # ── sf-f-v2-obs-05 : Wiki et gestion des connaissances ────────────────
    {
        "id": "sf-us-v2-033",
        "feature_id": "sf-f-v2-obs-05",
        "title": (
            "En tant que Tech Lead, je veux creer une page wiki Markdown pour documenter "
            "l'architecture du projet afin que les agents l'utilisent comme contexte."
        ),
        "acceptance_criteria": (
            "Given: wiki du projet ouvert / "
            "When: page creee et sauvegardee / "
            "Then: page visible dans l'arborescence, injectee dans le prompt systeme des agents."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v2-034",
        "feature_id": "sf-f-v2-obs-05",
        "title": (
            "En tant que Tech Lead, je veux consulter l'historique des modifications d'une page wiki "
            "afin de revenir a une version anterieure si necessaire."
        ),
        "acceptance_criteria": (
            "Given: page wiki avec plusieurs sauvegardes / "
            "When: onglet Historique / "
            "Then: liste des versions avec auteur, date, diff Markdown et bouton Restaurer."
        ),
        "story_points": 3,
        "priority": 5,
    },
    # ── sf-f-v2-obs-06 : Vue CTO ──────────────────────────────────────────
    {
        "id": "sf-us-v2-035",
        "feature_id": "sf-f-v2-obs-06",
        "title": (
            "En tant que CTO, je veux voir l'etat de tous les projets en une seule page "
            "afin d'avoir une vision portfolio sans naviguer projet par projet."
        ),
        "acceptance_criteria": (
            "Given: page Vue CTO / "
            "When: chargement / "
            "Then: tuiles projets avec sante, missions actives, DORA, budget LLM, alerte si derive."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-036",
        "feature_id": "sf-f-v2-obs-06",
        "title": (
            "En tant que CTO, je veux consulter la timeline roadmap des epics sur 4 trimestres "
            "afin d'anticiper les livraisons et ajuster les priorites."
        ),
        "acceptance_criteria": (
            "Given: epics avec dates planifiees / "
            "When: vue Roadmap CTO / "
            "Then: Gantt horizontal sur 4 trimestres, epics colores par statut, zoom possible."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # ── sf-f-v2-obs-07 : Gestion des sprints ──────────────────────────────
    {
        "id": "sf-us-v2-037",
        "feature_id": "sf-f-v2-obs-07",
        "title": (
            "En tant que Product Owner, je veux voir le burndown chart d'un sprint "
            "afin de suivre la progression par rapport a la velocite planifiee."
        ),
        "acceptance_criteria": (
            "Given: sprint actif avec stories / "
            "When: page Burndown du sprint / "
            "Then: courbe ideale vs courbe reelle, mise a jour en temps reel quand story = Done."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v2-038",
        "feature_id": "sf-f-v2-obs-07",
        "title": (
            "En tant que Tech Lead, je veux deplacer des stories d'un sprint a un autre par drag-drop "
            "afin d'ajuster le scope sans quitter la vue sprint."
        ),
        "acceptance_criteria": (
            "Given: vue Sprint Planning avec deux sprints / "
            "When: story glissee du Sprint 3 au Sprint 4 / "
            "Then: story assignee au Sprint 4, velocites recalculees, changement persiste."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # ── sf-f-v2-obs-08 : Instincts agents et modules ──────────────────────
    {
        "id": "sf-us-v2-039",
        "feature_id": "sf-f-v2-obs-08",
        "title": (
            "En tant que Tech Lead, je veux activer un instinct 'preferer les tests TDD' sur un agent "
            "afin que cet agent priorise systematiquement l'ecriture de tests avant le code."
        ),
        "acceptance_criteria": (
            "Given: agent sans instinct TDD / "
            "When: instinct 'prefer_tdd' active / "
            "Then: l'agent genere les tests en premier lors de la prochaine mission, sans redemarrage."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v2-040",
        "feature_id": "sf-f-v2-obs-08",
        "title": (
            "En tant qu'admin, je veux installer un module extension depuis le marketplace interne "
            "afin d'etendre les capacites de la plateforme sans modifier le code."
        ),
        "acceptance_criteria": (
            "Given: marketplace avec module 'git-insights' disponible / "
            "When: Installer / "
            "Then: module charge sans redemarrage, note et compteur d'installations mis a jour."
        ),
        "story_points": 5,
        "priority": 5,
    },
]

# ── V3 : Analytics, TMA, RBAC, Ideation, Rust Engine, Toolbox, Mercato ───────

SF_PERSONAS_V3: list[dict] = [
    {
        "id": "sf-p08-devops",
        "project_id": "software-factory",
        "name": "Karim — DevOps / SRE",
        "role": "member",
        "goals": (
            "Deployer sans downtime. Surveiller les metriques d'infrastructure. "
            "Automatiser les pipelines CI/CD avec les agents SF. "
            "Configurer les alertes Prometheus/Grafana depuis le cockpit."
        ),
        "pain_points": (
            "Pas de vue unifiee containers+agents. "
            "Les incidents P0 doivent etre traites en < 5 min sans acces SSH. "
            "Les logs sont disperses entre stdout, fichiers et Azure Monitor."
        ),
        "technical_level": "expert",
    },
    {
        "id": "sf-p09-po",
        "project_id": "software-factory",
        "name": "Inès — Product Owner",
        "role": "lead",
        "goals": (
            "Gerer le backlog SAFe (epics, features, stories). "
            "Prioriser avec WSJF. Suivre la velocite des equipes. "
            "Creer des missions depuis les stories directement. "
            "Consulter les KPIs produit sans aide technique."
        ),
        "pain_points": (
            "Difficulte a distinguer features techniques et business. "
            "Le scoring WSJF manuel est long et subjectif. "
            "Pas de notification quand une story est livree."
        ),
        "technical_level": "intermediate",
    },
]

SF_EPICS_V3: list[dict] = [
    {
        "id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Analytics & Observabilite",
        "description": (
            "Cockpit temps reel, DORA metrics, couts LLM, qualite du code, evaluations agents."
        ),
        "wsjf_score": 7.8,
        "status": "active",
    },
    {
        "id": "sf-e-10",
        "project_id": "software-factory",
        "title": "TMA & Gestion des Incidents",
        "description": (
            "Triage incidents P0-P4, SLA, escalation, maintenance planifiee, OpsView."
        ),
        "wsjf_score": 8.1,
        "status": "active",
    },
    {
        "id": "sf-e-11",
        "project_id": "software-factory",
        "title": "RBAC & Securite",
        "description": (
            "Gestion des roles (admin/lead/member/viewer), tokens API, audit logs, 2FA."
        ),
        "wsjf_score": 7.5,
        "status": "active",
    },
    {
        "id": "sf-e-12",
        "project_id": "software-factory",
        "title": "Ideation & Brainstorming",
        "description": (
            "Sessions d'ideation solo, groupe, MKT. Synthese automatique par agents."
        ),
        "wsjf_score": 6.2,
        "status": "active",
    },
    {
        "id": "sf-e-13",
        "project_id": "software-factory",
        "title": "Moteur Embarque Rust (sf-engine)",
        "description": (
            "Binaire Rust autonome: axum + SQLite + LLM streaming + tool-calling. "
            "Integre dans l'app macOS SF Inside, 5.3 MB, zero runtime Python."
        ),
        "wsjf_score": 9.2,
        "status": "active",
    },
    {
        "id": "sf-e-14",
        "project_id": "software-factory",
        "title": "Toolbox & MCP",
        "description": (
            "Gestion des outils (MCP, intégrations tierces, tool builder). "
            "Execution securisee des outils dans les missions agents."
        ),
        "wsjf_score": 7.0,
        "status": "active",
    },
    {
        "id": "sf-e-15",
        "project_id": "software-factory",
        "title": "Mercato & Evolution Darwinienne",
        "description": (
            "Marketplace agents, Thompson Sampling, Darwin teams, scoring fitness."
        ),
        "wsjf_score": 6.8,
        "status": "active",
    },
]

SF_FEATURES_V3: list[dict] = [
    # ── Analytics (E09) ──
    {
        "id": "sf-f-v3-ana-01",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Cockpit temps reel — metriques missions, agents, LLM",
        "description": "Dashboard avec KPIs: missions actives, tokens/minute, taux succes agents.",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v3-ana-02",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "DORA metrics — lead time, deploy frequency, MTTR, CFR",
        "description": "Calcul automatique des 4 metriques DORA depuis git + deploys.",
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-f-v3-ana-03",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Suivi couts LLM par agent et par mission",
        "description": "Comptage tokens entree/sortie, cout $, budget par projet.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v3-ana-04",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Evaluations agents — benchmark automatise",
        "description": "Grille d'eval: pertinence, format, hallucination, vitesse, cout.",
        "story_points": 8,
        "priority": 7,
    },
    # ── TMA (E10) ──
    {
        "id": "sf-f-v3-tma-01",
        "epic_id": "sf-e-10",
        "project_id": "software-factory",
        "title": "Triage incidents P0-P4 avec SLA automatique",
        "description": "Creation incident, assignation agent TMA, minuteur SLA, escalation.",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v3-tma-02",
        "epic_id": "sf-e-10",
        "project_id": "software-factory",
        "title": "Dashboard ops — etat services, alertes actives",
        "description": "Vue temps reel: containers UP/DOWN, endpoints health, alertes.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v3-tma-03",
        "epic_id": "sf-e-10",
        "project_id": "software-factory",
        "title": "Maintenance planifiee — fenetres, notifications",
        "description": "Planifier maintenance, notifier utilisateurs, mode degradé automatique.",
        "story_points": 3,
        "priority": 6,
    },
    # ── RBAC (E11) ──
    {
        "id": "sf-f-v3-rbac-01",
        "epic_id": "sf-e-11",
        "project_id": "software-factory",
        "title": "Gestion roles utilisateurs (admin/lead/member/viewer)",
        "description": "CRUD utilisateurs avec roles, assignation aux equipes, héritage.",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v3-rbac-02",
        "epic_id": "sf-e-11",
        "project_id": "software-factory",
        "title": "Tokens API et audit log",
        "description": "Generation tokens long-lived, log de toutes les actions sensibles.",
        "story_points": 5,
        "priority": 8,
    },
    # ── Ideation (E12) ──
    {
        "id": "sf-f-v3-ide-01",
        "epic_id": "sf-e-12",
        "project_id": "software-factory",
        "title": "Session d'ideation solo — brainstorming agent",
        "description": "Mode ideation: 1 utilisateur + N agents en debat, synthese finale.",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v3-ide-02",
        "epic_id": "sf-e-12",
        "project_id": "software-factory",
        "title": "Session d'ideation groupe — vote et convergence",
        "description": "Multi-utilisateurs + agents, vote sur idees, synthese consensus.",
        "story_points": 8,
        "priority": 6,
    },
    # ── Rust Engine (E13) ──
    {
        "id": "sf-f-v3-eng-01",
        "epic_id": "sf-e-13",
        "project_id": "software-factory",
        "title": "sf-engine binaire Rust — health, agents, sessions",
        "description": "API HTTP axum: /api/health, /api/agents, /api/sessions. SQLite WAL.",
        "story_points": 13,
        "priority": 10,
    },
    {
        "id": "sf-f-v3-eng-02",
        "epic_id": "sf-e-13",
        "project_id": "software-factory",
        "title": "LLM client streaming — Ollama, MiniMax, Azure",
        "description": "SSE streaming, tool_calls accumulation, fallback provider.",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-f-v3-eng-03",
        "epic_id": "sf-e-13",
        "project_id": "software-factory",
        "title": "Agent executor tool-calling loop",
        "description": "Max 10 rounds, tools: list_agents/memory_search/memory_store/list_projects.",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-f-v3-eng-04",
        "epic_id": "sf-e-13",
        "project_id": "software-factory",
        "title": "Seeding agents depuis sf_data.json au premier demarrage",
        "description": "Si table agents vide, parse sf_data.json et insere 192 agents en SQLite.",
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-f-v3-eng-05",
        "epic_id": "sf-e-13",
        "project_id": "software-factory",
        "title": "SFEngineManager.swift — lifecycle binaire dans SwiftUI",
        "description": "Start/stop/poll, env vars LLM depuis UserDefaults, status dot sidebar.",
        "story_points": 5,
        "priority": 9,
    },
    # ── Toolbox (E14) ──
    {
        "id": "sf-f-v3-tool-01",
        "epic_id": "sf-e-14",
        "project_id": "software-factory",
        "title": "Gestionnaire MCP (Model Context Protocol)",
        "description": "Lister, activer/desactiver les MCP servers. Proxy securise depuis agents.",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v3-tool-02",
        "epic_id": "sf-e-14",
        "project_id": "software-factory",
        "title": "Tool Builder — creer outils custom sans code",
        "description": "Interface no-code: nom, description, parametres, commande bash/HTTP.",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v3-tool-03",
        "epic_id": "sf-e-14",
        "project_id": "software-factory",
        "title": "Integrations tierces — GitHub, GitLab, Jira, Slack",
        "description": "Webhooks entrants + actions sortantes depuis les agents.",
        "story_points": 8,
        "priority": 6,
    },
    # ── Mercato (E15) ──
    {
        "id": "sf-f-v3-mkt-01",
        "epic_id": "sf-e-15",
        "project_id": "software-factory",
        "title": "Marketplace agents — notation, popularite, install",
        "description": "Catalogue agents avec score, tags, reviews, install en 1 clic.",
        "story_points": 8,
        "priority": 6,
    },
    {
        "id": "sf-f-v3-mkt-02",
        "epic_id": "sf-e-15",
        "project_id": "software-factory",
        "title": "Evolution darwinienne — Thompson Sampling + fitness",
        "description": "Score fitness par agent, selection naturelle, croisement de personas.",
        "story_points": 13,
        "priority": 7,
    },
    {
        "id": "sf-f-v3-mkt-03",
        "epic_id": "sf-e-15",
        "project_id": "software-factory",
        "title": "Darwin Teams — composition equipe optimale automatique",
        "description": "Algorithme génétique: muter, croiser, evaluer teams sur historique missions.",
        "story_points": 8,
        "priority": 6,
    },
]

SF_STORIES_V3: list[dict] = [
    # ── Analytics ──
    {
        "id": "sf-us-v3-001",
        "feature_id": "sf-f-v3-ana-01",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux voir les missions actives en temps reel sur le cockpit.",
        "acceptance_criteria": (
            "Given: cockpit ouvert / When: mission demarre / "
            "Then: compteur 'missions actives' s'incremente sans refresh."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v3-002",
        "feature_id": "sf-f-v3-ana-01",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux voir les tokens/minute par agent pour detecter les runaway loops.",
        "acceptance_criteria": (
            "Given: agent en boucle / When: cockpit / "
            "Then: graphe tokens/min monte, alerte visuelle si > seuil."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-003",
        "feature_id": "sf-f-v3-ana-02",
        "project_id": "software-factory",
        "title": "En tant que devops, je veux consulter les 4 metriques DORA pour evaluer notre maturite CI/CD.",
        "acceptance_criteria": (
            "Given: historique git+deploys disponible / When: page DORA / "
            "Then: lead time, deploy freq, MTTR, CFR affiches avec trend 30j."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-004",
        "feature_id": "sf-f-v3-ana-03",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux voir le cout LLM total de la semaine par projet.",
        "acceptance_criteria": (
            "Given: missions terminees / When: page LLM Costs / "
            "Then: tableau tokens/cout $ par projet, export CSV."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-005",
        "feature_id": "sf-f-v3-ana-04",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux evaluer un agent sur 5 criteres pour choisir le meilleur provider.",
        "acceptance_criteria": (
            "Given: 2 agents / When: lancer eval sur scenario / "
            "Then: scores pertinence/format/hallucination/vitesse/cout affiches cote a cote."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # ── TMA ──
    {
        "id": "sf-us-v3-006",
        "feature_id": "sf-f-v3-tma-01",
        "project_id": "software-factory",
        "title": "En tant que devops, je veux creer un incident P1 et que l'agent TMA soit notifie immediatement.",
        "acceptance_criteria": (
            "Given: nouveau incident P1 / When: sauvegarder / "
            "Then: agent TMA assigne, timer SLA 1h demarre, notification Slack."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v3-007",
        "feature_id": "sf-f-v3-tma-01",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux voir tous les incidents ouverts tries par severite.",
        "acceptance_criteria": (
            "Given: liste incidents / When: page TMA / "
            "Then: P0 en rouge en premier, timer SLA visible, filtre par statut."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-008",
        "feature_id": "sf-f-v3-tma-02",
        "project_id": "software-factory",
        "title": "En tant que SRE, je veux voir l'etat de chaque service en un coup d'oeil.",
        "acceptance_criteria": (
            "Given: page Ops / When: ouverte / "
            "Then: services listes avec badge UP/DOWN, latence, derniere check."
        ),
        "story_points": 3,
        "priority": 8,
    },
    # ── RBAC ──
    {
        "id": "sf-us-v3-009",
        "feature_id": "sf-f-v3-rbac-01",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux creer un utilisateur avec le role 'viewer' pour un client externe.",
        "acceptance_criteria": (
            "Given: page RBAC / When: creer user viewer / "
            "Then: user cree, acces lecture seule, impossible de lancer une mission."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-010",
        "feature_id": "sf-f-v3-rbac-02",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux generer un token API long-lived pour les intégrations CI/CD.",
        "acceptance_criteria": (
            "Given: page RBAC / When: generer token / "
            "Then: token affiché une seule fois, enregistre en DB (hash), révocable."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-011",
        "feature_id": "sf-f-v3-rbac-02",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux consulter l'audit log pour voir qui a lance quelle mission.",
        "acceptance_criteria": (
            "Given: missions lancees par plusieurs users / When: audit log / "
            "Then: entrees horodatees user+action+ressource, filtrable par date/user."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # ── Ideation ──
    {
        "id": "sf-us-v3-012",
        "feature_id": "sf-f-v3-ide-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux lancer une session d'ideation avec 3 agents pour generer des features.",
        "acceptance_criteria": (
            "Given: nouvelle session ideation / When: topic + agents selectionnes / "
            "Then: agents debattent, proposent 10+ idees, synthese finale en markdown."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-013",
        "feature_id": "sf-f-v3-ide-02",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux organiser un vote sur les idees generees pour prioriser le backlog.",
        "acceptance_criteria": (
            "Given: session ideation terminee / When: mode vote / "
            "Then: idees affichees avec boutons vote, top 3 apparait en temps reel."
        ),
        "story_points": 5,
        "priority": 6,
    },
    # ── Rust Engine ──
    {
        "id": "sf-us-v3-014",
        "feature_id": "sf-f-v3-eng-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux que SF Inside demarre automatiquement sans serveur externe.",
        "acceptance_criteria": (
            "Given: app SF macOS lancee / When: premiere ouverture / "
            "Then: moteur Rust demarre en arriere-plan, pret en < 3s, point vert sidebar."
        ),
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-v3-015",
        "feature_id": "sf-f-v3-eng-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur SF Inside, je veux chatter avec un agent Ollama en streaming.",
        "acceptance_criteria": (
            "Given: Ollama llama3.2 actif / When: message envoye / "
            "Then: tokens arrivent en streaming SSE < 200ms latence, aucun timeout."
        ),
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-v3-016",
        "feature_id": "sf-f-v3-eng-03",
        "project_id": "software-factory",
        "title": "En tant qu'agent SF Inside, je veux utiliser list_agents pour composer une equipe.",
        "acceptance_criteria": (
            "Given: 192 agents seedes / When: agent appelle list_agents / "
            "Then: reponse JSON avec agents en < 50ms, loop continue avec resultats."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v3-017",
        "feature_id": "sf-f-v3-eng-04",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux que les 192 agents soient disponibles des le premier demarrage.",
        "acceptance_criteria": (
            "Given: premiere installation / When: moteur demarre / "
            "Then: agents table seeded depuis sf_data.json, GET /api/agents retourne 192 agents."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v3-018",
        "feature_id": "sf-f-v3-eng-05",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir l'etat du moteur en temps reel dans la sidebar.",
        "acceptance_criteria": (
            "Given: sidebar ouverte / When: moteur en cours de demarrage / "
            "Then: point orange clignotant. Quand pret: point vert. Erreur: point rouge."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-019",
        "feature_id": "sf-f-v3-eng-05",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux configurer le LLM dans l'onboarding et que sf-engine en herite.",
        "acceptance_criteria": (
            "Given: onboarding Ollama active / When: terminer onboarding / "
            "Then: UserDefaults sf_llm_url/key/model mis a jour, moteur redemarre avec la nouvelle config."
        ),
        "story_points": 3,
        "priority": 9,
    },
    # ── Toolbox ──
    {
        "id": "sf-us-v3-020",
        "feature_id": "sf-f-v3-tool-01",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux activer le MCP 'filesystem' pour que les agents lisent les fichiers projet.",
        "acceptance_criteria": (
            "Given: MCP filesystem configure / When: activer / "
            "Then: agents dans missions peuvent appeler read_file, liste outils mise a jour."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-021",
        "feature_id": "sf-f-v3-tool-02",
        "project_id": "software-factory",
        "title": "En tant que membre, je veux creer un outil 'deploy-staging' sans coder.",
        "acceptance_criteria": (
            "Given: tool builder / When: creer outil avec commande 'gh workflow run ci.yml' / "
            "Then: outil visible dans toolbox, utilisable dans missions, schema JSON genere."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-022",
        "feature_id": "sf-f-v3-tool-03",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux connecter SF a GitHub pour que les agents creent des PRs.",
        "acceptance_criteria": (
            "Given: integration GitHub configuree / When: agent code termine / "
            "Then: PR creee automatiquement avec diff, titre, description generee par l'agent."
        ),
        "story_points": 8,
        "priority": 6,
    },
    # ── Mercato ──
    {
        "id": "sf-us-v3-023",
        "feature_id": "sf-f-v3-mkt-01",
        "project_id": "software-factory",
        "title": "En tant que membre, je veux installer un agent 'Security Scanner' depuis le marketplace.",
        "acceptance_criteria": (
            "Given: marketplace avec agent 'Security Scanner' / When: installer / "
            "Then: agent disponible dans mes equipes, compteur installs incremente."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v3-024",
        "feature_id": "sf-f-v3-mkt-02",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux voir le score fitness de chaque agent apres une mission.",
        "acceptance_criteria": (
            "Given: mission terminee / When: evolution dashboard / "
            "Then: tableau agents avec fitness score (pertinence, vitesse, cout), delta vs precedent."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-025",
        "feature_id": "sf-f-v3-mkt-03",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux lancer une generation darwinienne pour optimiser la composition d'une equipe.",
        "acceptance_criteria": (
            "Given: equipe existante avec historique missions / When: lancer evolution / "
            "Then: 5 generations calculees, meilleure composition proposee, diff affiché."
        ),
        "story_points": 8,
        "priority": 6,
    },
    # ── Onboarding & Instances (manquants) ──
    {
        "id": "sf-us-v3-026",
        "feature_id": "sf-f-v3-eng-05",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux connecter SF a une instance distante OVH depuis l'onboarding.",
        "acceptance_criteria": (
            "Given: onboarding step instances / When: URL OVH + token / "
            "Then: SF Inside + SF OVH affiches dans la liste, ping de sante effectue."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v3-027",
        "feature_id": "sf-f-v3-eng-05",
        "project_id": "software-factory",
        "title": "En tant que devops, je veux basculer d'une instance SF a l'autre en un clic.",
        "acceptance_criteria": (
            "Given: 3 instances configurees / When: clic sur badge instance sidebar / "
            "Then: liste instances, clic sur instance → toutes les vues chargent depuis cette instance."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v3-028",
        "feature_id": "sf-f-v3-ana-01",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux voir le taux de succes des missions sur 30 jours.",
        "acceptance_criteria": (
            "Given: historique missions / When: cockpit / "
            "Then: graphe taux succes/echec/partiel, sparkline 30j, delta vs periode precedente."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v3-029",
        "feature_id": "sf-f-v3-tma-03",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux planifier une maintenance et notifier les utilisateurs.",
        "acceptance_criteria": (
            "Given: maintenance planifiee / When: save / "
            "Then: banniere affichee dans toutes les vues, mode degradé automatique a l'heure H."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v3-030",
        "feature_id": "sf-f-v3-rbac-01",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux empecher un viewer de supprimer un projet.",
        "acceptance_criteria": (
            "Given: user role=viewer / When: tente DELETE /api/projects/x / "
            "Then: 403 Forbidden, bouton supprimer non visible dans l'UI."
        ),
        "story_points": 2,
        "priority": 8,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# V4 — Recherche · Raccourcis · Offline · Import/Export · Notifs · A11y · macOS
# ─────────────────────────────────────────────────────────────────────────────

SF_PERSONAS_V4: list[dict] = [
    {
        "id": "sf-p-10",
        "name": "Gestionnaire Qualité",
        "role": "qa_manager",
        "project_id": "software-factory",
        "description": "Responsable qualité logicielle, suit les métriques, gère les évaluations et les régressions.",
        "goals": "Maintenir un taux de succès tests > 95%, zéro régression en production.",
        "pain_points": "Manque de visibilité sur les scores de qualité en temps réel, trop d'alertes bruit.",
        "tools": ["quality dashboard", "eval runner", "test reports"],
    },
    {
        "id": "sf-p-11",
        "name": "Utilisateur Mobile/Mac",
        "role": "mac_user",
        "project_id": "software-factory",
        "description": "Utilise l'app macOS native SF Inside pour piloter la factory en déplacement ou hors-ligne.",
        "goals": "Continuer à travailler offline, basculer entre instances sans friction.",
        "pain_points": "Synchro lente, perte de contexte au redémarrage, absence de raccourcis clavier.",
        "tools": ["SF Inside (macOS)", "Ollama local", "MLX LM"],
    },
]

SF_EPICS_V4: list[dict] = [
    {
        "id": "sf-e-v4-search",
        "project_id": "software-factory",
        "title": "Recherche Universelle",
        "status": "planned",
        "wsjf": 34,
        "description": "Recherche globale full-text + sémantique sur tous les objets SF (agents, sessions, epics, mémoire, wiki).",
        "business_value": 9,
        "time_criticality": 6,
        "risk_reduction": 7,
        "job_size": 5,
    },
    {
        "id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "UX · Raccourcis · A11y",
        "status": "planned",
        "wsjf": 28,
        "description": "Raccourcis clavier universels, accessibilité WCAG 2.1 AA, thèmes, notifications natives.",
        "business_value": 8,
        "time_criticality": 5,
        "risk_reduction": 6,
        "job_size": 5,
    },
    {
        "id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "Mode Offline & Sync",
        "status": "planned",
        "wsjf": 31,
        "description": "Fonctionnement complet offline avec sync automatique au retour en ligne (macOS + web).",
        "business_value": 9,
        "time_criticality": 7,
        "risk_reduction": 8,
        "job_size": 6,
    },
    {
        "id": "sf-e-v4-import",
        "project_id": "software-factory",
        "title": "Import / Export & API publique",
        "status": "planned",
        "wsjf": 26,
        "description": "Export JSON/CSV/Markdown de tous objets SF, import depuis Jira/GitHub/Confluence, API REST publique documentée.",
        "business_value": 8,
        "time_criticality": 5,
        "risk_reduction": 5,
        "job_size": 6,
    },
]

SF_FEATURES_V4: list[dict] = [
    # ── Recherche Universelle ──
    {
        "id": "sf-f-v4-search-01",
        "epic_id": "sf-e-v4-search",
        "project_id": "software-factory",
        "title": "Barre de recherche globale (Cmd+K)",
        "description": "Palette de commandes accessible via Cmd+K — recherche agents, sessions, epics, skills, wiki en temps réel.",
        "acceptance_criteria": "Cmd+K ouvre palette · Résultats < 200ms · Navigation clavier (↑↓↩) · Historique récent · Fermeture Esc",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-f-v4-search-02",
        "epic_id": "sf-e-v4-search",
        "project_id": "software-factory",
        "title": "Recherche sémantique mémoire & wiki",
        "description": "Recherche vectorielle sur les entrées mémoire et pages wiki via embedding local ou API.",
        "acceptance_criteria": "Recherche mémoire retourne top-5 par similarité · Wiki filtre par catégorie · Highlight des termes",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v4-search-03",
        "epic_id": "sf-e-v4-search",
        "project_id": "software-factory",
        "title": "Filtres avancés & sauvegarde de recherches",
        "description": "Filtres combinables (type, status, date, projet, agent) + sauvegarde de requêtes nommées.",
        "acceptance_criteria": "≥5 critères combinables · Sauvegarde persistante · URL partageable",
        "story_points": 5,
        "priority": 6,
    },
    # ── UX · Raccourcis · A11y ──
    {
        "id": "sf-f-v4-ux-01",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Raccourcis clavier universels",
        "description": "Tous les écrans navigables au clavier. Cmd+K recherche, Cmd+N nouveau, Cmd+Entrée valider, Esc fermer.",
        "acceptance_criteria": "100% des actions principales accessibles clavier · Cheatsheet affichable (?) · Hints dans tooltips",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-f-v4-ux-02",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Notifications natives macOS",
        "description": "Notifications système pour: mission terminée, incident P1, agent en attente, build fail.",
        "acceptance_criteria": "UNUserNotificationCenter · Clic ouvre vue concernée · Niveau configurable · DND respecté",
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-f-v4-ux-03",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Menu bar / Status item macOS",
        "description": "Icône dans la barre de menu montrant le nombre de missions actives, accès rapide aux sessions.",
        "acceptance_criteria": "NSStatusItem visible · Badge missions actives · Popover: sessions récentes + nouvelle session",
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-f-v4-ux-04",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Accessibilité WCAG 2.1 AA",
        "description": "Tous les éléments interactifs ont des labels accessibilité, navigation VoiceOver complète, contraste ≥ 4.5:1.",
        "acceptance_criteria": "0 erreur axe · VoiceOver annonce actions · Focus visible partout · No motion option",
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-f-v4-ux-05",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Thèmes & personnalisation",
        "description": "Thème dark (default), light, et custom. Taille de police réglable. Densité compact/normal/confortable.",
        "acceptance_criteria": "3 thèmes · Persistance AppStorage · Live preview · Respect préférences système dark/light",
        "story_points": 5,
        "priority": 5,
    },
    {
        "id": "sf-f-v4-ux-06",
        "epic_id": "sf-e-v4-ux",
        "project_id": "software-factory",
        "title": "Drag & drop et gestures macOS",
        "description": "Drag & drop pour réordonner epics/stories dans le backlog, drag agents vers équipes dans l'org.",
        "acceptance_criteria": "D&D backlog réordonne WSJF · D&D org assigne agent · Feedback visuel · Annulable Cmd+Z",
        "story_points": 5,
        "priority": 6,
    },
    # ── Mode Offline & Sync ──
    {
        "id": "sf-f-v4-offline-01",
        "epic_id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "Détection & bannière mode offline",
        "description": "Bannière non-intrusive quand l'instance distante est injoignable. App reste fonctionnelle en lecture.",
        "acceptance_criteria": "Ping toutes les 30s · Bannière jaune si offline · Retry automatique · Données cache affichées",
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-f-v4-offline-02",
        "epic_id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "File d'attente mutations offline",
        "description": "Les actions (créer session, ajouter mémoire, créer incident) sont mises en file et rejouées au retour en ligne.",
        "acceptance_criteria": "Queue persistée SQLite local · Indicateur '3 en attente' · Ordre garanti · Gestion conflits simple (last-write-wins)",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v4-offline-03",
        "epic_id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "Sync intelligente au retour en ligne",
        "description": "Au retour en ligne, sync delta: envoie mutations locales, pull changements distants, résout conflits.",
        "acceptance_criteria": "Sync en < 5s pour < 100 mutations · Notification 'Sync terminée' · Log sync consultable",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v4-offline-04",
        "epic_id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "Mode SF Inside 100% offline avec Ollama",
        "description": "SF Inside fonctionne complètement offline avec Ollama local: sessions, agents, mémoire, backlog.",
        "acceptance_criteria": "Aucun appel réseau externe en mode Inside · LLM = Ollama local · DB = SQLite embarqué",
        "story_points": 5,
        "priority": 10,
    },
    # ── Import / Export & API publique ──
    {
        "id": "sf-f-v4-import-01",
        "epic_id": "sf-e-v4-import",
        "project_id": "software-factory",
        "title": "Export JSON/CSV/Markdown",
        "description": "Export complet d'un projet (epics, stories, agents, sessions) en JSON, CSV, ou Markdown bundle.",
        "acceptance_criteria": "3 formats · Sélection partielle (checkbox) · Fichier horodaté · Import du même format",
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-f-v4-import-02",
        "epic_id": "sf-e-v4-import",
        "project_id": "software-factory",
        "title": "Import depuis Jira / GitHub Issues",
        "description": "Import d'epics/stories depuis Jira JQL ou GitHub Issues via token API. Mapping champs configurable.",
        "acceptance_criteria": "Connexion OAuth ou token · Preview avant import · Dédoublonnage par ID externe · Sync incrémentale",
        "story_points": 8,
        "priority": 6,
    },
    {
        "id": "sf-f-v4-import-03",
        "epic_id": "sf-e-v4-import",
        "project_id": "software-factory",
        "title": "API REST publique documentée (OpenAPI)",
        "description": "Tous les endpoints SF documentés en OpenAPI 3.1 avec examples, auth Bearer, rate limits.",
        "acceptance_criteria": "Swagger UI à /api/docs · 100% des endpoints couverts · SDK Python auto-généré",
        "story_points": 8,
        "priority": 6,
    },
    {
        "id": "sf-f-v4-import-04",
        "epic_id": "sf-e-v4-import",
        "project_id": "software-factory",
        "title": "Webhooks & events sortants",
        "description": "Webhooks configurables: mission.completed, incident.p1.created, evolution.agent.promoted.",
        "acceptance_criteria": "CRUD webhooks via UI · Payload JSON signé HMAC · Retry 3x · Log deliveries · Test manuel",
        "story_points": 5,
        "priority": 5,
    },
    # ── Extra features manquantes (reviews) ──
    {
        "id": "sf-f-v4-misc-01",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Tableau de bord analytique temps réel",
        "description": "Vue cockpit avec graphes live (polling 30s): sessions actives, tokens/min, agents busy, incidents ouverts.",
        "acceptance_criteria": "Sparklines SVG · Polling auto · Cache 30s · Export PNG · Filtres par instance",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v4-misc-02",
        "epic_id": "sf-e-09",
        "project_id": "software-factory",
        "title": "Évaluations LLM (eval datasets)",
        "description": "Création de datasets d'évaluation, lancement de runs comparatifs entre modèles, scoring automatique.",
        "acceptance_criteria": "CRUD datasets · Run sur ≥2 modèles · Métriques: BLEU, exact-match, LLM-judge · Graphe comparatif",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v4-misc-03",
        "epic_id": "sf-e-10",
        "project_id": "software-factory",
        "title": "TMA · Runbooks automatisés",
        "description": "Runbooks exécutés automatiquement à la création d'un incident selon son type/sévérité.",
        "acceptance_criteria": "CRUD runbooks YAML · Exécution auto sur P1/P2 · Log steps · Override manuel possible",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v4-misc-04",
        "epic_id": "sf-e-11",
        "project_id": "software-factory",
        "title": "RBAC · Audit log",
        "description": "Log immuable de toutes les actions sensibles: connexion, suppression, changement de rôle.",
        "acceptance_criteria": "Table audit_log append-only · Filtres user/action/date · Export CSV · Retention 90j",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v4-misc-05",
        "epic_id": "sf-e-12",
        "project_id": "software-factory",
        "title": "Idéation · Évaluation et scoring des idées",
        "description": "Après génération, évaluation automatique des idées par un panel d'agents (feasibility, impact, novelty).",
        "acceptance_criteria": "Score 0-10 par axe · Classement automatique · Radar chart · Export ideas.json",
        "story_points": 5,
        "priority": 6,
    },
    {
        "id": "sf-f-v4-misc-06",
        "epic_id": "sf-e-v4-offline",
        "project_id": "software-factory",
        "title": "macOS · Instances distantes favoris & health",
        "description": "Gestion des instances (OVH/Azure/local) avec état santé en temps réel et basculement en 1 clic.",
        "acceptance_criteria": "Ping chaque instance / 60s · Indicateur vert/orange/rouge · Favoris persistés · Basculement sans perte",
        "story_points": 3,
        "priority": 9,
    },
]

SF_STORIES_V4: list[dict] = [
    # Recherche universelle
    {
        "id": "sf-us-v4-001",
        "feature_id": "sf-f-v4-search-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux ouvrir la palette de commandes via Cmd+K pour naviguer sans souris.",
        "acceptance_criteria": (
            "Given: app ouverte / When: Cmd+K / "
            "Then: palette s'ouvre, focus sur champ, liste raccourcis récents."
        ),
        "story_points": 3,
        "priority": 10,
    },
    {
        "id": "sf-us-v4-002",
        "feature_id": "sf-f-v4-search-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux chercher un agent par nom ou rôle et naviguer directement vers sa fiche.",
        "acceptance_criteria": (
            "Given: palette ouverte / When: tape 'Karim' / "
            "Then: AgentCard 'Karim Benchekroun' apparaît en < 200ms, Entrée ouvre la fiche."
        ),
        "story_points": 2,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-003",
        "feature_id": "sf-f-v4-search-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux chercher une epic ou une story dans la palette.",
        "acceptance_criteria": (
            "Given: palette / When: tape 'SF-E-01' ou un mot-clé / "
            "Then: epic correspondante apparaît avec statut + WSJF, Entrée ouvre le détail."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-004",
        "feature_id": "sf-f-v4-search-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux rechercher sémantiquement dans la mémoire globale.",
        "acceptance_criteria": (
            "Given: page mémoire / When: tape 'décision architecture' / "
            "Then: top-5 entrées pertinentes par score similarité, highlights termes matchés."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-005",
        "feature_id": "sf-f-v4-search-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux chercher dans le wiki par titre et contenu.",
        "acceptance_criteria": (
            "Given: page wiki / When: saisie dans search bar / "
            "Then: filtrage live, highlight extraits, tri par pertinence."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-006",
        "feature_id": "sf-f-v4-search-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux combiner filtre 'type=agent' + 'status=active' dans la palette.",
        "acceptance_criteria": (
            "Given: palette / When: tape 'type:agent status:active' / "
            "Then: résultats filtrés, chips filtres visibles, supprimables."
        ),
        "story_points": 3,
        "priority": 6,
    },
    # Raccourcis clavier
    {
        "id": "sf-us-v4-007",
        "feature_id": "sf-f-v4-ux-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux créer une nouvelle session via Cmd+N.",
        "acceptance_criteria": (
            "Given: app ouverte, sidebar visible / When: Cmd+N / "
            "Then: sheet 'Nouvelle session' s'ouvre avec focus sur champ agent."
        ),
        "story_points": 1,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-008",
        "feature_id": "sf-f-v4-ux-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux fermer un panneau ou sheet via Esc.",
        "acceptance_criteria": (
            "Given: sheet ouverte / When: Esc / "
            "Then: sheet fermée, focus retourné à l'élément déclencheur."
        ),
        "story_points": 1,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-009",
        "feature_id": "sf-f-v4-ux-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux afficher le cheatsheet des raccourcis avec '?'.",
        "acceptance_criteria": (
            "Given: app / When: touche '?' hors d'un champ texte / "
            "Then: overlay cheatsheet avec toutes les combinaisons par section."
        ),
        "story_points": 2,
        "priority": 7,
    },
    # Notifications
    {
        "id": "sf-us-v4-010",
        "feature_id": "sf-f-v4-ux-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux recevoir une notification macOS quand une mission se termine.",
        "acceptance_criteria": (
            "Given: mission en cours, app en arrière-plan / When: mission.status=completed / "
            "Then: notification système avec titre mission + durée, clic ouvre la mission."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-011",
        "feature_id": "sf-f-v4-ux-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux être notifié d'un incident P1 créé.",
        "acceptance_criteria": (
            "Given: incident P1 créé / When: incident.priority=critical / "
            "Then: notification urgente, badge rouge sur icône app, son distinct."
        ),
        "story_points": 2,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-012",
        "feature_id": "sf-f-v4-ux-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux configurer quels événements me notifient.",
        "acceptance_criteria": (
            "Given: Settings > Notifications / When: toggle par catégorie / "
            "Then: préférence persistée, seuls les types activés génèrent des notifs."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # Menu bar
    {
        "id": "sf-us-v4-013",
        "feature_id": "sf-f-v4-ux-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir le nombre de missions actives dans la barre de menu.",
        "acceptance_criteria": (
            "Given: app lancée / When: 2 missions running / "
            "Then: icône SF dans menubar avec badge '2', clic ouvre popover sessions."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-014",
        "feature_id": "sf-f-v4-ux-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux lancer une nouvelle session depuis le menu bar sans ouvrir l'app.",
        "acceptance_criteria": (
            "Given: app en arrière-plan / When: clic menubar > Nouvelle session / "
            "Then: window focus + NewSessionView ouverte directement."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # Accessibilité
    {
        "id": "sf-us-v4-015",
        "feature_id": "sf-f-v4-ux-04",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur VoiceOver, je veux naviguer dans la sidebar et entendre chaque section.",
        "acceptance_criteria": (
            "Given: VoiceOver actif / When: navigation Tab/↑↓ / "
            "Then: chaque bouton annoncé avec label + état, focus visible visible."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-016",
        "feature_id": "sf-f-v4-ux-04",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux que tous les graphiques analytiques aient des alternatives textuelles.",
        "acceptance_criteria": (
            "Given: page analytics / When: VoiceOver lit graphiques / "
            "Then: chaque graphe a un accessibilityLabel avec les valeurs clés."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # Thèmes
    {
        "id": "sf-us-v4-017",
        "feature_id": "sf-f-v4-ux-05",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux passer en mode clair pour travailler dans un environnement lumineux.",
        "acceptance_criteria": (
            "Given: Settings > Apparence / When: sélectionne 'Light' / "
            "Then: thème appliqué immédiatement, tous les contrastes conformes, persisté."
        ),
        "story_points": 3,
        "priority": 5,
    },
    # Offline
    {
        "id": "sf-us-v4-018",
        "feature_id": "sf-f-v4-offline-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir une bannière discrète quand mon instance OVH est hors-ligne.",
        "acceptance_criteria": (
            "Given: instance OVH down / When: app détecte (ping fail) / "
            "Then: bannière jaune 'Instance OVH non joignable — mode lecture' sans bloquer l'UI."
        ),
        "story_points": 2,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-019",
        "feature_id": "sf-f-v4-offline-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux continuer à voir mes données en mode lecture quand offline.",
        "acceptance_criteria": (
            "Given: offline / When: navigue dans backlog / "
            "Then: dernière snapshot visible, indicateur 'données cache HH:MM', boutons écriture grisés."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-020",
        "feature_id": "sf-f-v4-offline-02",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux créer un incident offline et qu'il soit envoyé dès le retour en ligne.",
        "acceptance_criteria": (
            "Given: offline / When: crée incident / "
            "Then: stocké localement, badge '1 en attente', envoyé auto quand online, confirmé."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-021",
        "feature_id": "sf-f-v4-offline-04",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux lancer une session avec Ollama sans aucune connexion réseau.",
        "acceptance_criteria": (
            "Given: WiFi coupé, SF Inside actif, Ollama local running / "
            "When: lance session / Then: session démarre, tokens streamés, aucune erreur réseau."
        ),
        "story_points": 3,
        "priority": 10,
    },
    # Import / Export
    {
        "id": "sf-us-v4-022",
        "feature_id": "sf-f-v4-import-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux exporter tout le backlog en JSON pour le partager avec mon équipe.",
        "acceptance_criteria": (
            "Given: projet avec epics/stories / When: Export > JSON / "
            "Then: fichier sf-backlog-YYYYMMDD.json téléchargé, valide, avec tous les champs."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-023",
        "feature_id": "sf-f-v4-import-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux exporter les sessions d'un projet en Markdown pour documentation.",
        "acceptance_criteria": (
            "Given: projet avec sessions / When: Export > Markdown / "
            "Then: bundle ZIP contenant un .md par session avec messages formatés."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v4-024",
        "feature_id": "sf-f-v4-import-02",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux importer mes issues GitHub en tant que stories SF.",
        "acceptance_criteria": (
            "Given: token GitHub, repo sélectionné / When: Import Issues / "
            "Then: preview 10 premières, mapping labels→priority, import avec lien issue_url."
        ),
        "story_points": 5,
        "priority": 6,
    },
    # API & Webhooks
    {
        "id": "sf-us-v4-025",
        "feature_id": "sf-f-v4-import-03",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux consulter la documentation OpenAPI de SF sur /api/docs.",
        "acceptance_criteria": (
            "Given: SF lancé / When: GET /api/docs / "
            "Then: Swagger UI avec tous les endpoints, auth Bearer, examples."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v4-026",
        "feature_id": "sf-f-v4-import-04",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux créer un webhook pour être notifié quand une mission se termine.",
        "acceptance_criteria": (
            "Given: Settings > Webhooks / When: crée webhook mission.completed + URL / "
            "Then: POST envoyé avec payload signé, log delivery avec status HTTP."
        ),
        "story_points": 3,
        "priority": 5,
    },
    # Cockpit & analytics
    {
        "id": "sf-us-v4-027",
        "feature_id": "sf-f-v4-misc-01",
        "project_id": "software-factory",
        "title": "En tant que DSI, je veux voir le nombre de tokens consommés ce mois par modèle LLM.",
        "acceptance_criteria": (
            "Given: cockpit / When: période = ce mois / "
            "Then: barChart tokens par modèle (GPT-5, Ollama, MiniMax), coût estimé en €."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-028",
        "feature_id": "sf-f-v4-misc-01",
        "project_id": "software-factory",
        "title": "En tant que DSI, je veux voir les métriques DORA (lead time, deploy freq, MTTR, change fail).",
        "acceptance_criteria": (
            "Given: page DORA / When: chargée / "
            "Then: 4 KPI cards avec valeurs + trend vs période précédente, badge Elite/High/Medium/Low."
        ),
        "story_points": 5,
        "priority": 8,
    },
    # Eval
    {
        "id": "sf-us-v4-029",
        "feature_id": "sf-f-v4-misc-02",
        "project_id": "software-factory",
        "title": "En tant que QA Manager, je veux créer un dataset d'évaluation avec 10 cas de test.",
        "acceptance_criteria": (
            "Given: page Évaluations / When: Nouveau dataset > ajoute 10 lignes (input/expected) / "
            "Then: dataset sauvegardé, ID généré, prêt pour un run."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-030",
        "feature_id": "sf-f-v4-misc-02",
        "project_id": "software-factory",
        "title": "En tant que QA Manager, je veux comparer les scores de GPT-5 et Ollama sur le même dataset.",
        "acceptance_criteria": (
            "Given: dataset + 2 modèles sélectionnés / When: Run / "
            "Then: tableau comparatif score/latence/coût, graphe radar, export CSV."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # Runbooks TMA
    {
        "id": "sf-us-v4-031",
        "feature_id": "sf-f-v4-misc-03",
        "project_id": "software-factory",
        "title": "En tant qu'ops, je veux qu'un runbook de diagnostic soit exécuté automatiquement sur un P1.",
        "acceptance_criteria": (
            "Given: runbook 'db-p1-diagnostic' lié à P1 / When: incident P1 créé / "
            "Then: runbook lancé dans les 30s, steps loggés, résultat affiché dans l'incident."
        ),
        "story_points": 3,
        "priority": 8,
    },
    # Audit log
    {
        "id": "sf-us-v4-032",
        "feature_id": "sf-f-v4-misc-04",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux consulter le log d'audit des suppressions.",
        "acceptance_criteria": (
            "Given: page RBAC > Audit Log / When: filtre action=delete / "
            "Then: liste user/action/objet/timestamp, export CSV."
        ),
        "story_points": 2,
        "priority": 8,
    },
    # Idéation scoring
    {
        "id": "sf-us-v4-033",
        "feature_id": "sf-f-v4-misc-05",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir un score d'impact pour chaque idée générée.",
        "acceptance_criteria": (
            "Given: session idéation terminée / When: onglet Scoring / "
            "Then: chaque idée a score feasibility/impact/novelty 0-10, classement automatique."
        ),
        "story_points": 3,
        "priority": 6,
    },
    # Instances health
    {
        "id": "sf-us-v4-034",
        "feature_id": "sf-f-v4-misc-06",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux voir l'état santé de mes 3 instances en un coup d'œil.",
        "acceptance_criteria": (
            "Given: 3 instances (local/OVH/Azure) / When: Settings > Instances / "
            "Then: tableau avec nom/URL/ping ms/statut, refresh auto toutes les 60s."
        ),
        "story_points": 2,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-035",
        "feature_id": "sf-f-v4-misc-06",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux basculer sur l'instance Azure en 1 clic depuis le menu bar.",
        "acceptance_criteria": (
            "Given: menu bar popover / When: tap 'Azure SF' / "
            "Then: instance basculée, sidebar mise à jour, session active transférée, < 1s."
        ),
        "story_points": 2,
        "priority": 9,
    },
    # PIBoard & Sessions
    {
        "id": "sf-us-v4-036",
        "feature_id": "sf-f-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux réordonner les épics dans le PI Board par drag-and-drop.",
        "acceptance_criteria": (
            "Given: PI Board / When: drag epic vers colonne sprint suivant / "
            "Then: epic déplacée, ordre persisté, WSJF recalculé si nécessaire."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-037",
        "feature_id": "sf-f-06",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux exporter l'historique d'une session en PDF.",
        "acceptance_criteria": (
            "Given: session terminée / When: bouton Export > PDF / "
            "Then: PDF généré avec tous les messages, horodaté, nom de l'agent, dans ~/Downloads."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v4-038",
        "feature_id": "sf-f-06",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux relancer une session depuis son historique.",
        "acceptance_criteria": (
            "Given: session archive / When: bouton 'Continuer' / "
            "Then: nouvelle session créée avec mêmes agent + contexte, historique chargé."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-039",
        "feature_id": "sf-f-04",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux créer un agent avec un prompt système personnalisé.",
        "acceptance_criteria": (
            "Given: AgentEdit / When: renseigne 'System Prompt' / "
            "Then: champ markdown, preview live, sauvegardé, utilisé à chaque session."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-040",
        "feature_id": "sf-f-04",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux cloner un agent existant pour en créer une variante.",
        "acceptance_criteria": (
            "Given: AgentDetail / When: bouton 'Cloner' / "
            "Then: nouvel agent créé avec nom 'Copy of X', même config, ID différent."
        ),
        "story_points": 2,
        "priority": 6,
    },
    # Backlog granulaire
    {
        "id": "sf-us-v4-041",
        "feature_id": "sf-f-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux créer une story directement depuis la vue épic.",
        "acceptance_criteria": (
            "Given: EpicDetail > onglet Stories / When: bouton '+' / "
            "Then: form inline avec titre/points/priorité, sauvegardée et affichée immédiatement."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-042",
        "feature_id": "sf-f-01",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux voir le vélocité réelle de l'équipe vs estimé par sprint.",
        "acceptance_criteria": (
            "Given: PI Board / When: sprint terminé / "
            "Then: barre comparée points livrés vs planifiés, taux complétion % par sprint."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-043",
        "feature_id": "sf-f-02",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux voir les skills associées à un agent lors de la création de session.",
        "acceptance_criteria": (
            "Given: NewSession > sélection agent / When: agent sélectionné / "
            "Then: liste compacte des skills actives, tooltip description."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-044",
        "feature_id": "sf-f-14",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir le graphe de compétences d'un agent (spider chart).",
        "acceptance_criteria": (
            "Given: AgentDetail / When: onglet Compétences / "
            "Then: spider/radar chart avec axes skills, valeurs 0-10, comparaison moyenne équipe."
        ),
        "story_points": 5,
        "priority": 6,
    },
    # Patterns & workflows
    {
        "id": "sf-us-v4-045",
        "feature_id": "sf-f-17",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux visualiser le graphe d'exécution d'un pattern avant de le lancer.",
        "acceptance_criteria": (
            "Given: PatternDetail / When: onglet Visualisation / "
            "Then: DAG interactif des étapes, agents assignés, durée estimée, flèches dépendances."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-046",
        "feature_id": "sf-f-17",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux créer un workflow personnalisé en enchaînant 3 patterns.",
        "acceptance_criteria": (
            "Given: Workflows > Nouveau / When: ajoute 3 étapes (patterns) / "
            "Then: workflow sauvegardé, exécutable sur tout projet, log par étape."
        ),
        "story_points": 8,
        "priority": 6,
    },
    # Mémoire
    {
        "id": "sf-us-v4-047",
        "feature_id": "sf-f-19",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux ajouter manuellement une entrée dans la mémoire globale.",
        "acceptance_criteria": (
            "Given: page Mémoire / When: bouton '+' > renseigne clé/valeur/catégorie / "
            "Then: entrée créée, recherchable immédiatement, category tag visible."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-048",
        "feature_id": "sf-f-19",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir la mémoire d'un projet séparément de la mémoire globale.",
        "acceptance_criteria": (
            "Given: ProjectDetail > onglet Mémoire / When: chargé / "
            "Then: entrées scope=project, filtrées par projet, ajout scope auto."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # Onboarding & Settings
    {
        "id": "sf-us-v4-049",
        "feature_id": "sf-f-v3-engine-01",
        "project_id": "software-factory",
        "title": "En tant que nouvel utilisateur macOS, je veux que l'onboarding détecte automatiquement Ollama.",
        "acceptance_criteria": (
            "Given: Ollama installé et actif / When: étape LLM onboarding / "
            "Then: 'Ollama détecté ✓' + liste modèles, sélection en 1 clic, pas de saisie manuelle."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-050",
        "feature_id": "sf-f-v3-engine-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux que SF Inside redémarre automatiquement le moteur après un crash.",
        "acceptance_criteria": (
            "Given: sf-engine crash / When: SFEngineManager détecte (process nil) / "
            "Then: redémarrage auto dans 5s, dot orange pendant, vert quand prêt, notification."
        ),
        "story_points": 3,
        "priority": 8,
    },
    # Org SAFe
    {
        "id": "sf-us-v4-051",
        "feature_id": "sf-f-27",
        "project_id": "software-factory",
        "title": "En tant que DSI, je veux voir le budget consommé vs alloué par ART dans le Portfolio.",
        "acceptance_criteria": (
            "Given: Portfolio view / When: section Budget / "
            "Then: barre progress par ART, montant €, % consommé, alerte si > 90%."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-052",
        "feature_id": "sf-f-27",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux voir le taux d'utilisation de chaque équipe dans l'ART.",
        "acceptance_criteria": (
            "Given: ARTDetail / When: onglet Capacité / "
            "Then: tableau équipes avec nb agents/WIP/capacité max, alertes surcharge rouge."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # TMA
    {
        "id": "sf-us-v4-053",
        "feature_id": "sf-f-v3-tma-02",
        "project_id": "software-factory",
        "title": "En tant qu'ops, je veux voir un chrono SLA en temps réel sur chaque incident ouvert.",
        "acceptance_criteria": (
            "Given: liste incidents / When: incident P2 ouvert depuis 3h / "
            "Then: chrono rouge décompte vers 0, P2 SLA = 4h, badge 'SLA restant: 1h'."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v4-054",
        "feature_id": "sf-f-v3-tma-02",
        "project_id": "software-factory",
        "title": "En tant qu'ops, je veux assigner un incident à un agent SF pour diagnostic automatique.",
        "acceptance_criteria": (
            "Given: IncidentDetail / When: Assigner > choisit 'Karim Diallo (devops)' / "
            "Then: session créée avec l'agent, contexte incident injecté, rapport généré < 5 min."
        ),
        "story_points": 5,
        "priority": 8,
    },
    # Evolution / Mercato
    {
        "id": "sf-us-v4-055",
        "feature_id": "sf-f-v3-mercato-01",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux voir le score Thompson Sampling de chaque agent sur 30 jours.",
        "acceptance_criteria": (
            "Given: Mercato / When: onglet Thompson Sampling / "
            "Then: tableau agents, colonnes: succès/echecs/score TS, tri par score, export CSV."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v4-056",
        "feature_id": "sf-f-v3-mercato-01",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux qu'une mutation Darwin soit proposée quand un agent est sous les 40%.",
        "acceptance_criteria": (
            "Given: agent fitness < 40% sur 10 runs / When: cycle évolution / "
            "Then: proposition mutation dans EvolutionView, diff prompt montré, validation requise."
        ),
        "story_points": 5,
        "priority": 7,
    },
    # Projects
    {
        "id": "sf-us-v4-057",
        "feature_id": "sf-f-09",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux archiver un projet terminé sans le supprimer.",
        "acceptance_criteria": (
            "Given: ProjectDetail / When: Archive / "
            "Then: status=archived, non visible par défaut, filtre 'Afficher archivés' le montre."
        ),
        "story_points": 2,
        "priority": 6,
    },
    {
        "id": "sf-us-v4-058",
        "feature_id": "sf-f-09",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux ajouter un README Markdown à un projet.",
        "acceptance_criteria": (
            "Given: ProjectDetail > onglet Readme / When: édite + sauvegarde / "
            "Then: Markdown rendu, modifiable par lead+, versionné."
        ),
        "story_points": 3,
        "priority": 6,
    },
    # Skill & Tools
    {
        "id": "sf-us-v4-059",
        "feature_id": "sf-f-v3-toolbox-01",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux tester un outil MCP directement depuis la Toolbox.",
        "acceptance_criteria": (
            "Given: MCPs > outil sélectionné / When: 'Tester' > saisit input / "
            "Then: appel exécuté, réponse JSON affichée, latence ms, status code."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v4-060",
        "feature_id": "sf-f-v3-toolbox-01",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux créer un outil custom avec schéma JSON via le Tool Builder.",
        "acceptance_criteria": (
            "Given: Tool Builder / When: renseigne nom/description/input schema (JSON) / "
            "Then: outil créé, assignable à agents, schéma validé JSONSchema draft-7."
        ),
        "story_points": 5,
        "priority": 7,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# V5 — Observabilité · RBAC · Git · CI/CD · Darwin · Knowledge · Notifs · i18n
# ─────────────────────────────────────────────────────────────────────────────

SF_PERSONAS_V5: list[dict] = [
    {
        "id": "sf-p-12",
        "name": "Ingénieur DevOps",
        "role": "devops_engineer",
        "project_id": "software-factory",
        "description": "Responsable de l'infrastructure CI/CD, de la supervision et du déploiement continu.",
        "goals": "Déployer en continu sans régressions, observer les métriques DORA, automatiser les pipelines.",
        "pain_points": "Logs dispersés, absence de traçabilité des déploiements, alertes trop nombreuses.",
        "tools": ["GitHub Actions", "GitLab CI", "Prometheus", "Grafana", "Datadog"],
    },
    {
        "id": "sf-p-13",
        "name": "Responsable Sécurité & Conformité",
        "role": "security_officer",
        "project_id": "software-factory",
        "description": "Gère les droits d'accès, les politiques de sécurité et la conformité réglementaire.",
        "goals": "Contrôler les accès au moindre privilège, auditer toutes les actions, garantir la conformité.",
        "pain_points": "Gestion des rôles trop grossière, pas d'audit trail centralisé, SSO fragmenté.",
        "tools": ["RBAC manager", "audit log", "SSO/LDAP", "policy engine"],
    },
]

SF_EPICS_V5: list[dict] = [
    {
        "id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Observabilité & DORA Metrics",
        "status": "planned",
        "wsjf": 42,
        "description": "Tableau de bord DORA en temps réel, logs et traces centralisés, alertes intelligentes, export métriques Prometheus/CSV.",
        "business_value": 10,
        "time_criticality": 8,
        "risk_reduction": 9,
        "job_size": 5,
    },
    {
        "id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "RBAC Fine-Grained & Teams",
        "status": "planned",
        "wsjf": 38,
        "description": "Contrôle d'accès granulaire par rôle, gestion des équipes, audit trail, SSO/LDAP, politiques de sécurité par projet.",
        "business_value": 9,
        "time_criticality": 7,
        "risk_reduction": 10,
        "job_size": 6,
    },
    {
        "id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Git & CI/CD Pipelines",
        "status": "planned",
        "wsjf": 36,
        "description": "Vue branches/PRs intégrée, diff viewer, pipelines GitHub Actions et GitLab CI, quality gates, webhooks Git entrants.",
        "business_value": 9,
        "time_criticality": 8,
        "risk_reduction": 7,
        "job_size": 6,
    },
    {
        "id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Darwin Teams & Agent Marketplace",
        "status": "planned",
        "wsjf": 33,
        "description": "Fitness scoring, spéciation, mutation automatique de prompts, marketplace agents, pools élastiques et généalogie.",
        "business_value": 8,
        "time_criticality": 6,
        "risk_reduction": 7,
        "job_size": 6,
    },
    {
        "id": "sf-e-v5-kb",
        "project_id": "software-factory",
        "title": "Knowledge Base & i18n",
        "status": "planned",
        "wsjf": 28,
        "description": "Wiki structuré par projet, templates (ADR/runbook/postmortem), internationalisation FR/EN/ZH, export PDF/DOCX.",
        "business_value": 7,
        "time_criticality": 5,
        "risk_reduction": 6,
        "job_size": 5,
    },
    {
        "id": "sf-e-v5-notif",
        "project_id": "software-factory",
        "title": "Notifications & Webhooks",
        "status": "planned",
        "wsjf": 30,
        "description": "Centre de notifications in-app, webhooks sortants configurables, intégrations Slack/Teams/Email, digest quotidien/hebdomadaire.",
        "business_value": 8,
        "time_criticality": 6,
        "risk_reduction": 6,
        "job_size": 5,
    },
]

SF_FEATURES_V5: list[dict] = [
    # ── Observabilité & DORA ──
    {
        "id": "sf-f-v5-obs-01",
        "epic_id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Dashboard DORA temps réel",
        "description": "Tableau de bord affichant les 4 métriques DORA (Lead Time for Changes, Deployment Frequency, MTTR, Change Failure Rate) mis à jour en temps réel avec benchmarks industry.",
        "acceptance_criteria": "4 widgets DORA · Graphes 7j/30j/90j · Tendance flèche · Benchmark élite/high/medium/low · Drill-down par projet",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-f-v5-obs-02",
        "epic_id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Logs centralisés et traces distribuées",
        "description": "Agrégation des logs de toutes les sessions et services SF avec corrélation de traces par trace_id pour le diagnostic d'incidents.",
        "acceptance_criteria": "Logs filtrables level/service/agent · Traces corrélées par trace_id · Vue waterfall spans · Rétention 30j · Export JSON/CSV",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-obs-03",
        "epic_id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Alertes et seuils de performance",
        "description": "Définition de seuils d'alerte sur les métriques clés (latence LLM, taux d'erreur, taux déploiement) avec notifications et acquittement.",
        "acceptance_criteria": "Seuils éditables par métrique · Notification in-app + webhook · Historique alertes 90j · ACK avec commentaire · Sévérité 4 niveaux",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-obs-04",
        "epic_id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Health dashboard multi-services",
        "description": "Vue synthétique de la santé de tous les services SF (API, DB, Redis, LLM providers) avec uptime historique et latences percentiles.",
        "acceptance_criteria": "Statut vert/orange/rouge par service · Uptime % 24h/7j/30j · Latence p50/p95/p99 · Historique incidents · Auto-refresh 30s",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-obs-05",
        "epic_id": "sf-e-v5-obs",
        "project_id": "software-factory",
        "title": "Export métriques Prometheus / CSV",
        "description": "Endpoint /metrics compatible Prometheus pour scraping Grafana, et export CSV des métriques DORA sur une période donnée.",
        "acceptance_criteria": "Endpoint /metrics format Prometheus · Scrape interval 15s · Métriques sf_* préfixées · Export CSV date range · Encodage UTF-8",
        "story_points": 3,
        "priority": 7,
    },
    # ── RBAC Fine-Grained ──
    {
        "id": "sf-f-v5-rbac-01",
        "epic_id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "Gestion des rôles et permissions granulaires",
        "description": "Définition de rôles personnalisés avec permissions fines (lecture/écriture/suppression/exécution) sur chaque type de ressource SF par projet.",
        "acceptance_criteria": "Rôles CRUD UI · Matrice ressource×action · Héritage de rôles · Preview droits utilisateur · Export politique JSON",
        "story_points": 8,
        "priority": 10,
    },
    {
        "id": "sf-f-v5-rbac-02",
        "epic_id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "Teams et groupes d'agents / utilisateurs",
        "description": "Création d'équipes regroupant agents et utilisateurs humains avec affectation de rôles et statistiques d'activité agrégées.",
        "acceptance_criteria": "Team CRUD · Ajout agents + humains · Rôle par team · Statistiques activité · Comparaison sprints",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-rbac-03",
        "epic_id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "Audit trail des accès et modifications",
        "description": "Journal d'audit centralisé de toutes les actions sensibles (création/modification/suppression/connexion) avec recherche, filtres et export.",
        "acceptance_criteria": "Log who/what/when/IP · Filtrable user/ressource/action · Rétention configurable · Export CSV · Alertes accès suspects hors heures",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-rbac-04",
        "epic_id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "SSO / LDAP integration",
        "description": "Authentification centralisée via SAML 2.0 / OIDC et synchronisation d'annuaire LDAP/Active Directory pour la gestion des identités.",
        "acceptance_criteria": "Config SAML/OIDC UI · Test connexion · Mapping attributs LDAP → rôles SF · Session SSO 8h · Sync groupes nightly · Fallback local",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-rbac-05",
        "epic_id": "sf-e-v5-rbac",
        "project_id": "software-factory",
        "title": "Politique de sécurité par projet",
        "description": "Configuration de politiques par projet : IP whitelist, MFA obligatoire, expiration de session, restriction des providers LLM autorisés.",
        "acceptance_criteria": "Politique JSON par projet · IP whitelist/blacklist · MFA toggle · Expiration session configurable · LLM providers autorisés",
        "story_points": 5,
        "priority": 8,
    },
    # ── Git & CI/CD ──
    {
        "id": "sf-f-v5-git-01",
        "epic_id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Vue branches et PRs intégrée",
        "description": "Affichage des branches et pull requests Git directement dans SF avec statut CI, auteur, reviewers et déclenchement de sessions d'analyse.",
        "acceptance_criteria": "Liste branches ahead/behind · PRs avec labels/CI status · Filtre auteur/statut · Créer session depuis PR · Pagination",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-git-02",
        "epic_id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Diff viewer et code review inline",
        "description": "Visualisation des diffs de commits et PRs avec syntaxe colorée, navigation fichier par fichier et commentaires inline.",
        "acceptance_criteria": "Diff side-by-side ou unified · Syntax highlighting 20+ langages · Commentaires inline · Stats ajouts/suppressions · Navigation fichiers",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-git-03",
        "epic_id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Pipelines GitHub Actions / GitLab CI",
        "description": "Déclenchement, suivi et historique des pipelines CI/CD GitHub Actions et GitLab CI depuis SF avec logs en streaming.",
        "acceptance_criteria": "Liste pipelines avec statut · Trigger manuel · Logs streaming SSE · Historique 90j · Statuts pending/running/success/failure",
        "story_points": 8,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-git-04",
        "epic_id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Quality gates et status checks",
        "description": "Définition de quality gates (tests pass rate, coverage, adversarial score) bloquant les PRs si non respectés, avec override justifié.",
        "acceptance_criteria": "Gates configurables par projet · Blocage PR si KO · Badge statut · Override avec justification · Log override dans audit trail",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-git-05",
        "epic_id": "sf-e-v5-git",
        "project_id": "software-factory",
        "title": "Déclenchement d'actions SF depuis événements Git",
        "description": "Webhooks Git entrants (push, PR opened, tag) déclenchant automatiquement des sessions SF, patterns ou workflows configurés.",
        "acceptance_criteria": "Webhook receiver configuré · Mapping event → action SF · Log historique webhooks · Retry automatique · Filtre branches/tags",
        "story_points": 5,
        "priority": 8,
    },
    # ── Darwin Teams & Marketplace ──
    {
        "id": "sf-f-v5-darwin-01",
        "epic_id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Fitness scoring et spéciation d'agents",
        "description": "Calcul du score de fitness multi-critères (qualité output, vitesse, taux succès, feedback utilisateur) et regroupement des agents en espèces.",
        "acceptance_criteria": "Score fitness 0-100 · Composantes pondérées configurables · Historique 50 évaluations · Graphe évolution · Seuil spéciation configurable",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-darwin-02",
        "epic_id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Mutation automatique de prompts",
        "description": "Système de mutation des prompts d'agents basé sur les performances, avec diff visuel, A/B test automatique et validation humaine.",
        "acceptance_criteria": "Mutation proposée si fitness < seuil · Diff prompt avant/après · Validation lead requise · A/B test 50/50 20 runs · Rollback 1 clic",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-darwin-03",
        "epic_id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Marketplace agents (publication et installation)",
        "description": "Publication d'agents SF dans un catalogue partagé avec versioning semver, ratings, recherche et installation en 1 clic dans un projet.",
        "acceptance_criteria": "Publish agent → catalogue · Version semver · Rating 1-5 étoiles · Install 1 clic · Fork agent · Recherche par rôle/tag/auteur",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v5-darwin-04",
        "epic_id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Généalogie et arbre évolutif",
        "description": "Visualisation de l'arbre généalogique des agents (clones, mutations, croisements) avec historique de versions et restauration d'ancêtre.",
        "acceptance_criteria": "Arbre D3.js interactif · Nœuds colorés par espèce · Score fitness visible · Diff ancêtre/descendant · Restauration 1 clic · Export SVG",
        "story_points": 5,
        "priority": 6,
    },
    {
        "id": "sf-f-v5-darwin-05",
        "epic_id": "sf-e-v5-darwin",
        "project_id": "software-factory",
        "title": "Agent pools élastiques",
        "description": "Gestion de pools d'agents homogènes avec auto-scaling selon la charge, file d'attente des tâches et métriques d'utilisation.",
        "acceptance_criteria": "Pool CRUD · Taille min/max configurable · Scale up/down auto · File d'attente visible · Métriques throughput · Historique charge",
        "story_points": 8,
        "priority": 7,
    },
    # ── Knowledge Base & i18n ──
    {
        "id": "sf-f-v5-kb-01",
        "epic_id": "sf-e-v5-kb",
        "project_id": "software-factory",
        "title": "Wiki structuré par projet avec pages et catégories",
        "description": "Création et organisation de pages wiki avec hiérarchie de catégories, éditeur Markdown enrichi, liens [[wiki]] et versioning.",
        "acceptance_criteria": "Éditeur Markdown + preview temps réel · Catégories hiérarchiques · Recherche FTS · Versioning pages · Liens [[page]] · Export PDF",
        "story_points": 8,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-kb-02",
        "epic_id": "sf-e-v5-kb",
        "project_id": "software-factory",
        "title": "Templates de pages et modèles de runbooks",
        "description": "Bibliothèque de templates pour pages wiki : ADR, runbook, postmortem, onboarding — avec variables substituables et aperçu.",
        "acceptance_criteria": "8+ templates prédéfinis · Variables {{variable}} substituées · Template custom CRUD · Aperçu avant création · Stats usage",
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-f-v5-kb-03",
        "epic_id": "sf-e-v5-kb",
        "project_id": "software-factory",
        "title": "Internationalisation FR / EN / ZH",
        "description": "Interface complète de SF disponible en français, anglais et chinois mandarin avec switch de langue persistant et formats localisés.",
        "acceptance_criteria": "Switch langue header · 3 locales: fr/en/zh · Toutes les chaînes UI traduites · Formats date/nombre locale · Architecture RTL-ready",
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-f-v5-kb-04",
        "epic_id": "sf-e-v5-kb",
        "project_id": "software-factory",
        "title": "Export PDF / DOCX et impression",
        "description": "Export des pages wiki, rapports de sprint et sessions en PDF ou DOCX avec mise en forme professionnelle et table des matières.",
        "acceptance_criteria": "Export PDF wiki · Export DOCX rapport sprint · Logo + en-tête · Table des matières auto · Code blocks avec syntax · CSS @media print",
        "story_points": 5,
        "priority": 6,
    },
    # ── Notifications & Webhooks ──
    {
        "id": "sf-f-v5-notif-01",
        "epic_id": "sf-e-v5-notif",
        "project_id": "software-factory",
        "title": "Centre de notifications in-app",
        "description": "Panneau de notifications centralisé avec catégorisation (incidents, CI, évolution, mentions), filtres et marquage lu/non-lu.",
        "acceptance_criteria": "Cloche avec badge compteur · Panneau slide-in · Catégories filtrables · Marquer tout lu · Notifs cliquables → ressource · Persistence DB",
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-f-v5-notif-02",
        "epic_id": "sf-e-v5-notif",
        "project_id": "software-factory",
        "title": "Webhooks sortants configurables",
        "description": "Configuration de webhooks sur les événements SF (session terminée, incident créé, déploiement, alerte) vers des URLs tierces avec signature HMAC.",
        "acceptance_criteria": "Webhook CRUD URL + events · Payload JSON configurable · Test manuel · Historique livraisons · Retry 3x · Signature HMAC-SHA256",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-notif-03",
        "epic_id": "sf-e-v5-notif",
        "project_id": "software-factory",
        "title": "Intégrations Slack / Teams / Email",
        "description": "Envoi de notifications vers Slack, Microsoft Teams et email avec templates de messages contextuels par événement et test d'envoi.",
        "acceptance_criteria": "Config Slack OAuth · Config Teams webhook · Config SMTP email · Templates Jinja2 par event · Test envoi · Preview message",
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-f-v5-notif-04",
        "epic_id": "sf-e-v5-notif",
        "project_id": "software-factory",
        "title": "Digest quotidien / hebdomadaire",
        "description": "Résumé automatique des activités SF (sessions, déploiements, incidents, métriques DORA) envoyé par email ou Slack selon préférence utilisateur.",
        "acceptance_criteria": "Digest daily/weekly configurable · Contenu: sessions/CI/incidents/DORA · Désactivable par projet · Heure envoi configurable · Lien rapport",
        "story_points": 3,
        "priority": 7,
    },
]

SF_STORIES_V5: list[dict] = [
    # ── Observabilité & DORA ──
    {
        "id": "sf-us-v5-001",
        "feature_id": "sf-f-v5-obs-01",
        "project_id": "software-factory",
        "title": "En tant qu'ingénieur DevOps, je veux voir les 4 métriques DORA sur un seul tableau de bord pour piloter la performance de livraison.",
        "acceptance_criteria": (
            "Given: page Observabilité / When: chargée / "
            "Then: 4 widgets DORA avec valeurs actuelles, tendances 7j, benchmark industry (elite/high/medium/low)."
        ),
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-v5-002",
        "feature_id": "sf-f-v5-obs-01",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux filtrer les métriques DORA par projet pour comparer les équipes.",
        "acceptance_criteria": (
            "Given: dashboard DORA / When: sélectionne projet 'backend' / "
            "Then: métriques recalculées pour ce projet, comparaison avec moyenne globale visible."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-003",
        "feature_id": "sf-f-v5-obs-01",
        "project_id": "software-factory",
        "title": "En tant que tech lead, je veux voir l'historique du Lead Time for Changes sur 90 jours pour identifier les tendances.",
        "acceptance_criteria": (
            "Given: DORA dashboard / When: sélectionne métrique 'Lead Time' + 90j / "
            "Then: graphe ligne avec valeurs quotidiennes, ligne tendance, annotation des déploiements majeurs."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-004",
        "feature_id": "sf-f-v5-obs-02",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux chercher des logs par niveau et service pour diagnostiquer un incident rapidement.",
        "acceptance_criteria": (
            "Given: page Logs / When: filtre ERROR + service=llm-client / "
            "Then: logs filtrés < 300ms, timestamps, trace_id, agent_id visibles, export 1000 lignes max."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-005",
        "feature_id": "sf-f-v5-obs-02",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux corréler une trace distribuée pour suivre une requête de bout en bout.",
        "acceptance_criteria": (
            "Given: log avec trace_id / When: clic sur trace_id / "
            "Then: vue waterfall des spans, durée par service, erreurs marquées rouge, export JSON."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-006",
        "feature_id": "sf-f-v5-obs-03",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux configurer un seuil d'alerte sur la latence LLM pour être notifié si elle dépasse 5 secondes.",
        "acceptance_criteria": (
            "Given: Alertes > Nouveau seuil / When: métrique=latence_llm, condition > 5000ms / "
            "Then: alerte créée, notification déclenchée dans < 60s si dépassement, log alerte."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-007",
        "feature_id": "sf-f-v5-obs-03",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux acquitter une alerte pour indiquer qu'elle est prise en charge.",
        "acceptance_criteria": (
            "Given: alerte active / When: bouton ACK + commentaire / "
            "Then: statut = acknowledged, commentaire visible, notif silencée 4h, badge alertes décrémenté."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-008",
        "feature_id": "sf-f-v5-obs-04",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir le statut de santé de tous les services SF en un coup d'œil.",
        "acceptance_criteria": (
            "Given: page Health / When: chargée / "
            "Then: grid services (API, DB, Redis, LLM×3), badge vert/orange/rouge, uptime 24h, latence p95."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-009",
        "feature_id": "sf-f-v5-obs-04",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir l'historique des incidents de santé pour analyser les patterns de pannes.",
        "acceptance_criteria": (
            "Given: Health dashboard / When: clic 'Historique' / "
            "Then: liste incidents classés par date, durée, services affectés, lien RCA si renseigné."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-010",
        "feature_id": "sf-f-v5-obs-05",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux scraper les métriques SF depuis Prometheus pour les afficher dans Grafana.",
        "acceptance_criteria": (
            "Given: Prometheus configuré scrape target /metrics SF / When: scrape toutes 15s / "
            "Then: métriques disponibles: sf_sessions_total, sf_llm_latency_seconds, sf_errors_total."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-011",
        "feature_id": "sf-f-v5-obs-05",
        "project_id": "software-factory",
        "title": "En tant que manager, je veux exporter les métriques DORA en CSV sur une période donnée pour un rapport.",
        "acceptance_criteria": (
            "Given: DORA dashboard / When: Export CSV + date range 3 mois / "
            "Then: CSV téléchargé avec colonnes date/metric/value/project, encodage UTF-8."
        ),
        "story_points": 2,
        "priority": 7,
    },
    # ── RBAC Fine-Grained ──
    {
        "id": "sf-us-v5-012",
        "feature_id": "sf-f-v5-rbac-01",
        "project_id": "software-factory",
        "title": "En tant que responsable sécurité, je veux créer un rôle 'observateur' avec droits lecture seule pour limiter les risques.",
        "acceptance_criteria": (
            "Given: Settings > Rôles > Nouveau / When: crée rôle 'observateur' avec permissions read-only / "
            "Then: rôle sauvegardé, assignable, aucune action write visible pour cet utilisateur."
        ),
        "story_points": 5,
        "priority": 10,
    },
    {
        "id": "sf-us-v5-013",
        "feature_id": "sf-f-v5-rbac-01",
        "project_id": "software-factory",
        "title": "En tant que responsable sécurité, je veux voir la matrice de permissions d'un utilisateur pour valider ses droits.",
        "acceptance_criteria": (
            "Given: UserDetail > onglet Permissions / When: chargé / "
            "Then: matrice ressource×action avec ✓/✗, héritage rôle visible, rôles cumulés affichés."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-014",
        "feature_id": "sf-f-v5-rbac-01",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux exporter la politique RBAC complète en JSON pour audit et versioning Git.",
        "acceptance_criteria": (
            "Given: Settings > RBAC / When: Export JSON / "
            "Then: fichier rbac-policy-{date}.json téléchargé, format importable, SHA256 affiché."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-015",
        "feature_id": "sf-f-v5-rbac-02",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux créer une team 'frontend' regroupant des agents et des développeurs pour piloter leur activité.",
        "acceptance_criteria": (
            "Given: Teams > Nouvelle team / When: ajoute membres agents + humains, rôle team-lead / "
            "Then: team créée, membres visibles, statistiques activité agrégées (sessions, points livrés)."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-016",
        "feature_id": "sf-f-v5-rbac-02",
        "project_id": "software-factory",
        "title": "En tant que manager, je veux voir le taux d'activité d'une team sur 30 jours pour évaluer la charge de travail.",
        "acceptance_criteria": (
            "Given: TeamDetail / When: onglet Activité / "
            "Then: graphe sessions/jour, points livrés cumulés, répartition agents top-3, comparaison sprint précédent."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-017",
        "feature_id": "sf-f-v5-rbac-03",
        "project_id": "software-factory",
        "title": "En tant que responsable sécurité, je veux consulter le journal d'audit de toutes les actions sur un agent.",
        "acceptance_criteria": (
            "Given: AgentDetail > Audit Log / When: chargé / "
            "Then: liste chronologique who/what/when/IP, filtrable par date et action, export CSV."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-018",
        "feature_id": "sf-f-v5-rbac-03",
        "project_id": "software-factory",
        "title": "En tant que responsable sécurité, je veux recevoir une alerte quand un accès admin est effectué hors des heures ouvrées.",
        "acceptance_criteria": (
            "Given: audit trail actif / When: action admin entre 22h-8h ou week-end / "
            "Then: alerte sécurité créée, notification email + in-app, enrichie avec IP et user-agent."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-019",
        "feature_id": "sf-f-v5-rbac-04",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux configurer une connexion SSO OIDC pour que les utilisateurs se connectent avec leur compte entreprise.",
        "acceptance_criteria": (
            "Given: Settings > SSO / When: config OIDC (client_id, secret, discovery URL) / "
            "Then: bouton 'Connexion SSO' sur login, test connexion OK, mapping email → rôle SF auto."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-020",
        "feature_id": "sf-f-v5-rbac-04",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux synchroniser les groupes LDAP avec les teams SF pour éviter la gestion manuelle des accès.",
        "acceptance_criteria": (
            "Given: LDAP configuré / When: sync manuelle ou cron nightly / "
            "Then: groupes LDAP → teams SF, membres ajoutés/retirés, log sync avec diff affiché."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-021",
        "feature_id": "sf-f-v5-rbac-05",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux forcer le MFA pour tous les utilisateurs d'un projet critique.",
        "acceptance_criteria": (
            "Given: ProjectSettings > Sécurité / When: MFA = obligatoire / "
            "Then: utilisateurs sans MFA invités à l'activer, accès bloqué sinon, log tentatives."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-022",
        "feature_id": "sf-f-v5-rbac-05",
        "project_id": "software-factory",
        "title": "En tant que responsable sécurité, je veux restreindre les providers LLM autorisés sur un projet pour éviter les fuites de données.",
        "acceptance_criteria": (
            "Given: ProjectSettings > LLM Policy / When: liste autorisée = [azure-openai] / "
            "Then: sessions du projet n'utilisent que azure-openai, appels autres providers bloqués + log."
        ),
        "story_points": 3,
        "priority": 9,
    },
    # ── Git & CI/CD ──
    {
        "id": "sf-us-v5-023",
        "feature_id": "sf-f-v5-git-01",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux voir la liste des branches Git d'un projet directement dans SF pour prioriser mes revues.",
        "acceptance_criteria": (
            "Given: ProjectDetail > onglet Git / When: chargé / "
            "Then: liste branches avec auteur, date, nb commits ahead/behind main, statut CI badge."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-024",
        "feature_id": "sf-f-v5-git-01",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux voir les PRs ouvertes avec leurs reviewers et status checks pour prioriser mes reviews.",
        "acceptance_criteria": (
            "Given: Git > PRs / When: chargé / "
            "Then: liste PRs titre/auteur/reviewers/labels/CI status, filtre branche cible, tri par date."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-025",
        "feature_id": "sf-f-v5-git-01",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux créer une session SF à partir d'une PR pour qu'un agent fasse la code review automatiquement.",
        "acceptance_criteria": (
            "Given: PRDetail / When: bouton 'Analyser avec SF' / "
            "Then: session créée avec diff PR en contexte, agent reviewer assigné, rapport généré et lié à la PR."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-026",
        "feature_id": "sf-f-v5-git-02",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux visualiser le diff d'un commit avec coloration syntaxique pour une review rapide.",
        "acceptance_criteria": (
            "Given: commit sélectionné / When: onglet Diff / "
            "Then: diff unifié ou side-by-side, syntax highlighting, stats +/- lignes, navigation fichiers."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-027",
        "feature_id": "sf-f-v5-git-02",
        "project_id": "software-factory",
        "title": "En tant que reviewer, je veux ajouter un commentaire inline sur une ligne du diff pour annoter ma review.",
        "acceptance_criteria": (
            "Given: diff viewer / When: clic ligne + saisie commentaire / "
            "Then: commentaire sauvegardé avec auteur/date, visible sur la PR via API GitHub/GitLab."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-028",
        "feature_id": "sf-f-v5-git-03",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir l'état de tous les pipelines CI/CD en cours en temps réel pour détecter les blocages.",
        "acceptance_criteria": (
            "Given: page Pipelines / When: chargée / "
            "Then: liste pipelines avec statut (running/success/failed), durée, branche, acteur, refresh 10s."
        ),
        "story_points": 5,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-029",
        "feature_id": "sf-f-v5-git-03",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux déclencher manuellement un pipeline CI depuis SF sans aller sur GitHub.",
        "acceptance_criteria": (
            "Given: PipelineList / When: bouton 'Déclencher' + sélection branche / "
            "Then: pipeline lancé via API GitHub/GitLab, statut mis à jour, lien vers le run affiché."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-030",
        "feature_id": "sf-f-v5-git-03",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir les logs d'un job CI en streaming pour suivre un déploiement en direct.",
        "acceptance_criteria": (
            "Given: job en running / When: clic 'Logs' / "
            "Then: logs affichés en streaming SSE, ANSI colors rendus, scroll auto bas, téléchargement brut."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-031",
        "feature_id": "sf-f-v5-git-04",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux définir un quality gate 'couverture tests > 80%' bloquant les PRs pour garantir la qualité.",
        "acceptance_criteria": (
            "Given: ProjectSettings > Quality Gates / When: règle coverage > 80% / "
            "Then: PRs avec coverage < 80% bloquées, badge rouge sur PR, message explicatif affiché."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-032",
        "feature_id": "sf-f-v5-git-04",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux bypasser un quality gate avec justification pour débloquer un hotfix urgent.",
        "acceptance_criteria": (
            "Given: PR bloquée par quality gate / When: Override + justification / "
            "Then: override enregistré dans audit log, notif responsable sécurité, PR débloquée."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-033",
        "feature_id": "sf-f-v5-git-05",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux qu'une PR ouverte sur main déclenche automatiquement un pattern 'Code Review' dans SF.",
        "acceptance_criteria": (
            "Given: webhook GitHub PR opened configuré / When: PR ouverte sur main / "
            "Then: session SF créée avec pattern code-review, agent assigné, lien session posté commentaire PR."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-034",
        "feature_id": "sf-f-v5-git-05",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir l'historique des webhooks reçus pour diagnostiquer les intégrations Git.",
        "acceptance_criteria": (
            "Given: Settings > Webhooks entrants / When: liste / "
            "Then: 100 derniers événements, payload JSON consultable, statut traitement, retry si erreur."
        ),
        "story_points": 2,
        "priority": 7,
    },
    # ── Darwin Teams & Marketplace ──
    {
        "id": "sf-us-v5-035",
        "feature_id": "sf-f-v5-darwin-01",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux voir le score de fitness de chaque agent avec ses composantes pour comprendre ses forces et faiblesses.",
        "acceptance_criteria": (
            "Given: Darwin > Fitness / When: agent sélectionné / "
            "Then: score global 0-100, décomposé en qualité/vitesse/succès/feedback, graphe radar."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-036",
        "feature_id": "sf-f-v5-darwin-01",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux voir les agents regroupés en espèces selon leur profil de compétences pour optimiser les équipes.",
        "acceptance_criteria": (
            "Given: Darwin > Spéciation / When: chargé / "
            "Then: clusters visuels d'agents, label espèce auto-généré, nb agents/espèce, fitness moyenne."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-037",
        "feature_id": "sf-f-v5-darwin-01",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux configurer les poids de fitness pour prioriser la vitesse sur mon projet urgent.",
        "acceptance_criteria": (
            "Given: ProjectSettings > Fitness Weights / When: poids vitesse = 0.5, qualité = 0.3 / "
            "Then: scores recalculés immédiatement, preview impact sur classement agents visible."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-038",
        "feature_id": "sf-f-v5-darwin-02",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux qu'une mutation de prompt soit proposée quand un agent a un fitness < 40% sur 10 runs consécutifs.",
        "acceptance_criteria": (
            "Given: agent fitness < 40% sur 10 runs / When: cycle évolution nightly / "
            "Then: proposition mutation dans Evolution View, diff prompt montré, validation lead requise."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-039",
        "feature_id": "sf-f-v5-darwin-02",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux comparer la performance d'un agent avant et après mutation sur un A/B test pour valider l'amélioration.",
        "acceptance_criteria": (
            "Given: mutation appliquée / When: A/B test activé / "
            "Then: 50% runs → version A, 50% → version B, résultats comparés, winner appliqué auto après 20 runs."
        ),
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-040",
        "feature_id": "sf-f-v5-darwin-03",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux publier un agent SF dans le marketplace pour partager mes solutions avec d'autres équipes.",
        "acceptance_criteria": (
            "Given: AgentDetail / When: Publier > renseigne description/tags/version / "
            "Then: agent visible dans marketplace, version semver, statut 'pending review' puis 'published'."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-041",
        "feature_id": "sf-f-v5-darwin-03",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux installer un agent du marketplace en 1 clic dans mon projet pour accélérer le démarrage.",
        "acceptance_criteria": (
            "Given: Marketplace > agent sélectionné / When: Installer / "
            "Then: agent cloné dans projet, ID unique, prompt original conservé, skills importées."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-042",
        "feature_id": "sf-f-v5-darwin-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux noter un agent du marketplace pour aider la communauté à choisir les meilleurs agents.",
        "acceptance_criteria": (
            "Given: Marketplace > agent installé et utilisé / When: note 1-5 étoiles + commentaire / "
            "Then: note enregistrée, moyenne mise à jour, commentaire visible, 1 note max par utilisateur."
        ),
        "story_points": 2,
        "priority": 6,
    },
    {
        "id": "sf-us-v5-043",
        "feature_id": "sf-f-v5-darwin-04",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux visualiser l'arbre généalogique d'un agent pour comprendre son historique évolutif.",
        "acceptance_criteria": (
            "Given: AgentDetail > Généalogie / When: chargé / "
            "Then: arbre D3.js interactif, nœuds colorés par espèce, score fitness par nœud, survol = diff prompt."
        ),
        "story_points": 5,
        "priority": 6,
    },
    {
        "id": "sf-us-v5-044",
        "feature_id": "sf-f-v5-darwin-04",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux restaurer une version ancestrale d'un agent si une mutation a dégradé ses performances.",
        "acceptance_criteria": (
            "Given: arbre généalogique / When: nœud ancêtre sélectionné > Restaurer / "
            "Then: prompt restauré, entrée audit log, fitness recalculée sur prochains runs, ancienne version archivée."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-045",
        "feature_id": "sf-f-v5-darwin-05",
        "project_id": "software-factory",
        "title": "En tant que RTE, je veux créer un pool de 5 agents 'analyste' avec auto-scaling pour absorber les pics de charge.",
        "acceptance_criteria": (
            "Given: Darwin > Pools > Nouveau / When: type=analyste, min=2, max=5 / "
            "Then: pool créé, agents instanciés selon charge, métriques utilisation visibles en temps réel."
        ),
        "story_points": 8,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-046",
        "feature_id": "sf-f-v5-darwin-05",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux voir la file d'attente d'un pool pour diagnostiquer les goulots d'étranglement.",
        "acceptance_criteria": (
            "Given: Pool detail / When: onglet Queue / "
            "Then: tâches en attente avec temps d'attente, tâches actives, agents libres, historique throughput."
        ),
        "story_points": 3,
        "priority": 7,
    },
    # ── Knowledge Base & i18n ──
    {
        "id": "sf-us-v5-047",
        "feature_id": "sf-f-v5-kb-01",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux créer une page wiki Markdown pour documenter l'architecture d'un projet.",
        "acceptance_criteria": (
            "Given: ProjectDetail > Wiki > Nouvelle page / When: titre + contenu Markdown / "
            "Then: page créée, preview temps réel, catégorie assignable, versionnée à chaque sauvegarde."
        ),
        "story_points": 5,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-048",
        "feature_id": "sf-f-v5-kb-01",
        "project_id": "software-factory",
        "title": "En tant que développeur, je veux rechercher dans le wiki par mot-clé pour trouver une documentation rapidement.",
        "acceptance_criteria": (
            "Given: Wiki > recherche / When: tape 'redis cluster' / "
            "Then: résultats FTS < 200ms, extraits avec highlights, tri par pertinence, filtre catégorie."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-049",
        "feature_id": "sf-f-v5-kb-01",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux voir l'historique des versions d'une page wiki pour comparer les modifications.",
        "acceptance_criteria": (
            "Given: page wiki / When: onglet Historique / "
            "Then: liste versions avec auteur/date, diff entre deux versions sélectionnables, restauration 1 clic."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-050",
        "feature_id": "sf-f-v5-kb-02",
        "project_id": "software-factory",
        "title": "En tant que lead, je veux créer une page ADR depuis un template préconfiguré pour standardiser les décisions d'architecture.",
        "acceptance_criteria": (
            "Given: Wiki > Nouveau > Template ADR / When: sélectionné / "
            "Then: page pré-remplie (contexte, décision, conséquences, alternatives), variables {{date}} remplacées."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-051",
        "feature_id": "sf-f-v5-kb-02",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux créer un runbook depuis un template pour documenter une procédure opérationnelle.",
        "acceptance_criteria": (
            "Given: Wiki > Nouveau > Template Runbook / When: sélectionné / "
            "Then: sections pré-remplies (prérequis, étapes numérotées, rollback, contacts), export PDF disponible."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-052",
        "feature_id": "sf-f-v5-kb-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur international, je veux basculer l'interface SF en anglais pour travailler dans ma langue.",
        "acceptance_criteria": (
            "Given: header > menu langue / When: sélectionne 'English' / "
            "Then: toute l'interface en anglais, préférence persistée en DB, format dates US (MM/DD/YYYY)."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-053",
        "feature_id": "sf-f-v5-kb-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux que les messages d'erreur et tooltips soient aussi traduits dans ma langue configurée.",
        "acceptance_criteria": (
            "Given: langue = EN / When: erreur validation formulaire / "
            "Then: message d'erreur en anglais, tooltips boutons en anglais, aucune chaîne en français visible."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v5-054",
        "feature_id": "sf-f-v5-kb-04",
        "project_id": "software-factory",
        "title": "En tant que manager, je veux exporter une page wiki en PDF pour la partager hors-SF avec des parties prenantes.",
        "acceptance_criteria": (
            "Given: page wiki / When: Export PDF / "
            "Then: PDF généré avec logo SF, titre, table des matières, code blocks avec syntax, images embarquées."
        ),
        "story_points": 3,
        "priority": 6,
    },
    {
        "id": "sf-us-v5-055",
        "feature_id": "sf-f-v5-kb-04",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux exporter le rapport de sprint en DOCX pour l'intégrer dans un reporting PowerPoint.",
        "acceptance_criteria": (
            "Given: SprintReport / When: Export DOCX / "
            "Then: fichier .docx téléchargé, styles Word appliqués, tableaux velocity/burndown inclus, éditable."
        ),
        "story_points": 3,
        "priority": 6,
    },
    # ── Notifications & Webhooks ──
    {
        "id": "sf-us-v5-056",
        "feature_id": "sf-f-v5-notif-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux voir toutes mes notifications dans un panneau centralisé pour ne rien manquer.",
        "acceptance_criteria": (
            "Given: cloche header / When: clic / "
            "Then: panneau slide-in, liste notifs catégorie/icône/date, badge compteur non-lues, 'Tout marquer lu'."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-057",
        "feature_id": "sf-f-v5-notif-01",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux filtrer mes notifications par catégorie pour me concentrer sur les incidents critiques.",
        "acceptance_criteria": (
            "Given: panneau notifications / When: filtre 'Incidents' / "
            "Then: seules les notifs catégorie=incident visibles, compteur mis à jour, filtre persisté session."
        ),
        "story_points": 2,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-058",
        "feature_id": "sf-f-v5-notif-02",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux configurer un webhook pour notifier mon orchestrateur quand une session SF se termine.",
        "acceptance_criteria": (
            "Given: Settings > Webhooks > Nouveau / When: event=session.completed, URL configurée / "
            "Then: webhook enregistré, payload JSON envoyé à chaque session terminée, retry 3x si échec."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-059",
        "feature_id": "sf-f-v5-notif-02",
        "project_id": "software-factory",
        "title": "En tant que DevOps, je veux tester un webhook manuellement pour vérifier l'intégration avant la mise en production.",
        "acceptance_criteria": (
            "Given: Webhook detail / When: bouton 'Test' / "
            "Then: payload test envoyé, réponse HTTP affichée, latence ms, statut success/failure, log conservé."
        ),
        "story_points": 2,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-060",
        "feature_id": "sf-f-v5-notif-03",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux configurer une intégration Slack pour recevoir les alertes SF dans un channel dédié.",
        "acceptance_criteria": (
            "Given: Settings > Intégrations > Slack / When: OAuth connecté + channel #alerts-sf / "
            "Then: messages au format Block Kit, avec type alerte, sévérité, lien ressource SF."
        ),
        "story_points": 3,
        "priority": 8,
    },
    {
        "id": "sf-us-v5-061",
        "feature_id": "sf-f-v5-notif-03",
        "project_id": "software-factory",
        "title": "En tant qu'admin, je veux envoyer les alertes SLA critiques par email aux responsables d'astreinte pour garantir la réactivité.",
        "acceptance_criteria": (
            "Given: incident P1 créé / When: SLA < 30min restant / "
            "Then: email envoyé aux astreintes, template HTML avec contexte incident, liens d'action directs."
        ),
        "story_points": 3,
        "priority": 9,
    },
    {
        "id": "sf-us-v5-062",
        "feature_id": "sf-f-v5-notif-04",
        "project_id": "software-factory",
        "title": "En tant que manager, je veux recevoir un digest quotidien par email résumant les sessions et déploiements du jour.",
        "acceptance_criteria": (
            "Given: digest daily activé / When: cron 18h00 / "
            "Then: email résumé: nb sessions, stories livrées, déploiements, incidents, métriques DORA, lien rapport."
        ),
        "story_points": 3,
        "priority": 7,
    },
    {
        "id": "sf-us-v5-063",
        "feature_id": "sf-f-v5-notif-04",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux désactiver le digest pour un projet spécifique sans affecter les autres projets.",
        "acceptance_criteria": (
            "Given: UserSettings > Notifications / When: désactive digest pour projet 'legacy' / "
            "Then: aucun email digest pour ce projet, les autres projets non affectés, préférence persistée."
        ),
        "story_points": 1,
        "priority": 6,
    },
]

# ── Stories manquantes pour features orphelines sf-f-v4-ux-06 et sf-f-v4-offline-03 ──

SF_STORIES_V4_PATCH: list[dict] = [
    {
        "id": "sf-us-v4p-001",
        "feature_id": "sf-f-v4-ux-06",
        "project_id": "software-factory",
        "title": "En tant que PO, je veux réordonner les stories dans le backlog par drag & drop pour prioriser rapidement.",
        "acceptance_criteria": (
            "Given: BacklogView, liste stories / When: drag story vers position supérieure / "
            "Then: story repositionnée, WSJF décrémenté d'1 rang, feedback visuel, Cmd+Z annule."
        ),
        "story_points": 5,
        "priority": 6,
    },
    {
        "id": "sf-us-v4p-002",
        "feature_id": "sf-f-v4-ux-06",
        "project_id": "software-factory",
        "title": "En tant que manager, je veux assigner un agent à une équipe par drag & drop dans la vue organisation.",
        "acceptance_criteria": (
            "Given: OrgView, carte agent et colonne équipe / When: drag agent vers colonne / "
            "Then: agent assigné, team_id mis à jour, indicateur WIP recalculé."
        ),
        "story_points": 5,
        "priority": 5,
    },
    {
        "id": "sf-us-v4p-003",
        "feature_id": "sf-f-v4-offline-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur macOS, je veux que mes mutations offline soient synchronisées automatiquement au retour en ligne.",
        "acceptance_criteria": (
            "Given: 3 mutations locales en queue / When: connexion rétablie / "
            "Then: sync démarrée en < 2s, progression affichée, notification 'Sync terminée (3/3)'."
        ),
        "story_points": 5,
        "priority": 7,
    },
    {
        "id": "sf-us-v4p-004",
        "feature_id": "sf-f-v4-offline-03",
        "project_id": "software-factory",
        "title": "En tant qu'utilisateur, je veux consulter le log de synchronisation pour vérifier que tout a bien été envoyé.",
        "acceptance_criteria": (
            "Given: Settings > Sync / When: onglet 'Log sync' / "
            "Then: liste horodatée des mutations avec statut ok/erreur, export possible."
        ),
        "story_points": 3,
        "priority": 5,
    },
]
