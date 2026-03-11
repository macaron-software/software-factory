# MACARON AGENT PLATFORM

## WHAT
Multi-agent SAFe platform. Agents collaborate (debate/veto/delegate) autonomously.
FastAPI+HTMX+SSE. PG16 primary / SQLite fallback. Dark purple. Port 8099/8090.

## RUN
```
cd _SOFTWARE_FACTORY
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# NO --reload · --ws none · DB: data/platform.db | PG_DSN
```

## ⚠ NEVER
- delete data/platform.db — init_db() idempotent
- set *_API_KEY=dummy — keys: ~/.config/factory/*.key | Infisical
- `import platform` top-level (shadows stdlib)
- `--reload` (same reason)
- kill -9 all python3 — kills platform

## SERVER LAUNCH (copilot-cli)
```
nohup python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none > /tmp/macaron-platform.log 2>&1 &
VERIFY: curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/
KILL:   lsof -ti:8099 | xargs kill -9
```

## SF INNOVATION CLUSTER (prod)
```
node-2 (nginx lb): sfadmin@40.89.174.75  SSH=~/.ssh/sf_innovation_ed25519
node-1 (primary):  sfadmin@10.0.1.4      via ProxyCommand thru node-2
node-3 (PG+Redis): 10.0.1.6              PG16 + Redis7
nginx: sf.veligo.app → upstream sf_api_ha · proxy_next_upstream http_503
Deploy: scp -i KEY files sfadmin@40.89.174.75:/home/sfadmin/platform/<path>/
Restart: sudo systemctl restart macaron-platform-blue
Health: curl http://localhost:8090/api/health | /api/ready
```

## DISTRIBUTED (LIVE)
```
PG advisory lock    auto_resume.py     pg_try_advisory_lock → no double-exec
Redis rate limit    rate_limit.py      slowapi REDIS_URL → shared multi-node
Leader election     evolution_sched.py Redis SET NX EX → first node wins
Graceful drain      server.py          _drain_flag → /api/ready 503 → nginx evicts
Health probes       /api/health        DB+Redis · /api/ready drain+DB (auth bypass)
```

## DEPLOY (Azure VM 4.233.64.30)
```
SSH_KEY="$HOME/.ssh/az_ssh_config/RG-MACARON-vm-macaron/id_rsa"
rsync -azP --delete --exclude='__pycache__' --exclude='data/' --exclude='.git' \
  platform/ -e "ssh -i $SSH_KEY" azureadmin@4.233.64.30:/opt/macaron/platform/
ssh -i "$SSH_KEY" azureadmin@4.233.64.30 "cd /opt/macaron && docker compose --env-file .env \
  -f platform/deploy/docker-compose-vm.yml up -d --build --no-deps platform"
# Container: /app/macaron_platform/ · Prod LLM: azure-openai gpt-5-mini (AZURE_DEPLOY=1)
```

## GIT
```
~/_MACARON-SOFTWARE/        .git → GitHub macaron-software/software-factory
  _SOFTWARE_FACTORY/       runtime local (not tracked)
~/_LAPOSTE/                 .git → GitLab udd-ia-native/software-factory (one-way sync)
```

## STATS
207 agents · 33 patterns (26 impls) · 68 workflows · 132 skills · 164 tools · 12 roles · 4 bricks
PG16 WAL+FTS5 ~35 tables · Zero build step · Zero emoji (SVG Feather)

---

## SAFe MAP
Epic=MissionDef · Feature=FeatureDef · Story=UserStoryDef · Task=TaskDef
PI=MissionRun · Iteration=SprintDef · ART=agent teams · Ceremony=SessionDef
`Portfolio → Epic(WSJF) → Feature → Story → Task`
`ART → PI → Iteration → Ceremony → Pattern`

---

## MISSION ORCHESTRATION
```
POST /api/missions/start → pg_run_lock(run_id) → _safe_run()
  → _mission_semaphore(N) → run_phases() → sprint loop(max) → run_pattern()
  → adversarial guard → gate(all_approved|no_veto|always) → next phase
```
- Semaphore configurable (settings/orchestrator, default 1)
- MAX_LLM_RETRIES=2 · non-dev: max_sprints=1 · gate `always` → DONE_WITH_ISSUES
- Auto-resume: all paused missions re-launched on restart w/ stagger
- WSJF: (BV+TC+RR)/JD · sliders in creation form
- Feature pull: product_backlog.list_features(epic_id) sorted WSJF → injected each sprint
- MAX_SPRINTS_GATED=20 (TDD) · MAX_SPRINTS_DEV=20 · override: config.max_iterations

---

## ADVERSARIAL GUARD — agents/adversarial.py (Swiss Cheese)
**L0 det (0ms):** SLOP · MOCK · FAKE_BUILD(+7) · HALLUCINATION · LIE ·
  STACK_MISMATCH(+7) · CODE_SLOP · ECHO · REPETITION · HARDCODED_SECRET ·
  FILE_TOO_LARGE(>200L,+4) · GOD_FILE(>3types,+3) · COGNITIVE_COMPLEXITY(>25,+4) ·
  DEEP_NESTING(>4lvl,+3) · HIGH_COUPLING(>12imports,+2) · MISSING_UUID_REF ·
  MISSING_TRACEABILITY · FAKE_TESTS · SECURITY_VULN · PII_LEAK ·
  PROMPT_INJECTION · IDENTITY_CLAIM · RESOURCE_ABUSE · EXTERNAL_RESOURCE
**L1 LLM semantic:** semi-formal (arXiv:2603.01896) premises→trace→verdict
  skipped for network/debate/aggregator/HITL
**Score:** <5=pass · 5-6=soft · ≥7=reject · HALLUCINATION/SLOP/FAKE_BUILD → force reject
MAX_ADVERSARIAL_RETRIES=0 — rejection = warning only

---

## PROTOCOLS — patterns/engine.py
**DECOMPOSE (lead):** list_files→deep_search("build,SDK")→subtasks. No lang mixing.
**EXEC (dev):** list_files→build→code_read→code_edit/write. MAX 150L/file. ONE class/file.
**QA:** build/test mandatory. Android: android_build→test→lint. Web: screenshot≥1.
**REVIEW:** semi-formal premises→trace→APPROVE/REQUEST_CHANGES
**RESEARCH:** deep_search+memory_search. Read only, no code_write.

---

## PATTERNS — patterns/impls/ (26 files)
solo · sequential · parallel · hierarchical · loop · network/debate · router ·
aggregator · wave · fractal_{worktree,qa,stories,tests} · backprop_merge ·
human_in_the_loop · tournament · escalation · voting · speculative ·
red_blue · relay · mob · map_reduce · blackboard · composite
NodeStatus: PENDING|RUNNING|COMPLETED|VETOED|FAILED (no DONE)

---

## QUALITY — metrics/quality.py (KISS enforcement)
QualityScanner.scan_architecture walks workspace, det checks:
LOC(>200L) · GOD_FILE(>3types) · COG_COMPLEXITY(>25) · DEEP_NESTING(>5) ·
HIGH_COUPLING(>12imports) · cyclomatic(radon) · duplication(jscpd) · MI(radon)
All language-agnostic: indent-tracking + regex, zero ext deps

---

## BRICKS — bricks/ (modular infra)
docker.py · github.py · sonarqube.py · rag.py
Each = self-contained infra capability, wirable as agent tool+skill

---

## LLM
```
Prod (SF Innovation)  azure-openai  gpt-5-mini   AZURE_DEPLOY=1 no fallback
Demo (Azure VM)       azure-openai  gpt-5-mini   no fallback
Local dev             minimax       MiniMax-M2.5  → azure-openai fallback
```
Routing: reasoning→gpt-5.2 · code→gpt-5.1-codex · generic→gpt-5-mini
Azure: max_completion_tokens · MiniMax: strips <think> auto
Rate: 15rpm (Redis or in-mem) · Keys: ~/.config/factory/*.key | Infisical

---

## JARVIS — A2A/ACP SERVER
```
strat-cto agent, delegates to RTE/PO/SM/teams
RULE: NEVER insert DB manually — always via Jarvis (/api/cto/message)

A2A v1.0 (Linux Foundation):
  GET  /.well-known/agent.json  POST /a2a/tasks  GET /a2a/tasks/{id}
  GET  /a2a/events?task_id={id}  POST /a2a/tasks/{id}/cancel
Auth bypass: /.well-known/* + /a2a/*

MCP bridge: mcp_lrm/mcp_jarvis.py → jarvis_ask/status/task_list/agent_card
ROLE_TOOL_MAP["cto"] = delegation only (create_project/mission/feature/story, launch_epic_run...)
```

---

## DB — db/adapter.py
is_postgresql() gates PG features (advisory lock, NOTIFY/LISTEN)
get_db() → sqlite3 or psycopg3 (same API via adapter)
SQLite fallback: PG_DSN unset → data/platform.db

---

## EXECUTOR — agents/executor.py
Tool loop max 15 rds · dev agents keep tools on penultimate rd
`_classify_agent_role()` → dev/devops get URGENT code_edit nudge at rd N-2
`_TOOL_SCHEMAS` cached globally — restart to refresh

---

## ADAPTIVE INTELLIGENCE
```
Thompson    selection.py     Beta bandit per-agent-slot · cold-start <5 → uniform
Darwin      darwin.py        team tournament · eliminate bottom-N · mutate top
Evolution   evolution.py     GA on workflow genomes · nightly 02:00 · Redis leader
RL          rl_policy.py     Q-learning · state=(wf,phase,reject%,quality) · ε=0.1
SkillHealth skill_health.py  det tools + LLM judge → improve skills 14D cycle
```

---

## SECURITY — arXiv:2602.20021 (11/11 CS mitigated)
```
L0 adversarial     PROMPT_INJECTION · IDENTITY_CLAIM · RESOURCE_ABUSE · PII_LEAK
Tool guards        path blocklist · MAX_TOOL_CALLS_PER_RUN=50
Memory sanitize    sanitize_agent_output on write · URL warning
A2A validation     from_agent identity + scope logging
Audit trail        admin_audit_log on destructive actions
Sandbox            SANDBOX_ENABLED=true → Docker per-agent UID isolation
Landlock fallback  Linux 5.13+ kernel sandbox when no Docker
```

---

## KEY FILES
```
server.py              lifespan, drain, auth middleware
agents/executor.py     tool loop max 15, dev penultimate logic
agents/adversarial.py  L0 (20+ det checks) + L1 (LLM semi-formal)
agents/tool_runner.py  all tools dispatch
agents/rl_policy.py    Q-learning offline batch
patterns/engine.py     26 patterns, protocols, adversarial guard
metrics/quality.py     KISS: LOC/GOD/COG/NESTING/COUPLING
services/auto_resume.py  pg_run_lock, mission resume
tools/build_tools.py   BuildTool (stderr+stdout combined)
tools/traceability_tools.py  legacy_scan/link/coverage/validate
bricks/                docker/github/sonarqube/rag
memory/manager.py      4-layer: project/global/vector/short-term
llm/client.py          multi-provider, MODEL_PROFILES, fallback chain
db/adapter.py          PG/SQLite adapter, is_postgresql()
```

## GOTCHAS
- NodeStatus: no DONE (COMPLETED only)
- HTTP 400 tool msg ordering — non-fatal
- Container path: /app/macaron_platform/ (NOT /app/platform/)
- PG advisory lock: connection-scoped → dedicated conn for mission
- Leader election fallback=True if Redis down (idempotent → safe)
- BuildTool: Swift outputs errors to stdout (not stderr) — both combined
