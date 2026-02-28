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

**Multi-Agent Software Factory — Autonomous AI agents orchestrating the full product lifecycle**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live: sf.macaron-software.com](https://sf.macaron-software.com)**

[Features](#features) · [Quick Start](#quick-start) · [Screenshots](#screenshots) · [Architecture](#architecture) · [Contributing](#contributing)

</div>

---

## What is this?

Software Factory is an **autonomous multi-agent platform** that orchestrates the entire software development lifecycle — from ideation to deployment — using specialized AI agents working together.

Think of it as a **virtual software factory** where 191 AI agents collaborate through structured workflows, following SAFe methodology, TDD practices, and automated quality gates.

### Key Highlights

- **191 specialized agents** — architects, developers, testers, SREs, security analysts, product owners
- **36 built-in workflows** — SAFe ceremonies, quality gates, nightly maintenance, security, knowledge management
- **8 home ideation groups** — CTO Jarvis, Business, Project, Knowledge, Architecture, Security, Data & AI, PI Planning
- **Agent Marketplace** — discover and launch agents from `/marketplace`; filter by ART, role, or skills
- **Mission Replay** — step-by-step timeline with tokens, cost, and duration per agent (`/missions/{id}/replay`)
- **LLM Metrics Dashboard** — real-time cost/latency/provider monitoring at `/metrics`
- **Agent Evaluation Framework** — LLM-as-judge golden dataset scoring at `/evals`
- **Tool Builder** — no-code HTTP/SQL/shell tool creation at `/tool-builder`
- **Multi-tenant Workspaces** — isolated namespaces per project/client at `/workspaces`
- **Knowledge Management** — 4 dedicated agents, ART Knowledge team, nightly knowledge-maintenance workflow
- **Memory Intelligence** — relevance scoring, access tracking, automatic pruning of stale entries
- **10 orchestration patterns** — solo, sequential, parallel, hierarchical, network, loop, router, aggregator, wave, human-in-the-loop
- **SAFe-aligned lifecycle** — Portfolio → Epic → Feature → Story with PI cadence
- **Auto-heal** — autonomous incident detection, triage, and self-repair
- **LLM resilience** — multi-provider fallback, jittered retry, rate-limit aware, env-driven model config
- **OpenTelemetry observability** — distributed tracing with Jaeger, pipeline analytics dashboard
- **Continuous watchdog** — auto-resume paused runs, stale session recovery, failed cleanup
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
<tr>
<td width="50%">
<strong>Home — 8 Ideation Groups (CTO Jarvis, Business, Project, Knowledge, Architecture, Security, Data & AI, PI Planning)</strong><br>
<img src="docs/screenshots/en/home.png" alt="Home" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — Strategic AI Advisor</strong><br>
<img src="docs/screenshots/en/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Business Ideation — 6-Agent Marketing Team</strong><br>
<img src="docs/screenshots/en/mkt_ideation.png" alt="Business Ideation" width="100%">
</td>
<td width="50%">
<strong>Project Ideation — Multi-Agent Tech Team</strong><br>
<img src="docs/screenshots/en/ideation_projet.png" alt="Project Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agent Marketplace — Discover & Launch Agents (/marketplace)</strong><br>
<img src="docs/screenshots/en/marketplace.png" alt="Marketplace" width="100%">
</td>
<td width="50%">
<strong>LLM Metrics — Cost/Latency/Provider Dashboard (/metrics)</strong><br>
<img src="docs/screenshots/en/metrics.png" alt="LLM Metrics" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Workspaces — Multi-Tenant Isolation (/workspaces)</strong><br>
<img src="docs/screenshots/en/workspaces.png" alt="Workspaces" width="100%">
</td>
<td width="50%">
<strong>Tool Builder — No-Code Tool Creation (/tool-builder)</strong><br>
<img src="docs/screenshots/en/tool_builder.png" alt="Tool Builder" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Evaluations — LLM-as-Judge Scoring (/evals)</strong><br>
<img src="docs/screenshots/en/evals.png" alt="Evaluations" width="100%">
</td>
<td width="50%">
<strong>Mission Replay — Step-by-step Timeline (/missions/{id}/replay)</strong><br>
<img src="docs/screenshots/en/mission_replay.png" alt="Mission Replay" width="100%">
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

Open http://localhost:8090 — the platform opens on the **CTO Jarvis** tab.

### Option 2: Local Installation

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # create your config (edit to add LLM key — see Step 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Start platform
make dev
# or manually: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Open http://localhost:8090 — the platform opens on the **CTO Jarvis** tab.
Choose your SAFe role or start typing directly in the Jarvis chat.

### Step 3: Configure an LLM Provider

Without an API key, the platform runs in **demo mode** — agents respond with mock answers.
This is useful to explore the UI, but agents won't generate real code or analysis.

To enable real AI agents, edit `.env` and add **one** API key:

```bash
# Option A: MiniMax (recommended for getting started)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# Option B: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

Then restart: `make run` (Docker) or `make dev` (local)

| Provider | Env Variable | Models |
|----------|-------------|--------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **OpenAI-compatible** | `OPENAI_API_KEY` | any OpenAI-compatible model |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

The platform auto-falls back to other configured providers if the primary fails.
You can also configure providers from the **Settings** page in the dashboard (`/settings`).

## Getting Started — Your First Project

After installation, here's how to go from idea to working project:

### Path A: Ask CTO Jarvis (Fastest)

1. **Open the home page** (`/`) — the platform starts on the CTO Jarvis tab
2. **Type your project idea or question** — e.g. *"Create a new project for an enterprise carpooling app with React and Python"*
3. **Jarvis (Gabriel Mercier, Strategic Orchestrator)** analyses the request, creates the project, provisions the SAFe backlog, and starts the first mission — all in one conversation

This is the **recommended entry point** for any new project.

### Path B: Ideation Workshops (8 Specialized Groups)

The home page offers **8 ideation contexts**, each with a dedicated team of specialized agents:

| Group | Agents | Focus |
|-------|--------|-------|
| **CTO Jarvis** | Gabriel Mercier (Strategic Orchestrator) | Technical strategy, architecture decisions, SAST audits, portfolio overview |
| **Business Ideation** | CMO Sophie Laurent + 5 marketing agents | Go-to-market, SWOT, brand strategy, investor pitch |
| **Project Ideation** | PM + Architect + Backend Dev + QA + SRE | Technical specification, epic/feature breakdown, tech stack selection |
| **Knowledge & Research** | Knowledge Manager + Wiki Maintainer | Knowledge gap analysis, wiki building, research synthesis |
| **Architecture Committee** | Solution Architect + Tech Lead | ADR reviews, technology choices, cross-team dependencies |
| **Security Council** | Security Analyst + Penetration Tester | Threat modeling, penetration testing, RBAC design |
| **Data & AI** | Data Engineer + ML Engineer | ML pipeline design, data architecture, LLM integration strategy |
| **PI Planning** | RTE + Product Owner + Scrum Master | Program Increment planning, capacity allocation, dependency mapping |

For each group: describe your need → agents stream their analysis → export as epic/project/ADR/plan.

### Path C: Explore the Agent Marketplace

Go to `/marketplace` to discover all 191 agents. Filter by ART, role, or skills. Click any agent to view their full profile — tools, skills, recent sessions — and launch a direct session.

### Path D: Create a Project Manually

1. Go to `/projects` and click **"New Project"**
2. Fill in: name, description, tech stack, repository path
3. The platform auto-creates:
   - A **Product Manager agent** assigned to the project
   - A **TMA mission** (continuous maintenance — monitors health, creates incidents)
   - A **Security mission** (weekly security audits — SAST, dependency checks)
   - A **Tech Debt mission** (monthly debt reduction — planned)

### Then: Create Epics & Features

- From the **Portfolio** page (`/portfolio`), create epics with WSJF prioritization
- From an epic, add **features** and break them into **user stories**
- Use the **PI Board** (`/pi-board`) to plan program increments and assign features to sprints

### Running Missions

- Click **"Start"** on any mission to launch agent execution
- Choose an **orchestration pattern** (hierarchical, network, parallel...)
- Watch agents work in real-time from **Mission Control**
- Agents use their tools (code_read, git, build, test, security scan) autonomously
- Replay any past mission at `/missions/{id}/replay` — step-by-step with tokens, cost, duration per agent

### TMA & Security — Always On

These are **automatically enabled** for every project — no configuration needed:

| Mission | Type | Schedule | What it does |
|---------|------|----------|-------------|
| **TMA** | Program | Continuous | Health monitoring, incident detection, auto-repair, ticket creation |
| **Security** | Review | Weekly | SAST scans (bandit/semgrep), dependency audit, secret detection |
| **Tech Debt** | Reduction | Monthly | Code quality analysis, refactoring recommendations |
| **Self-Healing** | Program | Continuous | Auto-detection of 5xx/crashes → TMA mission → agent diagnosis → code fix → validation |

All four are created with the project. TMA, Security, and Self-Healing start as **active**, Tech Debt starts as **planning** (activate when ready).

## Features

### 191 Specialized AI Agents

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

### 10 Orchestration Patterns

- **Solo** — single agent for simple tasks
- **Sequential** — pipeline of agents executing in order
- **Parallel** — multiple agents working simultaneously
- **Hierarchical** — manager delegating to sub-agents
- **Network** — agents collaborating peer-to-peer
- **Loop** — agent iterates until condition met
- **Router** — single agent routes to specialist based on input
- **Aggregator** — multiple inputs merged by a single aggregator
- **Wave** — parallel within waves, sequential across waves
- **Human-in-the-loop** — agent proposes, human validates

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

### Quality Metrics — Industrial Monitoring

Deterministic quality scanning (no LLM) with 10 dimensions, like a production line:

| Dimension | Tools | What it measures |
|-----------|-------|-----------------|
| **Complexity** | radon, lizard | Cyclomatic complexity, cognitive complexity |
| **Unit Test Coverage** | coverage.py, nyc | Line/branch coverage percentage |
| **E2E Test Coverage** | Playwright | Test file count, spec coverage |
| **Security** | bandit, semgrep | SAST findings by severity (critical/high/medium/low) |
| **Accessibility** | pa11y | WCAG 2.1 AA violations |
| **Performance** | Lighthouse | Core Web Vitals scores |
| **Documentation** | interrogate | README, changelog, API docs, docstring coverage |
| **Architecture** | madge, jscpd, mypy | Circular deps, code duplication, type errors |
| **Maintainability** | custom | File size distribution, large file ratio |
| **Adversarial** | built-in | Incident rate, adversarial rejection rate |

**Quality gates on workflow phases** — each workflow phase shows a quality badge (PASS/FAIL/PENDING) based on dimension thresholds configured per gate type:

| Gate Type | Threshold | Used in |
|-----------|-----------|---------|
| `always` | 0% | Analysis, planning phases |
| `no_veto` | 50% | Implementation, sprint phases |
| `all_approved` | 70% | Review, release phases |
| `quality_gate` | 80% | Deploy, production phases |

**Quality dashboard** at `/quality` — global scorecard, per-project scores, trend snapshots.
Quality badges visible on mission detail, project board, workflow phases, and the main dashboard.

### Continuous Improvement Workflows

Three built-in workflows for self-improvement:

| Workflow | Purpose | Agents |
|----------|---------|--------|
| **quality-improvement** | Scan metrics → identify worst dimensions → plan & execute improvements | QA Lead, Dev, Architect |
| **retrospective-quality** | End-of-sprint retro: collect ROTI, incidents, quality data → action items | Scrum Master, QA, Dev |
| **skill-evolution** | Analyze agent performance → update system prompts → evolve skills | Brain, Lead Dev, QA |

These workflows create a **feedback loop**: metrics → analysis → improvement → re-scan → track progress.

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

### Knowledge Management System

A dedicated subsystem for organizational knowledge, introduced in v2.7.0:

- **4 specialized agents** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **ART Knowledge team** — dedicated Agile Release Train team for knowledge operations
- **Nightly `knowledge-maintenance` workflow** — automatic curation, deduplication, and freshness scoring
- **Memory Health dashboard** — knowledge health metrics in the Metrics tab
- **Knowledge Health badge** — visible in the Settings page
- **Relevance scoring formula** — `confidence × recency × access_boost` for intelligent retrieval ranking
- **Access tracking** — `access_count` and `last_read_at` fields on every memory entry
- **Automatic pruning** — stale entries below threshold removed on each nightly run

### Settings Integrations Hub

Configurable tool integrations available to all agents:

- **Supported tools** — Jira, Confluence, SonarQube, and more
- **Domain-level BSCC guidelines** — architecture guidelines (Confluence/Solaris) enforced per project domain
- **Project Export/Import** — ZIP archive containing `project.json` + missions + mission runs + memories
- **Browser Push Notifications** — native browser push via Web Push API (VAPID)
- **Input Validation** — Pydantic models on all POST/PATCH routes

### Agent Marketplace

Discover, filter, and launch any of the 191 agents from a single catalog at `/marketplace`:

- **Filter by ART, role, or skills** — quickly find the right agent for any task
- **Agent profiles** — full detail view: system prompt, tools, skills, recent sessions
- **One-click session launch** — start a direct conversation with any agent instantly
- **Group browsing** — view agents organized by their Agile Release Train

### LLM Metrics Dashboard

Real-time observability for all LLM usage at `/metrics`:

- **Cost tracking** — per-agent, per-mission, per-provider spend
- **Latency monitoring** — P50/P95/P99 latency per model and provider
- **Provider comparison** — side-by-side cost/latency/quality across providers
- **Token budget alerts** — configurable thresholds with dashboard warnings

### Agent Evaluation Framework

LLM-as-judge scoring system at `/evals`:

- **Golden dataset** — curated test cases with expected outputs
- **Automated scoring** — LLM judge evaluates agent responses against ground truth
- **Per-agent benchmarks** — track quality scores over time and across versions
- **Regression detection** — alert on quality drops after agent prompt changes

### Tool Builder

No-code tool creation at `/tool-builder`:

- **HTTP tools** — configure REST API calls with headers, auth, and response mapping
- **SQL tools** — write SQL queries that agents can execute against configured databases
- **Shell tools** — wrap shell commands as agent-callable tools with parameter templating
- **Instant activation** — new tools available to agents immediately after saving

### Multi-Tenant Workspaces

Isolated project namespaces at `/workspaces`:

- **Namespace isolation** — separate data, agents, and memory per workspace
- **Per-client deployment** — onboard multiple clients or projects without cross-contamination
- **Workspace switching** — switch context without logout
- **RBAC per workspace** — granular role assignments scoped to each workspace

### Mission Replay

Step-by-step mission execution replay at `/missions/{id}/replay`:

- **Full execution history** — every agent turn, tool call, and LLM response
- **Per-step cost and tokens** — see exactly what each agent spent
- **Duration breakdown** — timeline view showing where time was spent
- **Exportable** — download replay as JSON for analysis or debugging

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
sf agents list                         # 181 agents
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

24 MCP tools for AI agent integration (port 9501):

```bash
# Start MCP server
python3 -m platform.mcp_platform.server

# Tools available:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architecture

### Platform Overview

```
                        ┌──────────────────────┐
                        │   CLI (sf) / Web UI  │
                        │   REST API :8090     │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     FastAPI Server           │
                    │  Auth (JWT + RBAC + OAuth)   │
                    │  17 route modules            │
                    └──┬──────────┬────────────┬───┘
                       │          │            │
          ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
          │ Agent Engine │   │ Workflow │   │   Mission    │
          │ 181 agents   │   │  Engine  │   │    Layer     │
          │ executor     │   │ 42 defs  │   │ SAFe cycle   │
          │ loop+retry   │   │ 10 ptrns │   │ Portfolio    │
          └──────┬───────┘   │ phases   │   │ Epic/Feature │
                 │           │ retry    │   │ Story/Sprint │
                 │           │ skip     │   └──────────────┘
                 │           │ ckpoint  │
                 │           └────┬─────┘
                 │                │
     ┌───────────┴────────────────┴───────────────┐
     │              Services                       │
     │  LLM Client (multi-provider fallback)       │
     │  Tools (code, git, deploy, memory, security)│
     │  MCP Bridge (fetch, memory, playwright)     │
     │  Quality Engine (10 dimensions)             │
     │  Notifications (Slack, Email, Webhook)      │
     └───────────────────┬─────────────────────────┘
                         │
     ┌───────────────────┴─────────────────────────┐
     │              Operations                      │
     │  Watchdog (auto-resume, stall detection)     │
     │  Auto-Heal (incident > triage > fix)         │
     │  OpenTelemetry (tracing + metrics > Jaeger)  │
     └───────────────────┬─────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   SQLite + Memory   │
              │   4-layer memory    │
              │   FTS5 search       │
              └─────────────────────┘
```

### Pipeline Flow

```
Mission Created
     │
     ▼
┌─────────────┐     ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Select     │────▶│sequential│    │ parallel │    │hierarchic│
│  Pattern    │────▶│          │    │          │    │          │
└─────────────┘────▶│ adversar.│    │          │    │          │
                    └────┬─────┘    └────┬─────┘    └────┬─────┘
                         └───────────────┴───────────────┘
                                         │
                    ┌────────────────────────────────────────┐
                    │         Phase Execution                 │
                    │                                        │
                    │  Agent ──▶ LLM Call ──▶ Result         │
                    │                          │             │
                    │              ┌───success──┴──failure──┐│
                    │              ▼                        ▼│
                    │         Code phase?            Retries? │
                    │           │ yes                  │ yes │
                    │           ▼                      ▼     │
                    │     Sandbox Build         Retry w/     │
                    │     Validation            backoff      │
                    │           │                      │ no  │
                    │           ▼                      ▼     │
                    │     Quality Gate          skip_on_fail?│
                    │      │        │            │yes  │no   │
                    │    pass     fail            │     │     │
                    │      │        │             │     ▼     │
                    │      ▼        ▼             │   PAUSED  │
                    │  Checkpoint  PAUSED ◀───────┘     │     │
                    └──────┬─────────────────────────────┘    │
                           │                                  │
                    More phases? ──yes──▶ next phase          │
                           │ no                               │
                           ▼                    watchdog      │
                    Mission Completed     auto-resume ◀───────┘
```

### Observability

```
┌──────────────────────┐    ┌────────────────────────────────┐
│   OTEL Middleware     │    │     Continuous Watchdog         │
│   (every request)     │    │                                │
│   spans + metrics     │    │  health check    every 60s     │
│         │             │    │  stall detection  phases>60min │
│         ▼             │    │  auto-resume     5/batch 5min  │
│   OTLP/HTTP export    │    │  session recovery  >30min      │
│         │             │    │  failed cleanup   zombies      │
│         ▼             │    └────────────────────────────────┘
│   Jaeger :16686       │
└──────────────────────┘    ┌────────────────────────────────┐
                            │     Failure Analysis            │
┌──────────────────────┐    │                                │
│   Quality Engine      │    │  error classification          │
│   10 dimensions       │    │  phase heatmap                 │
│   quality gates       │    │  recommendations               │
│   radar chart         │    │  resume-all button             │
│   badge + scorecard   │    └────────────────────────────────┘
└──────────────────────┘
                            ┌────────────────────────────────┐
         All data ─────────▶│  Dashboard /analytics           │
                            │  tracing stats + latency chart  │
                            │  error doughnut + phase bars    │
                            │  quality radar + scorecard      │
                            └────────────────────────────────┘
```

### Deployment

```
Docker (recommended) → http://localhost:8090
Local (dev)          → http://localhost:8090
Production           → your own infrastructure
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
│   ├── patterns/            # 10 orchestration patterns
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

### Quality Metrics — Industrial Monitoring
- **10 deterministic dimensions** — complexity, coverage (UT/E2E), security, accessibility, performance, documentation, architecture, maintainability, adversarial
- **Quality gates on workflow phases** — PASS/FAIL badges per phase with configurable thresholds (always/no_veto/all_approved/quality_gate)
- **Quality dashboard** at `/quality` — global scorecard, per-project scores, trend snapshots
- **Quality badges everywhere** — mission detail, project board, workflow phases, main dashboard
- **No LLM required** — all metrics computed deterministically using open-source tools (radon, bandit, semgrep, coverage.py, pa11y, madge)

### 4 Auto-Provisioned Missions per Project
Every project automatically gets 4 operational missions:
- **MCO/TMA** — continuous maintenance: health monitoring, incident triage (P0-P4), TDD fix, non-regression validation
- **Security** — weekly SAST scans, dependency audit, CVE watch, code review
- **Tech Debt** — monthly debt reduction: complexity audit, WSJF prioritization, refactoring sprints
- **Self-Healing** — autonomous incident pipeline: 5xx detection → TMA mission creation → agent diagnosis → code fix → validation

### Continuous Improvement
- **quality-improvement workflow** — scan → identify worst dimensions → plan & execute improvements
- **retrospective-quality workflow** — sprint retro with ROTI, incidents, quality metrics → action items
- **skill-evolution workflow** — analyze agent performance → update prompts → evolve skills
- **Feedback loop** — metrics → analysis → improvement → re-scan → track progress

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
- Playwright E2E test suite (11 spec files)
- Internationalization (EN/FR)
- Real-time notifications (Slack, Email, Webhook)
- Design System pipeline in workflows (UX → dev → review)
- 3D Agent World visualization

### Darwin Team Fitness — Evolutionary Agent Selection
- **Thompson Sampling selection** — probabilistic agent+pattern team selection via `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type)`
- **Fine-grained fitness tracking** — separate fitness score per context: a team expert at Angular migration may be poor at Angular new features; scores never bleed across contexts
- **Similarity fallback** — cold start handled by tech prefix matching (`angular_19` → `angular_*` → `generic`), ensuring no team goes unselected
- **Soft retirement** — consistently weak teams get `weight_multiplier=0.1`, deprioritized but never deleted; recoverable with one click
- **OKR / KPI system** — objectives and key results per domain and phase type; 8 default seeds (code/migration, security/audit, architecture/design, testing, docs, etc.)
- **A/B shadow testing** — automatic parallel shadow runs when two teams have close fitness scores (delta < 10) or at 10% probability; neutral evaluator picks winner
- **Teams dashboard** at `/teams` — leaderboard with champion/rising/declining/retired badges, inline OKR editing with green/amber/red status, Chart.js evolution charts, selection history, A/B test results
- **Non-breaking opt-in** — `agent_id: "skill:developer"` in patterns activates Darwin selection; explicit agent IDs are untouched

## Adaptive Intelligence — GA · RL · Thompson Sampling · OKR

The platform continuously self-optimizes through three complementary AI engines that work together to select the best team, pattern, and workflow configuration for every mission.

### Thompson Sampling — Probabilistic Team Selection

Darwin selects agent+pattern teams using **Bayesian bandit exploration**:

- `Beta(α=wins+1, β=losses+1)` distribution per `(agent_id, pattern_id, technology, phase_type)` context
- **Fine-grained fitness** — separate score per context; Angular-migration expertise never bleeds into Angular new-features
- **Cold-start similarity fallback** — `angular_19` → `angular_*` → `generic` prefix chain ensures no team is left unselected
- **Soft retirement** — consistently weak teams get `weight_multiplier=0.1`, deprioritized but recoverable in one click
- **A/B shadow testing** — automatic parallel shadow runs when two teams have close fitness (delta < 10) or at 10% probability; neutral evaluator picks the winner

**Darwin LLM** extends Thompson Sampling to model selection: same team competes across multiple LLM providers; `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type, llm_model)` — the best model wins automatically per context.

### Genetic Algorithm — Workflow Evolution

A nightly GA engine (`platform/agents/evolution.py`) evolves workflow templates using historical mission data:

- **Genome** = ordered list of `PhaseSpec` (pattern, agents, gate) — every workflow is a chromosome
- **Population** of 40 genomes, up to 30 generations, elite=2 carried unchanged
- **Crossover** — random splice of two parent phase lists
- **Mutation** — random swap of `pattern_id`, `gate`, or `agents` list (rate 15%)
- **Fitness function** — weighted combination of: phase success rate, agent fitness scores, gate veto rate, mission lead time
- **Tournament selection** (k=3) — avoids premature convergence
- **Top-3 proposals** saved to `evolution_proposals` table for human review before applying
- **On-demand trigger** via `POST /api/evolution/run/{wf_id}` — review proposals in the Workflows → Evolution tab
- **Scheduler** — runs nightly per active workflow; skipped if <5 missions exist (not enough signal)

### Reinforcement Learning — Mid-Mission Pattern Adaptation

A Q-learning policy (`platform/agents/rl_policy.py`) recommends **pattern switches in real time** during mission execution:

- **Action space**: `keep`, `switch_parallel`, `switch_sequential`, `switch_hierarchical`, `switch_debate`, `add_agent`, `remove_agent`
- **State encoding** — `(wf_id, phase_position_bucket, rejection_pct_bucket, quality_score_bucket)` — compact, generalizable
- **Q-update** (offline batch): `Q(s,a) ← Q(s,a) + α × [r + γ × max Q(s',·) − Q(s,a)]`
- **Hyperparameters**: α=0.1, γ=0.9, ε=0.1 (10% exploration), confidence threshold=0.70, min 3 state visits to fire
- **Experience replay** — `rl_experience` table accumulates `(state, action, reward, next_state)` tuples from every phase completion
- **Rewards** — positive for quality improvement + time saved; negative for rejections and SLA breaches
- **Integration** — called by `engine.py` at phase start; recommendations only fire above confidence threshold; always graceful degradation to the default pattern

### OKR / KPI — Objectives & Key Results

Quantified success criteria guide both GA fitness and RL rewards:

| Domain | Example OKR | Key Results |
|--------|-------------|-------------|
| code/migration | ≥90% build success | build_pass_rate, test_coverage |
| security/audit | 0 critical CVE | cve_critical_count, sast_score |
| architecture | <2h design review | review_duration, approval_rate |
| testing | ≥95% test pass | pass_rate, regression_count |
| documentation | 100% API covered | doc_coverage, freshness |

- **8 default seeds** pre-loaded at startup across all domain/phase-type combinations
- **Inline editing** on the Teams dashboard (`/teams`) — green/amber/red status per target
- **OKR-to-fitness bridge** — OKR attainment directly feeds the GA fitness function and RL reward signal
- **Per-project OKRs** — override defaults per project in the Settings page

### Simulation & Backtesting

Before applying any GA proposal or RL recommendation live, the platform can run **simulations**:

- `simulation_runs` table stores synthetic mission runs against proposed workflow genomes
- Compare simulated vs historical outcomes before promoting a proposal
- Results visible in the Workflows → Evolution tab alongside proposal cards

### Where to See It

| Feature | URL |
|---------|-----|
| Darwin Team leaderboard | `/teams` |
| GA proposals & evolution history | `/workflows` → Evolution tab |
| RL policy stats | `/analytics` or the Ops dashboard |
| OKR editing | `/teams` → OKR column |
| Adaptive Intelligence sidebar | All pages (role: DSI / Dev) |

## What's New in v2.2.0 (Feb 2026)

### OpenTelemetry & Distributed Tracing
- **OTEL integration** — OpenTelemetry SDK with OTLP/HTTP exporter to Jaeger
- **ASGI tracing middleware** — every HTTP request traced with spans, latency, status
- **Tracing dashboard** at `/analytics` — request stats, latency charts, operation table
- **Jaeger UI** — full distributed trace exploration at port 16686

### Pipeline Failure Analysis
- **Failure classification** — Python-based error categorization (setup_failed, llm_provider, timeout, phase_error, etc.)
- **Phase failure heatmap** — identify which pipeline phases fail most often
- **Recommendations engine** — actionable suggestions based on failure patterns
- **Resume All button** — one-click mass-resume of paused runs from the dashboard

### Continuous Watchdog
- **Auto-resume** — automatically resume paused runs in batches (5/batch, every 5 min, max 10 concurrent)
- **Stale session recovery** — detect sessions inactive >30 min, mark as interrupted for retry
- **Failed session cleanup** — clean zombie sessions blocking pipeline progress
- **Stall detection** — missions stuck in a phase >60 min get automatic retry

### Phase Resilience
- **Per-phase retry** — configurable retry count (default 3x) with exponential backoff per phase
- **skip_on_failure** — phases can be marked optional, allowing pipeline to continue
- **Checkpointing** — completed phases saved, smart resume skips finished work
- **Phase timeout** — 10-minute cap prevents infinite hangs

### Sandbox Build Validation
- **Post-code build check** — after code generation phases, automatically run build/lint
- **Auto-detect build system** — npm, cargo, go, maven, python, docker
- **Error injection** — build failures injected into agent context for self-correction

### Quality UI Enhancements
- **Radar chart** — Chart.js radar visualization of quality dimensions on `/quality`
- **Quality badge** — colored score circle for project headers (`/api/dashboard/quality-badge`)
- **Mission scorecard** — quality metrics in mission detail sidebar (`/api/dashboard/quality-mission`)

### Multi-Model LLM Routing
- **3 specialized models** — `gpt-5.2` for heavy reasoning/architecture, `gpt-5.1-codex` for code/tests, `gpt-5-mini` for lightweight tasks
- **Role-based routing** — agents automatically get the right model based on their tags (`reasoner`, `architect`, `developer`, `tester`, `security`, `doc_writer`, etc.)
- **DB-configurable** — routing matrix stored in `session_state`, editable live from Settings → LLM without restart
- **60s cache** with instant invalidation on save
- **Provider support** — Azure AI Foundry (gpt-5.2, gpt-5.1-codex, gpt-5.1-mini), Azure OpenAI (gpt-5-mini), MiniMax M2.5

### Darwin LLM Thompson Sampling
- **Model-level A/B testing** — same team (agent + pattern) competes across different LLM models; the best model for each context wins automatically
- **Beta distribution sampling** — `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type, llm_model)` — fine-grained, no cross-context bleed
- **Warmup phase** — random exploration for first 5 runs, then Thompson Sampling takes over
- **Fitness tables** — dedicated `team_llm_fitness` and `team_llm_ab_tests` tables, separate from agent team selection
- **Teams → LLM A/B tab** — live leaderboard per model and A/B test history at `/teams`
- **Priority chain** — Darwin LLM → DB routing config → hardcoded defaults (graceful degradation)

### Settings — LLM Tab
- **Providers grid** — shows all configured providers with enabled/disabled status and missing-key hints
- **Routing matrix** — configure heavy/light model per category (Reasoning, Production/Code, Tasks, Redaction) with dropdowns
- **Darwin LLM A/B section** — live view of ongoing model experiments from the Settings page
- **Save & invalidate** — one-click save pushes config to DB and flushes the executor cache

## What's New in v2.7.0 (2026)

### Knowledge Management System
- **4 new agents** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **ART Knowledge team** — dedicated Agile Release Train for knowledge operations
- **Nightly `knowledge-maintenance` workflow** — automatic curation, deduplication, freshness scoring
- **Memory Health dashboard** — knowledge health metrics panel in the Metrics tab
- **Knowledge Health badge** — visible in the Settings page

### Memory Intelligence
- **Relevance scoring** — `confidence × recency × access_boost` formula for ranked retrieval
- **Access tracking** — `access_count` and `last_read_at` fields on every memory entry
- **Automatic pruning** — stale entries below threshold removed on each nightly run

### LLM Cost Tracking
- **Per-mission cost** — displayed in the mission timeline tab header
- **Auto-summed** — aggregated from `llm_traces` table, no manual tracking needed

### Mission Timeline
- **Swimlane timeline tab** — in Mission Control, shows agent phases as horizontal swim lanes
- **Phase durations** — visual representation of how long each phase took

### Quality Scoring
- **PhaseRun `quality_score` field** — populated by the adversarial guard after each phase

### Project Export/Import
- **ZIP archive** — contains `project.json` + all missions + mission runs + memories
- **Portable projects** — export from one instance, import into another

### Input Validation
- **Pydantic models** — all POST/PATCH routes now validated with strict input schemas

### BSCC Domain Guidelines
- **Domain-level architecture guidelines** — Confluence/Solaris guidelines enforced per project domain
- **Configurable per project** in Settings

### Settings Integrations Hub
- **Configurable tool integrations** — Jira, Confluence, SonarQube available to all agents from a single Settings panel

### Browser Push Notifications
- **Web Push API (VAPID)** — native browser push notifications for mission events and alerts

## What's New in v3.0.0 (2026)

### Agent Marketplace
- **191 agents catalogued** — full-text search, filter by ART/role/skills at `/marketplace`
- **Agent profiles** — detailed view with tools, skills, and recent session history
- **One-click launch** — start a direct session with any agent from their profile page

### Mission Replay UI
- **Step-by-step replay** — every agent turn and tool call replayed at `/missions/{id}/replay`
- **Per-step cost and tokens** — granular LLM spend breakdown per agent
- **Exportable history** — download replay as JSON for debugging and auditing

### LLM Metrics Dashboard
- **Real-time cost/latency/provider monitoring** at `/metrics`
- **Per-agent and per-mission spend** — identify expensive agents and optimize
- **Provider comparison** — side-by-side P50/P95 latency and cost across providers

### RBAC + Rate Limiting
- **Workspace-scoped RBAC** — role assignments per workspace, not just per platform
- **Per-user rate limiting** — configurable token/request quotas per role
- **Audit trail** — all RBAC changes logged with actor, timestamp, and change detail

### Agent Evaluation Framework
- **LLM-as-judge scoring** — automated evaluation against golden datasets at `/evals`
- **Per-agent benchmarks** — track quality over time and detect regressions
- **Configurable judges** — use any configured LLM provider as the evaluation judge

### Tool Builder
- **No-code tool creation** at `/tool-builder` — HTTP, SQL, and shell tools
- **Instant activation** — tools available to agents immediately after saving
- **Parameter templates** — define input schemas with types and validation

### Multi-Tenant Workspaces
- **Isolated namespaces** at `/workspaces` — separate data, agents, and memory per workspace
- **Per-client deployment** — onboard multiple clients without cross-contamination
- **RBAC per workspace** — granular role assignments per namespace

### YAML Agents Hot-Reload
- **Live agent updates** — edit agent YAML files and reload without restarting the platform
- **No downtime** — in-flight missions continue with the previous agent definition

## Ecosystem & Related Tools

| Tool | Description | Why it matters |
|------|-------------|----------------|
| [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Rust Token Killer — CLI proxy that reduces LLM token consumption by 60-90% on common dev commands | Integrating into agent tool wrappers to reduce session costs |

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the AGPL v3 License - see the [LICENSE](LICENSE) file for details.

## Support

- Live: https://sf.macaron-software.com
- Issues: https://github.com/macaron-software/software-factory/issues
- Discussions: https://github.com/macaron-software/software-factory/discussions
