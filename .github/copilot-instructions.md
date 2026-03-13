# SF Platform — Quick Ref

## WHAT
Multi-agent SAFe orch. ~218 agents . 26 patterns . 50 wf . 28 phase tpl . 52 tool mods . 1091 skills.
FastAPI+HTMX+SSE. PG16(62tbl)+Redis7. 375py/148KLOC. Port 8099(dev)/8090(prod). Dark purple UI.

## ALWAYS — Start of Session
git pull on ALL project repos before any work:
```sh
for d in _SOFTWARE_FACTORY _BABY MVP_ADA _HELP/aides-macaron _FLO _PSY YOLONOW; do
  (cd ~/_MACARON-SOFTWARE/$d && git pull --rebase --autostash 2>/dev/null)
done
```
Note: PSY remote=github (not origin).

## NEVER
- `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- `--reload` — same shadow
- `*_API_KEY=dummy` — Infisical or `.env`
- change LLM models — if err check network/auth
- emoji . WebSocket — SSE only (`--ws none`) . SVG Feather only

## Stack
Py3.11 . FastAPI . Jinja2 . HTMX . SSE . PG16(62tbl WAL+FTS5) . SQLite fb . Redis7 . Infisical . zero build

## Run / Test
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9              # syntax HARD
python scripts/complexity_gate.py platform/   # CC+MI+LOC SOFT
pytest tests/test_platform_api.py -v          # API (PG req)
```

## Tree
```
platform/                       375py 148KLOC
  server.py                     lifespan . drain . auth mw . 8 bg tasks
  agents/                       exec . store(~215) . adversarial(L0+L1) . tool_runner(134)
                                selection(Thompson) . evolution(GA) . rl(Q) . darwin . skill_broker
  patterns/engine.py            26 topo: solo seq par loop hier net router aggr wave
                                hitl mr bb comp tournament escalation voting speculative
                                red-blue relay mob fractal_{qa,stories,tests,worktree} backprop
  workflows/                    store(PM v2, 28 tpl) . defs/(50 YAML) . builtins
  services/                     epic_orch . auto_resume . pm_checkpoint . evidence . notif
  a2a/                          bus . veto . negotiation . jarvis_mcp . azure_bridge
  ac/                           reward(14d) . convergence . experiments . skill_thompson
  security/                     prompt_guard . output_validator . audit . sanitize
  auth/                         service(JWT+bcrypt) . middleware(RBAC) . ses(AWS SES pw reset)
  llm/client.py                 5 providers: azure-ai/azure-openai/nvidia/minimax/local-mlx
  db/                           adapter(PG+SQLite) . schema(62tbl) . migrations . tenant
  cache.py                      TTL cache (get/put/invalidate) . prefix invalidation (key*)
  tools/(52)                    code git deploy build web sec mem mcp trace ast lint lsp ...
  ops/(17)                      auto_heal . traceability_scheduler . knowledge_scheduler ...
  web/routes/                   missions pages sessions wf agents projects auth . tpl(123)
  web/routes/api/partials.py    deferred HTML fragments (/partial/*) for skeleton loading
  web/static/css/components.css skeleton .sk shimmer + 20 macro variants
  web/templates/partials/       skeleton.html (20 macros) . agent_cards.html ...
  rbac/ mcps/ modules/(24) bricks/ metrics/
skills/                         1091 .md
projects/                       baby.yaml . factory.yaml (per-project config+git_url)
```

## Auth
POST /api/auth/login -> cookie JWT (15min access + 7d refresh) . bcrypt pw hash
POST /api/auth/forgot-password -> 6-digit code via AWS SES (15min expiry, 5 attempts max)
POST /api/auth/verify-reset-code -> validate code
POST /api/auth/reset-password -> set new pw + invalidate all sessions
OAuth: GitHub (/auth/github) . Microsoft Azure AD (/auth/azure)
Demo: POST /api/auth/demo (SF_DEMO_PASSWORD env)
Rate limit: 5 req/60s per IP on all auth endpoints
DB: users . user_sessions . user_project_roles . password_reset_codes
Config: AWS_SES_REGION (dflt eu-west-1) . AWS_SES_FROM_EMAIL (dflt noreply@macaron-software.com)

