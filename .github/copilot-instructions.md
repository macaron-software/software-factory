# Macaron Agent Platform

## WHAT
Multi-agent SAFe orchestration platform. ~193 agents, 21 patterns, 28 phase templates, 36 workflows.
PM v2 lego-brick orchestrator: phases = composable bricks (pattern + team + gate + feedback).
FastAPI+HTMX+SSE. PG16+Redis7. Port 8099(dev)/8090(prod). Dark purple UI.

## RULES
- NEVER delete `data/platform.db` — init_db() idempotent migrations
- NEVER `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- NEVER `--reload` — same stdlib shadow issue
- NEVER set `*_API_KEY=dummy` — keys from Infisical or `~/.config/factory/*.key`
- NEVER change LLM model names/deployments — working cfg, check network/auth instead
- NO emoji anywhere (code, UI, docs) — SVG Feather icons only
- NO WebSocket — SSE only (`--ws none`)
- NO `platform/` top-level import in stdlib-dependent code

## STACK
```
Python 3.11+ · FastAPI · Jinja2 · HTMX · SSE (no WS)
PG16 WAL+FTS5 (~35 tables) · Redis 7 (rate limit, leader elect)
Infisical (secrets) · .env fb · Zero build step · Zero ext deps frontend
```

## RUN
```bash
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
```

## TEST
```bash
ruff check platform/ --select E9                  # syntax lint (HARD)
python -m pytest tests/test_platform_api.py -v     # API tests (PG req)
python scripts/complexity_gate.py platform/        # CC+MI+LOC (SOFT)
```

## 21 PATTERNS
```
solo sequential parallel loop hierarchical network router aggregator wave
human-in-the-loop composite blackboard map_reduce tournament escalation
voting speculative red-blue relay mob
```

## 28 PHASE TEMPLATES (store.py _PHASE_TEMPLATES)
```
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review
```

## PM v2 — Lego-brick Orchestrator
After each phase PM LLM picks: next|loop|done|skip|**phase** (new dynamic brick).
`phase` = compose: pattern + team + gate + feedback → in-mem PatternDef+WorkflowPhase → _phase_queue.
PM checkpoint: quality score → retry/advance/skip. PM_GATE: build PASS/FAIL + sprint N/M.
Adversarial guard: L0 det (slop/mock/echo/hallucination) + L1 LLM — score 0-100, reject <40.

## TRACEABILITY SYSTEM
```
platform/traceability/migration_store.py  — legacy_items + traceability_links CRUD
platform/tools/traceability_tools.py      — 4 BaseTool classes
Tools: legacy_scan  traceability_link  traceability_coverage  traceability_validate
Wired: schemas(_platform.py) + registry(tool_runner.py) + roles(_mapping.py)
Roles: cdp/architecture/product/dev = all 4, qa = coverage+validate
Agents w/ skills: dba, architecte, qa_lead, product_manager, data_engineer
Source refs: // Ref: FEAT-xxx in every source file (adversarial enforced)
```

## QUALITY GATES (17 layers)
| # | Gate | Block |
|---|------|-------|
| 1 | Guardrails — regex destructive-action intercept | HARD |
| 2 | Hierarchical veto — ABSOLUTE/STRONG/ADVISORY | HARD |
| 3 | Prompt injection guard — score 0-10, block@7 | HARD |
| 4 | Tool ACL — 5 layers: ACL, path sandbox, rate, write, git | HARD |
| 5 | Adversarial L0 — slop/mock/cheat/hallucination/echo | HARD |
| 6 | Adversarial L1 — LLM semantic review (score 0-100) | SOFT |
| 7 | AC reward fn — R∈[-1,+1], 14 dims, veto if <60 | HARD |
| 8 | Convergence — plateau/regression/spike analysis | SOFT |
| 9 | RBAC — roles × actions × artifacts | HARD |
| 10-13 | CI: ruff E9, py_compile, pytest, complexity | HARD/SOFT |
| 14 | SonarQube (optional) | SOFT |
| 15 | Deploy health — blue-green canary + rollback | HARD |
| 16 | Output validator — security sanitize | SOFT |
| 17 | Stale builtin pruner — auto-cleanup orphans | SOFT |

## FILE MAP
```
platform/
├── server.py              lifespan, drain, auth middleware
├── agents/
│   ├── executor.py        LLM tool-call loop (max 15 rounds)
│   ├── store.py           193 agents CRUD + seed + prune
│   ├── adversarial.py     L0 det + L1 LLM guard
│   ├── tool_runner.py     tool dispatch (134 schemas)
│   ├── tool_schemas/      __init__ _platform _mapping (ROLE_TOOL_MAP)
│   ├── guardrails.py      regex destructive-action block
│   ├── permissions.py     5-layer tool ACL
│   ├── selection.py       Thompson Sampling Beta bandit
│   └── evolution.py       GA genome=PhaseSpec[], pop=40
├── patterns/engine.py     21 topologies, adversarial, RL hook
├── workflows/
│   ├── store.py           PM v2 orchestrator, _PHASE_TEMPLATES(28), _PATTERN_CATALOG(21)
│   ├── builtins.py        YAML→WorkflowDef loader (pm_driven merge)
│   └── definitions/       YAML wf defs (feature-sprint, data-migration…)
├── traceability/          migration_store.py — legacy items + links
├── services/
│   ├── epic_orchestrator.py  phase→pattern dispatch, sprint loop
│   ├── pm_checkpoint.py      PM gate: quality score, retry/advance
│   └── auto_resume.py        PG advisory lock, resume stuck runs
├── a2a/                   bus, veto, negotiation, jarvis MCP
├── ac/                    reward fn, convergence, experiments
├── security/              prompt_guard, output_validator, audit
├── llm/client.py          multi-provider (azure/minimax/local-mlx)
├── db/schema_pg.sql       DDL (~35 tables + legacy_items + traceability_links)
├── tools/                 code git deploy build web memory traceability MCP bridge
├── web/routes/            missions pages sessions workflows agents epics
│   templates/(64)         Jinja2 HTMX
└── rbac/                  roles, actions, artifacts
```

## SAFe VOCAB
```
Epic=MissionDef  Feature=FeatureDef  Story=UserStoryDef  Task=TaskDef
PI=MissionRun    Sprint=SprintDef    ART=agent teams     Ceremony=SessionDef
WSJF=(BV+TC+RR)/JD    Flow: PM→Phase→Pattern(agents)→Gate→PM checkpoint→next
```

## LLM CONFIG ⛔ DO NOT CHANGE
```
local     local-mlx      Qwen3.5-mlx       :8080 ollama-compat
ovh       minimax         MiniMax-M2.5      native tool_calls, no mangle
azure     azure-openai    gpt-5-mini(dflt)  +gpt-5.2 +gpt-5.2-codex
MiniMax: <think> stripped, json fences stripped, no temp, parallel_tool_calls=False
```

## DEPLOY
```
OVH demo:     docker blue-green slots/{blue,green,factory}/ --force-recreate
Azure Innov:  rsync + systemd sf-platform, 2 nodes
CI/CD:        .github/workflows/ci.yml + deploy-demo.yml
```

## GOTCHAS
- `platform/` shadows stdlib → `from platform.agents import ...` not `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock: connection-scoped → one conn per mission
- MiniMax M2.5: native tool_calls NO mangle. M2.1 legacy: role=tool→user
- Container path: `/app/macaron_platform/` not `/app/platform/`
- `/api/ready` + `/api/health`: auth bypass (PUBLIC_PATHS)
- SSE streams: `curl --max-time` — urllib blocks indefinitely
- Agent persona: MUST emphasize tool usage (see ft-auth-lead CRITICAL BEHAVIOR RULES)
- env-setup: MUST detect stack → install correct toolchain in Dockerfile (not generic python)
