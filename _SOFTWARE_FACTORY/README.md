# Software Factory

> Multi-agent AI platform for autonomous software development — 145 agents, SAFe methodology, full TDD pipeline.

## Overview

Macaron is a **multi-agent orchestration platform** that plans, develops, tests, and deploys software autonomously. It combines:

- **94+ AI agents** (Product Manager, Architect, Dev, QA, Security, UX, DevOps...)
- **SAFe-aligned workflow**: Epics → Features → User Stories → Sprints → Code
- **12 orchestration patterns**: solo, sequential, parallel, hierarchical, network, loop...
- **Multi-LLM**: Claude, GPT, MiniMax, GLM — with automatic fallback chains
- **Full TDD pipeline**: Brain analysis → FRACTAL decomposition → TDD workers → Adversarial review → Deploy

## Quick Start

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

## Architecture

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

## Three Interfaces

### 1. Web Dashboard (HTMX + SSE)

The main UI at `http://localhost:8090`:
- Real-time multi-agent conversations with SSE streaming
- PI Board, mission lifecycle, sprint planning
- Agent management, monitoring, incident dashboard

### 2. CLI (`sf`)

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

### 3. REST API + Swagger

94 API endpoints auto-documented at `/docs` (Swagger UI):

```bash
# Examples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl http://localhost:8090/api/stories
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: `http://localhost:8090/docs`

### 4. MCP Server

23 MCP tools for AI agent integration (port 9501):

```bash
# Start MCP server
python3 -m platform.mcp_platform.server

# Tools available:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Agent Organization

| Team | Agents | Role |
|------|--------|------|
| Product | Product Manager, Business Analyst, PO | SAFe planning, WSJF |
| Architecture | Solution Architect, Tech Lead | Architecture decisions |
| Development | Dev agents (per stack) | TDD implementation |
| Quality | QA, Security Engineer | Testing, security audit |
| Design | UX Designer | User experience |
| DevOps | DevOps, SRE | CI/CD, monitoring |
| Management | Scrum Master, RTE | Ceremonies, facilitation |

## Project Configuration

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

## Factory CLI (TDD Engine)

```bash
source setup_env.sh
factory <project> brain run --mode vision    # Deep analysis
factory <project> cycle start -w 5 -b 20    # Batch TDD workers
factory status --all                         # All projects
```

## Directory Structure

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
├── projects/*.yaml          # Per-project configs
├── tests/                   # 136+ automated tests
└── data/                    # SQLite databases
```

## Tests

```bash
python3 -m pytest tests/ -v                  # All tests (136+)
python3 -m pytest tests/test_cli.py -v       # CLI tests (53)
python3 -m pytest tests/test_mcp.py -v       # MCP tests (20)
python3 -m pytest tests/test_platform_api.py # API tests (48)
```

## Requirements

- Python 3.10+
- API keys (any combination):
  - Anthropic (Claude) — `~/.config/factory/anthropic.key`
  - MiniMax — `~/.config/factory/minimax.key`
  - OpenAI — `~/.config/factory/openai.key`

## License

MIT
