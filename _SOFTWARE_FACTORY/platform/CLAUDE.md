# MACARON AGENT PLATFORM

## WHAT
Web multi-agent platform. SAFe-aligned.
Agents collaborate (debate/veto/delegate) to produce code autonomously.
FastAPI + HTMX + SSE + SQLite. Dark purple theme.

## RUN
```bash
cd _SOFTWARE_FACTORY
rm -f data/platform.db  # re-seed
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
# NO --reload (conflicts stdlib `platform` module)
# --ws none mandatory (SSE not WS)
# DB: data/platform.db (parent dir, NOT platform/data/)
```

## DEPLOY (Azure VM)
```bash
# VM: 4.233.64.30, user azureadmin, key ~/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete --exclude='__pycache__' --exclude='data/' --exclude='tests/e2e/node_modules' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "cd /opt/macaron && sudo docker compose --env-file .env -f platform/deploy/docker-compose-vm.yml up -d --build"
# Basic Auth: macaron:macaron | .env: MINIMAX_API_KEY, AZURE_OPENAI_API_KEY
```

## STACK
- **Backend**: FastAPI, Jinja2, SSE (no WebSocket)
- **Frontend**: HTMX, CSS vars, no build step, zero emoji (SVG Feather icons only)
- **DB**: SQLite WAL + FTS5 (~25 tables)
- **LLM**: MiniMax M2.5 (primary) → Azure OpenAI → Azure AI (fallback)
- **128 agents**, 23 patterns, 12 workflows, 1222 skills

---

## SAFe VOCABULARY (AUTHORITATIVE)

### Glossary — What each term means in this platform

| SAFe Term | Platform Entity | DB Table | Description |
|-----------|----------------|----------|-------------|
| **Portfolio** | Strategic view | — | Cross-project governance, budgets, WSJF prioritization |
| **Epic** | `MissionDef` | `missions` | Strategic initiative, WSJF-scored. Decomposes into Features |
| **Feature** | `FeatureDef` | `features` | Product capability under an Epic. Has acceptance criteria |
| **Story** | `UserStoryDef` | `user_stories` | User need under a Feature. Estimable, testable |
| **Task** | `TaskDef` | `tasks` | Atomic work unit assigned to an agent |
| **PI** | `MissionRun` | `mission_runs` | Program Increment execution (multi-phase lifecycle) |
| **Iteration** | `SprintDef` | `sprints` | Time-boxed dev cycle within a PI |
| **ART** | Agent teams | `agents` | Agile Release Train = team of agents (per-project) |
| **Ceremony** | `SessionDef` | `sessions` | Agent collaboration instance (planning, review, retro...) |
| **Ceremony Template** | `WorkflowDef` | `workflows` | Reusable multi-phase ceremony definition |
| **Pattern** | `PatternDef` | `patterns` | Orchestration topology (sequential, hierarchical, debate...) |
| **Backlog** | Product view | — | Epic → Feature → Story hierarchy + prioritization |
| **Discovery** | Ideation flow | `ideation_*` | Brainstorm with agents → produces Epics |

### Hierarchy
```
Portfolio
  └── Epic (= mission, WSJF-ordered)
        └── Feature (product capability)
              └── Story (user need)
                    └── Task (atomic, assigned to agent)

Execution:
  ART (= agent team per project)
    └── PI (= mission_run, multi-phase lifecycle)
          └── Iteration (= sprint, time-boxed)
                └── Ceremony (= session, agent collaboration)
                      └── Pattern (orchestration: sequential/hierarchical/debate...)
```

### Terms to STOP using
| Wrong | Correct | Why |
|-------|---------|-----|
| "Mission" in UI | **Epic** or **PI** | "Mission" is military, not agile. Epic=backlog item, PI=execution |
| "Mega-workflow" | **PI Lifecycle** | It's a PI execution with phases |
| "Session" in UI | **Ceremony** | Sessions are SAFe ceremonies (planning, sprint, review, retro) |
| "Workflow" in UI | **Ceremony Template** | Template that defines how a ceremony runs |
| "Pipeline stratégique" | **Portfolio Kanban** | SAFe term for strategic flow |

NOTE: DB tables/code keep current names (missions, sessions, workflows) — rename is UI-only.

---

## NAV (sidebar — target: 8 entries, grouped)

