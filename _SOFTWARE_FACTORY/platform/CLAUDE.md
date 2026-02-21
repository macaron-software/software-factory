# MACARON AGENT PLATFORM

## WHAT
Web multi-agent platform SAFe-aligned. Agents collaborate (debate/veto/delegate) autonomously.
FastAPI + HTMX + SSE + SQLite. Dark purple theme. Port 8099.

## RUN
```bash
cd _SOFTWARE_FACTORY
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# NO --reload (conflicts stdlib `platform` module)
# --ws none mandatory (SSE not WS)
# DB: data/platform.db (parent dir, NOT platform/data/)
# ⚠️ NEVER rm -f data/platform.db — persistent, contains missions/sessions/memory
```

## ⚠️ CRITICAL RULES
- **NEVER delete data/platform.db** — init_db() handles migrations idempotently
- **NEVER set *_API_KEY=dummy** — real keys loaded from `~/.config/factory/*.key`
- **NEVER `import platform`** at top-level (shadows stdlib)
- **NEVER `--reload`** with uvicorn (same reason)

## COPILOT CLI — SERVER LAUNCH
```
ALWAYS: nohup + & (detached)
  nohup python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none > /tmp/macaron-platform.log 2>&1 &
NEVER: mode="async" sans detach | mode="sync" pour serveur
VERIFY: curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/
KILL:   lsof -ti:8099 | xargs kill -9
```

## DEPLOY (Azure VM 4.233.64.30)
```bash
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
# FULL rebuild:
rsync -azP --delete --exclude='__pycache__' --exclude='data/' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "cd /opt/macaron && sudo docker compose --env-file .env -f platform/deploy/docker-compose-vm.yml up -d --build"
# FAST hotpatch (no rebuild, preserves container state):
tar cf /tmp/update.tar <files...>
scp -i "$SSH_KEY" /tmp/update.tar azureadmin@4.233.64.30:/tmp/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "docker cp /tmp/update.tar deploy-platform-1:/tmp/ && docker exec deploy-platform-1 bash -c 'cd /app/macaron_platform && tar xf /tmp/update.tar' && docker restart deploy-platform-1"
# Container code path: /app/macaron_platform/ (NOT /app/platform/)
# Auth: macaron:macaron | Prod LLM: Azure OpenAI gpt-5-mini only (AZURE_DEPLOY=1)
# UID mismatch: /opt/macaron owned by 501 (macOS), azureadmin=1001 → use docker cp
```

## STACK
- FastAPI + Jinja2 + HTMX + SSE (no WS). Zero build step. Zero emoji (SVG Feather only)
- SQLite WAL + FTS5 (~35 tables)
- LLM local: MiniMax M2.5 → Azure OpenAI (fallback). Prod: Azure OpenAI gpt-5-mini only
- Rate limit: 15 rpm (token-limited ~10-16 calls/min in practice, 100K tokens/60s)
- **133+ agents** (95 YAML defs), 12 patterns, 19 workflows, 1271 skills

---

## SAFe VOCABULARY

| SAFe | Platform | DB |
|------|----------|-----|
| Epic | `MissionDef` | `missions` |
| Feature | `FeatureDef` | `features` |
| Story | `UserStoryDef` | `user_stories` |
| Task | `TaskDef` | `tasks` |
| PI | `MissionRun` | `mission_runs` |
| Iteration | `SprintDef` | `sprints` |
| ART | Agent teams | `agents` |
| Ceremony | `SessionDef` | `sessions` |
| Ceremony Template | `WorkflowDef` | `workflows` |
| Pattern | `PatternDef` | `patterns` |

```
Portfolio → Epic (WSJF) → Feature → Story → Task
ART → PI (mission_run) → Iteration (sprint) → Ceremony (session) → Pattern
```

DB names keep current (missions, sessions, workflows) — UI uses SAFe terms.

---

## MISSION ORCHESTRATION

