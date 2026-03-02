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

Welcome to the **Macaron Software Factory** — a multi-agent collaborative platform for autonomous software engineering.

## Quick Start (local)

```bash
# Clone & install
git clone https://github.com/macaron-software/software-factory.git
cd software-factory/platform
pip install -r requirements.txt

# Run locally (from parent directory — NEVER use --reload)
python -m uvicorn platform.server:app --port 8099 --ws none --log-level warning

# Open http://localhost:8099
```

## Docker

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup    # builds Docker image
make run      # starts platform on port 8090
```

## First Steps

![Dashboard](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/home.png)

1. **Complete onboarding** — The first screen guides you through initial setup
2. **Create a project** — Go to Projects → New Project
3. **Start a mission** — Open your project and type a message to the Agent Lead
4. **Watch agents collaborate** — The session view shows real-time agent collaboration

![Missions](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/missions.png)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATFORM_LLM_PROVIDER` | `minimax` | LLM provider (minimax, azure-openai, azure-ai) |
| `PLATFORM_LLM_MODEL` | `MiniMax-M2.5` | Model name |
| `PLATFORM_PORT` | `8090` | HTTP port |
| `DATABASE_URL` | *(none)* | PostgreSQL URL — `postgresql://user:pass@host/db` |
| `REDIS_URL` | *(none)* | Redis URL — `redis://host:6379/0` (optional, enables pub/sub) |
| `PLATFORM_MODE` | `full` | Process mode: `full`, `factory` (headless), or `ui` (web only) |
| `PLATFORM_DB_PATH` | `data/platform.db` | SQLite path (dev only, ignored when DATABASE_URL set) |

## Important Caveats

- **NEVER** use `--reload` with uvicorn (naming conflict with Python stdlib `platform` module)
- **NEVER** `import platform` at top-level inside the package
- **Always** run from the parent directory: `python -m uvicorn platform.server:app ...`
- `--ws none` is mandatory (the platform uses SSE, not WebSockets)

## Next Steps

- [User Guide](user-guide) — walkthrough of every feature
- [Settings Hub](settings-hub) — configure orchestration, LLM providers, integrations
- [Mission Cockpit](mission-cockpit) — monitor and control running missions
- [Core Concepts](concepts) — projects, agents, patterns, workflows
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

A practical walkthrough of every major section in the Software Factory.

---

## Dashboard

![Dashboard](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/home.png)

The Dashboard is your starting point. It adapts to your **perspective**:

| Perspective | What you see |
|-------------|-------------|
| **DSI** | Portfolio overview, project health, budget |
| **Product** | Backlog priority, feature pipeline |
| **Engineering** | Active sessions, agent activity, recent missions |
| **Scrum Master** | Velocity, team fitness, sprint progress |

**How to use it:**
1. Select your perspective from the top-right switcher.
2. Click any card to drill into that project or mission.
3. Use the global search bar (top center) to jump to any page.

---

## Projects

![Projects](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/projects.png)

A Project is the top-level workspace. It holds agents, missions, memory, and artifacts.

**Create a project:**
1. Click **Projects** → **+ New Project**.
2. Enter a name, description, and pick a color/avatar.
3. Choose your **Agent Lead** (the agent that receives your messages).
4. Optionally connect a Git repository.
5. Click **Create** — you land in the project chat.

**Inside a project** you have tabs: Chat, Missions, Backlog, Sessions, Agents, Memory, Workflows, Settings.

---

## Missions

![Missions Board](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/missions.png)

A Mission is a unit of work: your prompt → agent collaboration → result.

**Start a mission:**
1. Open a project.
2. Type your request in the chat (e.g. *"Add user authentication with JWT"*).
3. The Agent Lead creates a mission and dispatches agents.

**Status flow:** `planning → active → review → completed` (or `failed` / `interrupted`)

Each mission has **runs** (attempts) and **phases** (agent steps within a run). You can re-run a failed mission from the mission card.

---

## Mission Cockpit

![Mission Cockpit](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/cockpit.png)

The Cockpit gives you a real-time pipeline view of all running missions across the platform.

- **Semaphore gauge** — shows how many missions run in parallel (configured in Settings → Orchestrator).
- **Per-mission controls** — pause, stop, or inspect any running mission.
- **Phase timeline** — each bar is an agent phase; hover for token cost and duration.

Open it from the top nav **⚡ Cockpit** link or from any mission card.

---

## Backlog

![Backlog](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/backlog.png)

WSJF-prioritized feature backlog using SAFe methodology.

**How to use it:**
1. Click **Backlog** inside a project.
2. Use **+ Add Feature** to create items.
3. Set **User Value**, **Time Criticality**, and **Risk Reduction** — WSJF score is computed automatically.
4. Drag items to reorder or set priority manually.
5. Click a feature to start a mission from it directly.

**Ideation mode** (multi-agent brainstorming): type a prompt in the Ideation tab, agents collaborate to generate and score feature ideas.

---

## Sessions

Live agent collaboration view. Each message is color-coded by agent role.

**How to read a session:**
- **Blue** = Agent Lead (coordinator)
- **Green** = Developer agents
- **Orange** = Reviewer / QA agents
- **Purple** = Architect agents

Sessions stream in real-time via SSE. You can intervene with a message at any time — it goes to the Agent Lead.

---

## Metrics

![Metrics](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/metrics.png)

Five tabs covering engineering performance:

| Tab | Content |
|-----|---------|
| **DORA** | Deploy frequency, lead time, change failure rate, MTTR |
| **Quality** | Code quality scores, test coverage, security findings |
| **Analytics** | Mission stats, agent performance, cost per run |
| **Monitoring** | Real-time CPU, memory, request latency |
| **Pipeline** | CI/CD pipeline performance and trends |

LLM cost per mission is shown in **Analytics** → *Cost* column. See [LLM Cost Tracking](llm-cost-tracking) for details.

---

## Settings Hub

![Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings.png)

Global platform configuration. Five tabs: **General**, **Orchestrator**, **LLM**, **Integrations**, **Notifications**.

Key settings you'll use most:
- **Orchestrator → Mission Semaphore** — max parallel missions.
- **Orchestrator → Budget Cap** — max LLM cost per run (USD).
- **Orchestrator → YOLO Mode** — agents proceed without approval gates.
- **LLM → Provider Priority** — which LLM provider to use first.

Full details in [Settings Hub](settings-hub).

---

## Agents

![Agents](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/agents.png)

The agent catalog. Each agent has a role, system prompt, skills, tools, and LLM model.

**How to use it:**
1. Go to **Toolbox → Agents** (or **Projects → Agents** tab).
2. Click an agent to view/edit its system prompt and skills.
3. Use **+ New Agent** to create a custom agent.
4. Assign agents to a project via the project's **Agents** tab.

