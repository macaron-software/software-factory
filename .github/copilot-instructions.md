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
Tiered: L0=skeleton(instant) . L1=summary gzip(fast) . L2=full detail(on-demand)

## Design Tokens (CSS custom props — single source of truth)
Colors dark: --bg-primary=#0f0a1a . --bg-secondary=#1a1225 . --bg-tertiary=#251d33
  --border=#352d45 . --text-primary=#e6edf3 . --text-secondary=#9e95b0
  --purple=#a78bfa(accent) . --green=#34d399 . --red=#f87171 . --yellow=#fbbf24 . --blue=#60a5fa . --cyan=#22d3ee
Colors light: --bg-primary=#fff . --bg-secondary=#f8f9fa . --text-primary=#1a1a2e
Type: system-ui,-apple-system,sans-serif(0 ext deps) . --font-mono=ui-monospace
  xs=.75rem sm=.875rem base=1rem lg=1.125rem xl=1.25rem 2xl=1.5rem 3xl=2rem
Space(4px grid): 1=.25rem 2=.5rem 3=.75rem 4=1rem 5=1.5rem 6=2rem 8=3rem 10=4rem
Radius: sm=4px default=10px lg=16px full=9999px
Shadow: sm=0 1px 2px . default=0 4px 12px . lg=0 8px 24px
Z: dropdown=100 modal=200 toast=300 tooltip=400

## UI Components (60 — atomic design)
Atoms(29): avatar badge button checkbox color-picker date-input file heading icon image label link
  progress-bar quote radio rating select separator skeleton skip-link slider spacer spinner
  stepper text-input textarea toggle tooltip visually-hidden
Molecules(20): accordion alert breadcrumb button-group card combobox date-picker dropdown
  empty-state fieldset file-upload list pagination popover progress-tracker search segmented tabs toast tree-view
Organisms(11): carousel drawer footer form header hero modal navigation rich-text-editor table video
Icons: Feather SVG ONLY (stroke round-linecap 2px). No emoji anywhere.

## UX Laws (27 — lawsofux.com)
Perf: Doherty(<400ms) . Fitts(size/dist) . Goal-Gradient(progress)
Decision: Hicks(log2 choices) . Choice-Overload . Occam(simplest)
Memory: Miller(7±2) . Cognitive-Load(intrinsic/extraneous) . Chunking . Working-Memory . Mental-Model
Gestalt: Proximity . Similarity . Common-Region . Pragnanz . Uniform-Connectedness
Behavior: Jakob(familiarity) . Aesthetic-Usability . Active-User(no manuals) . Peak-End . Von-Restorff(isolation) . Serial-Position . Zeigarnik(incomplete) . Selective-Attention . Flow
Strategic: Pareto(80/20) . Parkinson(fill time) . Tesler(irreducible) . Postel(liberal accept)

## Patterns (DO) / Anti-Patterns (DON'T)
DO: skeleton-loading . progressive-disclosure . SSE-streaming . tiered-ctx(L0/L1/L2) . feature-ref-headers
  RBAC-as-dependency . CSS-custom-props . feather-svg . htmx-partial-swap . SAFe-hierarchy
  gzip-compress . system-font . dark-first . multi-step-form . empty-state-CTA
DON'T: gradient-bg . emoji . inline-styles . hardcoded-colors . websocket . --reload . import-platform
  spinner-no-context . wall-of-text . deep-nav(>3) . modal-abuse . no-feedback

## Compliance
SOC2: CC1-CC9+A1 — 76% (19/25 pass, 6 warn). Key: CC6 access=PASS, A1 availability=WARN
ISO27001: Annex A — 88% (22/25 pass, 3 warn). Key: A.9 access=PASS, A.12.6 vuln-mgmt=WARN
OWASP Top10: 7/10 pass, 3 warn (A05 miscfg, A06 deps, A10 SSRF)

## Security — White Hat
PASS: RBAC(54/54) . SQL-inject(param) . path-traversal . secrets(Infisical) . TLS . session-mgmt
WARN: CSRF(no tokens) . XSS(|safe audit) . 4 dep CVEs . missing CSP/X-Frame . SSRF-tools . RCE-sandbox . prompt-inject . rate-limit . CORS-permissive
Priority: 1.sandbox-RCE 2.security-headers 3.URL-allowlist 4.dep-CVEs 5.rate-limit

## E2E Traceability (100% all layers)
Chain: Persona(16) -> Feature(44,feat-*) -> Story(172,us-{uuid8}) -> AC(154,ac-{uuid8})
  -> IHM(124/124) -> Code(379/382) -> TU(36/36) -> E2E(23/23) -> CRUD(645) -> RBAC(54/54)
