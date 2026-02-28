# Plateforme Multi-Agents — La Poste

**Plateforme d'orchestration d'agents IA pour le cycle de vie logiciel**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Usage interne](https://img.shields.io/badge/Usage-La%20Poste%20UDD%20IA%20Native-yellow.svg)]()

---

## Présentation

Cette plateforme permet l'orchestration d'agents IA autonomes pour accompagner les équipes de développement dans le cycle de vie logiciel : idéation, conception, développement, tests, déploiement.

Elle s'inscrit dans le cadre de la démarche **UDD IA Native** et suit la méthodologie SAFe.

### Capacités principales

- **Agents IA spécialisés** — architectes, développeurs, testeurs, product owners, SRE
- **Patterns d'orchestration** — solo, séquentiel, parallèle, hiérarchique, réseau, boucle, routeur, agrégateur
- **Cycle de vie SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Interface web** — FastAPI + HTMX, pas de framework frontend, SSE temps réel
- **Mémoire multi-couches** — par session, par pattern, par projet, globale (FTS PostgreSQL)

---

## Nouvelles fonctionnalités v2.3.0

### CTO Jarvis — Conseiller IA Stratégique

![CTO Jarvis](docs/screenshots/fr/jarvis.png)

L'onglet **CTO Jarvis** (accessible depuis la page d'accueil `/`) offre un panneau de chat persistant avec un conseiller IA de niveau directeur technique :

- **Mémoire persistante** — les décisions techniques et contextes de session sont conservés entre les conversations
- **Conseiller stratégique** — aide à la prise de décision architecturale, choix technologiques, arbitrages
- **Intégration plateforme** — connait l'état du portfolio, les projets en cours et les équipes agents
- **Accessible depuis** : Accueil → onglet CTO Jarvis

#### Capacités outils

| Domaine | Outils disponibles |
|---------|-------------------|
| **Code** | Lire, chercher, éditer, écrire, lister fichiers |
| **Git** | Commit, diff, log, status · GitHub issues / PRs / search |
| **Build / Deploy** | Build, lint, test, deploy, Docker, run_command, infra |
| **Sécurité** | SAST, secrets scan, audit dépendances |
| **MCPs** | Web fetch, Knowledge graph, Playwright browser, GitHub |
| **Projet** | Jira, Confluence, phases SAFe, LRM context |
| **Mémoire** | Lecture + écriture Knowledge graph |

#### Raccourcis contextuels (chips)

`Stats portfolio` · `Missions en cours` · `Monter une équipe` · `GitHub` · `AO Veligo` · `Migration Angular 16→17` · `Dette tech · sécu · a11y · RGPD` · `Git commit & PR` · `E2E + Screenshots` · `Sync Jira` · `Mise à jour Wiki`

#### Exemples de questions

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

### Idéation Business (`/mkt-ideation`) — Équipe Marketing IA

![Idéation Business](docs/screenshots/fr/mkt_ideation.png)

L'onglet **Idéation Business** déploie une équipe de 6 agents marketing pilotée par Sophie Laurent (CMO) :

| Agent | Rôle |
|-------|------|
| Sophie Laurent | CMO — chef d'équipe marketing |
| Alex Dupont | Analyste SWOT & marché |
| Marie Chen | Stratège TAM/SAM/SOM |
| Pierre Martin | Responsable brand strategy |
| Julie Bernard | Experte go-to-market |
| Luc Rousseau | Analyste KPIs & budget |

- **Sortie structurée** — génère un plan marketing complet en JSON : SWOT, TAM/SAM/SOM, stratégie de marque, go-to-market, KPIs, budget
- **Graphe d'agents** — visualisation des agents avec photos avatars, arêtes de collaboration et popovers détaillés
- **Accessible depuis** : Accueil → onglet Idéation Business

### Idéation Projet (`/ideation`) — Équipe Tech Multi-Agents

![Idéation Projet](docs/screenshots/fr/ideation_projet.png)

L'onglet **Idéation Projet** orchestre un PM et 4 experts techniques pour transformer une idée en Epic SAFe :

- **Équipe de 5 agents** — Product Manager + Architecte + Dev Backend + QA + SRE
- **Sortie Epic** — génère automatiquement une Epic structurée avec Features, Stories et critères d'acceptance
- **Graphe interactif** — graphe ig-node avec cartes d'agents, photos avatars et popovers de contexte
- **Accessible depuis** : Accueil → onglet Idéation Projet

### Navigation Restructurée

La navigation a été reorganisée autour de deux pages principales :

| Page | URL | Onglets |
|------|-----|---------|
| **Accueil** | `/` | CTO Jarvis · Idéation Business · Idéation Projet |
| **Dashboard** | `/portfolio` | Vue d'ensemble · DSI · Business |

La sidebar latérale ne comporte plus que ces deux entrées, simplifiant l'accès aux fonctionnalités principales.

### Migration PostgreSQL

La base de données a migré de SQLite vers **PostgreSQL** :

- **Scripts de migration complets** — migration de schéma et de données inclus
- **FTS natif PostgreSQL** — recherche plein texte via `tsvector/tsquery` (plus performante)
- **40+ index PG** — couverture complète des chemins de requêtes chauds
- **Darwin Teams** — Thompson Sampling pour la sélection d'équipes agents par contexte (technologie + phase)

---

## Captures d'écran

