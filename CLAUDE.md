# SF Platform -- Agentic Workflow Engine

## Stats
~218 agents . 26 patterns (20 catalog+5 fractal+backprop) . 50 wf . 28 phase tpl
52 tool mods . 134 schemas . 1091 skills . 375py/148KLOC . 62 PG tables

## NEVER
- `import platform` top-level (shadows stdlib) -> `from platform.X import Y`
- `--reload` (same) . `*_API_KEY=dummy` . change LLM models . emoji . WebSocket

## Stack
Py3.11 . FastAPI . Jinja2 . HTMX . SSE . PG16(62tbl WAL+FTS5) . SQLite fb . Redis7 . Infisical/.env

## Run / Test
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9              # syntax HARD
python scripts/complexity_gate.py platform/   # CC+MI+LOC SOFT
pytest tests/test_platform_api.py -v          # API (PG req)
```

## Tree
```
platform/  server.py          lifespan drain auth-mw 8-bg-tasks
  agents/              exec store(~215) adversarial(L0+L1) tool_runner(134)
                       guardrails perms selection(Thompson) evolution(GA) rl(Q) darwin
  patterns/engine.py   26 topo: solo seq par loop hier net router aggr wave hitl mr bb
                       comp tournament escalation voting speculative red-blue relay mob
                       fractal_{qa,stories,tests,worktree} backprop_merge
  workflows/           store(PM v2, 28 tpl, 20 catalog) . defs/(50 YAML)
  services/            epic_orch . auto_resume . pm_checkpoint . evidence . notif
  a2a/                 bus veto negotiation jarvis_mcp azure_bridge
  ac/                  reward(14d) convergence experiments skill_thompson
  security/            prompt_guard output_validator audit sanitize
  auth/                service(JWT+bcrypt) . middleware(RBAC) . ses(AWS SES pw reset)
  llm/client.py        5 providers: azure-ai/azure-openai/nvidia/minimax/local-mlx
  db/                  adapter(PG+SQLite) schema(62tbl) migrations tenant
  cache.py             TTL cache get/put/invalidate . prefix invalidation (key*)
  tools/(52)           code git deploy build web sec mem mcp trace ast lint lsp ...
  traceability/        legacy_items + traceability_links CRUD
  ops/(17)             auto_heal traceability_scheduler knowledge_scheduler ...
  web/routes/          missions pages sessions wf agents projects auth . tpl(123)
  web/routes/api/partials.py   deferred HTML fragments for skeleton loading
  web/static/css/      main.css components.css(+skeleton .sk) agents.css ...
  web/templates/partials/      skeleton.html(20 macros) agent_cards.html ...
  rbac/ mcps/ modules/(24) bricks/ metrics/
cli/sf.py              sf status | sf ideation | sf missions list
skills/                1091 .md
projects/              baby.yaml factory.yaml (per-project config+git_url)
```

## Projects (SF-Baby: sf-baby.macaron-software.com)
| proj | repo | stack |
|------|------|-------|
| Baby | macaron-software/baby (priv) | Rust/WASM+SvelteKit+iOS/Android |
| ADA-NDIS | macaron-software/ada-ndis (pub) | FastAPI+Next.js+Supabase+Rust/gRPC+iOS/Android |
| SF | macaron-software/software-factory | Python/FastAPI+HTMX |

SAFe CRUD: POST /api/missions (epic) . /api/epics/{id}/features . /api/features/{id}/stories
Memory: POST /api/memory/project/{id} {key,value,category,source,confidence}

## Auth
JWT+bcrypt. Cookie: access 15min + refresh 7d. Rate limit: 5/60s per IP.
POST /api/auth/login . /register . /refresh . /logout . /setup . /demo
POST /api/auth/forgot-password -> 6-digit code via AWS SES (15min TTL, 5 attempts)
POST /api/auth/verify-reset-code -> validate code
POST /api/auth/reset-password -> set new pw + invalidate all sessions
OAuth: GitHub (/auth/github) . Microsoft AD (/auth/azure)
DB: users . user_sessions . user_project_roles . password_reset_codes
Config: AWS_SES_REGION(eu-west-1) . AWS_SES_FROM_EMAIL(noreply@macaron-software.com)
ses.py: boto3 send_email (styled HTML + plain text)

## Auto-Commit+Push (agents/executor.py)
code_write/code_edit -> ctx.code_files_written -> end of run: _auto_commit_and_push()
branch: agent/{agent_id}/{session_id[:8]} (never main/master/develop)
post-phase hook (epics/internal.py): git add -A + commit + push after EVERY phase

## Skeleton Loading — UI System
```
CSS:   .sk shimmer . .sk-line .sk-line-sm .sk-line-lg . .sk-circle .sk-avatar
       .sk-badge . .sk-card . .sk-metric . .sk-loaded(fade-in 0.3s)
       @keyframes skeleton-shimmer { background-position 200%->-200% }
