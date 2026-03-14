# MACARON AGENT PLATFORM — Architecture

## Distributed
```
PG advisory lock   auto_resume.py   pg_run_lock(int64) conn-scoped non-blocking
Redis rate limit   rate_limit.py    slowapi -> REDIS_URL shared . fb: in-memory
Leader election    evolution_sched  Redis SET NX EX ttl -> first wins
Graceful drain     server.py        _drain_flag + asyncio.wait(DRAIN_S)
Health probes      /api/health(DB+Redis) . /api/ready(503 drain — auth bypass)
```

## Mission Orchestration
```
POST /missions/start -> pg_run_lock(run_id) -> _safe_run()
  -> _mission_semaphore(N) -> run_phases()
    -> sprint_loop(max) -> run_pattern() -> adversarial_guard
    -> PUA retry(L1→L4) -> gate -> next_phase
```
product-lifecycle: 15 phases (ideation→strategic→setup→arch→design→dev→build→cicd→ux→qa-plan→qa-exec→deploy→**traceability-check**→tma-router→tma-fix)

## Adversarial Guard (Swiss Cheese) — agents/adversarial.py
L0 det (0ms): 25 checks — SLOP MOCK FAKE_BUILD(+7) HALLUC LIE STACK_MISMATCH(+7)
  CODE_SLOP ECHO REPETITION SECRET FILE_TOO_LARGE(>200L,+4) GOD_FILE(>3types,+3)
  COGNITIVE(>25,+4) DEEP_NEST(>4lvl,+3) HIGH_COUPLING(>12imp,+2) LOC_REGRESSION(+6)
  MISSING_UUID_REF MISSING_TRACE FAKE_TESTS NO_TESTS SECURITY_VULN PII_LEAK
  PROMPT_INJECT IDENTITY_CLAIM RESOURCE_ABUSE
L1 LLM semantic: semi-formal reasoning (arXiv:2603.01896)
Score: <5=pass 5-6=soft >=7=reject. Force: HALLUC/SLOP/STACK_MISMATCH/FAKE_BUILD

## Traceability — E2E UUID Chain
```
Persona → Feature(feat-XXXX) → Story(us-XXXX) → AC(ac-XXXX,Gherkin)
    → IHM(route,CRUD,RBAC) → Code(// Ref: feat-XXXX) → TU(// Verify: ac-XXXX) → E2E
```
Team: trace-lead(Nadia,VETO) trace-auditor(Mehdi) trace-writer(Sophie) trace-monitor(Lucas)
Phase: traceability-check in product-lifecycle (phase 13, sequential, gate=no_veto)
DB: features, user_stories, acceptance_criteria, legacy_items, traceability_links
Tools: legacy_scan, traceability_link, traceability_coverage, traceability_validate
Scheduler: 6h sweep, mission if coverage <80%

## Security — 25 SBD Controls (securebydesign v1.1)
L1-Input: SBD-01(validation) SBD-02(prompt injection) SBD-03(CSP/headers)
L2-Identity: SBD-04(auth Argon2id) SBD-05(authz default-DENY) SBD-06(least privilege)
L3-Data: SBD-07(secrets mgmt) SBD-08(crypto AES-256-GCM) SBD-09(data minimization)
L4-Resilience: SBD-10(audit log) SBD-11(rate limit) SBD-12(SSRF) SBD-13(error handling)
L5-Architecture: SBD-14(deps) SBD-15(CI/CD) SBD-16(model integrity) SBD-17(prompt protection)
  SBD-18(RAG) SBD-19(output validation) SBD-20(CORS) SBD-21(fail secure)
  SBD-22(governance) SBD-23(asset inventory) SBD-24(incident response) SBD-25(privacy)
Tiers: LOW(static/demos) STANDARD(SaaS/APIs) REGULATED(finance/health/gov)

## Compliance — SOC2 + ISO27001
SOC2: CC1.1(RBAC) CC1.2(CTO agent) CC3.1(adversarial) CC4.1(AC reward) CC5.1(tool ACL)
  CC6.1(JWT auth) CC6.8(CI/CD gates) CC7.1(watchdog) CC7.2(PUA+auto-heal) CC8.1(traceability)
ISO27001: A.5.1(security module) A.5.8(adversarial/phase) A.5.15(RBAC 5-layer)
  A.5.17(JWT+bcrypt) A.5.24(auto-heal) A.5.34(sanitize) A.8.1(agent store) A.8.25(quality gates)

## RBAC Roles
admin(full) cto(strategic) pm(backlog) lead_dev(code review) developer(code)
qa(tests) devops(infra) security(audit) trace_lead(coverage,veto)
viewer(read-only) auditor(compliance) scrum_master(ceremonies)

## UX Laws (30 from lawsofux.com)
Hick's(minimize choices) Fitts's(44px targets) Doherty(<400ms) Jakob's(familiar patterns)
Miller's(7±2 items) Peak-End(positive endings) Postel's(liberal in, strict out)
Gestalt: Proximity Similarity CommonRegion Pragnanz UniformConnectedness
Cognitive: Load Bias Chunking MentalModel WorkingMemory
Behavior: Flow GoalGradient ActiveUser Zeigarnik Parkinson SerialPosition
Design: Occam's Tesler's VonRestorff AestheticUsability Pareto ChoiceOverload SelectiveAttention

## A11Y — WAI-ARIA APG (30 patterns)
Accordion Alert AlertDialog Breadcrumb Button Carousel Checkbox Combobox
Dialog Disclosure Feed Grid Landmarks Link Listbox Menu MenuButton
Meter RadioGroup Slider MultiThumbSlider Spinbutton Switch Table Tabs
Toolbar Tooltip TreeView Treegrid WindowSplitter
Rules: semantic HTML first . keyboard accessible . accessible name . focus management
  state communicated to AT . color alone never conveys meaning . contrast 4.5:1/3:1

