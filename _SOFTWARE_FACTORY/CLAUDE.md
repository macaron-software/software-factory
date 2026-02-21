# Macaron Software — Project Context

## REPO STRUCTURE
```
_FACTORY_CORE/          # Shared utils (subprocess, logging, LLM, daemon)
_SOFTWARE_FACTORY/      # Software Factory (SF) — TDD automation + Agent Platform
  ├── cli/factory.py    # CLI: factory <project> <command>
  ├── core/             # Brain, TDD workers, adversarial, FRACTAL
  ├── platform/         # Macaron Agent Platform — FastAPI web app
  │   ├── server.py     # App factory, port 8090
  │   ├── web/routes/   # HTTP routes package (10 sub-modules, was 8800 LOC monolith)
  │   ├── a2a/          # Agent-to-Agent messaging (bus, negotiation, veto)
  │   ├── agents/       # Loop, executor, store (133 agents)
  │   ├── patterns/     # 8 orchestration patterns
  │   ├── missions/     # SAFe mission lifecycle
  │   ├── llm/          # Multi-provider LLM client
  │   ├── tools/        # Agent tools (code, git, deploy, memory, security, browser)
  │   └── deploy/       # Dockerfile + docker-compose (Azure VM)
  ├── projects/*.yaml   # Per-project configs
  ├── skills/*.md       # Domain-specific prompts
  └── data/             # SQLite DBs (factory.db, platform.db)
_MIGRATION_FACTORY/     # Code migration engine (Angular 16→17, ISO 100%)
```

## RUN COMMANDS
```bash
# SF CLI
cd _SOFTWARE_FACTORY && source setup_env.sh
factory <p> brain run --mode vision|fix|security|refactor|missing
factory <p> cycle start -w 5 -b 20 -t 30   # batch TDD
factory status --all

# Platform (NEVER --reload, ALWAYS --ws none)
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning

# Tests
python3 -m pytest tests/ -v
cd platform/tests/e2e && npx playwright test
```

## LLM PROVIDERS (env-driven)
```
Local (default):  PLATFORM_LLM_PROVIDER=minimax    PLATFORM_LLM_MODEL=MiniMax-M2.5
Azure (docker):   PLATFORM_LLM_PROVIDER=azure-openai PLATFORM_LLM_MODEL=gpt-5-mini
```
Fallback chain: primary → next in [minimax, azure-openai, azure-ai]
- MiniMax M2.5: fast, cheap, <think> blocks consume tokens (min 16K)
- Azure GPT-5-mini: reasoning model, NO temperature (only 1.0), needs max_completion_tokens≥8K
- Azure GPT-5.2: swedencentral private endpoint (VNet only)
- Keys: `~/.config/factory/*.key` — NEVER set `*_API_KEY=dummy`
- Client: `platform/llm/client.py` — `_PROVIDERS`, `_FALLBACK_CHAIN`, cooldown 90s on 429

## AZURE INFRASTRUCTURE
```
VM:   vm-macaron (RG-MACARON, francecentral) — Standard_D4as_v5 (4 vCPU, 16GB)
      IP: 4.233.64.30, SSH: azureadmin, nginx basic auth: macaron/macaron
      Files: /opt/macaron/platform/ — docker compose (platform + nginx)
      NOTE: D4as_v6 fails (SCSI disk controller incompatible, needs NVMe)
      NOTE: active compose = platform/docker-compose.yml (NOT deploy/)
      NOTE: files owned by azureadmin → SCP to /tmp + sudo cp

PG:   macaron-platform-pg (RG-MACARON, francecentral) — B1ms, PG 17, 32GB
      FQDN: macaron-platform-pg.postgres.database.azure.com
      DB: macaron_platform | User: macaron | SSL: require
      Extensions: pgvector 0.8.0, pg_trgm 1.6, uuid-ossp 1.1
      Firewall: allow-vm (4.233.64.30), allow-dev (update IP as needed)
      Status: ACTIVE — dual adapter (adapter.py), data migrated
      Schema: schema_pg.sql (33 tables, tsvector FTS, pgvector embeddings)
      Adapter: platform/db/adapter.py — translates SQLite SQL→PG SQL transparently
      Migration: platform/db/migrate_data.py — batch SQLite→PG with ON CONFLICT DO NOTHING

LLM:  ascii-ui-openai (rg-ascii-ui, francecentral) — gpt-5-mini
      Capacity: 100 req/min, 100K tokens/min
      NOTE: castudioia* resources are private endpoint (VNet only, unusable)

Deploy: rsync fails (permissions) → SCP to /tmp + sudo cp
        VM resize: az vm deallocate → az vm resize → az vm start
        Container rebuild: sudo docker compose up -d --build
```

