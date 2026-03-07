# MACARON AGENT PLATFORM

## WHAT
Web multi-agent platform SAFe-aligned. Agents collaborate (debate/veto/delegate) autonomously.
FastAPI + HTMX + SSE. PostgreSQL (primary) / SQLite (fallback). Dark purple. Port 8099/8090.

## RUN (local dev — SQLite)
```bash
cd _SOFTWARE_FACTORY
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# NO --reload | --ws none mandatory | DB: data/platform.db (parent dir)
```

## ⚠️ CRITICAL RULES
- **NEVER delete data/platform.db** — init_db() idempotent migrations
- **NEVER set \*\_API_KEY=dummy** — keys from ~/.config/factory/*.key or Infisical
- **NEVER `import platform`** top-level (shadows stdlib)
- **NEVER `--reload`** (same reason)
- **NEVER kill -9 all python3** — kills platform too

## COPILOT CLI — SERVER LAUNCH
```
ALWAYS: nohup + & (detached)
  nohup python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none > /tmp/macaron-platform.log 2>&1 &
VERIFY: curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/
KILL:   lsof -ti:8099 | xargs kill -9
```

## SF INNOVATION CLUSTER (prod)
```
node-2 (nginx lb) : sfadmin@40.89.174.75   SSH_KEY=~/.ssh/sf_innovation_ed25519
node-1 (primary)  : sfadmin@10.0.1.4       via ProxyCommand through node-2
node-3 (PG+Redis) : 10.0.1.6               PostgreSQL 16 + Redis 7

nginx: sf.veligo.app → upstream sf_api_ha (node-1:8090 + node-2:8090)
       sf_master_ha: node-1 primary, node-2 backup (SSE/pages)
       zone 64k + proxy_next_upstream http_503 → auto-evicts draining node

Deploy 5 files to node-2: scp -i KEY files sfadmin@40.89.174.75:/home/sfadmin/platform/<path>/
Deploy to node-1: scp -o "ProxyCommand=ssh -W %h:%p -i KEY sfadmin@40.89.174.75" -i KEY files sfadmin@10.0.1.4:/home/sfadmin/platform/<path>/
Kill stale: sudo ss -tlnp | grep 8090 → sudo kill -9 <PID>
Restart: sudo systemctl restart macaron-platform-blue
Verify: curl http://localhost:8090/api/health | curl http://localhost:8090/api/ready
node .env: SF_NODE_ID=sf-node-1|2 · REDIS_URL=redis://10.0.1.4:6379 · PG_DSN=postgresql://...
```

## DISTRIBUTED PATTERNS (LIVE)
```
PG advisory lock   auto_resume.py   pg_run_lock() → pg_try_advisory_lock(int64)
                   prevents double-execution across nodes (connection-scoped, non-blocking)
                   falls back to no-op if not postgresql

Redis rate limiter rate_limit.py    slowapi storage_uri=REDIS_URL → shared limits multi-node
                   fallback: in-memory if REDIS_URL not set or Redis down

Leader election    evolution_scheduler.py  Redis SET NX EX ttl → first node wins
                   key=leader:{task_name} val=SF_NODE_ID ttl=3600s (evolution), 300s (simulator)
                   server.py: leader election for simulator seed
                   fallback: returns True if Redis unavailable

Graceful drain     server.py        _drain_flag + asyncio.wait(tasks, timeout=SF_DRAIN_TIMEOUT_S)
                   /api/ready returns 503 while draining → nginx proxy_next_upstream removes node

Health probes      /api/health      DB+Redis checks, returns checks:{db, redis}
                   /api/ready       503 on drain or DB fail — public (auth bypass)
                   nginx: max_fails=2 fail_timeout=10s + proxy_next_upstream http_503
```

## DEPLOY (Azure VM 4.233.64.30 — Docker)
```bash
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete --exclude='__pycache__' --exclude='*.pyc' --exclude='data/' --exclude='.git' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "cd /opt/macaron && docker compose --env-file .env \
  -f platform/deploy/docker-compose-vm.yml up -d --build --no-deps platform"
# Hotpatch: tar + docker cp + docker restart (lost on --build → rsync BEFORE rebuild)
# Container path: /app/macaron_platform/ | Auth: admin@macaron-software.com/macaron2026
# Prod LLM: azure-openai gpt-5-mini (AZURE_DEPLOY=1 → no fallback)
```

## GIT (2 repos)
```
~/_MACARON-SOFTWARE/   .git → GitHub macaron-software/software-factory  (tracké)
  _SOFTWARE_FACTORY/  runtime local NON tracké (.gitignore)

~/_LAPOSTE/            .git → GitLab udd-ia-native/software-factory (squelette vide)
  sync: cd ~/_MACARON-SOFTWARE && ./sync-to-laposte.sh  (one-way, ⚠️ ne jamais éditer)
```

## STACK
FastAPI + Jinja2 + HTMX + SSE (no WS) · Zero build step · Zero emoji (SVG Feather only)
PostgreSQL 16 WAL + FTS5 (~35 tables) — SQLite fallback for local dev
Infisical REST API for secrets (INFISICAL_TOKEN) — .env fallback
133+ agents (95 YAML defs) · 12 patterns · 19 workflows · 1271 skills

---

## SAFe VOCABULARY
Epic=MissionDef · Feature=FeatureDef · Story=UserStoryDef · Task=TaskDef
PI=MissionRun · Iteration=SprintDef · ART=agent teams · Ceremony=SessionDef
```
Portfolio → Epic (WSJF) → Feature → Story → Task
ART → PI → Iteration → Ceremony → Pattern
```

---

## MISSION ORCHESTRATION
```
POST /api/missions/start → pg_run_lock(run_id) [PG advisory] → _safe_run()
  → _mission_semaphore(N) → MissionOrchestrator.run_phases()
    → sprint loop(max_sprints) → run_pattern() → adversarial guard
    → gate (all_approved|no_veto|always) → next phase
```
- `_mission_semaphore`: configurable (default 1) — settings/orchestrator
- `MAX_LLM_RETRIES=2` · non-dev phases: max_sprints=1 · gate `always` → DONE_WITH_ISSUES
- Auto-resume on restart: ALL paused missions re-launched with stagger
- WSJF: (BV + TC + RR) / JD · sliders in creation form

---

## BOUCLE SPRINT
```
Jarvis → create_project/epic → PM → create_feature/story (WSJF) → RTE → launch_epic_run → Workflow YAML
  Phase non-dev: 1 seul pass | Phase dev: for sprint in range(1, max+1)
  Sprint N: MVP feature WSJF → rétro LLM → sprint N+1 → sprint final → CI/CD handoff
  Failure → retry + feedback | max atteint → continue (non-bloquant)
```
Feature pull: `product_backlog.list_features(epic_id)` trié WSJF → head of prompt each sprint
Limits: `MAX_SPRINTS_GATED=20` (TDD) · `MAX_SPRINTS_DEV=20` (dev) · override: `config.max_iterations: N`

---

## ADVERSARIAL GUARD (agents/adversarial.py)
**L0 deterministic (0ms):** SLOP · MOCK · FAKE_BUILD(+7) · HALLUCINATION · LIE · STACK_MISMATCH(+7) · TOO_SHORT · ECHO · REPETITION
**L1 LLM semantic:** skipped for network/debate/aggregator/HITL
**Scoring:** <5=pass · 5-6=soft-pass · ≥7=reject · HALLUCINATION/SLOP/STACK_MISMATCH/FAKE_BUILD → force reject
`MAX_ADVERSARIAL_RETRIES=0` — rejection = warning only

---

## AGENT PROTOCOLS (patterns/engine.py)
**DECOMPOSE (Lead):** list_files → deep_search("build tools, SDK") → subtasks. No lang mixing.
**EXEC (Dev):** list_files → deep_search → memory_search → THEN code_write. Never fake builds.
**QA:** build/test tool mandatory. Android: android_build→test→lint. Web: browser_screenshot ≥1.
**RESEARCH (Discussion):** deep_search + memory_search. Read only, no code_write.

---

## LLM ENVIRONMENTS
```
SF Innovation (prod) │ azure-openai │ gpt-5-mini  │ no fallback (AZURE_DEPLOY=1)
Azure VM (demo)      │ azure-openai │ gpt-5-mini  │ no fallback
Local dev            │ minimax      │ MiniMax-M2.5│ → azure-openai
```
Provider: PLATFORM_LLM_PROVIDER + PLATFORM_LLM_MODEL env vars
Azure: max_completion_tokens (NOT max_tokens) · MiniMax: strips <think> auto
Rate limit: 15 rpm (in-memory) or Redis-backed (REDIS_URL set)
Keys: ~/.config/factory/*.key (local) | Infisical | .factory-keys/ volume (docker)

---

## DB ADAPTER (db/adapter.py)
`is_postgresql()` → gates PG-specific features (advisory lock, NOTIFY/LISTEN)
`get_connection()` → PgConnectionWrapper from pool
`get_db()` → sqlite3 or psycopg3 cursor (same API via adapter)
SQLite fallback: `PG_DSN` not set → uses data/platform.db

---

## KEY FILES
```
server.py              lifespan, _drain_flag, _is_draining(), auth middleware (/api/ready bypass)
rate_limit.py          slowapi limiter, Redis storage_uri when REDIS_URL set
services/auto_resume.py  _launch_run(), _safe_run(), pg_run_lock() ctx manager
agents/evolution_scheduler.py  _try_become_leader(), _run_evolution_cycle()
agents/selection.py    Thompson Sampling Beta bandit
agents/executor.py     LLM tool-calling loop (max 15 rounds)
agents/tool_runner.py  all tools dispatch + android redirect
patterns/engine.py     run_pattern() 8 topologies, adversarial guard, RL hook
web/routes/api/health.py  /api/health (DB+Redis) + /api/ready (drain probe)
web/routes/pages.py    /settings (infra={db_type,redis_url,node_id,drain_timeout})
db/adapter.py          is_postgresql(), get_connection(), PgConnectionWrapper
```

## FILE TREE
```
platform/
├── server.py, config.py, models.py, rate_limit.py
├── agents/    executor.py, loop.py, store.py, rlm.py, adversarial.py,
│              tool_runner.py, tool_schemas.py, selection.py,
│              evolution.py, evolution_scheduler.py, simulator.py, rl_policy.py
├── patterns/  engine.py, store.py
├── services/  mission_orchestrator.py, auto_resume.py
├── workflows/ store.py
├── sessions/  store.py, runner.py
├── a2a/       bus.py, protocol.py, veto.py, negotiation.py
├── llm/       client.py, observability.py
├── memory/    manager.py, project_files.py
├── db/        schema.sql, migrations.py, adapter.py
├── tools/     android_*, build, code, git, web, security, deploy,
│              chaos, phase, platform, compose, azure, memory, mcp_bridge
├── web/routes/ missions.py, pages.py, sessions.py, workflows.py,
│               projects.py, agents.py, api/{health,settings,analytics}.py
│   ws.py · templates/(64) · static/css(3) js(4+) avatars/
└── data/ → ../data/platform.db (SQLite local) or PostgreSQL via PG_DSN
```

---

## JARVIS — A2A/ACP SERVER
```
Jarvis = strat-cto agent, executive CTO, délègue à RTE/PO/SM/teams
RULE: NEVER insert DB records manually — toujours passer par Jarvis (/api/cto/message)

A2A spec: Linux Foundation A2A v1.0 (ex-ACP BeeAI/IBM, merged Q3 2025)
Endpoints (public, no auth):
  GET  /.well-known/agent.json    → Agent Card (discovery)
  POST /a2a/tasks                 → Submit task {"input":{"parts":[{"kind":"text","text":"..."}]}}
  GET  /a2a/tasks/{id}            → Status + result
  GET  /a2a/events?task_id={id}   → SSE streaming
  POST /a2a/tasks/{id}/cancel     → Cancel

Code: platform/web/routes/a2a_server.py
Auth bypass: /.well-known/* + /a2a/* via auth/middleware.py PUBLIC_PATHS

MCP Jarvis (stdio bridge → A2A): mcp_lrm/mcp_jarvis.py
  Registered in: ~/.claude/settings.json · ~/.config/opencode/opencode.json
                 ~/.config/github-copilot/copilot-cli/mcp.json
  Tools: jarvis_ask(message) · jarvis_status(task_id) · jarvis_task_list() · jarvis_agent_card()

LLM ROUTING (Azure, AZURE_DEPLOY=1):
  PLATFORM_LLM_PROVIDER=azure-openai  PLATFORM_LLM_MODEL=gpt-5-mini  AZURE_DEPLOY=1
  reasoning/leadership (CTO,PO,SM,arch) → gpt-5.2
  code/tests/QA/devops                  → gpt-5.1-codex
  tasks/generic                         → gpt-5-mini
  Settings UI → LLM tab: DB routing config (session_state key=llm_routing)
  routing.py _select_model_for_agent(): AZURE_DEPLOY=1 → use Settings DB routing
                                        AZURE_DEPLOY unset → local dev hardcoded path

ROLE_TOOL_MAP["cto"] = delegation tools only (NO developer tools)
  create_project, create_mission(workflow_id REQUIRED+enum), launch_epic_run,
  check_run_status, resume_run, create_sprint, create_feature, create_story,
  web_search, web_fetch, memory_*, get_project_context, platform_*
  YAML: skills/definitions/strat-cto.yaml (source of truth → overwrites DB on restart)
  POST-RESTART: must re-run /tmp/fix_agent5.sql (tools_json+system_prompt update)
```

## AGENT SCOPE MODEL
```
4 scopes — détermine ce qu'un agent peut lire/écrire/appeler

platform  Jarvis/CTO            lit tous projets · NO code_write · NO build/test
                                 outils: platform_agents, platform_missions, create_project, deploy_*
                                 délègue vers: art | project | self

art       Lead ART / RTE        lit projets de son ART · platform API read-only
                                 délègue vers: project uniquement

project   PM/dev/qa/docs/TMA/   scope = project_id de la session courante SEULEMENT
          sécu/dette             can_write = workspace/{project_id}/ uniquement
                                 build/test → exécution dans Docker du projet
                                 platform_agents/platform_missions → INTERDIT (passer par Jarvis)
                                 un agent peut être sur N projets, scope imposé par la session

self      AC/Evolution/          project_id="self" = PLATFORM_ROOT (la SF elle-même)
          Watchdog/Quality       R+W: skills/ templates/ workflows/ — PAS auth/ rbac/ data/platform.db
                                 platform API read-only (metrics, sessions)
```

Clé enforcement — agents/permissions.py:
```python
# Scope résolu depuis: agent.permissions["scope"] + session.project_id
# Layer 6 (NEW): check_scope(agent_scope, tool_name, session_project_id)
#   scope=project → platform_agents/missions/create_project → DENIED
#   scope=project → tool file args hors workspace/{project_id}/ → DENIED
#   scope=self    → path hors PLATFORM_ROOT → DENIED ; auth/ rbac/ → DENIED

# Hiérarchie délégation A2A (a2a/bus.py check_delegation_allowed):
#   platform → tous | art → même ART | project → même projet | self → platform(R)+self
```

Fichiers clés scope:
```
agents/permissions.py      check_scope(), check_delegation() — Layer 6+7
agents/store.py            AgentDef.permissions["scope"] — default "project"
agents/tool_schemas/_mapping.py  ROLE_TOOL_MAP: cto=platform_*, dev=NO platform_*
a2a/bus.py                 check_delegation_allowed()
db/migrations.py           ensure_self_project() au bootstrap
```

Agents spécialisés (tous scope=project sauf mention):
```
docs      R workspace · W /docs/ uniquement · NO git_commit sur code
security  R workspace · W rapport sécu · outils: trivy/bandit dans Docker projet
tech-debt R only · peut créer issues/stories via backlog tools
TMA       R+W code · git_commit · build/test Docker · NO deploy_* (CI/CD pipeline)
AC/evo    scope=self · R+W skills/templates/workflows · NO data/platform.db
```

---

## KNOWN ISSUES / GOTCHAS
- `NodeStatus`: PENDING/RUNNING/COMPLETED/VETOED/FAILED — **NO `DONE`**
- Landlock LSM sandbox: binary at `tools/sandbox/dist/landlock-runner-linux-x86_64`
  Enable on OVH: `cp tools/sandbox/dist/landlock-runner-linux-x86_64 tools/sandbox/landlock-runner && chmod +x tools/sandbox/landlock-runner`
  Then set `LANDLOCK_ENABLED=true` in env or `security.landlock_enabled: true` in config
- HTTP 400 tool message ordering `role 'tool' must follow 'tool_calls'` — non-fatal
- `_mission_semaphore` configurable now (settings → Orchestrator) — was hardcoded 1
- Container path: `/app/macaron_platform/` (NOT `/app/platform/`)
- UID mismatch Azure: /opt/macaron owned 501, azureadmin=1001 → docker cp
- SF Innovation node restart: must kill stale PID on 8090 before systemctl start
- `/api/ready` must be in auth bypass list (server.py middleware phase 2)
- PG advisory lock: connection-scoped → dedicated conn kept open for mission duration
- Leader election fallback=True if Redis down (GA/seeder are idempotent → safe)

---

## ADAPTIVE INTELLIGENCE
```
Layer 1 LIVE   Thompson Sampling   agents/selection.py     per-agent-slot Beta bandit
Layer 2 PLAN   Genetic Algorithm   agents/evolution.py     nightly workflow evolution
Layer 3 PLAN   Reinforcement Learning agents/rl_policy.py  mid-mission pattern adapt
```
**Thompson:** Beta(accepted+1, rejected+1) · cold-start <5 iter → uniform [0.4,0.6]
**GA:** genome=PhaseSpec[] · fitness=success_rate×quality · population=40 · nightly 02:00
  leader election: only one node runs GA (Redis SETNX)
**RL:** Q-learning · state=(wf_hash, phase_idx, reject_pct, quality) · ε=0.1
**DB:** agent_scores · evolution_proposals · evolution_runs · rl_experience

---

## AC — AMÉLIORATION CONTINUE

### Architecture (scope séparation CRITIQUE)
```
AC self-improvement team (coach/watchdog/monitor)
  → scope: platform/ code uniquement → commit → push GitHub → GH Actions → tous les serveurs

AC cycle workflow (architect/codex/adversarial/qa/cicd)
  → scope: pilot project workspace → code + tests + Docker
  ⚠️ NE TOUCHE PAS platform/ — pas son scope

Pilot projects (ac-hello-html, ac-fullstack-rs, ac-hello-vue)
  → chacun: workspace dir + git init + Dockerfile + workspace_path en DB
  → workspace RÉINIT à chaque cycle (git reset --hard <seed_sha>)
```

### Workflow ac-improvement-cycle (6 phases)
```
ac-inception → ac-tdd-sprint (loop, max_iter=3) → ac-adversarial-check
  → ac-qa-sprint (parallel: ac-qa-agent + ft-e2e-ihm) → ac-cicd → ac-coach-review
```
- VETO → recode (tdd-sprint reloop) · rollback → git revert + cycle N-1
- Coach lit scores N derniers cycles → écrit STRATEGY_N+1.md → architect lit au démarrage

### DB Tables AC
```
ac_project_state  project_id, current_cycle, status, current_run_id, seed_sha
ac_cycles         project_id, cycle_num, total_score, rl_reward, defect_count,
                  experiment_id, rolled_back
ac_experiments    project_id, cycle_num, experiment_key, variant_a, variant_b,
                  score_before, score_a, score_b, winner, rolled_back, strategy_notes
ac_skill_scores   skill_id, variant, wins, losses, avg_score, last_updated
```

### Pilot Projects — _AC_PROJECTS (pages.py:602)
```
ac-hello-html    tier=simple        html+css+nginx     max_cycles=20
ac-hello-vue     tier=simple-compile vue+vite+node     max_cycles=20
ac-fullstack-rs  tier=medium        rust+sveltekit+pg  max_cycles=20
```
- Définis dans _AC_PROJECTS list (NOT dans projects registry)
- ⚠️ ROOT CAUSE "no software": workspace_path absent en DB → code_write ne sait où écrire
- Fix requis: enregistrer en DB (projects table, path=DATA_DIR/workspaces/{project_id})
  + scaffold_project() (idempotent) + seed commit + reinit chaque cycle

### Workspace Flow par cycle
```
1. api_improvement_start → ensure project registered (projects table, path set)
2. scaffold_project() si missing → git init + Dockerfile seed + README + git commit (seed_sha)
3. Reinit: save ADVERSARIAL_{N-1}.md + CICD_FAILURE_{N-1}.md → git reset --hard seed_sha
           → git clean -fd → restore feedback files
4. Session créée avec project_id → runner.py charge project.path → injecté comme project_path
5. ac-codex code_write → path DOIT être sous DATA_DIR/workspaces/ (allowed root)
6. docker_deploy(cwd=workspace_path) → build + run container
```

### Intelligence AC (reward + RL + Thompson + GA + Convergence)
```
reward.py       ac_reward() → R∈[-1,+1] : quality(40%) + adversarial(30%) + trace(15%)
                + efficiency(10%) + regression(5%) · VETO absolu si dim critique < 60
rl_policy.py    record_experience() après inject_cycle · recommend() → next_cycle_hint
                hint stocké dans ac_project_state.next_cycle_hint (JSON)
skill_thompson  ac_skill_select_variant(skill_id) → Beta sampling · A/B: v1 vs v2 skills
                ac_skill_record() dans inject_cycle · tier fallback inter-projets
convergence.py  converging / plateau / regression / spike_failure / cold_start
                plateau → GA evolve() immédiat · regression → adversarial deep-dive
                spike_failure → skill eval sur tous les skills AC
```

### A/B Testing + Rollback
```
Experiments: record_experiment(project_id, cycle_num, key, variant_a, variant_b)
Rollback trigger: score[N] < score[N-1] - 10 → POST /api/improvement/rollback/{project_id}
  → git revert workspace + DELETE ac_cycles WHERE cycle_num=current + current_cycle=N-1
Coach écrit: STRATEGY_N+1.md (variante gagnante + ajustements prompts)
Skills v2: ac-codex-v2.md · ac-adversarial-v2.md (Thompson choisit chaque cycle)
```

### Auto-resume (server.py lifespan)
```
Après mark_orphaned_sessions() → trouve sessions AC interrompues (last 24h, config.ac=True)
DISTINCT ON project_id → only most recent per project → _run_workflow_background()
[skip deploy] tag sur commits → force deploy via commit vide séparé
```

### GH Actions (ac-launch.yml)
```
Actions: start-or-resume | status-only | force-restart
Auth: JWT cookie jar /tmp/sf-cookies.txt
Diagnostics: sessions + epic_runs + messages + ac_cycles scores + workspace paths + Docker
Prod: SSH sfadmin@52.143.158.19 (SF_NODE1_IP) · port 8091 · PG 10.0.1.6:5432/sfplatform
```

### Dashboard AC (/art → Amélioration Continue)
```
Tabs: Intelligence | RL | Thompson | GA | Self Healing (NEW)
Self Healing: /api/autoheal/stats + /api/incidents + /api/chaos/history
  KPIs: incidents open/investigating/resolved + epics completed/failed + heartbeat
  Manuel: POST /api/autoheal/trigger + POST /api/chaos/trigger
Graph équipe: _AC_AGENTS_GRAPH → coach/architect/codex/adversarial/qa/cicd (PAS watchdog seul)
Métrique "Score par cycle" : barre orange = 1 seul cycle → normal (cold_start)
```


---

## SECURITY — arXiv:2602.20021 Mitigations

**Reference:** "Red-Teaming Autonomous LLM Agents in Live Labs" (arXiv:2602.20021, Feb 2026)
11 case studies of red-teaming autonomous LLM agents. Full coverage (11/11 CS addressed):

### Case Study → Mitigation Map

| CS | Threat | Mitigation | File |
|---|---|---|---|
| CS1 Disproportionate response | Destructive self-action via social engineering | `RESOURCE_ABUSE` L0 + `MAX_TOOL_CALLS` | `adversarial.py`, `executor.py` |
| CS2 Non-owner compliance (SBD-01) | Agents comply with non-owner instructions | A2A `_check_delegation_scope()` + owner_id | `a2a/bus.py` |
| CS3 PII disclosure | Sensitive data embedded in output/code | `PII_LEAK` L0 (+7) + sensitive file blocklist | `adversarial.py`, `code_tools.py` |
| CS4 Resource looping (SBD-04) | Induced infinite loops consuming resources | `RESOURCE_ABUSE` L0 (+7) — busy-loops, fork bombs | `adversarial.py` |
| CS5 DoS storage (SBD-05) | Mass storage creation without bound | `MAX_TOOL_CALLS_PER_RUN=50` hard budget | `executor.py` |
| CS6 Provider values | LLM provider biases silently alter behavior | **Intentionally not mitigated** — inherent to LLM | N/A |
| CS7 Agent harm (SBD-08) | Destructive file ops under manipulation | Sensitive file blocklist + audit trail | `code_tools.py`, `security/audit.py` |
| CS8 Identity spoofing (SBD-06) | Cross-channel display-name spoofing | A2A `from_agent` validation + `IDENTITY_CLAIM` L0 | `a2a/bus.py`, `adversarial.py` |
| CS9 Cross-agent capability transfer | Unsafe skill propagation between agents | Memory sanitization limits poisoned knowledge | `memory/manager.py` |
| CS10 Agent corruption via external resource | Gist/Pastebin URL in memory → remote injection | `EXTERNAL_RESOURCE` L0 (+6) + WARNING log on write | `adversarial.py`, `memory/manager.py` |
| CS11 Libelous broadcast | Mass email/post after impersonation | `IDENTITY_CLAIM` L0 + `MAX_TOOL_CALLS` (no outbound tools) | `adversarial.py`, `executor.py` |

### SBD Code → Implementation

| SBD | Description | Mitigation | Score |
|---|---|---|---|
| SBD-02/03 | Info disclosure | `_SENSITIVE_FILE_RE` blocklist on read/write | block |
| SBD-04 | DoS / resource abuse | `RESOURCE_ABUSE` L0 | +7 |
| SBD-05 | Resource consumption | `MAX_TOOL_CALLS_PER_RUN=50` | hard stop |
| SBD-06 | Identity spoofing | `from_agent` + `IDENTITY_CLAIM` L0 | +7 |
| SBD-07/10 | Cross-agent propagation | `sanitize_agent_output` on all memory writes | strip |
| SBD-08 | Destructive actions | Blocklist + `audit_log` | block+log |
| SBD-09 | Prompt injection | `PROMPT_INJECTION` L0 in output + tool results | +8/+6 |
| SBD-11 | Fake completion | `FAKE_BUILD`/`MOCK`/`HALLUCINATION` (pre-existing) | +4/+7 |
| SBD-01 | Unauthorized compliance | A2A `_check_delegation_scope()` (log-only) | log |

### Swiss Cheese Defense Model
```
L0 adversarial (deterministic, 0ms)  → PROMPT_INJECTION · IDENTITY_CLAIM · RESOURCE_ABUSE
                                        EXTERNAL_RESOURCE · PII_LEAK · HARDCODED_SECRET
L1 adversarial (LLM semantic, ~5s)   → holistic review
Tool guards (sync, before execution) → path/file blocklist, tool budget
Memory sanitization (on write)       → sanitize_agent_output + URL warning (CS10)
A2A validation (on publish)          → from_agent identity + scope logging
Audit trail                          → admin_audit_log on destructive actions
```

### Intentional Non-Mitigations
- **CS6 — Provider values**: LLM provider biases/refusals are intrinsic to the model, not observable at platform level. No mitigation possible; monitor via L1 adversarial reviews.
- **No hard-block on A2A from_agent mismatch** — would break legitimate cross-session delegation (log+flag instead)
- **No Landlock/Docker per agent** — Phase 3+ (scope hierarchy plan)
- **No RBAC at runtime tool dispatch** — separate initiative (scope hierarchy plan)
- **No PII scrubbing on output text** — only code_write scanned; full NLP PII detection is Phase 3+
