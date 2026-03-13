# SF Platform — Quick Ref

## WHAT
Multi-agent SAFe orch. ~221 agents . 26 patterns . 69 wf . 32 phase tpl . 54 tool mods . 139 skills.
FastAPI+HTMX+SSE. PG16(62tbl)+Redis7. 375py/148KLOC. Port 8099(dev)/8090(prod).

## ALWAYS — Start of Session
```sh
for d in _SOFTWARE_FACTORY _BABY MVP_ADA _HELP/aides-macaron _FLO _PSY YOLONOW; do
  (cd ~/_MACARON-SOFTWARE/$d && git pull --rebase --autostash 2>/dev/null)
done
```
PSY remote=github (not origin).

## NEVER
- `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- `--reload` (same shadow) . `*_API_KEY=dummy` — Infisical/.env
- change LLM models . emoji in UI . WebSocket — SSE only (`--ws none`) . SVG Feather icons only
- gradient bg . inline styles . hardcoded hex colors in UI

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
platform/                    375py 148KLOC
  server.py                  lifespan . drain . auth mw . 8 bg tasks
  agents/                    exec . store(~221) . adversarial(L0+L1) . tool_runner(134)
                             selection(Thompson) . evolution(GA) . rl(Q) . darwin . skill_broker
  patterns/engine.py         26 topo: solo seq par loop hier net router aggr wave hitl mr bb
                             comp tournament escalation voting speculative red-blue relay mob
                             fractal_{qa,stories,tests,worktree} backprop
  workflows/                 store(PM v2, 32 tpl, 9 prompt sects) . defs/(69 YAML)
  services/                  epic_orch(+on_complete chain) . auto_resume . pm_checkpoint . notif
  a2a/                       bus . veto . negotiation . jarvis_mcp . azure_bridge
  ac/                        reward(14d) . convergence . experiments . skill_thompson
  security/                  prompt_guard . output_validator . audit . sanitize
  auth/                      service(JWT+bcrypt) . middleware(RBAC) . ses(AWS SES pw reset)
  llm/client.py              5 providers: azure-ai/azure-openai/nvidia/minimax/local-mlx
  db/                        adapter(PG+SQLite) . schema(62tbl) . migrations . tenant
  tools/(54)                 code git deploy build web sec mem mcp trace ast lint lsp ds ...
  ops/(17)                   auto_heal . traceability_scheduler . knowledge_scheduler ...
  web/routes/                missions pages sessions wf agents projects auth . tpl(123)
  web/static/css/            main.css components.css(.sk shimmer) agents.css ...
  web/templates/partials/    skeleton.html(20 macros) . agent_cards.html ...
skills/                      139 YAML
projects/                    baby.yaml . factory.yaml (per-project config+git_url)
```

## DB — LIVE = PostgreSQL
DATABASE_URL=postgresql://macaron:macaron@localhost:5432/macaron_platform
data/platform.db = STALE SQLite — do NOT query for live data.
psql: PGPASSWORD=macaron /opt/homebrew/bin/psql -h localhost -U macaron -d macaron_platform

## Projects
| proj | repo | path | stack |
|------|------|------|-------|
| Baby | macaron-software/baby | _BABY | Rust/WASM+SvelteKit+iOS/Android |
| ADA-NDIS | macaron-software/ada-ndis | MVP_ADA | FastAPI+Next.js+Supabase+Rust/gRPC |
| SF | macaron-software/software-factory | _SOFTWARE_FACTORY | Python/FastAPI+HTMX |
| FLO | macaron-software/luna | _FLO | TBD |
| PSY | macaron-software/psy-platform | _PSY | Rust/Axum+React |
| YOLONOW | macaron-software/yolonow | YOLONOW | Rust |
| MesAides | macaron-software/mes-aides | _HELP/aides-macaron | Rust+WASM+SwiftUI+Kotlin |

## Auth
JWT+bcrypt. Cookie: access 15min + refresh 7d. Rate limit: 5/60s per IP.
POST /api/auth/login . /register . /refresh . /logout . /forgot-password . /reset-password
OAuth: GitHub(/auth/github) . Azure AD(/auth/azure) . Demo(/api/auth/demo)
AWS SES: 6-digit code, 15min TTL, 5 attempts max.

## Auto-Commit+Push
code_write/code_edit -> ctx.code_files_written -> _auto_commit_and_push()
branch: agent/{agent_id}/{session_id[:8]} (never main/master/develop)
post-phase hook: git add -A + commit + push after EVERY phase

## Epic Workflow Engine — PM v2
Epic -> workflow(YAML phases) -> epic_runs(PG) -> PM LLM: next|loop|done|skip|phase(dyn).
compose: pattern+team+gate+feedback -> PatternDef+WorkflowPhase -> _phase_queue.
Checkpoint: quality<50% -> retry. Cap: 20. pm_driven:true -> PM checkpoint each phase.
on_complete: _on_complete_chain() reads workflow.config_json.on_complete[] -> auto-launch companion wf.
  41 wf configured: code-deliverable -> doc-pipeline+knowledge-maint; findings -> knowledge-maint.

## PM v2 — 9 Prompt Sections
DECISION . PATTERN GUIDE . PROGRESSION . NEVER-done(10 items) . TRACEABILITY . INFRA-PROVISION
DESIGN-SYSTEM . FRACTAL . PUA

