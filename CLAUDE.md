# SF Platform — Quick Ref

## WHAT
Multi-agent SAFe orch. ~324 agents · 26 patterns · 69 wf · 32 phase tpl · 55 tool mods · 2389 skills.
FastAPI+HTMX+SSE. PG16(62tbl)+Redis7. 375py/148KLOC. Port 8099(dev)/8090(prod).

## ALWAYS — Start of Session
```sh
for d in _SOFTWARE_FACTORY _BABY MVP_ADA _HELP/aides-macaron _FLO _PSY YOLONOW; do
  (cd ~/_MACARON-SOFTWARE/"$d" && git pull --rebase --autostash 2>/dev/null)
done
```
PSY remote=github (not origin).

## NEVER
- `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- `--reload` (same shadow) · `*_API_KEY=dummy` — Infisical/.env
- change LLM models · emoji in UI · WebSocket — SSE only (`--ws none`) · SVG Feather icons only
- gradient bg · inline styles · hardcoded hex colors in UI
- fake/mock/stub data — LIVE DATA ONLY · no test libs that cheat (fake pass)
- no slop (hallucinated code, placeholder "TODO", stub impl) · no fallback anywhere
- no `return {}` / `return None` / `pass` as impl — real logic or raise NotImplementedError

## Stack
Py3.11 · FastAPI · Jinja2 · HTMX · SSE · PG16(62tbl WAL+FTS5) · SQLite fb · Redis7 · Infisical · zero build

## Run / Test
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9              # syntax HARD
python scripts/complexity_gate.py platform/   # CC+MI+LOC SOFT
pytest tests/ -v                              # API+unit (PG req)
```

## Tree
```
platform/                    375py 148KLOC
  server.py                  lifespan · GZipMiddleware · auth mw · 8 bg tasks
  agents/                    exec · store(324) · adversarial(L0+L1) · tool_runner(134)
                             skills_integration — 3-tier: context->declared->trigger
                             subagent_prompts — implementer/spec-reviewer/code-quality/finish
                             pua — L0-L4 pressure · retry · debug methodology
                             cognitive — 4-layer: atoms(7)×archetypes(8)×figures(15)×pressure(L0-L4)
                             selection(Thompson) · evolution(GA) · rl(Q) · darwin · skill_broker
  patterns/engine.py         26 topo: solo seq par loop hier net router aggr wave hitl mr bb
                             fractal_{qa,stories,tests,worktree} backprop
  llm/                       client(5 providers) · context_tiers — L0(120ch)/L1(600ch)/L2(1500ch)
  workflows/                 store(PM v2, 32 tpl) · defs/(69 YAML)
  services/                  epic_orch · auto_resume · pm_checkpoint · notif
  a2a/                       bus · veto · negotiation · jarvis_mcp · azure_bridge
  security/                  prompt_guard · output_validator · audit · sanitize
  auth/                      service(JWT+bcrypt) · middleware(RBAC) · ses(AWS SES)
  db/                        adapter(PG+SQLite) · schema(62tbl) · migrations · tenant
  tools/(55)                 code git deploy build web sec mem mcp trace ast lint lsp ds worktree
  ops/(17)                   auto_heal · traceability · knowledge · project_audit
  web/routes/                missions pages sessions wf agents projects auth · tpl(124)
skills/                      2389 skills (139 YAML + GitHub cache)
projects/                    per-project config + git_url
```

## DB — LIVE = PostgreSQL
DATABASE_URL=postgresql://macaron:macaron@localhost:5432/macaron_platform
data/platform.db = STALE SQLite — do NOT query for live data.
psql: PGPASSWORD=macaron /opt/homebrew/bin/psql -h localhost -U macaron -d macaron_platform

## Projects
| proj | repo | path | stack |
|------|------|------|-------|
| Sienna | macaron-software/sienna (priv) | _BABY | Rust/WASM+SvelteKit+iOS/Android |
| CareOps | macaron-software/careops | MVP_ADA | FastAPI+Next.js+Supabase+Rust/gRPC |
| SF | macaron-software/software-factory | _SOFTWARE_FACTORY | Python/FastAPI+HTMX |
| PSY | macaron-software/psy-platform | _PSY | Rust/Axum+React |
| MesAides | macaron-software/mes-aides | _HELP/aides-macaron | Rust+WASM+SwiftUI+Kotlin |

## Auth
JWT+bcrypt. Cookie: access 15min + refresh 7d. Rate limit: 5/60s per IP.
POST /api/auth/login · /register · /refresh · /logout · /forgot-password · /reset-password
OAuth: GitHub(/auth/github) · Azure AD(/auth/azure) · Demo(/api/auth/demo)