Annotations: .py=`# Ref: feat-*` . .html=`<!-- Ref: feat-* -->` . .ts=`// Ref: feat-*`
Wiki: 63 pages — 8 traceability + 10 DS/UX + 6 compliance + 3 devops + 1 LEAN

## A11Y — WCAG AA (W3C ARIA APG)
30 patterns: accordion alert alertdialog breadcrumb button carousel checkbox combobox dialog
  disclosure feed grid landmarks link listbox menubar menubutton meter radio slider
  slider-multi spinbutton switch table tabs toolbar tooltip treeview treegrid splitter
Required: skip-link . focus-visible(:focus-visible 2px solid --purple) . ARIA landmarks(banner/nav/main)
  semantic HTML . kbd nav(Tab/Enter/Space/Arrow/Esc) . contrast 4.5:1 . Cmd+K palette
IHM header: partials/ihm_context.html macro → persona/feature/RBAC/CRUD/stories context bar

## i18n — 40 Languages + RTL
Active: en,fr. Planned: es,de,it,pt,ar,zh,ja,ko,ru,tr + 28 more
RTL(4): ar,he,fa,ur → `<html dir="rtl">` + CSS logical properties (margin-inline-start)
Keys: `{{ t('nav.home') }}` via platform/i18n/ locales/*.json
Detection: URL?lang= > Cookie(sf_lang) > Accept-Language > en

## SecureByDesign (25 controls, v1.1)
L1-Input(3): SBD-01 validation=PASS . SBD-02 prompt-inject=PASS . SBD-03 CSP=WARN
L2-Auth(3): SBD-04 auth=PASS . SBD-05 authz=PASS . SBD-06 least-priv=PASS
L3-Data(3): SBD-07 secrets=PASS . SBD-08 crypto=PASS . SBD-09 minimize=WARN
L4-Resilience(4): SBD-10 logging=PASS . SBD-11 rate-limit=WARN . SBD-12 SSRF=WARN . SBD-13 errors=PASS
L5-Supply(12): 9 PASS, 3 WARN (SBD-14 deps, SBD-20 CORS, SBD-24 IRP)
Score: 72% (18/25 pass, 7 warn)

## Observability (OTEL)
Traces: Jaeger :16686 — agent exec, LLM calls, DB queries, HTTP
Metrics: /metrics — sf_llm_calls_total, sf_llm_cost_usd, sf_agent_executions, sf_http_requests
Health: /api/health(liveness) . /api/readiness(PG+Redis) . /api/metrics(prometheus)
Alerts: auto-heal 60s . app-down(restart) . high-latency(p99>5s) . LLM-errors(>10%) . agent-stuck(>10min)
Dashboard: :8080 real-time SSE

## API
Auth: JWT access(15min) + refresh(7d) . OAuth GitHub/Azure . Demo mode
Rate: auth=5/60s . read=100/60s . write=30/60s . LLM=10/60s . SSE=5 concurrent
Headers: X-RateLimit-Limit/Remaining/Reset . Retry-After(429)
Versioning: v1 implicit . v2 prefix planned . Sunset header for deprecation
Errors: {"error":"code","message":"text","status":NNN,"request_id":"req-*"}

## GDPR (33% — 4/12 pass)
PASS: Art.6(lawful) . Art.25(privacy-by-design) . Art.32(security) . Art.30(partial)
WARN: Art.5(no DPR) . Art.7(no consent UI) . Art.12(no privacy page) . Art.15(no export)
  Art.17(no erasure) . Art.20(no portability) . Art.33(no breach proc) . Art.35(no DPIA)
Retention: PII=lifetime+30d . sessions=90d . security-logs=90d(pseudonymize@30d) . metrics=1y

## DR (Disaster Recovery)
RTO/RPO: app=4h/1h . PG=4h/1h . Redis=15min/0 . LLM=5min/0 . full-site=8h/4h
Failover: Azure→OVH→local . PG=pg_dump daily+WAL . LLM=multi-provider auto
Backup: pg_dump 02:00 daily(30d) . Redis RDB 15min . Git=continuous . Infisical=cloud HA

## Annotation Studio (sf-annotate.js)
Agentation-inspired. Types: comment/bug/move/area/text. Click element→annotate→export markdown.
Drag-drop markers. Pause animations. CSS selector + component path capture.

## Gotchas
- `platform/` shadows stdlib — NEVER `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock conn-scoped -> dedicated conn/mission
- Container: /app/macaron_platform/ not /app/platform/
- SSE: `curl --max-time` (urllib blocks)
- Epic orch: _build_phase_prompt() not workflows/store.py
- Epic chat: _auto_create_planning_run() if no active run
