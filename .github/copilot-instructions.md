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
Multi-agent SAFe orch. ~324 agents · 26 patterns · 69 wf · 32 phase tpl · 54 tools · 2389 skills.
Py3.11 + FastAPI + Jinja2 + HTMX + SSE. PG16(62tbl) + Redis7.

### Tree
```
platform/
  server.py              lifespan · GZipMiddleware · auth mw · 8 bg tasks
  agents/                exec · store(324) · adversarial(L0+L1) · tool_runner(134)
                         skills_integration.py — 3-tier: context→declared→trigger
                         subagent_prompts.py — implementer/spec-reviewer/code-quality/finish
                         pua.py — L0-L4 pressure · retry · debug methodology
  patterns/engine.py     26 topo: solo seq par loop hier net router aggr wave hitl bb
                         fractal_worktree.py — decompose+isolate+finish (auto-merge)
  workflows/             store(PM v2) · defs/(69 YAML)
  services/              epic_orch · auto_resume · pm_checkpoint · notif
  llm/                   client(5 providers) · context_tiers.py — L0(120ch)/L1(600ch)/L2(1500ch)
  db/                    adapter(PG+SQLite) · schema(62tbl) · migrations
  web/routes/            HTMX routes · templates(124) · static/css/
  tools/(54)             code git deploy build web sec mem mcp trace ast lint lsp ds
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

## UI / Frontend
- HTMX partial swaps: `hx-get="/partial/X" hx-trigger="load"` · returns HTML not JSON
- Skeleton loading: `.sk` shimmer · tiered L0(instant) → L1(gzip) → L2(on-demand)
- CSS custom props (tokens) · dark-first · `[data-theme]` light/dark/hi-contrast
- i18n: `{{ t('key') }}` · locales/*.json · 40 langs planned · RTL support (ar,he,fa,ur)

## Code Style
- PEP 8 (ruff) · type hints public APIs · conventional commits
- Traceability refs: `# Ref: feat-*` (py) · `<!-- Ref: feat-* -->` (html) · `// Ref: feat-*` (ts)
- Agent status: PENDING | RUNNING | COMPLETED | VETOED | FAILED — no DONE

## Superpowers (obra/superpowers-inspired)
### Context Auto-Trigger (skills_integration.py)
7 phases: debug/review/implement/plan/test/security/deploy.
Keywords in mission text → mandatory skills injected before trigger matching.
3-tier priority: context-pattern → declared → trigger-matched.
`_detect_context_phase(text) → list[str]` · `_CONTEXT_PATTERNS[phase] → skill_ids`

### Subagent Prompts (subagent_prompts.py)
4 builders: `build_implementer_prompt` (TDD + DONE/NEEDS_CONTEXT/BLOCKED)
· `build_spec_reviewer_prompt` (APPROVED/REJECTED + MISSING/WRONG/EXTRA)
· `build_code_quality_reviewer_prompt` (Critical/Important/Minor + APPROVED/CHANGES_REQUESTED)
· `build_finish_prompt` (Merge/PR/Keep/Discard)

### Worktree Finish (fractal_worktree.py)
Phase 3 after leaf execution. `_finish_worktree_branches()`:
auto-merge clean branches · keep branches w/ conflicts · discard empty branches.

## PUA — Pressure Unified Architecture (pua.py)
L0(0-1 fails)=normal · L1(2)=switch · L2(3)=root-cause · L3(4)=7pt-checklist · L4(5+)=escalate
`get_pressure_level(fails) → int` · `build_retry_prompt(task=,feedback=,consecutive_failures=,agent_name=)`
5-step: Smell→Elevate→Mirror→Execute→Retrospective

## Skills Tiered Loading (llm/context_tiers.py)
L0=120ch (routes/webhooks) · L1=600ch (standard) · L2=1500ch (reviews/top agents)
`select_tier(hierarchy_rank=, capability_grade=, task_type=) → ContextTier`
`format_skill_tiered(name, content, tier) → str`

## Traceability (live PG → session SQLite)
### UUID Scheme
- Features: `feat-{uuid}` (669 in PG) · Stories: `us-{uuid8}` (227) · ACs: `ac-{uuid8}` (154)
- Trace links: `tl-{type}-{uuid8}` — 566 bidirectional links (code/ihm/test→feature)

### E2E Chain (8 layers)
Persona(16) → Feature(669) → Story(227) → AC(154,Gherkin)
→ IHM(43 feat-linked) → Code(38) → UnitTest(17) → E2E(14)
+ CRUD(655 handlers) + RBAC(49/49 route files)

### Coverage Gaps (to improve)
Feature→Story: 70/669 (10.5%) · Story→AC: 154/227 (67.8%)
Feature→Code: 38/669 · Feature→E2E: 14/669
Fully traced (all 8 layers): 8/669 features

### Integrity Tests (28 pass)
UUID format · referential integrity · bidirectional links · coverage 0-100%
gap detection · Gherkin completeness · Feature→Story→AC chain join

## Lighthouse (all pages 100/100/100/91+)
GZipMiddleware · meta description · /robots.txt · heading hierarchy · contrast 4.5:1+
Login: 100/100/100/100 · Dashboard: 100/100/100/91 · Wiki/Projects: 100/100/100/91

## LLM — FROZEN
minimax M2.5 · azure-openai gpt-5-mini/5.2/5.2-codex · azure-ai gpt-5.2 · nvidia Kimi-K2 · local-mlx
MiniMax: no temp · no mangle · `<think>` stripped · parallel_tool_calls=False

## Security
JWT(15min access + 7d refresh) + bcrypt · rate limit/endpoint · Infisical secrets
CI pinned to SHA · prompt_guard.py · RBAC(49 files) · SOC2(92%) · ISO27001(88%)

## Gotchas
- Container: `/app/macaron_platform/` not `/app/platform/`
- SSE test: `curl --max-time` — urllib blocks forever
- Epic orch: `_build_phase_prompt()` not `workflows/store.py`
- Epic chat: `_auto_create_planning_run()` if no active run
- `GZipMiddleware` (capital Z) from `starlette.middleware.gzip`
- AgentStore: DB agents have bare-string persona (by design); YAML agents use PersonaConfig dict