## Cognitive Architecture (agents/cognitive.py)
4-layer composable profiles. All 324 agents assigned. AgentCeption-inspired (MIT).

### Layers
```
L0: Atoms (7)       epistemic_style · cognitive_rhythm · uncertainty_handling
                     collaboration_posture · creativity_level · quality_bar · scope_instinct
L1: Archetypes (8)   architect scholar pragmatist hacker guardian mentor operator visionary
L2: Figures (15)     turing von_neumann dijkstra knuth hopper linus_torvalds kent_beck
                     rob_pike guido_van_rossum feynman martin_fowler bruce_schneier
                     don_norman steve_jobs jeff_dean
L3: Pressure (L0-L4) PUA-driven atom shifting under consecutive failures
```

### Syntax
`"pragmatist"` · `"turing,don_norman"` (blend, last-wins) · `"hacker+quality_bar=craftsperson"` (override)

### API
`resolve_cognitive_arch(str)` -> CognitiveProfile · `render_cognitive_prompt(profile)` -> str
`apply_pressure_shift(profile, level)` -> CognitiveProfile (overrides survive)
`infer_archetype_for_role(role)` -> str (49 patterns, longest-match)
`diff_profiles(a, b)` · `cognitive_ab_variants(a, b)` — A/B testing

### Distribution: pragmatist:216 mentor:45 scholar:23 visionary:12 operator:12 architect:11 guardian:4 hacker:1

### Pressure Shifts
L1→iterative · L2→+conservative,pragmatic · L3→+minimal,conservative · L4→deep_focus,perfectionist,consultative

## PUA — Pressure Unified Architecture (pua.py)
`get_pressure_level(fails)` -> int (0=L0..4=L4)
L0(0-1) · L1(2)=switch · L2(3)=root-cause · L3(4)=7pt · L4(5+)=escalate
`build_retry_prompt(task=, feedback=, consecutive_failures=, agent_name=)`

## Git Worktree Isolation
`git_worktree` tool: create/list/remove. 11 git tools total.
Fractal pattern: decompose → parallel worktrees → auto-merge clean branches.

## LSP Tools (tools/lsp_tools.py)
10 tools: 7 Python (definition refs diagnostics symbols call_hierarchy rename hover) + 3 TS.
Backend: Jedi. 400-3600x faster than grep. Params: `file` (not file_path), absolute paths.

## Superpowers (obra/superpowers-inspired)

### Context Auto-Trigger (agents/skills_integration.py)
7 phases: debug/review/implement/plan/test/security/deploy.
`_detect_context_phase(text)` -> `_CONTEXT_PATTERNS[phase]` -> mandatory skill injection.
3-tier: context-pattern -> declared -> trigger-matched.

### Subagent Prompts (agents/subagent_prompts.py)
`build_implementer_prompt` — TDD + DONE/NEEDS_CONTEXT/BLOCKED
`build_spec_reviewer_prompt` — APPROVED/REJECTED + MISSING/WRONG/EXTRA
`build_code_quality_reviewer_prompt` — Critical/Important/Minor
`build_finish_prompt` — Merge/PR/Keep/Discard

### Worktree Finish (patterns/impls/fractal_worktree.py)
Phase 3: `_finish_worktree_branches(repo, branches, session)`
Auto-merge clean · keep conflicting · discard empty.

## Skills Tiered Loading (llm/context_tiers.py)
L0=120ch · L1=600ch · L2=1500ch
`select_tier(hierarchy_rank=, capability_grade=, task_type=)` -> ContextTier
`format_skill_tiered(name, content, tier)` -> str

## Traceability — UUID-Linked (live PG → session SQLite)

### UUID Scheme
Features: `feat-{id}` (685) · Stories: `us-{id}` (262) · ACs: `ac-{id}` (221)
Personas: `p-{role}` (16) · Trace links: `tl-{type}-{id}` (615)

### E2E Chain (8 layers · 108 integrity tests)
Persona(16) → Feature(685) → Story(262) → AC(221, Gherkin)
→ IHM(43) → Code(45) → UnitTest(17) → E2E(14)
+ CRUD(655: 403G/202P/27D/13PA/10PU) + RBAC(49/49)

### Cognitive Arch Traceability (100%)
7 features · 21 stories · 39 ACs · 24 trace links · 42/42 tests
cognitive.py · prompt_builder.py · store.py · pua.py · git_tools.py · migrations.py

### SWE-CI / RC Fixes Traceability (100%)
9 features · 14 stories · 28 ACs · 25 trace links · 78 tests
pm_checkpoint.py · adversarial.py · engine.py · human_in_the_loop.py

