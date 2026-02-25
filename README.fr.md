<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a>
</p>

<div align="center">

# Software Factory

**Usine Logicielle Multi-Agents — Agents IA autonomes orchestrant le cycle de vie complet des produits**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Demo live : sf.macaron-software.com](https://sf.macaron-software.com)** — cliquez "Skip (Demo)" pour explorer

[Fonctionnalités](#fonctionnalités) · [Démarrage rapide](#démarrage-rapide) · [Captures d'écran](#captures-décran) · [Architecture](#architecture) · [Contribuer](#contribuer)

</div>

---

## C'est quoi ?

Software Factory est une **plateforme multi-agents autonome** qui orchestre l'intégralité du cycle de développement logiciel — de l'idéation au déploiement — en utilisant des agents IA spécialisés travaillant ensemble.

Imaginez une **usine logicielle virtuelle** où 161 agents IA collaborent à travers des workflows structurés, suivant la méthodologie SAFe, les pratiques TDD et des portes de qualité automatisées.

### Points clés

- **161 agents spécialisés** — architectes, développeurs, testeurs, SRE, analystes sécurité, product owners
- **10 patterns d'orchestration** — solo, séquentiel, parallèle, hiérarchique, réseau, boucle, routeur, agrégateur, vague, human-in-the-loop
- **Cycle de vie SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Résilience LLM** — fallback multi-provider, retry avec jitter, gestion rate-limit, config modèle par env
- **Observabilité OpenTelemetry** — tracing distribué avec Jaeger, dashboard analytics pipeline
- **Watchdog continu** — auto-reprise des runs en pause, récupération sessions bloquées, nettoyage échecs
- **Sécurité prioritaire** — garde injection de prompt, RBAC, masquage secrets, connection pooling
- **Métriques DORA** — fréquence déploiement, lead time, MTTR, taux échec changements

## Captures d'écran

<table>
<tr>
<td width="50%">
<strong>Dashboard — Perspective SAFe Adaptative</strong><br>
<img src="docs/screenshots/fr/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — Backlog Stratégique & WSJF</strong><br>
<img src="docs/screenshots/fr/portfolio.png" alt="Portfolio" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Planification Program Increment</strong><br>
<img src="docs/screenshots/fr/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Idéation — Brainstorming Multi-Agents IA</strong><br>
<img src="docs/screenshots/fr/ideation.png" alt="Idéation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Trains & Équipes Agents</strong><br>
<img src="docs/screenshots/fr/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>Cérémonies — Templates Workflows & Patterns</strong><br>
<img src="docs/screenshots/fr/ceremonies.png" alt="Cérémonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoring — Métriques DORA & Santé Système</strong><br>
<img src="docs/screenshots/fr/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — Wizard Sélection Rôle SAFe</strong><br>
<img src="docs/screenshots/fr/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
</table>

## Démarrage rapide

### Option 1 : Docker (Recommandé)

L'image inclut : **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # copie .env.example → .env (éditez pour ajouter votre clé LLM)
make run     # construit et lance la plateforme
```

Ouvrir http://localhost:8090 — au premier lancement, l'**assistant d'onboarding** apparaît.
Choisissez votre rôle SAFe ou cliquez sur **« Skip (Demo) »** pour explorer directement.

### Option 2 : Installation locale

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # créer votre config (éditer pour ajouter la clé LLM — voir Étape 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Démarrer la plateforme
make dev
# ou manuellement : PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Ouvrir http://localhost:8090 — au premier lancement, l'**assistant d'onboarding** apparaît.
Choisissez votre rôle SAFe ou cliquez sur **« Skip (Demo) »** pour explorer directement.

### Étape 3 : Configurer un fournisseur LLM

Sans clé API, la plateforme tourne en **mode demo** — les agents répondent avec des réponses simulées.
C'est utile pour explorer l'interface, mais les agents ne génèreront pas de vrai code ou d'analyse.

Pour activer les vrais agents IA, éditez `.env` et ajoutez **une** clé API :

```bash
# Option A : MiniMax (recommande pour demarrer)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-votre-clé-ici

# Option B : Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=votre-clé
AZURE_OPENAI_ENDPOINT=https://votre-resource.openai.azure.com

# Option C : NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-votre-clé-ici
```

Puis relancez : `make run` (Docker) ou `make dev` (local)

| Fournisseur | Variable d'env | Modeles |
|-------------|---------------|---------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

La plateforme bascule automatiquement sur les autres fournisseurs configurés en cas d'échec.

Vous pouvez aussi configurer les fournisseurs depuis la page **Settings** du dashboard (`/settings`).

## Fonctionnalités

### 🤖 145 Agents IA Spécialisés

Les agents sont organisés en équipes reflétant de vraies organisations logicielles :

| Équipe | Agents | Rôle |
|--------|--------|------|
| **Product** | Product Manager, Business Analyst, PO | Planification SAFe, priorisation WSJF |
| **Architecture** | Solution Architect, Tech Lead, System Architect | Décisions architecture, design patterns |
| **Développement** | Backend/Frontend/Mobile/Data Engineers | Implémentation TDD par stack |
| **Qualité** | QA Engineers, Security Analysts, Test Automation | Tests, audits sécurité, tests pénétration |
| **Design** | UX Designer, UI Designer | Expérience utilisateur, design visuel |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, monitoring, infrastructure |
| **Management** | Scrum Master, RTE, Agile Coach | Cérémonies, facilitation, levée obstacles |

### 10 Patterns d'Orchestration

- **Solo** — un seul agent pour tâches simples
- **Séquentiel** — pipeline d'agents exécutant dans l'ordre
- **Parallèle** — plusieurs agents travaillant simultanément
- **Hiérarchique** — manager déléguant à sous-agents
- **Réseau** — agents collaborant peer-to-peer
- **Boucle** — agent itère jusqu'à condition remplie
- **Routeur** — un agent route vers le spécialiste approprié
- **Agrégateur** — plusieurs entrées fusionnées par un agrégateur
- **Vague** — parallèle au sein des vagues, séquentiel entre vagues
- **Human-in-the-loop** — agent propose, humain valide

### 📊 Cycle de Vie Aligné SAFe

Hiérarchie complète Portfolio → Epic → Feature → Story avec :

- **Portfolio Stratégique** — canvas portfolio, thèmes stratégiques, value streams
- **Program Increment** — planification PI, objectifs, dépendances
- **Team Backlog** — user stories, tâches, critères d'acceptation
- **Sprint Execution** — daily standups, sprint reviews, rétrospectives

### 🛡️ Sécurité & Conformité

- **Authentification** — auth JWT avec RBAC
- **Garde injection prompt** — détection et blocage prompts malveillants
- **Masquage secrets** — redaction automatique données sensibles
- **CSP (Content Security Policy)** — headers durcis
- **Rate limiting** — quotas API par utilisateur
- **Audit logging** — logs d'activité complets

### 📈 Métriques DORA & Monitoring

- **Deployment frequency** — fréquence du code en production
- **Lead time** — durée commit vers déploiement
- **MTTR** — temps moyen de récupération des incidents
- **Change failure rate** — pourcentage de déploiements échoués
- **Dashboards temps réel** — visualisations Chart.js
- **Métriques Prometheus** — endpoint /metrics

### 📊 Métriques Qualité — Monitoring Industriel

Scan qualité déterministe (sans LLM) avec 10 dimensions, comme une chaîne de production :

| Dimension | Outils | Ce qui est mesuré |
|-----------|--------|------------------|
| **Complexité** | radon, lizard | Complexité cyclomatique, complexité cognitive |
| **Couverture UT** | coverage.py, nyc | Pourcentage de couverture lignes/branches |
| **Couverture E2E** | Playwright | Nombre de fichiers test, couverture specs |
| **Sécurité** | bandit, semgrep | Findings SAST par sévérité (critique/haute/moyenne/basse) |
| **Accessibilité** | pa11y | Violations WCAG 2.1 AA |
| **Performance** | Lighthouse | Scores Core Web Vitals |
| **Documentation** | interrogate | README, changelog, API docs, couverture docstrings |
| **Architecture** | madge, jscpd, mypy | Dépendances circulaires, duplication, erreurs type |
| **Maintenabilité** | custom | Distribution taille fichiers, ratio gros fichiers |
| **Adversarial** | intégré | Taux incidents, taux rejets adversarial |

**Portes qualité sur les phases de workflow** — chaque phase affiche un badge qualité (PASS/FAIL/PENDING) basé sur des seuils configurables :

| Type de porte | Seuil | Utilisé dans |
|---------------|-------|-------------|
| `always` | 0% | Phases analyse, planning |
| `no_veto` | 50% | Phases implémentation, sprint |
| `all_approved` | 70% | Phases revue, release |
| `quality_gate` | 80% | Phases deploy, production |

**Dashboard qualité** sur `/quality` — scorecard global, scores par projet, snapshots tendances.
Badges qualité visibles sur les missions, projets, workflows et le dashboard principal.

### 🔄 4 Missions Auto-Provisionnées par Projet

Chaque projet reçoit automatiquement 4 missions opérationnelles :

| Mission | Type | Fréquence | Description |
|---------|------|-----------|-------------|
| **MCO/TMA** | Programme | Continue | Monitoring santé, triage incidents (P0-P4), correctif TDD, validation non-régression |
| **Sécurité** | Revue | Hebdomadaire | Scans SAST (bandit/semgrep), audit dépendances, veille CVE |
| **Dette Technique** | Réduction | Mensuelle | Audit complexité, priorisation WSJF, sprints refactoring |
| **Self-Healing** | Programme | Continue | Pipeline autonome : détection 5xx → mission TMA → diagnostic agent → correctif code → validation |

### 🔃 Amélioration Continue

Trois workflows intégrés pour l'auto-amélioration :

| Workflow | Objectif | Agents |
|----------|---------|--------|
| **quality-improvement** | Scan → identifier pires dimensions → planifier et exécuter améliorations | QA Lead, Dev, Architecte |
| **retrospective-quality** | Rétro sprint : ROTI, incidents, métriques qualité → actions | Scrum Master, QA, Dev |
| **skill-evolution** | Analyser performance agents → mettre à jour prompts → évoluer skills | Brain, Lead Dev, QA |

Ces workflows créent une **boucle de feedback** : métriques → analyse → amélioration → re-scan → suivi progrès.

### 🔧 Outils Intégrés des Agents

L'image Docker inclut tout le nécessaire pour que les agents travaillent en autonomie :

| Catégorie | Outils | Description |
|-----------|--------|-------------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search` | Lecture, écriture et recherche de fichiers |
| **Build** | `build`, `test`, `local_ci` | Builds, tests, pipeline CI local (npm/pip/cargo auto-détecté) |
| **Git** | `git_commit`, `git_diff`, `git_log` | Contrôle de version avec isolation par branche agent |
| **Sécurité** | `sast_scan`, `dependency_audit`, `secrets_scan` | SAST via bandit/semgrep, audit CVE, détection de secrets |
| **QA** | `playwright_test`, `browser_screenshot` | Tests E2E Playwright et captures d'écran (Chromium inclus) |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | Création d'incidents/tickets pour le suivi TMA |
| **Deploy** | `docker_deploy`, `github_actions` | Déploiement conteneur et statut CI/CD |
| **Mémoire** | `memory_store`, `memory_search`, `deep_search` | Mémoire projet persistante entre sessions |

### 🔄 Auto-Réparation & Self-Healing (TMA)

Cycle autonome de détection, triage et réparation d'incidents :

- **Heartbeat monitoring** — vérification continue de la santé des missions et services
- **Détection auto d'incidents** — HTTP 5xx, timeout, crash agent → création automatique d'incident
- **Triage & classification** — sévérité (P0-P3), analyse d'impact, hypothèse cause racine
- **Auto-réparation** — les agents diagnostiquent et corrigent autonomement (patches, config, restarts)
- **Création de tickets** — incidents non résolus → tickets trackés pour revue humaine
- **Escalade** — P0/P1 déclenche notifications Slack/Email à l'équipe d'astreinte
- **Boucle rétrospective** — apprentissages post-incident stockés en mémoire, injectés dans les sprints futurs

### 🎭 Perspectives SAFe & Onboarding

Interface adaptative par rôle SAFe :

- **9 perspectives SAFe** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Dashboard adaptatif** — KPIs, actions rapides et sidebar varient selon le rôle sélectionné
- **Wizard d'onboarding** — parcours 3 étapes (choisir rôle → choisir projet → démarrer)
- **Sélecteur de perspective** — changer de rôle SAFe depuis la topbar
- **Sidebar dynamique** — navigation filtrée selon la perspective courante

### 🧠 Mémoire 4 Couches & RLM Deep Search

Connaissance persistante inter-sessions avec recherche intelligente :

- **Mémoire session** — contexte conversationnel
- **Mémoire pattern** — apprentissages des exécutions de patterns d'orchestration
- **Mémoire projet** — connaissances par projet (décisions, conventions, architecture)
- **Mémoire globale** — connaissances organisationnelles cross-projets (FTS5)
- **Fichiers projet auto-chargés** — CLAUDE.md, SPECS.md, VISION.md injectés dans chaque prompt LLM (max 8K)
- **RLM Deep Search** — boucle itérative WRITE-EXECUTE-OBSERVE-DECIDE (jusqu'à 10 itérations)

### 🛒 Mercato Agents (Marché des Transferts)

Place de marché à tokens pour la composition d'équipes :

- **Listings agents** — mettre des agents en vente avec prix demandé
- **Pool agents libres** — agents non assignés disponibles au draft
- **Transferts & prêts** — acheter, vendre ou prêter des agents entre projets
- **Valorisation marché** — valorisation automatique basée sur skills et performance
- **Système de wallets** — portefeuilles tokens par projet avec historique

### 🛡️ Garde Qualité Adversariale

Porte de qualité double couche bloquant le code fake/placeholder :

- **L0 Déterministe** — détection instantanée de slop, mocks, fake builds, hallucinations, erreurs de stack
- **L1 Sémantique LLM** — revue qualité par LLM séparé sur les sorties d'exécution
- **Rejet forcé** — hallucinations et erreurs de stack toujours bloquées

### 📝 Auto-Documentation & Wiki

Génération automatique de documentation tout au long du cycle :

- **Rétrospectives sprint** — notes retro générées par LLM, stockées en mémoire et injectées dans les sprints suivants
- **Résumés de phases** — documentation automatique des décisions et résultats de chaque phase mission
- **Sync Confluence** — synchronisation bidirectionnelle avec les pages wiki Confluence
- **Swagger auto-docs** — 94 endpoints REST auto-documentés sur `/docs`

## Quatre Interfaces

### 1. Dashboard Web (HTMX + SSE)

Interface principale sur http://localhost:8090 :

- **Conversations multi-agents temps réel** avec streaming SSE
- **PI Board** — planification program increment
- **Mission Control** — monitoring d'exécution
- **Gestion Agents** — voir, configurer, monitorer agents
- **Dashboard Incidents** — triage auto-réparation
- **Responsive mobile** — fonctionne sur tablettes et téléphones

### 2. CLI (`sf`)

Interface ligne de commande complète :

```bash
# Installation (ajouter au PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Navigation
sf status                              # Santé plateforme
sf projects list                       # Tous les projets
sf missions list                       # Missions avec scores WSJF
sf agents list                         # 161 agents
sf features list <epic_id>             # Features d'un epic
sf stories list --feature <id>         # User stories

# Travail
sf ideation "app e-commerce React"     # Idéation multi-agents (streamé)
sf missions start <id>                 # Démarrer une mission
sf metrics dora                        # Métriques DORA

# Monitoring
sf incidents list                      # Incidents
sf llm stats                           # Usage LLM (tokens, coût)
sf chaos status                        # Chaos engineering
```

**22 groupes de commandes** · Mode dual : API (serveur live) ou DB (offline) · Sortie JSON (`--json`) · Animations spinner · Rendu tables Markdown

### 3. API REST + Swagger

94 endpoints API auto-documentés sur `/docs` (Swagger UI) :

```bash
# Exemples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "app GPS vélo"}'
```

Swagger UI : http://localhost:8090/docs

### 4. Serveur MCP (Model Context Protocol)

23 outils MCP pour intégration agents IA (port 9501) :

```bash
# Démarrer serveur MCP
python3 -m platform.mcp_platform.server

# Outils disponibles :
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architecture

### Vue d'ensemble

```
                        ┌──────────────────────┐
                        │   CLI (sf) / IHM Web │
                        │   API REST :8090     │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     Serveur FastAPI           │
                    │  Auth (JWT + RBAC + OAuth)    │
                    │  17 modules de routes         │
                    └──┬──────────┬────────────┬───┘
                       │          │            │
          ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
          │ Moteur       │   │ Moteur   │   │   Couche     │
          │  Agents      │   │ Workflow │   │   Missions   │
          │ 161 agents   │   │ 39 defs  │   │ Cycle SAFe   │
          │ executeur    │   │ 10 ptrns │   │ Portfolio    │
          │ boucle+retry │   │ phases   │   │ Epic/Feature │
          └──────┬───────┘   │ retry    │   │ Story/Sprint │
                 │           │ skip     │   └──────────────┘
                 │           │ ckpoint  │
                 │           └────┬─────┘
                 │                │
     ┌───────────┴────────────────┴───────────────┐
     │              Services                       │
     │  Client LLM (fallback multi-provider)       │
     │  Outils (code, git, deploy, memoire, secu)  │
     │  Pont MCP (fetch, memory, playwright)       │
     │  Moteur Qualite (10 dimensions)             │
     │  Notifications (Slack, Email, Webhook)      │
     └───────────────────┬─────────────────────────┘
                         │
     ┌───────────────────┴─────────────────────────┐
     │              Operations                      │
     │  Watchdog (auto-reprise, detection blocage)  │
     │  Auto-Reparation (incident > triage > fix)   │
     │  OpenTelemetry (tracing + metriques > Jaeger)│
     └───────────────────┬─────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   SQLite + Memoire  │
              │   memoire 4 couches │
              │   recherche FTS5    │
              └─────────────────────┘
```

### Flux du Pipeline

```
Mission Creee
     │
     ▼
┌─────────────┐     ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Selection  │────▶│sequentiel│    │ parallele│    │hierarchiq│
│  Pattern    │────▶│          │    │          │    │          │
└─────────────┘────▶│ adversar.│    │          │    │          │
                    └────┬─────┘    └────┬─────┘    └────┬─────┘
                         └───────────────┴───────────────┘
                                         │
                    ┌────────────────────────────────────────┐
                    │         Execution de Phase              │
                    │                                        │
                    │  Agent ──▶ Appel LLM ──▶ Resultat     │
                    │                            │           │
                    │              ┌───succes─────┴──echec──┐│
                    │              ▼                        ▼│
                    │         Phase code?           Essais?  │
                    │           │ oui                 │ oui │
                    │           ▼                     ▼     │
                    │     Validation           Retry avec   │
                    │     Build Sandbox        backoff      │
                    │           │                     │ non │
                    │           ▼                     ▼     │
                    │     Porte Qualite        skip_on_fail?│
                    │      │        │           │oui  │non  │
                    │    passe    echec          │     │     │
                    │      │        │            │     ▼     │
                    │      ▼        ▼            │   PAUSE   │
                    │  Checkpoint  PAUSE ◀───────┘     │     │
                    └──────┬─────────────────────────────┘    │
                           │                                  │
                    Autres phases? ──oui──▶ phase suivante    │
                           │ non                              │
                           ▼                    watchdog      │
                    Mission Terminee      auto-reprise ◀──────┘
```

### Observabilite

```
┌──────────────────────┐    ┌────────────────────────────────┐
│   Middleware OTEL     │    │     Watchdog Continu            │
│   (chaque requete)    │    │                                │
│   spans + metriques   │    │  bilan sante      toutes 60s  │
│         │             │    │  detection blocage phases>60min│
│         ▼             │    │  auto-reprise    5/lot 5min   │
│   Export OTLP/HTTP    │    │  recuperation    sessions>30m │
│         │             │    │  nettoyage       zombies      │
│         ▼             │    └────────────────────────────────┘
│   Jaeger :16686       │
└──────────────────────┘    ┌────────────────────────────────┐
                            │     Analyse des Echecs          │
┌──────────────────────┐    │                                │
│   Moteur Qualite      │    │  classification erreurs        │
│   10 dimensions       │    │  heatmap phases                │
│   portes qualite      │    │  recommandations               │
│   radar chart         │    │  bouton reprendre tout         │
│   badge + scorecard   │    └────────────────────────────────┘
└──────────────────────┘
                            ┌────────────────────────────────┐
         Donnees ──────────▶│  Tableau de bord /analytics     │
                            │  stats tracing + graphe latence │
                            │  doughnut erreurs + barres phases│
                            │  radar qualite + scorecard      │
                            └────────────────────────────────┘
```

### Deploiement

```
                          Internet
                     ┌───────┴────────┐
                     │                │
          ┌──────────▼─────┐  ┌───────▼────────┐
          │ VM Azure (Prod)│  │ VPS OVH (Demo) │
          │ 4.233.64.30   │  │ 54.36.183.124  │
          │                │  │                │
          │ Nginx :443     │  │ Nginx :443     │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Plateforme     │  │ Plateforme     │
          │ :8090          │  │ :8090          │
          │ GPT-5-mini     │  │ MiniMax-M2.5   │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Jaeger :16686  │  │ Jaeger :16686  │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ SQLite DB      │  │ SQLite DB      │
          │ /patches (ro)  │  │                │
          └────────────────┘  └────────────────┘
                     │                │
                     └───────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ GitHub          │
                    │ macaron-software│
                    │ /software-factory│
                    └─────────────────┘
```

## Nouveautés v2.1.0 (fév 2026)

### Métriques Qualité — Monitoring Industriel
- **10 dimensions déterministes** — complexité, couverture (UT/E2E), sécurité, accessibilité, performance, documentation, architecture, maintenabilité, adversarial
- **Portes qualité sur les phases** — badges PASS/FAIL par phase avec seuils configurables (always/no_veto/all_approved/quality_gate)
- **Dashboard qualité** sur `/quality` — scorecard global, scores par projet, snapshots tendances
- **Badges qualité partout** — missions, projets, workflows, dashboard principal
- **Sans LLM** — toutes les métriques calculées de manière déterministe (radon, bandit, semgrep, coverage.py, pa11y, madge)

### 4 Missions Auto-Provisionnées par Projet
Chaque projet reçoit automatiquement 4 missions opérationnelles :
- **MCO/TMA** — maintenance continue : monitoring santé, triage incidents (P0-P4), correctif TDD, validation non-régression
- **Sécurité** — scans SAST hebdomadaires, audit dépendances, veille CVE
- **Dette Technique** — réduction mensuelle : audit complexité, priorisation WSJF, sprints refactoring
- **Self-Healing** — pipeline autonome : détection 5xx → mission TMA → diagnostic agent → correctif code → validation

### Amélioration Continue
- **Workflow quality-improvement** — scan → identifier pires dimensions → planifier et exécuter améliorations
- **Workflow retrospective-quality** — rétro sprint avec ROTI, incidents, métriques qualité → actions
- **Workflow skill-evolution** — analyser performance agents → mettre à jour prompts → évoluer skills
- **Boucle de feedback** — métriques → analyse → amélioration → re-scan → suivi progrès

### Perspectives SAFe & Onboarding
- **9 perspectives SAFe** — dashboard, sidebar et KPIs adaptatifs par rôle
- **Wizard d'onboarding** — parcours 3 étapes première connexion
- **Sélecteur de perspective** — changer de rôle SAFe depuis la topbar

### Auto-Réparation & Self-Healing
- **Heartbeat TMA** — monitoring continu avec création auto d'incidents
- **Agents auto-réparation** — diagnostic et correction autonomes
- **Escalade tickets** — incidents non résolus créent des tickets avec notifications

### Mémoire 4 Couches & RLM
- **Connaissance persistante** — mémoire session, pattern, projet et globale avec FTS5
- **RLM deep search** — boucle d'exploration récursive (jusqu'à 10 itérations)
- **Contexte projet auto-chargé** — CLAUDE.md, SPECS.md, VISION.md injectés dans chaque prompt agent

### Garde Qualité Adversariale
- **L0 déterministe** — détection instantanée de slop, mocks, fake builds, hallucinations
- **L1 sémantique** — revue qualité LLM sur les sorties d'exécution
- **Rejet forcé** — hallucinations et erreurs de stack toujours bloquées

### Mercato Agents
- **Place de marché à tokens** avec listings, transferts, prêts et draft d'agents libres
- **Valorisation marché** — pricing automatique basé sur skills et performance
- **Système wallets** — économie tokens par projet avec historique

### Auth & Sécurité
- **Auth JWT** avec login/register/refresh/logout
- **RBAC** — admin, project_manager, developer, viewer
- **OAuth** — GitHub et Azure AD SSO
- **Mode démo** — bouton "Skip" pour accès instantané

### Auto-Documentation
- **Rétrospectives sprint** — notes retro LLM avec boucle d'apprentissage
- **Résumés de phases** — documentation auto des résultats de missions
- **Sync Confluence** — intégration wiki bidirectionnelle

### Fournisseurs LLM
- **Multi-provider** avec fallback automatique
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Mode démo** pour exploration UI sans clés API

### Améliorations Plateforme
- Dashboard métriques DORA avec suivi coûts LLM
- Sync bidirectionnelle Jira
- Suite E2E Playwright (11 specs)
- Internationalisation (EN/FR)
- Notifications temps réel (Slack, Email, Webhook)
- Pipeline Design System dans les workflows
- Visualisation 3D Agent World

## Nouveautés v2.2.0 (fév 2026)

### OpenTelemetry & Tracing Distribué
- **Intégration OTEL** — SDK OpenTelemetry avec exporteur OTLP/HTTP vers Jaeger
- **Middleware tracing ASGI** — chaque requête HTTP tracée avec spans, latence, statut
- **Dashboard tracing** sur `/analytics` — stats requêtes, graphiques latence, table opérations
- **UI Jaeger** — exploration complète des traces distribuées sur port 16686

### Analyse des Échecs Pipeline
- **Classification des erreurs** — catégorisation Python (setup_failed, llm_provider, timeout, phase_error, etc.)
- **Heatmap phases** — identifier quelles phases du pipeline échouent le plus
- **Moteur de recommandations** — suggestions actionnables basées sur les patterns d'échec
- **Bouton Resume All** — reprise en masse des runs en pause depuis le dashboard

### Watchdog Continu
- **Auto-reprise** — reprend les runs en pause par lots (5/lot, toutes les 5 min, max 10 concurrents)
- **Récupération sessions bloquées** — détecte sessions inactives >30 min, marque pour retry
- **Nettoyage sessions échouées** — supprime les sessions zombies bloquant le pipeline
- **Détection blocage** — missions bloquées >60 min dans une phase relancées automatiquement

### Résilience des Phases
- **Retry par phase** — nombre de retry configurable (défaut 3x) avec backoff exponentiel
- **skip_on_failure** — phases optionnelles permettant au pipeline de continuer
- **Checkpointing** — phases terminées sauvegardées, reprise intelligente saute le travail fait
- **Timeout de phase** — limite 10 min empêche les blocages infinis

### Validation Build Sandbox
- **Vérification post-code** — après les phases de génération de code, lance automatiquement build/lint
- **Détection auto du build system** — npm, cargo, go, maven, python, docker
- **Injection d'erreur** — les échecs build injectés dans le contexte agent pour auto-correction

### Améliorations UI Qualité
- **Radar chart** — visualisation Chart.js des dimensions qualité sur `/quality`
- **Badge qualité** — cercle coloré dans les en-têtes projet (`/api/dashboard/quality-badge`)
- **Scorecard mission** — métriques qualité dans la sidebar mission (`/api/dashboard/quality-mission`)

## Contribuer

Les contributions sont bienvenues ! Veuillez lire [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives.

## Licence

Ce projet est sous licence AGPL v3 - voir le fichier [LICENSE](LICENSE) pour détails.

## Support

- Demo live : https://sf.macaron-software.com
- Issues : https://github.com/macaron-software/software-factory/issues
- Discussions : https://github.com/macaron-software/software-factory/discussions
