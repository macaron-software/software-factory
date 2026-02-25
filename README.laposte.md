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

## Architecture

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
