# MACARON AGENT PLATFORM — Technical Reference

## WHAT
Multi-agent SAFe platform. ~193 agents, 12 patterns, 19 wf.
FastAPI+HTMX+SSE. PG16+Redis7. Port 8099(dev)/8090(prod). Dark purple UI.

## CRITICAL RULES
- NEVER delete `data/platform.db` — init_db() idempotent
- NEVER `import platform` top-level — shadows stdlib
- NEVER `--reload` — same stdlib issue
- NEVER `*_API_KEY=dummy` — keys from Infisical / `~/.config/factory/*.key`
- NEVER change LLM model deployments — if LLM err → check network/auth
- NO emoji (SVG Feather) · NO WebSocket (`--ws none`)

## RUN
```bash
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# Detached: nohup ... > /tmp/sf.log 2>&1 &
# Verify:   curl -so/dev/null -w "%{http_code}" http://localhost:8099/
```

## TEST
```bash
ruff check platform/ --select E9                  # syntax (HARD)
python scripts/complexity_gate.py platform/        # CC+MI+LOC (SOFT)
python -m pytest tests/test_platform_api.py -v     # API (needs PG)
```

## STACK
Python 3.11 · FastAPI · Jinja2 · HTMX · SSE · PG16 WAL+FTS5 (~35 tables)
SQLite fb (no PG_DSN) · Redis 7 (rate limit, leader election) · Infisical secrets

## QUALITY GATES (17 layers)
| # | Gate | Block |
|---|------|-------|
| 1 | Guardrails — regex destructive-action | HARD |
| 2 | Veto hierarchy — ABSOLUTE/STRONG/ADVISORY | HARD |
| 3 | Prompt injection — score 0-10, block@7 | HARD |
| 4 | Tool ACL — 5 layers (ACL, sandbox, rate, write, git) | HARD |
| 5 | Adversarial L0 — slop/mock/cheat/hallucination | HARD |
| 6 | Adversarial L1 — LLM semantic | SOFT |
| 7 | AC reward — R∈[-1,+1], 14 dims, 8 critical@60 | HARD |
| 8 | Convergence — plateau/regression/spike | SOFT |
| 9 | RBAC — roles×actions×artifacts | HARD |
| 10-12 | CI: ruff E9 + py_compile + pytest | HARD |
| 13 | CI complexity — radon CC+MI, LOC cap | SOFT |
| 14 | SonarQube (external) | SOFT |
| 15 | Deploy health — blue-green canary | HARD |
| 16 | Output validator | SOFT |
| 17 | Stale builtin pruner | SOFT |

Complexity thresholds: CC fn >10=err >5=warn · LOC >500=err >300=warn · MI <10=err <20=warn

## DISTRIBUTED PATTERNS
```
PG advisory lock    auto_resume.py    pg_run_lock(int64) — conn-scoped, non-blocking
                    prevents double-exec across nodes · fb=no-op if not PG

Redis rate limit    rate_limit.py     slowapi storage_uri=REDIS_URL → shared multi-node
                    fb: in-memory if no Redis

Leader election     evolution_sched   Redis SET NX EX ttl → first node wins
                    key=leader:{task} val=SF_NODE_ID ttl=3600s(GA)/300s(sim)
                    fb=True if Redis down (idempotent tasks)

Graceful drain      server.py         _drain_flag + asyncio.wait(timeout=DRAIN_S)
                    /api/ready→503 → nginx proxy_next_upstream evicts node

Health probes       /api/health       DB+Redis checks → {db,redis}
                    /api/ready        503 on drain/DB fail — auth bypass
```

## MISSION ORCHESTRATION
```
POST /missions/start → pg_run_lock(run_id) → _safe_run()
  → _mission_semaphore(N) → run_phases()
    → sprint_loop(max) → run_pattern() → adversarial_guard
    → gate(all_approved|no_veto|always) → next_phase
```
Semaphore: configurable (settings→Orchestrator). MAX_LLM_RETRIES=2.
Auto-resume: all paused missions re-launched on restart w/ stagger.
WSJF=(BV+TC+RR)/JD. Feature pull: sorted WSJF → prompt head.
Limits: MAX_SPRINTS_GATED=20 · MAX_SPRINTS_DEV=20 · override `config.max_iterations`.

## ADVERSARIAL GUARD (agents/adversarial.py)
L0 deterministic (0ms): SLOP·MOCK·FAKE_BUILD(+7)·HALLUCINATION·LIE·STACK_MISMATCH(+7)·TOO_SHORT·ECHO·REPETITION
L1 LLM semantic: skipped for network/debate/aggregator/HITL
Score: <5=pass · 5-6=soft · ≥7=reject · HALLUCINATION/SLOP/STACK_MISMATCH/FAKE_BUILD → force reject
MAX_ADVERSARIAL_RETRIES=0 — rejection = warning only

## AGENT PROTOCOLS (patterns/engine.py)
DECOMPOSE (Lead): list_files → deep_search → subtasks. No lang mix.
EXEC (Dev): list_files → deep_search → memory_search → code_write. Never fake builds.
QA: build/test mandatory. Android: build→test→lint. Web: browser_screenshot≥1.
RESEARCH: deep_search + memory_search. Read only.

