# MACARON AGENT PLATFORM

## WHAT
Web multi-agent platform SAFe-aligned. Agents collaborate (debate/veto/delegate) autonomously.
FastAPI + HTMX + SSE + SQLite. Dark purple theme. Port 8099.

## RUN
```bash
cd _SOFTWARE_FACTORY
rm -f data/platform.db data/platform.db-wal data/platform.db-shm  # re-seed
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# NO --reload (conflicts stdlib `platform` module)
# --ws none mandatory (SSE not WS)
# DB: data/platform.db (parent dir, NOT platform/data/)
```

## ⚠️ COPILOT CLI — SERVER LAUNCH
```
ALWAYS: nohup + & (detached, survives session shutdown)
  nohup python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none > /tmp/macaron-platform.log 2>&1 &
NEVER: mode="async" sans detach | mode="sync" pour serveur
VERIFY: curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/
KILL:   lsof -ti:8099 | xargs kill -9
```

## DEPLOY (Azure VM)
```bash
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete --exclude='__pycache__' --exclude='data/' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "cd /opt/macaron && sudo docker compose --env-file .env -f platform/deploy/docker-compose-vm.yml up -d --build"
# Basic Auth: macaron:macaron | .env: MINIMAX_API_KEY, AZURE_OPENAI_API_KEY
```

## STACK
- FastAPI + Jinja2 + HTMX + SSE (no WS). Zero build step. Zero emoji (SVG Feather only)
- SQLite WAL + FTS5 (~30 tables)
- LLM: MiniMax M2.5 → Azure OpenAI → Azure AI (fallback chain)
- **133 agents** (75 YAML defs), 12 patterns, 19 workflows, 1271 skills

---

## SAFe VOCABULARY

| SAFe | Platform | DB Table |
|------|----------|----------|
| Portfolio | Strategic view | — |
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
| Discovery | Ideation flow | `ideation_*` |

```
Portfolio → Epic (WSJF) → Feature → Story → Task
ART → PI (mission_run) → Iteration (sprint) → Ceremony (session) → Pattern
```

DB tables/code keep current names (missions, sessions, workflows) — rename UI-only.

---

## SAFe BACKBONE (implemented)

### WSJF Real Computation
- Mission creation form: sliders BV/TC/RR/JD (1-10)
- Formula: `(business_value + time_criticality + risk_reduction) / job_duration`
- Live computation in JS, stored in `missions` table

### Gate Enforcement
- `wf_phase.gate` enforced at runtime: `all_approved` blocks, `no_veto` blocks, `always` passes
- No more hardcoded blocking — uses workflow config

### Sprint Lifecycle
- Auto-created at dev-sprint start (SprintDef in `sprints` table)
- Status flow: `planning → active → review → completed → failed`
- Velocity tracking: `velocity` + `planned_sp` columns
- Retro auto-generated via LLM after each sprint, stored in `sprints.retro_notes` + `memory_global`

### Feature Pull
- Features from product backlog auto-injected into dev-sprint prompt
- Status set to `in_progress` at sprint 1 start

### Learning Loop
- Retro lessons from `memory_global` (category=retrospective) injected into sprint>1 prompts
- Continuous improvement across missions

### Portfolio Kanban
- 5 columns: Funnel → Analyzing → Backlog → Implementing → Done
- WIP limit: 3 epics max in Implementing (red border when exceeded)
- Route: `/api/portfolio/kanban` (HTMX tab in Backlog page)
- `kanban_status` on missions table, auto-updated on status change

### DORA + Velocity Metrics
- 4 DORA metrics + velocity card in dashboard
- Predictability: % sprints where velocity ≥ planned SP
- Velocity trend per sprint across missions

### I&A Ceremony
- Auto-trigger `_auto_retrospective()` after epic completes all phases
- LLM generates: successes, failures, lessons, improvements (JSON)
- Stored in `retrospectives` table + `memory_global` (lesson/improvement categories)

---

## NAV (sidebar — 8 entries)

```
STRATEGY                           ENGINEERING
  Portfolio /                        Ceremonies /ceremonies
  Backlog /backlog                   Live /live
  PI Board /pi                       ART /art
  Metrics /metrics                   Toolbox /toolbox
```
View switcher: all|strategy|engineering. localStorage persist.

---

## DYNAMIC ORCHESTRATOR

Workflow config `"orchestrator": "<agent_id>"` → overrides default `chef_de_programme`.
- `api_mission_start` reads `wf.config.orchestrator` → sets `mission.cdp_agent_id`
- `mission_control.html` uses `orchestrator_id` template var (avatar/name/role/SSE)
- `api_mission_run` resolves orch_id/name/role/avatar once → all SSE messages
- `api_mission_validate` sends GO/NOGO to `mission.cdp_agent_id`

Example: `security-hacking` workflow → CISO (Rachid Amrani) orchestrates, NOT CDP.

---

## SECURITY AUDIT WORKFLOW (`security-hacking`)

