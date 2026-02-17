# MACARON AGENT PLATFORM

## WHAT
Web multi-agent platform replacing CLI Software Factory.
Agents collaborate (debate/veto/delegate) to produce code autonomously.
Mission-driven: VISION.md → Missions → Sprints → Tasks → Code → Deploy.
FastAPI + HTMX + SSE + SQLite. Port 8090. Dark purple theme.

## RUN
```bash
cd _SOFTWARE_FACTORY
rm -f data/platform.db  # re-seed agents/workflows
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
# ⚠️ NO --reload (conflicts stdlib `platform` module)
# ⚠️ --ws none mandatory (SSE not WS)
# DB: data/platform.db (parent dir, NOT platform/data/)
```

## STACK
- **Backend**: FastAPI, Jinja2, SSE (no WebSocket)
- **Frontend**: HTMX, CSS vars, no build step
- **DB**: SQLite WAL + FTS5 (20 tables)
- **LLM**: Azure OpenAI → MiniMax M2.5 → Azure AI (fallback chain)
- **128 agents**, 23 patterns, 12 workflows, 1222 skills

## ARCHITECTURE

```
┌─ STRATEGIC ──────────────────────────────────┐
│ CPO (Julie) · CTO (Karim) · Dir.Prog        │
│ (Thomas) · Portfolio (Sofia)                 │
│ → debate VISION.md → create Missions (WSJF)  │
├─ OPERATIONAL (per project) ──────────────────┤
│ CP · SM · Lead · Devs×N · QA                │
│ + pool: sécu, adversarial, chaos, e2e, perf │
│ → Scrum: Planning → Sprint → Review+Retro   │
├─ EXECUTION (subprocess, no LLM) ────────────┤
│ Build · Deploy · Preflight · Evidence        │
└──────────────────────────────────────────────┘
```

## ENTITY HIERARCHY
```
Project → Mission (WSJF-ordered)
            → Sprint (planning|active|review|completed|failed)
              → Task (pending|assigned|in_progress|review|done|failed)
```

## NAV (sidebar)
🏠 Portfolio `/` → 🚀 Missions `/missions` → ⚡ Workflows → 🔲 Patterns → 🤖 Équipe → 🎯 Skills → 🧠 Memory → 🔌 MCPs → ⚙️ Settings

## KEY ROUTES
```
GET  /                    portfolio (DSI dashboard)
GET  /projects/{id}       project detail + missions sidebar
GET  /missions            mission list (filter by project/status)
GET  /missions/{id}       mission cockpit (sprints + kanban + team)
GET  /sessions/{id}/live  real-time agent view (graph/thread/chat)
POST /api/missions        create mission
POST /api/missions/{id}/start   launch mission
POST /api/missions/{id}/sprints create sprint
GET  /api/missions/{id}/board   kanban partial (HTMX, 10s refresh)
POST /api/sessions/{id}/run-pattern  execute pattern
POST /api/sessions/{id}/run-workflow execute workflow
```

## MODULES (key files)

### Core
- `server.py` — FastAPI app factory + lifespan
- `config.py` — PlatformConfig, 7 config classes
- `models.py` — 20+ Pydantic models (A2AMessage, AgentStatus, MessageType)

### Agents
- `agents/executor.py` (660L) — LLM tool-calling loop (max 15 rounds)
- `agents/loop.py` (516L) — AgentLoop autonomous + AgentLoopManager
- `agents/store.py` (335L) — AgentDef CRUD + YAML seed (42 definitions)
- `agents/rlm.py` (403L) — RLM deep search (arXiv:2512.24601)

### Patterns
- `patterns/engine.py` (860L) — run_pattern(), 8 types:
  solo, sequential, parallel, loop, hierarchical, network, debate, sf-tdd
- Gate types: `all_approved` | `no_veto` | `always`
- VETO detection: `[VETO]`, `NOGO`, `NO-GO`, `❌`, `Statut: NOGO`
- APPROVE detection: `[APPROVE]`, `✅ GO`, `Statut: GO`

### Missions (NEW)
- `missions/store.py` (376L) — MissionDef, SprintDef, TaskDef + MissionStore
- `missions/runner.py` — TODO: autonomous execution engine
- `missions/risk.py` — TODO: risk classification per file path
- `missions/preflight.py` — TODO: deterministic gates (lint/typecheck/tests)

### Workflows
- `workflows/store.py` (518L) — WorkflowDef, WorkflowPhase, WorkflowRun
- SAFe ceremonies: Planning (sequential) → Sprint (hierarchical) → Review (sequential, gate=all_approved)
- 12 workflows: safe-veligo, safe-popinz, safe-psy, safe-yolonow, safe-fervenza, safe-solaris, safe-logs, safe-factory, migration-sharelook, sf-pipeline, review-cycle, debate-decide

### A2A (Agent-to-Agent)
- `a2a/bus.py` (249L) — MessageBus, async queues, SSE bridge, dead letter
- `a2a/protocol.py` (207L) — 11 message types, priority mapping (VETO=10, REQUEST=5)
- `a2a/veto.py` (190L) — 3 levels: ABSOLUTE, STRONG, ADVISORY
- `a2a/negotiation.py` (171L) — propose→counter→vote cycle

### LLM
- `llm/client.py` (384L) — LLMClient singleton, multi-provider, cooldown on 429
- Fallback: minimax → azure-ai
- Azure uses `max_completion_tokens` (not `max_tokens`)
- MiniMax strips `<think>` blocks automatically

### Memory
- `memory/manager.py` (205L) — 4-layer: session/pattern/project/global
- `memory/project_files.py` (120L) — auto-loads CLAUDE.md, SPECS.md, VISION.md, README.md (3K/file, 8K total)

