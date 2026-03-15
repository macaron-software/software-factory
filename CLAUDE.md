# SF Platform — Quick Ref

## WHAT
Multi-agent SAFe orch. ~324 agents · 26 patterns · 69 wf · 32 phase tpl · 54 tool mods · 2389 skills.
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
  tools/(54)                 code git deploy build web sec mem mcp trace ast lint lsp ds
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

## PUA — Pressure Unified Architecture (pua.py)
`get_pressure_level(fails)` -> int (0=L0..4=L4)
L0(0-1) · L1(2)=switch · L2(3)=root-cause · L3(4)=7pt · L4(5+)=escalate
`build_retry_prompt(task=, feedback=, consecutive_failures=, agent_name=)`

## Skills Tiered Loading (llm/context_tiers.py)
L0=120ch · L1=600ch · L2=1500ch
`select_tier(hierarchy_rank=, capability_grade=, task_type=)` -> ContextTier
`format_skill_tiered(name, content, tier)` -> str

## Lighthouse — 100/100/100/91+
GZipMiddleware(capital Z) · meta description · /robots.txt · heading hierarchy · contrast 4.5:1+

## Epic Workflow Engine — PM v2
Epic -> wf(YAML) -> epic_runs(PG) -> PM LLM: next|loop|done|skip|phase(dyn).
on_complete: 41 wf auto-chain. Checkpoint: quality<50% retry. Cap: 20.

NEVER done if: build fail · tests fail · src<3 · adversarial reject(>=7) · AC unresolved
  · frontend missing design-system/ux-review · responsive/themes/WCAG missing

## Traceability — UUID-Linked (live PG -> session SQLite)

### UUID Scheme
Features: `feat-{uuid}` (669) · Stories: `us-{uuid8}` (227) · ACs: `ac-{uuid8}` (154)
Personas: `p-{role}` (16) · Trace links: `tl-{type}-{uuid8}` (566)

### E2E Chain (8 layers · 28 integrity tests)
Persona(16) -> Feature(669) -> Story(227) -> AC(154, Gherkin)
-> IHM(43) -> Code(38) -> UnitTest(17) -> E2E(14)
+ CRUD(655: 403G/202P/27D/13PA/10PU) + RBAC(49/49)

### Session SQLite Tables
| Table | Rows | Key Columns |
|-------|------|-------------|
| features | 669 | id,name,status,story_count,ac_count,has_{ihm,code,unit_test,e2e_test,crud,rbac},coverage_pct |
| user_stories | 227 | id,title,feature_id(FK),status,ac_count |
| acceptance_criteria | 154 | id,feature_id,story_id(FK),title,given/when/then_text,status |
| personas | 16 | id,name,role,feature_count |
| trace_links | 566 | id,source_type,source_id,target_type,target_id,link_type,verified |
| traceability_matrix | 14 | id,layer,total,covered,pct,details |

### Gaps
Feature->Story: 70/669 (10.5%) · Story->AC: 154/227 (67.8%)
Fully traced (all 8 layers): 8 features
Annotations: .py=`# Ref: feat-*` · .html=`<!-- Ref: feat-* -->` · .ts=`// Ref: feat-*`

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
