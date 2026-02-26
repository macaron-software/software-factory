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
<tr>
<td width="50%">
<strong>Accueil — Onglets CTO Jarvis / Idéation Business / Idéation Projet</strong><br>
<img src="docs/screenshots/fr/home.png" alt="Accueil" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — Conseiller IA Stratégique</strong><br>
<img src="docs/screenshots/fr/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Idéation Business — Équipe Marketing 6 Agents</strong><br>
<img src="docs/screenshots/fr/mkt_ideation.png" alt="Idéation Business" width="100%">
</td>
<td width="50%">
<strong>Idéation Projet — Équipe Tech Multi-Agents</strong><br>
<img src="docs/screenshots/fr/ideation_projet.png" alt="Idéation Projet" width="100%">
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

## Premiers pas — Votre premier projet

Apres l'installation, voici comment passer d'une idee a un projet fonctionnel :

### Voie A : Partir d'une idee (Atelier d'ideation)

1. **Ouvrez la page Ideation** — allez sur `/ideation` (ou cliquez "Ideation" dans la barre laterale)
2. **Decrivez votre idee** — ex. *"Application de covoiturage d'entreprise avec matching en temps reel"*
3. **Regardez les agents discuter** — 5 agents specialises (Product Manager, Business Analyst, Architecte, UX Designer, Securite) analysent votre idee en temps reel via streaming SSE
4. **Creez un projet a partir du resultat** — cliquez **"Creer un Epic a partir de cette idee"**. La plateforme va :
   - Creer un nouveau **projet** avec `VISION.md` et scaffolding CI/CD generes
   - Creer un **epic** avec des features et user stories decomposees par l'agent PO
   - Auto-provisionner les missions **TMA**, **Securite** et **Dette technique**

### Voie B : Creer un projet manuellement

1. Allez sur `/projects` et cliquez **"Nouveau Projet"**
2. Remplissez : nom, description, stack technique, chemin du depot
3. La plateforme cree automatiquement :
   - Un **agent Product Manager** assigne au projet
   - Une **mission TMA** (maintenance continue — surveille la sante, cree des incidents)
   - Une **mission Securite** (audits de securite hebdomadaires — SAST, verification des dependances)
   - Une **mission Dette Technique** (reduction mensuelle de la dette — planifiee)

### Ensuite : Creer des Epics et Features

- Depuis la page **Portfolio** (`/portfolio`), creez des epics avec priorisation WSJF
- Depuis un epic, ajoutez des **features** et decomposez-les en **user stories**
- Utilisez le **PI Board** (`/pi-board`) pour planifier les increments programme et assigner les features aux sprints

### Lancer des missions

- Cliquez **"Demarrer"** sur une mission pour lancer l'execution des agents
- Choisissez un **pattern d'orchestration** (hierarchique, reseau, parallele...)
- Suivez le travail des agents en temps reel depuis **Mission Control**
- Les agents utilisent leurs outils (code_read, git, build, test, security scan) de maniere autonome

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
          │ sf.macaron-software.com   │  │ demo.macaron-software.com  │
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

## Intelligence Adaptative — AG · AR · Thompson Sampling · OKR

La plateforme s'auto-optimise en continu grâce à trois moteurs d'IA complémentaires qui choisissent ensemble la meilleure équipe, le meilleur pattern et la meilleure configuration de workflow pour chaque mission.

### Thompson Sampling — Sélection Probabiliste des Équipes

Darwin choisit les équipes agent+pattern via un **bandit bayésien à exploration** :

- Distribution `Beta(α=wins+1, β=losses+1)` par contexte `(agent_id, pattern_id, technologie, type_phase)`
- **Fitness granulaire** — score séparé par contexte : l'expertise migration Angular ne contamine jamais l'expertise nouvelle-fonctionnalité Angular
- **Fallback cold-start** — chaîne de préfixe `angular_19` → `angular_*` → `generic` : aucune équipe ne reste sans sélection
- **Retraite souple** — équipes faibles passent à `weight_multiplier=0.1`, déprioritisées mais récupérables en un clic
- **Tests A/B en shadow** — runs parallèles automatiques quand deux équipes ont un score proche (delta < 10) ou à 10% de probabilité ; un évaluateur neutre choisit le gagnant

**Darwin LLM** étend le Thompson Sampling à la sélection de modèles : même équipe, fournisseurs LLM différents — `Beta(wins+1, losses+1)` par `(agent_id, pattern_id, technologie, type_phase, llm_model)` — le meilleur modèle s'impose automatiquement par contexte.