## Projects (SF-Baby: sf-baby.macaron-software.com)
| proj | repo | path | stack |
|------|------|------|-------|
| Baby | macaron-software/baby (priv) | _BABY | Rust/WASM+SvelteKit+iOS/Android |
| ADA-NDIS | macaron-software/ada-ndis (pub) | MVP_ADA | FastAPI+Next.js+Supabase+Rust/gRPC+iOS/Android |
| SF | macaron-software/software-factory | _SOFTWARE_FACTORY | Python/FastAPI+HTMX |
| FLO | macaron-software/luna | _FLO | TBD |
| PSY | macaron-software/psy-platform (priv) | _PSY | Rust/Axum+React |
| YOLONOW | macaron-software/yolonow (priv) | YOLONOW | Rust |
| MesAides | macaron-software/mes-aides | _HELP/aides-macaron | Rust+WASM+SwiftUI+Kotlin |

SAFe CRUD API: POST /api/missions (epic) . POST /api/epics/{id}/features . POST /api/features/{id}/stories
Memory API: POST /api/memory/project/{id} (key,value,category,source,confidence)

## Auto-Commit+Push (agents/executor.py)
code_write/code_edit -> ctx.code_files_written tracked -> end of run: _auto_commit_and_push()
branch: agent/{agent_id}/{session_id[:8]} (never main/master/develop)
post-phase hook (epics/internal.py): git add -A + commit + push after EVERY phase

## Skeleton Loading — UI System
CSS: .sk shimmer gradient animation . .sk-line .sk-circle .sk-badge .sk-card .sk-loaded(fade-in)
Macros: partials/skeleton.html — 20 variants (import + call in Jinja2)
  skeleton_item_grid(n) . skeleton_agents(n) . skeleton_missions(n) . skeleton_stat_cards(n)
  skeleton_chart(h) . skeleton_kpi_row(n) . skeleton_table(r,c) . skeleton_teams_table(n)
  skeleton_strategic(n) . skeleton_pipeline(n) . skeleton_marketplace(n) . skeleton_kanban(c,n)
  skeleton_timeline(n) . skeleton_feed(n) . skeleton_hub_cards(n) . skeleton_projects(n)
  skeleton_ck_card(n) . skeleton_tab_panel(style) . skeleton_ds_tokens(n) . skeleton_block(n)
Pattern: hx-get="/partial/X" hx-trigger="load" hx-swap="innerHTML" wrapping skeleton macro
Coverage: 31/88 templates (all data pages). DS page /design-system -> Skeleton tab.
Cache: platform/cache.py TTL (agents 60s, missions 30s, runs 15s, wf 120s). Prefix invalidation.
HTTP: Cache-Control immutable for versioned static (?v=), 1h unversioned.

## Epic Workflow Engine — PM v2 (Lego Orchestrator)
NOT "PACMAN" — PACMAN is a game project in SF. Pipeline = Epic Runner.
Epic -> workflow YAML (phases) -> epic_runs (PG) -> PM LLM drives phases.
Phase -> PM LLM: next|loop|done|skip|**phase**(dynamic brick).
compose: pattern+team+gate+feedback -> PatternDef+WorkflowPhase -> _phase_queue.
Checkpoint: quality<50% -> retry. PM_OVERRIDE: force on build fail. Cap: 20.

