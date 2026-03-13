# MACARON AGENT PLATFORM — Architecture

## Distributed
```
PG advisory lock   auto_resume.py   pg_run_lock(int64) conn-scoped non-blocking
                   prevents double-exec . fb=no-op if not PG
Redis rate limit   rate_limit.py    slowapi -> REDIS_URL shared . fb: in-memory
Leader election    evolution_sched  Redis SET NX EX ttl -> first wins
                   key=leader:{task} val=SF_NODE_ID ttl=3600s(GA)/300s(sim) fb=True
Graceful drain     server.py        _drain_flag + asyncio.wait(DRAIN_S)
                   /api/ready->503 -> nginx proxy_next_upstream
Health probes      /api/health(DB+Redis) . /api/ready(503 drain — auth bypass)
```

## Mission Orchestration
```
POST /missions/start -> pg_run_lock(run_id) -> _safe_run()
  -> _mission_semaphore(N) -> run_phases()
    -> sprint_loop(max) -> run_pattern() -> adversarial_guard
    -> PUA retry(L1→L4) -> gate(all_approved|no_veto|always) -> next_phase
```
Semaphore: cfgable. MAX_LLM_RETRIES=2. Auto-resume on restart w/ stagger.
WSJF=(BV+TC+RR)/JD. Feature pull: sorted -> head. MAX_SPRINTS=20.

## Epic Orchestrator — services/epic_orchestrator.py
Phase task via _build_phase_prompt() (NOT workflows/store.py).
Platform detect: _detect_project_platform(ws, brief) ->
  rust-native|macos-native|ios-native|android-native|web-node|web-docker|web-static
Priority: brief keywords -> .stack -> filesystem (Cargo.toml, package.json)

## Adversarial Guard — agents/adversarial.py (Swiss Cheese)
L0 det (0ms): SLOP . MOCK . FAKE_BUILD(+7) . HALLUC . LIE . STACK_MISMATCH(+7)
  CODE_SLOP . ECHO . REPETITION . SECRET . FILE_TOO_LARGE(>200L,+4)
  GOD_FILE(>3types,+3) . COGNITIVE(>25,+4) . DEEP_NEST(>4lvl,+3)
  HIGH_COUPLING(>12imp,+2) . LOC_REGRESSION(+6) . MISSING_UUID_REF
  MISSING_TRACE . FAKE_TESTS . NO_TESTS . SECURITY_VULN . PII_LEAK
  PROMPT_INJECT . IDENTITY_CLAIM . RESOURCE_ABUSE
L1 LLM: skip for network/debate/aggregator/HITL
Score: <5=pass . 5-6=soft . >=7=reject
Force reject: HALLUC/SLOP/STACK_MISMATCH/FAKE_BUILD
MAX_RETRIES=1 (2 attempts) + PUA escalation -> FAILED, output discarded

## PUA Motivation — agents/pua.py (source: tanweai/pua, MIT)
Pressure escalation on adversarial retry: L1=disappointment L2=soul L3=review+5step L4=graduation
Iron Rules + Proactivity injected ALL agent prompts via prompt_builder.py
Debug 5-step: Smell->Elevate->Mirror->Execute->Retrospective
Cross-agent pressure: peer success/failure from run.nodes
build_retry_prompt(): feedback+pressure+debug+peer+task+protocol

## Stack Enforcement Chain
1. _detect_project_platform() -> type from brief/memory/fs
2. _build_phase_prompt() -> platform-specific wf (Cargo vs npm)
3. full_task: "STACK: Rust" -> adversarial guard
4. L0 _check_stack_mismatch() -> wrong-lang=+7
5. Exhaustion -> FAILED, bad code discarded

## Agent Protocols — patterns/engine.py
DECOMPOSE(Lead): list_files->deep_search->subtasks. No lang mix.
EXEC(Dev): list_files->deep_search->memory->code_write. Never fake.
QA: build/test mandatory. Android: build->test->lint. Web: screenshot>=1.
RESEARCH: deep_search+memory. Read only.
Role match: dev|lead|veloppeur|engineer|coder|tdd|worker|fullstack|back|front

## Traceability — traceability/ + ops/traceability_scheduler.py
Team: trace-lead(Nadia) . trace-auditor(Mehdi) . trace-writer(Sophie) . trace-monitor(Lucas)
Role: "traceability" in classifier → tools: legacy_scan, link, coverage, validate + code + git
Scheduler: every 6h all active projects. Phase1=lightweight(no LLM). Phase2=mission if <80%
Workflow: traceability-sweep.yaml (4 phases: audit→fix→validate→memory-sync)
PM v2: auto-insert traceability-check after dev, always for migrations
DB: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(src→tgt)
Tools: legacy_scan . traceability_link . traceability_coverage . traceability_validate