### Algorithme Génétique — Évolution des Workflows

Un moteur GA nightly (`platform/agents/evolution.py`) fait évoluer les templates de workflows à partir des données historiques des missions :

- **Génome** = liste ordonnée de `PhaseSpec` (pattern, agents, gate) — chaque workflow est un chromosome
- **Population** de 40 génomes, jusqu'à 30 générations, élitisme=2 génomes portés intacts
- **Croisement** — splice aléatoire de deux listes de phases parentes
- **Mutation** — permutation aléatoire de `pattern_id`, `gate` ou liste `agents` (taux 15%)
- **Fonction fitness** — combinaison pondérée : taux de réussite des phases, scores fitness agents, taux de veto, lead time mission
- **Sélection par tournoi** (k=3) — évite la convergence prématurée
- **Top-3 propositions** sauvegardées dans la table `evolution_proposals` pour revue humaine avant application
- **Déclenchement à la demande** via `POST /api/evolution/run/{wf_id}` — revue des propositions dans Workflows → onglet Évolution
- **Scheduler nightly** — tourne chaque nuit par workflow actif ; ignoré si <5 missions (signal insuffisant)

### Reinforcement Learning — Adaptation de Pattern en Cours de Mission

Une politique Q-learning (`platform/agents/rl_policy.py`) recommande des **changements de pattern en temps réel** pendant l'exécution d'une mission :

- **Espace d'action** : `keep`, `switch_parallel`, `switch_sequential`, `switch_hierarchical`, `switch_debate`, `add_agent`, `remove_agent`
- **Encodage d'état** — `(wf_id, bucket_position_phase, bucket_rejet_pct, bucket_score_qualité)` — compact et généralisable
- **Mise à jour Q** (batch offline) : `Q(s,a) ← Q(s,a) + α × [r + γ × max Q(s',·) − Q(s,a)]`
- **Hyperparamètres** : α=0.1, γ=0.9, ε=0.1 (10% exploration), seuil confiance=0.70, min 3 visites d'état avant déclenchement
- **Experience replay** — table `rl_experience` accumule des tuples `(état, action, récompense, état_suivant)` à chaque fin de phase
- **Récompenses** — positives si amélioration qualité + gain de temps ; négatives pour rejets et dépassements SLA
- **Intégration** — appelé par `engine.py` au démarrage de chaque phase ; recommandation déclenchée seulement au-dessus du seuil de confiance ; dégradation gracieuse vers le pattern par défaut

### OKR / KPI — Objectifs et Indicateurs Clés

Des critères de succès quantifiés guident la fitness GA et les récompenses RL :

| Domaine | Exemple OKR | Indicateurs clés |
|---------|-------------|-----------------|
| code/migration | ≥90% build success | build_pass_rate, test_coverage |
| sécurité/audit | 0 CVE critique | cve_critical_count, sast_score |
| architecture | revue design <2h | review_duration, approval_rate |
| tests | ≥95% tests OK | pass_rate, regression_count |
| documentation | 100% API couverte | doc_coverage, freshness |

- **8 seeds par défaut** pré-chargés au démarrage pour tous les domaines/types de phase
- **Édition inline** sur le dashboard Teams (`/teams`) — statut vert/amber/rouge par objectif
- **Pont OKR→fitness** — l'atteinte des OKR alimente directement la fonction fitness GA et le signal de récompense RL
- **OKR par projet** — surchargeables par projet dans la page Paramètres

### Simulation & Backtesting

Avant d'appliquer une proposition GA ou une recommandation RL en production, la plateforme peut lancer des **simulations** :

- Table `simulation_runs` stocke les runs synthétiques contre les génomes de workflow proposés
- Comparaison des résultats simulés vs historiques avant promotion d'une proposition
- Résultats visibles dans Workflows → onglet Évolution, à côté des cartes de propositions

### Où le Voir

| Fonctionnalité | URL |
|----------------|-----|
| Classement Darwin Teams | `/teams` |
| Propositions GA et historique évolution | `/workflows` → onglet Évolution |
| Statistiques politique RL | `/analytics` ou le dashboard Ops |
| Édition OKR | `/teams` → colonne OKR |
| Sidebar Intelligence Adaptative | Toutes les pages (rôle : DSI / Dev) |

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