---

## Memory

![Memory](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/memory.png)

Persistent knowledge store for each project. Agents read from and write to memory automatically.

**How to use it:**
1. Open **Toolbox → Memory**.
2. Search memory entries with the full-text search bar.
3. Click an entry to view or edit it.
4. Use **+ Add** to inject knowledge manually (e.g. architecture decisions, constraints).

Memory entries are scoped per project. Agents reference them during planning phases.

---

## Workflows

![Workflows](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/workflows.png)

Workflows chain **Patterns** (agent assemblies) into multi-step pipelines.

**How to use it:**
1. Go to **Projects → Workflows** tab.
2. Click **+ New Workflow**.
3. Add steps — each step picks a Pattern and configuration.
4. Save and trigger the workflow from the chat (`/workflow <name>`).

Common built-in workflows: `full-dev` (plan → code → review → test), `quick-fix` (code → review).

---

## Toolbox

The Toolbox collects platform-wide utilities:

| Tab | Description |
|-----|-------------|
| **Skills** | Agent skill library — browse and assign skills |
| **Memory** | Cross-project memory browser |
| **MCPs** | MCP server connections — add/remove tool servers |
| **Evals** | Run quality evaluations on agent outputs |
| **API** | Interactive Swagger docs |
| **CLI** | Web terminal for direct platform commands |
| **Design System** | UI component reference |
| **Wiki** | This documentation |

---

## Next Steps

- [Mission Cockpit](mission-cockpit) — deep dive into the pipeline view
- [Settings Hub](settings-hub) — configure orchestration, LLM, integrations
- [LLM Cost Tracking](llm-cost-tracking) — understand and control costs
- [Patterns Guide](patterns-guide) — orchestration patterns
- [Workflows Guide](workflows-guide) — build pipelines
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

## Production Architecture (IHM/Factory decoupled)

```
Browser
  |
  v
nginx (port 80/443)  --  blue-green switch
  +-- /* --> platform-web-blue/green:8090  (IHM, restartable)

platform-web  --Redis sub-->  Redis pub/sub  <--Redis pub--  platform-factory
                                                                    |
                                                              PostgreSQL (shared)
```

- **platform-factory** — headless agent engine, never restarts on UI changes
  - Missions, patterns engine, orchestrator, watchdog, A2A bus
  - Publishes events to Redis channel `a2a:events`
- **platform-web** (blue/green) — IHM, hot-restartable
  - Web routes, Jinja2 templates, static files, SSE streams
  - Subscribes to Redis `a2a:events` and forwards to browser SSE
- **Redis** — pub/sub bridge between factory and web containers
- **PostgreSQL** — shared persistent storage (both containers read/write)
- **nginx** — blue-green switch + TLS termination

`PLATFORM_MODE` controls which subsystems start:

| Mode | Factory (agents/missions) | Web (routes/UI) | Redis listener |
|------|--------------------------|-----------------|----------------|
| `full` | yes | yes | if REDIS_URL set |
| `factory` | yes | no | publisher |
| `ui` | no | yes | subscriber |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTMX + Jinja2 templates + SSE |
| **Backend** | Python 3.12 + FastAPI + Uvicorn |
| **Database** | PostgreSQL (prod) / SQLite WAL (dev) |
| **Cache/Pub-sub** | Redis 7 (optional, fallback to in-memory) |
| **LLM** | MiniMax M2.5, Azure OpenAI gpt-5-mini, Azure AI |
| **Tools** | MCP protocol (fetch, memory, playwright, solaris) |
| **Deploy** | Docker + docker-compose on Azure VM + OVH VPS |
| **Reverse proxy** | nginx — blue-green + TLS + HSTS |
| **Auth** | JWT (HttpOnly cookies) |
| **i18n** | 18 languages via Accept-Language header |

## Directory Structure

```
platform/
|-- server.py          # FastAPI entry point + PLATFORM_MODE dispatch
|-- config.py          # Configuration (7 classes)
|-- models.py          # Pydantic models (~25)
|-- web/
|   |-- routes/        # 13 route modules + wiki, wiki_content
|   |-- templates/     # Jinja2 HTML templates (64 files)
|   +-- static/        # CSS, JS, images
|-- agents/            # Agent loop, executor, store, tool_schemas
|-- orchestrator/      # Mission orchestrator, WSJF
|-- patterns/          # 15 orchestration patterns + engine
|-- workflows/         # 36 built-in workflows
|-- llm/               # Multi-provider LLM client (fallback chain)
|-- tools/             # Code, git, deploy, memory, security, web, MCP
|-- db/                # Migrations, PG adapter, pool management
|-- a2a/               # Agent-to-Agent protocol + Redis pub/sub backend
|-- missions/          # SAFe lifecycle (Epics, Features, Stories, Tasks)
|-- mcps/              # MCP server manager
|-- memory/            # 4-layer persistent memory (FTS5)
|-- services/          # Notifications + mission orchestration
|-- ops/               # Auto-heal, chaos, backup/restore
|-- security/          # Auth, RBAC, permissions
|-- i18n/              # Locale catalogs (18 languages)
+-- deploy/            # Dockerfile, docker-compose-vm.yml, nginx configs
```

## Agent Architecture

```
Pattern Engine (engine.py)
  |
  +-- Sequential: A -> B -> C
  +-- Parallel: A | B | C -> merge
  +-- Hierarchical: Lead -> [Dev1, Dev2, QA]
  +-- Loop: iterate until quality gate passes
  +-- Router: dispatch by content type
  +-- Aggregator: synthesize multiple outputs
  +-- Adversarial: L0 (deterministic) + L1 (LLM guard)
  +-- Network: debate / human-in-the-loop
```

See [Orchestration Patterns](patterns) for details.
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

![Missions Board](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/missions.png)

## Mission Lifecycle

```
User Prompt → Planning → Active → Review → Completed
                                      ↓
                                   Failed / Interrupted
```

Each mission has **runs** (attempts) and **phases** (agent steps per run). Failed missions can be retried from the mission card.

## Mission Cockpit

![Mission Cockpit](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/cockpit.png)

The Cockpit shows all running missions in a pipeline view. Use it to monitor progress, inspect phases, and intervene if needed. See [Mission Cockpit](mission-cockpit) for details.

## Mission Replay

![Mission Replay](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/mission_replay.png)

Step through a completed mission phase by phase. Useful for debugging unexpected results.

**How to use it:**
1. Open a completed or failed mission.
2. Click the **Replay** button.
3. Use ◀ ▶ to step through each agent phase.
4. Each phase shows the agent, its prompt, and its output.

