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

# Macaron Software Factory

**Multi-Agent Software Factory — Autonomous AI agents orchestrating the full product lifecycle**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Features](#features) · [Quick Start](#quick-start) · [Screenshots](#screenshots) · [Architecture](#architecture) · [Contributing](#contributing)

</div>

---

## What is this?

Macaron is an **autonomous multi-agent platform** that orchestrates the entire software development lifecycle — from ideation to deployment — using specialized AI agents working together.

Think of it as a **virtual software factory** where 94 AI agents collaborate through structured workflows, following SAFe methodology, TDD practices, and automated quality gates.

### Key Highlights

- **94 specialized agents** — architects, developers, testers, SREs, security analysts, product owners
- **12 orchestration patterns** — solo, parallel, hierarchical, network, adversarial-pair, human-in-the-loop
- **SAFe-aligned lifecycle** — Portfolio → Epic → Feature → Story with PI cadence
- **Auto-heal** — autonomous incident detection, triage, and self-repair
- **Security-first** — prompt injection guard, RBAC, secret scrubbing, connection pooling
- **DORA metrics** — deployment frequency, lead time, MTTR, change failure rate

## Screenshots

<table>
<tr>
<td width="50%">
<strong>Portfolio — Strategic Committee & Governance</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
<td width="50%">
<strong>PI Board — Program Increment Planning</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agents — 94 Specialized AI Agents</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>Ideation Workshop — AI-Powered Brainstorming</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Mission Control — Real-Time Execution Monitoring</strong><br>
<img src="docs/screenshots/en/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>Monitoring — System Health & Metrics</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

# Setup environment
make setup
# Edit .env with your LLM API key (OpenAI, Anthropic, or Azure OpenAI)

# Start the platform
make run
```

Open **http://localhost:8090** in your browser.

### Option 2: Docker Compose (Manual)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### Option 3: Local Development

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

# Set your LLM key
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...

# Start the server
make dev
```

### Verify Installation

```bash
curl http://localhost:8090/api/health
# → {"status": "healthy", ...}
```

## Features

### Multi-Agent Orchestration
- **94 specialized agents** organized in 5 SAFe levels (Portfolio → Team)
- **12 orchestration patterns** — solo, sequential, parallel, hierarchical, network, loop, router, aggregator, adversarial-pair, human-in-the-loop
- **Agent-to-Agent messaging** — async message bus with priority routing, negotiation, and veto capabilities

### Software Factory Pipeline
```
Brain (deep analysis) → FRACTAL decomposition → TDD Workers (parallel) → Adversarial Review → Build → Deploy
```
- **Brain**: Recursive project analysis, generates tasks with WSJF priority scoring
- **FRACTAL**: Splits tasks into 3 concerns — feature, guards, failure handling
- **TDD Workers**: N parallel workers write code test-first
- **Adversarial Review**: Multi-LLM cascaded review (L0 fast → L1 code → L2 architecture)

### SAFe-Aligned Product Lifecycle
- **Full hierarchy**: Portfolio → Product Line → Product → Epic → Feature → Story → Task
- **Mission Control**: Real-time monitoring of mission execution with phase management
- **PI Board**: Program Increment planning and tracking
- **Ceremony support**: Sprint planning, reviews, retrospectives
- **4 built-in workflows**: product-lifecycle (11 phases), feature-request (6), tech-debt-reduction (5), tma-maintenance (4)

### Auto-Heal & Self-Repair
- **Incident detection**: Automatic error capture and classification (P0-P3)
- **TMA workflow**: Diagnose → Fix → Verify → Close — fully autonomous
- **Deduplication**: Prevents duplicate healing sessions
- **Circuit breaker**: Max 3 concurrent heals, rate-limit aware

### Ideation Workshop
- **AI-powered brainstorming**: Describe an idea, get a structured project with backlog
- **Multi-agent analysis**: Domain experts, architects, and POs collaborate on feasibility
- **Auto-generation**: Creates Epic → Features → User Stories with acceptance criteria

### Security & Resilience
- **Prompt guard**: Input sanitization and injection detection
- **RBAC**: Role-based access control for agents and humans
- **Secret scrubbing**: Log sanitization, no hardcoded credentials
- **Connection pooling**: PostgreSQL with psycopg pool
- **Structured logging**: JSON logs with trace IDs

### Observability
- **DORA metrics**: Deployment frequency, lead time, change failure rate, MTTR
- **Real-time SSE**: Server-Sent Events for live UI updates
- **Health monitoring**: Container and service health checks
- **Backup & DR**: Automated backup scripts with Azure Blob storage

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web UI (HTMX + SSE)                  │
├─────────────────────────────────────────────────────────┤
│                  FastAPI Server (Python)                 │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  Agent   │ Mission  │ Pattern  │ Workflow │   Tools     │
│  Store   │  Store   │  Engine  │  Engine  │  Registry   │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│               Message Bus (A2A Protocol)                │
├──────────┬──────────┬──────────┬────────────────────────┤
│  LLM     │ Memory   │ Security │  Ops (Auto-Heal,      │
│  Client  │ Manager  │ Module   │   Metrics, Deploy)    │
├──────────┴──────────┴──────────┴────────────────────────┤
│              SQLite / PostgreSQL + pgvector              │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | Jinja2 + HTMX + SSE (zero JS build step) |
| Backend | FastAPI (Python 3.10+) |
| Database | SQLite (dev) / PostgreSQL + pgvector (prod) |
| LLM Providers | OpenAI, Anthropic, Azure OpenAI, MiniMax, GLM |
| Deployment | Docker Compose, Azure VM, nginx |
| CI/CD | GitHub Actions |

### Project Structure
```
├── platform/           # Agent Platform — FastAPI web app
│   ├── server.py       # App factory, port 8090
│   ├── web/            # Routes + Jinja2 templates
│   ├── a2a/            # Agent-to-Agent messaging
│   ├── agents/         # Agent loop, executor, store
│   ├── patterns/       # 12 orchestration patterns
│   ├── missions/       # SAFe-aligned mission lifecycle
│   ├── llm/            # Multi-provider LLM client
│   ├── tools/          # Agent tools (code, git, deploy, memory)
│   ├── workflows/      # Built-in workflow definitions
│   ├── ops/            # Auto-heal, metrics, deployment
│   └── i18n/           # Internationalization (EN/FR)
├── core/               # Factory engine (Brain, FRACTAL, TDD)
├── skills/             # Agent skill definitions (YAML)
├── projects/           # Per-project configurations
├── cli/                # CLI entry point
└── tests/              # Unit + E2E tests
```

## Configuration

### Environment Variables

```bash
# LLM Provider (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Platform settings
PLATFORM_LLM_PROVIDER=openai          # openai | anthropic | azure-openai | minimax
PLATFORM_LLM_MODEL=gpt-4o             # Model for the selected provider
```

See [`.env.example`](.env.example) for all available options.

### Project Configuration

Each managed project has a YAML config in `projects/`:

```yaml
project:
  name: my-project
  root: /path/to/project
  language: python

build:
  command: python -m pytest
  timeout: 300

brain:
  phase: vision  # vision | fix | security | refactor
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

# Run tests
make test

# Run platform in dev mode (with auto-reload)
make dev
```

## License

This project is licensed under the **GNU Affero General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

- Use, modify, and distribute freely
- Commercial use allowed
- Network use requires sharing source code
- Derivative works must be AGPL v3

---

<div align="center">

**Built with love by [Macaron Software](https://github.com/macaron-software)**

[Report Bug](https://github.com/macaron-software/software-factory/issues) · [Request Feature](https://github.com/macaron-software/software-factory/issues)

</div>