### Tools (available to agents)
```
code_read, code_search, code_write, code_edit
git_status, git_log, git_diff
build, test, lint  (subprocess, 300s/120s timeout)
memory_search, memory_store
list_files, deep_search (RLM)
```

### Web
- `web/routes.py` (2130L) — 70+ endpoints
- `web/ws.py` (156L) — SSE endpoints
- 33 templates (Jinja2), 3 CSS files
- HTMX patterns: hx-get/post, hx-target, hx-swap, hx-trigger="load, every 30s"

## DB TABLES (20)
```
agents, agent_instances, patterns, skills, mcps,
missions, sprints, tasks,
sessions (legacy), messages, messages_fts, artifacts,
memory_pattern, memory_project, memory_project_fts,
memory_global, memory_global_fts, tool_calls,
skill_github_sources, projects, workflows
```

## AGENT TEAMS (128 total)

### Strategic (4, cross-project, pool)
strat-cpo (Julie), strat-cto (Karim), strat-dirprog (Thomas), strat-portfolio (Sofia)

### Per-project teams (prefix: veligo-, ppz-, psy-, yolo-, ferv-, sol-, logs-, fact-)
Each has: CP, SM, Lead Dev, Dev×2-3, QA, UX

### Pool agents (prefix: pool-)
security, whitebox-hacker, adversarial, e2e-tester, chaos, perf, data, devops, dpo, techwriter, a11y

### Agent definitions (42 YAML in skills/definitions/)
Roles: DSI, architects, devs (back/front/full/mobile), QA, devops, SRE, DBA, SM, agile coach, RTE, PO, tech writer, security, compliance, UX, accessibility, data, ML

## PATTERNS (23)

### Core (8 types)
solo-chat, sequential, parallel, adversarial-pair, adversarial-cascade, hierarchical, debate, sf-tdd

### Project-specific (15)
Per-project: *-pi (planning), *-sprint (dev), *-release, *-retro
Projects: veligo, ppz, psy, yolo, ferv, sol, logs, fact

## WORKFLOWS (12)
```
safe-veligo, safe-popinz, safe-psy, safe-yolonow,
safe-fervenza, safe-solaris, safe-logs, safe-factory,
migration-sharelook, sf-pipeline, review-cycle, debate-decide
```
Each SAFe workflow = 3 ceremonies: Planning → Sprint → Review+Retro

## HARNESS ENGINEERING (NEXT — Phase 3)

### Concept
Inside each Task in a Sprint, run a harness loop:
```
Dev codes → Preflight gate (deterministic) → Review gate (LLM) → Evidence → Done
     ↑_________ remediation (max 3) _________↩
```

### Risk tiers (per project, in yaml)
- HIGH: api/, auth/, db/, security/, migrations/ → full checks
- LOW: everything else → preflight + build only

### Preflight gate (subprocess, NOT LLM)
lint + typecheck + unit tests → catch 60%+ errors before LLM review

### Review gate (SHA-discipline)
- Review valid ONLY for current HEAD SHA
- Stale review = re-run
- VETO → remediation → re-review

### Evidence (structured JSON, machine-verifiable)
test results, coverage delta, security scan, browser evidence (UI)

### Harness gap tracking
regression → harness_gap task → test case → preflight grows → caught deterministically

## CONVENTIONS

### Imports
```python
from ..db.migrations import get_db
from ..agents.store import get_agent_store
from ..llm.client import LLMMessage, get_llm_client
```
Always relative. `from __future__ import annotations` for forward refs.

### Singletons
```python
get_agent_store(), get_project_store(), get_session_store(),
get_mission_store(), get_pattern_store(), get_memory_manager(),
get_llm_client(), get_workflow_store()
```

### Templates
Extend `base.html`, blocks: `topbar_actions`, `content`.
Markdown filter: `{{ content | markdown | safe }}`.

### CSS
Vars: `--bg-primary:#0f0a1a`, `--purple:#a855f7`, `--accent:#f78166`.
Font: `JetBrains Mono`. Radius: 10px. Sidebar: 56px.

### View modes
`.item-grid[data-view-grid]` + `.item-card`, 4 modes: card, card-simple, list, list-compact.

### SSE
`bus.add_sse_listener()`, filter by session_id, keepalive 30s.
`/sse/session/{id}` for live views.

### Process
No `--reload`. No `import platform` at top level.
Run from parent: `python -m uvicorn platform.server:app`.
Kill via `lsof -ti :8090` then `kill PID`.

## FILE TREE (key files only)
```
platform/
├── server.py, config.py, models.py, security.py
├── agents/    executor.py, loop.py, store.py, rlm.py
├── patterns/  engine.py, store.py
├── missions/  store.py, __init__.py
├── workflows/ store.py
├── sessions/  store.py, runner.py, compressor.py
├── a2a/       bus.py, protocol.py, veto.py, negotiation.py
├── llm/       client.py, providers.py
├── memory/    manager.py, project_files.py
├── tools/     build_tools.py, code_tools.py, git_tools.py, web_tools.py
├── projects/  manager.py, git_service.py, factory_tasks.py
├── skills/    library.py, loader.py, definitions/*.yaml (42)
├── db/        schema.sql, migrations.py
├── web/
│   ├── routes.py (2130L, 70+ endpoints)
│   ├── ws.py (SSE)
│   ├── templates/ (33 files)
│   │   ├── base.html, portfolio.html, missions.html, mission_detail.html
│   │   ├── agents.html, patterns.html, workflows.html, skills.html
│   │   ├── project_detail.html, session_live.html, conversation.html
│   │   └── partials/ (11 reusable components)
│   └── static/css/ main.css, agents.css, projects.css
└── data/ → ../data/platform.db
```
