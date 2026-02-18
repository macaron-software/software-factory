# Software Factory & Macaron Agent Platform

This repo contains two interrelated systems:

1. **Software Factory** (`core/`, `cli/`) — CLI-based multi-project build/deploy pipeline with TDD, adversarial review, and FRACTAL task decomposition.
2. **Macaron Agent Platform** (`platform/`) — Web-based multi-agent orchestration platform (FastAPI + HTMX + SSE + SQLite) that emulates a DSI with 70+ agent personas collaborating through 8 agentic patterns.

## ⚠️ Critical Rules

- **NEVER `rm -f data/platform.db`** — The DB is persistent. It contains user missions, sessions, messages, and memory. `init_db()` handles migrations idempotently.
- **NEVER set `MINIMAX_API_KEY=dummy`** or any `*_API_KEY=dummy` — API keys load from `~/.config/factory/*.key` files automatically. Dummy env vars override real keys.
- **NEVER use `--reload`** with uvicorn — conflicts with Python's stdlib `platform` module.
- **NEVER use `test.skip()`, `@ts-ignore`, `#[ignore]`** — Fix the problem, don't skip it.

## Build, Test, Run

```bash
# Start the platform (from _SOFTWARE_FACTORY/ root)
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning

# E2E tests (Playwright, requires server running on port 8099)
cd platform/tests/e2e && npx playwright test                  # all 23 tests
cd platform/tests/e2e && npx playwright test ideation.spec.ts  # single suite
cd platform/tests/e2e && npx playwright test ideation.spec.ts:10  # single test

# Unit tests (factory core)
pytest tests/ -x -q
pytest tests/test_fractal_decomposition.py -x  # single file

# Factory CLI
factory <project> brain run --mode vision
factory <project> cycle start -w 5 -b 20 -t 30
```

## Platform Architecture

```
Request → routes.py (5400 lines, 125 endpoints)
  ↓ Jinja2 templates + HTMX (no frontend build step)
  ↓
Sessions (runner.py) → _push_sse() → dual SSE delivery (queues + bus)
  ↓
Patterns (engine.py) → 8 patterns: solo, sequential, parallel, loop,
                        hierarchical, network, router, aggregator
  ↓
Agents (executor.py) → tool-calling loop (max 5 rounds)
  ↓ tools: code_write, code_edit, git_commit, docker_build, deploy_azure, etc.
  ↓
LLM (client.py) → multi-provider fallback: MiniMax → Azure → GLM → NVIDIA
  ↓ keys from ~/.config/factory/*.key (env var → key file fallback)
  ↓
A2A (bus.py) → inter-agent messaging, veto hierarchy, negotiation
  ↓
Memory (manager.py) → 4 layers: session → pattern → project → global (FTS5)
  ↓
SQLite (schema.sql) → ~20 tables, WAL mode, FTS5 search
```

### Agent Hierarchy (tools access depends on rank)

| Rank | Role | Tools | Example |
|------|------|-------|---------|
| 0-10 | C-Level (DSI, CPO, CTO) | Read-only (code_read, code_search) | Philippe Laurent |
| 20 | Leads/Managers | Review tools + memory | Lead Dev, Architecte |
| 30 | Specialists | Full code tools | Sécurité, DevOps, QA Lead |
| 40 | Workers | Full code + build + deploy | Dev Frontend, Dev Backend |

`tools_enabled = bool(project_id)` — agents only get tools when a mission has a workspace.

### Mission Lifecycle

When a mission starts via `/api/missions/start`:
1. Creates `data/workspaces/{mission_id}/` with `git init`
2. Passes `workspace_path` through `PatternRun → ExecutionContext → agent tools`
3. Phase prompts instruct dev agents to USE tools (code_write, git_commit)
4. Post-phase hooks: auto git commit after dev sprint, docker build after CI/CD, file listing after deploy

### Dual SSE System

Two SSE pathways coexist — both must deliver to the frontend:
- `_push_sse(session_id, dict)` → session queues AND `bus._sse_listeners`
- `bus.publish(A2AMessage)` → `bus._sse_listeners` via `_notify_sse()`
- SSE endpoint `/sse/session/{id}` → filters by `session_id`

If events aren't reaching the frontend, check that `_push_sse()` broadcasts to both systems.

## Key Conventions

### Data Layer
- Domain objects: Pydantic `BaseModel` in `models.py` (MissionRun, PhaseRun, etc.)
- Agent definitions: `@dataclass AgentDef` in `agents/store.py`
- Store singletons: `get_agent_store()`, `get_session_store()`, `get_mission_run_store()`, etc.
- Raw `sqlite3` via `get_db()` — no ORM. Row→object via `_row_to_*()` helpers.

### DB Migrations
- Schema in `platform/db/schema.sql` (CREATE IF NOT EXISTS)
- Migrations in `platform/db/migrations.py` (`_migrate()` uses PRAGMA table_info to add columns safely)
- DB path: `data/platform.db` (at `_SOFTWARE_FACTORY/` root, NOT `platform/data/`)

### Agent Definitions
- 52 YAML files in `platform/skills/definitions/*.yaml`
- Each defines: id, name, avatar, role, persona, system_prompt, skills, tools, permissions, hierarchy_rank
- Seeded on startup via `get_agent_store().seed_builtins()`

### Templates & CSS
- Jinja2 templates extend `base.html` (blocks: `topbar_actions`, `content`)
- Dark purple theme: `--bg-primary: #0f0a1a`, `--purple: #a855f7`
- HTMX: `hx-get`/`hx-post`, `hx-target`, `hx-swap`, `hx-trigger`
- Markdown filter: `{{ content | markdown | safe }}`
- View modes: card/card-simple/list/list-compact via `partials/view_switcher.html`
- `_agent_map_for_template(agents)` returns dicts — access `a["name"]` not `a.name`

### Imports
- Always relative within `platform/`: `from ..db.migrations import get_db`
- Never `import platform` at top level (shadows stdlib)

### Pattern Engine
- `run_pattern(PatternDef, session_id, task, project_id, project_path)` in `engine.py`
- Role-based protocols injected into agent prompts: `_EXEC_PROTOCOL` (rank ≥ 40), `_QA_PROTOCOL`, `_REVIEW_PROTOCOL`, `_RESEARCH_PROTOCOL`
- Multi-pattern graph edges: 8 color-coded interaction types (hierarchical, network, sequential, loop, parallel, gate, aggregation, routing)

## Factory Core Architecture

```
Brain (core/brain.py) — Opus orchestrator, generates WSJF-prioritized tasks
  ↓
FRACTAL (core/fractal.py) — L1: 3 concerns (feature/guards/failures), L2: KISS atomic
  ↓
Cycle Worker (core/cycle_worker.py) — batch TDD→BUILD→DEPLOY (preferred over wiggum)
  ↓
Adversarial (core/adversarial.py) — 100% LLM review (MiniMax), never regex
  ↓
Deploy (core/wiggum_deploy.py) — subprocess.run for build/test, NOT LLM
```

Projects: ppz, psy, veligo, yolonow, fervenza, solaris, factory (self)
Config: `projects/*.yaml` — fractal, adversarial, build_queue, deploy settings
Tasks DB: `data/factory.db` (SQLite) — status flow: pending→locked→tdd_in_progress→code_written→build→commit→deploy