## Quality Gates (17)
| # | Gate | |
|---|------|--|
| 1 | Guardrails regex destruct-action | HARD |
| 2 | Veto ABSOLUTE/STRONG/ADVISORY | HARD |
| 3 | Prompt inject score 0-10 block@7 | HARD |
| 4 | Tool ACL 5-layer (acl.sandbox.rate.write.git) | HARD |
| 5 | Adversarial L0 — 25 det checks | HARD |
| 6 | Adversarial L1 — LLM semantic | SOFT |
| 7 | AC reward R in [-1,+1] 14d 8crit@60 | HARD |
| 8 | Convergence plateau/regr/spike | SOFT |
| 9 | RBAC roles x actions x artifacts | HARD |
| 10-12 | CI ruff.compile.pytest | HARD |
| 13 | CI complexity radon CC+MI LOC | SOFT |
| 14 | SonarQube ext | SOFT |
| 15 | Deploy blue-green canary | HARD |
| 16 | Output validator | SOFT |
| 17 | Stale builtin prune | SOFT |

CC fn >10err >5warn . LOC >500err >300warn . MI <10err <20warn

## Scheduled Background Tasks (server.py lifespan)
| task | file | interval | purpose |
|------|------|----------|---------|
| auto_resume | services/auto_resume.py | 5min | resume paused epics, retry continuous missions |
| traceability | ops/traceability_scheduler.py | 6h | SAFe audit: epics/feat/stories/ACs gaps, incidents |
| evolution | agents/evolution_scheduler.py | 02:00 UTC | GA + RL nightly retrain |
| auto_heal | ops/auto_heal.py | 60s | incident->epic->TMA workflow |
| platform_watchdog | ops/platform_watchdog.py | varies | false-positive detection |
| node_heartbeat | server.py | 10s | cluster registration |
| knowledge | ops/knowledge_scheduler.py | 04:00 UTC | memory audit+seed+curate (manual start) |

## SAFe Vocab
Epic=MissionDef . Feature=FeatureDef . Story=UserStoryDef . PI=MissionRun . Sprint=SprintDef
UDID format: EP-{PRJ}-NNN . FT-{PRJ}-NNN . US-{PRJ}-NNN . AC-{PRJ}-NNN

## LLM — FROZEN
local-mlx Qwen3.5-mlx . minimax M2.5 . azure-openai gpt-5-mini/5.2/5.2-codex
azure-ai gpt-5.2 . nvidia Kimi-K2

## Deploy
OVH: blue-green Docker slots/{blue,green,factory}/ --force-recreate
Azure: systemd sf-platform via az vm run-command . Innovation: 3-node nginx lb
CI: .github/workflows/deploy-demo.yml . deploy-baby.yml (backup/E2E/rollback)

## Gotchas
- `platform/` shadows stdlib — NEVER `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock conn-scoped -> dedicated conn/mission
- MiniMax M2.5: native tool_calls . no mangle . no temp . `<think>` stripped
- Container: /app/macaron_platform/ not /app/platform/
- SSE: `curl --max-time` — urllib blocks
- Epic orch: _build_phase_prompt() not workflows/store.py
- Epic chat: _auto_create_planning_run() if no active run (execution.py)

## PUA / Motivation
pua.py: Iron Rules+Proactivity ALL agents. L1-L4 pressure on retry.
agent.motivation field: injected in prompt. L2+ fires [PERSONAL ACCOUNTABILITY] hook.
_PUA_QA_BLOCK: QA = REVIEWER not IMPLEMENTER.
5-step debug each retry: Smell->Elevate->Mirror->Execute->Retrospective

## Traceability
Adversarial L0: MISSING_TRACEABILITY — all .py/.ts files need `# Ref: FEAT-xxx`
Tools: legacy_scan . traceability_coverage . traceability_validate . traceability_link
Team (SF-Baby): Trace Lead . QA Traceability . Code Auditor . Trace Reporter
Team (platform): team-traceability (art-platform) — trace-lead/auditor/writer/monitor
Scheduler: ops/traceability_scheduler.py every 6h (TRACEABILITY_INTERVAL env)
  scans ALL active projects: SAFe hierarchy audit, GIVEN/WHEN/THEN AC check
  stores results in project memory: traceability-audit-latest + traceability-metrics
  creates platform incidents if >3 high-severity gaps
PM v2: auto-inserts traceability-check after dev phases