### Current (17 entries — TOO MANY, vocabulary mess)
Portfolio `/` → DSI Board `/dsi` → Vue Métier `/metier` → Product `/product` → Idéation `/ideation` → Missions `/missions` → Mission Control `/mission-control` → Workflows `/workflows` → Patterns `/patterns` → Sessions `/sessions` → Équipe `/agents` → Org SAFe `/org` → Skills `/skills` → Memory `/memory` → MCPs `/mcps` → Generator `/generate` → DORA `/metrics`

### Target (8 entries — SAFe-aligned, clean groups)
```
STRATÉGIE
  Portfolio ........... Epics stratégiques + DSI + vue métier (3 onglets)
  Backlog ............. Epics → Features → Stories + Discovery (idéation)

EXÉCUTION
  PI Board ............ Program Increments en cours + contrôle
  Ceremonies .......... Templates (workflow + patterns), catalogue
  Live ................ Cérémonies actives (sessions en cours)

ÉQUIPE
  ART ................. Agents, org SAFe, générateur d'équipe
  Toolbox ............. Skills, MCPs, Memory (3 onglets)
  Metrics ............. DORA + vélocité + throughput
```

### View switcher (3 modes, bottom sidebar)
| Mode | Shows |
|------|-------|
| **all** | 8 items |
| **strategy** | Portfolio, Backlog, Metrics |
| **engineering** | Ceremonies, Live, ART, Toolbox |

### Page consolidation map
| New page | Merges | URL |
|----------|--------|-----|
| Portfolio | portfolio + dsi + metier (3 tabs) | `/` |
| Backlog | product + ideation (2 tabs: Backlog, Discovery) | `/backlog` |
| PI Board | missions + mission-control (list + control) | `/pi` |
| Ceremonies | workflows + patterns (2 tabs: Templates, Patterns) | `/ceremonies` |
| Live | sessions list + session_live | `/live` |
| ART | agents + org + generate (3 tabs: Agents, Org, Generator) | `/art` |
| Toolbox | skills + memory + mcps (3 tabs) | `/toolbox` |
| Metrics | dora_dashboard | `/metrics` |

---

## ARCHITECTURE

```
┌─ PORTFOLIO (Strategic) ─────────────────────┐
│ CPO (Julie) · CTO (Karim) · Dir.Prog        │
│ (Thomas) · Portfolio Mgr (Sofia)             │
│ → debate VISION.md → create Epics (WSJF)     │
├─ ART (per project) ─────────────────────────┤
│ RTE · PO · Lead · Devs×N · QA               │
│ + pool: sécu, adversarial, chaos, e2e, perf │
│ → Ceremonies: PI Planning → Iteration → I&A  │
├─ EXECUTION (subprocess, no LLM) ────────────┤
│ Build · Deploy · Preflight · Evidence        │
└──────────────────────────────────────────────┘
```

## KEY ROUTES (current → target)
```
# CURRENT                          # TARGET (after refactor)
GET  /                             GET  /                    Portfolio (tabs: overview/dsi/metier)
GET  /dsi                          (merged into / tab)
GET  /metier                       (merged into / tab)
GET  /product                      GET  /backlog             Backlog (tabs: backlog/discovery)
GET  /ideation                     (merged into /backlog tab)
GET  /missions                     GET  /pi                  PI list
GET  /missions/{id}                GET  /pi/{id}             PI detail (iterations + kanban)
GET  /mission-control              GET  /pi/{id}/control     PI lifecycle control
GET  /workflows                    GET  /ceremonies          Ceremony templates
GET  /patterns                     (merged into /ceremonies tab)
GET  /sessions                     GET  /live                Active ceremonies
GET  /sessions/{id}/live           GET  /live/{id}           Ceremony live view
GET  /agents                       GET  /art                 ART (tabs: agents/org/generator)
GET  /org                          (merged into /art tab)
GET  /generate                     (merged into /art tab)
GET  /skills                       GET  /toolbox             Toolbox (tabs: skills/memory/mcps)
GET  /memory                       (merged into /toolbox tab)
GET  /mcps                         (merged into /toolbox tab)
GET  /metrics                      GET  /metrics             DORA metrics
GET  /projects/{id}                GET  /projects/{id}       Project detail
```

---

## GRAPH VIZ (session_live.html → live/{id})

### Pan & Zoom
- Mouse wheel zoom 0.3x–3x, drag-to-pan, +/-/fit-all buttons
- CSS transform (translate+scale) on SVG, NOT viewBox

### Flow particles
- SVG `<animateMotion>` along Bezier edge path on SSE message
- 900ms duration, auto-cleanup

### Focus/dim mode
- Click node → `focusedNode` + `connectedSet` computed from edges
- Unconnected: `.dimmed` (opacity 0.18, pointer-events none)
- Click background to clear

