# Plateforme Agents IA — La Poste

**Plateforme d'orchestration d'agents IA pour le cycle de vie logiciel**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Usage interne](https://img.shields.io/badge/Usage-La%20Poste%20UDD%20IA%20Native-yellow.svg)]()

---

## Presentation

Cette plateforme permet l'orchestration d'agents IA autonomes pour accompagner les equipes de developpement dans le cycle de vie logiciel : ideation, conception, developpement, tests, deploiement.

Elle s'inscrit dans le cadre de la demarche **UDD IA Native** et suit la methodologie SAFe (Scaled Agile Framework).

### Chiffres cles v3.0.0

- 192 agents IA specialises
- 33 equipes agents
- 10 ARTs (Agile Release Trains)
- 8 groupes d'ideation sur la page d'accueil
- 46 workflows de ceremonie

---

## Fonctionnalites principales

### Page d'accueil — 8 groupes d'ideation

La page d'accueil (`/`) propose 8 onglets couvrant l'ensemble du cycle strategique et technique :

| Onglet | Role |
|--------|------|
| **CTO Jarvis** | Conseiller IA strategique — point d'entree recommande |
| **Ideation Business** | Equipe marketing 6 agents, plans SWOT/TAM/KPI |
| **Ideation Projet** | Equipe tech 5 agents, creation d'Epics SAFe |
| **Knowledge & Recherche** | Veille technologique et analyse documentaire |
| **Comite Architecture** | Revue et decision architecturale multi-agents |
| **Conseil Securite** | Audit securite, SAST, analyse CVE |
| **Data & IA** | Analyse de donnees, MLOps, gouvernance IA |
| **PI Planning** | Planification des Program Increments SAFe |

### CTO Jarvis — Conseiller IA Strategique

L'onglet **CTO Jarvis** est le **point d'entree recommande** pour tout nouveau projet. Jarvis (Gabriel Mercier, orchestrateur strategique) analyse votre demande, cree le projet, provisionne le backlog SAFe et lance la premiere mission — le tout en une seule conversation.

**Capacites outils de Jarvis** :

| Domaine | Outils disponibles |
|---------|-------------------|
| **Code** | Lire, chercher, editer, ecrire, lister fichiers |
| **Git** | Commit, diff, log, status, issues / PRs / search |
| **Build / Deploy** | Build, lint, test, deploy, Docker, run_command, infra |
| **Securite** | SAST, secrets scan, audit dependances |
| **MCPs** | Web fetch, Knowledge graph, Playwright, plateforme interne |
| **Projet** | Jira, Confluence, phases SAFe, contexte LRM |
| **Memoire** | Lecture + ecriture Knowledge graph |

**Exemples de questions a Jarvis** :

> *« Cree un nouveau projet pour une application de covoiturage d'entreprise avec React et Python. »*

> *« Quel est l'etat de sante global du portfolio ? Quels projets sont en retard ? »*

> *« Lance un audit SAST sur le projet Veligo et dis-moi les 3 CVE critiques a traiter en priorite. »*

> *« On doit migrer l'API de REST vers GraphQL — quelle equipe d'agents recommandes-tu ? »*

> *« Quelle est notre dette technique actuelle ? Priorise les items par impact/effort. »*

> *« Compare nos metriques DORA ce mois-ci vs le mois dernier — ou regressons-nous ? »*

### Marche d'Agents (`/marketplace`)

Catalogue de tous les 192 agents avec recherche plein texte et filtres par ART, role et competences. Chaque agent dispose d'un profil detail avec ses outils, ses competences et son historique de sessions recent.

### Tableau de Bord LLM (`/metrics`)

Surveillance en temps reel des couts, latences et utilisation par fournisseur. Permet d'identifier les agents couteux, de comparer les fournisseurs LLM et d'optimiser les depenses par mission.

### Relecture de Mission (`/missions/{id}/replay`)

Rejoue pas a pas chaque tour d'agent et chaque appel d'outil d'une mission terminee. Affiche le cout et les tokens par etape. Exportable en JSON pour le debogage et l'audit.

### Cadre d'Evaluation d'Agents (`/evals`)

Evaluation automatisee des agents contre des jeux de donnees de reference (LLM-as-judge). Suivi de la qualite dans le temps, detection de regressions, juges configurables par fournisseur LLM.

### Constructeur d'Outils (`/tool-builder`)

Creation d'outils personnalises sans code : HTTP, SQL, shell. Les outils sont disponibles pour les agents immediatement apres enregistrement. Definition des schemas de parametres avec types et validation.

### Espaces de Travail Multi-Tenants (`/workspaces`)

Espaces de noms isoles avec donnees, agents et memoire separes. Permet d'onboarder plusieurs entites ou projets sensibles sans contamination croisee. RBAC granulaire par espace de travail.

---

## Captures d'ecran

<table>
<tr>
<td width="50%">
<strong>Accueil — 8 onglets d'ideation</strong><br>
<img src="docs/screenshots/fr/home.png" alt="Accueil" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — Conseiller IA Strategique</strong><br>
<img src="docs/screenshots/fr/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Ideation Business — Equipe Marketing 6 Agents</strong><br>
<img src="docs/screenshots/fr/mkt_ideation.png" alt="Ideation Business" width="100%">
</td>
<td width="50%">
<strong>Ideation Projet — Equipe Tech Multi-Agents</strong><br>
<img src="docs/screenshots/fr/ideation_projet.png" alt="Ideation Projet" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Marche d'Agents — Catalogue 192 agents</strong><br>
<img src="docs/screenshots/fr/marketplace.png" alt="Marche d'Agents" width="100%">
</td>
<td width="50%">
<strong>Tableau de Bord LLM — Couts et latences</strong><br>
<img src="docs/screenshots/fr/metrics.png" alt="Metriques LLM" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Evaluation Agents — Benchmarks qualite</strong><br>
<img src="docs/screenshots/fr/evals.png" alt="Evaluations" width="100%">
</td>
<td width="50%">
<strong>Constructeur d'Outils — Creation sans code</strong><br>
<img src="docs/screenshots/fr/tool_builder.png" alt="Constructeur Outils" width="100%">
</td>
</tr>
</table>

---

## Intelligence Adaptative

La plateforme integre trois moteurs d'IA qui s'auto-optimisent en continu.

### Thompson Sampling — Selection Probabiliste

Darwin selectionne les equipes agent+pattern via un bandit bayesien :

- **Beta(wins+1, losses+1)** par contexte `(agent_id, pattern_id, technologie, type_phase)`
- Score de fitness distinct par contexte (pas de contamination inter-contextes)
- Fallback cold-start par prefixe technologique (`angular_19` vers `angular_*` vers `generic`)
- Tests A/B en shadow automatiques ; evaluateur neutre choisit le gagnant
- Etendu aux modeles LLM (Darwin LLM) : le meilleur fournisseur s'impose par contexte

### Algorithme Genetique — Evolution des Workflows

Le moteur GA (`platform/agents/evolution.py`) fait evoluer les templates de workflows chaque nuit :

| Parametre | Valeur |
|-----------|--------|
| Taille population | 40 genomes |
| Generations max | 30 |
| Taux de mutation | 15% |
| Elitisme | 2 genomes |
| Selection | Tournoi k=3 |

- **Genome** = liste ordonnee de `PhaseSpec` (pattern, agents, gate)
- **Fitness** = taux reussite phases x score agents x (1 — taux veto) x bonus lead time
- **Propositions** top-3 soumises a revue humaine avant application (`evolution_proposals`)

### Reinforcement Learning — Adaptation en Temps Reel

La politique Q-learning (`platform/agents/rl_policy.py`) recommande des changements de pattern pendant l'execution :

- **Actions** : keep, switch_parallel, switch_sequential, switch_hierarchical, switch_debate, add_agent, remove_agent
- **Etat** : `(wf_id, position_phase, taux_rejet, score_qualite)` — discretise en buckets
- Recommandation declenchee seulement si confiance >= 70% et >= 3 visites d'etat

---

## Architecture

```
FastAPI + HTMX + SSE (pas de WebSocket, pas de build frontend)
PostgreSQL + FTS natif (tsvector/tsquery)
LLM : fournisseur interne configurable (.env)
```

```
platform/
├── agents/        <- Boucle d'execution, evolution.py (GA), rl_policy.py (RL)
├── patterns/      <- Moteur d'orchestration (8 types)
├── missions/      <- SAFe lifecycle + Product Backlog
├── workflows/     <- Templates de ceremonie + Evolution
├── llm/           <- Client multi-provider + Darwin LLM
├── memory/        <- Gestionnaire memoire 4 couches
├── web/           <- Routes FastAPI + templates Jinja2
└── db/            <- Migrations PostgreSQL (40+ index)
```

## Securite Renforcee et Raisonnement (v3.1.0)

### Garde Adversariale L0/L1

Double couche de protection bloquant le code fake et les contenus malveillants :

- **L0 Deterministe (0ms)** : detection slop/mocks/fake builds/hallucinations + 12 mitigations CS : injection prompt, usurpation identite, PII, traversee chemin, SSRF, budget outils, sanitisation memoire, validation A2A, audit trail (arXiv:2602.20021 — 50 tests securite)
- **L1 Semi-formel** : le reveur LLM emet Premisses (preuves outils) → Trace (carte affirmation↔preuve) → Verdict, certificat de raisonnement verifie ; remontee des affirmations non verifiees (arXiv:2603.01896)
- **86 tests unitaires** : suite complete couvrant securite et raisonnement

---

## Demarrage rapide

### Prerequis

- Python 3.10+
- PostgreSQL 14+
- Fournisseur LLM interne (configurer dans `.env`)

### Installation

```bash
# Cloner le depot
git clone <DEPOT_INTERNE>/software-factory.git
cd software-factory

# Installer les dependances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Editer .env : LLM_API_KEY, LLM_ENDPOINT, DATABASE_URL

# Lancer la plateforme
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Acces : http://localhost:8090

### Docker

```bash
make setup
make run
```

---

## Configuration

Variables d'environnement (`.env`) :

```bash
PLATFORM_LLM_PROVIDER=openai-compatible
PLATFORM_LLM_MODEL=gpt-4o
LLM_API_KEY=...
LLM_ENDPOINT=https://<endpoint-interne>/
DATABASE_URL=postgresql://user:password@localhost:5432/software_factory
```

---

## Structure du squelette

Ce depot est un **squelette** — les definitions d'agents (`platform/skills/definitions/`),
les workflows (`platform/workflows/definitions/`) et les projets (`projects/`) sont vides.

Pour demarrer, ajoutez vos propres :
- Definitions d'agents dans `platform/skills/definitions/*.yaml`
- Workflows dans `platform/workflows/definitions/*.yaml`
- Projets dans `projects/*.yaml`

Voir `platform/skills/definitions/_template.yaml` pour le format.

---

## Premiers Pas — Premier Projet

Apres installation :

**Etape 1 : Ouvrir la page d'accueil** (`/`) — la plateforme demarre sur l'onglet CTO Jarvis.

**Etape 2 : Decrire votre projet** — exemple : *« Cree un nouveau projet pour une application RH interne en React et FastAPI. »*

**Etape 3 : Jarvis** analyse la demande, cree le projet, provisionne le backlog SAFe (epics, features, stories) et lance les premieres missions (TMA, Securite, Dette Technique).

**Etape 4 : Naviguer dans le portfolio** (`/portfolio`) — suivre l'avancement des projets, les missions en cours et les metriques SAFe.

---

## Support interne

- Wiki interne : Confluence — espace UDD IA Native
- Demandes et incidents : Jira — projet SFACT
- Equipe responsable : equipe UDD IA Native La Poste
