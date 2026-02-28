<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.id.md">Bahasa</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.nl.md">Nederlands</a> |
  <a href="README.vi.md">Tiếng Việt</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.sv.md">Svenska</a>
</p>

<div align="center">

# Software Factory

**Usine Logicielle Multi-Agents — Agents IA autonomes orchestrant le cycle de vie complet des produits**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live : sf.macaron-software.com](https://sf.macaron-software.com)**

[Fonctionnalités](#fonctionnalités) · [Démarrage rapide](#démarrage-rapide) · [Captures d'écran](#captures-décran) · [Architecture](#architecture) · [Contribuer](#contribuer)

</div>

---

## C'est quoi ?

Software Factory est une **plateforme multi-agents autonome** qui orchestre l'intégralité du cycle de développement logiciel — de l'idéation au déploiement — en utilisant des agents IA spécialisés travaillant ensemble.

Imaginez une **usine logicielle virtuelle** où 191 agents IA collaborent à travers des workflows structurés, suivant la méthodologie SAFe, les pratiques TDD et des portes de qualité automatisées.

### Points clés

- **191 agents spécialisés** — architectes, développeurs, testeurs, SRE, analystes sécurité, product owners
- **36 workflows intégrés** — cérémonies SAFe, quality gates, maintenance nocturne, sécurité, gestion des connaissances
- **8 groupes d'idéation** — CTO Jarvis, Business, Projet, Knowledge, Architecture, Sécurité, Data & IA, PI Planning
- **Marketplace d'agents** — découvrir et lancer des agents depuis `/marketplace` ; filtrer par ART, rôle ou compétences
- **Replay de mission** — timeline pas-à-pas avec tokens, coût et durée par agent (`/missions/{id}/replay`)
- **Dashboard Métriques LLM** — monitoring coût/latence/provider en temps réel à `/metrics`
- **Framework d'évaluation** — scoring LLM-as-judge sur dataset golden à `/evals`
- **Tool Builder** — création d'outils HTTP/SQL/shell sans code à `/tool-builder`
- **Workspaces multi-tenant** — namespaces isolés par projet/client à `/workspaces`
- **Gestion des Connaissances** — 4 agents dédiés, équipe ART Knowledge, workflow `knowledge-maintenance` nocturne
- **Intelligence Mémoire** — score de pertinence, suivi des accès, élagage automatique des entrées obsolètes
- **10 patterns d'orchestration** — solo, séquentiel, parallèle, hiérarchique, réseau, boucle, routeur, agrégateur, vague, human-in-the-loop
- **Cycle de vie SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Auto-réparation** — détection autonome d'incidents, triage et auto-réparation
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
<strong>Accueil — 8 Groupes d'Idéation (CTO Jarvis, Business, Projet, Knowledge, Architecture, Sécurité, Data & IA, PI Planning)</strong><br>
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
<tr>
<td width="50%">
<strong>Marketplace — Découvrir & Lancer des Agents (/marketplace)</strong><br>
<img src="docs/screenshots/fr/marketplace.png" alt="Marketplace" width="100%">
</td>
<td width="50%">
<strong>Métriques LLM — Tableau de bord Coût/Latence (/metrics)</strong><br>
<img src="docs/screenshots/fr/metrics.png" alt="Métriques LLM" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Workspaces — Isolation Multi-Tenant (/workspaces)</strong><br>
<img src="docs/screenshots/fr/workspaces.png" alt="Workspaces" width="100%">
</td>
<td width="50%">
<strong>Tool Builder — Création d'Outils Sans Code (/tool-builder)</strong><br>
<img src="docs/screenshots/fr/tool_builder.png" alt="Tool Builder" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Évaluations — Scoring LLM-as-Judge (/evals)</strong><br>
<img src="docs/screenshots/fr/evals.png" alt="Évaluations" width="100%">
</td>
<td width="50%">
<strong>Replay Mission — Timeline Pas-à-Pas (/missions/{id}/replay)</strong><br>
<img src="docs/screenshots/fr/mission_replay.png" alt="Replay Mission" width="100%">
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

Ouvrir http://localhost:8090 — la plateforme s'ouvre sur l'onglet **CTO Jarvis**.
Choisissez votre rôle SAFe ou commencez directement à écrire dans le chat Jarvis.

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

Ouvrir http://localhost:8090 — la plateforme s'ouvre sur l'onglet **CTO Jarvis**.

### Étape 3 : Configurer un fournisseur LLM

Sans clé API, la plateforme tourne en **mode demo** — les agents répondent avec des réponses simulées.
C'est utile pour explorer l'interface, mais les agents ne génèreront pas de vrai code ou d'analyse.

Pour activer les vrais agents IA, éditez `.env` et ajoutez **une** clé API :

```bash
# Option A : MiniMax (recommandé pour démarrer)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-votre-clé-ici

# Option B : NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-votre-clé-ici
```

Puis relancez : `make run` (Docker) ou `make dev` (local)

| Fournisseur | Variable d'env | Modeles |
|-------------|---------------|---------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Compatible OpenAI** | `OPENAI_API_KEY` | tout modèle compatible OpenAI |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

La plateforme bascule automatiquement sur les autres fournisseurs configurés en cas d'échec.

Vous pouvez aussi configurer les fournisseurs depuis la page **Settings** du dashboard (`/settings`).

## Premiers pas — Votre premier projet

Après l'installation, voici comment passer d'une idée à un projet fonctionnel :

### Voie A : Demander à CTO Jarvis (Plus rapide)

1. **Ouvrez la page d'accueil** (`/`) — la plateforme démarre sur l'onglet CTO Jarvis
2. **Tapez votre idée ou question** — ex. *"Crée un nouveau projet pour une application de covoiturage d'entreprise avec React et Python"*
3. **Jarvis (Gabriel Mercier, Orchestrateur Stratégique)** analyse la demande, crée le projet, provisionne le backlog SAFe et démarre la première mission — tout en une seule conversation

C'est le **point d'entrée recommandé** pour tout nouveau projet.

### Voie B : Ateliers d'Idéation (8 Groupes Spécialisés)

La page d'accueil propose **8 contextes d'idéation**, chacun avec une équipe d'agents spécialisés :

| Groupe | Agents | Domaine |
|--------|--------|---------|
| **CTO Jarvis** | Gabriel Mercier (Orchestrateur Stratégique) | Stratégie technique, décisions architecture, audits SAST, vue portfolio |
| **Idéation Business** | CMO Sophie Laurent + 5 agents marketing | Go-to-market, SWOT, stratégie de marque, pitch investisseur |
| **Idéation Projet** | PM + Architecte + Dev Backend + QA + SRE | Spécification technique, décomposition epic/feature, choix stack |
| **Knowledge & Recherche** | Knowledge Manager + Wiki Maintainer | Analyse des lacunes, construction wiki, synthèse de recherche |
| **Comité Architecture** | Solution Architect + Tech Lead | Revues ADR, choix technologiques, dépendances inter-équipes |
| **Conseil Sécurité** | Security Analyst + Penetration Tester | Modélisation des menaces, tests de pénétration, conception RBAC |
| **Data & IA** | Data Engineer + ML Engineer | Conception pipelines ML, architecture data, stratégie intégration LLM |
| **PI Planning** | RTE + Product Owner + Scrum Master | Planification Program Increment, allocation capacité, cartographie dépendances |

Pour chaque groupe : décrivez votre besoin → les agents diffusent leur analyse → exportez en epic/projet/ADR/plan.

### Voie C : Explorer le Marketplace d'Agents

Allez sur `/marketplace` pour découvrir les 191 agents. Filtrez par ART, rôle ou compétences. Cliquez sur un agent pour voir son profil complet — outils, compétences, sessions récentes — et lancer une session directe.

### Voie D : Créer un Projet Manuellement

1. Allez sur `/projects` et cliquez **"Nouveau Projet"**
2. Remplissez : nom, description, stack technique, chemin du dépôt
3. La plateforme crée automatiquement :
   - Un **agent Product Manager** assigné au projet
   - Une **mission TMA** (maintenance continue — surveille la santé, crée des incidents)
   - Une **mission Sécurité** (audits de sécurité hebdomadaires — SAST, vérification des dépendances)
   - Une **mission Dette Technique** (réduction mensuelle de la dette — planifiée)

### Ensuite : Créer des Epics et Features

- Depuis la page **Portfolio** (`/portfolio`), créez des epics avec priorisation WSJF
- Depuis un epic, ajoutez des **features** et décomposez-les en **user stories**
- Utilisez le **PI Board** (`/pi-board`) pour planifier les incréments programme et assigner les features aux sprints

### Lancer des missions

- Cliquez **"Démarrer"** sur une mission pour lancer l'exécution des agents
- Choisissez un **pattern d'orchestration** (hiérarchique, réseau, parallèle...)
- Suivez le travail des agents en temps réel depuis **Mission Control**
- Les agents utilisent leurs outils (code_read, git, build, test, security scan) de manière autonome
- Rejouez toute mission passée à `/missions/{id}/replay` — pas-à-pas avec tokens, coût, durée par agent

## Fonctionnalités

### 191 Agents IA Spécialisés

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

### Cycle de Vie Aligné SAFe

Hiérarchie complète Portfolio → Epic → Feature → Story avec :

- **Portfolio Stratégique** — canvas portfolio, thèmes stratégiques, value streams
- **Program Increment** — planification PI, objectifs, dépendances
- **Team Backlog** — user stories, tâches, critères d'acceptation
- **Sprint Execution** — daily standups, sprint reviews, rétrospectives

### Sécurité & Conformité

- **Authentification** — auth JWT avec RBAC
- **Garde injection prompt** — détection et blocage prompts malveillants
- **Masquage secrets** — redaction automatique données sensibles
- **CSP (Content Security Policy)** — headers durcis
- **Rate limiting** — quotas API par utilisateur
- **Audit logging** — logs d'activité complets

### Métriques DORA & Monitoring

- **Deployment frequency** — fréquence du code en production
- **Lead time** — durée commit vers déploiement
- **MTTR** — temps moyen de récupération des incidents
- **Change failure rate** — pourcentage de déploiements échoués
- **Dashboards temps réel** — visualisations Chart.js
- **Métriques Prometheus** — endpoint /metrics

### Métriques Qualité — Monitoring Industriel

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

### 4 Missions Auto-Provisionnées par Projet

Chaque projet reçoit automatiquement 4 missions opérationnelles :

| Mission | Type | Fréquence | Description |
|---------|------|-----------|-------------|
| **MCO/TMA** | Programme | Continue | Monitoring santé, triage incidents (P0-P4), correctif TDD, validation non-régression |
| **Sécurité** | Revue | Hebdomadaire | Scans SAST (bandit/semgrep), audit dépendances, veille CVE |
| **Dette Technique** | Réduction | Mensuelle | Audit complexité, priorisation WSJF, sprints refactoring |
| **Self-Healing** | Programme | Continue | Pipeline autonome : détection 5xx → mission TMA → diagnostic agent → correctif code → validation |

### Amélioration Continue

Trois workflows intégrés pour l'auto-amélioration :

| Workflow | Objectif | Agents |
|----------|---------|--------|
| **quality-improvement** | Scan → identifier pires dimensions → planifier et exécuter améliorations | QA Lead, Dev, Architecte |
| **retrospective-quality** | Rétro sprint : ROTI, incidents, métriques qualité → actions | Scrum Master, QA, Dev |
| **skill-evolution** | Analyser performance agents → mettre à jour prompts → évoluer skills | Brain, Lead Dev, QA |

Ces workflows créent une **boucle de feedback** : métriques → analyse → amélioration → re-scan → suivi progrès.

### Outils Intégrés des Agents

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

### Auto-Réparation & Self-Healing (TMA)

Cycle autonome de détection, triage et réparation d'incidents :

- **Heartbeat monitoring** — vérification continue de la santé des missions et services
- **Détection auto d'incidents** — HTTP 5xx, timeout, crash agent → création automatique d'incident
- **Triage & classification** — sévérité (P0-P3), analyse d'impact, hypothèse cause racine
- **Auto-réparation** — les agents diagnostiquent et corrigent autonomement (patches, config, restarts)
- **Création de tickets** — incidents non résolus → tickets trackés pour revue humaine
- **Escalade** — P0/P1 déclenche notifications Slack/Email à l'équipe d'astreinte
- **Boucle rétrospective** — apprentissages post-incident stockés en mémoire, injectés dans les sprints futurs

### Perspectives SAFe & Onboarding

Interface adaptative par rôle SAFe :

- **9 perspectives SAFe** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Dashboard adaptatif** — KPIs, actions rapides et sidebar varient selon le rôle sélectionné
- **Wizard d'onboarding** — parcours 3 étapes (choisir rôle → choisir projet → démarrer)
- **Sélecteur de perspective** — changer de rôle SAFe depuis la topbar
- **Sidebar dynamique** — navigation filtrée selon la perspective courante

### Mémoire 4 Couches & RLM Deep Search

Connaissance persistante inter-sessions avec recherche intelligente :

- **Mémoire session** — contexte conversationnel
- **Mémoire pattern** — apprentissages des exécutions de patterns d'orchestration
- **Mémoire projet** — connaissances par projet (décisions, conventions, architecture)
- **Mémoire globale** — connaissances organisationnelles cross-projets (FTS5)
- **Fichiers projet auto-chargés** — CLAUDE.md, SPECS.md, VISION.md injectés dans chaque prompt LLM (max 8K)
- **RLM Deep Search** — boucle itérative WRITE-EXECUTE-OBSERVE-DECIDE (jusqu'à 10 itérations)

### Mercato Agents (Marché des Transferts)

Place de marché à tokens pour la composition d'équipes :

- **Listings agents** — mettre des agents en vente avec prix demandé
- **Pool agents libres** — agents non assignés disponibles au draft
- **Transferts & prêts** — acheter, vendre ou prêter des agents entre projets
- **Valorisation marché** — valorisation automatique basée sur skills et performance
- **Système de wallets** — portefeuilles tokens par projet avec historique

### Garde Qualité Adversariale

Porte de qualité double couche bloquant le code fake/placeholder :

- **L0 Déterministe** — détection instantanée de slop, mocks, fake builds, hallucinations, erreurs de stack
- **L1 Sémantique LLM** — revue qualité par LLM séparé sur les sorties d'exécution
- **Rejet forcé** — hallucinations et erreurs de stack toujours bloquées

### Auto-Documentation & Wiki

Génération automatique de documentation tout au long du cycle :

- **Rétrospectives sprint** — notes retro générées par LLM, stockées en mémoire et injectées dans les sprints suivants
- **Résumés de phases** — documentation automatique des décisions et résultats de chaque phase mission
- **Sync Confluence** — synchronisation bidirectionnelle avec les pages wiki Confluence
- **Swagger auto-docs** — 94 endpoints REST auto-documentés sur `/docs`

### Système de Gestion des Connaissances

Sous-système dédié à la connaissance organisationnelle, introduit en v2.7.0 :

- **4 agents spécialisés** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **Équipe ART Knowledge** — Agile Release Train dédié aux opérations de connaissance
- **Workflow nocturne `knowledge-maintenance`** — curation automatique, déduplication, score de fraîcheur
- **Dashboard Santé Mémoire** — métriques de santé des connaissances dans l'onglet Métriques
- **Badge Santé des Connaissances** — visible dans la page Paramètres
- **Formule de score de pertinence** — `confiance × récence × boost_accès` pour le classement intelligent
- **Suivi des accès** — champs `access_count` et `last_read_at` sur chaque entrée mémoire
- **Élagage automatique** — entrées obsolètes supprimées à chaque exécution nocturne

### Hub d'Intégrations Paramètres

Intégrations d'outils configurables disponibles pour tous les agents :

- **Outils supportés** — Jira, Confluence, SonarQube et plus
- **Directives domaine BSCC** — directives d'architecture (Confluence/Solaris) appliquées par domaine de projet
- **Export/Import Projet** — archive ZIP contenant `project.json` + missions + exécutions + mémoires
- **Notifications Push Navigateur** — notifications push natives via Web Push API (VAPID)
- **Validation des Entrées** — modèles Pydantic sur toutes les routes POST/PATCH

### Marketplace d'Agents

Découvrez, filtrez et lancez n'importe lequel des 191 agents depuis un catalogue unique à `/marketplace` :

- **Filtrer par ART, rôle ou compétences** — trouvez rapidement l'agent adapté à chaque tâche
- **Profils agents** — vue détaillée : prompt système, outils, compétences, sessions récentes
- **Lancement en un clic** — démarrez une conversation directe avec n'importe quel agent
- **Navigation par groupes** — visualisez les agents organisés par Agile Release Train

### Dashboard Métriques LLM

Observabilité en temps réel de tous les usages LLM à `/metrics` :

- **Suivi des coûts** — dépenses par agent, par mission, par provider
- **Monitoring de latence** — P50/P95/P99 par modèle et provider
- **Comparaison providers** — coût/latence/qualité côte à côte entre providers
- **Alertes budget tokens** — seuils configurables avec avertissements sur le dashboard

### Framework d'Évaluation des Agents

Système de scoring LLM-as-judge à `/evals` :

- **Dataset golden** — cas de test curés avec sorties attendues
- **Scoring automatisé** — le juge LLM évalue les réponses des agents par rapport à la vérité terrain
- **Benchmarks par agent** — suivez les scores de qualité dans le temps et entre versions
- **Détection de régressions** — alertes sur les baisses de qualité après modification des prompts

### Tool Builder

Création d'outils sans code à `/tool-builder` :

- **Outils HTTP** — configurez des appels REST avec headers, auth et mapping de réponse
- **Outils SQL** — écrivez des requêtes SQL que les agents peuvent exécuter sur des bases configurées
- **Outils Shell** — encapsulez des commandes shell en outils appelables par les agents
- **Activation instantanée** — nouveaux outils disponibles pour les agents immédiatement après sauvegarde

### Workspaces Multi-Tenant

Namespaces de projet isolés à `/workspaces` :

- **Isolation namespace** — données, agents et mémoire séparés par workspace
- **Déploiement par client** — embarquez plusieurs clients sans contamination croisée
- **Changement de contexte** — basculez entre workspaces sans déconnexion
- **RBAC par workspace** — assignations de rôles granulaires par namespace

### Replay de Mission

Replay pas-à-pas de l'exécution des missions à `/missions/{id}/replay` :

- **Historique d'exécution complet** — chaque tour d'agent, appel outil et réponse LLM
- **Coût et tokens par étape** — visualisez exactement ce que chaque agent a dépensé
- **Détail des durées** — vue timeline montrant où le temps a été passé
- **Exportable** — téléchargez le replay en JSON pour analyse ou débogage

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
sf agents list                         # 191 agents
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
          │ 191 agents   │   │ 36 defs  │   │ Cycle SAFe   │
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
Docker (recommandé) → http://localhost:8090
Local (dev)         → http://localhost:8090
Production          → votre propre infrastructure
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

## Nouveautés v2.7.0 (2026)

### Système de Gestion des Connaissances
- **4 nouveaux agents** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **Équipe ART Knowledge** — Agile Release Train dédié aux opérations de connaissance
- **Workflow nocturne `knowledge-maintenance`** — curation automatique, déduplication, score de fraîcheur
- **Dashboard Santé Mémoire** — panel de métriques dans l'onglet Métriques
- **Badge Santé des Connaissances** — visible dans la page Paramètres

### Intelligence Mémoire
- **Score de pertinence** — formule `confiance × récence × boost_accès` pour la récupération classée
- **Suivi des accès** — champs `access_count` et `last_read_at` sur chaque entrée mémoire
- **Élagage automatique** — entrées obsolètes supprimées à chaque exécution nocturne

### Suivi Coût LLM
- **Coût par mission** — affiché dans l'en-tête de l'onglet timeline de mission
- **Agrégation automatique** — calculé depuis la table `llm_traces`, aucun suivi manuel nécessaire

### Timeline Mission
- **Onglet timeline en couloirs** — dans Mission Control, affiche les phases agent en couloirs horizontaux
- **Durées de phases** — représentation visuelle du temps passé dans chaque phase

### Score Qualité
- **Champ `quality_score` sur PhaseRun** — renseigné par la garde adversariale après chaque phase

### Export/Import Projet
- **Archive ZIP** — contient `project.json` + toutes les missions + exécutions + mémoires

### Validation des Entrées
- **Modèles Pydantic** — toutes les routes POST/PATCH validées avec des schémas stricts

### Directives Domaine BSCC
- **Directives d'architecture par domaine** — Confluence/Solaris appliquées par domaine de projet

### Hub d'Intégrations Paramètres
- **Intégrations configurables** — Jira, Confluence, SonarQube disponibles pour tous les agents depuis un panel unique

### Notifications Push Navigateur
- **Web Push API (VAPID)** — notifications push natives pour les événements de mission et alertes

## Nouveautés v3.0.0 (2026)

### Marketplace d'Agents
- **191 agents catalogués** — recherche plein-texte, filtre par ART/rôle/compétences à `/marketplace`
- **Profils agents** — vue détaillée avec outils, compétences et historique des sessions récentes
- **Lancement en un clic** — démarrez une session directe avec n'importe quel agent depuis son profil

### Replay de Mission
- **Replay pas-à-pas** — chaque tour d'agent et appel outil rejoué à `/missions/{id}/replay`
- **Coût et tokens par étape** — détail granulaire des dépenses LLM par agent
- **Historique exportable** — téléchargez le replay en JSON pour débogage et audit

### Dashboard Métriques LLM
- **Monitoring coût/latence/provider en temps réel** à `/metrics`
- **Dépenses par agent et par mission** — identifiez les agents coûteux et optimisez
- **Comparaison providers** — P50/P95 latence et coût côte à côte entre providers

### RBAC + Rate Limiting
- **RBAC par workspace** — assignations de rôles par workspace, pas seulement par plateforme
- **Rate limiting par utilisateur** — quotas tokens/requêtes configurables par rôle
- **Piste d'audit** — toutes les modifications RBAC enregistrées avec acteur, horodatage et détail

### Framework d'Évaluation des Agents
- **Scoring LLM-as-judge** — évaluation automatisée sur datasets golden à `/evals`
- **Benchmarks par agent** — suivez la qualité dans le temps et détectez les régressions
- **Juges configurables** — utilisez n'importe quel provider LLM configuré comme juge d'évaluation

### Tool Builder
- **Création d'outils sans code** à `/tool-builder` — outils HTTP, SQL et shell
- **Activation instantanée** — outils disponibles pour les agents immédiatement après sauvegarde
- **Templates de paramètres** — définissez des schémas d'entrée avec types et validation

### Workspaces Multi-Tenant
- **Namespaces isolés** à `/workspaces` — données, agents et mémoire séparés par workspace
- **Déploiement par client** — embarquez plusieurs clients sans contamination croisée
- **RBAC par workspace** — assignations de rôles granulaires par namespace

### Rechargement à Chaud des Agents YAML
- **Mises à jour agents en direct** — modifiez les fichiers YAML des agents et rechargez sans redémarrer
- **Zéro interruption** — les missions en cours continuent avec la définition précédente de l'agent

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

- Live : https://sf.macaron-software.com
- Issues : https://github.com/macaron-software/software-factory/issues
- Discussions : https://github.com/macaron-software/software-factory/discussions