### Teams (11 agents + compliance_officer)
```
🔴 RED TEAM: pentester-lead (Karim), security-researcher (Léa), exploit-dev (Yassine)
🔵 BLUE TEAM: security-architect (Fatima), threat-analyst (Maxime), ciso (Rachid), secops-engineer (Aurélien)
🟣 PURPLE TEAM: security-dev-lead (Inès), security-backend-dev (Thomas), security-frontend-dev (Clara), qa-security (Samira)
+ compliance_officer (Hélène, existing)
```

### 8 Phases
| # | Phase | Pattern | Agents |
|---|-------|---------|--------|
| 1 | Recon | parallel | Red Team (3) |
| 2 | Threat Model | network | Red+Blue debate (4) |
| 3 | Exploitation | loop ×5 | Red Team PoCs |
| 4 | Vuln Report | aggregator | threat-analyst consolidates |
| 5 | Security Review | human-in-the-loop | CISO GO/NOGO checkpoint |
| 6 | Remediation | loop ×3 | Purple Team TDD fixes |
| 7 | Verification | parallel | re-exploit + compliance |
| 8 | Deploy Secure | sequential | staging→QA→canary→prod |

### Skills (4 .md files)
pentest_web, pentest_infra, threat_intel, security_remediation

### Veto hierarchy
ABSOLUTE: ciso, qa-security | STRONG: pentester-lead, compliance_officer, security-architect, threat-analyst

---

## PRODUCT LINE VIEW (`/product-line`)

Responsable produit → applications → épics → roadmap jalons.
DORA pilotage: qualité / time to market. SVG Feather icons (no emoji).

---

## GRAPH VIZ (session_live.html)

Pan+zoom (wheel 0.3–3x, drag). Flow particles (animateMotion 900ms).
Focus/dim mode (click node). Minimap 160×100px.
Agent chat panel 380px slide-in (avatar, skills, quick actions, WhatsApp-style dots).
Pulse ring on thinking/acting agents.

---

## MODULES

### Core
- `server.py` — FastAPI app + Jinja `_clean_llm()` filter
- `config.py` — PlatformConfig (7 config classes)
- `models.py` — 20+ Pydantic models

### Agents
- `agents/executor.py` (2438L) — LLM tool-calling loop (max 15 rounds), mission tools, tool ACL + path sandbox
- `agents/loop.py` (516L) — AgentLoop autonomous + AgentLoopManager
- `agents/store.py` (335L) — AgentDef CRUD + YAML seed (75 definitions)
- `agents/rlm.py` (403L) — RLM deep search (arXiv:2512.24601)

### Patterns
- `patterns/engine.py` (1727L) — run_pattern(), 8 types: solo, sequential, parallel, loop, hierarchical, network, debate, sf-tdd
- Gate: `all_approved` | `no_veto` | `always` | `checkpoint`
- VETO: `[VETO]`, `NOGO`, `NO-GO` | APPROVE: `[APPROVE]`, `Statut: GO`
- Phase summaries LLM-generated from conversation

### Missions
- `missions/store.py` — MissionDef, SprintDef, TaskDef + MissionStore + MissionRunStore
- `missions/product.py` — Product backlog (Epics → Features → Stories)

### Workflows
- `workflows/store.py` (1760L) — WorkflowDef, WorkflowPhase, seed_builtins()
- 19 templates: safe-{veligo,ppz,psy,yolo,ferv,sol,logs,factory}, migration-sharelook, sf-pipeline, review-cycle, debate-decide, security-hacking, product-lifecycle, dsi-platform-features, dsi-platform-tma, + others

### A2A
- `a2a/bus.py` (247L) — MessageBus, async queues (2000), SSE bridge, dead letter
- `a2a/protocol.py` (207L) — 11 msg types, priority (VETO=10)
- `a2a/veto.py` (190L) — ABSOLUTE/STRONG/ADVISORY
- `a2a/negotiation.py` (171L) — propose→counter→vote

### LLM
- `llm/client.py` (~500L) — multi-provider, cooldown on 429
- MiniMax M2.5 (primary) → Azure AI (fallback)
- httpx: connect=30s, read=300s. MiniMax strips `<think>` auto
- Azure: `max_completion_tokens` (NOT `max_tokens`)

### Memory
- `memory/manager.py` (205L) — 4-layer: session/pattern/project/global (FTS5)
- `memory/project_files.py` (120L) — auto-loads CLAUDE.md, SPECS.md, VISION.md

### Tools (agent-callable)
```
code_read, code_search, code_write, code_edit
git_status, git_log, git_diff
build, test, lint  (subprocess 300s/120s)
memory_search, memory_store
list_files, deep_search (RLM)
run_phase, list_phases, request_validation (orchestrator only)
```

### Web
- `web/routes.py` (8575L) — 100+ endpoints
- `web/ws.py` (156L) — SSE endpoints
- 44 templates (Jinja2), 3 CSS files
- HTMX: hx-get/post, hx-target, hx-swap, hx-trigger="load, every 30s"

---

## ISOLATION LAYERS (implemented)

