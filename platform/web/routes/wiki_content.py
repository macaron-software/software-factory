"""Wiki seed content — all built-in documentation pages."""

WIKI_PAGES = [
    # ── Getting Started ─────────────────────────────────────────
    {
        "slug": "getting-started",
        "title": "Getting Started",
        "category": "Guide",
        "icon": "",
        "sort_order": 10,
        "content": """\
# Getting Started

Welcome to the **Software Factory** — a multi-agent collaborative platform for software engineering.

## Quick Start

```bash
# Clone & install
git clone https://github.com/macaron-software/software-factory.git
cd software-factory/platform
pip install -r requirements.txt

# Run locally
python -m uvicorn platform.server:app --port 8090 --ws none

# Open http://localhost:8090
```

## Docker

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup    # builds Docker image
make run      # starts platform on port 8090
```

## Home Page — 8 Ideation Groups

The home page (`/`) provides 8 tabs covering the full strategic and technical cycle:

| Tab | Role |
|-----|------|
| **CTO Jarvis** | Strategic AI advisor — recommended entry point for new projects |
| **Business Ideation** | 6-agent marketing team, SWOT/TAM/KPI plans |
| **Project Ideation** | 5-agent tech team, SAFe Epic generation |
| **Knowledge & Research** | Technology watch and document analysis |
| **Architecture Committee** | Multi-agent architectural review and decisions |
| **Security Council** | Security audit, SAST, CVE analysis |
| **Data & AI** | Data analysis, MLOps, AI governance |
| **PI Planning** | SAFe Program Increment planning |

## Recommended Entry Point: CTO Jarvis

Open the home page and use the **CTO Jarvis** tab to create a new project in one conversation:

> *"Create a new project for an enterprise carpooling app with React and Python."*

Jarvis (Gabriel Mercier, Strategic Orchestrator) will analyze your request, create the project,
provision a SAFe backlog, and start the first missions automatically.

## Other Entry Points

- **Agent Marketplace** (`/marketplace`) — browse all 191 agents, filter by ART/role/skills, start a direct session
- **Portfolio** (`/portfolio`) — manage epics, features, stories with WSJF prioritization
- **Projects** (`/projects`) — create or manage projects manually
- **Evaluations** (`/evals`) — run LLM-as-judge benchmarks on any agent
- **Tool Builder** (`/tool-builder`) — create custom HTTP/SQL/shell tools without code
- **Workspaces** (`/workspaces`) — manage isolated multi-tenant namespaces

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATFORM_LLM_PROVIDER` | `minimax` | LLM provider (minimax, openai-compatible, azure-openai) |
| `PLATFORM_LLM_MODEL` | `MiniMax-M2.5` | Model name |
| `PLATFORM_PORT` | `8090` | HTTP port |
| `DATABASE_URL` | (SQLite fallback) | PostgreSQL connection string |
""",
    },
    {
        "slug": "concepts",
        "title": "Core Concepts",
        "category": "Guide",
        "icon": "",
        "sort_order": 20,
        "content": """\
# Core Concepts

## Project

Everything starts with a **Project** — a complete workspace:

```
PROJECT
├── Identity     → name, description, avatar, color
├── Vision       → product vision document (VISION.md)
├── Git          → local repository, history, branches
├── Agent Lead   → default LLM agent (human interface)
├── Agents       → pool of available agents
├── Patterns     → agent assemblies (orchestration)
├── Workflows    → chains of patterns (pipelines)
├── Memory       → persistent project memory (FTS5)
├── Tools        → connected MCP tools
├── Sessions     → current conversations/executions
└── Artifacts    → produced files (code, specs, tests, docs)
```

## Agent

A specialized AI persona with a role, system prompt, skills, tools, and personality.

## Mission

A user request processed by the platform: prompt → workflow → agent collaboration → result.

## Pattern

How agents collaborate: Sequential, Parallel, Loop, Router, Aggregator, Adversarial, Negotiation, Hierarchical.

## Workflow

Chains multiple patterns into a pipeline (e.g. code_review = Router → Sequential → Adversarial → Aggregator).

## SAFe Integration

Program Increments, Features & Epics with WSJF prioritization, ART (Agile Release Train), Backlog with ideation.
""",
    },
    {
        "slug": "user-guide",
        "title": "User Guide",
        "category": "Guide",
        "icon": "",
        "sort_order": 30,
        "content": """\
# User Guide

## Dashboard

Personalized by perspective: **DSI** (portfolio), **Product** (backlog), **Engineering** (sessions), **Scrum Master** (velocity).

## Projects

1. Navigate to **Projects** → **New Project**
2. Fill in name, description, select a color
3. Choose Agent Lead, configure Git (optional)
4. Use the chat to send missions

## Missions

- **Status flow**: planning → active → review → completed
- Each mission has runs (attempts) with phases (agent steps)

## Sessions

Live agent collaboration with real-time SSE streaming, color-coded by role.

## Backlog & Ideation

- **Backlog**: WSJF-prioritized features
- **Ideation**: multi-agent brainstorming — type a prompt, agents collaborate

## Metrics

| Tab | Content |
|-----|---------|
| **DORA** | Deploy frequency, lead time, change failure rate, MTTR |
| **Quality** | Code quality scores, test coverage, security |
| **Analytics** | Mission stats, agent performance, system health |
| **Monitoring** | Real-time CPU, memory, request latency |
| **Pipeline** | CI/CD pipeline performance |

## Toolbox

| Tab | Content |
|-----|---------|
| **Skills** | Agent skill library |
| **Memory** | Persistent memory browser |
| **MCPs** | MCP server management |
| **API** | Swagger interactive docs |
| **CLI** | Web terminal |
| **Design System** | UI component reference |
| **Wiki** | This documentation |
""",
    },
    # ── Architecture ────────────────────────────────────────────
    {
        "slug": "architecture",
        "title": "Architecture Overview",
        "category": "Architecture",
        "icon": "",
        "sort_order": 10,
        "content": """\
# Architecture Overview

```
┌─── Web UI (HTMX + SSE) ────────────────────────────────┐
│  Dashboard │ Projects │ Sessions │ Agents │ Metrics      │
└─────────────────────────────────────────────────────────┘
         │ SSE (real-time)          │ REST API
┌────────┴──────────────────────────┴────────────────────┐
│              ORCHESTRATOR (Python/FastAPI)               │
│  Router │ Scheduler (WSJF) │ A2A Bus │ Pattern Engine   │
└─────────────────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────────┐
│              AGENT RUNTIME                               │
│  👔 Business  📋 PM  🏗️ Lead Dev  💻 Dev  🧪 Tester    │
│  🔒 Security  🚀 DevOps  🏛️ Architect  🎨 UX  📊 Data │
└─────────────────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────────┐
│  LLM Providers │ Memory (SQLite+FTS5) │ MCP Tools       │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTMX + Jinja2 templates + SSE |
| **Backend** | Python 3.12 + FastAPI + Uvicorn |
| **Database** | SQLite (WAL) + FTS5 full-text search |
| **LLM** | MiniMax M2.5, Azure OpenAI, Azure AI |
| **Tools** | MCP protocol (fetch, memory, playwright, solaris) |
| **Deploy** | Docker on Azure VM + nginx |
| **Auth** | JWT (HttpOnly cookies) |

## Directory Structure

```
platform/
├── server.py          # FastAPI entry point (port 8090)
├── config.py          # Configuration
├── models.py          # Pydantic models
├── web/
│   ├── routes/        # 13 route modules + API sub-package
│   ├── templates/     # Jinja2 HTML templates
│   └── static/        # CSS, JS, images
├── agents/            # Agent loop, executor, store
├── orchestrator/      # Mission orchestrator, WSJF
├── patterns/          # 15 orchestration patterns
├── workflows/         # 36 built-in workflows
├── llm/               # Multi-provider LLM client
├── tools/             # Code, git, deploy, memory, security
├── db/                # Migrations and adapters
├── a2a/               # Agent-to-Agent protocol
├── missions/          # SAFe lifecycle
├── mcps/              # MCP server manager
├── memory/            # Persistent memory (FTS5)
├── services/          # Notifications
├── ops/               # Auto-heal, chaos, backup
├── security/          # Auth, RBAC
└── i18n/              # 8 languages
```
""",
    },
    {
        "slug": "database-schema",
        "title": "Database Schema",
        "category": "Architecture",
        "icon": "",
        "sort_order": 30,
        "content": """\
# Database Schema

## Core Tables

### agents
```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL, role TEXT NOT NULL,
    system_prompt TEXT, skills TEXT DEFAULT '[]',
    tools TEXT DEFAULT '[]', avatar TEXT DEFAULT '',
    status TEXT DEFAULT 'idle',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### missions
```sql
CREATE TABLE missions (
    id TEXT PRIMARY KEY, project_id TEXT,
    title TEXT, prompt TEXT NOT NULL,
    status TEXT DEFAULT 'planning',
    workflow TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### projects
```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    description TEXT, color TEXT DEFAULT '#8b5cf6',
    git_repo TEXT, agent_lead TEXT, vision TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### users
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
    name TEXT, hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    is_active INTEGER DEFAULT 1
);
```

## Full Table List (~30 tables)

`agents`, `missions`, `mission_runs`, `run_phases`, `projects`, `sessions`,
`session_messages`, `memory_entries`, `features`, `feature_deps`,
`program_increments`, `users`, `user_sessions`, `user_project_roles`,
`agent_scores`, `retrospectives`, `quality_reports`, `quality_snapshots`,
`notifications`, `integrations`, `llm_usage`, `wiki_pages`,
`mercato_listings`, `mercato_transfers`, `token_transactions`,
`project_wallets`, `agent_assignments`, `platform_incidents`,
`support_tickets`, `confluence_pages`, `custom_ai_providers`, `session_state`

Use `db status` in the CLI to see row counts.
""",
    },
    # ── Agents ──────────────────────────────────────────────────
    {
        "slug": "agents",
        "title": "Agents System",
        "category": "Agents",
        "icon": "",
        "sort_order": 10,
        "content": """\
# Agents System

## Built-in Roles (~160 agents)

| Role | Count | Purpose |
|------|-------|---------|
| 💻 Developer | ~30 | Code generation, refactoring |
| 🧪 Tester | ~15 | Test writing, QA |
| 🏛️ Architect | ~10 | System design |
| 🔒 Security | ~8 | Audits, vulnerability scanning |
| 📋 PM | ~10 | Planning, tracking |
| 👔 Business | ~8 | Requirements |
| 🎨 UX/UI | ~8 | Design, accessibility |
| 🚀 DevOps | ~10 | CI/CD, infrastructure |

## Agent Lifecycle

```
Created → Idle → Assigned → Running → Idle
```

## Scoring

Agents are scored on quality, speed, collaboration, and innovation.
Scores affect future selection by the Orchestrator.

## Custom Agents (YAML)

```yaml
id: my-agent
name: "Data Pipeline Expert"
role: developer
system_prompt: |
  Expert in Airflow, dbt, Snowflake.
skills: [data-pipeline-design]
tools: [code, git]
```
""",
    },
    {
        "slug": "patterns",
        "title": "Orchestration Patterns",
        "category": "Agents",
        "icon": "",
        "sort_order": 20,
        "content": """\
# Orchestration Patterns (15)

## Core Patterns

| Pattern | Flow | Use Case |
|---------|------|----------|
| **Sequential** | A → B → C | Code → Review → Test |
| **Parallel** | A, B, C simultaneously | Brainstorming |
| **Loop** | Dev → Test → Fix → repeat | TDD |
| **Router** | Dispatch to specialist | Triage |
| **Aggregator** | Many propose → one synthesizes | Architecture decisions |
| **Adversarial** | Producer → Challenger | Code review |
| **Negotiation** | Agents debate → consensus | Tech choices |
| **Hierarchical** | Manager → sub-agents | Complex projects |

## Engine-Only Patterns

- **Evaluate** — Score and rank outputs
- **Map-Reduce** — Split, process, merge
- **Pipeline** — Sequential with branching

## Auto-Selection

The Orchestrator selects patterns based on workflow definition, task complexity, agent skills, and historical success rates.
""",
    },
    {
        "slug": "workflows",
        "title": "Workflows",
        "category": "Agents",
        "icon": "",
        "sort_order": 30,
        "content": """\
# Workflows (36 built-in)

## Development
| Workflow | Description |
|----------|-------------|
| `code_generation` | Analyze → Code → Review |
| `tdd_workflow` | Test → Code → Verify → Iterate |
| `code_review` | Review → Challenge → Approve |
| `refactoring` | Analyze → Plan → Refactor → Verify |
| `bug_fix` | Diagnose → Fix → Test → Verify |

## Architecture
| Workflow | Description |
|----------|-------------|
| `architecture_design` | Multiple architects propose → synthesize |
| `tech_decision` | Agents debate tech choices |
| `api_design` | Analyze → Design → Review → Document |

## Quality & Security
| Workflow | Description |
|----------|-------------|
| `security_audit` | Scan → Challenge → Report |
| `quality_gate` | Multiple quality checks in parallel |

## DevOps
| Workflow | Description |
|----------|-------------|
| `deployment` | Build → Test → Stage → Deploy |
| `incident_response` | Triage → Investigate → Fix → Report |

## Custom Workflows (YAML)

```yaml
id: my-workflow
name: "Custom Pipeline"
phases:
  - name: analyze
    pattern: router
    agents: [architect, lead-dev]
  - name: implement
    pattern: parallel
    agents: [dev-frontend, dev-backend]
  - name: review
    pattern: adversarial
    agents: [reviewer, security]
```
""",
    },
    {
        "slug": "a2a-protocol",
        "title": "A2A Protocol",
        "category": "Agents",
        "icon": "",
        "sort_order": 40,
        "content": """\
# Agent-to-Agent (A2A) Protocol

## Message Types

| Type | Description |
|------|-------------|
| `request` | Ask another agent for help |
| `response` | Reply to a request |
| `broadcast` | Notify all agents |
| `veto` | Block a decision (adversarial) |
| `delegate` | Pass work to another agent |
| `negotiate` | Propose/counter-propose |

## Bus Architecture

```
Agent A ──┐
Agent B ──┼── A2A Bus ──┬── Pattern Engine
Agent C ──┘             └── Session Logger
```

## Veto System

- **Soft veto**: request revision (loop continues)
- **Hard veto**: reject entirely (escalate to human)
""",
    },
    # ── Projects & Missions ─────────────────────────────────────
    {
        "slug": "projects",
        "title": "Projects",
        "category": "Projects",
        "icon": "",
        "sort_order": 10,
        "content": """\
# Projects

## Creating a Project

### Via UI
Projects → New Project → fill name, description, color → select Agent Lead

### Via API
```bash
curl -X POST /api/projects \\
  -H "Content-Type: application/json" \\
  -d '{"name": "My Project", "description": "...", "color": "#8b5cf6"}'
```

### Via CLI
```bash
sf projects create "My Project" --description "..."
```

## Project Chat

1. Type a message in the project chat
2. Agent Lead analyzes and selects workflow
3. Agents collaborate → results stream via SSE
""",
    },
    {
        "slug": "missions",
        "title": "Missions & SAFe",
        "category": "Projects",
        "icon": "",
        "sort_order": 20,
        "content": """\
# Missions & SAFe

## Mission Lifecycle

```
User Prompt → Planning → Active → Review → Completed
                                      ↓
                                   Failed / Interrupted
```

## SAFe Framework

- **Program Increments (PI)** — time-boxed planning (8-12 weeks)
- **Features** — WSJF-prioritized capabilities
- **Epics** — large initiatives: Funnel → Analyzing → Backlog → Implementing → Done
- **ART** — teams of agents with Scrum Master

### WSJF Scoring
```
WSJF = Cost of Delay / Job Size
Cost of Delay = User Value + Time Criticality + Risk Reduction
```
""",
    },
    # ── DevOps ──────────────────────────────────────────────────
    {
        "slug": "deployment",
        "title": "Deployment Guide",
        "category": "DevOps",
        "icon": "",
        "sort_order": 10,
        "content": """\
# Deployment Guide

## Docker (Recommended)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
docker compose up -d
# → http://localhost:8090
```

## Azure VM (Production)

```bash
# nginx reverse proxy → Docker container (port 8090)
# Patches: /opt/macaron/patches → /patches in container
# Backup: docker exec platform cp /app/data/platform.db /app/data/backup.db
```

## Local Development

```bash
cd platform && pip install -r requirements.txt
# NEVER --reload, ALWAYS --ws none
python -m uvicorn platform.server:app --port 8099 --ws none --log-level warning

# Tests
python -m pytest tests/ -v                    # 52+ tests
cd tests/e2e && npx playwright test           # 82+ E2E tests
```
""",
    },
    {
        "slug": "cli-reference",
        "title": "CLI Reference",
        "category": "DevOps",
        "icon": "",
        "sort_order": 20,
        "content": """\
# CLI Reference

```bash
alias sf='python3 cli/sf.py'

# Platform
sf status                          # Overview
sf health                          # Health check

# Projects
sf projects list | create | chat ID "msg"

# Missions
sf missions list | show ID | cancel ID

# Agents
sf agents list | show ID | sync

# Ideation
sf ideation "prompt"               # Multi-agent brainstorming (SSE)

# Skills & Memory
sf skills sync | search "query"
sf memory search "query" | project ID | global

# Output
sf status --json                   # JSON format
```

## Configuration
```bash
export SF_PLATFORM_URL=http://localhost:8090    # local
export SF_PLATFORM_URL=http://<AZURE_VM_IP>       # production
```
""",
    },
    {
        "slug": "api-reference",
        "title": "API Reference",
        "category": "DevOps",
        "icon": "",
        "sort_order": 30,
        "content": """\
# API Reference

## Auth
```
POST /api/auth/login     {"email": "...", "password": "..."}
POST /api/auth/refresh   → new access_token
```

## Projects
```
GET/POST   /api/projects
GET/PUT/DELETE /api/projects/{id}
POST       /api/projects/{id}/chat
```

## Missions
```
GET/POST   /api/missions
GET        /api/missions/{id}
GET        /api/missions/{id}/sse    (SSE stream)
POST       /api/missions/{id}/cancel
```

## Agents
```
GET/POST   /api/agents
GET/PUT/DELETE /api/agents/{id}
POST       /api/agents/sync
```

## Wiki
```
GET    /api/wiki/pages
GET    /api/wiki/{slug}
POST   /api/wiki          {"slug", "title", "content", "category"}
PUT    /api/wiki/{slug}    {"content", "title"}
DELETE /api/wiki/{slug}
```

Full Swagger UI: `GET /docs`
""",
    },
    # ── Configuration ───────────────────────────────────────────
    {
        "slug": "llm-providers",
        "title": "LLM Providers",
        "category": "Configuration",
        "icon": "",
        "sort_order": 10,
        "content": """\
# LLM Providers

## Supported

| Provider | Models | Role |
|----------|--------|------|
| **MiniMax** | MiniMax-M2.5 | Primary |
| **Azure OpenAI** | gpt-5-mini | Fallback 1 |
| **Azure AI** | various | Fallback 2 |
| **Demo** | Mock | Testing |

## Fallback Chain

```
MiniMax → (429/error) → Azure OpenAI → (error) → Azure AI → raise
```
Cooldown: 90s on rate limit.

## Keys

```
~/.config/factory/minimax.key
~/.config/factory/azure-openai.key
```
> ⚠️ Never set `*_API_KEY=dummy` — use `PLATFORM_LLM_PROVIDER=demo`.
""",
    },
    {
        "slug": "mcp-servers",
        "title": "MCP Servers",
        "category": "Configuration",
        "icon": "",
        "sort_order": 20,
        "content": """\
# MCP Servers

## Built-in

| Server | Purpose |
|--------|---------|
| **fetch** | HTTP requests, web scraping |
| **memory** | Persistent memory storage |
| **playwright** | Browser automation |
| **solaris** | Design system (Figma, WCAG) |
| **lrm** | Project files, conventions, builds |

## Tool Categories

- **Code**: file read/write, search, AST
- **Git**: status, diff, commit, push, PR
- **Deploy**: Docker, Kubernetes
- **Memory**: store/retrieve, FTS5 search
- **Security**: dependency scan, SAST, secrets
- **Browser**: screenshots, interaction (Playwright)

## Adding MCPs

Toolbox → MCPs → Add Server → configure command, args, env → test → assign to projects.
""",
    },
    {
        "slug": "security",
        "title": "Security & RBAC",
        "category": "Configuration",
        "icon": "",
        "sort_order": 30,
        "content": """\
# Security & RBAC

## Auth
JWT tokens (HttpOnly cookies), bcrypt passwords, server-side sessions.

## Roles

| Role | Permissions |
|------|-------------|
| **Owner** | Full access, user management |
| **Admin** | Project management, agent config |
| **Member** | Create missions, chat |
| **Viewer** | Read-only |

## Security Features

- SQL injection prevention (parameterized queries)
- XSS protection (auto-escaping)
- CSP headers, CORS
- Rate limiting per user/IP
- Agent sandboxing with tool allowlists
- Audit logging (trace_id on every request)
""",
    },
    # ── New enriched pages ──────────────────────────────────────
    {
        "slug": "patterns-guide",
        "title": "Patterns Guide",
        "category": "Guide",
        "icon": "",
        "sort_order": 40,
        "content": """\
# Patterns Guide

The platform includes 15 orchestration patterns. Each pattern determines how agents
communicate, share context, and produce outputs.

## Sequential

Agents execute one after another. The output of each agent feeds into the next.

When to use: ordered pipelines where each step depends on the previous one.
Example: Analyze requirements -> Write code -> Review code -> Write tests.

```yaml
pattern: sequential
agents: [analyst, developer, reviewer, tester]
```

## Parallel

All agents execute simultaneously on the same input. Results are collected when all finish.

When to use: independent tasks that do not depend on each other.
Example: Security scan + Performance audit + Accessibility check.

```yaml
pattern: parallel
agents: [security-expert, performance-expert, accessibility-expert]
max_concurrency: 3
```

## Loop

One agent or a group iterates until a quality threshold is met or max_iterations is reached.

When to use: TDD, self-correcting code generation, iterative refinement.

```yaml
pattern: loop
agents: [developer, tester]
max_iterations: 5
exit_condition: all_tests_pass
```

## Router

A dispatcher agent reads the input and routes to the most appropriate specialist.

When to use: triage, multi-domain questions, classification before processing.

```yaml
pattern: router
dispatcher: tech-lead
routes:
  frontend: [dev-frontend]
  backend: [dev-backend]
  infra: [devops]
```

## Aggregator

Multiple agents each produce a proposal. A synthesis agent combines them into one output.

When to use: architecture decisions, brainstorming, multiple perspectives.

```yaml
pattern: aggregator
contributors: [architect-1, architect-2, architect-3]
synthesizer: lead-architect
```

## Adversarial

A producer creates output. A challenger reviews and may reject. On rejection, the producer
revises. Cycle repeats up to max_retries times.

When to use: high-quality code review, security review, formal spec validation.

```yaml
pattern: adversarial
producer: developer
challenger: senior-reviewer
max_retries: 3
```

The challenger can issue a soft veto (request revision) or hard veto (escalate to human).

## Negotiation

Multiple agents exchange proposals and counter-proposals until consensus is reached
or a moderator breaks the tie.

When to use: tech stack selection, API contract definition, architecture disputes.

```yaml
pattern: negotiation
agents: [architect, lead-dev, devops]
moderator: cto-agent
max_rounds: 4
```

## Hierarchical

A manager agent decomposes the task and dispatches subtasks to specialist workers.
Results flow back up.

When to use: large complex features, multi-file refactoring, cross-team work.

```yaml
pattern: hierarchical
manager: tech-lead
workers: [dev-frontend, dev-backend, devops]
max_depth: 2
```

## Solo

A single agent handles the entire task. Simplest pattern, lowest latency.

When to use: simple, well-scoped tasks. Documentation, quick fixes, Q&A.

```yaml
pattern: solo
agent: developer
```

## Human in the Loop

The workflow pauses at configured steps and waits for human input or approval
before continuing.

When to use: risky operations (deploy to prod), compliance checkpoints, ambiguous requirements.

```yaml
pattern: human_in_the_loop
checkpoints:
  - after: design
    prompt: "Approve the design before implementation?"
  - after: implementation
    prompt: "Review code before deployment?"
```

## Wave

Agents execute in waves. Wave 1 runs in parallel, wave 2 runs after wave 1 completes, etc.

When to use: layered architectures (models first, then API, then UI).

```yaml
pattern: wave
waves:
  - [db-designer, schema-reviewer]
  - [backend-dev, api-designer]
  - [frontend-dev, ui-reviewer]
```

## Network

Agents form a graph where each agent can communicate with its neighbors. No strict ordering.

When to use: research tasks, cross-cutting concerns, dependency analysis.

```yaml
pattern: network
agents: [analyst, researcher, architect, domain-expert]
topology: mesh
```

## Pipeline (engine-only)

Sequential execution with branching. If a condition is met, flow goes to branch A, else B.

## Map-Reduce (engine-only)

Split a large input, process each chunk in parallel, then merge results.
Used internally for large codebase analysis.

## Evaluate (engine-only)

Score outputs from multiple agents and select the best one.
Used internally after aggregator or parallel patterns.

---

## Choosing the Right Pattern

| Situation | Recommended Pattern |
|-----------|-------------------|
| Simple, one-step task | Solo |
| Ordered multi-step process | Sequential |
| Independent parallel tasks | Parallel |
| Iterative improvement | Loop |
| Input categorization | Router |
| Multiple perspectives needed | Aggregator |
| Rigorous quality review | Adversarial |
| Tech decisions with debate | Negotiation |
| Complex decomposable task | Hierarchical |
| Human approval required | Human in the Loop |
| Layered build process | Wave |
""",
    },
    {
        "slug": "workflows-guide",
        "title": "Workflows Guide",
        "category": "Guide",
        "icon": "",
        "sort_order": 50,
        "content": """\
# Workflows Guide

A workflow chains multiple patterns and agents into a repeatable pipeline.
The platform ships with 36 built-in workflows.

## Workflow Anatomy

```yaml
id: feature-sprint
name: "Feature Sprint"
description: "Full sprint cycle: plan, code, test, review, document"
phases:
  - id: planning
    pattern: hierarchical
    agents: [product-owner, scrum-master, tech-lead]
    description: "Break down feature into tasks"
  - id: implementation
    pattern: parallel
    agents: [dev-frontend, dev-backend]
    description: "Parallel implementation"
  - id: review
    pattern: adversarial
    agents: [developer, senior-reviewer]
    description: "Code review with challenge"
  - id: testing
    pattern: loop
    agents: [developer, qa-engineer]
    max_iterations: 3
  - id: documentation
    pattern: solo
    agent: tech-writer
config:
  timeout_minutes: 120
  on_complete:
    workflow_id: review-cycle
    condition: completed
```

## Development Workflows

### code-generation
Single feature implementation.
Phases: Analyze -> Architect -> Code -> Self-review.
Pattern mix: Router + Sequential + Adversarial.
Duration: 5-15 min.

### tdd-workflow
Test-driven development cycle.
Phases: Write failing tests -> Implement -> Run tests -> Fix -> Repeat.
Pattern: Loop (max 5 iterations).
Exit condition: all tests pass.

### bug-fix
Diagnose and fix a reported bug.
Phases: Reproduce -> Root cause -> Fix -> Regression test -> Verify.
Pattern: Sequential + Adversarial.

### refactoring
Safe code refactoring with quality preservation.
Phases: Analyze coverage -> Identify smells -> Plan refactor -> Implement -> Verify behavior.
Pattern: Hierarchical + Sequential.

### code-review
Thorough code review by multiple reviewers.
Phases: Initial review -> Security check -> Performance check -> Aggregate feedback.
Pattern: Parallel reviewers + Aggregator.

### api-design
Design and document a REST API.
Phases: Analyze requirements -> Draft contract -> Security review -> Doc generation.
Pattern: Sequential + Adversarial.

## Architecture Workflows

### architecture-design
System architecture proposal and validation.
Phases: Multiple architects propose -> Challenge assumptions -> Consensus -> Document ADR.
Pattern: Aggregator + Adversarial + Negotiation.

### tech-decision
Evaluate and decide on a technology choice.
Phases: Define criteria -> Research options -> Agents argue for/against -> Vote.
Pattern: Negotiation + Aggregator.

### database-design
Schema design and normalization.
Phases: Analyze domain model -> Design schema -> Review -> Migration plan.
Pattern: Sequential + Adversarial.

## Quality & Security Workflows

### security-audit
Comprehensive security review.
Phases: SAST scan -> Dependency check -> Manual review -> Threat modeling -> Report.
Pattern: Parallel + Aggregator.

### sast-continuous
Lightweight automated security scan (runs on each commit).
Pattern: Solo (security agent with SAST tool).
Duration: 1-3 min.

### quality-gate
Multi-dimensional quality assessment.
Phases: Test coverage -> Code complexity -> Security -> Accessibility -> Score.
Pattern: Parallel + Aggregator.

## DevOps Workflows

### deployment
Full deployment pipeline.
Phases: Build -> Unit tests -> Integration tests -> Stage deploy -> Smoke test -> Prod deploy.
Pattern: Sequential with human_in_the_loop before prod.

### incident-response
Respond to a production incident.
Phases: Triage -> Impact assessment -> Root cause -> Fix -> Post-mortem.
Pattern: Hierarchical + Sequential.

### tma-maintenance
Technical maintenance and debt reduction.
Phases: Analyze debt -> Prioritize -> Fix -> Verify -> Document.
Pattern: WSJF Router + Sequential.

## Specialized Workflows

### design-system-component
Design system component creation (Solaris agents).
Phases: Figma audit -> Component generation -> A11y validation -> Visual regression -> Storybook docs -> PR review.
Pattern: Sequential with Solaris MCP tools.
On complete: chains to review-cycle.

### sf-pipeline
Full software factory pipeline from idea to production.
Phases: Ideation -> Architecture -> Implementation -> Testing -> Security -> Deploy.
10-phase meta-cycle.

### ideation-to-prod
Complete product lifecycle from ideation to production deployment.
The longest workflow: 10 phases spanning planning, architecture, implementation, testing, security, and deployment.

## Creating Custom Workflows

```yaml
# platform/workflows/definitions/my-workflow.yaml
id: my-workflow
name: "My Custom Workflow"
description: "Description shown in UI"
phases:
  - id: phase-1
    pattern: solo
    agents: [analyst]
  - id: phase-2
    pattern: parallel
    agents: [dev-1, dev-2]
config:
  timeout_minutes: 60
```

Restart the platform to load new workflows. They appear in the workflow selector automatically.

## Workflow Chaining

```yaml
config:
  on_complete:
    workflow_id: review-cycle    # auto-triggered when this workflow completes
    condition: completed         # only if status = completed (not failed)
```
""",
    },
    {
        "slug": "metrics-guide",
        "title": "Metrics Guide",
        "category": "Guide",
        "icon": "",
        "sort_order": 60,
        "content": """\
# Metrics Guide

## DORA Metrics

DORA (DevOps Research and Assessment) measures software delivery performance using 4 key metrics.

### Deployment Frequency

How often code is deployed to production.

| Level | Frequency |
|-------|-----------|
| Elite | Multiple times per day |
| High | Once per day to once per week |
| Medium | Once per week to once per month |
| Low | Less than once per month |

In the platform: calculated from mission runs with status=completed that triggered a deployment phase.

### Lead Time for Changes

Time from code committed to running in production.

| Level | Lead Time |
|-------|-----------|
| Elite | Less than 1 hour |
| High | 1 day to 1 week |
| Medium | 1 week to 1 month |
| Low | More than 1 month |

In the platform: measured from session start to mission completion.

### Change Failure Rate

Percentage of deployments causing production failures.

| Level | Rate |
|-------|------|
| Elite | 0-15% |
| High | 16-30% |
| Medium | 16-30% |
| Low | 46-60% |

In the platform: ratio of failed mission runs to total runs.

### Mean Time to Recovery (MTTR)

Time to recover from a production failure.

| Level | MTTR |
|-------|------|
| Elite | Less than 1 hour |
| High | Less than 1 day |
| Medium | 1 day to 1 week |
| Low | More than 1 week |

In the platform: time from incident creation to resolution.

---

## Quality Metrics

### Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Security | 25% | Vulnerability count, SAST results |
| Test Coverage | 20% | Line/branch coverage |
| Accessibility | 20% | WCAG compliance score |
| Code Quality | 20% | Complexity, duplication, code smells |
| Documentation | 15% | Doc coverage, readability |

### Score Levels

- 90-100: Excellent
- 75-89: Good
- 60-74: Acceptable
- 40-59: Needs work
- 0-39: Critical

---

## Agent Performance Scoring

### 4-Dimension Model

**Production (35%)**
```
accept_ratio = accepted / (accepted + rejected)
iter_efficiency = accepted / iterations
score = accept_ratio * 60 + iter_efficiency * 40
```

**Collaboration (25%)**
```
score = min(100, agent_messages / total_messages * 5 * 100)
```

**Coherence (25%)**
```
veto_rate = veto_messages / total_messages
if veto_rate == 0: score = 70   # rubber-stamp penalty
elif veto_rate < 0.1: score = 70 + veto_rate * 200
elif veto_rate <= 0.3: score = 90 - (veto_rate - 0.1) * 100
else: score = max(0, 70 - (veto_rate - 0.3) * 100)
```

**Efficiency (15%)**
```
speed = max(0, 100 - avg_ms / 100)
score = speed * success_pct / 100 * output_factor
```

### Composite Score
```
composite = production * 0.35 + collaboration * 0.25 + coherence * 0.25 + efficiency * 0.15
```

### API
```
GET /api/analytics/team-score          -> agents ranked by composite score
GET /api/analytics/agent-pattern-score -> (agent, pattern) combos ranked by accept_rate
```

---

## Pipeline Metrics

### Velocity
Story points completed per sprint. Tracked in the sprints table.

### Cycle Time
Time from task creation to completion. Shown as histogram distribution.

### Burndown
Remaining story points over time within an epic.

---

## Analytics Dashboard

Access via Metrics -> Analytics tab.

Key panels:
- Total missions (all-time)
- Success rate (%)
- Active agents count
- Top skills used
- Mission status breakdown (chart)
- Agent leaderboard
- LLM usage and cost by provider
- System health (CPU, memory, latency)
""",
    },
    {
        "slug": "agent-scoring",
        "title": "Agent Scoring",
        "category": "Reference",
        "icon": "",
        "sort_order": 100,
        "content": """\
# Agent Scoring

The platform tracks agent performance across every mission and computes a composite score.

## Data Sources

| Table | Signal |
|-------|--------|
| `agent_scores` | accepted, rejected, iterations per epic |
| `agent_pattern_scores` | accepted, rejected per (agent, pattern) combo |
| `messages` | message types: veto, approve, delegate, text |
| `llm_traces` | duration_ms, tokens_out, status |
| `quality_reports` | dimension scores per report |

## Score Tables

### agent_scores
```sql
SELECT agent_id, accepted, rejected, iterations
FROM agent_scores
ORDER BY accepted DESC;
```

### agent_pattern_scores
```sql
SELECT agent_id, pattern_id,
       ROUND(100.0 * accepted / (accepted + rejected), 1) as accept_rate
FROM agent_pattern_scores
WHERE accepted + rejected >= 3
ORDER BY accept_rate DESC;
```

## Production Score Interpretation

| Score | Meaning |
|-------|---------|
| 90-100 | Consistently produces accepted outputs on first try |
| 70-89 | Good quality, occasional revisions needed |
| 50-69 | Frequently needs revision |
| 30-49 | More rejected than accepted |
| 0-29 | Consistently failing |

## Coherence Score Interpretation

The coherence score penalizes both extremes:

- A veto rate of 0% means the agent never challenges — it approves everything (rubber-stamp).
  These agents provide no value in adversarial patterns.
- A veto rate of 10-30% is optimal — the agent maintains quality standards without being disruptive.
- A veto rate above 30% means the agent is blocking too much — possible prompt misconfiguration.

## Using Scores for Team Selection

When building a team for a project, prefer agents with:
1. High production score (>70) for the primary workflow
2. Moderate coherence score (>65) — avoid rubber-stamps for review roles
3. High collaboration score for patterns requiring coordination (hierarchical, network)

## Pattern-Agent Fit

Some agents perform better in specific patterns. Check the agent-pattern-score endpoint
to find the best agents for each pattern in your specific context.

```bash
GET /api/analytics/agent-pattern-score?limit=30
```

Example interpretation:
- `architecte` performs best in `aggregator` pattern (accept_rate = 95%)
- `dev_frontend` performs best in `sequential` but struggles in `adversarial`
- `responsable_tma` has perfect production score but very low collaboration score
  — use as executor in sequential patterns, not in team discussions
""",
    },
    {
        "slug": "team-templates",
        "title": "Team Templates",
        "category": "Reference",
        "icon": "",
        "sort_order": 110,
        "content": """\
# Team Templates

Team templates define pre-configured agent pools for specific project types.
Templates are stored as YAML in `teams/` directory and accessible via `/api/teams`.

## Available Templates

### saas-fullstack
Full-stack SaaS product team.

Agents: product-owner, architect, lead-dev, dev-frontend, dev-backend, qa-engineer, devops, security-expert, tech-writer
Patterns: hierarchical (sprints), parallel (implementation), adversarial (review), sequential (deploy)
Use for: web applications, APIs, microservices

### safe-art
SAFe Agile Release Train configuration.

Agents: release-train-engineer, product-manager, system-architect, agile-coach, team-lead-1, team-lead-2, dev-1, dev-2, dev-3, dev-4, qa-1, qa-2
Patterns: hierarchical (PI planning), wave (team sprints), aggregator (PI review)
Use for: large-scale agile programs, PI planning, enterprise software

### security-audit
Security-focused review team.

Agents: security-lead, sast-analyst, dependency-checker, pen-tester, compliance-reviewer, report-writer
Patterns: parallel (scan phases), aggregator (findings consolidation), sequential (remediation)
Use for: security audits, compliance reviews, vulnerability assessments

### tma-maintenance
Technical Maintenance and Administration team.

Agents: tma-lead, debt-analyst, refactoring-expert, test-coverage-agent, documentation-agent
Patterns: router (triage by debt type), loop (iterative fixes), sequential (verify)
Use for: technical debt reduction, legacy modernization, ongoing maintenance

## Using Team Templates

### Via UI
Projects -> New Project -> Select Template -> adjust agent list if needed

### Via API
```bash
# List templates
GET /api/teams

# Export template as YAML
GET /api/teams/export?name=saas-fullstack

# Import a custom template
POST /api/teams/import
Content-Type: application/json
{
  "name": "my-team",
  "description": "Custom team",
  "agents": ["analyst", "developer", "reviewer"],
  "patterns": ["sequential", "adversarial"]
}
```

## Creating Custom Templates

```yaml
# teams/my-team.yaml
name: my-team
description: "Specialized data engineering team"
agents:
  - data-engineer
  - data-scientist
  - ml-ops
  - data-qa
patterns:
  - sequential
  - parallel
  - loop
workflows:
  - tdd-workflow
  - quality-gate
config:
  default_pattern: sequential
  max_concurrent_agents: 4
```
""",
    },
    {
        "slug": "safe-lifecycle",
        "title": "SAFe Lifecycle",
        "category": "Reference",
        "icon": "",
        "sort_order": 120,
        "content": """\
# SAFe Lifecycle

The platform implements a SAFe (Scaled Agile Framework) lifecycle for managing
software delivery at scale.

## Hierarchy

```
Portfolio
└── Program Increment (PI)
    └── ART (Agile Release Train)
        └── Sprint
            └── Epic
                └── Feature
                    └── User Story
                        └── Task
```

## Program Increment (PI)

A time-boxed planning horizon (typically 8-12 weeks).
Contains multiple sprints and ART ceremonies.

PI states: planning, executing, reviewing, completed

### PI Planning
All agents participate in a 2-phase planning event:
1. Business context (Product Owner presents vision)
2. Team breakout (each sub-team plans their sprint objectives)

## ART (Agile Release Train)

A long-lived team of agent teams that plan, commit, and execute together.
Each ART has: Release Train Engineer (RTE), Product Manager, System Architect.

## Sprints

Two-week iteration cycles. Each sprint has:
- Sprint Planning (hierarchical pattern)
- Daily Standup (solo per agent, aggregated)
- Sprint Review (adversarial pattern)
- Retrospective (negotiation pattern)

Sprint metrics: velocity (story points), planned vs. actual.

## Epics

Large-body work requiring multiple sprints.

Epic funnel: Ideation -> Analyzing -> Backlog -> Implementing -> Done

### WSJF Prioritization

Weighted Shortest Job First determines backlog order:

```
WSJF = Cost of Delay / Job Duration

Cost of Delay = User Business Value (1-10)
              + Time Criticality (1-10)
              + Risk Reduction / Opportunity Enablement (1-10)

Job Duration = estimated story points / team velocity
```

Higher WSJF = higher priority.

## Features

Deliverable functionality within an epic (1-3 sprints).
Each feature has: acceptance criteria, story points, owner agent.

## User Stories

Atomic units of work: "As a [user], I want [capability] so that [benefit]."
Estimated in story points (Fibonacci: 1, 2, 3, 5, 8, 13).

## Ceremonies

All accessible from the Ceremonies tab:

| Ceremony | Frequency | Pattern | Duration |
|----------|-----------|---------|---------|
| Sprint Planning | Per sprint | Hierarchical | 2h |
| Daily Standup | Daily | Parallel | 15min |
| Sprint Review | Per sprint | Adversarial | 1h |
| Sprint Retro | Per sprint | Negotiation | 1h |
| PI Planning | Per PI | Hierarchical + Wave | 2 days |
| PI Review | Per PI | Aggregator | 4h |
| System Demo | Per sprint | Sequential | 1h |
""",
    },
    {
        "slug": "session-architecture",
        "title": "Session Architecture",
        "category": "Architecture",
        "icon": "",
        "sort_order": 20,
        "content": """\
# Session Architecture

A session is the runtime context for a single agent collaboration unit.

## Session Lifecycle

```
Mission created
    -> Orchestrator selects workflow
    -> Workflow creates N sessions (one per phase)
    -> Each session:
        -> PatternRun initialized
        -> Agents assigned
        -> Pattern engine executes
        -> SSE events streamed to UI
        -> Session completed/failed
    -> Workflow phase transitions
-> Mission completed
```

## Session Components

### PatternRun
```python
@dataclass
class PatternRun:
    pattern: PatternDef      # which pattern is executing
    session_id: str          # unique session ID
    project_id: str          # owning project
    project_path: str        # workspace filesystem path
    phase_id: str            # mission phase ID (for SSE routing)
    nodes: dict[str, NodeState]  # per-agent state
    iteration: int           # current loop iteration
    max_iterations: int      # loop limit
    finished: bool
    success: bool
```

### SSE Streaming

Each session streams events in real-time using Server-Sent Events (SSE).

Event format:
```
event: agent_message
data: {"agent_id": "...", "role": "assistant", "content": "...", "session_id": "..."}

event: phase_complete
data: {"phase_id": "...", "status": "completed", "duration_ms": 12345}

event: session_error
data: {"error": "...", "recoverable": false}
```

### Session Store

In-memory message store (bounded, last 100 messages):
```python
store = get_session_store()
history = store.get_messages(session_id, limit=30)
store.add_message(session_id, MessageDef(role="assistant", content="..."))
```

### Execution Context

Each agent receives an `ExecutionContext`:
- system_prompt (compiled from template + project context)
- history (last N messages)
- tools (allowed MCP tools)
- project_path (workspace filesystem)
- phase_context (current phase metadata)

## Concurrency

- Multiple sessions can run in parallel (asyncio tasks)
- SSE queue per session (bounded at 500 events)
- Semaphore limits concurrent LLM calls (default: 10)

## Session Recovery

If a session fails mid-execution:
1. Auto-heal attempts restart (up to 2 retries)
2. If all retries fail, platform incident is created
3. Mission can be manually resumed from UI (Missions -> Resume)

## Memory Persistence

After each session, agent outputs are stored in:
- `messages` table (full history)
- `memory_entries` table (FTS5 indexed, project-scoped)
- `llm_traces` table (per-call performance data)
""",
    },
    {
        "slug": "quality-system",
        "title": "Quality System",
        "category": "Architecture",
        "icon": "",
        "sort_order": 40,
        "content": """\
# Quality System

The platform continuously measures and tracks quality across multiple dimensions.

## Quality Scanner

The `QualityScanner` runs after each mission completion and computes scores
for each quality dimension.

### Dimensions

| Dimension | Max Score | Measurement |
|-----------|-----------|-------------|
| Security | 100 | SAST findings, dependency vulnerabilities, secrets exposure |
| Test Coverage | 100 | Line coverage %, branch coverage % |
| Accessibility | 100 | WCAG 2.1 AA compliance (automated + agent review) |
| Code Quality | 100 | Cyclomatic complexity, duplication, code smells |
| Documentation | 100 | JSDoc/docstring coverage, README completeness |
| Performance | 100 | Lighthouse score, Core Web Vitals |

### Overall Score Calculation

```python
weights = {
    "security": 0.25,
    "test_coverage": 0.20,
    "accessibility": 0.20,
    "code_quality": 0.20,
    "documentation": 0.15,
}
overall = sum(score[dim] * weight for dim, weight in weights.items())
```

## Quality Snapshots

A snapshot is taken at the end of each sprint and after each major workflow completion.

```sql
SELECT project_id, created_at, overall_score, breakdown_json
FROM quality_snapshots
WHERE project_id = ?
ORDER BY created_at DESC
LIMIT 10;
```

## Quality Reports

Individual dimension reports are stored per mission run:

```sql
SELECT dimension, score, notes, agent_id
FROM quality_reports
WHERE mission_run_id = ?;
```

## Quality Gate Workflow

The `quality-gate` workflow enforces quality thresholds before deployment:

1. Run all quality checks in parallel
2. Aggregate scores
3. If any dimension falls below threshold, block deployment
4. Report findings to product owner

Default thresholds:
- Security: >= 70 (CRITICAL — below this blocks all deployments)
- Test Coverage: >= 60
- Code Quality: >= 65
- Accessibility: >= 70

## Viewing Quality Metrics

Metrics -> Quality tab:
- Project selector
- Latest snapshot radar chart
- Trend over time (line chart)
- Dimension breakdown with notes

API:
```
GET /api/metrics/quality/{project_id}    -> latest snapshot
GET /api/metrics/quality/{project_id}/trend  -> history
```
""",
    },
    {
        "slug": "tools-reference",
        "title": "Tools Reference",
        "category": "Reference",
        "icon": "",
        "sort_order": 130,
        "content": """\
# Tools Reference

Agents have access to tools via the MCP (Model Context Protocol) bridge.

## Code Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Create or overwrite a file |
| `edit_file` | Make targeted edits (old_str -> new_str) |
| `search_code` | ripgrep-based code search |
| `list_files` | Directory listing with patterns |
| `run_command` | Execute shell commands (sandboxed) |

## Git Tools

| Tool | Description |
|------|-------------|
| `git_status` | Working tree status |
| `git_diff` | Show changes |
| `git_commit` | Stage and commit changes |
| `git_push` | Push to remote |
| `git_branch` | List/create/switch branches |
| `git_log` | Commit history |
| `create_pr` | Create GitHub/GitLab pull request |

## Memory Tools

| Tool | Description |
|------|-------------|
| `memory_store` | Save key-value to persistent memory |
| `memory_retrieve` | Get a memory entry by key |
| `memory_search` | FTS5 full-text search across memory |
| `memory_list` | List recent memory entries |

## Security Tools

| Tool | Description |
|------|-------------|
| `sast_scan` | Static analysis (Bandit, ESLint security) |
| `dependency_check` | Check for vulnerable dependencies |
| `secrets_scan` | Detect hardcoded credentials |
| `generate_sbom` | Software Bill of Materials |

## Deploy Tools

| Tool | Description |
|------|-------------|
| `docker_build` | Build Docker image |
| `docker_run` | Run a container |
| `docker_compose` | docker compose up/down/restart |
| `kubectl_apply` | Apply Kubernetes manifests |
| `health_check` | HTTP health probe |

## Browser Tools (Playwright)

| Tool | Description |
|------|-------------|
| `browser_navigate` | Go to URL |
| `browser_screenshot` | Capture page screenshot |
| `browser_click` | Click element by selector |
| `browser_fill` | Fill form field |
| `browser_evaluate` | Execute JavaScript |
| `browser_extract` | Extract text/HTML from page |

## Solaris Design System Tools

| Tool | Description |
|------|-------------|
| `solaris_component` | Get Figma component details and variants |
| `solaris_variant` | Get exact variant with CSS values |
| `solaris_wcag` | WCAG accessibility pattern for component |
| `solaris_validation` | Get validation status from latest report |
| `solaris_knowledge` | Query design system knowledge base |

## MCP Fetch Tools

| Tool | Description |
|------|-------------|
| `fetch_url` | HTTP GET with markdown conversion |
| `fetch_post` | HTTP POST |

## Tool Allowlist

Each agent YAML can restrict which tools are available:

```yaml
id: my-secure-agent
tools:
  - read_file     # can only read, not write
  - search_code
  - memory_search
  - sast_scan
# write_file, git_commit, etc. NOT listed = not allowed
```
""",
    },
    {
        "slug": "llm-guide",
        "title": "LLM Configuration Guide",
        "category": "Reference",
        "icon": "",
        "sort_order": 140,
        "content": """\
# LLM Configuration Guide

## Provider Selection

The platform supports multiple LLM providers with automatic fallback.

### Environment Variables

```bash
# Primary provider
PLATFORM_LLM_PROVIDER=minimax          # minimax | azure-openai | azure-ai | demo
PLATFORM_LLM_MODEL=MiniMax-M2.5        # model name

# Provider-specific (set via key files, not env vars)
# ~/.config/factory/minimax.key
# ~/.config/factory/azure-openai.key
# ~/.config/factory/azure-ai.key
```

### Key Files

```bash
# MiniMax
echo "your-minimax-api-key" > ~/.config/factory/minimax.key

# Azure OpenAI
cat > ~/.config/factory/azure-openai.key << EOF
api_key=your-key
endpoint=https://your-resource.openai.azure.com/
deployment=gpt-5-mini
api_version=2024-02-01
EOF
```

## Fallback Chain

```
Primary provider (configured) 
    -> on 429 (rate limit): wait 90s, retry
    -> on persistent failure: try next provider
    -> Azure OpenAI
    -> Azure AI
    -> raise exception (no more providers)
```

## Model Recommendations

| Use Case | Recommended Model | Reason |
|----------|------------------|--------|
| Primary workload | MiniMax-M2.5 | Fast, cost-effective, strong coding |
| Complex architecture | GPT-5-mini | Strong reasoning |
| Security audit | GPT-5-mini | Better security knowledge |
| Demo / testing | demo (mock) | No cost, instant response |

## Cost Tracking

LLM costs are tracked per session and project:

```sql
SELECT provider, model, SUM(tokens_in + tokens_out) as total_tokens,
       SUM(estimated_cost_usd) as total_cost
FROM llm_traces
GROUP BY provider, model
ORDER BY total_cost DESC;
```

View in: Metrics -> Analytics -> System Health -> LLM Usage

## Performance Tuning

### Temperature
- Default: 0.7 (creative tasks)
- Override per agent: `temperature: 0.2` (deterministic code generation)

### Max Tokens
- Default: 4096 per call
- Override per workflow phase: `max_tokens: 8192`

### Timeout
- Default: 120s per LLM call
- Long workflows can be affected by LLM timeouts — the platform auto-retries failed phases

## Demo Mode

For local development and CI without API keys:

```bash
PLATFORM_LLM_PROVIDER=demo python -m uvicorn platform.server:app --port 8090 --ws none
```

Demo mode returns simulated responses. Useful for:
- UI development
- Integration testing
- Demos without billing
""",
    },
    {
        "slug": "troubleshooting",
        "title": "Troubleshooting",
        "category": "Guide",
        "icon": "",
        "sort_order": 70,
        "content": """\
# Troubleshooting

## Platform won't start

**Symptom**: uvicorn fails to start.

Check:
```bash
# Port conflict
lsof -i :8090

# Missing dependencies
pip install -r requirements.txt

# DB corruption
python -c "from platform.db.migrations import init_db; init_db()"
```

## Missions stuck in "active" state

**Cause**: LLM timeout or agent loop stuck.

Fix:
```bash
# Via CLI
sf missions list --status active
sf missions cancel <id>

# Via UI: Missions -> find mission -> Cancel

# If auto-heal is running, wait up to 2 retries (2-5 min)
```

## "Chart is not defined" in Metrics

**Cause**: CDN blocked or chart.js not loaded.

Fix: The platform now serves chart.js locally (`/static/js/chart.umd.min.js`).
If still occurring, hard refresh the page (Ctrl+Shift+R).

## LLM rate limits (429 errors)

**Symptom**: missions fail with "rate limit" in logs.

Fix:
```bash
# Check current provider
sf status | grep provider

# Switch to fallback manually
export PLATFORM_LLM_PROVIDER=azure-openai
# Restart platform
```

The platform auto-retries after 90s cooldown.

## Docker container not updating

**Symptom**: code changes not reflected after `docker compose restart`.

Fix: Use rsync for file changes:
```bash
rsync -az platform/ server:/opt/app/platform/
ssh server "cd /opt/app && docker compose restart platform"
```
Only rebuild the image when `requirements.txt` changes.

## Database migration errors

**Symptom**: `no such column` or `no such table` errors.

Fix:
```bash
# The platform runs migrations on startup automatically.
# Force re-init (safe — uses CREATE IF NOT EXISTS):
python -c "
from platform.db.migrations import init_db
from pathlib import Path
init_db(Path('data/platform.db'))
print('done')
"
```

## Memory leaks / high CPU

**Symptom**: platform slows over time.

Fix:
1. Check for stuck async tasks: `GET /api/monitoring/live`
2. Look for sessions with no end time in DB
3. Restart platform (sessions are designed to be resumable)

## SSE disconnections

**Symptom**: session stream cuts off.

Cause: nginx or load balancer timeout on long-running requests.

Fix in nginx config:
```nginx
location /api/missions/ {
    proxy_read_timeout 3600;
    proxy_buffering off;
    proxy_cache off;
}
```

## Wiki not showing on first load

**Symptom**: wiki shows "Select a page" instead of content.

Fix: The wiki auto-seeds and auto-navigates to getting-started on load.
If pages are missing, use `POST /api/wiki/seed` to repopulate.

## Agent scoring shows 0

**Symptom**: `GET /api/analytics/team-score` returns all zeros.

Cause: `agent_pattern_scores` table was created recently — scores accumulate from new runs only.
Historical `agent_scores` data (prior to the feature) can be queried directly:

```sql
SELECT agent_id, accepted, rejected,
       ROUND(100.0 * accepted / (accepted + rejected), 1) as accept_rate
FROM agent_scores
WHERE accepted + rejected > 0
ORDER BY accept_rate DESC;
```
""",
    },
    {
        "slug": "glossary",
        "title": "Glossary",
        "category": "Reference",
        "icon": "",
        "sort_order": 200,
        "content": """\
# Glossary

## A

**A2A (Agent-to-Agent)**
The inter-agent communication protocol. Agents exchange structured messages via
the A2A Bus: request, response, broadcast, veto, delegate, negotiate.

**ART (Agile Release Train)**
A team of agent teams that plans and executes together within a Program Increment.
Includes Release Train Engineer, Product Manager, System Architect.

**Adversarial Pattern**
A two-agent pattern where a producer creates output and a challenger reviews it.
The cycle repeats until the output passes review or max retries is reached.

## B

**Burndown**
Chart showing remaining story points over time within a sprint or epic.
Ideally a straight line from planned SP to zero at sprint end.

## C

**Ceremony**
SAFe events: Sprint Planning, Daily Standup, Sprint Review, Retrospective,
PI Planning, PI Review, System Demo.

**Composite Score**
Agent performance metric combining production (35%), collaboration (25%),
coherence (25%), and efficiency (15%).

**Cycle Time**
Time from when work starts on a task to when it is completed.
Measured in the platform from feature creation to feature completion.

## D

**DORA**
DevOps Research and Assessment. Four metrics: Deployment Frequency,
Lead Time for Changes, Change Failure Rate, MTTR.

## E

**Epic**
Large-body work item decomposed into features. Goes through a funnel:
Ideation -> Analyzing -> Backlog -> Implementing -> Done.

**ExecutionContext**
Runtime data passed to each agent: system prompt, message history, tools, 
project path, and phase metadata.

## F

**Feature**
Deliverable functionality within an epic, completable in 1-3 sprints.
Has acceptance criteria, story points, and assigned agent.

**FTS5**
SQLite's Full-Text Search extension. Used for the memory system to enable
semantic search over agent-generated content.

## H

**HTMX**
JavaScript library used for the platform UI. Enables partial page updates
via HTTP without a full JavaScript framework.

## L

**Lead Time**
Time from code committed to code running in production. One of the 4 DORA metrics.

**Loop Pattern**
A pattern where agents iterate (develop -> test -> fix) until quality criteria
are met or max_iterations is reached.

## M

**MCP (Model Context Protocol)**
Protocol for tool communication between agents and external services.
The platform acts as an MCP client, connecting to MCP servers (fetch, memory,
playwright, solaris, lrm).

**Mission**
A user request processed by the platform from start to completion.
Has runs (attempts) which have phases (agent steps).

**MTTR (Mean Time to Recovery)**
Time to recover from a production failure. One of the 4 DORA metrics.

## P

**PatternRun**
The runtime state of a pattern execution, including which agents are assigned,
current iteration, success/failure state, and message history.

**PI (Program Increment)**
A time-boxed planning and execution period (8-12 weeks) containing multiple sprints.

## R

**Rubber-stamp**
An agent that approves everything without critique. Detected by 0% veto rate.
Penalized in the coherence score. Should not be used in adversarial patterns.

## S

**SAFe (Scaled Agile Framework)**
Enterprise agile framework. The platform implements PI planning, ART, sprints,
epics, features, and stories following SAFe principles.

**Session**
A runtime conversation between one or more agents.
Streams events via SSE. Belongs to a phase of a mission run.

**SSE (Server-Sent Events)**
One-directional streaming protocol (server to browser). Used to show agent
messages in real-time as they are generated.

## T

**WSJF (Weighted Shortest Job First)**
SAFe prioritization formula: Cost of Delay / Job Duration.
Used to order the product backlog.

## V

**Velocity**
Story points completed per sprint. Key measure of team throughput.

**Veto**
An agent action in the A2A protocol. Soft veto: request revision.
Hard veto: reject entirely and escalate to human or stop the workflow.
""",
    },
    # ── SAFe User Guides ─────────────────────────────────────────
    {
        "slug": "guide-product-owner",
        "title": "Guide: Product Owner",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 310,
        "content": """\
# Guide: Product Owner

As Product Owner, you define what gets built. The platform helps you articulate
requirements with precision, decompose epics into actionable stories, and ensure
acceptance criteria are testable.

## Key Workflows

### Epic Breakdown

```
Mission input: "Epic: Replace legacy auth with OAuth2/OIDC across all services"
Workflow: epic-breakdown
```

Output: hypothesis statement, WSJF scoring, 10-15 features, user stories with
acceptance criteria, risks and dependencies.

### User Story Refinement

```
Mission input: "As a user, I want to reset my password via email"
Workflow: user-story-refinement
```

Output: INVEST criteria, Given/When/Then acceptance criteria, story point estimate,
test scenarios, technical notes.

### Sprint Planning

```
Mission input: "Sprint 8: Team capacity 42pts. Stories: US-201, US-202, US-203"
Workflow: sprint-planning
```

Output: sprint goal, committed backlog, risk flags, dependency map.

### PI Planning

```
Mission input: "PI 2025-Q3: Team Payments. 5 sprints x 40pts = 200pts. Focus: PCI compliance"
Workflow: pi-planning
```

Output: team PI objectives, uncommitted objectives, cross-team dependencies, risks.

## Tips

- Provide context: domain, technical constraints, compliance requirements.
- Include Cost of Delay estimates for accurate WSJF scoring.
- Use project context so the AI knows your codebase and domain.
- Iterate: use `sf missions chat <id>` to refine outputs.
""",
    },
    {
        "slug": "guide-scrum-master",
        "title": "Guide: Scrum Master",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 320,
        "content": """\
# Guide: Scrum Master

As Scrum Master, you are the guardian of the process. The platform helps you
generate ceremony artifacts, analyze performance, and prepare actionable retrospectives.

## Key Workflows

### Sprint Planning Facilitation

```
Mission input: "Sprint 12. Team: 6 devs + 1 QA. Velocity: 42pts. Backlog: [stories]"
Workflow: sprint-planning
```

Output: sprint goal, capacity breakdown, committed backlog, dependency map, DoD reminder.

### Retrospective

```
Mission input: "Sprint 12 retro. Went well: [input]. Improve: [input]. Team size: 8"
Workflow: retrospective
```

Output: categorized observations, root cause analysis, 3-5 SMART action items.

### Scrum of Scrums

```
Mission input: "Teams: A (auth), B (payment), C (infra). Dependencies: [list]. Risks: [list]"
Workflow: scrum-of-scrums
```

## Team Performance Metrics

```bash
sf analytics dora              # DORA metrics
sf analytics team-score        # Agent quality scores
```

View sprint velocity trend in the Pipeline tab at /metrics.

## SAFe Ceremonies

- **System Demo**: use `demo-preparation` workflow to generate a demo script.
- **Inspect and Adapt**: use `retrospective` workflow with PI-level data.
- **PI Planning**: coordinate with RTE using `pi-planning` workflow.

## Tips

- Use actual DORA data in retrospectives, not subjective feelings.
- Low coherence scores on reviewer agents may indicate rubber-stamping — a process smell.
- Reference previous retro outputs to track whether action items were implemented.
""",
    },
    {
        "slug": "guide-developer",
        "title": "Guide: Developer",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 330,
        "content": """\
# Guide: Developer

As Developer, you use the platform to bootstrap features, get adversarial code review,
run TDD loops, and get unstuck on complex problems.

## Key Workflows

### TDD Feature Development

```
Mission input: "Implement rate limiter middleware for FastAPI. Sliding window. Max 100 req/min/IP. Redis-backed."
Workflow: tdd-feature (loop pattern)
```

The loop pattern writes failing tests first, then iterates until all tests pass.

### Full Stack Feature

```
Mission input: "Add real-time notification system: backend SSE + React toast component"
Workflow: full-stack-feature
```

### Adversarial Code Review

```
Mission input: "Review: [paste code]. Focus: security, edge cases, performance"
Workflow: adversarial-review
```

A challenger agent vetoes if critical issues are found. Up to 3 revision cycles.

### API Feature

```
Mission input: "Add GET /users/{id}/activity — last 30 days, filterable, paginated"
Workflow: api-feature
```

Output: OpenAPI spec, implementation, unit + integration tests, migration.

## Best Agent-Pattern Combos

| Task | Recommended |
|------|-------------|
| Python implementation | dev-python + tdd-feature (loop) |
| Security review | security-expert + adversarial |
| API design | api-architect + dev-backend + negotiation |
| Refactoring | dev-python + senior-reviewer + adversarial |

Check current performance: `sf analytics agent-patterns`

## Git Integration

Set up project context for codebase-aware missions:
```bash
sf projects create --name "My Service" --path ./src
sf projects chat <id> "Refactor UserRepository to use async/await"
```

## Tips

- Provide existing code, DB schema, framework constraints in your input.
- Use TDD for complex logic — the loop pattern self-corrects based on test failures.
- Review all AI-generated code before committing — you own the code you merge.
""",
    },
    {
        "slug": "guide-architect",
        "title": "Guide: System Architect",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 340,
        "content": """\
# Guide: System Architect

As System Architect, you set the technical direction. The platform helps you
explore architectural options, generate ADRs, design APIs, and validate implementations.

## Key Workflows

### Architecture Design (Aggregator)

Multiple architect agents propose independent solutions, then a synthesis agent
produces the best combined recommendation.

```
Mission input: "Design multi-tenant SaaS backend. 10k orgs, 500 users each.
Data isolation: strict per-tenant. Latency: <200ms p95. Stack: Python, PostgreSQL, Azure AKS."
Workflow: architecture-design
```

Output: architecture diagram (Mermaid), component breakdown, technology rationale,
trade-offs, risks.

### ADR Creation

```
Mission input: "Decision: use event sourcing for order domain.
Context: high read volume 100:1, audit trail needed, CQRS partially implemented.
Options: event sourcing, CRUD + audit log, hybrid"
Workflow: adr-creation
```

Output: MADR format with status, context, decision, consequences, alternatives.

### API Design Negotiation

```
Mission input: "Design REST API for notification service.
Consumers: web (React), mobile (iOS/Android), webhooks.
Requirements: SSE real-time, bulk ops, filtering, idempotent delivery"
Workflow: api-design
```

The negotiation pattern has backend, frontend, and consumer agents debate
the contract until consensus.

### Migration Planning

```
Mission input: "Migrate Django monolith (200k LOC) to microservices.
8 bounded contexts. Team: 12 devs, 3 teams. Timeline: 18 months."
Workflow: migration-plan
```

Output: Strangler Fig plan, domain boundary analysis, migration sequence, risk matrix.

## Tips

- Provide numeric constraints (latency targets, scale, cost limits) — not qualitative ones.
- ADR every significant decision — the platform generates them in <5 minutes.
- Check `sf analytics agent-patterns` for which architecture agents produce the best results.
""",
    },
    {
        "slug": "guide-security",
        "title": "Guide: Security Engineer",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 350,
        "content": """\
# Guide: Security Engineer

As Security Engineer, you protect the system from vulnerabilities and compliance failures.
The platform accelerates security audits, threat modeling, and compliance review.

## Key Workflows

### Security Audit (Parallel)

Runs OWASP analysis, CVE scan, and secret detection simultaneously.

```
Mission input: "Audit auth module. Stack: Python/FastAPI, JWT, PostgreSQL. Deps: [requirements.txt]"
Workflow: security-audit
```

Output per dimension: OWASP Top 10 findings with severity, CVE list with CVSS scores,
secret pattern matches, combined risk summary.

### Threat Modeling (STRIDE)

```
Mission input: "OAuth2 service. Entry: /login /token /refresh /logout.
Data: hashed password, JWT, refresh token. Trust boundaries: mobile, browser, OAuth providers."
Workflow: threat-model
```

Output: data flow diagram, STRIDE analysis, attack trees, prioritized mitigations.

### Compliance Review

```
# GDPR
Mission input: "GDPR review: personal data processed: [list], purpose: [list], retention: [policy]"
Workflow: gdpr-review

# PCI-DSS
Mission input: "PCI-DSS review: payment module, tokenization service, provider: Stripe"
Workflow: compliance-check
```

### Adversarial Security Review

The producer implements; the security challenger finds vulnerabilities.

```
Mission: producer=dev-backend, challenger=security-expert
Input: "Implement JWT validation with refresh token rotation.
Secure against: token theft, replay attacks, timing attacks."
```

## Rubber-Stamp Detection

A security reviewer who never vetoes is not doing their job.
Check coherence scores: `sf analytics team-score`

Coherence < 50 on security agents = review the system prompt.

## Tips

- Provide full context: the whole function, not just the suspicious line.
- Specify your compliance standard explicitly.
- Run threat modeling before development — catching issues early is 10x cheaper.
""",
    },
    {
        "slug": "guide-devops",
        "title": "Guide: DevOps / Platform Engineer",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 360,
        "content": """\
# Guide: DevOps / Platform Engineer

As DevOps engineer, you build the delivery system. The platform helps you design
CI/CD pipelines, generate Infrastructure as Code, and create runbooks.

## Key Workflows

### Pipeline Design

```
Mission input: "CI/CD for Python microservice. Source: GitHub. Target: AKS.
Stages: lint, test (unit+integration), security scan, build, push ACR, deploy staging,
smoke test, deploy prod (manual gate). 2-3 deploys/day."
Workflow: pipeline-design
```

Output: GitHub Actions YAML (or GitLab CI), stage breakdown, caching strategy, rollback.

### Infrastructure as Code

```
Mission input: "Terraform for Azure: AKS (3-10 node autoscale), ACR, PostgreSQL Flexible,
Redis C1, Key Vault, App Gateway WAF. Region: West Europe. Env: production."
Workflow: infrastructure-as-code
```

### Docker Containerization

```
Mission input: "Containerize FastAPI app. Multi-stage build. Non-root user. Target <150MB."
Workflow: docker-containerize
```

### Kubernetes Deployment

```
Mission input: "K8s manifests: 3 replicas, HPA (2-10, CPU 70%), resources: 500m/512Mi request,
1/1Gi limit. Liveness GET /health. Ingress: notifications.myapp.com. Rolling update."
Workflow: kubernetes-deploy
```

### Incident Runbook

```
Mission input: "Runbook: DB connection pool exhaustion. Service: API gateway.
Symptoms: 503 errors. Current mitigation: manual restart. Infra: AKS, PgBouncer."
Workflow: incident-runbook
```

## Tips

- Version IaC and manifests in git — have the agent commit its own outputs.
- Run security review on generated IaC before deploying.
- Define SLOs before building dashboards — not the other way around.
- Test runbooks in game days before they are needed in incidents.
""",
    },
    {
        "slug": "guide-ux-designer",
        "title": "Guide: UX Designer",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 370,
        "content": """\
# Guide: UX Designer

As UX Designer, you champion user experience. The platform accelerates user research
synthesis, wireframe specification, and accessibility review.

## Key Workflows

### User Research Synthesis

```
Mission input: "Usability test findings. Task: onboarding (sign up to first project).
8 participants. Notes: [raw notes]. Success: 5/8. Avg time: 4:20. SUS: 68."
Agent: ux-designer
```

Output: affinity clusters, top 5 usability issues (Nielsen severity), recommended changes.

### User Flow Specification

```
Mission input: "Design flow for 2FA setup. Methods: TOTP, SMS, email.
Edge cases: lost authenticator, new device, admin-enforced 2FA."
Agent: ux-designer
```

Output: step-by-step flow with decision points, error states, copy recommendations.

### Accessibility Review (WCAG 2.1 AA)

```
Mission input: "A11y review: dashboard left sidebar, collapsible nav.
Implementation: [paste HTML/JSX]. Target: WCAG 2.1 AA."
Agent: accessibility-expert
```

Output: WCAG criteria mapping, specific issues with location, remediation by priority.

### Design Handoff Documentation

```
Mission input: "Handoff for product listing page. Components: search, filters,
product cards, pagination. Responsive breakpoints: [describe]."
Agent: ux-designer
```

Output: component inventory with states, spacing spec (tokens), interaction descriptions,
edge cases (empty, error, loading).

## Tips

- Provide concrete research data (quotes, task success rates) — not assumptions.
- Use accessibility review at specification stage — cheaper than fixing in implementation.
- For copy: generate multiple variants then choose the best.
""",
    },
    {
        "slug": "guide-tech-writer",
        "title": "Guide: Technical Writer",
        "category": "SAFe Guides",
        "icon": "",
        "sort_order": 380,
        "content": """\
# Guide: Technical Writer

As Technical Writer, you make the product understandable. The platform helps you
produce API docs, user guides, and release notes at scale.

## Key Workflows

### API Documentation

```
Mission input: "Document notifications API. Audience: third-party developers.
Source: [paste route handlers or OpenAPI spec].
Include: auth, rate limiting, error codes, examples in Python + curl + JS."
Workflow: api-documentation
```

### README Generation

```
Mission input: "Generate README. Project: [describe]. Entry points: [list].
Stack: [list]. Audience: developers who want to run or contribute."
Workflow: readme-generation
```

### Release Notes

```
Mission input: "Release notes for v2.1.0. Git log: [paste git log --oneline].
Audience: end users (non-technical). Exclude: refactoring, test changes."
Workflow: release-notes
```

### Architecture Documentation

```
Mission input: "Document event-driven order processing system.
Audience: engineers new to the codebase. Components: [list]. Message bus: [describe]."
Workflow: architecture-doc
```

### Gap Analysis

```
Mission input: "Find documentation gaps. Existing docs: [link/paste].
API source: [paste routes]. Identify: undocumented endpoints, stale examples."
Agent: tech-writer
```

### Docstring Generation

```
Mission input: "Add Google-style docstrings to all public functions and classes.
Include: Args, Returns, Raises. Code: [paste module]."
Agent: tech-writer
```

## Writing Quality

Always specify:
- **Audience**: junior dev vs senior integrator vs non-technical user
- **Style guide**: Microsoft, Google, or your own
- **Reading level**: helps calibrate vocabulary and sentence complexity
- **Localization needs**: if content will be translated, avoid idioms and humor

## Tips

- Provide the actual code — docs from real code are far more accurate.
- Use adversarial pattern: have a challenger read docs as a new user.
  If they get confused, the docs need work.
- Automate release notes in CI/CD — generate on every tag.
""",
    },
    {
        "slug": "darwin-teams",
        "title": "Darwin Teams — Evolutionary Selection",
        "category": "Agents",
        "sort_order": 5,
        "content": """# Darwin Teams — Evolutionary Agent Selection

The Darwin system gives the platform the ability to **learn which agent+pattern combinations perform best** per technology and phase type, using **Thompson Sampling** for probabilistic team selection with built-in A/B shadow testing.

## Core Concept

Each team is scored independently per a 4-dimensional key:

```
(agent_id, pattern_id, technology, phase_type)
```

A team that excels at Angular migration is tracked separately from the same team doing Angular new features. Scores never bleed across contexts.

## Thompson Sampling

For each candidate team, sample from `Beta(wins + 1, losses + 1)`. Select the team with the highest sample. The `+1` prior ensures exploration before data exists. Naturally balances exploitation vs exploration without tuning.

After each mission: update wins/losses, recompute fitness score.

## Fitness Formula

```
production_score = (acceptance_rate - iteration_penalty) × 100
fitness = production×0.35 + coherence×0.25 + collaboration×0.25 + efficiency×0.15
```

Capped at 100.0. Multiplied by `weight_multiplier` (1.0 normal, 0.1 soft-retired).

## Cold Start Handling

1. Warmup: first 5 runs use random selection
2. Similarity fallback: `angular_19` → `angular_*` → `generic` prefix matching
3. Generic fallback: all teams have a `generic/generic` baseline score

## Soft Retirement

Teams with `fitness < 20` after 10+ runs receive `weight_multiplier = 0.1`. They remain in the system and can recover. Toggle from the `/teams` dashboard.

## Opt-In Usage

```yaml
# In a pattern step — activates Darwin
- step: implement
  agent_id: "skill:developer"    # Darwin selects best team

# Explicit ID — Darwin bypassed
- step: review
  agent_id: "developer_01"
```

Context (technology, phase_type) is auto-inferred from workflow ID and mission title.

## OKR / KPI System

8 default OKR seeds per domain and phase type:

| Domain | Phase | Default OKR |
|--------|-------|-------------|
| code | migration | 90% acceptance rate, max 5 iterations |
| code | new_feature | 85% acceptance rate |
| code | bugfix | 95% fix rate, max 3 iterations |
| code | refactoring | 80% no-regression rate |
| security | audit | 100% critical CVE coverage |
| architecture | design | 85% coherence score |
| testing | generic | 80% coverage target |
| docs | generic | 90% completeness |

Edit targets inline from the OKR tab at `/teams`.

## A/B Shadow Testing

Automatic parallel runs trigger when:
- Top two team fitness scores differ by less than **10 points**
- Random **10% probability** on any mission

Both teams execute the same mission independently. A neutral evaluator picks the winner. Winner gets +1 win, loser +1 loss.

## Dashboard — /teams

Five tabs accessible at `/teams`:

| Tab | Description |
|-----|-------------|
| Leaderboard | Ranked teams with champion/rising/declining/retired badges, retire/unretire actions |
| OKR / KPIs | Inline target and current value editing, green/amber/red status |
| Evolution | Chart.js fitness history per technology+phase, multi-team comparison |
| Selections | Log of Thompson Sampling decisions with mode and score |
| A/B Tests | Shadow test records with teams, winner, scores |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teams/leaderboard` | GET | Ranked teams with badges |
| `/api/teams/okr` | GET | OKR/KPI objectives |
| `/api/teams/okr/{id}` | PUT | Update OKR target/current |
| `/api/teams/evolution` | GET | Fitness history |
| `/api/teams/selections` | GET | Thompson Sampling log |
| `/api/teams/contexts` | GET | Active (technology, phase_type) combinations |
| `/api/teams/{agent}/{pattern}/retire` | POST | Soft-retire a team |
| `/api/teams/{agent}/{pattern}/unretire` | POST | Restore a retired team |
| `/api/teams/ab-tests` | GET | A/B shadow test records |

## Database Tables

- `team_fitness` — core scores per (agent, pattern, technology, phase_type)
- `team_fitness_history` — daily snapshots for evolution chart
- `team_okr` — OKR/KPI targets per domain
- `team_selections` — Thompson Sampling decision log
- `team_ab_tests` — A/B shadow test records

## Related Pages

- [Agents System](agents) — agent catalog and roles
- [Orchestration Patterns](patterns) — where `skill:` prefix activates Darwin
- [Metrics Guide](metrics-guide) — DORA and quality metrics
""",
    },

    # ── Traceability Space (owner RBAC) ──
    {
        "slug": "traceability-overview",
        "title": "Traceability Model",
        "category": "Traceability",
        "icon": "",
        "sort_order": 10,
        "parent_slug": None,
        "owner": "system",
        "visibility": "owner",
        "content": """# Traceability Model

## UUID Format
All artifacts use `{prefix}-{uuid4.hex[:8]}` format:
| Prefix | Artifact | Example |
|--------|----------|---------|
| `feat-` | Feature | `feat-cockpit` |
| `us-` | User Story | `us-47d6b39b` |
| `ac-` | Acceptance Criterion | `ac-f4fbb5f3` |
| `pers-` | Persona | `pers-a1b2c3d4` |
| `jour-` | User Journey | `jour-5e6f7a8b` |
| `sprint-` | Sprint | `sprint-c9d0e1f2` |

## Chain Model
```
Persona --> Feature (feat-*) --> User Story (us-*) --> AC (ac-*)
                |                      |                    |
                v                      v                    v
            IHM/Screen             Code (# Ref:)      Tests (TU/E2E)
```

## Coverage Summary
| Layer | Count | Status |
|-------|-------|--------|
| Epics | 10 | In PG |
| Features | 44 | In PG (feat-*) |
| User Stories | 172 | In PG (us-*) |
| Acceptance Criteria | 154 | In PG (ac-*) |
| IHM Annotations | 0 | Planned |
| Code # Ref: | 14/384 (3.6%) | In progress |
| TU linked | 0/35 | Planned |
| E2E linked | 0/23 | Planned |

## RBAC
Traceability pages are **owner-protected** (`visibility: owner`).
Only the page owner or admin can edit. All users can read.

## Related Pages
- [Personas](traceability-personas)
- [Features Registry](traceability-features)
- [User Stories](traceability-stories)
- [Acceptance Criteria](traceability-acceptance)
- [IHM / Screens](traceability-ihm)
- [Code References](traceability-code-refs)
- [Test Traceability](traceability-tests)
""",
    },
    {
        "slug": "traceability-personas",
        "title": "Personas",
        "category": "Traceability",
        "icon": "",
        "sort_order": 20,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# Personas

| Persona | Features | Stories |
|---------|----------|---------|
| **Admin Plateforme** | 4 (`feat-org`, `feat-rbac`, `feat-settings`, `feat-workspaces`) | 16 |
| **Architecte** | 2 (`feat-mcps`, `feat-patterns`) | 6 |
| **Business Analyst** | 1 (`feat-metier`) | 3 |
| **CTO** | 1 (`feat-cto`) | 3 |
| **DSI** | 1 (`feat-dsi`) | 3 |
| **Data Scientist** | 2 (`feat-evals`, `feat-metrics`) | 9 |
| **Designer** | 1 (`feat-design-system`) | 3 |
| **Développeur** | 9 (`feat-agent-chat`, `feat-agents-create`, `feat-agents-list`, `feat-marketplace`, `feat-tool-builder`, `feat-toolbox`, `feat-jarvis`, `feat-mission-detail`, `feat-mission-replay`) | 31 |
| **Marketing Manager** | 1 (`feat-mkt-ideation`) | 3 |
| **Nouveau Utilisateur** | 1 (`feat-onboarding`) | 3 |
| **Ops Engineer** | 2 (`feat-monitoring`, `feat-ops`) | 7 |
| **Product Manager** | 4 (`feat-portfolio`, `feat-projects`, `feat-ideation`, `feat-product-line`) | 14 |
| **Product Owner** | 2 (`feat-annotate`, `feat-backlog`) | 10 |
| **Release Train Engineer** | 2 (`feat-pi-board`, `feat-art`) | 7 |
| **Scrum Master** | 2 (`feat-ceremonies`, `feat-live`) | 6 |
| **Tech Lead** | 8 (`feat-skills`, `feat-workflows`, `feat-mercato`, `feat-memory`, `feat-wiki`, `feat-quality`, `feat-cockpit`, `feat-mission-control`) | 30 |

**Total**: 16 personas across 44 features""",
    },
    {
        "slug": "traceability-features",
        "title": "Features Registry",
        "category": "Traceability",
        "icon": "",
        "sort_order": 30,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# Features Registry


## e03ab032 (`e03ab032`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-35792a` | Core Gameplay MVP |  | 2 | 0 | backlog |

## Configuration & Administration (`epic-admin`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-org` | Organisation & Équipes | Admin Plateforme | 4 | 4 | backlog |
| `feat-rbac` | RBAC — Gestion des Rôles | Admin Plateforme | 4 | 4 | backlog |
| `feat-settings` | Paramètres Plateforme | Admin Plateforme | 4 | 4 | backlog |
| `feat-workspaces` | Workspaces | Admin Plateforme | 4 | 4 | backlog |

## Agent Management (`epic-agents`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-agent-chat` | Chat Agent | Développeur | 3 | 3 | backlog |
| `feat-agents-create` | Création d'Agent | Développeur | 4 | 4 | backlog |
| `feat-agents-list` | Catalogue d'Agents | Développeur | 3 | 3 | backlog |
| `feat-marketplace` | Marketplace d'Agents | Développeur | 4 | 4 | backlog |
| `feat-skills` | Skills & Compétences | Tech Lead | 3 | 3 | backlog |

## Annotation & Traceability (`epic-annotation`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-annotate` | Annotation Studio | Product Owner | 5 | 5 | backlog |

## Automation & Workflows (`epic-automation`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-mcps` | MCP Servers | Architecte | 3 | 3 | backlog |
| `feat-patterns` | Patterns d'Orchestration | Architecte | 3 | 3 | backlog |
| `feat-tool-builder` | Tool Builder | Développeur | 4 | 4 | backlog |
| `feat-workflows` | Workflows | Tech Lead | 5 | 5 | backlog |

## SAFe Backlog & Planning (`epic-backlog`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-backlog` | Product Backlog | Product Owner | 5 | 5 | backlog |
| `feat-ceremonies` | Cérémonies SAFe | Scrum Master | 3 | 3 | backlog |
| `feat-pi-board` | PI Board — Program Increment | Release Train Engineer | 4 | 4 | backlog |
| `feat-portfolio` | Portfolio | Product Manager | 3 | 3 | backlog |
| `feat-projects` | Projets | Product Manager | 4 | 4 | backlog |

## Ideation & Innovation (`epic-ideation`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-design-system` | Design System | Designer | 3 | 3 | backlog |
| `feat-ideation` | Idéation Projet | Product Manager | 4 | 4 | backlog |
| `feat-metier` | Domaine Métier | Business Analyst | 3 | 3 | backlog |
| `feat-mkt-ideation` | Idéation Marketing | Marketing Manager | 3 | 3 | backlog |
| `feat-product-line` | Product Line | Product Manager | 3 | 3 | backlog |

## Integrations & Partners (`epic-integrations`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-cto` | Vue CTO | CTO | 3 | 3 | backlog |
| `feat-dsi` | Vue DSI | DSI | 3 | 3 | backlog |
| `feat-mercato` | Mercato Agents | Tech Lead | 3 | 3 | backlog |
| `feat-onboarding` | Onboarding | Nouveau Utilisateur | 3 | 3 | backlog |
| `feat-toolbox` | Toolbox | Développeur | 2 | 2 | backlog |

## Knowledge & Memory (`epic-knowledge`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-evals` | Évaluations LLM | Data Scientist | 4 | 4 | backlog |
| `feat-jarvis` | Jarvis — Assistant IA | Développeur | 3 | 3 | backlog |
| `feat-memory` | Memory Agent | Tech Lead | 4 | 4 | backlog |
| `feat-wiki` | Wiki SF | Tech Lead | 3 | 3 | backlog |

## Observability & Ops (`epic-observability`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-metrics` | Métriques & Analytics | Data Scientist | 5 | 5 | backlog |
| `feat-monitoring` | Monitoring Temps Réel | Ops Engineer | 3 | 3 | backlog |
| `feat-ops` | Opérations Plateforme | Ops Engineer | 4 | 4 | backlog |
| `feat-quality` | Qualité Code | Tech Lead | 3 | 3 | backlog |

## Orchestration & Missions (`epic-orchestration`)

| ID | Name | Persona | Stories | AC | Status |
|-----|------|---------|---------|-----|--------|
| `feat-art` | ART — Agile Release Train | Release Train Engineer | 3 | 3 | backlog |
| `feat-cockpit` | Dashboard / Cockpit | Tech Lead | 4 | 4 | backlog |
| `feat-live` | Sessions Live | Scrum Master | 3 | 3 | backlog |
| `feat-mission-control` | Mission Control | Tech Lead | 5 | 5 | backlog |
| `feat-mission-detail` | Détail Mission | Développeur | 4 | 4 | backlog |
| `feat-mission-replay` | Sessions & Replay | Développeur | 4 | 4 | backlog |

**Total**: 44 features across 11 epics""",
    },
    {
        "slug": "traceability-stories",
        "title": "User Stories",
        "category": "Traceability",
        "icon": "",
        "sort_order": 40,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# User Stories

**Total**: 172 stories with `us-{uuid8}` IDs


### Core Gameplay MVP (`feat-35792a`)

| Story ID | Title |
|----------|-------|
| `us-d049b5` | US-E1: à US-E2 + US-U2 (Conditions fin) |
| `us-f7f257` | US-E1: | **Win condition** | Mario atteint DK (haut) = Victory |

### Organisation & Équipes (`feat-org`)

| Story ID | Title |
|----------|-------|
| `us-0900e9a6` | Gérer les groupes utilisateurs |
| `us-dd995131` | Assigner des agents et utilisateurs à une équipe |
| `us-e592e464` | Créer une nouvelle équipe dans l'organisation |
| `us-f2bfa4a7` | Visualiser l'organigramme de l'organisation |

### RBAC — Gestion des Rôles (`feat-rbac`)

| Story ID | Title |
|----------|-------|
| `us-15f0225e` | Créer un rôle personnalisé avec des permissions spécifiques |
| `us-27c29a39` | Assigner un rôle à un utilisateur |
| `us-44321768` | Consulter le journal d'audit des actions utilisateurs |
| `us-447c47ed` | Gérer les accès par projet |

### Paramètres Plateforme (`feat-settings`)

| Story ID | Title |
|----------|-------|
| `us-0d38f9ae` | Gérer les clés API des intégrations tierces |
| `us-8d3564da` | Configurer les limites de rate limiting |
| `us-9f042499` | Configurer le fournisseur LLM par défaut |
| `us-d2316b10` | Activer ou désactiver les notifications Slack/Email |

### Workspaces (`feat-workspaces`)

| Story ID | Title |
|----------|-------|
| `us-67574311` | Configurer les ressources allouées à un workspace |
| `us-aa162b7e` | Archiver un workspace inactif |
| `us-f492769d` | Inviter des membres dans un workspace |
| `us-ff580d89` | Créer un nouveau workspace pour une équipe |

### Chat Agent (`feat-agent-chat`)

| Story ID | Title |
|----------|-------|
| `us-4147308b` | Envoyer un message et recevoir une réponse en streaming |
| `us-917150b3` | Démarrer une conversation avec un agent depuis son profil |
| `us-ab6a4187` | Consulter l'historique de conversation avec un agent |

### Création d'Agent (`feat-agents-create`)

| Story ID | Title |
|----------|-------|
| `us-28e84baa` | Définir les instructions système d'un agent |
| `us-b23ce69a` | Créer un nouvel agent avec son persona et ses skills |
| `us-d03a1814` | Tester un agent depuis l'interface d'édition |
| `us-d925f84a` | Configurer le modèle LLM d'un agent |

### Catalogue d'Agents (`feat-agents-list`)

| Story ID | Title |
|----------|-------|
| `us-5e1e5369` | Filtrer les agents par rôle, compétence ou statut |
| `us-a6ee2bd8` | Accéder au profil d'un agent depuis le catalogue |
| `us-d7bb4fd7` | Parcourir la liste des agents disponibles |

### Marketplace d'Agents (`feat-marketplace`)

| Story ID | Title |
|----------|-------|
| `us-2ac311d6` | Publier un agent dans la marketplace |
| `us-73fb26af` | Évaluer et noter un agent de la marketplace |
| `us-a37f7139` | Importer un agent de la marketplace dans son catalogue |
| `us-ca4a9997` | Parcourir la marketplace d'agents communautaires |

### Skills & Compétences (`feat-skills`)

| Story ID | Title |
|----------|-------|
| `us-88dad1d2` | Versionner et rollback un skill |
| `us-91b93cb5` | Assigner un skill à un ou plusieurs agents |
| `us-e444416d` | Créer un nouveau skill agent (prompt, tool, workflow) |

### Annotation Studio (`feat-annotate`)

| Story ID | Title |
|----------|-------|
| `us-307ac0dd` | Créer un ticket TMA depuis une annotation |
| `us-78a52813` | Consulter toutes les annotations d'un projet |
| `us-94809bbf` | Filtrer les annotations par type (bug, feature, question) |
| `us-aa93df2b` | Annoter un élément UI en cliquant dessus |
| `us-c76aa9ea` | Exporter les annotations en markdown |

### MCP Servers (`feat-mcps`)

| Story ID | Title |
|----------|-------|
| `us-084bc4f2` | Lister les serveurs MCP disponibles |
| `us-b2b1d5c5` | Configurer les paramètres d'un serveur MCP |
| `us-c8f3de69` | Activer ou désactiver un serveur MCP |

### Patterns d'Orchestration (`feat-patterns`)

| Story ID | Title |
|----------|-------|
| `us-22d0f438` | Parcourir la bibliothèque des patterns d'orchestration |
| `us-7bcd3de8` | Instancier un pattern dans un projet |
| `us-98fe50be` | Créer un nouveau pattern personnalisé |

### Tool Builder (`feat-tool-builder`)

| Story ID | Title |
|----------|-------|
| `us-409bccb0` | Documenter un outil avec sa spec OpenAPI |
| `us-633d0b74` | Versionner et déployer un outil |
| `us-d0810d81` | Créer un nouvel outil pour agent (fonction Python/API REST) |
| `us-e5ea9a32` | Tester un outil depuis l'interface builder |

### Workflows (`feat-workflows`)

| Story ID | Title |
|----------|-------|
| `us-06b42bc5` | Déclencher un workflow manuellement |
| `us-06d0e8ec` | Voir l'évolution des workflows dans le temps |
| `us-1328e134` | Créer un nouveau workflow d'automatisation |
| `us-3561ddab` | Consulter l'historique des exécutions d'un workflow |
| `us-f69eaa7c` | Visualiser la liste des workflows actifs |

### Product Backlog (`feat-backlog`)

| Story ID | Title |
|----------|-------|
| `us-72e2d803` | Lier une story à une feature SAFe |
| `us-af7da823` | Affecter un story points à une user story |
| `us-cd4bc004` | Créer une nouvelle user story depuis le backlog |
| `us-e9e21236` | Prioriser les items du backlog par drag-and-drop |
| `us-f76fbac3` | Filtrer le backlog par epic, feature ou sprint |

### Cérémonies SAFe (`feat-ceremonies`)

| Story ID | Title |
|----------|-------|
| `us-33f70f3b` | Consulter l'agenda des cérémonies de l'ART |
| `us-922e5132` | Planifier une nouvelle cérémonie (sprint review, retro) |
| `us-b64042dd` | Enregistrer les décisions d'une cérémonie |

### PI Board — Program Increment (`feat-pi-board`)

| Story ID | Title |
|----------|-------|
| `us-6a5d1ae0` | Visualiser les objectifs du PI en cours |
| `us-aac74b8e` | Identifier les dépendances inter-équipes sur le PI board |
| `us-bca96c00` | Marquer un risque ou un impediment sur le PI board |
| `us-e674f1fc` | Suivre l'avancement des features du PI |

### Portfolio (`feat-portfolio`)

| Story ID | Title |
|----------|-------|
| `us-2aba9879` | Visualiser les epics du portfolio avec leur statut et budget |
| `us-b4ce4b0b` | Suivre l'avancement des programmes dans le portfolio |
| `us-b7da91c2` | Créer et prioriser un nouvel epic depuis le portfolio |

### Projets (`feat-projects`)

| Story ID | Title |
|----------|-------|
| `us-17ea58ca` | Archiver un projet terminé |
| `us-287a4e7a` | Accéder rapidement à un projet depuis la liste |
| `us-6fa36606` | Assigner des membres à un projet |
| `us-748a03d5` | Créer un nouveau projet sur la plateforme |

### Design System (`feat-design-system`)

| Story ID | Title |
|----------|-------|
| `us-719e11ad` | Télécharger les assets du design system |
| `us-bbb46fed` | Consulter les tokens de couleur et typographie |
| `us-d9674c23` | Parcourir la bibliothèque de composants du design system |

### Idéation Projet (`feat-ideation`)

| Story ID | Title |
|----------|-------|
| `us-42644521` | Générer automatiquement un backlog initial depuis une idée |
| `us-60c7147c` | Consulter l'historique des idéations précédentes |
| `us-c0724a89` | Décrire une idée de projet et obtenir un brief structuré |
| `us-c1c33e1b` | Exporter une idéation en PDF |

### Domaine Métier (`feat-metier`)

| Story ID | Title |
|----------|-------|
| `us-016d8073` | Importer un référentiel métier existant |
| `us-d7b7f88b` | Définir les règles métier d'un domaine |
| `us-de14a443` | Cartographier un processus métier avec les agents |

### Idéation Marketing (`feat-mkt-ideation`)

| Story ID | Title |
|----------|-------|
| `us-109d6ee2` | Générer des personas utilisateurs depuis un brief produit |
| `us-7d702e6d` | Créer un user journey map assisté par IA |
| `us-be24050f` | Générer des idées de campagnes marketing |

### Product Line (`feat-product-line`)

| Story ID | Title |
|----------|-------|
| `us-62a2efb6` | Créer une nouvelle ligne de produit |
| `us-8061301a` | Visualiser la roadmap produit |
| `us-a2ee4899` | Définir les variantes d'un produit |

### Vue CTO (`feat-cto`)

| Story ID | Title |
|----------|-------|
| `us-707ca4f0` | Consulter le tableau de bord technique du CTO |
| `us-8695ac07` | Suivre la vélocité d'innovation de l'équipe |
| `us-ae034dbd` | Analyser la dette technique globale |

### Vue DSI (`feat-dsi`)

| Story ID | Title |
|----------|-------|
| `us-3ab2cee5` | Suivre les coûts d'infrastructure et LLM |
| `us-49b87adf` | Vérifier la conformité sécurité de la plateforme |
| `us-58fb2f82` | Consulter le tableau de bord de gouvernance DSI |

### Mercato Agents (`feat-mercato`)

| Story ID | Title |
|----------|-------|
| `us-04bb0e38` | Proposer un agent sur le mercato |
| `us-5de43b7b` | Trouver et acquérir un agent depuis le mercato |
| `us-74a6c645` | Négocier les conditions d'utilisation d'un agent |

### Onboarding (`feat-onboarding`)

| Story ID | Title |
|----------|-------|
| `us-136afcc7` | Créer son premier projet lors de l'onboarding |
| `us-1941c362` | Suivre le tutoriel d'onboarding pas à pas |
| `us-20e4e89b` | Configurer son profil lors de l'onboarding |

### Toolbox (`feat-toolbox`)

| Story ID | Title |
|----------|-------|
| `us-7921d0b0` | Partager un outil avec l'équipe |
| `us-d7f6ea0c` | Accéder aux utilitaires partagés de la plateforme |

### Évaluations LLM (`feat-evals`)

| Story ID | Title |
|----------|-------|
| `us-2b2263cc` | Consulter l'historique des évaluations |
| `us-71090532` | Exporter les résultats d'évaluation en CSV |
| `us-7409e5ea` | Comparer les scores de deux modèles LLM |
| `us-e03946af` | Lancer un benchmark d'évaluation sur un agent |

### Jarvis — Assistant IA (`feat-jarvis`)

| Story ID | Title |
|----------|-------|
| `us-847b14fc` | Poser une question à Jarvis sur la plateforme |
| `us-c9f7c6af` | Obtenir des suggestions contextuelles depuis n'importe quelle page |
| `us-e5f1da02` | Générer du code avec l'assistant IA |

### Memory Agent (`feat-memory`)

| Story ID | Title |
|----------|-------|
| `us-31017884` | Filtrer la mémoire par scope (global, projet, session) |
| `us-4bf433e0` | Ajouter manuellement une entrée en mémoire |
| `us-8910a4b6` | Consulter les entrées mémoire d'un agent |
| `us-efb253fd` | Effacer ou archiver des entrées mémoire |

### Wiki SF (`feat-wiki`)

| Story ID | Title |
|----------|-------|
| `us-b32f6354` | Rechercher dans le wiki par mot-clé |
| `us-dbc20525` | Créer ou éditer une page wiki |
| `us-ed1003a8` | Consulter la documentation de la plateforme depuis le wiki |

### Métriques & Analytics (`feat-metrics`)

| Story ID | Title |
|----------|-------|
| `us-046781a4` | Consulter les métriques DORA (lead time, MTTR, deployment frequency) |
| `us-389091a6` | Visualiser les coûts LLM par agent et par projet |
| `us-91cbc95c` | Analyser les performances du pipeline CI/CD |
| `us-b5ddeb24` | Exporter les métriques en CSV ou JSON |
| `us-cb58a4d5` | Suivre la qualité du code sur le dashboard qualité |

### Monitoring Temps Réel (`feat-monitoring`)

| Story ID | Title |
|----------|-------|
| `us-4546292c` | Voir le statut de tous les agents en temps réel |
| `us-64d85c8b` | Consulter les files d'attente et la charge du système |
| `us-b244b26c` | Recevoir des alertes en cas d'erreur critique |

### Opérations Plateforme (`feat-ops`)

| Story ID | Title |
|----------|-------|
| `us-561129fc` | Consulter les résultats des tests d'endurance |
| `us-ad3e8b9a` | Déclencher un auto-heal sur un service dégradé |
| `us-c41f43db` | Lancer un test de chaos engineering |
| `us-e0672015` | Effectuer un backup de la base de données |

### Qualité Code (`feat-quality`)

| Story ID | Title |
|----------|-------|
| `us-7a642ea5` | Suivre l'évolution de la couverture de tests |
| `us-94e176eb` | Identifier les fichiers avec le plus de dette technique |
| `us-f409f61c` | Consulter le score de qualité global du codebase |

### ART — Agile Release Train (`feat-art`)

| Story ID | Title |
|----------|-------|
| `us-417125f6` | Assigner des rôles et capacités aux équipes |
| `us-5015432f` | Suivre la vélocité de l'ART par PI |
| `us-50973372` | Visualiser la composition de l'ART (équipes, agents) |

### Dashboard / Cockpit (`feat-cockpit`)

| Story ID | Title |
|----------|-------|
| `us-47d6b39b` | Voir les missions actives en temps réel sur le cockpit |
| `us-504dc0af` | Naviguer vers une mission depuis le cockpit en un clic |
| `us-7d44de4d` | Accéder aux métriques clés de la plateforme depuis la page d'accueil |
| `us-93ac9fe5` | Consulter le nombre d'agents actifs et les erreurs récentes |

### Sessions Live (`feat-live`)

| Story ID | Title |
|----------|-------|
| `us-3e8ad464` | Envoyer un message dans une session live |
| `us-6e6b0975` | Rejoindre une cérémonie live (PI Planning, sprint review) |
| `us-e80561b1` | Voir la conversation en cours d'un agent en temps réel |

### Mission Control (`feat-mission-control`)

| Story ID | Title |
|----------|-------|
| `us-00c7e56b` | Annuler ou interrompre une mission depuis l'interface |
| `us-1d2a7899` | Filtrer les missions par statut, projet ou agent |
| `us-660f2bc9` | Consulter les détails d'une mission (logs, artefacts, durée) |
| `us-69704608` | Lancer une mission avec un prompt libre |
| `us-d49f05a0` | Surveiller l'avancement d'une mission en cours |

### Détail Mission (`feat-mission-detail`)

| Story ID | Title |
|----------|-------|
| `us-654a711f` | Consulter les artefacts produits par une mission |
| `us-65b54e84` | Voir le graphe d'exécution d'une mission |
| `us-70f858f5` | Contrôler manuellement les étapes d'une mission |
| `us-8c707eed` | Lier une mission à un ticket du backlog |

### Sessions & Replay (`feat-mission-replay`)

| Story ID | Title |
|----------|-------|
| `us-200d742a` | Exporter les logs d'une session en markdown |
| `us-2dc56c62` | Rejouer une session agent précédente étape par étape |
| `us-48ce4600` | Créer une nouvelle session de travail collaboratif |
| `us-cfae88ce` | Consulter l'historique complet des messages d'une session |""",
    },
    {
        "slug": "traceability-acceptance",
        "title": "Acceptance Criteria",
        "category": "Traceability",
        "icon": "",
        "sort_order": 50,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# Acceptance Criteria

**Total**: 154 AC with `ac-{uuid8}` IDs in Gherkin GIVEN/WHEN/THEN


### Organisation & Équipes (`feat-org`)

**`ac-0aac3e2e`** (pending)
- **GIVEN** un utilisateur sur la page Organisation & Équipes
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Gérer les groupes utilisateurs

**`ac-26274837`** (pending)
- **GIVEN** un utilisateur sur la page Organisation & Équipes
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Assigner des agents et utilisateurs à une équipe

**`ac-78578588`** (pending)
- **GIVEN** un utilisateur sur la page Organisation & Équipes
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer une nouvelle équipe dans l'organisation

**`ac-8d9df802`** (pending)
- **GIVEN** un utilisateur sur la page Organisation & Équipes
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Visualiser l'organigramme de l'organisation


### RBAC — Gestion des Rôles (`feat-rbac`)

**`ac-c68ca87a`** (pending)
- **GIVEN** un utilisateur sur la page RBAC — Gestion des Rôles
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un rôle personnalisé avec des permissions spécifiques

**`ac-2296627b`** (pending)
- **GIVEN** un utilisateur sur la page RBAC — Gestion des Rôles
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Assigner un rôle à un utilisateur

**`ac-5677fbde`** (pending)
- **GIVEN** un utilisateur authentifie sur la page RBAC — Gestion des Rôles
- **WHEN** la page se charge
- **THEN** Consulter le journal d'audit des actions utilisateurs

**`ac-cea00bd2`** (pending)
- **GIVEN** un utilisateur sur la page RBAC — Gestion des Rôles
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Gérer les accès par projet


### Paramètres Plateforme (`feat-settings`)

**`ac-6cb3dfdf`** (pending)
- **GIVEN** un utilisateur sur la page Paramètres Plateforme
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Gérer les clés API des intégrations tierces

**`ac-168e8b56`** (pending)
- **GIVEN** un administrateur sur la page Paramètres Plateforme
- **WHEN** l'utilisateur modifie la configuration
- **THEN** Configurer les limites de rate limiting

**`ac-b803f4ca`** (pending)
- **GIVEN** un administrateur sur la page Paramètres Plateforme
- **WHEN** l'utilisateur modifie la configuration
- **THEN** Configurer le fournisseur LLM par défaut

**`ac-6aaca744`** (pending)
- **GIVEN** un utilisateur sur la page Paramètres Plateforme
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Activer ou désactiver les notifications Slack/Email


### Workspaces (`feat-workspaces`)

**`ac-8b305d4a`** (pending)
- **GIVEN** un administrateur sur la page Workspaces
- **WHEN** l'utilisateur modifie la configuration
- **THEN** Configurer les ressources allouées à un workspace

**`ac-520a8c74`** (pending)
- **GIVEN** un utilisateur sur la page Workspaces
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Archiver un workspace inactif

**`ac-c2c73418`** (pending)
- **GIVEN** un utilisateur sur la page Workspaces
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Inviter des membres dans un workspace

**`ac-7f1a2d66`** (pending)
- **GIVEN** un utilisateur sur la page Workspaces
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouveau workspace pour une équipe


### Chat Agent (`feat-agent-chat`)

**`ac-d44998f8`** (pending)
- **GIVEN** un utilisateur sur la page Chat Agent
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Envoyer un message et recevoir une réponse en streaming

**`ac-a937583a`** (pending)
- **GIVEN** un utilisateur sur la page Chat Agent
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Démarrer une conversation avec un agent depuis son profil

**`ac-b308f23c`** (pending)
- **GIVEN** un utilisateur authentifie sur la page Chat Agent
- **WHEN** la page se charge
- **THEN** Consulter l'historique de conversation avec un agent


### Création d'Agent (`feat-agents-create`)

**`ac-4ac92ddb`** (pending)
- **GIVEN** un utilisateur sur la page Création d'Agent
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Définir les instructions système d'un agent

**`ac-d473c3c7`** (pending)
- **GIVEN** un utilisateur sur la page Création d'Agent
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouvel agent avec son persona et ses skills

**`ac-8b6eff57`** (pending)
- **GIVEN** un utilisateur sur la page Création d'Agent
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Tester un agent depuis l'interface d'édition

**`ac-2ab2f23c`** (pending)
- **GIVEN** un administrateur sur la page Création d'Agent
- **WHEN** l'utilisateur modifie la configuration
- **THEN** Configurer le modèle LLM d'un agent


### Catalogue d'Agents (`feat-agents-list`)

**`ac-b61dafd9`** (pending)
- **GIVEN** une liste affichee sur la page Catalogue d'Agents
- **WHEN** l'utilisateur applique un filtre ou une recherche
- **THEN** Filtrer les agents par rôle, compétence ou statut

**`ac-93e4ee98`** (pending)
- **GIVEN** un utilisateur sur le cockpit ou la navigation
- **WHEN** l'utilisateur clique sur le lien
- **THEN** Accéder au profil d'un agent depuis le catalogue

**`ac-23f2a94d`** (pending)
- **GIVEN** un utilisateur sur la page Catalogue d'Agents
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Parcourir la liste des agents disponibles


### Marketplace d'Agents (`feat-marketplace`)

**`ac-2f4e1d1a`** (pending)
- **GIVEN** un utilisateur sur la page Marketplace d'Agents
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Publier un agent dans la marketplace

**`ac-e74da44f`** (pending)
- **GIVEN** un utilisateur sur la page Marketplace d'Agents
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Évaluer et noter un agent de la marketplace

**`ac-1f18b61f`** (pending)
- **GIVEN** un utilisateur sur la page Marketplace d'Agents
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Importer un agent de la marketplace dans son catalogue

**`ac-2e793898`** (pending)
- **GIVEN** un utilisateur sur la page Marketplace d'Agents
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Parcourir la marketplace d'agents communautaires


### Skills & Compétences (`feat-skills`)

**`ac-9670e7ba`** (pending)
- **GIVEN** un utilisateur sur la page Skills & Compétences
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Versionner et rollback un skill

**`ac-ff90fae5`** (pending)
- **GIVEN** un utilisateur sur la page Skills & Compétences
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Assigner un skill à un ou plusieurs agents

**`ac-99eae97f`** (pending)
- **GIVEN** un utilisateur sur la page Skills & Compétences
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouveau skill agent (prompt, tool, workflow)


### Annotation Studio (`feat-annotate`)

**`ac-23458abc`** (pending)
- **GIVEN** un utilisateur sur la page Annotation Studio
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un ticket TMA depuis une annotation

**`ac-49186240`** (pending)
- **GIVEN** un utilisateur authentifie sur la page Annotation Studio
- **WHEN** la page se charge
- **THEN** Consulter toutes les annotations d'un projet

**`ac-41be2fb1`** (pending)
- **GIVEN** une liste affichee sur la page Annotation Studio
- **WHEN** l'utilisateur applique un filtre ou une recherche
- **THEN** Filtrer les annotations par type (bug, feature, question)

**`ac-2e371fb2`** (pending)
- **GIVEN** un utilisateur sur la page Annotation Studio
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Annoter un élément UI en cliquant dessus

**`ac-a7e384ff`** (pending)
- **GIVEN** des donnees disponibles sur la page Annotation Studio
- **WHEN** l'utilisateur clique sur exporter
- **THEN** Exporter les annotations en markdown


### MCP Servers (`feat-mcps`)

**`ac-f9bf5498`** (pending)
- **GIVEN** un utilisateur sur la page MCP Servers
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Lister les serveurs MCP disponibles

**`ac-2a84f361`** (pending)
- **GIVEN** un administrateur sur la page MCP Servers
- **WHEN** l'utilisateur modifie la configuration
- **THEN** Configurer les paramètres d'un serveur MCP

**`ac-d9ecde72`** (pending)
- **GIVEN** un utilisateur sur la page MCP Servers
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Activer ou désactiver un serveur MCP


### Patterns d'Orchestration (`feat-patterns`)

**`ac-daba7df2`** (pending)
- **GIVEN** un utilisateur sur la page Patterns d'Orchestration
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Parcourir la bibliothèque des patterns d'orchestration

**`ac-a9b1c393`** (pending)
- **GIVEN** un utilisateur sur la page Patterns d'Orchestration
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Instancier un pattern dans un projet

**`ac-e16d337b`** (pending)
- **GIVEN** un utilisateur sur la page Patterns d'Orchestration
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouveau pattern personnalisé


### Tool Builder (`feat-tool-builder`)

**`ac-765fe0b6`** (pending)
- **GIVEN** un utilisateur sur la page Tool Builder
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Documenter un outil avec sa spec OpenAPI

**`ac-1cace2f5`** (pending)
- **GIVEN** un utilisateur sur la page Tool Builder
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Versionner et déployer un outil

**`ac-ba0c0700`** (pending)
- **GIVEN** un utilisateur sur la page Tool Builder
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouvel outil pour agent (fonction Python/API REST)

**`ac-0fcb5bb5`** (pending)
- **GIVEN** un utilisateur sur la page Tool Builder
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Tester un outil depuis l'interface builder


### Workflows (`feat-workflows`)

**`ac-41b33fbc`** (pending)
- **GIVEN** un utilisateur sur la page Workflows
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Déclencher un workflow manuellement

**`ac-b9cd214a`** (pending)
- **GIVEN** un utilisateur authentifie sur la page Workflows
- **WHEN** la page se charge
- **THEN** Voir l'évolution des workflows dans le temps

**`ac-0b7cfd5c`** (pending)
- **GIVEN** un utilisateur sur la page Workflows
- **WHEN** l'utilisateur clique sur le bouton d'action
- **THEN** Créer un nouveau workflow d'automatisation

**`ac-de89ee71`** (pending)
- **GIVEN** un utilisateur authentifie sur la page Workflows
- **WHEN** la page se charge
- **THEN** Consulter l'historique des exécutions d'un workflow

**`ac-2b471c67`** (pending)
- **GIVEN** un utilisateur sur la page Workflows
- **WHEN** l'utilisateur interagit avec l'interface
- **THEN** Visualiser la liste des workflows actifs


*Showing first 15 features. Full data via `/projects/sf-platform/product` traceability tab.*""",
    },
    {
        "slug": "traceability-ihm",
        "title": "IHM / Screens",
        "category": "Traceability",
        "icon": "",
        "sort_order": 60,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# IHM / Screen Annotations

## Status: Planned

Screen-to-feature mapping is the next traceability layer.

### Target Format
```html
<!-- Ref: feat-cockpit -->
<div class="cockpit-dashboard">...</div>
```

### Screens to Annotate
| Page | Route | Features |
|------|-------|----------|
| Cockpit | `/cockpit` | feat-cockpit |
| Missions | `/missions` | feat-mission-control, feat-mission-detail |
| Agents | `/agents` | feat-agents-list, feat-agents-create |
| Backlog | `/backlog` | feat-backlog, feat-portfolio |
| Workflows | `/workflows` | feat-workflows, feat-patterns |
| Metrics | `/metrics` | feat-metrics, feat-monitoring |
| Settings | `/settings` | feat-settings, feat-rbac |
| Wiki | `/toolbox` > Wiki | feat-wiki |
| Skills | `/toolbox` > Skills | feat-skills |
| Memory | `/toolbox` > Memory | feat-memory |
| Design System | `/design-system` | feat-design-system |
| PI Board | `/pi-board` | feat-pi-board |
| Art / Teams | `/art` | feat-art |
| Evaluations | `/evals` | feat-evals |
""",
    },
    {
        "slug": "traceability-code-refs",
        "title": "Code References",
        "category": "Traceability",
        "icon": "",
        "sort_order": 70,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# Code Reference Headers

## Format
Every Python file in `platform/` should include a `# Ref:` header:
```python
# Ref: feat-cockpit, feat-live
# Description: Real-time cockpit dashboard WebSocket handler
```

## Current Coverage
- **14 / 384** files have `# Ref:` headers (**3.6%**)
- Target: **80%** of platform/ files

## Priority Files
| File | Expected Ref |
|------|-------------|
| `web/routes/pages.py` | feat-cockpit, feat-portfolio |
| `web/routes/missions.py` | feat-mission-control, feat-mission-detail |
| `web/routes/projects.py` | feat-projects, feat-backlog |
| `agents/loop.py` | feat-agents-list, feat-agent-chat |
| `agents/executor.py` | feat-agents-list |
| `agents/prompt_builder.py` | feat-skills |
| `missions/product.py` | feat-backlog, feat-portfolio |
| `llm/client.py` | feat-metrics |
| `web/routes/wiki.py` | feat-wiki |
| `web/routes/api/memory.py` | feat-memory |
| `web/routes/api/rbac.py` | feat-rbac |
| `patterns/engine.py` | feat-patterns |
| `workflows/registry.py` | feat-workflows |
| `tools/code_tools.py` | feat-tool-builder |
| `mcps/manager.py` | feat-mcps |

## Automation
Scheduled scan of `platform/` reports:
- Missing `# Ref:` headers
- Stale references (feat-xxx not in DB)
- Coverage % by directory
""",
    },
    {
        "slug": "traceability-tests",
        "title": "Test Traceability",
        "category": "Traceability",
        "icon": "",
        "sort_order": 80,
        "parent_slug": "traceability-overview",
        "owner": "system",
        "visibility": "owner",
        "content": """# Test Traceability

## Status: In Progress

### Unit Tests (TU)
- **35 test functions** in `tests/`
- **0** currently linked to feature IDs
- Target: each test references `feat-xxx` or `us-xxx` in docstring

#### Format
```python
def test_cockpit_loads():
    # Ref: feat-cockpit, us-47d6b39b
    ...
```

### E2E Tests (Playwright)
- **23 spec files** in `platform/tests/e2e/`
- **0** currently linked to feature IDs

#### Format
```typescript
test.describe('Cockpit Dashboard', () => {
    // Ref: feat-cockpit, feat-live
    test('shows active missions', async ({ page }) => {
        // Ref: us-47d6b39b, ac-f4fbb5f3
        ...
    });
});
```

### Coverage Matrix (sample)
| Feature | TU | E2E | AC pass/total |
|---------|-----|------|--------------|
| feat-cockpit | 0 | 1 | 0/4 |
| feat-agents-list | 2 | 1 | 0/3 |
| feat-workflows | 1 | 2 | 0/5 |
| feat-metrics | 3 | 1 | 0/5 |
| feat-settings | 0 | 1 | 0/4 |
| feat-rbac | 1 | 1 | 0/4 |

### Automation Plan
1. Add `# Ref:` to existing test files
2. `traceability_report.py` scans tests + code + templates
3. Coverage matrix per feature in CI
4. Gate: new feature must have >= 1 test
""",
    },
]
