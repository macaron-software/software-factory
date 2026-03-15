# Software Factory — Copilot Instructions

## CRITICAL — Import Trap
`platform/` shadows stdlib. NEVER `import platform` — use `from platform.X import Y`.
Same issue blocks `--reload`. Always: `--ws none`, no `--reload`.

## Run / Test / Lint
```bash
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
make run                                    # Docker → :8090
ruff check platform/ --select E9            # syntax HARD gate
python scripts/complexity_gate.py platform/  # CC>10err LOC>500err MI<10err
pytest tests/ -v                            # needs PG running
make test                                   # full suite
```

## Architecture
Multi-agent SAFe orch. ~324 agents · 26 patterns · 69 wf · 32 phase tpl · 55 tools · 2389 skills.
Py3.11 + FastAPI + Jinja2 + HTMX + SSE. PG16(62tbl) + Redis7.

### Tree
```
platform/
  server.py              lifespan · GZipMiddleware · auth mw · 8 bg tasks
  agents/                exec · store(324) · adversarial(L0+L1) · tool_runner(134)
                         skills_integration.py — 3-tier: context→declared→trigger
                         subagent_prompts.py — implementer/spec-reviewer/code-quality/finish
                         pua.py — L0-L4 pressure · retry · debug methodology
                         cognitive.py — 4-layer composable profiles (atoms×archetypes×figures)
  patterns/engine.py     26 topo: solo seq par loop hier net router aggr wave hitl bb
                         fractal_worktree.py — decompose+isolate+finish (auto-merge)
  workflows/             store(PM v2) · defs/(69 YAML)
  services/              epic_orch · auto_resume · pm_checkpoint · notif
  llm/                   client(5 providers) · context_tiers.py — L0(120ch)/L1(600ch)/L2(1500ch)
  db/                    adapter(PG+SQLite) · schema(62tbl) · migrations
  web/routes/            HTMX routes · templates(124) · static/css/
  tools/(55)             code git deploy build web sec mem mcp trace ast lint lsp ds worktree
  ops/(17)               auto_heal · traceability · knowledge · project_audit
  auth/                  JWT+bcrypt · middleware(RBAC) · OAuth(GitHub/Azure)
  security/              prompt_guard · output_validator · audit
skills/                  2389 skills (139 YAML + GitHub cache)
projects/                per-project config + git_url
```

### Data Flow
Epic → Workflow(YAML phases) → epic_runs(PG) → PM LLM: next|loop|done|skip|phase(dyn).
compose: pattern + team + gate + feedback → PatternDef + WorkflowPhase → _phase_queue.

## NEVER
- `import platform` top-level · `--reload` · WebSocket (SSE only `--ws none`)
- emoji · gradient bg · inline styles · hardcoded hex · icon fonts (Feather SVG only)
- mock/fake/stub/dummy data — LIVE DATA ONLY · no test libs that cheat
- slop (hallucinated code, placeholder TODO, stub impl, `return {}`, `pass` as impl)
- change LLM models · set `*_API_KEY=dummy` — Infisical/.env only

## DB — LIVE = PostgreSQL
`data/platform.db` = STALE SQLite — NEVER query for live data.
PG advisory locks conn-scoped → 1 dedicated conn/mission.

## Cognitive Architecture (agents/cognitive.py)
4-layer composable profiles. All 324 agents assigned.

### Layers
```
L0: Atoms (7)     epistemic_style · cognitive_rhythm · uncertainty_handling
                   collaboration_posture · creativity_level · quality_bar · scope_instinct
L1: Archetypes (8) architect · scholar · pragmatist · hacker · guardian · mentor · operator · visionary
L2: Figures (15)   turing · von_neumann · dijkstra · knuth · hopper · linus_torvalds · kent_beck
                   rob_pike · guido_van_rossum · feynman · martin_fowler · bruce_schneier
                   don_norman · steve_jobs · jeff_dean
L3: Pressure       PUA L0-L4 → atom shifting (conservative under stress)
```

### Syntax
`"pragmatist"` · `"turing,don_norman"` (blend, last-wins) · `"hacker+quality_bar=craftsperson"` (override)
Figures extend archetypes: `turing` → `architect` base + `{quality_bar:perfectionist, scope_instinct:minimal}`

### API
`resolve_cognitive_arch(str) → CognitiveProfile` · `render_cognitive_prompt(profile) → str`
`apply_pressure_shift(profile, level) → CognitiveProfile` — explicit overrides survive pressure
`infer_archetype_for_role(role) → str` — 49 patterns, longest-match, default=pragmatist
`diff_profiles(a, b) → dict` · `cognitive_ab_variants(a, b)` — A/B testing

### Distribution (324 agents)
pragmatist:216 · mentor:45 · scholar:23 · visionary:12 · operator:12 · architect:11 · guardian:4 · hacker:1