<table>
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
<tr>
<td width="50%">
<strong>Dashboard — Perspective SAFe Adaptative</strong><br>
<img src="docs/screenshots/fr/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Idéation — Brainstorming Multi-Agents IA</strong><br>
<img src="docs/screenshots/fr/ideation.png" alt="Idéation" width="100%">
</td>
</tr>
</table>

---

## Intelligence Adaptative

La plateforme intègre trois moteurs d'IA qui s'auto-optimisent en continu pour sélectionner la meilleure équipe, le meilleur pattern et la meilleure configuration de workflow pour chaque mission.

### Thompson Sampling — Sélection Probabiliste

Darwin sélectionne les équipes agent+pattern via un bandit bayésien :

- **Beta(wins+1, losses+1)** par contexte `(agent_id, pattern_id, technologie, type_phase)`
- Score de fitness distinct par contexte (pas de contamination inter-contextes)
- Fallback cold-start par préfixe technologique (`angular_19` → `angular_*` → `generic`)
- Tests A/B en shadow automatiques ; évaluateur neutre choisit le gagnant
- Étendu aux modèles LLM (Darwin LLM) : le meilleur fournisseur s'impose par contexte

### Algorithme Génétique — Évolution des Workflows

Le moteur GA (`platform/agents/evolution.py`) fait évoluer les templates de workflows chaque nuit :

| Paramètre | Valeur |
|-----------|--------|
| Taille population | 40 génomes |
| Générations max | 30 |
| Taux de mutation | 15% |
| Élitisme | 2 génomes |
| Sélection | Tournoi k=3 |

- **Génome** = liste ordonnée de `PhaseSpec` (pattern, agents, gate)
- **Fitness** = taux réussite phases × score agents × (1 − taux veto) × bonus lead time
- **Propositions** top-3 soumises à revue humaine avant application (`evolution_proposals`)
- **Déclenchement manuel** : `POST /api/evolution/run/{wf_id}`
- **Vue** : Workflows → onglet Évolution

### Reinforcement Learning — Adaptation en Temps Réel

La politique Q-learning (`platform/agents/rl_policy.py`) recommande des changements de pattern pendant l'exécution :

- **Actions** : keep, switch_parallel, switch_sequential, switch_hierarchical, switch_debate, add_agent, remove_agent
- **État** : `(wf_id, position_phase, taux_rejet, score_qualité)` — discrétisé en buckets
- **Mise à jour Q** : α=0.1, γ=0.9, ε=0.1 — entraînement offline sur la table `rl_experience`
- Recommandation déclenchée seulement si confiance ≥ 70% et ≥ 3 visites d'état
- Dégradation gracieuse vers le pattern par défaut

### OKR / KPI — Objectifs et Indicateurs

Les OKR servent de signal de fitness pour le GA et de récompense pour le RL :

| Domaine | OKR type | Indicateurs |
|---------|----------|-------------|
| code/migration | ≥90% build success | build_pass_rate, coverage |
| sécurité | 0 CVE critique | cve_count, sast_score |
| architecture | revue <2h | review_duration |
| tests | ≥95% pass | pass_rate, regressions |
| documentation | 100% API couverte | doc_coverage |

- 8 seeds par défaut pré-chargés au démarrage
- Édition inline sur `/teams` (vert/amber/rouge)
- Surchargeables par projet dans les Paramètres

---

## Architecture

```
FastAPI + HTMX + SSE (pas de WebSocket, pas de build frontend)
PostgreSQL + FTS natif (tsvector/tsquery)
LLM : Azure OpenAI (gpt-4o / gpt-5-mini)
```

```
platform/
├── agents/        ← Boucle d'exécution, evolution.py (GA), rl_policy.py (RL)
├── patterns/      ← Moteur d'orchestration (8 types)
├── missions/      ← SAFe lifecycle + Product Backlog
├── workflows/     ← Templates de cérémonie + Evolution
├── llm/           ← Client multi-provider + Darwin LLM
├── memory/        ← Gestionnaire mémoire 4 couches
├── web/           ← Routes FastAPI + templates Jinja2
└── db/            ← Migrations PostgreSQL (40+ index)
```

---

## Démarrage rapide

### Prérequis

- Python 3.10+
- PostgreSQL 14+
- Azure OpenAI (endpoint + clé API)

### Installation

```bash
# Cloner le repo
git clone <GITLAB_URL>/software-factory.git
cd software-factory

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env : AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, DATABASE_URL

# Lancer la plateforme
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Accès : http://localhost:8090

### Docker

```bash
make setup
make run
```

---

## Configuration

Variables d'environnement (`.env`) :

```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
PLATFORM_LLM_PROVIDER=azure-openai
PLATFORM_LLM_MODEL=gpt-5-mini
DATABASE_URL=postgresql://user:password@localhost:5432/software_factory
```

---

## Structure du squelette

Ce repo est un **squelette** — les définitions d'agents (`platform/skills/definitions/`),
les workflows (`platform/workflows/definitions/`) et les projets (`projects/`) sont vides.

Pour démarrer, ajoutez vos propres :
- Définitions d'agents dans `platform/skills/definitions/*.yaml`
- Workflows dans `platform/workflows/definitions/*.yaml`
- Projets dans `projects/*.yaml`

Voir `platform/skills/definitions/_template.yaml` pour le format.

---