---

## Semaphore Control

The **Mission Semaphore** limits how many missions run in parallel across the platform.

- Default: `3` concurrent missions.
- Higher values = more parallelism but more LLM API load.
- Set it in **Settings → Orchestrator → Mission Semaphore**.

**When to change it:**
- Reduce to `1` when debugging a single mission and you want full resource focus.
- Increase up to your LLM provider's rate limit to maximize throughput.

---

## YOLO Mode

YOLO Mode lets agents proceed through all phases **without waiting for human approval gates**.

- **Disabled (default)**: agents pause at review checkpoints and wait for your ✅.
- **Enabled**: agents skip approval steps and run fully autonomously end-to-end.

**When to use it:**
- Rapid prototyping where speed matters more than oversight.
- Batch processing of many small missions.
- Fully trusted workflows with well-tested patterns.

**How to enable it:**
1. Go to **Settings → Orchestrator**.
2. Toggle **YOLO Mode** on.
3. Save. Takes effect immediately for new missions.

> ⚠️ Use with caution on production-critical projects.

---

## Auto-Resume Watchdog

The watchdog monitors stalled missions and resumes them automatically.

- A mission is considered **stalled** if no agent has produced output for more than `N` minutes (configurable).
- The watchdog re-dispatches the last active agent with the same context.
- Prevents missions from hanging indefinitely due to LLM timeouts or transient errors.

**Configure it** in **Settings → Orchestrator → Auto-Resume Watchdog** (enable/disable + timeout threshold).

---

## Budget Cap

Limit the maximum LLM spend per mission run.

- Set in **Settings → Orchestrator → Budget Cap (USD)**.
- When a run's `llm_cost_usd` reaches the cap, the mission is paused and marked `budget_exceeded`.
- You can raise the cap and resume, or close the mission.
- Default: no cap (`0` = unlimited).

**Example:** set cap to `$0.50` for exploratory missions to avoid runaway costs.

See [LLM Cost Tracking](llm-cost-tracking) for how costs are measured.

---

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

## Environments

| Environment | URL | Server | Mode |
|-------------|-----|--------|------|
| Local dev | http://localhost:8099 | macOS, Python 3.12 | full |
| OVH Demo | http://54.36.183.124 | Debian VPS | full |
| Azure Prod | https://sf.macaron-software.com | Azure VM D4as_v5 4CPU/16GB | factory + web blue/green |

## Local Development

```bash
cd software-factory/platform
pip install -r requirements.txt

# Run (NEVER --reload, ALWAYS --ws none, run from parent dir)
python -m uvicorn platform.server:app --port 8099 --ws none --log-level warning

# Tests
python -m pytest tests/ -v                  # unit + integration
cd tests/e2e && npx playwright test         # E2E (82+ tests)
```

## Docker (local or simple server)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
docker compose up -d
# -> http://localhost:8090
```

## Azure Prod — Blue-Green Deployment

Architecture: nginx -> blue/green swap. Factory never restarts for UI changes.

```
nginx:443 -> platform-web-blue:8090  (active)
          -> platform-web-green:8090 (standby)
platform-factory:8091               (always-on headless engine)
redis:6379                          (pub/sub bridge)
postgres:5432                       (shared DB)
```

### Full redeploy (rsync + rebuild)

```bash
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='data/' --exclude='.git' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 \
  "cd /opt/macaron && docker compose --env-file .env \
   -f platform/deploy/docker-compose-vm.yml up -d --build --no-deps platform"
```

### Hotpatch (no rebuild, no factory restart)

```bash
# Fast: copy files, restart only web container
tar cf /tmp/update.tar web/templates/ web/static/ web/routes/
scp -i "$SSH_KEY" /tmp/update.tar azureadmin@4.233.64.30:/tmp/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 \
  "docker cp /tmp/update.tar deploy-platform-1:/tmp/ && \
   docker exec deploy-platform-1 bash -c 'cd /app/macaron_platform && tar xf /tmp/update.tar' && \
   docker restart deploy-platform-1"
```

> Note: hotpatch content is lost on next `docker compose --build`. Always rsync before rebuild.

### Blue-green switch (nginx)

```bash
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 \
  "docker exec nginx-proxy sh -c 'ln -sf /etc/nginx/conf.d/blue.conf /etc/nginx/conf.d/active.conf && nginx -s reload'"
```

## OVH Demo

```bash
ssh debian@54.36.183.124
cd /opt/software-factory
docker compose pull && docker compose up -d
```

CI/CD: GitHub Actions `.github/workflows/deploy-demo.yml`
Secrets: `OVH_SSH_KEY`, `OVH_IP`

## CI/CD

| Pipeline | Trigger | Actions |
|----------|---------|---------|
| `.github/workflows/deploy-demo.yml` | push to `main` | rsync + docker restart on OVH |
| `.gitlab-ci.yml` | push to `main` | rsync + docker build on Azure |

Smart deploy: if diff limited to `web/templates/`, `web/static/`, `web/routes/` only, factory is NOT restarted.
""",
    },
    {
        "slug": "resilience",
        "title": "Resilience & Stability",
        "category": "DevOps",
        "icon": "",
        "sort_order": 15,
        "content": """\
# Resilience & Stability

## PostgreSQL Connection Pool

The platform uses `psycopg_pool.ConnectionPool` (psycopg3 sync pool) with an asyncio FastAPI server.

| Container | Pool size | Notes |
|-----------|-----------|-------|
| platform-factory | 20 | Runs missions, watchdog, auto-resume, auto-heal concurrently |
| platform-web (blue/green) | 5 | Read-heavy, lighter load |

### Connection Leak Prevention

All DB connections MUST follow this pattern:

```python
db = None
try:
    db = get_db()
    # ... work ...
finally:
    if db:
        db.close()   # returns connection to pool via putconn()
