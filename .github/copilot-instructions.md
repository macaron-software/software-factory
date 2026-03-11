# Macaron Agent Platform

## WHAT
Multi-agent SAFe orchestration platform. ~193 agents, 12 patterns, 19 workflows.
FastAPI+HTMX+SSE. PG16+Redis7. Port 8099(dev)/8090(prod). Dark purple UI.

## RULES
- NEVER delete `data/platform.db` — init_db() idempotent migrations
- NEVER `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- NEVER `--reload` — same stdlib shadow issue
- NEVER set `*_API_KEY=dummy` — keys from Infisical or `~/.config/factory/*.key`
- NEVER change LLM model names/deployments — if LLM err check network/auth
- NO emoji anywhere (code, UI, docs) — SVG Feather icons only
- NO WebSocket — SSE only (`--ws none`)

## STACK
```
Python 3.11+ · FastAPI · Jinja2 · HTMX · SSE (no WS)
PG16 WAL+FTS5 (~35 tables) · SQLite fb (no PG_DSN)
Redis 7 (rate limit, leader election) · optional
Infisical (secrets) · .env fb · Zero frontend build step
```

## RUN
```bash
# Dev (NEVER --reload, ALWAYS --ws none)
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
# Detached
nohup python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none > /tmp/sf.log 2>&1 &
```

## TEST
```bash
ruff check platform/ --select E9                  # syntax lint (HARD gate)
python scripts/complexity_gate.py platform/        # CC+MI+LOC (SOFT gate)
python -m pytest tests/test_platform_api.py -v     # API tests (needs PG)
```

## QUALITY GATES (17 layers)
| # | Gate | Type | Block |
|---|------|------|-------|
| 1 | Agent guardrails — regex destructive-action intercept | deterministic | HARD |
| 2 | Hierarchical veto — ABSOLUTE/STRONG/ADVISORY | deterministic | HARD |
| 3 | Prompt injection guard — score 0-10, block@7 | deterministic | HARD |
| 4 | Tool ACL — 5 layers: ACL, path sandbox, rate, write perms, git guard | deterministic | HARD |
| 5 | Adversarial L0 — slop/mock/cheat/hallucination/echo detection | deterministic | HARD |
| 6 | Adversarial L1 — LLM semantic review | LLM | SOFT |
| 7 | AC reward fn — R in [-1,+1], 14 dims, 8 critical (veto if <60) | deterministic | HARD |
| 8 | Convergence detection — plateau/regression/spike analysis | deterministic | SOFT |
| 9 | RBAC — roles x actions x artifacts matrix | deterministic | HARD |
| 10 | CI ruff lint (E9 syntax) | deterministic | HARD |
| 11 | CI py_compile | deterministic | HARD |
| 12 | CI pytest (48 tests, real PG) | deterministic | HARD |
| 13 | CI complexity gate — radon CC+MI, LOC cap | deterministic | SOFT |
| 14 | SonarQube (external, optional) | deterministic | SOFT |
| 15 | Deploy health check — blue-green canary + rollback | deterministic | HARD |
| 16 | Output validator — security sanitize | deterministic | SOFT |
| 17 | Stale builtin pruner — auto-cleanup orphaned agents | deterministic | SOFT |

### Complexity thresholds (scripts/complexity_gate.py)
```
CC per fn:    warn >5 (grade C)    error >10 (grade D+)
LOC per file: warn >300            error >500
MI per file:  warn <20 (grade C)   error <10 (grade D)
```

## FILE MAP
```
platform/
  server.py             lifespan, drain, auth middleware
  agents/               executor, store, adversarial, tool_runner, tool_schemas,
                        selection(Thompson), evolution(GA), simulator, rl_policy
  patterns/engine.py    8 topologies, adversarial, RL hook
  services/             mission_orchestrator, auto_resume, epic_*
  a2a/                  bus, veto, negotiation, jarvis MCP
  ac/                   reward, convergence, experiments, skill_thompson
  security/             prompt_guard, output_validator, audit, sanitize
  llm/client.py         multi-provider (azure/minimax/local-mlx)
  db/                   adapter(PG+SQLite), schema_pg, migrations
  tools/                code, git, deploy, build, web, security, memory, MCP bridge
  web/routes/           missions, pages, sessions, workflows, agents, projects
    templates/(64)      Jinja2 HTMX partials
    static/             css(3) js(4+) avatars/
  rbac/                 roles, actions, artifacts
```

## SAFe VOCAB
```
Epic=MissionDef  Feature=FeatureDef  Story=UserStoryDef  Task=TaskDef
PI=MissionRun    Iteration=SprintDef ART=agent teams     Ceremony=SessionDef
WSJF=(BV+TC+RR)/JD  Sprint loop: Jarvis->Epic->Sprint->Feature->TDD->Adversarial->Deploy
```

## LLM CONFIG
| Env | Provider | Model | Notes |
|-----|----------|-------|-------|
| Local dev | local-mlx | Qwen3.5-mlx | port 8080, ollama-compat |
| OVH demo | minimax | MiniMax-M2.5 | native tool_calls, NO mangling |
| Azure prod | azure-openai | gpt-5-mini | AZURE_DEPLOY=1 |

Azure routing (AZURE_DEPLOY=1): reason->gpt-5.2, code->gpt-5.2-codex, default->gpt-5-mini
Rate limit: 15 rpm (Redis-backed or in-memory fb)

## DEPLOY
```bash
# OVH demo (blue-green Docker)
# slots/{blue,green,factory}/ -> --force-recreate
# Azure Innovation (systemd)
# CI: .github/workflows/deploy-demo.yml (rsync + chown + restart)
```

## GOTCHAS
- `platform/` shadows stdlib -- never `import platform` at top level
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED -- NO `DONE`
- PG advisory lock: connection-scoped, dedicated conn per mission
- Leader election: Redis SETNX, fb=True if Redis down (idempotent)
- MiniMax M2.5: native tool_calls, NO mangling (M2.1 legacy: role=tool->user)
- Container path: /app/macaron_platform/ (NOT /app/platform/)
- /api/ready + /api/health: auth bypass (PUBLIC_PATHS)
- SSE streams: use `curl --max-time` (urllib blocks indefinitely)
