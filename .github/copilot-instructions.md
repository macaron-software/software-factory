# Macaron Software — Copilot Instructions

## Repository Structure

This is a monorepo containing a **multi-agent Software Factory** and a **web-based Agent Platform**:

```
_FACTORY_CORE/          # Shared Python utils (subprocess, logging, LLM client, daemon)
_SOFTWARE_FACTORY/      # Software Factory — TDD automation engine
  ├── cli/factory.py    # CLI entry point (`factory <project> <command>`)
  ├── core/             # Brain, TDD workers, adversarial review, FRACTAL decomposition
  ├── platform/         # Macaron Agent Platform — FastAPI web app
  │   ├── server.py     # App factory (create_app), port 8090
  │   ├── web/routes.py # All HTTP routes (~8600 lines)
  │   ├── web/templates/# Jinja2 + HTMX templates
  │   ├── a2a/          # Agent-to-Agent messaging (bus, negotiation, veto)
  │   ├── agents/       # Agent loop, executor, store (94 agents)
  │   ├── patterns/     # 12 orchestration patterns (solo, network, hierarchical...)
  │   ├── missions/     # SAFe-aligned mission lifecycle
  │   ├── llm/          # Multi-provider LLM client (Anthropic, MiniMax, GLM, Azure)
  │   └── tools/        # Agent tools (code, git, deploy, memory, security...)
  ├── projects/*.yaml   # Per-project configs (ppz, psy, veligo, yolonow, fervenza, solaris)
  ├── skills/*.md       # Specialized prompts auto-loaded by domain
  └── data/             # SQLite DBs (factory.db, platform.db)
_MIGRATION_FACTORY/     # Code migration engine (Angular 16→17, ISO 100%)
```

## Build & Run Commands

### Software Factory CLI
```bash
cd _SOFTWARE_FACTORY
source setup_env.sh                          # Sets PYTHONPATH
factory <project> brain run --mode vision    # Analyze project (vision/fix/security/refactor)
factory <project> cycle start -w 5 -b 20    # Start batch TDD workers
factory <project> cycle stop
factory status --all                         # All projects status
```

### Macaron Agent Platform
```bash
cd _SOFTWARE_FACTORY
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
```
- **Never** use `--reload` (conflicts with Python stdlib `platform` module)
- **Always** pass `--ws none` (SSE-only, no WebSocket)
- DB lives at `data/platform.db` (parent of `platform/`), not inside `platform/data/`

### Tests
```bash
# Core unit tests
cd _SOFTWARE_FACTORY
python3 -m pytest tests/test_fractal_decomposition.py -v  # Single test file
python3 -m pytest tests/ -v                                # All core tests

# Platform E2E (Playwright)
cd _SOFTWARE_FACTORY/platform/tests/e2e
npx playwright test                          # All E2E
npx playwright test ideation.spec.ts         # Single spec
```

## Architecture — Key Concepts

### Factory Pipeline
```
Brain (Opus) → FRACTAL decompose → TDD Workers (parallel) → Adversarial Review → Build → Deploy
```
- **Brain** (`core/brain.py`): Deep recursive analysis, generates tasks with WSJF priority
- **FRACTAL** (`core/fractal.py`): Splits tasks into 3 concerns: feature → guards → failures
- **Cycle Worker** (`core/cycle_worker.py`): Batch TDD—N workers write code, one build for all
- **Adversarial** (`core/adversarial.py`): Multi-LLM cascaded review (L0 fast → L1 code → L2 architecture)
- **Task Store** (`core/task_store.py`): SQLite with zlib compression, status: pending → locked → tdd_in_progress → code_written → build → commit → deploy

### Agent Platform
- **FastAPI + HTMX + SSE** — zero JS build step, server-rendered with real-time streaming
- **Dual SSE system**: `_push_sse()` pushes to both internal queues AND `bus._sse_listeners`
- **Pattern Engine** (`patterns/engine.py`): Runs multi-agent orchestrations (solo, sequential, parallel, hierarchical, network, loop, router, aggregator, human-in-the-loop)
- **AgentLoop** (`agents/loop.py`): Autonomous asyncio.Task per agent — inbox → think → act → route
- **MessageBus** (`a2a/bus.py`): Async queues per-agent, 11 message types, priority routing
- **SAFe vocabulary**: Epic = Mission, Feature, Story, Task; PI = MissionRun; Ceremony = Session

### Project Configs (`projects/*.yaml`)
Each managed project declares its root path, CLI commands, brain phase, build queue, and adversarial settings. Projects: ppz (Rust+TS SaaS), psy (SvelteKit), veligo (SvelteKit+multi-tenant), yolonow (mobile), fervenza (Python), solaris (design system).

## Conventions

### Zero Skip Policy
Never use `test.skip()`, `@ts-ignore`, `#[ignore]`, or `--skip-*` flags. Fix the problem instead.

### Python
- Python 3.10+. All async code uses `asyncio`.
- PYTHONPATH must include the monorepo root for cross-directory imports (`from _FACTORY_CORE.log import ...`).
- Process cleanup: always use `start_new_session=True` + `os.killpg()` for subprocess timeouts.
- LLM fallback chain: MiniMax-M2.5 → MiniMax-M2.1 → GLM-4.7-free.

### Platform Web
- Templates use Jinja2 + HTMX. Dark purple/indigo theme with CSS vars (`--bg-primary:#0f0d1a`, `--purple:#7c3aed`).
- Agent data passed to templates as dicts — access `a["name"]` not `a.name`.
- All routes are in `platform/web/routes.py`. SSE endpoints in `platform/web/ws.py`.
- `init_db()` handles migrations idempotently (CREATE IF NOT EXISTS + ALTER TABLE safe). **Never delete `data/platform.db`** — it contains persistent user data.

### API Keys
Loaded from `~/.config/factory/*.key` files. Never set `*_API_KEY=dummy` env vars — it overrides real keys.