### Darwin — Sélection Evolutive d'Equipes
- **Sélection Thompson Sampling** — choix probabiliste équipe agent+pattern via `Beta(wins+1, losses+1)` par `(agent_id, pattern_id, technologie, type_phase)`
- **Fitness granulaire** — score séparé par contexte : une équipe experte en migration Angular peut être mauvaise en nouvelle fonctionnalité Angular
- **Fallback similarité** — démarrage à froid géré par préfixe tech (`angular_19` → `angular_*` → `generic`)
- **Retraite souple** — équipes faibles reçoivent `weight_multiplier=0.1`, déprioritisées mais récupérables
- **OKR / KPI** — objectifs et indicateurs par domaine et type de phase ; 8 seeds par défaut (code/migration, sécurité/audit, architecture/conception, tests, docs, etc.)
- **Tests A/B en shadow** — runs parallèles automatiques quand deux équipes ont des scores proches (delta < 10) ou à 10% de probabilité
- **Dashboard Teams** sur `/teams` — classement avec badges champion/rising/declining/retired, édition OKR inline, courbes d'évolution Chart.js, historique sélections, résultats A/B
- **Non-breaking opt-in** — `agent_id: "skill:developer"` dans les patterns active Darwin ; les IDs explicites sont inchangés

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

### Routage LLM Multi-Modèle
- **3 modèles spécialisés** — `gpt-5.2` pour la réflexion lourde, `gpt-5.1-codex` pour le code/tests, `gpt-5-mini` pour les tâches légères
- **Routage par rôle** — les agents reçoivent automatiquement le bon modèle selon leurs tags (`reasoner`, `architect`, `developer`, `tester`, `doc_writer`…)
- **Configurable en live** — matrice de routage éditable depuis Paramètres → LLM sans redémarrage

### Darwin LLM — Thompson Sampling sur les Modèles
- **A/B testing de modèles** — même équipe (agent + pattern), différents LLM ; le meilleur modèle s'impose automatiquement par contexte
- **Beta distribution** — `Beta(wins+1, losses+1)` par `(agent_id, pattern_id, technology, phase_type, llm_model)`
- **Onglet LLM A/B** sur `/teams` — classement fitness par modèle et historique des tests
- **Chaîne de priorité** — Darwin LLM → config DB → défauts (dégradation gracieuse)

### Paramètres — Onglet LLM
- **Grille providers** — statut actif/inactif avec indices de clé manquante
- **Matrice de routage** — lourd/léger par catégorie (Raisonnement, Production/Code, Tâches, Rédaction)
- **Section Darwin LLM A/B** — vue live des expériences de modèles en cours

## Nouveautés v2.3.0 (fév 2026)

### Navigation Restructurée — Home + Dashboard
- **Page Accueil** (`/`) — trois onglets : CTO Jarvis · Idéation Business · Idéation Projet
- **Page Dashboard** (`/portfolio`) — trois onglets : Vue d'ensemble · DSI · Business
- **Sidebar épurée** — deux entrées seulement : Home et Dashboard
- **Icônes SVG Feather** — remplacement des emojis par des icônes vectorielles cohérentes

### CTO Jarvis — Conseiller IA Stratégique

![CTO Jarvis](docs/screenshots/fr/jarvis.png)

- **Panneau de chat persistant** — onglet dédié sur la page d'accueil
- **Mémoire persistante** — décisions techniques et contexte de session conservés
- **Conseiller de niveau CTO** — aide à la prise de décision architecturale, choix technologiques
- **Connaissance plateforme** — accès à l'état du portfolio, des projets et des équipes agents

**Capacités outils** : Code (lire/chercher/éditer/écrire/lister) · Git (commit, diff, log, status, issues/PRs/search) · Build/Deploy (build, lint, test, deploy, Docker, run_command, infra) · Sécurité (SAST, secrets scan, audit dépendances) · MCPs (Web fetch, Knowledge graph, Playwright, GitHub) · Projet (Jira, Confluence, phases SAFe, LRM context) · Mémoire (lecture + écriture Knowledge graph)

**Raccourcis contextuels** : `Stats portfolio` · `Missions en cours` · `Monter une équipe` · `GitHub` · `AO Veligo` · `Migration Angular 16→17` · `Dette tech · sécu · a11y · RGPD` · `Git commit & PR` · `E2E + Screenshots` · `Sync Jira` · `Mise à jour Wiki`

**Exemples de questions à Jarvis**

> *« Quel est l'état de santé global du portfolio ? Quels projets sont en retard ? »*

> *« Lance un audit SAST sur le projet Veligo et dis-moi les 3 CVE critiques à traiter en priorité. »*

> *« On doit migrer l'API de REST vers GraphQL — quelle équipe d'agents recommandes-tu et par où commencer ? »*

> *« Montre-moi le diff des 5 derniers commits sur la branche feature/auth et résume les changements. »*