## i18n — 40 Languages + RTL
LTR(34): en fr es pt de it nl pl ro cs sk hu hr bg uk ru el tr vi th ko ja zh-CN zh-TW id ms tl hi bn sw am ha yo ig
RTL(6): ar he fa ur ps ku
CSS: logical properties (margin-inline-start not margin-left). Flexbox auto-reverses.
CLDR plurals. Babel date/number formatting. ICU message format.

## UI Components (60) — Atomic Design
Atoms: Button Badge Icon Label Link Input Separator Spacer Toggle Heading Image VisuallyHidden
Molecules: Accordion Alert Avatar Breadcrumb Card Combobox DateInput Drawer Dropdown EmptyState
  FileUpload Pagination Popover ProgressBar Radio Search Select Skeleton Slider Spinner Stepper Tabs Toast Tooltip
Organisms: Carousel DataTable Footer Form Header Hero Modal Navigation RTE TreeView VideoPlayer
Icons: SVG Feather ONLY. No emoji. No FontAwesome.
Skeleton: every component with data needs skeleton variant. .sk shimmer 1.5s. aria-busy="true"

## Design Tokens
Colors: --bg-primary:#0f0a1a --purple:#a855f7 --success:#10b981 --warning:#f59e0b --error:#ef4444 --info:#3b82f6
Typo: JetBrains Mono. --font-size-{xs:0.75,sm:0.875,base:1,lg:1.125,xl:1.25,2xl:1.5,3xl:1.875}rem
Space: --space-{xs:0.25,sm:0.5,md:1,lg:1.5,xl:2,2xl:3}rem
Radius: --radius-{sm:0.25,md:0.5,lg:0.75,xl:1,full:9999}rem
Shadow: sm/md/lg. Animation: fast:150ms base:300ms slow:500ms. Z: dropdown:100 sticky:200 modal:300 toast:400 tooltip:500

## Observability — OTEL
Traces: mission.execute, phase.execute, agent.invoke, tool.call
Metrics: mission.duration, phase.duration, llm.latency, adversarial.reject_count, quality.score
Alerts: MissionStuck(>2h) LLMFailing(>10fb/5m) HighRejectRate(>80%) DBExhausted(>90%)
Health: /api/health /api/ready /api/metrics

## DR — RTO/RPO
Critical(15min/0): auth, DB, API. Important(1h/5m): missions, SSE. Standard(4h/1h): analytics.
Failover: nginx lb → proxy_next_upstream. Blue-green Docker. PG WAL streaming.
Backup: hourly pg_dump(48h) daily(30d) weekly(90d) monthly(1y). Monthly restore drill.

## API — OpenAPI + Rate Limits
Versioning: URL /api/v2/ for breaking. Header Accept for content negotiation.
Rate: auth=5/min/IP, read=60/min, write=30/min, LLM-heavy=5/min. 429+Retry-After.
Errors: {"error","code","details"}. JWT Bearer. Swagger /docs.

## GDPR Data Lifecycle
Collection(consent,minimize) → Processing(audit,lawful) → Storage(encrypt,access) → Retention(30/90/365d) → Deletion(purge,verify)
Art.17 erasure: delete PII, anonymize audit logs, delete sessions, schedule backup purge.

## Patterns (26) + Anti-Patterns
Patterns: solo seq par hier loop network router aggregator wave hitl mr bb
  comp tournament escalation voting speculative red-blue relay mob
  fractal_{qa,stories,tests,worktree} backprop_merge
Anti: GodFile DeepNesting HighCoupling CogComplexity CodeSlop Echo FakeTests LOCRegression
  MonolithCreep DistributedMonolith GoldenHammer PrematureOpt NIH HallucinationAcceptance
  PromptInjectionBlindness TokenWaste ModelWorship StackMismatch WaterfallDisguise TestAfterDeploy

## Adaptive Intelligence
Thompson(Beta selection) Darwin(team tournament) Evolution(GA pop=40 nightly)
RL(Q-learning state-action) Skills(det+LLM judge) AC(reward 14d convergence experiments)

## LLM — FROZEN
local-mlx Qwen3.5-mlx . minimax M2.5 . azure-oai gpt-5-mini/5.2/5.2-codex
azure-ai gpt-5.2 . nvidia Kimi-K2
MiniMax: native tool_calls no temp `<think>` stripped NEVER empty. GPT-5.x: reasoning budget>=16K

## Infra
OVH: 54.36.183.124 blue-green Docker. Azure: 3-node nginx lb n2→n1+n2 PG+Redis n3(10.0.1.6)
Deploy: rsync+docker-compose --force-recreate. CI: deploy-demo.yml

## Gotchas
NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
Container: /app/platform/ (OVH blue) or /app/macaron_platform/ (Azure)
PG advisory lock conn-scoped. SSE: curl --max-time. `platform/` shadows stdlib.
Think-strip: NEVER empty — 3-layer safety. Epic orch: _build_phase_prompt() not wf/store.py

## Stats
~215 agents . 26 patterns . 29 phase tpl . 50 wf . 57 tool mods . 1098 skills
4 bricks . 123 tpl . 375py/148KLOC . 61 PG tbl . 17 ops . 5 LLM providers
30 UX laws . 60 UI components . 30 A11Y patterns . 25 SBD controls . 59 design tokens
12 RBAC roles . 40 i18n languages . 15 bg tasks . 20 skeleton macros
