# Software Factory — Copilot Instructions

## Critical: The `platform` Import Trap

The `platform/` directory shadows Python's stdlib `platform` module. **Never** write `import platform` at the top level — it will import the project directory, not stdlib.

```python
# WRONG — imports the project directory
import platform

# CORRECT — always use explicit submodule imports
from platform.db.adapter import get_db
from platform.agents.executor import AgentExecutor
```

The same issue affects `uvicorn --reload` (it re-imports and hits the shadow). Always run with `--ws none` and without `--reload`.

## Build, Test, Lint

```bash
# Dev server (no Docker)
PYTHONPATH=$(pwd) uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning

# Docker
make run              # docker compose up -d --build → http://localhost:8090
make logs             # docker compose logs -f platform

# Lint (syntax errors — HARD gate in CI)
ruff check platform/ --select E9

# Complexity analysis (SOFT gate — CC > 10 = error, LOC > 500 = error, MI < 10 = error)
python scripts/complexity_gate.py platform/

# Tests — require a running PostgreSQL (CI uses services: postgres:16)
pytest tests/test_platform_api.py -v                    # API tests
pytest tests/test_cache.py tests/test_auto_heal.py -v   # Unit tests
pytest tests/test_demo.py -v                            # Demo mode tests

# Single test file
pytest tests/test_engine.py -v

# Single test function
pytest tests/test_platform_api.py::test_health -v

# Full Makefile test suite
make test
```

## Architecture

Multi-agent orchestration platform (SAFe methodology). ~221 AI agents, 26 orchestration patterns, 69 YAML workflows. Python 3.11 + FastAPI + Jinja2 + HTMX + SSE. PostgreSQL 16 (62 tables) + Redis 7.

### Core Layers

- **`platform/server.py`** — FastAPI app, lifespan, auth middleware, 8 background tasks
- **`platform/agents/`** — Agent engine: executor, store (~221 agents), adversarial review (L0 deterministic + L1 LLM), tool runner (134 tool modules)
- **`platform/patterns/engine.py`** — 26 orchestration topologies (solo, sequential, parallel, hierarchical, loop, network, router, aggregator, wave, tournament, voting, etc.)
- **`platform/workflows/`** — Workflow store with PM v2, 32 phase templates, 69 YAML definitions in `defs/`
- **`platform/services/`** — Epic orchestrator (with on_complete chaining), auto_resume, PM checkpoint, notifications
- **`platform/a2a/`** — Agent-to-agent bus, veto protocol, negotiation
- **`platform/llm/client.py`** — 5 LLM providers: azure-ai, azure-openai, nvidia, minimax, local-mlx
- **`platform/db/`** — DB adapter (PostgreSQL primary, SQLite fallback), schema (62 tables), migrations, multi-tenant
- **`platform/web/routes/`** — HTMX routes (missions, agents, projects, workflows, sessions, auth)
- **`platform/tools/`** — 54 tool modules (code, git, deploy, build, web, security, memory, MCP, tracing, AST, lint, LSP, design system)
- **`platform/ops/`** — 17 operational modules (auto_heal, traceability_scheduler, knowledge_scheduler)

### Supporting Directories

- **`skills/`** — 139 YAML skill definitions injected into agent prompts
- **`workflows/defs/`** — 69 YAML workflow definitions
- **`projects/`** — Per-project config (e.g., `sienna.yaml`, `factory.yaml`) with git_url

### Data Flow

Epic → Workflow (YAML phases) → `epic_runs` (PG) → PM LLM decides: next | loop | done | skip | phase(dynamic). Each phase composes pattern + team + gate + feedback → `PatternDef` + `WorkflowPhase` → `_phase_queue`.

## Key Conventions

### Database

- **PostgreSQL is the live database.** `data/platform.db` is a stale SQLite fallback — never query it for live data.
- Use `platform/db/adapter.py` for all DB access — it handles PG vs SQLite transparently.
- PG advisory locks are connection-scoped → one dedicated connection per mission.

### UI / Frontend

