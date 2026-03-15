# SF Platform — Copilot Instructions

## RUN
```bash
cd _SOFTWARE_FACTORY
pip install -r requirements.txt
python -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
# NO --reload (shadows stdlib `platform`) . --ws none (SSE only)
```

## ARCH — FastAPI + Jinja2 + HTMX + SSE (no WS, zero build step)
```
Web (routes, templates/123)  → HTMX endpoints, Jinja2 HTML
Sessions (runner.py)         → User↔Agent bridge, SSE events
Agents (executor.py)         → Tool-call loop (max 15 rds) + per-agent no-think inference
Orchestrator (engine.py)     → 26 pattern impls (solo→fractal→mob) + tier-based history
Epic Orch (epic_orch.py)     → 15-phase product-lifecycle, sprint loop + phase memory storage
A2A (bus.py, veto.py)        → Inter-agent msg + veto hierarchy
LLM (client.py)              → 5-provider auto-fallback (azure→minimax→local)
Phase Memory (phase_memory)  → Rule-based telegraphic digests (~100 tok/phase, 0 LLM cost)
Memory (manager.py)          → 4-layer: project/global/vector/short-term
Traceability (traceability/) → E2E UUID chain + stores(AC/Journey/Migration/WhyLog)
Security (security/)         → 25 SBD controls, prompt_guard, output_validator
AC (ac/)                     → reward(14-dim), convergence, experiments, skill_thompson
```

## PRODUCT-LIFECYCLE — 15 Phases
ideation(network) → strategic-committee(HITL) → project-setup(sequential) → architecture(aggregator) → design-system(sequential) → dev-sprint(hierarchical) → build-verify(sequential) → cicd(sequential) → ux-review(loop) → qa-campaign(loop) → qa-execution(parallel) → deploy-prod(HITL) → **traceability-check**(sequential) → tma-router(router) → tma-fix(loop)

## TOKEN OPTIMIZATION — Hybrid 3-lever (arXiv:2603.05488)
```
Lever 1: Tier-based history — producers=30 reviewers=15 coordinators=8 msg cap
Lever 2: Per-agent no-think — tags(orchestrator/coordination/review/audit) auto-infer
Lever 3: Per-phase no-think — disable_thinking:true in workflow YAML phase config
Lever 4: Phase memory — rule-based digests (~100tok/phase) between phases (0 LLM cost)
         → backfill_missing_summaries() on crash-recovery resume
         → _build_node_context() prepends "MISSION MEMORY" to all agents
```
Files: llm/phase_memory.py . engine.py(_build_node_context) . executor.py(disable_thinking) . epic_orch.py(store+backfill)
Context tiers: L0=routing(no memory) L1=executor(limited) L2=organizer(full)

## TRACEABILITY — E2E UUID Chain
```
Persona(pers-XXXX) → Feature(feat-XXXX) → Story(us-XXXX) → AC(ac-XXXX,Gherkin)
  → IHM(route,CRUD,RBAC) → Code(// Ref: feat-XXXX) → TU(// Verify: ac-XXXX) → E2E
```
Team: trace-lead(Nadia,VETO) trace-auditor(Mehdi) trace-writer(Sophie) trace-monitor(Lucas)
DB: features, user_stories, acceptance_criteria, legacy_items, traceability_links
Tools: legacy_scan, traceability_link, traceability_coverage, traceability_validate
Stores: AcceptanceCriteriaStore(CRUD+coverage) JourneyStore(CRUD+migrate) MigrationStore(links+orphans+matrix)
Auto-persist: _auto_persist_backlog() parses PM markdown → features/stories in DB
Tests: tests/test_traceability.py — AC/Journey/Migration/WhyLog stores + make_id()

## ADVERSARIAL GUARD (Swiss Cheese)
L0 det (0ms): 25 checks. L1 LLM semantic. Score: <5=pass 5-6=soft >=7=reject
MAX_RETRIES=1 + PUA escalation. Force reject: HALLUC/SLOP/STACK_MISMATCH/FAKE_BUILD

