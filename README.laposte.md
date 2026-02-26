# Plateforme Multi-Agents — La Poste

**Plateforme d'orchestration d'agents IA pour le cycle de vie logiciel**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Usage interne](https://img.shields.io/badge/Usage-Interne%20La%20Poste-yellow.svg)]()

---

## Présentation

Cette plateforme permet l'orchestration d'agents IA autonomes pour accompagner les équipes de développement dans le cycle de vie logiciel : idéation, conception, développement, tests, déploiement.

Elle s'inscrit dans le cadre de la démarche **UDD IA Native** et suit la méthodologie SAFe.

### Capacités principales

- **Agents IA spécialisés** — architectes, développeurs, testeurs, product owners, SRE
- **Patterns d'orchestration** — solo, séquentiel, parallèle, hiérarchique, réseau, boucle, routeur, agrégateur
- **Cycle de vie SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Interface web** — FastAPI + HTMX, pas de framework frontend, SSE temps réel
- **Mémoire multi-couches** — par session, par pattern, par projet, globale (FTS5)

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
SQLite WAL + FTS5
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
└── db/            ← Migrations SQLite
```

---

## Démarrage rapide

### Prérequis

- Python 3.10+
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
# Éditer .env : AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT

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

## Usage interne

Ce projet est à usage interne La Poste — UDD IA Native.
Toute diffusion externe est soumise à validation de la DSI.


```
FastAPI + HTMX + SSE (pas de WebSocket, pas de build frontend)
SQLite WAL + FTS5
LLM : Azure OpenAI (gpt-4o / gpt-5-mini)
```

```
platform/
├── agents/        ← Boucle d'exécution, outils, mémoire
├── patterns/      ← Moteur d'orchestration (8 types)
├── missions/      ← SAFe lifecycle + Product Backlog
├── workflows/     ← Templates de cérémonie
├── llm/           ← Client multi-provider
├── memory/        ← Gestionnaire mémoire 4 couches
├── web/           ← Routes FastAPI + templates Jinja2
└── db/            ← Migrations SQLite
```

---

## Démarrage rapide

### Prérequis

- Python 3.10+
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
# Éditer .env : AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT

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

## Usage interne

Ce projet est à usage interne La Poste — UDD IA Native.
Toute diffusion externe est soumise à validation de la DSI.