### Flow
```
POST /api/missions/start → MissionRun created → asyncio.create_task(_safe_run)
  → _mission_semaphore (1 concurrent) → MissionOrchestrator.run_phases()
    → per phase: sprint loop (max_sprints) → run_pattern() → adversarial guard
    → gate check (all_approved | no_veto | always) → next phase
```

### Key params
- `_mission_semaphore = Semaphore(1)` — 1 mission at a time
- `MAX_LLM_RETRIES = 2` — rate-limit retries per phase
- Non-dev phases: `max_sprints = 1` (try once, move on)
- Gate `always` → phase passes even on failure (`DONE_WITH_ISSUES`)
- Auto-resume on restart: finds ALL running/paused missions → re-launches

### WSJF
- Fields: `business_value`, `time_criticality`, `risk_reduction`, `job_duration`
- Formula: `(BV + TC + RR) / JD`. Sliders in creation form.

### Sprint Lifecycle
- Auto-created at dev-sprint start. Status: `planning→active→review→completed→failed`
- Velocity tracking: `velocity` + `planned_sp` columns
- Retro auto-generated via LLM → `sprints.retro_notes` + `memory_global`
- Retro lessons injected into sprint>1 prompts (learning loop)

### Portfolio Kanban
- 5 columns: Funnel→Analyzing→Backlog→Implementing→Done
- WIP limit: 3 epics in Implementing

---

## ADVERSARIAL GUARD (agents/adversarial.py)

### L0: Deterministic (0ms)
- SLOP: lorem ipsum, placeholder, TBD, XXX
- MOCK: TODO implement, NotImplementedError, pass+todo, fake/mock data
- **FAKE_BUILD**: placeholder gradlew, hardcoded "BUILD SUCCESS", tiny scripts <50 chars (score +7)
- HALLUCINATION: claims action without tool evidence
- LIE: invented URLs/file paths
- STACK_MISMATCH: Swift in Android, Kotlin in iOS (score +7)
- **code_write content inspection**: scans actual file content for mock/stub/fake patterns
- TOO_SHORT, ECHO, REPETITION

### L1: LLM Semantic (skipped for discussion patterns)
- Separate LLM reviews output quality
- Skip for: network, debate, aggregator, human-in-the-loop

### Scoring
- `score < 5` → pass. `5-6` → soft-pass with warning. `7+` → reject
- HALLUCINATION/SLOP/STACK_MISMATCH/FAKE_BUILD → always force reject (never soft-pass)
- `MAX_ADVERSARIAL_RETRIES = 0` — rejection = warning only, no retry loop

---

## AGENT PROTOCOLS (patterns/engine.py)

### _DECOMPOSE_PROTOCOL (Lead Dev)
- ENVIRONMENT CHECK mandatory before decomposing
- Must: `list_files` → `deep_search("build tools, SDK")` → subtasks
- Android→`android_build()`, iOS→swiftc, Web→node/npm
- No language mixing. Missing SDK → first subtask = setup.

### _EXEC_PROTOCOL (Dev)
- EXPLORE FIRST: `list_files` → `deep_search` → `memory_search` → THEN `code_write`
- NEVER create fake build scripts
- Android: `android_build()` / `android_test()` / `android_lint()` / `android_emulator_test()`
- Python: `build(command="python3 -m py_compile ...")`. Node: `build(command="npm ...")`
- Generic `build()` REJECTS gradle/gradlew commands → redirects to `android_build()`

### _QA_PROTOCOL (QA)
- Must call build/test tool at least once
- Android: `android_build()` → `android_test()` → `android_lint()` (NEVER generic build)
- Web: `browser_screenshot()` at least once
- Verify REAL compilation output — empty output = fake wrapper

### _RESEARCH_PROTOCOL (Discussion)
- Use `deep_search` and `memory_search` explicitly
- Read/search only, no code writes

---

## SPECIALIZED LEADS PER TECHNO