Macros (partials/skeleton.html — import + call):
  skeleton_item_grid(n,with_icon) . skeleton_agents(n) . skeleton_missions(n)
  skeleton_stat_cards(n) . skeleton_chart(h) . skeleton_kpi_row(n)
  skeleton_table(r,c) . skeleton_teams_table(n) . skeleton_strategic(n)
  skeleton_pipeline(n) . skeleton_marketplace(n) . skeleton_kanban(cols,cards)
  skeleton_timeline(n) . skeleton_feed(n) . skeleton_hub_cards(n)
  skeleton_projects(n) . skeleton_ck_card(lines) . skeleton_tab_panel(style)
  skeleton_ds_tokens(n) . skeleton_block(lines)
Deferred: hx-get="/partial/X" hx-trigger="load" hx-swap="innerHTML"
Partials: /partial/portfolio/metrics . /partial/agents/grid . /partial/projects/grid
          /partial/sessions/grid . /partial/patterns/grid . /partial/missions/grid
          /partial/cockpit/pipeline . /partial/cockpit/projects
Cache: platform/cache.py TTL: agents 60s . missions 30s . runs 15s . wf 120s . projects 60s
  invalidate("missions:*") — prefix glob . CUD ops auto-invalidate
HTTP cache: Cache-Control immutable ?v= versioned . 1h unversioned static
Coverage: 31/88 templates . DS page /design-system -> Skeleton tab (20 live demos)
```

## Epic Workflow Engine (PM v2)
NOT "PACMAN" — PACMAN is a game project. SF pipeline = Epic Runner.
Epic -> workflow (YAML phases) -> epic_runs (DB) -> PM LLM drives phases.
PM LLM: next|loop|done|skip|**phase**(dynamic brick).
compose: pattern+team+gate+feedback -> PatternDef+WorkflowPhase -> _phase_queue.
Checkpoint: quality<50% -> retry. PM_OVERRIDE: force on build fail. Cap: 20.
Vocab: EpicRun . WorkflowPhase . PatternDef . epic_orch . auto_resume

```
store.py layout:
  L543   _PATTERN_CATALOG (20)   L556 _FEEDBACK_TYPES _GATE_TYPES
  L580   _PHASE_TEMPLATES (28 bricks)
  L700   _PM_DECISION_PROMPT_V2
  L754   _build_dynamic_phase(block) -> (WPhase, PatDef)
  L809   _build_evidence() -- src/build/test from tool_calls
  L1054  _dynamic_patterns{} + _phase_queue[]
  L1592  PM inserts: _dynamic_patterns[id] = _dyn_pattern
```

## 28 Phase Templates
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review

## Gates and Feedback
Gates: all_approved . no_veto . always . best_effort
Feedback: adversarial->config.adversarial_guard | tools->require_tool_validation
          judge->network+debate | human->hitl

## Dataclasses
```
WorkflowPhase  id pattern_id name desc gate config retry_count skip_on_failure timeout
PatternDef     id name desc type agents[{id,agent_id}] edges config steps
AgentDef       id name role desc system_prompt provider model temp max_tokens
               skills[] tools[] tags[] motivation="" persona=""
EpicRun        id workflow_id session_id status current_phase started_at cancel_reason
WorkflowRun    workflow session_id project_id current_phase phase_results[] status
PatternRun     pattern session_id project_id project_path phase_id max_iterations
```

## Quality Gates (17)
1-4 HARD: guardrails(regex) . veto(ABS/STRONG/ADV) . prompt_inject(block@7) . tool_acl(5-layer)
5-6: adversarial L0(25 det) HARD . L1(LLM) SOFT
7-9: AC reward(R[-1,+1] 14d 8crit@60) HARD . convergence SOFT . RBAC HARD
10-13: CI ruff.compile.pytest HARD . complexity(radon) SOFT
14-17: sonar SOFT . deploy canary HARD . output_validator SOFT . stale_prune SOFT

CC fn >10err >5warn . LOC >500err >300warn . MI <10err <20warn

## Scheduled Background Tasks (server.py lifespan)
| task | interval | purpose |
|------|----------|---------|
| auto_resume | 5min | resume paused epics, retry continuous missions |
| traceability | 6h | SAFe audit: hierarchy+ACs completeness, incidents on gaps |
| evolution | 02:00 UTC | GA + RL nightly retrain |
| auto_heal | 60s | incident->epic->TMA workflow |
| platform_watchdog | varies | false-positive detection |
| node_heartbeat | 10s | cluster registration |
| knowledge | 04:00 UTC | memory audit+seed+curate (manual start) |

## Traceability
DB: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(legacy->story/test)
Tools: legacy_scan . traceability_link . traceability_coverage . traceability_validate
Roles: cdp/arch/product/dev=all4 qa=coverage+validate
Adversarial: `# Ref: FEAT-xxx` / `// Ref:` enforced (MISSING_TRACEABILITY L0)
Role: `traceability` in _classify_agent_role() + ROLE_TOOL_MAP["traceability"] (40+ tools)
Team (platform): team-traceability / art-platform:
  trace-lead (Nadia) . trace-auditor (Mehdi) . trace-writer (Sophie) . trace-monitor (Lucas)
  VETO if coverage <80% . trace-writer = only SPECS.md maintainer
