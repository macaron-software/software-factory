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
    -> gate(all_approved|no_veto|always) -> next_phase
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
MAX_RETRIES=1 (2 attempts) -> FAILED, output discarded

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
CTO tools: create_{project,mission,sprint,feature,story} . launch_epic_run . check_run_status . resume_run

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
MiniMax: `<think>`+json fences stripped . parallel_tool_calls=False
GPT-5.x: reasoning . max_completion_tokens not max_tokens . budget>=16K

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
- Watchdog retry: needs auth — spams 401 if no cookie