| Agent | Role | Stack | Special Tools |
|-------|------|-------|---------------|
| Karim Benali | Lead Android | Kotlin/Compose/Gradle | android_build/test/lint/emulator |
| Sophie Durand | Lead iOS | SwiftUI/async-await | — |
| Emma Laurent | Lead Frontend | React/SvelteKit/TS/a11y | browser_screenshot, playwright |
| Julien Moreau | Lead Backend | Python/Rust/API/PostgreSQL | docker_build, deep_search |
| Thomas Dubois | Lead Dev | Generic (fallback) | all dev tools |

---

## ANDROID BUILD PIPELINE

```
Agent code_write → android_build() → docker exec android-builder ./gradlew assembleDebug
                                                    ↓
                            android-builder container: JDK 17, Android SDK 35, API 34
                            Shared volume: /workspace/workspaces/{mission_id}
```
- `build()` tool intercepts gradle commands → returns error → "use android_build()"
- `tools/android_tools.py`: AndroidBuildTool, AndroidTestTool, AndroidLintTool, AndroidEmulatorTestTool
- All run via `docker exec android-builder` with 600s/900s timeout

---

## NAV (sidebar — 8 entries)

```
STRATEGY                     ENGINEERING
  Portfolio /                  Ceremonies /ceremonies
  Backlog /backlog             Live /live
  PI Board /pi                 ART /art
  Metrics /metrics             Toolbox /toolbox
```

---

## MODULES

### Core
- `server.py` — FastAPI app, lifespan (auto-resume missions), Jinja `_clean_llm()`
- `config.py` — PlatformConfig (7 config classes)
- `models.py` — 20+ Pydantic: A2AMessage, AgentStatus, MessageType, PhaseStatus, MissionStatus

### Agents
- `agents/executor.py` (545L) — LLM tool-calling loop (max 15 rounds)
- `agents/loop.py` (516L) — AgentLoop autonomous + AgentLoopManager
- `agents/store.py` (335L) — AgentDef CRUD + YAML seed (95 definitions)
- `agents/rlm.py` (403L) — RLM deep search, accepts `workspace_path` fallback
- `agents/adversarial.py` (435L) — L0 deterministic + L1 semantic guard
- `agents/tool_runner.py` (1086L) — all tool dispatch, android redirect, path resolution
- `agents/tool_schemas.py` (1135L) — ROLE_TOOL_MAP, role classification, schema cache

### Patterns
- `patterns/engine.py` (1144L) — run_pattern(), 8 types, protocols, adversarial guard
- Gate: `all_approved` | `no_veto` | `always` | `checkpoint`
- NodeStatus: PENDING, RUNNING, COMPLETED, VETOED, FAILED (NO "DONE")
- Phase summaries LLM-generated from conversation

### Services
- `services/mission_orchestrator.py` (780L) — MissionOrchestrator, phase loop, sprint management

### Missions
- `missions/store.py` — MissionDef (WSJF fields), SprintDef, TaskDef, FeatureDef
- `missions/product.py` — Product backlog (Epics→Features→Stories)

### Workflows
- `workflows/store.py` (440L) — WorkflowDef, WorkflowPhase, seed_builtins()
- 19 templates: safe-{veligo,ppz,psy,yolo,ferv,sol,logs,factory}, migration-sharelook, security-hacking, product-lifecycle, etc.

### A2A
- `a2a/bus.py` — MessageBus, async queues (2000), SSE bridge, dead letter
- `a2a/protocol.py` — 11 msg types, priority (VETO=10)
- `a2a/veto.py` — ABSOLUTE/STRONG/ADVISORY
- `a2a/negotiation.py` — propose→counter→vote

### LLM
- `llm/client.py` (~500L) — multi-provider, rate limiter (15 rpm), cooldown on 429
- Fallback: MiniMax M2.5 → Azure OpenAI. Prod: `AZURE_DEPLOY=1` → azure-openai only
- httpx: connect=30s, read=300s. MiniMax strips `<think>` auto
- Azure: `max_completion_tokens` (NOT `max_tokens`)