### Minimap
- 160x100px, auto-hidden if ≤6 agents. Viewport rect, click-to-navigate

### Agent chat panel
- 380px slide-in from right (CSS transform)
- Avatar, name, role, status dot, skills tags
- Quick actions: Status/Review/Delegate (pre-filled prompts)
- Chat bubbles (user/agent), animated typing dots (WhatsApp-style)
- Sends via `POST /api/sessions/{id}/agents/{agent_id}/message` → A2A bus

### Pulse ring
- `@keyframes pulseRing` on thinking/acting agents

## SVG SPRITES
All icons SVG in `partials/svg_sprites.html`. **ZERO emoji anywhere — ENFORCED**.
`cleanLLM()` strips `<think>`, `[TOOL_CALL]`, `[DELEGATE:...]` from all rendered content.

## MODULES (key files)

### Core
- `server.py` — FastAPI app + Jinja markdown filter with `_clean_llm()`
- `config.py` — PlatformConfig, 7 config classes
- `models.py` — 20+ Pydantic models (A2AMessage, AgentStatus, MessageType)

### Agents
- `agents/executor.py` (~1150L) — LLM tool-calling loop (max 15 rounds), mission tools
- `agents/loop.py` (516L) — AgentLoop autonomous + AgentLoopManager
- `agents/store.py` (335L) — AgentDef CRUD + YAML seed (42 definitions)
- `agents/rlm.py` (403L) — RLM deep search (arXiv:2512.24601)

### Patterns
- `patterns/engine.py` (~1200L) — run_pattern(), 8 types:
  solo, sequential, parallel, loop, hierarchical, network, debate, sf-tdd
- Gate types: `all_approved` | `no_veto` | `always`
- VETO detection: `[VETO]`, `NOGO`, `NO-GO`, `Statut: NOGO`
- APPROVE detection: `[APPROVE]`, `Statut: GO`
- SSE: `stream_thinking` heartbeat, `pattern_end` with DB fallback

### Missions (= Epics + PI execution)
- `missions/store.py` — MissionDef, SprintDef, TaskDef + MissionStore + MissionRunStore
- `missions/product.py` — Product backlog (Epics → Features → Stories)

### Workflows (= Ceremony Templates)
- `workflows/store.py` (518L) — WorkflowDef, WorkflowPhase, WorkflowRun
- SAFe ceremonies: Planning (sequential) → Sprint (hierarchical) → Review (gate=all_approved)
- 12 templates: safe-{veligo,popinz,psy,yolonow,fervenza,solaris,logs,factory}, migration-sharelook, sf-pipeline, review-cycle, debate-decide

### A2A (Agent-to-Agent)
- `a2a/bus.py` (249L) — MessageBus, async queues (maxsize=2000), SSE bridge, dead letter
- `a2a/protocol.py` (207L) — 11 message types, priority mapping (VETO=10, REQUEST=5)
- `a2a/veto.py` (190L) — 3 levels: ABSOLUTE, STRONG, ADVISORY
- `a2a/negotiation.py` (171L) — propose→counter→vote cycle

### LLM
- `llm/client.py` (~500L) — LLMClient singleton, multi-provider, cooldown on 429
- Fallback: minimax → azure-ai
- httpx timeout: connect=30s, read=300s (MiniMax thinking can be slow)
- MiniMax strips `<think>` blocks automatically
- Azure uses `max_completion_tokens` (not `max_tokens`)

### Memory
- `memory/manager.py` (205L) — 4-layer: session/pattern/project/global
- `memory/project_files.py` (120L) — auto-loads CLAUDE.md, SPECS.md, VISION.md (3K/file, 8K total)

### Generators
- `generators/team.py` — Team composition from mission brief

### Metrics
- `metrics/dora.py` — DORA metrics (Deployment Freq, Lead Time, CFR, MTTR)

### Tools (available to agents)
```
code_read, code_search, code_write, code_edit
git_status, git_log, git_diff
build, test, lint  (subprocess, 300s/120s timeout)
memory_search, memory_store
list_files, deep_search (RLM)
```

### Web
- `web/routes.py` (~5000L) — 100+ endpoints
- `web/ws.py` (156L) — SSE endpoints
- ~48 templates (Jinja2), 3 CSS files
- HTMX patterns: hx-get/post, hx-target, hx-swap, hx-trigger="load, every 30s"