- **SSE only** — no WebSockets anywhere. Pass `--ws none` to uvicorn.
- **HTMX partial swaps** — routes return HTML fragments, not JSON. Pattern: `hx-get="/partial/X" hx-trigger="load"`.
- **Skeleton loading** — CSS class `.sk` with shimmer animation. Use macros from `partials/skeleton.html`. Tiered: L0 skeleton (instant) → L1 summary (fast) → L2 full detail (on-demand).
- **Feather SVG icons only** — no emoji, no icon fonts. Stroke with `round` linecap, 2px.
- **CSS custom properties** — all colors, spacing, typography via design tokens. Never hardcode hex colors or use inline styles.
- **Dark-first** — default theme is dark. Support light + dark + high-contrast via `[data-theme]`.
- **No gradient backgrounds.**
- i18n via `{{ t('key') }}` — locales in `platform/i18n/locales/*.json`. Active: en, fr.

### Code Style

- PEP 8 enforced by `ruff`. Type hints required for public APIs.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- All source files need traceability: `# Ref: FEAT-xxx` (Python), `<!-- Ref: feat-* -->` (HTML), `// Ref: feat-*` (TS/JS).
- Agent statuses are `PENDING | RUNNING | COMPLETED | VETOED | FAILED` — there is no `DONE` status.

### Data Integrity

- **No mocks, fakes, stubs, or dummy data.** Tests use real DB (test schema), real LLM calls, real file I/O.
- If an external service is unavailable, skip the test with a reason — don't fake it.
- No `return {}` / `return None` / `pass` as implementation — write real logic or `raise NotImplementedError`.
- No placeholder `TODO` implementations or fallback empty returns.

### LLM Configuration

LLM model configuration is frozen — do not change models. Current providers: MiniMax M2.5, Azure OpenAI (gpt-5-mini, gpt-5.2, gpt-5.2-codex), Azure AI (gpt-5.2), NVIDIA (Kimi-K2), local MLX. API keys come from Infisical or `.env` — never set dummy values.

### Security

- Secrets managed via Infisical — never commit API keys.
- Auth: JWT (access 15min + refresh 7d cookie) + bcrypt. Rate limiting per endpoint.
- CI actions are pinned to SHA (not mutable tags) to prevent supply-chain attacks.
- Prompt injection guard in `platform/security/prompt_guard.py`.

## Traceability SQLite DB (session-scoped, live data)

UDID scheme: `FT-SF-NNN` (features) · `US-SF-NNN` (stories) · `AC-SF-NNN` (acceptance) · `TU-SF-NNN` / `TE-SF-NNN` (tests) · `CO-{CAT}-NNN` (concepts)

### Tables & Counts
| Table | Count | Schema |
|-------|-------|--------|
| `trace_features` | 49 | id,name,desc,priority,status,persona_id,soc2,iso27001 |
| `trace_stories` | 57 | id,feature_id(FK),title,desc,story_points,status,acceptance_gherkin |
| `trace_acceptance` | 38 | id,story_id(FK),criterion,gherkin,status |
| `trace_tests_unit` | 21 | id,file_path,test_name,ac_id(FK),story_id,status |
| `trace_tests_e2e` | 10 | id,file_path,test_name,story_id,ihm_id,persona_id,status |
| `trace_links` | 61 | source_type,source_id,target_type,target_id,link_type |
| `concepts` | 140 | udid,name,category,source_file,description |
| `feature_tests` | 30 | id,feature,test_type,status,details |

### Coverage
- 49/49 features → stories (100%)
- 33/57 stories → ACs (58%)
- 38/38 ACs pass · 21/21 unit tests pass · 10/10 E2E pass
- 175 unique UDIDs · 0 orphans · 0 broken links

### GossipSub (platform/ac/gossip.py)
Cross-project mutation broadcasting: 4 types (skill_variant, instinct, genome, meta_insight)
Producers: skill_thompson→broadcast_skill_win · instinct→broadcast_instinct_promotion
Consumer: get_recent_gossip for cherry-picking · record_adoption for tracking
DB: gossip_ledger (auto-created) · API: /api/cockpit/summary includes gossip stats

## Gotchas

- **Container path**: inside Docker it's `/app/macaron_platform/`, not `/app/platform/`
- **SSE testing**: use `curl --max-time` — urllib will block forever on SSE streams
- **Epic orchestration**: prompt building happens in `_build_phase_prompt()`, not in `workflows/store.py`
- **Epic chat**: calls `_auto_create_planning_run()` if no active run exists
