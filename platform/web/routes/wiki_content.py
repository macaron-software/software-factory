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

Welcome to the **Macaron Software Factory** — a multi-agent collaborative platform for software engineering.

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

## First Steps

1. **Complete onboarding** — The first screen guides you through initial setup
2. **Create a project** — Go to Projects → New Project
3. **Start a mission** — Open your project and type a message to the Agent Lead
4. **Watch agents collaborate** — The session view shows real-time agent collaboration

## Demo Mode

For testing without LLM keys:

```bash
export PLATFORM_LLM_PROVIDER=demo
python -m uvicorn platform.server:app --port 8090 --ws none
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATFORM_LLM_PROVIDER` | `minimax` | LLM provider (minimax, azure-openai, azure-ai, demo) |
| `PLATFORM_LLM_MODEL` | `MiniMax-M2.5` | Model name |
| `PLATFORM_PORT` | `8090` | HTTP port |
| `PLATFORM_DB_PATH` | `data/platform.db` | SQLite database path |
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
]