### Session SQLite Tables
| Table | Rows | Key Columns |
|-------|------|-------------|
| features | 685 | id,name,status,story_count,ac_count,has_{ihm,code,unit_test,e2e,crud,rbac},coverage_pct |
| user_stories | 262 | id,title,feature_id(FK),status,ac_count |
| acceptance_criteria | 221 | id,feature_id,story_id(FK),title,given/when/then_text,status |
| personas | 16 | id,name,role,feature_count |
| trace_links | 615 | id,source_type,source_id,target_type,target_id,link_type,verified |
| traceability_matrix | 31 | id,layer,total,covered,pct,details |

### Annotations: .py=`# Ref: feat-*` · .html=`<!-- Ref: feat-* -->` · .ts=`// Ref: feat-*`

## ANC Metric — SWE-CI CI-Loop (services/pm_checkpoint.py)
NC = (p_i-p_0)/(p_*-p_0) improve · (p_i-p_0)/p_0 regress. ANC = mean(NC).
`TestResult`: total/passed/failed/skipped. `ANCScore`: baseline/current/target/nc/history/anc.
`run_test_gate(ws)` — auto pytest/Jest/cargo/Go. `compute_anc()` — NC+ANC.
`generate_test_gap_requirements()` — CI-loop architect→programmer bridge.
PM checkpoint: NC<-0.2 → force retry. PMDecision +test_result +anc_score.

## Maintainability Detectors (agents/adversarial.py)
8 _MAINTAINABILITY_PATTERNS: MAGIC_NUMBER · HARDCODED_CONFIG · GOD_FUNCTION
DEEP_INHERITANCE · BARE_EXCEPT · STRING_CONCAT_LOOP · MUTABLE_DEFAULT
Score +1 each (warning), cap 3/file. Total: 53 adversarial patterns.

## Lighthouse — 100/100/100/91+
GZipMiddleware(capital Z) · meta description · /robots.txt · heading hierarchy · contrast 4.5:1+

## Epic Workflow Engine — PM v2
Epic -> wf(YAML) -> epic_runs(PG) -> PM LLM: next|loop|done|skip|phase(dyn).
on_complete: 41 wf auto-chain. Checkpoint: quality<50% retry. Cap: 20.

NEVER done if: build fail · tests fail · src<3 · adversarial reject(>=7) · AC unresolved
  · frontend missing design-system/ux-review · responsive/themes/WCAG missing

## Quality Gates (17)
1-4 HARD: guardrails · veto · prompt_inject · tool_acl
5-6: adv L0(25 det) HARD · L1(LLM) SOFT
7-9: AC reward HARD · convergence SOFT · RBAC HARD
10-13: CI ruff/compile/pytest HARD · complexity SOFT
DATA RULE: no mock/fake/stub — live PG, real LLM, real file I/O.

## Design Tokens (CSS custom props)
Colors dark: --bg-primary=#0f0a1a · --purple=#a78bfa(accent) · --green=#34d399 · --red=#f87171
Type: system-ui · xs=.75rem base=1rem 2xl=1.5rem
Space(4px): 1=.25rem 2=.5rem 4=1rem 6=2rem · Radius: sm=4px default=10px lg=16px

## UI Components (60 — atomic)
Atoms(29) · Molecules(20) · Organisms(11). Icons: Feather SVG ONLY. No emoji.

## UX Laws (27) · A11Y (30 ARIA patterns) · i18n (40 langs + RTL)

## Compliance
SOC2: 92% · ISO27001: 88% · SecureByDesign: 96% · OWASP: 7/10 · GDPR: 92%

## Observability (OTEL)
Jaeger :16686 · /metrics · /api/health · /api/readiness · auto-heal 60s

## LLM — FROZEN
minimax M2.5 · azure-openai gpt-5-mini/5.2/5.2-codex · nvidia Kimi-K2 · local-mlx
MiniMax: no temp · no mangle · `<think>` stripped · parallel_tool_calls=False

## Deploy
OVH: blue-green slots/{blue,green}/ · Azure: systemd sf-platform · az vm run-command

## Gotchas
- `platform/` shadows stdlib — NEVER `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock conn-scoped · Container: /app/macaron_platform/
- SSE: `curl --max-time` · GZipMiddleware(capital Z)
- AgentStore: DB agents = bare-string persona; YAML = PersonaConfig dict
- LSP: `file` param not `file_path` · absolute paths · jedi>=0.19.0
- Cognitive: figures tried before archetypes · `resolve("")` = empty (no crash)
