# Software Factory

[🇫🇷 Français](#français) | [🇬🇧 English](#english)

---

## Français

> Plateforme multi-agents pour le développement logiciel autonome — 145 agents, méthodologie SAFe, pipeline TDD complet.

### Vue d'ensemble

**Software Factory** est une plateforme d'orchestration multi-agents qui planifie, développe, teste et déploie des logiciels de manière autonome. Elle combine :

- **145 agents IA** (Product Manager, Architecte, Dev, QA, Sécurité, UX, DevOps...)
- **Workflow SAFe** : Epics → Features → User Stories → Sprints → Code
- **12 patterns d'orchestration** : solo, séquentiel, parallèle, hiérarchique, réseau, boucle...
- **Multi-LLM** : Claude, GPT, MiniMax, GLM — avec fallback automatique
- **Pipeline TDD complet** : Analyse Brain → Décomposition FRACTAL → Workers TDD → Revue adversariale → Déploiement

### Screenshots

![Dashboard](screenshots/02_dashboard.png)
*Dashboard temps réel avec streaming SSE des conversations multi-agents*

![Swagger API](screenshots/03_swagger.png)
*94 endpoints REST auto-documentés*

![CLI](screenshots/04_cli.png)
*Interface en ligne de commande complète (22 groupes de commandes)*

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  🧠 Brain (Claude Opus)                                          │
│  Analyse Vision → Génération tâches → Priorisation WSJF         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  Workers TDD × N    │      │  Pipeline Deploy    │
│  FRACTAL decompose  │      │  Build → Stage →    │
│  RED → GREEN →      │      │  E2E → Prod →       │
│  VERIFY → COMMIT    │      │  Rollback           │
└─────────────────────┘      └─────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  🔴 Gate Adversarial (revue multi-LLM en cascade)                │
│  L0: Scan rapide → L1: Revue code → L2: Revue architecture      │
└──────────────────────────────────────────────────────────────────┘
```

### Démarrage rapide

```bash
# Clone
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

# Installation
pip install -r requirements.txt

# Configuration API keys
mkdir -p ~/.config/factory
echo "sk-ant-..." > ~/.config/factory/anthropic.key

# Démarrer la plateforme
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Ouvrir `http://localhost:8090` — le dashboard est prêt.

### Trois interfaces

#### 1. Dashboard Web (HTMX + SSE)

Interface principale sur `http://localhost:8090` :
- Conversations multi-agents en temps réel avec streaming SSE
- PI Board, cycle de vie des missions, planification sprints
- Gestion agents, monitoring, tableau de bord incidents

#### 2. CLI (`sf`)

Interface en ligne de commande complète miroir du dashboard :

```bash
# Installation (ajouter au PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Navigation
sf status                              # Santé plateforme
sf projects list                       # Tous les projets
sf missions list                       # Missions avec scores WSJF
sf agents list                         # 145 agents
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

#### 3. API REST + Swagger

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

Swagger UI : `http://localhost:8090/docs`

### Organisation des agents

| Équipe | Agents | Rôle |
|--------|--------|------|
| Product | Product Manager, Business Analyst, PO | Planification SAFe, WSJF |
| Architecture | Solution Architect, Tech Lead | Décisions architecture |
| Développement | Agents Dev (par stack) | Implémentation TDD |
| Qualité | QA, Security Engineer | Tests, audit sécurité |
| Design | UX Designer | Expérience utilisateur |
| DevOps | DevOps, SRE | CI/CD, monitoring |
| Management | Scrum Master, RTE | Cérémonies, facilitation |

### Configuration projet

Les projets sont définis dans `projects/*.yaml` :

```yaml
project:
  name: mon-projet
  root_path: /chemin/vers/projet
  vision_doc: CLAUDE.md

domains:
  typescript:
    paths: [src/]
    build_cmd: npm run build
    test_cmd: npm run test

fractal:
  max_files: 5
  max_loc: 400

adversarial:
  threshold: 5
```

### Structure répertoires

```
├── cli/                     # sf CLI (5 fichiers, 2100+ LOC)
│   ├── sf.py                # 22 groupes commandes, 40+ sous-commandes
│   ├── _api.py              # Client REST httpx
│   ├── _db.py               # Backend offline sqlite3
│   ├── _output.py           # Tables ANSI, rendu markdown
│   └── _stream.py           # Streaming SSE avec spinner
│
├── platform/                # Plateforme Agents (FastAPI + HTMX)
│   ├── server.py            # Factory app, port 8090
│   ├── agents/              # Agent loop, executor, store
│   ├── a2a/                 # Bus messaging agent-to-agent
│   ├── patterns/            # 12 patterns orchestration
│   ├── missions/            # Cycle de vie mission SAFe
│   ├── sessions/            # Runner conversation + SSE
│   ├── web/                 # Routes + templates Jinja2
│   ├── mcp_platform/        # Serveur MCP (23 tools)
│   └── tools/               # Outils agents (code, git, deploy)
│
├── core/                    # Moteur TDD
│   ├── brain.py             # RLM Brain (Claude Opus)
│   ├── fractal.py           # Décomposition tâches
│   ├── cycle_worker.py      # Workers TDD batch
│   ├── adversarial.py       # Gate qualité multi-LLM
│   └── task_store.py        # Stockage SQLite + zlib
│
├── projects/                # Configurations projets YAML
├── data/                    # Base de données plateforme
├── screenshots/             # Screenshots documentation
└── tests/                   # Tests E2E
```

---

## English

> Multi-agent AI platform for autonomous software development — 145 agents, SAFe methodology, full TDD pipeline.

### Overview

**Software Factory** is a multi-agent orchestration platform that plans, develops, tests, and deploys software autonomously. It combines:

- **145 AI agents** (Product Manager, Architect, Dev, QA, Security, UX, DevOps...)
- **SAFe-aligned workflow**: Epics → Features → User Stories → Sprints → Code
- **12 orchestration patterns**: solo, sequential, parallel, hierarchical, network, loop...
- **Multi-LLM**: Claude, GPT, MiniMax, GLM — with automatic fallback chains
- **Full TDD pipeline**: Brain analysis → FRACTAL decomposition → TDD workers → Adversarial review → Deploy

### Screenshots

![Dashboard](screenshots/02_dashboard.png)
*Real-time dashboard with SSE streaming of multi-agent conversations*

![Swagger API](screenshots/03_swagger.png)
*94 auto-documented REST endpoints*

![CLI](screenshots/04_cli.png)
*Full-featured command-line interface (22 command groups)*

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  🧠 Brain (Claude Opus)                                          │
│  Vision analysis → Task generation → WSJF prioritization         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  TDD Workers × N    │      │  Deploy Pipeline    │
│  FRACTAL decompose  │      │  Build → Stage →    │
│  RED → GREEN →      │      │  E2E → Prod →       │
│  VERIFY → COMMIT    │      │  Rollback           │
└─────────────────────┘      └─────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  🔴 Adversarial Gate (multi-LLM cascaded review)                 │
│  L0: Fast scan → L1: Code review → L2: Architecture review      │
└──────────────────────────────────────────────────────────────────┘
```

### Quick Start

```bash
# Clone
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

# Install dependencies
pip install -r requirements.txt

# Set API keys
mkdir -p ~/.config/factory
echo "sk-ant-..." > ~/.config/factory/anthropic.key

# Start the platform
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Open `http://localhost:8090` — the platform UI is ready.

### Three Interfaces

#### 1. Web Dashboard (HTMX + SSE)

The main UI at `http://localhost:8090`:
- Real-time multi-agent conversations with SSE streaming
- PI Board, mission lifecycle, sprint planning
- Agent management, monitoring, incident dashboard

#### 2. CLI (`sf`)

Full-featured command-line interface mirroring the dashboard:

```bash
# Install (add to PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Browse
sf status                              # Platform health
sf projects list                       # All projects
sf missions list                       # Missions with WSJF scores
sf agents list                         # 145 agents
sf features list <epic_id>             # Epic features
sf stories list --feature <id>         # User stories

# Work
sf ideation "e-commerce app in React"  # Multi-agent ideation (streamed)
sf missions start <id>                 # Start mission run
sf metrics dora                        # DORA metrics

# Monitor
sf incidents list                      # Incidents
sf llm stats                           # LLM usage (tokens, cost)
sf chaos status                        # Chaos engineering
```

**22 command groups** · Dual mode: API (live server) or DB (offline) · JSON output (`--json`) · Spinner animations · Markdown table rendering

#### 3. REST API + Swagger

94 API endpoints auto-documented at `/docs` (Swagger UI):

```bash
# Examples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: `http://localhost:8090/docs`

### Agent Organization

| Team | Agents | Role |
|------|--------|------|
| Product | Product Manager, Business Analyst, PO | SAFe planning, WSJF |
| Architecture | Solution Architect, Tech Lead | Architecture decisions |
| Development | Dev agents (per stack) | TDD implementation |
| Quality | QA, Security Engineer | Testing, security audit |
| Design | UX Designer | User experience |
| DevOps | DevOps, SRE | CI/CD, monitoring |
| Management | Scrum Master, RTE | Ceremonies, facilitation |

### Project Configuration

Projects are defined in `projects/*.yaml`:

```yaml
project:
  name: my-project
  root_path: /path/to/project
  vision_doc: CLAUDE.md

domains:
  typescript:
    paths: [src/]
    build_cmd: npm run build
    test_cmd: npm run test

fractal:
  max_files: 5
  max_loc: 400

adversarial:
  threshold: 5
```

### Directory Structure

```
├── cli/                     # sf CLI (5 files, 2100+ LOC)
│   ├── sf.py                # 22 command groups, 40+ subcommands
│   ├── _api.py              # httpx REST client
│   ├── _db.py               # sqlite3 offline backend
│   ├── _output.py           # ANSI tables, markdown rendering
│   └── _stream.py           # SSE streaming with spinner
│
├── platform/                # Agent Platform (FastAPI + HTMX)
│   ├── server.py            # App factory, port 8090
│   ├── agents/              # Agent loop, executor, store
│   ├── a2a/                 # Agent-to-agent messaging bus
│   ├── patterns/            # 12 orchestration patterns
│   ├── missions/            # SAFe mission lifecycle
│   ├── sessions/            # Conversation runner + SSE
│   ├── web/                 # Routes + Jinja2 templates
│   ├── mcp_platform/        # MCP server (23 tools)
│   └── tools/               # Agent tools (code, git, deploy)
│
├── core/                    # TDD engine
│   ├── brain.py             # RLM Brain (Claude Opus)
│   ├── fractal.py           # Task decomposition
│   ├── cycle_worker.py      # Batch TDD workers
│   ├── adversarial.py       # Multi-LLM quality gate
│   └── task_store.py        # SQLite + zlib storage
│
├── projects/                # Project YAML configurations
├── data/                    # Platform database
├── screenshots/             # Documentation screenshots
└── tests/                   # E2E tests
```

---

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.
