# Macaron Agent Platform

## WHAT
Multi-agent SAFe orchestration. 215 agents, 25 patterns, 49 workflows, 28 phase templates.
FastAPI+HTMX+SSE. PG16+Redis7. Port 8099(dev)/8090(prod). Dark purple UI.
PM v2 Lego-brick orchestrator: dynamic phase composition at runtime.

## RULES
- NEVER `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- NEVER `--reload` — same stdlib shadow
- NEVER set `*_API_KEY=dummy` — keys from Infisical or `.env`
- NEVER change LLM model names/deployments — if LLM err check network/auth
- NO emoji (code/UI/docs) — SVG Feather icons only
- NO WebSocket — SSE only (`--ws none`)

## STACK
```
Python 3.11+ · FastAPI · Jinja2 · HTMX · SSE (no WS)
PG16 (~35 tables) · SQLite fb (no PG_DSN)
Redis 7 (rate limit, leader election) · optional
Infisical (secrets) · .env fb · Zero frontend build step
```

## RUN
```bash
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
```

## TEST
```bash
ruff check platform/ --select E9                  # syntax lint (HARD)
python scripts/complexity_gate.py platform/        # CC+MI+LOC (SOFT)
python -m pytest tests/test_platform_api.py -v     # API (needs PG)
```

## FILE MAP
```
platform/
  server.py              lifespan, drain, auth middleware
  agents/                executor, store(215), adversarial(L0+L1), tool_runner(134 schemas)
                         selection(Thompson), evolution(GA), simulator, rl_policy
  patterns/engine.py     25 topologies (20 catalog + 5 fractal/backprop)
  patterns/impls/        solo seq par loop hier net router aggr wave hitl comp bb mr
                         tournament escalation voting speculative red-blue relay mob
                         fractal_qa fractal_stories fractal_tests fractal_worktree backprop_merge
  workflows/store.py     PM v2 orchestrator, 28 phase templates, 20 pattern catalog
  workflows/defs/        49 YAML workflow definitions
  services/              epic_orchestrator pm_checkpoint auto_resume evidence push notification
  a2a/                   bus veto negotiation protocol jarvis_mcp jarvis_acp azure_bridge
  ac/                    reward convergence experiments skill_thompson
  security/              prompt_guard output_validator audit sanitize
  llm/client.py          multi-provider (azure-ai/azure-openai/nvidia/minimax/local-mlx/ollama)
  db/                    adapter(PG+SQLite) migrations tenant
  tools/(53)             code git deploy build web security memory mcp_bridge traceability
                         ast lint lsp sandbox perf_audit deep_bench sf_bench agent_bench
                         android browser chaos compose dead_code dep diag gsd infisical
                         jira knowledge llm_bench memory_bench mflux monitoring package
                         phase plan platform project quality registry reward rtk
                         sast security_pentest skill_eval team_bench test type_check workflow_bench
  traceability/          migration_store — legacy_items + traceability_links CRUD
  web/routes/            missions pages sessions workflows agents projects
    templates/(64)       Jinja2 HTMX partials
    static/              css(3) js(4+) avatars/
  rbac/                  roles x actions x artifacts matrix
  ops/(17)               auto_heal endurance_watchdog platform_watchdog chaos_endurance
                         backup restore health zombie_cleanup error_clustering
  mcps/                  MCP srv mgr (fetch memory playwright)