## ADAPTIVE INTELLIGENCE
```
Thompson     selection.py      Beta(wins+1,losses+1) · cold-start <5 → uniform [0.4,0.6]
Darwin       darwin.py         team tournament · eliminate bottom-N · mutate top
Evolution    evolution.py      GA genome=PhaseSpec[] · fitness=success×quality · pop=40 · nightly 02:00
RL           rl_policy.py      Q-learning · state=(wf,phase,reject%,quality) · ε=0.1
Skills       skill_health.py   deterministic tools + LLM judge → improve skills
AC           ac/ (reward+convergence) 14-dim scoring, 8 critical@60, convergence detection
```
DB: agent_scores · evolution_proposals/runs · rl_experience · ac_cycles · ac_project_state

## JARVIS (CTO Agent + A2A Server)
strat-cto = exec CTO. Delegates to RTE/PO/SM/teams.
RULE: never insert DB records manually — use Jarvis (/api/cto/message).

A2A (Linux Foundation v1.0):
  GET /.well-known/agent.json → Agent Card · POST /a2a/tasks → submit
  GET /a2a/tasks/{id} → status · GET /a2a/events → SSE
MCP bridge: mcp_lrm/mcp_jarvis.py → jarvis_ask(), jarvis_status()

LLM routing (AZURE_DEPLOY=1):
  reason(CTO,PO,SM,arch) → gpt-5.2 · code(dev,QA) → gpt-5.2-codex · default → gpt-5-mini
  cfg: Settings UI → LLM tab (session_state key=llm_routing)

CTO tools: create_project, create_mission, launch_epic_run, check_run_status,
  resume_run, create_sprint, create_feature, create_story, web_search, memory_*, platform_*

## SF INNOVATION CLUSTER
```
node-2 (nginx lb)  sfadmin@40.89.174.75   SSH=~/.ssh/sf_innovation_ed25519
node-1 (primary)   sfadmin@10.0.1.4       via ProxyJump node-2
node-3 (PG+Redis)  10.0.1.6               PG16 + Redis 7
```
nginx: upstream sf_api_ha (node-1:8090+node-2:8090) · proxy_next_upstream http_503
Deploy: rsync + chown + systemctl restart · CI: .github/workflows/deploy-demo.yml
OVH demo: Docker blue-green, slots/{blue,green,factory}/, --force-recreate

## LLM CONFIG
```
Local:  local-mlx / Qwen3.5-mlx (port 8080, ollama-compat)
OVH:    minimax / MiniMax-M2.5 (native tool_calls, NO mangling)
Azure:  azure-openai / gpt-5-mini (AZURE_DEPLOY=1)
  routing: reason→gpt-5.2 · code→gpt-5.2-codex · default→gpt-5-mini
  max_completion_tokens (NOT max_tokens) · rate: 15rpm (Redis or in-memory)
```

## DB ADAPTER (db/adapter.py)
is_postgresql() gates PG features (advisory lock, NOTIFY/LISTEN).
PgConnectionWrapper from pool · SQLite fb: data/platform.db.
schema_pg.sql runs first → migrations.py second (incremental ALTER/CREATE).

## FILE MAP
```
platform/
├── server.py           lifespan, drain, auth middleware
├── agents/
│   ├── executor.py     LLM tool-call loop (max 15 rounds)
│   ├── store.py        CRUD + seed + prune stale builtins
│   ├── adversarial.py  L0 deterministic + L1 LLM guard
│   ├── tool_runner.py  all tools dispatch
│   ├── guardrails.py   regex destructive-action block
│   ├── permissions.py  5-layer tool ACL
│   ├── selection.py    Thompson Sampling Beta bandit
│   ├── evolution.py    GA genome=PhaseSpec[]
│   └── rl_policy.py    Q-learning
├── patterns/engine.py  8 topologies, adversarial, RL hook
├── services/           mission_orchestrator, auto_resume
├── a2a/                bus, veto, negotiation, jarvis MCP
├── ac/                 reward, convergence, experiments
├── security/           prompt_guard, output_validator, audit
├── llm/client.py       multi-provider (azure/minimax/local-mlx)
├── db/                 adapter(PG+SQLite), schema_pg, migrations
├── tools/              code, git, deploy, build, web, memory, MCP bridge
├── web/routes/         missions, pages, sessions, workflows, agents
│   templates/(64) · static/ · avatars/
└── rbac/               roles, actions, artifacts
```

## GOTCHAS
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — NO `DONE`
- HTTP 400 tool msg ordering (role=tool must follow tool_calls) — non-fatal
- Container path: `/app/macaron_platform/` not `/app/platform/`
- PG advisory lock: conn-scoped → dedicated conn per mission
- Leader election: fb=True if Redis down (idempotent → safe)
- MiniMax M2.5: native tool_calls. M2.1 legacy: role=tool→user
- `/api/ready` must be in PUBLIC_PATHS (auth bypass)
- SSE: use `curl --max-time` — urllib blocks indefinitely
