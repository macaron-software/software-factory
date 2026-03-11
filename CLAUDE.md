# SF Platform — Agentic Workflow Engine

## Tree
```
platform/              FastAPI :8090(prod) :8099(dev)
  server.py            uvicorn (NEVER --reload, --ws none)
  web/routes/          10 route mods (helpers.py: _parse_body JSON|form)
  a2a/                 A2A bus, negotiation, veto
  agents/store.py      AgentDef DC, 193 agents PG
  agents/executor.py   LLM tool-call loop (max 15 rds)
  agents/adversarial.py L0 det + L1 LLM guard (score 0-100, reject<40)
  agents/tool_runner.py dispatch 134 schemas, traceability reg
  agents/tool_schemas/  __init__ _platform(TRACEABILITY_SCHEMAS) _mapping(ROLE_TOOL_MAP)
  patterns/engine.py   run_pattern(PatternDef,sid,task) → 21 types
  patterns/impls/      solo seq par loop hier net router aggr wave hitl comp bb mr
                       tournament escalation voting speculative red-blue relay mob
  workflows/store.py   PM v2 orchestrator, _PHASE_TEMPLATES(28), _PATTERN_CATALOG(21)
  workflows/builtins.py YAML→WorkflowDef (pm_driven merge into config)
  workflows/defs/      YAML wf defs (feature-sprint, data-migration…)
  traceability/        migration_store.py — legacy_items + traceability_links CRUD
  tools/traceability_tools.py  4 BaseTool: legacy_scan link coverage validate
  llm/client.py        Multi-provider + cooldown/retry + _provider_cooldown{}
  tools/               code git deploy build memory security browser mcp-bridge traceability
  services/
    epic_orchestrator.py  phase dispatch, sprint loop, PM_GATE
    pm_checkpoint.py      quality score → retry/advance/skip
    auto_resume.py        PG advisory lock, resume stuck
  missions/            SAFe lifecycle + ProductBacklog
  ops/                 auto-heal chaos endurance backup
  mcps/                MCP srv mgr (fetch memory playwright)
cli/sf.py              sf status | sf ideation "…" | sf missions list
dashboard/             Monitor UI :8080
tests/                 52 pytest + 82 playwright E2E
```

## PM v2 — Lego-brick Orchestrator
After each phase PM LLM picks: next|loop|done|skip|**phase** (new dynamic brick).
`phase` = compose: pattern + team + gate + feedback → in-mem PatternDef+WorkflowPhase → _phase_queue.
PM checkpoint: quality score → retry if <50%, advance if OK. PM_GATE: build PASS/FAIL + sprint N/M.
PM_OVERRIDE: force retry if build failed even when agent claims success.

```
workflows/store.py layout:
  L538   _PATTERN_CATALOG (21 types + desc)
  L556   _FEEDBACK_TYPES _GATE_TYPES
  L580   _PHASE_TEMPLATES (28 reusable bricks)
  L639   _build_agent_catalog() — agents grouped by role
  L660   _PM_DECISION_PROMPT_V2 — full prompt w/ catalogs
  L700   _build_dynamic_phase(block) → (WPhase, PatDef)
  L720   _build_evidence() — extract src/build/test from tool_calls
  L740   _pm_checkpoint() — call PM LLM, parse JSON, fallback v1
  L810+  run_workflow() — _dynamic_patterns{} + _phase_queue[]
  L880   pattern lookup: _dynamic_patterns[id] || pattern_store.get(id)
  L892   config merge: phase.config > pattern.config (YAML wins)
  L1456  finally: PM checkpoint → handle phase|loop|skip|done|next
```

## 21 Patterns
solo sequential parallel loop hierarchical network router aggregator wave
human-in-the-loop composite blackboard map_reduce tournament escalation
voting speculative red-blue relay mob

## 28 Phase Templates
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review

## Gates
all_approved no_veto always best_effort

## Feedback (PM v2)
adversarial→config.adversarial_guard | tools→require_tool_validation | judge→network+debate | human→hitl

## Traceability System
```
DB tables: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(legacy→story/test)
Tools: legacy_scan  traceability_link  traceability_coverage  traceability_validate
Wired 3 layers: schemas(_platform.py) + registry(tool_runner.py) + roles(_mapping.py)
Role map: cdp/arch/product/dev=all4  qa=coverage+validate
Agents: dba architecte qa_lead product_manager data_engineer (skills assigned)
Adversarial enforces: // Ref: FEAT-xxx in source files (MISSING_TRACEABILITY check)
```

## Dataclasses
```
WorkflowPhase  id pattern_id name desc gate config retry_count skip_on_failure timeout
PatternDef     id name desc type agents[{id,agent_id}] edges config steps
AgentDef       id name role desc system_prompt provider model temp max_tokens skills[] tools[] tags[]
EpicRun        id workflow_id session_id status current_phase started_at cancel_reason
WorkflowRun    workflow session_id project_id current_phase phase_results[] status
PatternRun     pattern session_id project_id project_path phase_id max_iterations
```

## LLM ⛔ DO NOT CHANGE
```
local   local-mlx    Qwen3.5-mlx        :8080 ollama-compat
ovh     minimax      MiniMax-M2.5        tool_calls native, no mangle
azure   azure-openai gpt-5-mini(dflt)    +gpt-5.2 +gpt-5.2-codex
```
MiniMax: `<think>` stripped, json fences stripped, no temp, parallel_tool_calls=False
MiniMax quirk: agents slop on round 2+ (text-only, no tools) — adversarial catches it

## Envs
```
local   localhost:8099   PG localhost:5432   MLX :8080
ovh     $OVH_IP          blue-green /opt/software-factory/slots/{blue,green}
azure   $SF_NODE1_IP:8090  $SF_NODE2_IP   az vm run-command (no SSH)
```

## Run
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
pytest tests/ -v                              # unit
cd platform/tests/e2e && npx playwright test  # E2E
```

## Deploy OVH
```sh
git archive HEAD platform/ | tar -x -C /tmp/sf-deploy/
rsync -az --checksum --delete /tmp/sf-deploy/platform/ debian@$OVH_IP:/opt/software-factory/slots/blue/
rsync same → .../slots/factory/
docker compose up -d --no-deps --force-recreate platform-blue platform-factory
# Reseed: docker exec platform-blue python3 -c "WorkflowStore().seed_builtins()"
```

## Repos
GitHub macaron-software/software-factory AGPL-3.0 ← dev here
GitLab La Poste ← one-way sync via sync-to-laposte.sh (never edit)

## DB
PG psycopg `%s` params. Tables: agents sessions messages patterns workflows projects
ac_cycles epics features stories sprints pattern_runs legacy_items traceability_links epic_runs

## Rules
- YAML phase.config > pattern.config (merge L892)
- Agent resolve: explicit → TeamSelector(Darwin) → role → dev_fullstack
- `pm_driven: true` in wf YAML → PM checkpoint each phase (builtins.py merges to config)
- `_phase_queue` mutable — PM inserts/reorders dynamically
- `_dynamic_patterns{}` caches PM-built PatternDefs (run-scoped)
- Loop safety: `_pm_loop_limit=20`
- env-setup: MUST detect stack → install correct toolchain in Dockerfile (not generic)
- Agent persona: MUST emphasize tool usage (CRITICAL BEHAVIOR RULES pattern)
- _auto_qa_screenshots: dispatches to platform-specific helpers, skips native in Docker (no GUI)
- Git: AC wf creates agent branches — ALWAYS commit before launching cycle