### Memory
- `memory/manager.py` — 4-layer: session/pattern/project/global (FTS5)
- `memory/project_files.py` — auto-loads CLAUDE.md, SPECS.md, VISION.md (3K/file, 8K total)

### Tools (18 modules in tools/)
```
code_tools.py    — code_read, code_write, code_edit, code_search
build_tools.py   — build, test, lint (subprocess 120s)
android_tools.py — android_build, android_test, android_lint, android_emulator_test (docker exec)
git_tools.py     — git_status, git_log, git_diff, git_commit
memory_tools.py  — memory_search, memory_store
phase_tools.py   — run_phase, list_phases, request_validation (orchestrator only)
platform_tools.py— platform_agents, platform_missions, platform_memory_search, platform_metrics
web_tools.py     — browser_screenshot, playwright_test
security_tools.py— sast_scan, dependency_audit, secrets_scan
deploy_tools.py  — deploy_azure
chaos_tools.py   — chaos_test, tmc_load_test
azure_tools.py   — Azure-specific
compose_tools.py — compose_workflow, create_team, create_sub_mission
```

### Generators
- `generators/team.py` — LLM-driven team composition, _ROLE_LAYERS (0-5)

### Web
- `web/routes/` — missions.py(3184L), pages.py(928L), sessions.py(924L), workflows.py(980L), projects.py(799L), agents.py, api.py, ideation.py, helpers.py
- `web/ws.py` — SSE endpoints (bus.add_sse_listener, keepalive 30s)
- `web/templates/` — 64 files (Jinja2)
- `web/static/` — css/(3), js/(4+), avatars/

---

## AGENT TEAMS (133+)

| Category | Agents |
|----------|--------|
| Strategic (4) | strat-cpo (Julie), strat-cto (Karim), strat-dirprog (Thomas), strat-portfolio (Sofia) |
| Per-project ×8 | veligo-, ppz-, psy-, yolo-, ferv-, sol-, logs-, fact-: RTE, PO, Lead, Devs×2-3, QA, UX |
| Pool | security, whitebox-hacker, adversarial, e2e-tester, chaos, perf, data, devops, dpo, techwriter, a11y |
| Security (11) | pentester-lead, security-researcher, exploit-dev, security-architect, threat-analyst, ciso, secops-engineer, security-dev-lead, security-backend-dev, security-frontend-dev, qa-security |
| Specialized leads | mobile_android_lead, mobile_ios_lead, lead_frontend, lead_backend, tech_lead_mobile |
| 95 YAML defs | `skills/definitions/*.yaml` |

## PATTERNS (12 types)
solo, sequential, parallel, loop, hierarchical, network, human-in-the-loop, wave, adversarial-pair, adversarial-cascade, router, aggregator

Protocol-based (NOT hierarchy_rank):
- DISCUSSION (network, HITL, debate, aggregator): RESEARCH_PROTOCOL
- EXECUTION (hierarchical, sequential, parallel, loop): EXEC/QA/REVIEW/DECOMPOSE

---

## ROLE_TOOL_MAP (tool_schemas.py)

| Role | Key Tools |
|------|-----------|
| dev | code_*, git_*, build, test, deep_search, fractal_code, android_* |
| qa | code_read, build, test, playwright_test, browser_screenshot, android_*, chaos, tmc |
| devops | code_*, git_*, docker_build, deploy_azure, infra_check |
| security | code_read, code_search, deep_search, sast_scan, dependency_audit, secrets_scan |
| product | memory_*, deep_search, code_read, list_files |
| architecture | code_*, deep_search, memory_*, git_* |
| cdp | memory_*, deep_search, run_phase, compose_workflow, create_team, create_sub_mission |
| ALL roles | +platform_agents, +platform_missions, +platform_memory_search, +platform_metrics |

`_classify_agent_role(agent)` — keyword-based: role+name → category

---

## CONVENTIONS

### Imports (always relative)
```python
from ..db.migrations import get_db
from ..agents.store import get_agent_store
from ..llm.client import LLMMessage, get_llm_client
```