NEVER done if: build fail . tests fail . src<3 . adversarial reject(>=7) . AC-xxx unresolved
  . frontend missing design-system phase . frontend missing ux-review gate
  . responsive not tested(375/768/1280) . themes(light/dark/hi-contrast) missing
  . WCAG AA missing(skip-link/focus-visible/aria/kbd) . error states show raw tech copy

## 32 Phase Templates
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence design-system ux-review deploy rework
bug-triage creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review
fractal-decomp story-sprint

feature-sprint (PG) — 11 phases:
  feature-design -> story-decomp -> qa-decomp -> design-system* -> env-setup
  -> tdd-sprint[dev-react,dev-java-spring,testeur] -> adversarial-review[archi,code-critic,code-reviewer]
  -> traceability-check[trace-lead,trace-auditor,trace-monitor] -> ux-review[ux-adversarial,llm-judge-ux]
  -> feature-e2e -> feature-deploy  (*skip_on_failure if no frontend)

## Design System
Agents: ds-lead . ux-adversarial . llm-judge-ux
Tools: css_computed_check(WCAG contrast+computed styles) . ds_token_audit(token completeness)
Skills: design_system_enforcer . ds_lead . ux_adversarial . llm_judge_ux
Required files: tokens.css . themes.css([data-theme]) . base.css . components.css . lib/theme.ts
Themes: light + dark + high-contrast(WCAG AAA 7:1) togglable via <html data-theme>.
Responsive: mobile-first 375->768->1024->1280px. Touch targets min 44x44px.
WCAG AA+: skip-to-content . focus-visible . aria landmarks . semantic HTML . kbd nav . Cmd+K.
Adv checks: hardcoded hex . gradient bg . emoji . inline styles . missing aria . no retry btn.

## Network Resilience (skill: network_resilience.yaml)
5 states per data component: loading(skeleton+aria-busy) . success . empty . error . offline(+stale)
Web: window online/offline events + HEAD/healthz . SW + IDB mutation queue
  fetchWithRetry: exp backoff+jitter(500ms*2^i+rnd*200) . AbortSignal.timeout(8s) . max 3
iOS: NWPathMonitor(@Observable NetworkMonitor) . waitsForConnectivity=true . SwiftData PendingOp queue
Android: ConnectivityManager.NetworkCallback -> StateFlow . WorkManager(CONNECTED) . retryWhen
Empathetic copy: FORBIDDEN phrases = "Error" / "HTTP 5xx" / "Network Error" / "Request failed"
  USE: "Youre offline - changes will sync when you reconnect."
       "Something went wrong on our end - please try again."
Adv checks: offline_state_missing . raw_error_in_ui . missing_retry_btn . forbidden_copy

## Traceability
L0 det: MISSING_TRACEABILITY — all .py/.ts need `# Ref: FEAT-xxx`
Tools: legacy_scan . traceability_coverage . traceability_validate . traceability_link
Team: trace-lead . trace-auditor . trace-monitor . trace-writer (VETO if coverage <80%)
UDID: EP-{PRJ}-NNN . FT-{PRJ}-NNN . US-{PRJ}-NNN . AC-{PRJ}-NNN
Scheduler: ops/traceability_scheduler.py 6h — SAFe audit, incidents if >3 gaps

## PUA
pua.py: Iron Rules+Proactivity ALL agents.
L1(2nd fail)=switch . L2(3rd)=root cause . L3(4th)=7-pt checklist . L4(5th+)=escalate
L2+: [PERSONAL ACCOUNTABILITY] hook. QA=REVIEWER not IMPLEMENTER.
5-step retry: Smell->Elevate->Mirror->Execute->Retrospective.

## Quality Gates (17)
1-4 HARD: guardrails . veto(ABS/STR/ADV) . prompt_inject(block@7) . tool_acl(5-layer)
5-6: adv L0(25 det) HARD . L1(LLM) SOFT
7-9: AC reward(R[-1,+1] 14d 8crit@60) HARD . convergence SOFT . RBAC HARD
10-12: CI ruff.compile.pytest HARD . 13: complexity(radon) SOFT
14-17: sonar SOFT . deploy canary HARD . output_validator SOFT . stale_prune SOFT
CC>10err>5warn . LOC>500err>300warn . MI<10err<20warn

## Bg Tasks
auto_resume(5min) . traceability(6h) . evolution(02:00) . auto_heal(60s)
platform_watchdog(varies) . node_heartbeat(10s) . knowledge(04:00)

## LLM — FROZEN
minimax M2.5 . azure-openai gpt-5-mini/5.2/5.2-codex . azure-ai gpt-5.2 . nvidia Kimi-K2 . local-mlx
MiniMax quirks: no temp . no mangle . `<think>` stripped . json fences stripped . parallel_tool_calls=False

## Deploy
OVH: blue-green Docker slots/{blue,green,factory}/ --force-recreate
Azure: systemd sf-platform -> az vm run-command . Innovation: 3-node nginx lb
CI: deploy-demo.yml . deploy-baby.yml

## Skeleton Loading
CSS: .sk shimmer gradient . .sk-line .sk-circle .sk-badge .sk-card .sk-loaded(fade-in)
Macros: partials/skeleton.html — 20 variants. Pattern: hx-get="/partial/X" hx-trigger="load".

## Gotchas
- `platform/` shadows stdlib — NEVER `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock conn-scoped -> dedicated conn/mission
- Container: /app/macaron_platform/ not /app/platform/
- SSE: `curl --max-time` (urllib blocks)
- Epic orch: _build_phase_prompt() not workflows/store.py
- Epic chat: _auto_create_planning_run() if no active run
