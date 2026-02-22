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

**Multi-Agent Software Factory — Autonomous AI agents orchestrating the full product lifecycle**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Features](#features) · [Quick Start](#quick-start) · [Screenshots](#screenshots) · [Architecture](#architecture) · [Contributing](#contributing)

</div>

---

## What is this?

Software Factory is an **autonomous multi-agent platform** that orchestrates the entire software development lifecycle — from ideation to deployment — using specialized AI agents working together.

Think of it as a **virtual software factory** where 158 AI agents collaborate through structured workflows, following SAFe methodology, TDD practices, and automated quality gates.

### Key Highlights

- **158 specialized agents** — architects, developers, testers, SREs, security analysts, product owners
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
<strong>Agents — 158 Specialized AI Agents</strong><br>
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
<tr>
<td width="50%">
<strong>Swagger API — 94 REST Endpoints</strong><br>
<img src="docs/screenshots/en/swagger.png" alt="Swagger API" width="100%">
</td>
<td width="50%">
<strong>CLI — 40+ Commands</strong><br>
<img src="docs/screenshots/en/cli.png" alt="CLI" width="100%">
</td>
</tr>
</table>

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
docker-compose up -d
```

Open http://localhost:8099

### Option 2: Local Installation

```bash
# Clone repository
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

# Install dependencies
pip install -r requirements.txt

# Configure API keys
mkdir -p ~/.config/factory
echo "sk-ant-..." > ~/.config/factory/anthropic.key

# Start platform
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none
```

Open http://localhost:8099

## Features

### 🤖 158 Specialized AI Agents

Agents are organized in teams mirroring real software organizations:

| Team | Agents | Role |
|------|--------|------|
| **Product** | Product Manager, Business Analyst, PO | SAFe planning, WSJF prioritization |
| **Architecture** | Solution Architect, Tech Lead, System Architect | Architecture decisions, design patterns |
| **Development** | Backend/Frontend/Mobile/Data Engineers | TDD implementation per stack |
| **Quality** | QA Engineers, Security Analysts, Test Automation | Testing, security audits, penetration testing |
| **Design** | UX Designer, UI Designer | User experience, visual design |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, monitoring, infrastructure |
| **Management** | Scrum Master, RTE, Agile Coach | Ceremonies, facilitation, impediment removal |

### 🎯 12 Orchestration Patterns

- **Solo** — single agent for simple tasks
- **Sequential** — pipeline of agents executing in order
- **Parallel** — multiple agents working simultaneously
- **Hierarchical** — manager delegating to sub-agents
- **Network** — agents collaborating peer-to-peer
- **Adversarial-pair** — one agent generates, another criticizes
- **Human-in-the-loop** — agent proposes, human validates
- **Ensemble** — multiple agents vote on decisions
- **Recursive** — agent spawns sub-agents recursively
- **Loop** — agent iterates until condition met
- **Saga** — distributed transaction with compensations
- **Event-driven** — agents react to events asynchronously

### 📊 SAFe-Aligned Lifecycle

Full Portfolio → Epic → Feature → Story hierarchy with:

- **Strategic Portfolio** — portfolio canvas, strategic themes, value streams
- **Program Increment** — PI planning, objectives, dependencies
- **Team Backlog** — user stories, tasks, acceptance criteria
- **Sprint Execution** — daily standups, sprint reviews, retrospectives

### 🛡️ Security & Compliance

- **Authentication** — JWT-based auth with RBAC
- **Prompt injection guard** — detect and block malicious prompts
- **Secret scrubbing** — automatic redaction of sensitive data
- **CSP (Content Security Policy)** — hardened headers
- **Rate limiting** — per-user API quotas
- **Audit logging** — comprehensive activity logs

### 📈 DORA Metrics & Monitoring

- **Deployment frequency** — how often code reaches production
- **Lead time** — commit to deploy duration
- **MTTR** — mean time to recovery from incidents
- **Change failure rate** — percentage of failed deployments
- **Real-time dashboards** — Chart.js visualizations
- **Prometheus metrics** — /metrics endpoint

## Four Interfaces

### 1. Web Dashboard (HTMX + SSE)

Main UI at http://localhost:8099:

- **Real-time multi-agent conversations** with SSE streaming
- **PI Board** — program increment planning
- **Mission Control** — execution monitoring
- **Agent Management** — view, configure, monitor agents
- **Incident Dashboard** — auto-heal triage
- **Mobile responsive** — works on tablets and phones

### 2. CLI (`sf`)

Full-featured command-line interface:

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

### 3. REST API + Swagger

94 API endpoints auto-documented at `/docs` (Swagger UI):

```bash
# Examples
curl http://localhost:8099/api/projects
curl http://localhost:8099/api/agents
curl http://localhost:8099/api/missions
curl -X POST http://localhost:8099/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8099/docs

### 4. MCP Server (Model Context Protocol)

23 MCP tools for AI agent integration (port 9501):

```bash
# Start MCP server
python3 -m platform.mcp_platform.server

# Tools available:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  🎯 Strategic Portfolio (Portfolio Canvas, Value Streams)       │
│  Vision, Themes, Epics → WSJF Prioritization                    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  PI Planning Board  │      │  Mission Execution  │
│  Program Increment  │      │  145 Agents         │
│  Features → Stories │      │  12 Patterns        │
│  Dependencies       │      │  TDD Pipeline       │
└─────────────────────┘      └─────────────────────┘
          │                             │
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  Sprint Backlog     │      │  Deploy Pipeline    │
│  Daily Standups     │      │  Build → Stage →    │
│  Reviews            │      │  E2E → Prod         │
└─────────────────────┘      └─────────────────────┘
          │                             │
          └──────────────┬──────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  🔴 Quality Gates + Auto-Heal                                    │
│  Tests, Security, Performance → Incident Detection → Self-Repair │
└──────────────────────────────────────────────────────────────────┘
```

## Project Configuration

Projects are defined in `projects/*.yaml`:

```yaml
project:
  name: my-project
  root_path: /path/to/project
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

monitoring:
  prometheus: true
  grafana_dashboard: project-metrics
```

## Directory Structure

```
├── platform/                # Agent Platform (152 Python files)
│   ├── server.py            # FastAPI app, port 8090
│   ├── agents/              # Agent loop, executor, store
│   ├── a2a/                 # Agent-to-agent messaging bus
│   ├── patterns/            # 12 orchestration patterns
│   ├── missions/            # SAFe mission lifecycle
│   ├── sessions/            # Conversation runner + SSE
│   ├── web/                 # Routes + Jinja2 templates
│   ├── mcp_platform/        # MCP server (23 tools)
│   └── tools/               # Agent tools (code, git, deploy)
│
├── cli/                     # CLI 'sf' (6 files, 2100+ LOC)
│   ├── sf.py                # 22 command groups, 40+ subcommands
│   ├── _api.py              # httpx REST client
│   ├── _db.py               # sqlite3 offline backend
│   ├── _output.py           # ANSI tables, markdown rendering
│   └── _stream.py           # SSE streaming with spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm charts, Docker, K8s
├── tests/                   # E2E Playwright tests
├── skills/                  # Agent skills library
├── projects/                # Project YAML configurations
└── data/                    # SQLite database
```

## Testing

```bash
# Run all tests
make test

# E2E tests (Playwright)
cd platform/tests/e2e
npm test

# Unit tests
pytest tests/

# Chaos engineering
python3 tests/test_chaos.py

# Endurance tests
python3 tests/test_endurance.py
```

## Deployment

### Docker

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional
PORT=8090
DATABASE_URL=sqlite:///data/platform.db
LOG_LEVEL=INFO
ENABLE_AUTH=true
```

## What's New in v1.2.0 (Feb 21-22, 2026)

### CLI 'sf' - Full Command-Line Interface
- 40+ commands mirroring all web dashboard functionality
- Dual mode: API (live server) or DB (offline)
- SSE streaming with per-agent colored output
- JSON output for scripting
- 52 automated tests

### Product Management Enhancements
- 11 new PM capabilities
- WSJF prioritization algorithms
- Value stream mapping

### Security Hardening
- AuthMiddleware enabled by default
- CSP headers tightened
- Secret scrubbing in logs and API responses
- Rate limiting per user

### Testing & Quality
- Endurance test suite
- Chaos engineering tests
- E2E Playwright tests for all pages
- Debian 13 fresh install validation

### DevOps & Monitoring
- GitHub webhooks integration
- Helm chart for Kubernetes
- Prometheus metrics endpoint
- Grafana dashboards
- CD pipeline automation

### UI Improvements
- Real-time notifications
- Chart.js analytics visualizations
- Mobile responsive design
- Improved SSE streaming stability

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the AGPL v3 License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: https://docs.software-factory.dev
- Issues: https://github.com/macaron-software/software-factory/issues
- Discussions: https://github.com/macaron-software/software-factory/discussions