skills/                  1090 skill .md files
```

## PM v2 — Lego-brick Orchestrator
After each phase PM LLM picks: next|loop|done|skip|**phase** (new dynamic brick).
`phase` = compose: pattern + team + gate + feedback -> in-mem PatternDef+WorkflowPhase -> _phase_queue.
PM checkpoint: quality score -> retry if <50%, advance if OK.
PM_OVERRIDE: force retry if build failed even when agent claims success.
PM_GATE: build PASS/FAIL + sprint N/M. Loop safety: _pm_loop_limit=20.

## 25 Patterns (20 catalog + 5 impl-only)
```
solo sequential parallel loop hierarchical network router aggregator wave
human-in-the-loop map_reduce blackboard composite tournament escalation
voting speculative red-blue relay mob
+fractal_qa fractal_stories fractal_tests fractal_worktree backprop_merge
```

## 28 Phase Templates
```
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review
```

## 49 Workflows (YAML)
```
feature-sprint(primary) epic-decompose cicd-pipeline project-onboarding data-migration
ao-compliance canary-deployment chaos-scheduled code-simplify debate-decide
design-system-component documentation-pipeline dsi-platform-features dsi-platform-tma
error-monitoring-cycle feature-request hardening-sprint i18n-validation iac-pipeline
ideation-to-prod knowledge-maintenance license-compliance mobile-android-epic
mobile-ios-epic monitoring-setup pac-mac-compile performance-testing pi-planning
pr-auto-review product-lifecycle quality-improvement retrospective-quality review-cycle
rse-compliance sast-continuous security-hacking sf-pipeline skill-ab-test skill-eval
skill-evolution strategic-committee tech-debt-reduction test-campaign test-data-pipeline
tma-autoheal tma-maintenance backup-restore
```

## Traceability System
```
DB: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(legacy->story/test)
Tools: legacy_scan traceability_link traceability_coverage traceability_validate
Wired: schemas(_platform.py) + registry(tool_runner.py) + roles(_mapping.py)
Role map: cdp/arch/product/dev=all4  qa=coverage+validate
Adversarial enforces: // Ref: FEAT-xxx in source (MISSING_TRACEABILITY check)
```

## Quality Gates (17 layers)
| # | Gate | Block |
|---|------|-------|
| 1 | Guardrails — regex destructive-action intercept | HARD |
| 2 | Hierarchical veto — ABSOLUTE/STRONG/ADVISORY | HARD |
| 3 | Prompt injection guard — score 0-10, block@7 | HARD |
| 4 | Tool ACL — 5 layers: ACL, path sandbox, rate, write perms, git guard | HARD |
| 5 | Adversarial L0 — slop/mock/cheat/hallucination/echo/missing_traceability | HARD |
| 6 | Adversarial L1 — LLM semantic review | SOFT |
| 7 | AC reward fn — R[-1,+1], 14 dims, 8 critical (veto<60) | HARD |
| 8 | Convergence — plateau/regression/spike | SOFT |
| 9 | RBAC — roles x actions x artifacts | HARD |
| 10 | CI ruff lint (E9) | HARD |
| 11 | CI py_compile | HARD |
| 12 | CI pytest | HARD |
| 13 | CI complexity (radon CC+MI, LOC cap) | SOFT |
| 14 | SonarQube (optional) | SOFT |
| 15 | Deploy health — blue-green canary + rollback | HARD |
| 16 | Output validator — security sanitize | SOFT |
| 17 | Stale builtin pruner | SOFT |

## LLM ⛔ DO NOT CHANGE
| Env | Provider | Model |
|-----|----------|-------|
| Local | local-mlx | Qwen3.5-mlx (:8080 ollama-compat) |
| OVH | minimax | MiniMax-M2.5 (tool_calls native, NO mangle) |
| Azure | azure-openai | gpt-5-mini + gpt-5.2 + gpt-5.2-codex |
| Azure AI | azure-ai | gpt-5.2 (swedencentral) |
| NVIDIA | nvidia | Kimi-K2 (integrate.api.nvidia.com) |

## SAFe Vocab
```
Epic=MissionDef  Feature=FeatureDef  Story=UserStoryDef  Task=TaskDef
PI=MissionRun    Iteration=SprintDef  ART=agent teams    Ceremony=SessionDef
```

## Deploy
```bash
# OVH (blue-green Docker): slots/{blue,green,factory}/ -> --force-recreate
# Azure (systemd sf-platform): az vm run-command (no SSH)
# CI: .github/workflows/deploy-demo.yml
```

## Gotchas
- `platform/` shadows stdlib — never `import platform` top-level
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED (NO `DONE`)
- PG advisory lock: connection-scoped, dedicated conn per mission
- MiniMax M2.5: native tool_calls, no mangle, no temp, `<think>` stripped
- Container path: /app/macaron_platform/ (NOT /app/platform/)
- env-setup: MUST detect stack -> correct Dockerfile base (not generic python:3.12-slim)
- Agent persona: MUST emphasize tool usage (CRITICAL BEHAVIOR RULES pattern)
- SSE: use `curl --max-time` (urllib blocks indefinitely)