```

A missing `finally` block = connection never returned to pool on exception.
The `PgConnectionWrapper` has a `__del__` GC safety net, but GC is non-deterministic.

### Symptoms of Pool Exhaustion

```
PoolTimeout: couldn't get a connection after 15.00 sec
```

This appears in logs when all connections are held (either active or leaked).
Check with: `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`

## Blue-Green nginx Failover

nginx upstream uses a health-checked blue-green switch:

```nginx
upstream platform_web {
    server platform-blue:8090  max_fails=3 fail_timeout=10s;
    server platform-green:8090 max_fails=3 fail_timeout=10s backup;
}
```

Health endpoint: `GET /health` returns `{"status": "ok"}` with HTTP 200.
nginx re-adds a recovered upstream automatically after `fail_timeout`.

## IHM / Factory Decoupling

**Problem:** Restarting the web container to deploy a UI change was interrupting running missions.

**Solution:** `PLATFORM_MODE` splits the process:

- `factory`: starts agents/missions/orchestrator, connects Redis as publisher, no HTTP routes
- `ui`: starts web routes/templates/SSE, subscribes Redis for events, no agent execution
- `full`: both (default, for dev or simple deployments)

Redis pub/sub channel: `a2a:events` — factory publishes, web subscribes and forwards to browser SSE.
Fallback: if `REDIS_URL` is not set, falls back to in-memory bus (no cross-process events, `full` mode only).

## Stability Test Suite

Located at `platform/tests/test_stability.py`. Run with:

```bash
STABILITY_TESTS=1 \
STABILITY_AZ_HOST=https://sf.macaron-software.com \
STABILITY_OVH_HOST=http://54.36.183.124 \
python -m pytest tests/test_stability.py -v -m stability
```

| Test | What it checks |
|------|---------------|
| `test_health_az/ovh` | `/health` returns 200 |
| `test_latency_p99` | p99 < 3s over 20 requests |
| `test_concurrent_10/50` | 10/50 concurrent requests, < 5% error rate |
| `test_rate_limit` | 429 returned when rate exceeded |
| `test_pages_smoke` | 8 key pages return 200 |
| `test_sse_connect` | SSE stream connects and sends `:ping` keepalive |
| `test_disk_memory` | disk < 90%, memory < 90% |
| `test_hot_restart` | container restart, service back in < 30s |
| `test_nginx_failover` | stop blue, nginx switches to green, back in < 10s |
| `test_cold_restart` | full server reboot, service back in < 120s |
| `test_chaos_pause_resume` | docker pause/unpause mission container |

## Auto-Heal

`ops/auto_heal.py` monitors platform health every 60s and creates P1/P2 incidents for:

- LLM provider failures (auto-switches provider)
- PG pool exhaustion (logs alert, triggers incident)
- Container memory > 90% (creates P0 incident)

Incidents visible at `/toolbox` under the Incidents tab.
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
    # ── Settings Hub ─────────────────────────────────────────────
    {
        "slug": "settings-hub",
        "title": "Settings Hub",
        "category": "Guide",
        "icon": "⚙️",
        "sort_order": 56,
        "content": """\
# Settings Hub

![Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings.png)

The Settings Hub is the global configuration centre for the platform. Access it from **⚙️ Settings** in the top nav.

Five tabs: **General**, **Orchestrator**, **LLM**, **Integrations**, **Notifications**.

---

## General Tab

Basic platform identity and preferences:

| Setting | Description |
|---------|-------------|
| **Platform Name** | Display name shown in the header and emails |
| **Timezone** | Used for scheduling, metrics timestamps, and cron jobs |
| **Theme** | Light / Dark / System |
| **Default Perspective** | Which dashboard perspective loads on login |

---

## Orchestrator Tab

![Orchestrator Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings-orchestrator.png)

Controls how missions run at the platform level.

### Mission Semaphore

Maximum number of missions that run **in parallel** across all projects.

- **Default:** `3`
- Increase for high-throughput batch work (up to your LLM rate limit).
- Decrease to `1` when debugging to avoid interference between missions.
- The Cockpit's semaphore gauge reflects this value in real time.

### Budget Cap (USD)

Maximum LLM cost allowed for a single mission run.

- **Default:** `0` (unlimited)
- When a run's cost reaches the cap, it pauses with status `budget_exceeded`.
- You can raise the cap and resume without losing progress.
- Set to `$0.50`–`$2.00` for exploratory missions to control spend.

### YOLO Mode

When **enabled**, agents skip human approval gates and run end-to-end autonomously.

- **Disabled (default):** agents pause at review checkpoints and wait for ✅.
- **Enabled:** full autonomy — no interruptions.
- Best for: rapid prototyping, trusted pipelines, batch processing.
- ⚠️ Disable on production-critical projects where oversight is required.

### Auto-Resume Watchdog

Automatically resumes missions that have stalled (no agent output for N minutes).

- **Enable/Disable** toggle.
- **Timeout threshold** — minutes of inactivity before auto-resume triggers (default: `10`).
- The watchdog re-dispatches the last active phase with the same context.
- Prevents missions from hanging due to transient LLM timeouts.

---

## LLM Tab

![LLM Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings-llm.png)

Configure which LLM providers and models the platform uses.

| Setting | Description |
|---------|-------------|
| **Provider Priority** | Ordered list of providers — first available wins |
| **Default Model** | Model used when no agent-specific override is set |
| **Fallback Model** | Used when the primary model returns a rate-limit error |
| **Rate Limit Handling** | `retry` (back-off + retry) or `fallback` (switch provider) |
| **Max Retries** | How many times to retry a rate-limited request before failing |
| **Request Timeout** | Seconds before a single LLM request times out |

**Provider setup:** each provider requires an API key, base URL, and optional deployment name. Keys are stored encrypted in the database (never in plaintext files).

**Tips:**
- Set MiniMax as primary and Azure OpenAI as fallback for cost/resilience balance.
- Use `retry` mode for providers with burst limits; use `fallback` for strict quotas.

---

## Integrations Tab

![Integrations Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings-integrations.png)

30+ connectors organized by category.

| Category | Examples |
|----------|---------|
| **Source Control** | GitHub, GitLab, Bitbucket, Azure DevOps |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins, CircleCI |
| **Issue Tracking** | Jira, Linear, GitHub Issues, Trello |
| **Cloud** | AWS, Azure, GCP (credentials for deployment agents) |
| **Databases** | PostgreSQL, MySQL, MongoDB, Redis |
| **Communication** | Slack, Microsoft Teams, Discord |
| **Monitoring** | Datadog, Grafana, PagerDuty, Sentry |
| **Secrets** | HashiCorp Vault, AWS Secrets Manager |

**How to configure a connector:**
1. Click the connector card.
2. Enter the required credentials (token, URL, org/project IDs).
3. Click **Test Connection** — a green ✅ confirms it works.
4. Save. The connector is now available to agents as a tool.

Connectors are used by agents automatically when their skill set includes the matching tool category.

---

## Notifications Tab

![Notifications Settings](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/settings-notifications.png)

Configure how and when the platform notifies you.

| Channel | Configuration |
|---------|--------------|
| **Slack** | Webhook URL + channel name. Events: mission complete, failed, budget exceeded |
| **Email** | SMTP settings + recipient list. Events: daily digest, critical failures |
| **Webhook** | HTTP POST to any URL with JSON payload. Fully customizable event filter |

**Event types you can subscribe to:**
- `mission.completed` — mission finished successfully
- `mission.failed` — mission failed after max retries
- `mission.budget_exceeded` — run hit the budget cap
- `mission.stalled` — watchdog triggered
- `agent.error` — agent produced an error response
- `platform.health` — system health alerts

**How to configure Slack:**
1. Create an incoming webhook in your Slack workspace.
2. Paste the webhook URL in **Notifications → Slack → Webhook URL**.
3. Set the channel (e.g. `#engineering-alerts`).
4. Check the events you want.
5. Click **Send Test** to verify.
""",
    },
    # ── Mission Cockpit ──────────────────────────────────────────
    {
        "slug": "mission-cockpit",
        "title": "Mission Cockpit",
        "category": "Guide",
        "icon": "🚀",
        "sort_order": 57,
        "content": """\