## SF PIPELINE
```
Brain (Opus) → FRACTAL (3 concerns) → TDD Workers (//) → Adversarial → Build → Infra Check → Deploy → E2E → Promote/Rollback → Feedback → XP Agent
```

## ADVERSARIAL (Team of Rivals — arXiv:2601.14351)
```
L0: deterministic (test.skip, @ts-ignore, empty catch) → VETO ABSOLU
L1: LLM semantic (SLOP, hallucination, logic) → VETO ABSOLU
  - HALLUCINATION/SLOP keywords → force score≥7 + REJECT (engine.py has_critical_flags)
  - Retry loop: 5 attempts max, then NodeStatus.FAILED
L2: architecture (RBAC, validation, API design) → VETO + ESCALATION
```
Multi-vendor: Brain=Opus, Worker=MiniMax, Security=GLM, Arch=Opus
Rule: "Code writers cannot declare their own success"

### Métriques (core/metrics.py)

| Métrique | Target | Source Paper |
|----------|--------|--------------|
| L0 catch rate | 25% | 24.9% (paper) |
| L1 catch rate | 75% | 87.8% (Code+Chart) |
| L2 catch rate | 85% | 14.6% supplémentaire |
| Final success | 90%+ | 92.1% (paper) |

Config: `projects/*.yaml` → `adversarial:` block (cascade_enabled, l0_fast, l1_code, l2_arch, metrics_enabled)

## CoVe (Chain-of-Verification) — arxiv:2309.11495
4-stage anti-hallucination: Draft → Plan Verify → Answer Independently → Final
Applied to Brain (feature→AO trace), Adversarial (bypass detection), Infra (diagnostic)