> *« Crée une mission de refactoring pour réduire la complexité cyclomatique des fichiers au-dessus de 15. »*

> *« Quelle est notre dette technique actuelle ? Priorise les items par impact/effort. »*

> *« Rédige les user stories pour la fonctionnalité de connexion SSO Azure AD et ouvre les tickets Jira. »*

> *« Lance les tests E2E Playwright et capture des screenshots des pages critiques. »*

> *« Compare nos métriques DORA ce mois-ci vs le mois dernier — où régressons-nous ? »*

> *« Met à jour le wiki de l'architecture avec les dernières décisions sur la migration PostgreSQL. »*

### Idéation Business — Équipe Marketing 6 Agents

![Idéation Business](docs/screenshots/fr/mkt_ideation.png)

- **Route** `/mkt-ideation` — accessible depuis l'onglet Idéation Business de la page d'accueil
- **CMO Sophie Laurent** — chef d'équipe supervisant 5 experts marketing spécialisés
- **Plan marketing JSON complet** — SWOT, TAM/SAM/SOM, stratégie de marque, go-to-market, KPIs, budget
- **Graphe d'agents** — visualisation ig-node avec photos avatars, arêtes de collaboration, popovers

### Migration PostgreSQL + 40 Index
- **Migration SQLite → PostgreSQL** — scripts complets de migration schéma et données
- **FTS natif PostgreSQL** — `tsvector/tsquery` remplace FTS5, plus performant et scalable
- **40+ index PG** — couverture exhaustive de tous les chemins de requêtes chauds
- **Darwin Teams** — Thompson Sampling pour la sélection d'équipes agents par contexte (technologie + phase)

## Configuration Projet

Les projets sont definis dans `projects/*.yaml` :

```yaml
project:
  name: mon-projet
  root_path: /chemin/vers/projet
  vision_doc: CLAUDE.md

agents:
  - product_manager
  - solution_architect
  - backend_dev
  - qa_engineer

patterns:
  ideation: hierarchical
  development: parallel
  review: adversarial-pair

deployment:
  strategy: blue-green
  auto_prod: true
  health_check_url: /health
```

## Structure du Projet

```
├── platform/                # Plateforme Agent (152 fichiers Python)
│   ├── server.py            # App FastAPI, port 8090
│   ├── agents/              # Moteur agent (store, executor, loop)
│   ├── a2a/                 # Bus de messagerie agent-a-agent
│   ├── patterns/            # 10 patterns d'orchestration
│   ├── missions/            # Cycle de vie SAFe des missions
│   ├── sessions/            # Execution conversations + SSE
│   ├── web/                 # Routes + templates Jinja2
│   ├── mcp_platform/        # Serveur MCP (23 outils)
│   └── tools/               # Outils agent (code, git, deploy)
│
├── cli/                     # CLI 'sf' (6 fichiers, 2100+ lignes)
│   ├── sf.py                # 22 groupes de commandes, 40+ sous-commandes
│   ├── _api.py              # Client REST httpx
│   ├── _db.py               # Backend offline sqlite3
│   ├── _output.py           # Tables ANSI, rendu markdown
│   └── _stream.py           # Streaming SSE avec spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Charts Helm, Docker, K8s
├── tests/                   # Tests E2E Playwright
├── skills/                  # Bibliotheque de competences agents
├── projects/                # Configurations YAML des projets
└── data/                    # Base de donnees SQLite
```

## Tests

```bash
# Lancer tous les tests
make test

# Tests E2E (Playwright — installation requise)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Tests unitaires
pytest tests/

# Tests de chaos
python3 tests/test_chaos.py

# Tests d'endurance
python3 tests/test_endurance.py
```

## Deploiement

### Docker

L'image Docker inclut : **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.
Les agents peuvent builder des projets, lancer des tests E2E avec captures d'ecran, et effectuer des scans SAST.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### Variables d'Environnement

Voir [`.env.example`](.env.example) pour la liste complete. Variables principales :

```bash
# Fournisseur LLM (requis pour de vrais agents)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # Cle API MiniMax

# Authentification (optionnel)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth

# Integrations (optionnel)
JIRA_URL=https://votre-jira.atlassian.net
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Contribuer

Les contributions sont bienvenues ! Veuillez lire [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives.

## Licence

Ce projet est sous licence AGPL v3 - voir le fichier [LICENSE](LICENSE) pour détails.

## Support

- Demo live : https://sf.macaron-software.com
- Issues : https://github.com/macaron-software/software-factory/issues
- Discussions : https://github.com/macaron-software/software-factory/discussions