## DB TABLES (~25)
```
agents, agent_instances, patterns, skills, mcps,
missions, sprints, tasks, features, user_stories,
sessions, messages, messages_fts, artifacts,
memory_pattern, memory_project, memory_project_fts,
memory_global, memory_global_fts, tool_calls,
skill_github_sources, projects, workflows,
mission_runs, org_portfolios, org_arts, org_teams, org_team_members,
ideation_sessions, ideation_messages, ideation_findings, retrospectives
```

## AGENT TEAMS (128 total)

### Strategic (4, cross-project, pool)
strat-cpo (Julie), strat-cto (Karim), strat-dirprog (Thomas), strat-portfolio (Sofia)

### Per-project teams (prefix: veligo-, ppz-, psy-, yolo-, ferv-, sol-, logs-, fact-)
Each has: RTE, PO, Lead Dev, Dev×2-3, QA, UX

### Pool agents (prefix: pool-)
security, whitebox-hacker, adversarial, e2e-tester, chaos, perf, data, devops, dpo, techwriter, a11y

### Agent definitions (42 YAML in skills/definitions/)
Roles: DSI, architects, devs (back/front/full/mobile), QA, devops, SRE, DBA, SM, agile coach, RTE, PO, tech writer, security, compliance, UX, accessibility, data, ML

## PATTERNS (23)

### Core (8 types)
solo-chat, sequential, parallel, adversarial-pair, adversarial-cascade, hierarchical, debate, sf-tdd

### Project-specific (15)
Per-project: *-pi (planning), *-sprint (dev), *-release, *-retro

## HARNESS ENGINEERING (NEXT)

### Concept
Inside each Task in an Iteration, run a harness loop:
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
- Stale review = re-run. VETO → remediation → re-review

### Evidence (structured JSON, machine-verifiable)
test results, coverage delta, security scan, browser evidence (UI)

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
Markdown filter: `{{ content | markdown | safe }}` (auto-strips `<think>`, `[TOOL_CALL]`).

### CSS
Vars: `--bg-primary:#0f0a1a`, `--purple:#a855f7`, `--accent:#f78166`.
Font: `JetBrains Mono`. Radius: 10px. Sidebar: 56px.

### UI rules
- **ZERO emoji** — SVG Feather icons or plain text only
- Animated typing dots (WhatsApp-style `dotPulse` keyframes)
- `cleanLLM()` in JS + `_clean_llm()` in Jinja filter
- 4 view modes: card, card-simple, list, list-compact

### SSE
`bus.add_sse_listener()`, filter by session_id, keepalive 30s.
Queue maxsize=2000. `stream_thinking` heartbeat during MiniMax think phase.

### Process
No `--reload`. No `import platform` at top level.
Run from parent: `python -m uvicorn platform.server:app`.
Clean `__pycache__` before restart if stale bytecode errors.

## FILE TREE
```
platform/
├── server.py, config.py, models.py, security.py
├── agents/    executor.py, loop.py, store.py, rlm.py
├── patterns/  engine.py, store.py
├── missions/  store.py, product.py
├── workflows/ store.py
├── sessions/  store.py, runner.py
├── a2a/       bus.py, protocol.py, veto.py, negotiation.py
├── llm/       client.py
├── memory/    manager.py, project_files.py
├── generators/ team.py
├── metrics/   dora.py
├── rbac/      __init__.py
├── tools/     build_tools.py, code_tools.py, git_tools.py, web_tools.py
├── projects/  manager.py
├── skills/    library.py, definitions/*.yaml (42)
├── db/        schema.sql, migrations.py
├── deploy/    Dockerfile, docker-compose-vm.yml, nginx-vm.conf
├── web/
│   ├── routes.py (~5000L, 100+ endpoints)
│   ├── ws.py (SSE)
│   ├── templates/ (~48 files)
│   │   ├── base.html (sidebar view-switch)
│   │   ├── portfolio.html, dsi.html, metier.html, product.html
│   │   ├── ideation.html, ideation_history.html
│   │   ├── missions.html, mission_detail.html, mission_control.html, mission_control_list.html, mission_start.html
│   │   ├── session_live.html (~1700L, graph+chat+thread)
│   │   ├── conversation.html, workflows.html, workflow_edit.html
│   │   ├── agents.html, org.html, generate.html, skills.html, memory.html
│   │   ├── dora_dashboard.html, project_detail.html, project_board.html, project_overview.html
│   │   └── partials/ (msg_unified.html, svg_sprites.html, view_switcher.html, ...)
│   └── static/css/ main.css, agents.css, projects.css
└── data/ → ../data/platform.db
```
