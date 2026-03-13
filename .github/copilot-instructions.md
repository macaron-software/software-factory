# SF Platform — Quick Ref

## WHAT
Multi-agent SAFe orch. ~218 agents . 26 patterns . 49 wf . 28 phase tpl . 52 tool mods . 1090 skills.
FastAPI+HTMX+SSE. PG16(61tbl)+Redis7. 372py/146KLOC. Port 8099(dev)/8090(prod). Dark purple UI.

## NEVER
- `import platform` top-level — shadows stdlib; use `from platform.X import Y`
- `--reload` — same shadow
- `*_API_KEY=dummy` — Infisical or `.env`
- change LLM models — if err check network/auth
- emoji . WebSocket — SSE only (`--ws none`) . SVG Feather only

## Stack
Py3.11 . FastAPI . Jinja2 . HTMX . SSE . PG16(61tbl WAL+FTS5) . SQLite fb . Redis7 . Infisical . zero build

## Run / Test
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9              # syntax HARD
python scripts/complexity_gate.py platform/   # CC+MI+LOC SOFT
pytest tests/test_platform_api.py -v          # API (PG req)
```

## Tree
```
platform/                       372py 146KLOC
  server.py                     lifespan . drain . auth mw
  agents/                       exec . store(~215) . adversarial(L0+L1) . tool_runner(134)
                                selection(Thompson) . evolution(GA) . rl(Q) . darwin . skill_broker
  patterns/engine.py            26 topo: solo seq par loop hier net router aggr wave
                                hitl mr bb comp tournament escalation voting speculative
                                red-blue relay mob fractal_{qa,stories,tests,worktree} backprop
  workflows/                    store(PM v2, 28 tpl) . defs/(49 YAML) . builtins
  services/                     epic_orch . auto_resume . pm_checkpoint . evidence . notif
  a2a/                          bus . veto . negotiation . jarvis_mcp . azure_bridge
  ac/                           reward(14d) . convergence . experiments . skill_thompson
  security/                     prompt_guard . output_validator . audit . sanitize
  llm/client.py                 5 providers: azure-ai/azure-openai/nvidia/minimax/local-mlx
  db/                           adapter(PG+SQLite) . schema(61tbl) . migrations . tenant
  tools/(52)                    code git deploy build web sec mem mcp trace ast lint lsp ...
  web/routes/                   missions pages sessions wf agents projects . tpl(117)
  rbac/ ops/(17) mcps/ modules/(24) bricks/ metrics/
skills/                         1090 .md
```

## PM v2 — Lego Orchestrator
Phase -> PM LLM: next|loop|done|skip|**phase**(dynamic brick).
compose: pattern+team+gate+feedback -> PatternDef+WorkflowPhase -> _phase_queue.
Checkpoint: quality<50% -> retry. PM_OVERRIDE: force on build fail. Cap: 20.

## Quality Gates (17)
| # | Gate | |
|---|------|--|
| 1 | Guardrails regex destruct-action | HARD |
| 2 | Veto ABSOLUTE/STRONG/ADVISORY | HARD |
| 3 | Prompt inject score 0-10 block@7 | HARD |
| 4 | Tool ACL 5-layer (acl.sandbox.rate.write.git) | HARD |
| 5 | Adversarial L0 — 25 det checks | HARD |
| 6 | Adversarial L1 — LLM semantic | SOFT |
| 7 | AC reward R in [-1,+1] 14d 8crit@60 | HARD |
| 8 | Convergence plateau/regr/spike | SOFT |
| 9 | RBAC roles x actions x artifacts | HARD |
| 10-12 | CI ruff.compile.pytest | HARD |
| 13 | CI complexity radon CC+MI LOC | SOFT |
| 14 | SonarQube ext | SOFT |
| 15 | Deploy blue-green canary | HARD |
| 16 | Output validator | SOFT |
| 17 | Stale builtin prune | SOFT |

CC fn >10err >5warn . LOC >500err >300warn . MI <10err <20warn

## SAFe Vocab
Epic=MissionDef . Feature=FeatureDef . Story=UserStoryDef . PI=MissionRun . Sprint=SprintDef

## LLM — FROZEN
local-mlx Qwen3.5-mlx . minimax M2.5 . azure-openai gpt-5-mini/5.2/5.2-codex
azure-ai gpt-5.2 . nvidia Kimi-K2

## Deploy
OVH: blue-green Docker slots/{blue,green,factory}/ --force-recreate
Azure: systemd sf-platform via az vm run-command . Innovation: 3-node nginx lb
CI: .github/workflows/deploy-demo.yml

## Gotchas
- `platform/` shadows stdlib — NEVER `import platform`
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- PG advisory lock conn-scoped -> dedicated conn/mission
- MiniMax M2.5: native tool_calls . no mangle . no temp . `<think>` stripped
- Container: /app/macaron_platform/ not /app/platform/
- SSE: `curl --max-time` — urllib blocks
- Epic orch: _build_phase_prompt() not workflows/store.py

## PUA / Motivation
pua.py: Iron Rules+Proactivity ALL agents. L1-L4 pressure on retry.
agent.motivation field: injected in prompt. L2+ fires [PERSONAL ACCOUNTABILITY] hook.
_PUA_QA_BLOCK: QA = REVIEWER not IMPLEMENTER.
5-step debug each retry: Smell→Elevate→Mirror→Execute→Retrospective

## Traceability
Adversarial L0: MISSING_TRACEABILITY — all .py/.ts files need `# Ref: FEAT-xxx`
Tools: legacy_scan . traceability_coverage . traceability_validate . traceability_link
Team: team-traceability (art-platform) — 4 agents: trace-lead/trace-auditor/trace-writer/trace-monitor
Scheduler: ops/traceability_scheduler.py every 6h — SAFe hierarchy audit, incidents on >3 gaps
PM v2: auto-inserts traceability-check after dev phases
