# 🍪 Software Factory

**Multi-agent collaborative platform web** — agents spécialisés (Métier, Lead Dev, Testeur, Sécurité, DevOps...) qui dialoguent entre eux via le protocole A2A, orchestrés selon 8 patterns agentic, hébergé sur VM Azure avec Azure AI Foundry.

## Quick Start

```bash
# Install deps
cd platform
pip install -r requirements.txt

# Run locally
python -m uvicorn platform.server:app --port 8090 --reload

# Open http://localhost:8090
```

## Architecture

```
┌─── Web UI (HTMX + SSE) ────────────────────────────────┐
│  Workspace │ Agent Chat │ Conversation │ Skills │ Monitor │
└─────────────────────────────────────────────────────────┘
         │ SSE (real-time)          │ REST API
┌────────┴──────────────────────────┴────────────────────┐
│              ORCHESTRATOR (Python)                       │
│  Router │ Scheduler (WSJF) │ A2A Bus │ Pattern Engine   │
└─────────────────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────────┐
│              AGENT RUNTIME                               │
│  👔 Métier   📋 Chef Projet  🏗️ Lead Dev  💻 Dev        │
│  🧪 Testeur  🔒 Sécurité    🚀 DevOps    🏛️ Architecte │
│  🎨 UX       📊 Data        📝 Tech Writer + Custom...  │
└─────────────────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────────┐
│  Azure AI Foundry │ Memory (SQLite+FTS5) │ Factory Core │
└─────────────────────────────────────────────────────────┘
```

## Orchestration Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Parallel** | N agents travaillent simultanément | Brainstorming, reviews parallèles |
| **Sequential** | Pipeline agent → agent | Code → Review → Test → Deploy |
| **Loop** | Itération jusqu'à convergence | Dev → Test → Fix → retest |
| **Router** | 1 agent dispatche vers le spécialiste | Classification de demandes |
| **Aggregator** | Plusieurs proposent, 1 synthétise | Architecture decisions |
| **Hierarchical** | Manager décompose, workers exécutent | Sprint planning, features |
| **Network** | Mesh complet, agents communiquent librement | Débats techniques |
| **Human-in-the-loop** | Agent + humain valide | Déploiements production |

## A2A Protocol

Messages typés entre agents :

| Type | Description |
|------|-------------|
| `REQUEST` | Demande d'action |
| `RESPONSE` | Réponse |
| `DELEGATE` | Délégation de tâche |
| `VETO` | Blocage avec justification |
| `APPROVE` | Validation |
| `INFORM` | Information broadcast |
| `NEGOTIATE` | Proposition de compromis |
| `ESCALATE` | Escalade au niveau supérieur |
| `HUMAN_REQUEST` | Demande d'input humain |

### Veto System

Hiérarchie de veto (comme Team of Rivals) :
- 🔒 **Sécurité** : VETO ABSOLU (vulnérabilités critiques)
- 🏛️ **Architecte** : VETO STRONG (violations patterns)
- 🏗️ **Lead Dev** : VETO STRONG (qualité code)
- 🧪 **Testeur** : VETO STRONG (coverage insuffisante)
- 👔 **Métier** : VETO ADVISORY (valeur business)

## Custom Skills (YAML)

Chaque agent est défini par un fichier YAML :

```yaml
# platform/skills/definitions/my_agent.yaml
id: my_agent
name: "Mon Agent Custom"
persona:
  description: "Expert en..."
  traits: ["Rigoureux", "Pragmatique"]
system_prompt: |
  Tu es...
skills: [tdd, code_review]
tools: [code_read, code_write, git_commit]
llm:
  model: gpt-4o
  temperature: 0.5
permissions:
  can_veto: true
  veto_level: strong
communication:
  responds_to: [lead_dev]
  can_contact: [dev, testeur]
```

## Deployment (Azure VM)

```bash
# Docker
cd platform
docker compose up -d

# Systemd
sudo cp macaron-platform.service /etc/systemd/system/
sudo systemctl enable --now macaron-platform
```

## Integration with Factory

The platform reuses existing Factory core:
- **Brain** → deep recursive analysis (Opus 4.5)
- **Adversarial** → Team of Rivals review cascade
- **FRACTAL** → task decomposition (3 concerns)
- **Build Queue** → global build coordination
- **Skills** → existing skill library (backward compatible)
- **MCP LRM** → code navigation tools

## Tech Stack

- **Backend**: Python 3.12 + FastAPI
- **Frontend**: HTMX + SSE (no build step)
- **Database**: SQLite + FTS5
- **LLMs**: Azure AI Foundry (GPT-4o, Claude Sonnet 4, GPT-4.1)
- **Deploy**: Docker + nginx + certbot on Azure VM

## Project Structure

```
platform/
├── server.py              # FastAPI main app
├── config.py              # Config (Azure, server, agents)
├── models.py              # Pydantic data models
├── security.py            # Auth, rate limiting
├── factory_bridge.py      # Bridge to existing Factory
├── agents/                # Agent runtime
│   ├── base.py            # BaseAgent class
│   ├── registry.py        # YAML role loader
│   ├── runtime.py         # Agent lifecycle
│   └── memory.py          # Short/long-term memory
├── a2a/                   # Agent-to-Agent protocol
│   ├── bus.py             # Message bus (pub/sub)
│   ├── protocol.py        # Message types & routing
│   ├── negotiation.py     # Consensus algorithm
│   ├── veto.py            # Veto hierarchy
│   └── azure_bridge.py    # Azure Foundry A2A
├── orchestrator/          # Orchestration engine
│   ├── engine.py          # Main coordinator
│   ├── patterns.py        # 8 agentic patterns
│   ├── router.py          # Intent classification
│   ├── scheduler.py       # WSJF priority
│   ├── state_machine.py   # Workflow FSM
│   └── llm_provider.py    # Azure LLM routing
├── tools/                 # Tool registry
│   ├── code_tools.py      # Code read/write/edit
│   ├── git_tools.py       # Git operations
│   ├── build_tools.py     # Build/test/lint
│   ├── mcp_bridge.py      # MCP LRM bridge
│   └── azure_tools.py     # Azure AI tools
├── skills/                # Skill definitions
│   ├── loader.py          # YAML loader
│   └── definitions/       # 11 role YAMLs
├── web/                   # Web UI
│   ├── routes.py          # HTTP routes
│   ├── ws.py              # SSE handlers
│   ├── templates/         # Jinja2 HTML
│   └── static/            # CSS, JS
├── db/                    # Database
│   ├── schema.sql         # SQLite schema
│   └── migrations.py      # Init & migrate
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── macaron-platform.service
```