Team (SF-Baby): Trace Lead . QA Traceability . Code Auditor . Trace Reporter
Phase: traceability-check tpl uses team_roles=["traceability" x3, "qa"]
PM v2: auto-inserts traceability-check after dev phases; legacy->story->traceability for migrations
Scheduler: ops/traceability_scheduler.py -- every 6h (TRACEABILITY_INTERVAL env)
  scans ALL active projects: SAFe hierarchy (epics/features/stories/ACs)
  stores in memory: traceability-audit-latest + traceability-metrics
  creates platform incidents if >3 high-severity gaps
UDID format: EP-{PRJ}-NNN . FT-{PRJ}-NNN . US-{PRJ}-NNN . AC-{PRJ}-NNN

## LLM -- FROZEN
local-mlx Qwen3.5-mlx . minimax M2.5(native tool_calls, no mangle, `<think>` stripped)
azure-openai gpt-5-mini/5.2/5.2-codex . azure-ai gpt-5.2 . nvidia Kimi-K2
MiniMax: no temp . parallel_tool_calls=False . json fences stripped
GPT-5.x: reasoning . max_completion_tokens not max_tokens . budget>=16K

## Envs
```
local    :8099   PG localhost:5432 . MLX :8080
ovh      OVH_IP blue-green Docker /opt/software-factory/slots/{blue,green}
azure    SF_NODE1_IP:8090 . SF_NODE2_IP . az vm run-command (no SSH)
innov    3-node: n2(nginx lb) n1(primary) n3(PG+Redis 10.0.1.6)
```

## Deploy
OVH: rsync -> --force-recreate Docker (blue/green/factory)
Azure: systemd sf-platform -> az vm run-command
CI: .github/workflows/deploy-demo.yml . deploy-baby.yml (backup/E2E/rollback)

## PUA -- Persistence Under Adversity
Source: github.com/tanweai/pua (+36% fixes, +65% verif, +50% tool calls)
Engine: platform/agents/pua.py -- 3 Iron Rules + Proactivity injected ALL agents
Pressure: L1(2nd fail=switch) L2(3rd=soul) L3(4th=7-pt checklist) L4(5th+=escalate)
L2+: [PERSONAL ACCOUNTABILITY] hook fires using agent.motivation (own words)
5-step debug (each retry): Smell->Elevate->Mirror->Execute->Retrospective
QA boundary: _PUA_QA_BLOCK -- REVIEWER != IMPLEMENTER; QA persistence rules
agent.motivation field injected in system prompt alongside persona
engine.py: passes agent.motivation to build_retry_prompt() on adversarial reject

## Deep Bench -- Motivation ACs
deep_bench_tools.py -- agents layer adds 3 cases:
  3i agents-motivation-coverage  det  >=30% agents have motivation (currently 55%)
  3j agents-pua-motivation-hook  det  PUA hook fires at L2+/with-motivation, silent at L1/none
  3k agents-judge-motivation     llm  output reflects stated values under pressure

## Key Patterns
- YAML phase.config > pattern.config (merge L892)
- Agent resolve: explicit -> TeamSelector(Darwin) -> role -> dev_fullstack
- pm_driven:true -> PM checkpoint each phase
- _phase_queue mutable -- PM inserts/reorders
- _dynamic_patterns{} run-scoped cache
- env-setup: detect stack -> correct Dockerfile
- Agent persona: emphasize tool usage (CRITICAL BEHAVIOR RULES)
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED -- no DONE
- Container: /app/macaron_platform/ not /app/platform/
- `platform/` shadows stdlib
- SSE: `curl --max-time` (urllib blocks)
- Epic chat: _auto_create_planning_run() if no active run (execution.py)

## Repo
GitHub macaron-software/software-factory (AGPL-3.0)
