# SF Platform — Agentic Workflow Engine

## Tree
```
platform/              FastAPI :8090(prod) :8099(dev)
  server.py            uvicorn (NEVER --reload, --ws none)
  web/routes/          10 route mods (helpers.py: _parse_body JSON|form)
  a2a/                 A2A bus, negotiation, veto
  agents/store.py      AgentDef DC, 192 agents PG
  patterns/engine.py   run_pattern(PatternDef,sid,task) → 13 types
  patterns/store.py    PatternDef DC (pure, no DB)
  patterns/impls/      solo seq par loop hier net router aggr wave hitl comp bb mr
  workflows/store.py   run_workflow() — PM v2 orchestrator
  workflows/defs/      YAML wf defs (feature-sprint, ac-improvement-cycle…)
  llm/client.py        Multi-provider + cooldown/retry + _provider_cooldown{}
  tools/               code git deploy memory security browser mcp-bridge
  missions/            SAFe lifecycle + ProductBacklog
  ops/                 auto-heal chaos endurance backup
  mcps/                MCP srv mgr (fetch memory playwright)
cli/sf.py              sf status | sf ideation "…" | sf missions list
dashboard/             Monitor UI :8080
tests/                 52 pytest + 82 playwright E2E
```

## PM v2 — Lego-brick Orchestrator
After each phase PM LLM picks: next|loop|done|skip|**phase** (new).
`phase` = compose dynamic brick: pattern + team + gate + feedback → in-mem PatternDef+WorkflowPhase → insert `_phase_queue`.

```
workflows/store.py layout:
  L538   _PATTERN_CATALOG (13 types + desc)
  L556   _FEEDBACK_TYPES _GATE_TYPES
  L570   _PHASE_TEMPLATES (8 reusable bricks)
  L580   _build_agent_catalog() — agents grouped by role
  L600   _PM_DECISION_PROMPT_V2 — full prompt w/ catalogs
  L680   _build_dynamic_phase(block) → (WPhase, PatDef)
  L700   _build_evidence() — extract src/build/test from tool_calls
  L720   _pm_checkpoint() — call PM LLM, parse JSON, fallback v1
  L810+  run_workflow() — _dynamic_patterns{} + _phase_queue[]
  L880   pattern lookup: _dynamic_patterns[id] || pattern_store.get(id)
  L892   config merge: phase.config > pattern.config (YAML wins)
  L1456  finally: PM checkpoint → handle phase|loop|skip|done|next
```

## 13 Patterns
solo sequential parallel loop hierarchical network router aggregator wave human-in-the-loop composite blackboard map_reduce

## Gates
all_approved no_veto always best_effort

## Feedback (PM v2)
adversarial→config.adversarial_guard | tools→require_tool_validation | judge→network+debate | human→hitl

## Dataclasses
```
WorkflowPhase  id pattern_id name desc gate config retry_count skip_on_failure timeout min_complexity
PatternDef     id name desc type agents[{id,agent_id}] edges config memory_config steps ab_alt_id ab_ratio
AgentDef       id name role desc system_prompt provider model temp max_tokens skills[] tools[] mcps[] tags[] hierarchy_rank
WorkflowRun    workflow session_id project_id current_phase phase_results[] status error
PatternRun     pattern session_id project_id project_path phase_id max_iterations
```

## LLM ⛔ DO NOT CHANGE
```
local   local-mlx    Qwen3.5-mlx        :8080 ollama-compat
ovh     minimax      MiniMax-M2.5        tool_calls native, no mangle
azure   azure-openai gpt-5-mini(dflt)    +gpt-5.2 +gpt-5.2-codex
```
MiniMax: `<think>` stripped, json fences stripped, no temp param, parallel_tool_calls=False

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

## Repos
GitHub macaron-software/software-factory AGPL-3.0 ← dev here
GitLab La Poste ← one-way sync via sync-to-laposte.sh (never edit)

## DB
PG psycopg `%s` params. Tables: agents sessions messages patterns workflows projects ac_cycles epics features stories sprints pattern_runs

## Rules
- YAML phase.config > pattern.config (merge L892)
- Agent resolve: explicit → TeamSelector(Darwin) → role → dev_fullstack
- `pm_driven: true` in wf YAML → PM checkpoint each phase
- `_phase_queue` mutable — PM inserts/reorders dynamically
- `_dynamic_patterns{}` caches PM-built PatternDefs (run-scoped)
- `_phase_catalog{}` maps phase.id→WorkflowPhase (incl dynamic)
- Loop safety: `_pm_loop_limit=20`
- Pattern dispatch: engine.py L808 ptype switch
- Phase timeout: asyncio.wait_for(run_pattern(), phase_timeout)
- Git: AC wf creates agent branches — ALWAYS commit before launching cycle