## AO TRACEABILITY
Rule: no feature without AO ref (= SLOP). Config: `ao_compliance.enabled/refs_file` in projects/*.yaml

## DEPLOY & POST-DEPLOY
- CLI tools per project: `factory <p> deploy staging|prod`
- All stages gated by adversarial (build, staging, E2E, prod)
- Stuck detection: 0 chars 5min → fallback LLM chain
- Post-deploy: TMC (k6) → Chaos Monkey → TMC Verify → DEPLOYED
  - TMC: p95<500ms, errors<1%, >50rps. Fail → perf task
  - Chaos: kill/latency/cpu scenarios, 30s recovery. Fail → ROLLBACK
  - Files: `core/tmc_runner.py`, `core/chaos_runner.py`

## LEAN/XP
- WIP limits: max_concurrent, max_per_domain, wsjf queue priority
- WSJF dynamique: recalcul on feedback, decay temporel
- Quality gates: coverage 80%+, complexity <15, security 0 critical
- Canary deploy: 1%→10%→50%→100%, rollback si error>baseline+5%
- XP Agent retro: weekly patterns → auto-patch adversarial rules

## MCP ARCHITECTURE
```
MCP LRM (port 9500) ← proxy (stdio) ← opencode workers
MCP Platform (port 9501, auto-start) ← proxy ← agents/CLI
```
LRM tools: lrm_locate/read/conventions/task_read/task_update/build, confluence_search/read, jira_search
Platform tools: platform_agents/missions/phases/messages/memory/git/code/metrics
Anonymization: PII stripping (phones, emails, names) via `mcp_lrm/anonymizer.py`
RLM Cache: SQLite FTS5 `data/rlm_cache.db`, 1h TTL, cache-first

## BUILD QUEUE & CYCLE WORKER
Global build queue: 1 job at a time, all projects. `factory queue start/stop/status`
Cycle worker (preferred): batch N TDD → 1 build → deploy. `factory <p> cycle start -w 5 -b 20 -t 30`
Files: `core/build_queue.py`, `core/cycle_worker.py`

## CORE MODULES
- **Brain** (`core/brain.py`): recursive analysis, modes: all/vision/fix/security/perf/refactor/test/migrate/debt/missing
  - Missing mode: TRUE TDD — finds tests importing non-existent modules → IMPLEMENT tasks
  - Context: ProjectContext RAG (10 categories, FTS5, auto-refresh 1h)
- **Cycle** (`core/cycle_worker.py`): TDD→BUILD→DEPLOY, batch, no FRACTAL
- **Wiggum** (`core/wiggum_tdd.py`): pool daemon, FRACTAL enabled, adversarial per commit
- **Skills** (`core/skills.py`): domain→prompt auto-mapping (smoke_ihm, e2e_api, e2e_ihm, ui, ux, tdd)
- **FRACTAL** (`core/fractal.py`): L1=3 concerns (feature→guards→failures), L2=KISS atomic (impl→test→verify)
- **Adversarial** (`core/adversarial.py`): 100% LLM+CoVe, zero regex. Understands context (CLI Exit≠skip, fixture secrets≠leak)
- **Infra** (`core/wiggum_infra.py`): check_site/docker/nginx/db → CoVe diagnosis → auto-fix
- **Deploy** (`core/wiggum_deploy.py`): BUILD→ADVERSARIAL→INFRA CHECK→STAGING→E2E(subprocess direct)→PROD
- **TaskStore** (`core/task_store.py`): SQLite data/factory.db, status: pending→locked→tdd_in_progress→code_written→build→commit→deploy
- **ProjectContext** (`core/project_context.py`): RAG 10 categories, FTS5, auto-refresh 1h, 12K chars max
- **Meta-Awareness** (`core/meta_awareness.py`): cross-project error detection (50+ reps → SYSTEMIC, 2+ projects → CROSS-PROJECT)

## CLI REFERENCE
```bash
factory <p> brain run --mode vision|fix|security|perf|refactor|test|migrate|debt|missing
factory <p> brain --chat "q"
factory <p> cycle start -w 5 -b 20 -t 30   # PREFERRED (batch build)
factory <p> wiggum start -w 5               # LEGACY (1-by-1 build)
factory <p> infra check|diagnose|fix
factory queue start|stop|status
factory meta status|analyze --create-tasks
factory xp analyze --apply
factory <p> tasks retry [-t pending] [-s tdd_failed]
factory status --all
```

## PROJECTS
ppz psy veligo yolonow fervenza solaris **factory** (self)
LLM: brain=Opus, wiggum/cycle=MiniMax-M2.5, fallback→M2.1→GLM-4.7-free, timeout=30min

## BRAIN PHASE CYCLE
```
PHASE 1: FEATURES (vision) → TDD → DEPLOY → OK? → PHASE 2: FIXES → TDD → DEPLOY → OK? → PHASE 3: REFACTOR → LOOP
```
Rule: NO REFACTOR until FIXES deployed. NO FIXES until FEATURES deployed.
Config: `brain.current_phase` + `brain.vision_doc` in projects/*.yaml

## CONVENTIONS
- **⛔ ZERO SKIP**: NEVER `--skip-*`, `test.skip()`, `@ts-ignore`, `#[ignore]` — FIX > SKIP
- **Adversarial 100% LLM**: always MiniMax semantic, never regex
- **Cycle > Wiggum**: batch build, ~20x less CPU
- SvelteKit: no `+` prefix test files, tests in `__tests__/` subfolder
- opencode: `permission.doom_loop: "allow"` mandatory (prevents stdin hang)
- Process cleanup: `start_new_session=True` + `os.killpg()` on timeout

## FIGMA MCP
Figma Desktop (127.0.0.1:3845) via `proxy_figma.py`, fallback `mcp.figma.com`
Tools: get_file, get_node, get_styles, get_selection

## MIGRATION FACTORY (`_MIGRATION_FACTORY/`)
ISO 100%: OLD === NEW (bit-à-bit). NO features, NO improvements, NO refactoring during migration.
Transform: PRE-VALIDATE(golden files) → TRANSFORM(codemod>LLM) → POST-VALIDATE → COMPARE(3-layer) → COMMIT/ROLLBACK
Comparative adversarial: L0=golden diff(0%), L1a=backward compat, L1b=RLM exhaustiveness(MCP), L2=breaking changes
Codemods: jscodeshift (NgModule→standalone, FormGroup→typed, *ngIf→@if)
CLI: `factory-migrate <p> brain|transform|validate|status`
Files: `core/transform_worker.py`, `core/comparative_adversarial.py`, `core/migration_state.py`

## MACARON AGENT PLATFORM (`platform/`)

### VISION
Real agentic orchestration ≠ workflow automation (n8n/LangFlow = RPA glorifié)
Team of Rivals: agents debate, veto, negotiate, delegate — not boxes with arrows

### ARCH
```
FastAPI + HTMX + Jinja2 + SSE | Dark purple theme | SQLite(local) / PostgreSQL(Azure)
AgentLoop (async task) ←→ MessageBus (per-agent queues) → SSE → Frontend
AgentExecutor → LLM (Azure/MiniMax) → tool calls → route via bus
```
Nav: Projects → Workflows → Patterns → Agents → Skills → Memory → MCPs | Settings

### DUAL SSE (CRITICAL)
`_push_sse()` pushes to BOTH `_sse_queues` (runner.py) AND `bus._sse_listeners` (broadcast)
`bus.publish()` → `bus._sse_listeners` via `_notify_sse()`
SSE endpoint `/sse/session/{id}` → `bus.add_sse_listener()` + filter by session_id

### PATTERN ENGINE (patterns/engine.py)
8 patterns: solo, sequential, parallel, loop, hierarchical, network, router, aggregator, human-in-the-loop
`run_pattern(PatternDef, session_id, task)` → `_execute_node()` → agent LLM streaming
Adversarial guard in `_execute_node`: L0 fast → L1 semantic → retry 2x → FAILED if still reject

### MISSION CONTROL
CDP orchestre 11 phases product lifecycle:
1.Idéation(network) 2.Comité(HITL) 3.Constitution(seq) 4.Archi(aggregator)
5.Sprints(hierarchical) 6.CI/CD(seq) 7.QA(loop) 8.Tests(parallel)
9.Deploy(HITL) 10.TMA Routage(router) 11.Correctif(loop)

### SAFe (Score ~7/10)
WSJF real calc, sprint auto-creation, feature pull PO, sprint review/retro, velocity tracking
Learning loop, I&A retrospective, gates GO/NOGO/PIVOT, error reloop (QA fail → dev-sprint max 2x)
Build gate: preflight build + reloop max 5x. TDD enforcement in dev-sprint prompt.

### KEY FILES
```
server.py, models.py, config.py
llm/client.py (multi-provider), llm/observability.py (per-call tracing)
a2a/bus.py (MessageBus), a2a/protocol.py, a2a/negotiation.py, a2a/veto.py
agents/loop.py (AgentLoop), agents/executor.py (LLM+tools), agents/store.py (133 agents YAML)
patterns/engine.py (8 patterns), patterns/store.py (PatternDef/Run/NodeState)
missions/store.py (MissionRun/PhaseRun/Sprint), missions/product.py (backlog)
sessions/store.py (SessionDef+MessageDef), sessions/runner.py (_push_sse dual)
memory/manager.py (4 layers FTS5), memory/vectors.py (pgvector/numpy dual)
db/adapter.py (SQLite/PG dual), db/migrations.py, db/schema_pg.sql, db/migrate_data.py
metrics/dora.py (DORA + velocity), workflows/store.py (27 nodes, 34 edges)
skills/library.py (1200+ GitHub), skills/definitions/*.yaml (42 YAML agents)
tools/ (code, git, deploy, memory, phase, browser, android, compose)
web/routes/ (10 sub-modules), web/ws.py (SSE), web/templates/ (20+ templates)
mcp_platform/ (port 9501, auto-start, 8 tools)
```

### DB PATH
`data/platform.db` (racine _SOFTWARE_FACTORY), PAS `platform/data/`
Dual backend: `DATABASE_URL` env var selects PG, absent = SQLite
⚠️ NEVER `rm -f data/platform.db` — persistent user data. `init_db()` handles migrations idempotently.
⚠️ NEVER set `*_API_KEY=dummy` — overrides real keys from `~/.config/factory/*.key`

### MONITORING
DORA: deploy freq, lead time, CFR, MTTR + velocity + 12-week sparklines
LLM: per-call tracing (provider, model, tokens, cost), `/api/llm/stats`, `/api/llm/traces`
Live: `/monitoring` SSE agents/messages/sessions
Cost: per-model pricing ($0.30-$15/1M tokens)

### DASHBOARD VIEWS
DSI/CTO (`/dsi`), Métier (`/metier`), Portefeuille (`/`), Projet Board (`/projects/{id}/board`)

### IDEATION
`/ideation` → 5 agents (BA+Archi+UX+Sécu+PM) → run_pattern(network) → streaming debate → Brief→Analyse→Synthèse
"Créer Epic" → PO creates project+git

### MEMORY
4-layer: session→pattern→project→global (FTS5 on SQLite, tsvector on PG)
Wiki-like `/memory`, confidence bars, auto-population from epic creation
Retrospectives → LLM analyze → lessons → memory_global (recursive self-improvement)