### Singletons
`get_agent_store()`, `get_project_store()`, `get_session_store()`, `get_mission_store()`, `get_pattern_store()`, `get_memory_manager()`, `get_llm_client()`, `get_workflow_store()`, `get_mission_run_store()`

### Templates
Extend `base.html`, blocks: `topbar_actions`, `content`.
Markdown: `{{ content | markdown | safe }}` (auto-strips `<think>`, `[TOOL_CALL]`).

### CSS
`--bg-primary:#0f0a1a`, `--purple:#a855f7`, `--accent:#f78166`. JetBrains Mono. Radius 10px. Sidebar 56px.

### Rules
- ZERO emoji — SVG Feather or text only
- `cleanLLM()` JS + `_clean_llm()` Jinja
- 4 view modes: card, card-simple, list, list-compact
- SSE: `bus.add_sse_listener()`, keepalive 30s, queue 2000
- No `--reload`. No `import platform` top-level. Run from parent dir.

---

## DB TABLES (~35 real + FTS virtual)
```
agents, agent_instances, agent_scores, patterns, skills, mcps,
missions, sprints, tasks, features, user_stories, feature_deps,
sessions, messages, messages_fts, artifacts, tool_calls,
memory_pattern, memory_project, memory_project_fts,
memory_global, memory_global_fts,
skill_github_sources, projects, workflows,
mission_runs, org_portfolios, org_arts, org_teams, org_team_members,
ideation_sessions, ideation_messages, ideation_findings,
retrospectives, confluence_pages, support_tickets,
program_increments, integrations, llm_traces, platform_incidents
```

---

## FILE TREE
```
platform/
├── server.py, config.py, models.py, security.py
├── agents/    executor.py, loop.py, store.py, rlm.py, adversarial.py, tool_runner.py, tool_schemas.py, permissions.py
├── patterns/  engine.py(1144L), store.py
├── missions/  store.py, product.py
├── services/  mission_orchestrator.py(780L)
├── workflows/ store.py(440L)
├── sessions/  store.py, runner.py(672L)
├── a2a/       bus.py, protocol.py, veto.py, negotiation.py
├── llm/       client.py, observability.py
├── memory/    manager.py, project_files.py
├── generators/ team.py
├── metrics/   dora.py
├── tools/     android_tools.py, build_tools.py, code_tools.py, git_tools.py, web_tools.py, security_tools.py, deploy_tools.py, chaos_tools.py, phase_tools.py, platform_tools.py, compose_tools.py, azure_tools.py, memory_tools.py, mcp_bridge.py, registry.py, sandbox.py, test_tools.py
├── projects/  manager.py, registry.py
├── skills/    library.py, definitions/*.yaml (95)
├── db/        schema.sql, migrations.py
├── security/  __init__.py
├── deploy/    Dockerfile, docker-compose-vm.yml, nginx-vm.conf
├── web/
│   ├── routes/ missions.py(3184L), pages.py, sessions.py, workflows.py, projects.py, agents.py, api.py, ideation.py, helpers.py
│   ├── ws.py (SSE)
│   ├── templates/ (64 files)
│   └── static/ css/(3), js/(4+), avatars/
└── data/ → ../data/platform.db
```

## KNOWN ISSUES / GOTCHAS
- `NodeStatus` enum: PENDING, RUNNING, COMPLETED, VETOED, FAILED — **NO** `DONE` value
- HTTP 400 tool message ordering: `messages with role 'tool' must follow 'tool_calls'` — executor bug, non-fatal
- UID mismatch on Azure: /opt/macaron owned by 501, azureadmin=1001 → docker cp workaround
- `_mission_semaphore = Semaphore(1)` — only 1 mission runs at a time, others queue
- Container path: `/app/macaron_platform/` (Dockerfile copies `platform/` as `macaron_platform/`)
- curl inside container: use docker network IP, NOT localhost (nginx proxies port 80→8090)