## SECURITY — 25 SBD Controls (v1.1, SOC2+ISO27001)
L1: Input validation, Prompt injection, CSP/headers
L2: Auth(Argon2id), Authz(default-DENY), Least privilege
L3: Secrets mgmt, Crypto(AES-256-GCM), Data minimization
L4: Audit logging, Rate limiting, SSRF prevention, Error handling
L5: Deps security, CI/CD integrity, Model integrity, Prompt protection, RAG security,
    Output validation, CORS, Fail secure, Governance, Asset inventory, Incident response, Privacy

## COMPLIANCE
SOC2: CC1-CC8 all implemented. ISO27001 Annex A: 13 controls mapped.
RBAC: admin cto pm lead_dev developer qa devops security trace_lead viewer auditor scrum_master

## UX LAWS (30 — lawsofux.com)
Hick's(min choices) Fitts's(44px targets) Doherty(<400ms) Jakob's(familiar)
Miller's(7±2) Peak-End(positive end) Postel's(liberal in/strict out)
Gestalt: Proximity Similarity CommonRegion Pragnanz UniformConnectedness
Cognitive: Load Bias Chunking MentalModel WorkingMemory

## A11Y — WAI-ARIA APG (30 patterns)
Accordion Alert AlertDialog Breadcrumb Button Carousel Checkbox Combobox Dialog Disclosure
Feed Grid Landmarks Link Listbox Menu MenuButton Meter RadioGroup Slider Spinbutton
Switch Table Tabs Toolbar Tooltip TreeView Treegrid WindowSplitter
Rules: semantic HTML . keyboard . accessible name . focus mgmt . not color-only . 4.5:1 contrast

## i18n — 40 Languages + RTL
LTR(34): en fr es pt de it nl pl ro cs sk hu hr bg uk ru el tr vi th ko ja zh-CN zh-TW id ms tl hi bn sw am ha yo ig
RTL(6): ar he fa ur ps ku — CSS logical properties, dir="rtl", flexbox auto-reverses

## UI — 60 Components + Design Tokens
Atoms(12) Molecules(28) Organisms(12). Icons: SVG Feather ONLY. No emoji.
Skeleton: every data component needs .sk variant. aria-busy="true". shimmer 1.5s.
Tokens: --bg-primary:#0f0a1a --purple:#a855f7 --success:#10b981 --error:#ef4444
  JetBrains Mono. Space: xs-2xl(0.25-3rem). Radius: sm-full. Z: 100-500.

## OBSERVABILITY
OTEL traces: mission/phase/agent/tool spans. Prometheus metrics.
Alerts: MissionStuck(>2h) LLMFailing(>10fb/5m) HighRejectRate(>80%)
Health: /api/health /api/ready(503 drain) /api/metrics

## DR — RTO/RPO
Critical(15min/0): auth,DB. Important(1h/5m): missions. Standard(4h/1h): analytics.
Blue-green Docker. PG WAL streaming. Backup: hourly(48h) daily(30d) weekly(90d).

## API — OpenAPI + Rate Limits
Versioning: URL /api/v2/. Rate: auth=5/min read=60/min write=30/min LLM=5/min.
JWT Bearer. Swagger /docs. Errors: {"error","code","details"}. 429+Retry-After.

## GDPR
Collection→Processing→Storage→Retention→Deletion. Art.17 erasure procedure.
Data classification: Public/Internal/Confidential/Restricted. 30/90/365d retention.

## SKILLS (7 deep skills)
ux-laws-deep.md(30 laws) ui-components-deep.md(60 comp+tokens) a11y-wai-aria-deep.md(30 patterns)
secure-by-design-deep.md(25 SBD) i18n-rtl-40lang.md(40 lang+RTL) patterns-antipatterns-deep.md(26+22)
observability-api-data-dr-deep.md(OTEL+API+GDPR+DR)

## CONVENTIONS
- @dataclass + Store singletons. Relative imports.
- NEVER `import platform` top-level. No emoji. SSE only (--ws none).
- Templates: base.html → {% block content %} . HTMX hx-get/post/swap
- CSS vars. JetBrains Mono. card/list views via view_switcher.html

## STATS
~221 agents . 26 patterns . 32 phase tpl . 69 wf . 54 tool mods . 139 skills
60 UI comp . 30 UX laws . 30 A11Y patterns . 25 SBD controls . 59 tokens . 12 RBAC roles
40 i18n langs . 375py/148KLOC . 62 PG tbl . 17 ops . 5 LLM providers
