# SF Platform — Agentic Workflow Engine

## Stats
215 agents · 25 patterns (20 catalog + 5 fractal/backprop) · 49 workflows · 28 phase templates · 53 tool mods · 1090 skills

## Tree
```
platform/
  server.py              lifespan, drain, auth middleware
  agents/store.py        AgentDef DC, 215 agents PG
  agents/executor.py     LLM tool-call loop (max 15 rds)
  agents/adversarial.py  L0 det + L1 LLM guard (score 0-100, reject<40)
  agents/tool_runner.py  dispatch 134 schemas, traceability reg
  agents/tool_schemas/   __init__ _platform(TRACEABILITY_SCHEMAS) _mapping(ROLE_TOOL_MAP)
  patterns/engine.py     run_pattern(PatternDef,sid,task) -> 25 topologies
  patterns/impls/        solo seq par loop hier net router aggr wave hitl comp bb mr
                         tournament escalation voting speculative red-blue relay mob
                         fractal_qa fractal_stories fractal_tests fractal_worktree backprop_merge
  workflows/store.py     PM v2 orchestrator, _PHASE_TEMPLATES(28), _PATTERN_CATALOG(20)
  workflows/builtins.py  YAML->WorkflowDef (pm_driven merge into config)
  workflows/defs/        49 YAML wf defs (feature-sprint primary, data-migration, etc)
  traceability/          migration_store.py — legacy_items + traceability_links CRUD
  tools/(53)             code git deploy build web security memory mcp_bridge traceability
                         ast lint lsp sandbox perf_audit deep_bench sf_bench agent_bench
                         android browser chaos compose dead_code dep diag gsd infisical
                         jira knowledge llm_bench memory_bench mflux monitoring package
                         phase plan platform project quality registry reward rtk
                         sast security_pentest skill_eval team_bench test type_check workflow_bench
  tools/traceability_tools.py  4 BaseTool: legacy_scan link coverage validate
  llm/client.py          Multi-provider: azure-ai, azure-openai, nvidia(Kimi-K2), minimax, local-mlx, ollama
  services/
    epic_orchestrator.py  phase dispatch, sprint loop, PM_GATE
    pm_checkpoint.py      quality score -> retry/advance/skip
    auto_resume.py        PG advisory lock, resume stuck
    evidence.py push.py notification_service.py
  a2a/                   bus veto negotiation protocol jarvis_mcp jarvis_acp azure_bridge
  ac/                    reward convergence experiments skill_thompson
  security/              prompt_guard output_validator audit sanitize
  missions/              SAFe lifecycle + ProductBacklog
  ops/(17)               auto_heal endurance_watchdog platform_watchdog chaos_endurance
                         backup restore health zombie_cleanup error_clustering
  mcps/                  MCP srv mgr (fetch memory playwright)
  db/                    adapter(PG+SQLite) migrations tenant
  rbac/                  roles x actions x artifacts
  web/routes/            missions pages sessions workflows agents projects
    templates/(64)       Jinja2 HTMX partials
    static/              css(3) js(4+) avatars/
cli/sf.py                sf status | sf ideation "..." | sf missions list
dashboard/               Monitor UI :8080
skills/                  1090 skill .md files
tests/                   pytest + playwright E2E
```

## PM v2 — Lego-brick Orchestrator
After each phase PM LLM picks: next|loop|done|skip|**phase** (new dynamic brick).
`phase` = compose: pattern + team + gate + feedback -> in-mem PatternDef+WorkflowPhase -> _phase_queue.
PM checkpoint: quality score -> retry if <50%, advance if OK.
PM_OVERRIDE: force retry if build failed even when agent claims success.
PM_GATE: build PASS/FAIL + sprint N/M. Loop safety: _pm_loop_limit=20.

```
store.py layout:
  L543   _PATTERN_CATALOG (20 types + desc)
  L556   _FEEDBACK_TYPES _GATE_TYPES
  L580   _PHASE_TEMPLATES (28 reusable bricks)
  L674   _format_templates_section()
  L700   _PM_DECISION_PROMPT_V2 — full prompt w/ catalogs
  L754   _build_dynamic_phase(block) -> (WPhase, PatDef)
  L809   _build_evidence() — extract src/build/test from tool_calls
  L875   PM prompt assembly w/ patterns+templates+agents
  L1054  _dynamic_patterns{} + _phase_queue[]
  L1127  pattern lookup: _dynamic_patterns[id] || pattern_store.get(id)
  L1592  PM inserts dynamic phases: _dynamic_patterns[_dyn_phase.id] = _dyn_pattern
```