| Layer | What | Status |
|-------|------|--------|
| Tool ACL | Agent only calls its declared tools | ✅ |
| Path sandbox | Files restricted to workspace | ✅ |
| Memory isolation | memory_search/store forced project scope | ❌ TODO |
| Git branch isolation | agent/{id}/ branch, never master | ❌ TODO |
| Rate limits | Max 100 tool calls, 50 writes/session | ❌ TODO |
| Git path guard | git_diff/log restricted to project_path | ❌ TODO |
| Docker per-agent | Container isolation for build/test | ❌ Optional |

---

## DB TABLES (~33)
```
agents, agent_instances, agent_scores, patterns, skills, mcps,
missions, sprints, tasks, features, user_stories,
sessions, messages, messages_fts, artifacts,
memory_pattern, memory_project, memory_project_fts,
memory_global, memory_global_fts, tool_calls,
skill_github_sources, projects, workflows,
mission_runs, org_portfolios, org_arts, org_teams, org_team_members,
ideation_sessions, ideation_messages, ideation_findings,
retrospectives, confluence_pages, support_tickets,
feature_deps, program_increments
```

## AGENT TEAMS (133 total)

### Strategic (4): strat-cpo (Julie), strat-cto (Karim), strat-dirprog (Thomas), strat-portfolio (Sofia)
### Per-project (prefix: veligo-, ppz-, psy-, yolo-, ferv-, sol-, logs-, fact-): RTE, PO, Lead, Devs×2-3, QA, UX
### Pool (prefix: pool-): security, whitebox-hacker, adversarial, e2e-tester, chaos, perf, data, devops, dpo, techwriter, a11y
### Security (11 new): pentester-lead, security-researcher, exploit-dev, security-architect, threat-analyst, ciso, secops-engineer, security-dev-lead, security-backend-dev, security-frontend-dev, qa-security
### 75 YAML definitions in skills/definitions/

## PATTERNS (12 DB)
Core types: solo, sequential, parallel, loop, hierarchical, network, human-in-the-loop, wave, adversarial-pair, adversarial-cascade, router, aggregator

Protocol: pattern type → agent behavior (NOT hierarchy_rank)
- DISCUSSION (network, HITL): RESEARCH_PROTOCOL, no code writes
- EXECUTION (hierarchical, sequential, parallel, loop): role-based (dev→EXEC, qa→QA, lead→REVIEW)

---

## CONVENTIONS

### Imports (always relative)
```python
from ..db.migrations import get_db
from ..agents.store import get_agent_store
from ..llm.client import LLMMessage, get_llm_client
```

### Singletons
`get_agent_store()`, `get_project_store()`, `get_session_store()`, `get_mission_store()`, `get_pattern_store()`, `get_memory_manager()`, `get_llm_client()`, `get_workflow_store()`

### Templates
Extend `base.html`, blocks: `topbar_actions`, `content`.
Markdown: `{{ content | markdown | safe }}` (strips `<think>`, `[TOOL_CALL]`).

### CSS
`--bg-primary:#0f0a1a`, `--purple:#a855f7`, `--accent:#f78166`. JetBrains Mono. Radius 10px. Sidebar 56px.

### Rules
- ZERO emoji — SVG Feather or text only
- `cleanLLM()` JS + `_clean_llm()` Jinja
- 4 view modes: card, card-simple, list, list-compact
- SSE: `bus.add_sse_listener()`, keepalive 30s, queue 2000
- No `--reload`. No `import platform` top-level. Run from parent dir.

---

## FILE TREE
```
platform/
├── server.py, config.py, models.py, security.py
├── agents/    executor.py(2438L), loop.py, store.py, rlm.py
├── patterns/  engine.py(1727L), store.py
├── missions/  store.py, product.py
├── workflows/ store.py(1760L)
├── sessions/  store.py, runner.py(672L)
├── a2a/       bus.py, protocol.py, veto.py, negotiation.py
├── llm/       client.py
├── memory/    manager.py, project_files.py
├── generators/ team.py
├── metrics/   dora.py
├── rbac/      __init__.py
├── tools/     build_tools.py, code_tools.py, git_tools.py, web_tools.py
├── projects/  manager.py
├── skills/    library.py, definitions/*.yaml (75)
├── db/        schema.sql, migrations.py
├── deploy/    Dockerfile, docker-compose-vm.yml, nginx-vm.conf
├── web/
│   ├── routes.py (8575L)
│   ├── ws.py (SSE)
│   ├── templates/ (44 files)
│   │   ├── base.html, portfolio.html, dsi.html, metier.html, product.html
│   │   ├── ideation.html, ideation_history.html, backlog.html
│   │   ├── ceremonies.html, art.html, toolbox.html, pi_board.html
│   │   ├── mission_control.html, mission_start.html, mission_detail.html
│   │   ├── session_live.html (~1700L), conversation.html
│   │   ├── agents.html, org.html, generate.html, agent_edit.html
│   │   ├── product_line.html, agent_world.html, settings.html
│   │   ├── dora_dashboard.html, monitoring.html, design_system.html
│   │   ├── project_detail.html, project_board.html, project_overview.html
│   │   └── partials/ (svg_sprites.html, msg_unified.html, view_switcher.html)
│   └── static/ css/(3), js/(4), avatars/(SVG+JPG)
└── data/ → ../data/platform.db
```
