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
]