## PUA — Pressure Unified Architecture (pua.py)
L0(0-1 fails)=normal · L1(2)=switch · L2(3)=root-cause · L3(4)=7pt-checklist · L4(5+)=escalate
`get_pressure_level(fails) → int` · `build_retry_prompt(task=,feedback=,consecutive_failures=,agent_name=)`
PUA+Cognitive: L1→iterative · L2→+conservative,pragmatic · L3→+minimal,conservative · L4→deep_focus,perfectionist

## Git Worktree Isolation (tools/git_tools.py)
`git_worktree` tool: create/list/remove isolated worktrees per agent task.
11 git tools: init status diff log commit push create_pr get_pr_diff post_pr_review merge_pr worktree.
Fractal pattern: auto-decompose → parallel worktrees → auto-merge clean branches.

## Superpowers (obra/superpowers-inspired)
### Context Auto-Trigger (skills_integration.py)
7 phases: debug/review/implement/plan/test/security/deploy.
Keywords in mission text → mandatory skills injected before trigger matching.
3-tier priority: context-pattern → declared → trigger-matched.

### Subagent Prompts (subagent_prompts.py)
4 builders: `build_implementer_prompt` (TDD + DONE/NEEDS_CONTEXT/BLOCKED)
· `build_spec_reviewer_prompt` (APPROVED/REJECTED + MISSING/WRONG/EXTRA)
· `build_code_quality_reviewer_prompt` (Critical/Important/Minor + APPROVED/CHANGES_REQUESTED)
· `build_finish_prompt` (Merge/PR/Keep/Discard)

## Skills Tiered Loading (llm/context_tiers.py)
L0=120ch (routes/webhooks) · L1=600ch (standard) · L2=1500ch (reviews/top agents)
`select_tier(hierarchy_rank=, capability_grade=, task_type=) → ContextTier`
`format_skill_tiered(name, content, tier) → str`

## LSP Tools (tools/lsp_tools.py)
10 tools: 7 Python (definition references diagnostics symbols call_hierarchy rename hover) + 3 TypeScript.
Backend: Jedi (pure Python). 400-3600x faster than grep for goToDefinition.
Params: `file` (not `file_path`), absolute paths required.

## Traceability (live PG → session SQLite)
### UUID Scheme
Features: `feat-{id}` (676) · Stories: `us-{id}` (248) · ACs: `ac-{id}` (193)
Trace links: `tl-{type}-{id}` (590) · Personas: `p-{role}` (16)

### E2E Chain (8 layers)
Persona(16) → Feature(676) → Story(248) → AC(193,Gherkin)
→ IHM(43 feat-linked) → Code(45) → UnitTest(17) → E2E(14)
+ CRUD(655 handlers) + RBAC(49/49 route files)

### Cognitive Arch Traceability (100% complete)
7 features · 21 stories · 39 ACs · 24 trace links · 42/42 tests pass
Files: cognitive.py prompt_builder.py store.py pua.py git_tools.py migrations.py

### Integrity Tests (28+42 pass)
UUID format · referential integrity · bidirectional links · coverage 0-100%
gap detection · Gherkin completeness · Feature→Story→AC chain join

## UI / Frontend
- HTMX partial swaps: `hx-get="/partial/X" hx-trigger="load"` · returns HTML not JSON
- Skeleton loading: `.sk` shimmer · tiered L0(instant) → L1(gzip) → L2(on-demand)
- CSS custom props (tokens) · dark-first · `[data-theme]` light/dark/hi-contrast
- i18n: `{{ t('key') }}` · locales/*.json · 40 langs planned · RTL support (ar,he,fa,ur)

## Lighthouse — 100/100/100/91+
GZipMiddleware · meta description · /robots.txt · heading hierarchy · contrast 4.5:1+

## LLM — FROZEN
minimax M2.5 · azure-openai gpt-5-mini/5.2/5.2-codex · nvidia Kimi-K2 · local-mlx
MiniMax: no temp · no mangle · `<think>` stripped · parallel_tool_calls=False

## Security
JWT(15min access + 7d refresh) + bcrypt · rate limit/endpoint · Infisical secrets
CI pinned to SHA · prompt_guard.py · RBAC(49 files) · SOC2(92%) · ISO27001(88%)

## Code Style
PEP 8 (ruff) · type hints public APIs · conventional commits
Traceability refs: `# Ref: feat-*` (py) · `<!-- Ref: feat-* -->` (html) · `// Ref: feat-*` (ts)
Agent status: PENDING | RUNNING | COMPLETED | VETOED | FAILED — no DONE

## Gotchas
- Container: `/app/macaron_platform/` not `/app/platform/`
- SSE test: `curl --max-time` — urllib blocks forever
- Epic orch: `_build_phase_prompt()` not `workflows/store.py`
- `GZipMiddleware` (capital Z) from `starlette.middleware.gzip`
- AgentStore: DB agents have bare-string persona (by design); YAML agents use PersonaConfig dict
- LSP tools: `file` param not `file_path` · absolute paths · jedi>=0.19.0 required
- Cognitive: `resolve_cognitive_arch("")` returns empty profile (no crash); figures tried before archetypes