## 25 Patterns
```
Catalog(20): solo sequential parallel loop hierarchical network router aggregator wave
  human-in-the-loop map_reduce blackboard composite tournament escalation
  voting speculative red-blue relay mob
Impl-only(5): fractal_qa fractal_stories fractal_tests fractal_worktree backprop_merge
```

## 28 Phase Templates
```
inception design design-debate dev-sprint parallel-dev tdd-sprint code-review
qa-acceptance multi-file-refactor design-convergence deploy rework bug-triage
creative-tournament tiered-fix quality-vote speculative-fix security-audit
progressive-build mob-debug legacy-inventory story-from-legacy traceability-check
migration-sprint migration-verify infra-provision wave-build human-review
```

## Gates & Feedback
```
Gates: all_approved no_veto always best_effort
Feedback: adversarial->config.adversarial_guard | tools->require_tool_validation
          judge->network+debate | human->hitl
```

## Traceability
```
DB: legacy_items(uuid,project,category,name,metadata_json) + traceability_links(legacy->story/test)
Tools: legacy_scan traceability_link traceability_coverage traceability_validate
Wired 3 layers: schemas(_platform.py) + registry(tool_runner.py) + roles(_mapping.py)
Role map: cdp/arch/product/dev=all4  qa=coverage+validate
Adversarial: // Ref: FEAT-xxx enforced (MISSING_TRACEABILITY check)
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
local   local-mlx     Qwen3.5-mlx         :8080 ollama-compat
ovh     minimax       MiniMax-M2.5         tool_calls native, no mangle
azure   azure-openai  gpt-5-mini(dflt)     +gpt-5.2 +gpt-5.2-codex
azure   azure-ai      gpt-5.2              swedencentral
nvidia  nvidia        Kimi-K2              integrate.api.nvidia.com
```
MiniMax: `<think>` stripped, json fences stripped, no temp, parallel_tool_calls=False
MiniMax quirk: agents slop round 2+ (text-only no tools) — adversarial catches it

## Envs
```
local   localhost:8099   PG localhost:5432   MLX :8080
ovh     $OVH_IP          blue-green /opt/software-factory/slots/{blue,green}
azure   $SF_NODE1_IP:8090  $SF_NODE2_IP   az vm run-command (no SSH)
```

## Run
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
pytest tests/ -v
cd platform/tests/e2e && npx playwright test
```

## Deploy OVH
```sh
git archive HEAD platform/ | tar -x -C /tmp/sf-deploy/
rsync -az --checksum --delete /tmp/sf-deploy/platform/ debian@$OVH_IP:/opt/software-factory/slots/blue/
docker compose up -d --no-deps --force-recreate platform-blue platform-factory
docker exec platform-blue python3 -c "WorkflowStore().seed_builtins()"
```

## Repos
GitHub macaron-software/software-factory AGPL-3.0 <- dev here
GitLab La Poste <- one-way sync via sync-to-laposte.sh (never edit)

## DB
PG psycopg `%s` params. Tables: agents sessions messages patterns workflows projects
ac_cycles epics features stories sprints pattern_runs legacy_items traceability_links epic_runs

## Rules
- YAML phase.config > pattern.config (merge L892)
- Agent resolve: explicit -> TeamSelector(Darwin) -> role -> dev_fullstack
- `pm_driven: true` in wf YAML -> PM checkpoint each phase
- `_phase_queue` mutable — PM inserts/reorders dynamically
- `_dynamic_patterns{}` caches PM-built PatternDefs (run-scoped)
- env-setup: MUST detect stack -> correct Dockerfile (not generic python:3.12-slim)
- Agent persona: MUST emphasize tool usage (CRITICAL BEHAVIOR RULES pattern)
- NodeStatus: PENDING/RUNNING/COMPLETED/VETOED/FAILED (NO `DONE`)
- Container path: /app/macaron_platform/ (NOT /app/platform/)
- `platform/` shadows stdlib — never `import platform` top-level