# Mission Cockpit

![Mission Cockpit](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/cockpit.png)

The Mission Cockpit is the real-time control panel for all running missions across the platform.

Access it from **⚡ Cockpit** in the top navigation bar.

---

## What you see

### Semaphore Gauge

A circular gauge at the top showing:
- **Running** — missions currently executing (green slice)
- **Queued** — missions waiting for a semaphore slot (amber slice)
- **Cap** — the configured maximum (set in Settings → Orchestrator)

### Mission Pipeline View

Each active mission is shown as a horizontal pipeline row:

```
[Mission Title]  [Project]  ████░░░░  Phase 3/7  ⏱ 2m 14s  💰 $0.12
```

Columns: title, project, progress bar, current phase, elapsed time, LLM cost so far.

Click any mission row to open its full session view.

### Per-Mission Controls

Each row has action buttons:

| Button | Action |
|--------|--------|
| **⏸ Pause** | Suspend the mission after the current phase completes |
| **▶ Resume** | Resume a paused mission |
| **⏹ Stop** | Terminate the mission immediately (marks as `interrupted`) |
| **🔍 Inspect** | Open the live session transcript |
| **🔁 Retry** | Re-run the last failed phase |

---

## How to use the Cockpit

**Monitor a long-running mission:**
1. Open Cockpit.
2. Find your mission in the pipeline view.
3. Watch the phase progress bar advance.
4. If it stalls, click **🔍 Inspect** to see what the agent is doing.

**Intervene in a running mission:**
1. Click **⏸ Pause** to pause after the current phase.
2. Open **🔍 Inspect** to review the transcript.
3. Send a correction message in the session.
4. Click **▶ Resume** to continue.

**Handle a budget warning:**
- When the cost indicator turns amber (>80% of budget cap), consider pausing and reviewing.
- If the mission exceeds the cap it stops automatically — raise the cap in Settings and resume.

---

## Practical Tips

- Keep the Cockpit open in a side monitor when running batch missions.
- Use **Pause** rather than **Stop** — paused missions retain all progress.
- The semaphore gauge tells you at a glance if you're hitting capacity limits.
- Phase duration spikes often mean an LLM is slow or retrying — check the session transcript.
- LLM cost shown is cumulative for the current run. See [LLM Cost Tracking](llm-cost-tracking) for full history.

---

## Related Pages

- [Missions & SAFe](missions) — mission lifecycle and controls
- [Settings Hub](settings-hub) — configure semaphore, budget cap, YOLO mode
- [LLM Cost Tracking](llm-cost-tracking) — understand run costs
""",
    },
    # ── LLM Cost Tracking ────────────────────────────────────────
    {
        "slug": "llm-cost-tracking",
        "title": "LLM Cost Tracking",
        "category": "Guide",
        "icon": "💰",
        "sort_order": 58,
        "content": """\
# LLM Cost Tracking

The platform tracks LLM spend per mission run in the `llm_cost_usd` field.

---

## How costs are measured

Every LLM call records:
- **Input tokens** — prompt size (system prompt + context + history)
- **Output tokens** — agent response size
- **Cost** — `(input_tokens × input_price + output_tokens × output_price)` per provider pricing

These are summed into `llm_cost_usd` on the run record. The Cockpit shows the running total in real time.

---

## Viewing costs in Metrics

