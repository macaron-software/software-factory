# SF Platform — Agentic Workflow Engine

## Stats
~215 agents . 26 patterns (20 catalog+5 fractal+backprop) . 49 wf . 28 phase tpl
52 tool mods . 134 schemas . 1090 skills . 372py/146KLOC . 61 PG tables

## NEVER
- `import platform` top-level (shadows stdlib) -> `from platform.X import Y`
- `--reload` (same) . `*_API_KEY=dummy` . change LLM models . emoji . WebSocket

## Stack
Py3.11 . FastAPI . Jinja2 . HTMX . SSE . PG16(61tbl WAL+FTS5) . SQLite fb . Redis7 . Infisical/.env

## Run / Test
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9              # syntax HARD
python scripts/complexity_gate.py platform/   # CC+MI+LOC SOFT
pytest tests/test_platform_api.py -v          # API (PG req)
```

## Tree
```
platform/  server.py          lifespan drain auth-mw
  agents/              exec store(~215) adversarial(L0+L1) tool_runner(134)
                       guardrails perms selection(Thompson) evolution(GA) rl(Q) darwin
  patterns/engine.py   26 topo: solo seq par loop hier net router aggr wave hitl mr bb
                       comp tournament escalation voting speculative red-blue relay mob
                       fractal_{qa,stories,tests,worktree} backprop_merge
  workflows/           store(PM v2, 28 tpl, 20 catalog) . defs/(49 YAML)
  services/            epic_orch . auto_resume . pm_checkpoint . evidence . notif
  a2a/                 bus veto negotiation jarvis_mcp azure_bridge
  ac/                  reward(14d) convergence experiments skill_thompson
  security/            prompt_guard output_validator audit sanitize
  llm/client.py        5 providers: azure-ai/azure-openai/nvidia/minimax/local-mlx
  db/                  adapter(PG+SQLite) schema(61tbl) migrations tenant
  tools/(52)           code git deploy build web sec mem mcp trace ast lint lsp ...
  traceability/        legacy_items + traceability_links CRUD
  web/routes/          missions pages sessions wf agents projects . tpl(117)
  rbac/ ops/(17) mcps/ modules/(24) bricks/ metrics/
cli/sf.py              sf status | sf ideation | sf missions list
skills/                1090 .md
```

## PM v2 — Lego Orchestrator
Phase -> PM LLM: next|loop|done|skip|**phase**(dynamic brick).
compose: pattern+team+gate+feedback -> PatternDef+WorkflowPhase -> _phase_queue.
Checkpoint: quality<50% -> retry. PM_OVERRIDE: force on build fail. Cap: 20.

```
store.py layout:
  L543   _PATTERN_CATALOG (20)   L556 _FEEDBACK_TYPES _GATE_TYPES
  L580   _PHASE_TEMPLATES (28 bricks)
  L700   _PM_DECISION_PROMPT_V2
  L754   _build_dynamic_phase(block) -> (WPhase, PatDef)
  L809   _build_evidence() — src/build/test from tool_calls
  L1054  _dynamic_patterns{} + _phase_queue[]
  L1592  PM inserts: _dynamic_patterns[id] = _dyn_pattern
```

## 28 Phase Templates
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review

## Gates and Feedback
Gates: all_approved . no_veto . always . best_effort
Feedback: adversarial->config.adversarial_guard | tools->require_tool_validation
          judge->network+debate | human->hitl

## Dataclasses
```
WorkflowPhase  id pattern_id name desc gate config retry_count skip_on_failure timeout
PatternDef     id name desc type agents[{id,agent_id}] edges config steps
AgentDef       id name role desc system_prompt provider model temp max_tokens skills[] tools[] tags[]
EpicRun        id workflow_id session_id status current_phase started_at cancel_reason
WorkflowRun    workflow session_id project_id current_phase phase_results[] status
PatternRun     pattern session_id project_id project_path phase_id max_iterations
```

## Quality Gates (17)
1-4 HARD: guardrails(regex) . veto(ABS/STRONG/ADV) . prompt_inject(block@7) . tool_acl(5-layer)
5-6: adversarial L0(25 det) HARD . L1(LLM) SOFT
7-9: AC reward(R[-1,+1] 14d 8crit@60) HARD . convergence SOFT . RBAC HARD
10-13: CI ruff.compile.pytest HARD . complexity(radon) SOFT
14-17: sonar SOFT . deploy canary HARD . output_validator SOFT . stale_prune SOFT

CC fn >10err >5warn . LOC >500err >300warn . MI <10err <20warn

## Traceability
DB: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(legacy->story/test)
Tools: legacy_scan . traceability_link . traceability_coverage . traceability_validate
Roles: cdp/arch/product/dev=all4 qa=coverage+validate
Adversarial: `// Ref: FEAT-xxx` enforced (MISSING_TRACEABILITY)

## LLM — FROZEN
local-mlx Qwen3.5-mlx . minimax M2.5(native tool_calls, no mangle, `<think>` stripped)
azure-openai gpt-5-mini/5.2/5.2-codex . azure-ai gpt-5.2 . nvidia Kimi-K2
MiniMax: no temp . parallel_tool_calls=False . json fences stripped
GPT-5.x: reasoning . max_completion_tokens not max_tokens . budget>=16K

## Envs
```
local    :8099   PG localhost:5432 . MLX :8080
ovh      OVH_IP blue-green Docker /opt/software-factory/slots/{blue,green}
azure    SF_NODE1_IP:8090 . SF_NODE2_IP . az vm run-command (no SSH)
innov    3-node: n2(nginx lb) n1(primary) n3(PG+Redis 10.0.1.6)
```

## Deploy
OVH: rsync -> --force-recreate Docker (blue/green/factory)
Azure: systemd sf-platform -> az vm run-command
CI: .github/workflows/deploy-demo.yml

## Rules
- YAML phase.config > pattern.config (merge L892)
- Agent resolve: explicit -> TeamSelector(Darwin) -> role -> dev_fullstack
- pm_driven:true -> PM checkpoint each phase
- _phase_queue mutable — PM inserts/reorders
- _dynamic_patterns{} run-scoped cache
- env-setup: detect stack -> correct Dockerfile
- Agent persona: emphasize tool usage (CRITICAL BEHAVIOR RULES)
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED — no DONE
- Container: /app/macaron_platform/ not /app/platform/
- `platform/` shadows stdlib
- SSE: `curl --max-time` (urllib blocks)

## Repo
GitHub macaron-software/software-factory (AGPL-3.0)