## Adaptive Intelligence
```
Thompson   selection.py    Beta(w+1,l+1) . cold<5->uniform [0.4,0.6]
Darwin     darwin.py       team tournament . elim bottom-N . mutate top
Evolution  evolution.py    GA genome=PhaseSpec[] . fitness=success*quality . pop=40 . nightly
RL         rl_policy.py    Q-learning . state=(wf,phase,rej%,quality) . e=0.1
Skills     skill_health.py det tools+LLM judge -> improve
AC         ac/             reward(14d) convergence experiments skill_thompson
```
DB: agent_scores . evolution_proposals/runs . rl_experience . ac_cycles . ac_project_state

## Jarvis (CTO + A2A)
strat-cto = exec CTO -> delegates RTE/PO/SM/teams.
A2A (LF v1.0): /.well-known/agent.json . POST /a2a/tasks . GET /a2a/events(SSE)
MCP: mcp_lrm/mcp_jarvis.py -> jarvis_ask() jarvis_status()
LLM routing (AZURE_DEPLOY=1): reason->5.2 . code->5.2-codex . default->5-mini
CTO tools: create_{project,mission,sprint,feature,story} . launch_epic_run . check_run_status

## Scheduled Ops (15 bg tasks from server.py lifespan)
auto_resume(5min) . evolution(02:00 nightly GA+RL) . traceability(6h sweep+mission)
auto_heal(60s) . platform_watchdog . endurance_watchdog . zombie_cleanup . mcp_watchdog
heal_seed . darwin_seed . simulator_seed . redis_sse . pg_notify

## Innovation Cluster
```
n2(nginx lb) sfadmin@40.89.174.75  SSH=~/.ssh/sf_innovation_ed25519
n1(primary)  sfadmin@10.0.1.4      via ProxyJump n2
n3(PG+Redis) 10.0.1.6
nginx: upstream sf_api_ha (n1:8090+n2:8090) proxy_next_upstream http_503
Deploy: rsync+chown+systemctl . CI: deploy-demo.yml
```

## Security — arXiv:2602.20021
```
L0 adversarial(det)   -> PROMPT_INJECT.IDENTITY.RESOURCE.PII.SECRET
L1 adversarial(LLM)   -> semi-formal (arXiv:2603.01896)
Tool guards(pre)      -> path/file blocklist . MAX_TOOL_CALLS=50
Memory sanitize       -> sanitize_agent_output + URL warn
A2A validation        -> from_agent identity + scope log
Audit trail           -> admin_audit_log destructive actions
Sandbox(Docker)       -> per-agent UID . --network none . mem 512m
```

## Auth — auth/
JWT+bcrypt+rate-limit. Password reset: 6-digit code via AWS SES (auth/ses.py)
Code hashed SHA-256, 15min expiry, max 5 attempts. No email enumeration.
Routes: forgot-password, verify-reset-code, reset-password (all PUBLIC_PATHS)

## DB — db/adapter.py
is_postgresql() gates PG feats (advisory lock, NOTIFY/LISTEN).
PgConnectionWrapper from pool . SQLite fb: data/platform.db.
schema_pg.sql(61tbl) first -> migrations.py second (incremental).
executescript() w/ savepoints. execute() full rollback on err.

## LLM — FROZEN
```
local-mlx   Qwen3.5-mlx(:8080)         ollama-compat
minimax     M2.5                        native tool_calls . no mangle . no temp
azure-oai   gpt-5-mini/5.2/5.2-codex   AZURE_DEPLOY=1
azure-ai    gpt-5.2                     swedencentral
nvidia      Kimi-K2                     integrate.api.nvidia.com
```
MiniMax: `<think>`+json fences stripped (NEVER produce empty — keep original fb)
parallel_tool_calls=False . GPT-5.x: reasoning . max_completion_tokens . budget>=16K

## Gotchas
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- HTTP 400 tool msg ordering (role=tool after tool_calls) — non-fatal
- Container: /app/macaron_platform/ not /app/platform/
- PG advisory lock: conn-scoped -> dedicated conn/mission
- Leader election: fb=True if Redis down (idempotent safe)
- /api/ready in PUBLIC_PATHS (auth bypass)
- SSE: `curl --max-time` — urllib blocks
- Epic orch: _build_phase_prompt() not workflows/store.py
- Role "Lead Developpeur": "lead"+"veloppeur" (accent-safe)
- Think-strip: NEVER return empty — 3-layer safety (client→executor→engine)

## Stats
~215 agents · 26 patterns · 29 phase tpl · 50 workflows · 57 tool mods · 1091 skills
4 bricks · 123 tpl · 375py/148KLOC · 61 PG tbl · 17 ops · 5 LLM providers · 15 bg tasks