![Metrics](https://raw.githubusercontent.com/wiki/macaron-software/software-factory/metrics.png)

1. Go to **Metrics → Analytics**.
2. The **Missions** table has a **Cost** column showing `llm_cost_usd` per run.
3. Use the date filter to see costs over a time range.
4. The **Cost by Provider** chart breaks down spend by LLM provider.
5. The **Cost by Project** chart shows which projects consume the most budget.

---

## Budget Cap

Prevent runaway spend by setting a per-run maximum:

1. Go to **Settings → Orchestrator → Budget Cap (USD)**.
2. Enter a value, e.g. `1.00`.
3. Save. New runs will pause and set status `budget_exceeded` when the cap is reached.
4. To resume: raise the cap (or set to `0` for unlimited) and click **▶ Resume** in the Cockpit.

**Recommended caps by mission type:**

| Mission type | Suggested cap |
|-------------|--------------|
| Quick bug fix | $0.25 |
| Feature implementation | $1.00 |
| Full module with tests | $3.00 |
| Architecture review | $2.00 |
| No cap (trusted pipeline) | $0 (unlimited) |

---

## Provider Comparison Tips

Different providers have very different cost profiles:

| Provider | Strength | Cost profile |
|----------|----------|-------------|
| **MiniMax M2.5** | Fast, cheap | Very low — good for high-volume missions |
| **Azure OpenAI (GPT-4o)** | High quality | Medium — use for complex reasoning |
| **Azure AI (DeepSeek)** | Long context | Low — good for large codebase analysis |

**To minimize costs:**
- Use MiniMax as primary provider for routine missions.
- Reserve GPT-4o for review phases that need higher reasoning quality.
- Set provider priority in **Settings → LLM → Provider Priority**.
- Keep system prompts concise — input tokens are the biggest cost driver.
- Use memory to avoid re-sending large context blocks on every turn.

---

## Related Pages

- [Settings Hub](settings-hub) — set budget cap and provider priority
- [Mission Cockpit](mission-cockpit) — real-time cost gauge
- [Metrics Guide](metrics-guide) — full analytics reference
- [LLM Providers Guide](llm-guide) — provider configuration
""",
    },
]

# ── French translations ────────────────────────────────────────────────────────
# Each entry overrides the EN page for French-speaking browsers.
WIKI_TRANSLATIONS = [
    {
        "slug": "getting-started",
        "lang": "fr",
        "title": "Premiers pas",
        "content": """\
# Premiers pas

Bienvenue dans la **Macaron Software Factory** — une plateforme multi-agents pour l'ingénierie logicielle autonome.

## Démarrage rapide (local)

```bash
# Cloner et installer
git clone https://github.com/macaron-software/software-factory.git
cd software-factory/platform
pip install -r requirements.txt

# Lancer (depuis le répertoire parent — JAMAIS --reload)
python -m uvicorn platform.server:app --port 8099 --ws none --log-level warning

# Ouvrir http://localhost:8099
```

## Docker

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup    # construit l'image Docker
make run      # démarre la plateforme sur le port 8090
```

## Premiers pas dans l'interface

1. **Compléter l'onboarding** — le premier écran guide la configuration initiale
2. **Créer un projet** — aller dans Projets → Nouveau projet
3. **Lancer une mission** — ouvrir le projet et envoyer un message au Lead Agent
4. **Observer la collaboration** — la vue session affiche la collaboration en temps réel via SSE

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `PLATFORM_LLM_PROVIDER` | `minimax` | Fournisseur LLM (minimax, azure-openai, azure-ai) |
| `PLATFORM_LLM_MODEL` | `MiniMax-M2.5` | Nom du modèle |
| `PLATFORM_PORT` | `8090` | Port HTTP |
| `DATABASE_URL` | *(aucun)* | URL PostgreSQL — `postgresql://user:pass@host/db` |
| `REDIS_URL` | *(aucun)* | URL Redis — `redis://host:6379/0` (optionnel, active le pub/sub) |
| `PLATFORM_MODE` | `full` | Mode de process : `full`, `factory` (headless) ou `ui` (web uniquement) |
| `PLATFORM_DB_PATH` | `data/platform.db` | Chemin SQLite (dev uniquement) |

## Points importants

- Ne **jamais** utiliser `--reload` avec uvicorn (conflit avec le module stdlib `platform`)
- Ne **jamais** faire `import platform` en top-level dans le package
- Toujours lancer depuis le répertoire parent : `python -m uvicorn platform.server:app ...`
- `--ws none` est obligatoire (la plateforme utilise SSE, pas WebSocket)
""",
    },
    {
        "slug": "architecture",
        "lang": "fr",
        "title": "Architecture",
        "content": """\
# Architecture

## Architecture de production (IHM/Factory découplées)

```
Navigateur
  |
  v
nginx (port 80/443)  --  commutation blue-green
  +-- /* --> platform-web-blue/green:8090  (IHM, redémarrable)

platform-web  --Redis sub-->  Redis pub/sub  <--Redis pub--  platform-factory
                                                                    |
                                                              PostgreSQL (partagé)
```

- **platform-factory** — moteur d'agents headless, ne redémarre jamais pour une modif UI
  - Missions, moteur de patterns, orchestrateur, watchdog, bus A2A
  - Publie les events sur le canal Redis `a2a:events`
- **platform-web** (blue/green) — IHM, redémarrable à chaud
  - Routes web, templates Jinja2, fichiers statiques, flux SSE
  - S'abonne à Redis `a2a:events` et relaie vers le navigateur via SSE
- **Redis** — pont pub/sub entre les conteneurs factory et web
- **PostgreSQL** — stockage persistant partagé
- **nginx** — commutation blue-green + terminaison TLS

`PLATFORM_MODE` contrôle les sous-systèmes démarrés :

| Mode | Factory (agents/missions) | Web (routes/IHM) | Listener Redis |
|------|--------------------------|-----------------|----------------|
| `full` | oui | oui | si REDIS_URL défini |
| `factory` | oui | non | publisher |
| `ui` | non | oui | subscriber |

## Stack technique

| Couche | Technologie |
|--------|-------------|
| **Frontend** | HTMX + templates Jinja2 + SSE |
| **Backend** | Python 3.12 + FastAPI + Uvicorn |
| **Base de données** | PostgreSQL (prod) / SQLite WAL (dev) |
| **Cache/Pub-sub** | Redis 7 (optionnel, fallback in-memory) |
| **LLM** | MiniMax M2.5, Azure OpenAI gpt-5-mini, Azure AI |
| **Outils** | Protocole MCP (fetch, memory, playwright, solaris) |
| **Déploiement** | Docker + docker-compose sur Azure VM + OVH VPS |
| **Reverse proxy** | nginx — blue-green + TLS + HSTS |
| **Auth** | JWT (cookies HttpOnly) |
| **i18n** | 18 langues via en-tête Accept-Language |

## Architecture des agents

```
Moteur de patterns (engine.py)
  |
  +-- Sequential  : A -> B -> C
  +-- Parallel    : A | B | C -> fusion
  +-- Hierarchical: Lead -> [Dev1, Dev2, QA]
  +-- Loop        : itère jusqu'au critère qualité
  +-- Router      : dispatch par type de contenu
  +-- Aggregator  : synthèse de sorties multiples
  +-- Adversarial : L0 (déterministe) + L1 (garde LLM)
  +-- Network     : débat / human-in-the-loop
```

Voir [Patterns d'orchestration](patterns) pour les détails.
""",
    },
    {
        "slug": "deployment",
        "lang": "fr",
        "title": "Guide de déploiement",
        "content": """\
# Guide de déploiement

## Environnements

| Environnement | URL | Serveur | Mode |
|---------------|-----|---------|------|
| Dev local | http://localhost:8099 | macOS, Python 3.12 | full |
| OVH Démo | http://54.36.183.124 | VPS Debian | full |
| Azure Prod | https://sf.macaron-software.com | Azure VM D4as_v5 4CPU/16GB | factory + web blue/green |

## Développement local

```bash
cd software-factory/platform
pip install -r requirements.txt

# Lancer (JAMAIS --reload, TOUJOURS --ws none, depuis le répertoire parent)
python -m uvicorn platform.server:app --port 8099 --ws none --log-level warning

# Tests
python -m pytest tests/ -v                  # tests unitaires + intégration
cd tests/e2e && npx playwright test         # tests E2E (82+)
```

## Azure Prod — Déploiement Blue-Green

Architecture : nginx -> commutation blue/green. La factory ne redémarre jamais pour une modif UI.

```
nginx:443 -> platform-web-blue:8090  (actif)
          -> platform-web-green:8090 (standby)
platform-factory:8091               (moteur headless toujours actif)
redis:6379                          (pont pub/sub)
postgres:5432                       (DB partagée)
```

### Déploiement complet (rsync + rebuild)

```bash
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete \\
  --exclude='__pycache__' --exclude='*.pyc' --exclude='data/' --exclude='.git' \\
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 \\
  "cd /opt/macaron && docker compose --env-file .env \\
   -f platform/deploy/docker-compose-vm.yml up -d --build --no-deps platform"
```

### Hotpatch (sans rebuild, sans arrêt de la factory)

```bash
tar cf /tmp/update.tar web/templates/ web/static/ web/routes/
scp -i "$SSH_KEY" /tmp/update.tar azureadmin@4.233.64.30:/tmp/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 \\
  "docker cp /tmp/update.tar deploy-platform-1:/tmp/ && \\
   docker exec deploy-platform-1 bash -c 'cd /app/macaron_platform && tar xf /tmp/update.tar' && \\
   docker restart deploy-platform-1"
```

## OVH Démo

```bash
ssh debian@54.36.183.124
cd /opt/software-factory
docker compose pull && docker compose up -d
```

CI/CD : GitHub Actions `.github/workflows/deploy-demo.yml`
Secrets : `OVH_SSH_KEY`, `OVH_IP`

## CI/CD

| Pipeline | Déclencheur | Actions |
|----------|-------------|---------|
| `.github/workflows/deploy-demo.yml` | push sur `main` | rsync + docker restart sur OVH |
| `.gitlab-ci.yml` | push sur `main` | rsync + docker build sur Azure |

Déploiement intelligent : si le diff est limité à `web/templates/`, `web/static/`, `web/routes/`, la factory n'est PAS redémarrée.
""",
    },
    {
        "slug": "resilience",
        "lang": "fr",
        "title": "Résilience & Stabilité",
        "content": """\
# Résilience & Stabilité

## Pool de connexions PostgreSQL

La plateforme utilise `psycopg_pool.ConnectionPool` (pool synchrone psycopg3) avec un serveur FastAPI asyncio.

| Conteneur | Taille du pool | Notes |
|-----------|---------------|-------|
| platform-factory | 20 | Exécute missions, watchdog, auto-resume, auto-heal en parallèle |
| platform-web (blue/green) | 5 | Lecture dominante, charge plus légère |

### Prévention des fuites de connexions

Toutes les connexions DB DOIVENT suivre ce modèle :

```python
db = None
try:
    db = get_db()
    # ... travail ...
finally:
    if db:
        db.close()   # retourne la connexion au pool via putconn()
```

Un bloc `finally` manquant = connexion jamais retournée en cas d'exception.
`PgConnectionWrapper` dispose d'un filet de sécurité GC via `__del__`, mais le GC est non-déterministe.

### Symptômes d'épuisement du pool

```
PoolTimeout: couldn't get a connection after 15.00 sec
```

Vérifier avec : `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`

## Failover nginx Blue-Green

L'upstream nginx utilise une commutation blue-green avec health check :

```nginx
upstream platform_web {
    server platform-blue:8090  max_fails=3 fail_timeout=10s;
    server platform-green:8090 max_fails=3 fail_timeout=10s backup;
}
```

Endpoint de santé : `GET /health` retourne `{"status": "ok"}` avec HTTP 200.

## Découplage IHM / Factory

**Problème :** Redémarrer le conteneur web pour déployer une modif UI interrompait les missions en cours.

**Solution :** `PLATFORM_MODE` divise le processus :

- `factory` : démarre agents/missions/orchestrateur, publie sur Redis, pas de routes HTTP
- `ui` : démarre routes web/templates/SSE, s'abonne à Redis pour les events, pas d'exécution d'agents
- `full` : les deux (défaut, pour dev ou déploiements simples)

Canal Redis pub/sub : `a2a:events` — factory publie, web s'abonne et relaie vers le SSE navigateur.
Fallback : si `REDIS_URL` n'est pas défini, bascule sur le bus in-memory (mode `full` uniquement).

## Suite de tests de stabilité

Emplacement : `platform/tests/test_stability.py`. Lancer avec :

```bash
STABILITY_TESTS=1 \\
STABILITY_AZ_HOST=https://sf.macaron-software.com \\
STABILITY_OVH_HOST=http://54.36.183.124 \\
python -m pytest tests/test_stability.py -v -m stability
```

| Test | Ce qu'il vérifie |
|------|-----------------|
| `test_health_az/ovh` | `/health` retourne 200 |
| `test_latency_p99` | p99 < 3s sur 20 requêtes |
| `test_concurrent_10/50` | 10/50 requêtes concurrentes, < 5% d'erreurs |
| `test_rate_limit` | 429 retourné quand la limite est dépassée |
| `test_pages_smoke` | 8 pages clés retournent 200 |
| `test_sse_connect` | Le flux SSE se connecte et envoie le keepalive `:ping` |
| `test_disk_memory` | disque < 90%, mémoire < 90% |
| `test_hot_restart` | redémarrage du conteneur, service de retour en < 30s |
| `test_nginx_failover` | arrêt blue, nginx bascule sur green, retour en < 10s |
| `test_cold_restart` | redémarrage complet du serveur, service de retour en < 120s |
| `test_chaos_pause_resume` | docker pause/unpause du conteneur mission |

## Auto-Heal

`ops/auto_heal.py` surveille la santé de la plateforme toutes les 60s et crée des incidents P1/P2 pour :

- Échecs de fournisseur LLM (bascule automatique de provider)
- Épuisement du pool PG (log d'alerte, déclenchement d'incident)
- Mémoire du conteneur > 90% (crée un incident P0)

Les incidents sont visibles dans `/toolbox` sous l'onglet Incidents.
""",
    },
    {
        "slug": "user-guide",
        "lang": "fr",
        "title": "Guide utilisateur",
        "content": """\
# Guide utilisateur

## Tableau de bord

Personnalisé par perspective : **DSI** (portfolio), **Produit** (backlog), **Engineering** (sessions), **Scrum Master** (vélocité).

## Projets

1. Aller dans **Projets** → **Nouveau projet**
2. Renseigner le nom, la description, choisir une couleur
3. Choisir le Lead Agent, configurer Git (optionnel)
4. Utiliser le chat pour envoyer des missions

## Missions

- **Flux de statut** : planning → active → review → completed
- Chaque mission a des runs (tentatives) avec des phases (étapes agents)

## Sessions

Collaboration d'agents en direct avec streaming SSE temps réel, code couleur par rôle.

## Backlog & Idéation

- **Backlog** : features priorisées par WSJF
- **Idéation** : brainstorming multi-agents — taper un prompt, les agents collaborent

## Métriques

| Onglet | Contenu |
|--------|---------|
| **DORA** | Fréquence de déploiement, lead time, taux d'échec, MTTR |
| **Qualité** | Scores de qualité de code, couverture de tests, sécurité |
| **Analytics** | Stats missions, performance des agents, santé du système |
| **Monitoring** | CPU, mémoire, latence des requêtes en temps réel |
| **Pipeline** | Performance des pipelines CI/CD |

## Boîte à outils

| Onglet | Contenu |
|--------|---------|
| **Skills** | Bibliothèque de compétences des agents |
| **Memory** | Navigateur de mémoire persistante |
| **MCPs** | Gestion des serveurs MCP |
| **API** | Documentation Swagger interactive |
| **CLI** | Terminal web |
| **Design System** | Référence des composants UI |
| **Wiki** | Cette documentation |

## Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl+K` | Recherche rapide |
| `Ctrl+Enter` | Envoyer un message |
| `Esc` | Fermer un modal |
""",
    },
    # ── Annotation Studio ─────────────────────────────────────────────────
    {
        "slug": "annotation-studio-safe-traceability",
        "title": "Annotation Studio — Feedback Visuel & Traçabilité SAFe",
        "category": "Guide",
        "icon": "✏️",
        "sort_order": 59,
        "content": """\
# Annotation Studio — Feedback Visuel & Traçabilité SAFe

## Vue d'ensemble

L'**Annotation Studio** est un layer de feedback visuel intégré à la Software Factory.
Il permet à n'importe quel utilisateur (PM, designer, développeur, QA, stakeholder) d'annoter
directement les pages de la plateforme sans quitter l'interface.

Il s'auto-applique à la SF elle-même via le projet réservé `_sf` (rétro-ingénierie SAFe complète).

---

## Activation

Deux boutons sont disponibles dans la topbar de chaque page :

| Icône | Action | Résultat |
|-------|--------|----------|
| 👤 Persona | Barre de traçabilité SAFe | Affiche Programme → Epic → Feature → Stories pour la page courante |
| ⊞ Wireframe | Mode wireframe | Remplace le contenu par un squelette/shimmer pour inspection UX |

### Mode Annotation

Cliquez sur **✏️ Annoter** (bas-droite) pour activer le mode annotation :
- Tous les clics sont interceptés (navigation bloquée)
- Une bannière bleue confirme que le mode est actif
- Cliquez sur n'importe quel élément → popover de saisie

---

## Types d'annotations

| Type | Usage |
|------|-------|
| Bug 🐛 | Défaut fonctionnel, comportement incorrect |
| Commentaire 💬 | Note, question, suggestion libre |
| Feature ✨ | Demande d'une nouvelle fonctionnalité |
| Design 🎨 | Problème visuel, alignement, couleur |
| Texte 📝 | Correction de copie, traduction |

Chaque annotation capture : sélecteur CSS, texte visible, styles computed, URL + timestamp.

---

## Barre de traçabilité SAFe

La barre affiche la hiérarchie SAFe de la page courante :

```
┌─────────────────┬──────────────────┬──────────────────┬──────────────────────┐
│   Programme     │      Epic        │     Feature      │   Stories / Tasks    │
│ Software Factory│ Backlog & Planning│  Product Backlog │ · Prioriser stories  │
│                 │                  │  status: active  │ · Affiner le backlog │
│                 │                  │                  │ · Filtrer par epic   │
└─────────────────┴──────────────────┴──────────────────┴──────────────────────┘
  Persona: Product Owner  |  /backlog  |  ✏️ Annoter cette page  |  Backlog SAFe
```

---

## Rétro-ingénierie — Mapping SAFe de la SF

Script : `platform/scripts/retro_sf_safe.py`

La hiérarchie SAFe de la SF couvre **49 écrans** répartis en **8 epics** :

| Epic | Features | Pages couvertes |
|------|----------|-----------------|
| Orchestration & Missions | 4 | /, /cockpit, /mission-control, /art, /live |
| SAFe Backlog & Planning | 4 | /portfolio, /pi, /backlog, /projects |
| Agent Factory | 4 | /agents, /skills, /workflows, /patterns |
| Monitoring & Quality | 5 | /monitoring, /analytics, /quality, /memory, /ops |
| Product Discovery | 3 | /ideation, /product-line, /generate |
| Integrations & Marketplace | 3 | /marketplace, /mcps, /metier |
| Platform Administration | 4 | /settings, /admin/users, /org, /notifications |
| UX & Annotation Studio | 2 | /annotate, /design-system |

**Total** : 8 epics · 29 features · 91 user stories · 49 écrans

Pour ré-exécuter la rétro-ingénierie :
```bash
python3 platform/scripts/retro_sf_safe.py
```

---

## Mode Wireframe

Le mode wireframe transforme les pages en squelette UX :

- **TreeWalker** : parcourt les nœuds texte feuilles → `.sf-skel-bar` (shimmer)
- **Blocs** : images, inputs, iframes → `.sf-skel-block`
- **Périmètre** : `.main-area` uniquement (sidebar/topbar inchangées)
- **Restauration** : `removeSkeleton()` restaure les nœuds DOM originaux
- **Thème** : shimmer utilise `var(--bg-secondary/tertiary/border)` → light/dark compatible

---

## API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/projects/{id}/annotations` | GET | Liste des annotations |
| `/api/projects/{id}/annotations` | POST | Créer une annotation |
| `/api/projects/{id}/annotations/{ann_id}` | PATCH | Mettre à jour |
| `/api/projects/{id}/annotations/{ann_id}` | DELETE | Supprimer |
| `/api/projects/{id}/annotations/export` | GET | Export JSON/CSV |
| `/api/projects/{id}/screens/{screen_id}/traceability` | GET | SAFe traceability |
| `/api/projects/{id}/screens/{screen_id}` | PATCH | Lier écran ↔ feature |

---

## Architecture technique

```
sf-annotate.js (chargé sur toutes les pages via base.html)
├── buildToolbar()       — barre flottante bas-droite (CSS vars)
├── toggleAnnotate()     — active/désactive le mode + bannière
├── captureClick()       — intercepte les clics (capture phase)
├── showPopover()        — popover de saisie (CSS vars, thème-adaptatif)
├── saveAnnotation()     — POST /api/projects/_sf/annotations
└── renderMarkers()      — affiche les markers sur la page

base.html
├── toggleSpecBar()      — barre SAFe (Programme|Epic|Feature|Stories)
├── loadSpecData()       — fetch traceability API → populate cards
└── toggleWireframeMode() — TreeWalker skeleton + CSS vars shimmer
```

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `platform/web/static/sf-annotate.js` | Toolbar, popover, markers, API calls |
| `platform/web/templates/base.html` | SAFe bar, wireframe mode, topbar buttons |
| `platform/web/templates/annotate.html` | Studio standalone `/annotate/{project_id}` |
| `platform/web/routes/api/screens.py` | Endpoints annotation + traceability |
| `platform/scripts/retro_sf_safe.py` | Rétro-ingénierie SAFe de la SF |
| `platform/db/migrations.py` | Table `epics` (programme_id, name, description) |
""",
    },
]
