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

**[Live Demo: sf.macaron-software.com](https://sf.macaron-software.com)** — click "Skip (Demo)" to explore

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
<strong>Dashboard — Adaptive SAFe Perspective</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — Strategic Backlog & WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Program Increment Planning</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Ideation Workshop — AI-Powered Brainstorming</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Trains & Agent Teams</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>Ceremonies — Workflow Templates & Patterns</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoring — DORA Metrics & System Health</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — SAFe Role Selection Wizard</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
</table>

## Quick Start

### Option 1: Docker (Recommended)

The Docker image includes: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # copies .env.example → .env (edit it to add your LLM API key)
make run     # builds & starts the platform
```

Open http://localhost:8090 — click **"Skip (Demo)"** to explore without an API key.

### Option 2: Local Installation

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Start platform
make dev
# or manually: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Open http://localhost:8090

### Step 3: Configure an LLM Provider

Without an API key, the platform runs in **demo mode** — agents respond with mock answers.
This is useful to explore the UI, but agents won't generate real code or analysis.

To enable real AI agents, edit `.env` and add **one** API key:

```bash
# Option A: MiniMax (free tier — recommended for getting started)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# Option B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Option C: NVIDIA NIM (free tier)
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

Then restart: `make run`

| Provider | Env Variable | Models | Free Tier |
|----------|-------------|--------|-----------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 | Yes |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini | No |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 | No |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 | Yes |

The platform auto-falls back to other configured providers if the primary fails.
You can also configure providers from the **Settings** page in the dashboard (`/settings`).

## Features

### 158 Specialized AI Agents

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

### 12 Orchestration Patterns

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

### SAFe-Aligned Lifecycle

Full Portfolio → Epic → Feature → Story hierarchy with:

- **Strategic Portfolio** — portfolio canvas, strategic themes, value streams
- **Program Increment** — PI planning, objectives, dependencies
- **Team Backlog** — user stories, tasks, acceptance criteria
- **Sprint Execution** — daily standups, sprint reviews, retrospectives

### Security & Compliance

- **Authentication** — JWT-based auth with RBAC
- **Prompt injection guard** — detect and block malicious prompts
- **Secret scrubbing** — automatic redaction of sensitive data
- **CSP (Content Security Policy)** — hardened headers
- **Rate limiting** — per-user API quotas
- **Audit logging** — comprehensive activity logs

### DORA Metrics & Monitoring

- **Deployment frequency** — how often code reaches production
- **Lead time** — commit to deploy duration
- **MTTR** — mean time to recovery from incidents
- **Change failure rate** — percentage of failed deployments
- **Real-time dashboards** — Chart.js visualizations
- **Prometheus metrics** — /metrics endpoint

### Built-in Agent Tools

The Docker image includes everything agents need to work autonomously:

| Category | Tools | Description |
|----------|-------|-------------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | Read, write, and search project files |
| **Build** | `build`, `test`, `local_ci` | Run builds, tests, and local CI pipelines (npm/pip/cargo auto-detected) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | Version control with agent branch isolation |
| **Security** | `sast_scan`, `dependency_audit`, `secrets_scan` | SAST via bandit/semgrep, CVE audit, secret detection |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright E2E tests and screenshots (Chromium included) |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | Create incidents/tickets for TMA tracking |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | Container deployment and CI/CD status |
| **Memory** | `memory_store`, `memory_search`, `deep_search` | Persistent project memory across sessions |

### Auto-Heal & Self-Repair (TMA)

Autonomous incident detection, triage, and self-repair cycle:

- **Heartbeat monitoring** — continuous health checks on all running missions and services
- **Incident auto-detection** — HTTP 5xx, timeout, agent crash → automatic incident creation
- **Triage & classification** — severity (P0-P3), impact analysis, root cause hypothesis
- **Self-repair** — agents autonomously diagnose and fix issues (code patches, config changes, restarts)
- **Ticket creation** — unresolved incidents automatically create tracked tickets for human review
- **Escalation** — P0/P1 incidents trigger Slack/Email notifications to on-call team
- **Retrospective loop** — post-incident learnings stored in memory, injected into future sprints

### SAFe Perspectives & Onboarding

Role-based adaptive UI that mirrors real SAFe organization:

- **9 SAFe perspectives** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Adaptive dashboard** — KPIs, quick actions, and sidebar links change per selected role
- **Onboarding wizard** — 3-step first-time user flow (choose role → choose project → start)
- **Perspective selector** — switch SAFe role anytime from the topbar dropdown
- **Dynamic sidebar** — only shows navigation relevant to the current perspective

### 4-Layer Memory & RLM Deep Search

Persistent knowledge across sessions with intelligent retrieval:

- **Session memory** — conversation context within a single session
- **Pattern memory** — learnings from orchestration pattern execution
- **Project memory** — per-project knowledge (decisions, conventions, architecture)
- **Global memory** — cross-project organizational knowledge (FTS5 full-text search)
- **Auto-loaded project files** — CLAUDE.md, SPECS.md, VISION.md, README.md injected into every LLM prompt (max 8K)
- **RLM Deep Search** — Recursive Language Model (arXiv:2512.24601) — iterative WRITE-EXECUTE-OBSERVE-DECIDE loop with up to 10 exploration iterations

### Agent Mercato (Transfer Market)

Token-based agent marketplace for team composition:

- **Agent listings** — list agents for transfer with asking price
- **Free agent pool** — unassigned agents available for drafting
- **Transfers & loans** — buy, sell, or loan agents between projects
- **Market valuation** — automatic agent valuation based on skills, experience, and performance
- **Wallet system** — per-project token wallets with transaction history
- **Draft system** — claim free agents for your project

### Adversarial Quality Guard

Two-layer quality gate that blocks fake/placeholder code from passing:

- **L0 Deterministic** — instant detection of slop (lorem ipsum, TBD), mocks (NotImplementedError, TODO), fake builds, hallucinations, stack mismatches
- **L1 LLM Semantic** — separate LLM reviews output quality for execution patterns
- **Scoring** — score < 5 passes, 5-6 soft-pass with warning, 7+ rejected
- **Force reject** — hallucination, slop, stack mismatch, fake builds always rejected regardless of score

### Auto-Documentation & Wiki

Automatic documentation generation throughout the lifecycle:

- **Sprint retrospectives** — LLM-generated retro notes stored in DB and memory, injected into next sprint prompts (learning loop)
- **Phase summaries** — each mission phase produces an LLM-generated summary of decisions and outcomes
- **Architecture Decision Records** — architecture patterns automatically document design decisions in project memory
- **Project context files** — auto-loaded instruction files (CLAUDE.md, SPECS.md, CONVENTIONS.md) serve as living documentation
- **Confluence sync** — bidirectional sync with Confluence wiki pages for enterprise documentation
- **Swagger auto-docs** — 94 REST endpoints auto-documented at `/docs` with OpenAPI schema

## Four Interfaces

### 1. Web Dashboard (HTMX + SSE)

Main UI at http://localhost:8090:

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
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

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
│  Strategic Portfolio (Portfolio Canvas, Value Streams)       │
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
│  Quality Gates + Auto-Heal                                    │
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

# E2E tests (Playwright — requires install first)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
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

The Docker image includes: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.
Agents can build projects, run E2E tests with screenshots, and perform SAST security scans out of the box.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

```bash
# LLM Provider (required for real agents)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API key

# Authentication (optional)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# Integrations (optional)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## What's New in v2.1.0 (Feb 2026)

### SAFe Perspectives & Onboarding
- **9 SAFe role perspectives** — adaptive dashboard, sidebar, and KPIs per role
- **Onboarding wizard** — 3-step first-time user flow with role and project selection
- **Perspective selector** — switch SAFe role from topbar at any time

### Auto-Heal & Self-Repair
- **TMA heartbeat** — continuous health monitoring with auto-incident creation
- **Self-repair agents** — autonomous diagnosis and fix for common failures
- **Ticket escalation** — unresolved incidents create tracked tickets with notifications

### 4-Layer Memory & RLM
- **Persistent knowledge** — session, pattern, project, and global memory layers with FTS5
- **RLM deep search** — recursive exploration loop (up to 10 iterations) for complex codebase analysis
- **Auto-loaded project context** — CLAUDE.md, SPECS.md, VISION.md injected into every agent prompt

### Adversarial Quality Guard
- **L0 deterministic** — instant detection of slop, mocks, fake builds, hallucinations
- **L1 semantic** — LLM-based quality review for execution outputs
- **Force reject** — hallucination and stack mismatch always blocked

### Agent Mercato
- **Token-based marketplace** with agent listings, transfers, loans, and free agent draft
- **Market valuation** — automatic agent pricing based on skills and performance
- **Wallet system** — per-project token economy with transaction history

### Authentication & Security
- **JWT-based auth** with login/register/refresh/logout
- **RBAC** — admin, project_manager, developer, viewer roles
- **OAuth** — GitHub and Azure AD SSO login
- **Admin panel** — user management UI (`/admin/users`)
- **Demo mode** — one-click "Skip" button for instant access

### Auto-Documentation
- **Sprint retrospectives** — LLM-generated retro notes with learning loop
- **Phase summaries** — automatic documentation of mission phase outcomes
- **Confluence sync** — bidirectional wiki integration

### LLM Providers
- **Multi-provider** with automatic fallback chain
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Demo mode** for UI exploration without API keys

### Platform Improvements
- DORA metrics dashboard with LLM cost tracking
- Jira bidirectional sync
- Playwright E2E test suite (82 tests)
- Internationalization (EN/FR)
- Real-time notifications (Slack, Email, Webhook)
- Design System pipeline in workflows (UX → dev → review)
- 3D Agent World visualization

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the AGPL v3 License - see the [LICENSE](LICENSE) file for details.

## Support

- Live Demo: https://sf.macaron-software.com
- Issues: https://github.com/macaron-software/software-factory/issues
- Discussions: https://github.com/macaron-software/software-factory/discussions
