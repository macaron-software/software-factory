# SF Platform — Agent Context

## Arch
```
platform/           FastAPI :8090(prod) :8099(dev)
  server.py          uvicorn entrypoint (NEVER --reload, ALWAYS --ws none)
  web/routes/        10 sub-modules (helpers.py: _parse_body dual JSON/form)
  a2a/               Agent-to-Agent bus, negotiation, veto
  agents/store.py    AgentDef dataclass, 192 agents in PG
  patterns/engine.py run_pattern(PatternDef, session_id, task) — 13 pattern types
  patterns/store.py  PatternDef dataclass (pure, no DB needed)
  workflows/store.py run_workflow() — PM v2 orchestrator, phase loop
  llm/client.py      Multi-provider LLM client + cooldown/retry
  tools/             code, git, deploy, memory, security, browser, MCP bridge
  missions/          SAFe lifecycle + ProductBacklog
  ops/               Auto-heal, chaos, endurance
  mcps/              MCP server manager (fetch, memory, playwright)
cli/sf.py            CLI client (sf status | sf ideation "..." | sf missions list)
dashboard/           Monitoring UI :8080
```

## PM v2 Orchestrator (Lego-brick phases)
PM LLM decides after each phase: next/loop/done/skip OR compose dynamic phase.
Dynamic phase = PM picks pattern + team + gate + feedback → built in-memory as
PatternDef + WorkflowPhase → inserted into _phase_queue.

Key files:
- `platform/workflows/store.py` L538-780: _PATTERN_CATALOG, _PHASE_TEMPLATES,
  _build_agent_catalog(), _PM_DECISION_PROMPT_V2, _build_dynamic_phase(), _pm_checkpoint()
- `platform/workflows/store.py` L800+: run_workflow() _dynamic_patterns dict,
  pattern lookup checks _dynamic_patterns first, finally block handles "phase" decision
- `platform/patterns/engine.py` L675+: run_pattern() dispatch to 13 impls

## Patterns (13)
solo | sequential | parallel | loop | hierarchical | network | router |
aggregator | wave | human-in-the-loop | composite | blackboard | map_reduce

## Gates
all_approved | no_veto | always | best_effort

## Feedback types (PM v2)
adversarial → config.adversarial_guard=True
tools → config.require_tool_validation=True
judge → network pattern w/ debate
human → human-in-the-loop checkpoint

## Key Dataclasses
WorkflowPhase: id, pattern_id, name, desc, gate, config, retry_count, skip_on_failure, timeout, min_complexity
PatternDef: id, name, desc, type, agents[{id,agent_id}], edges, config, steps, ab_alt_id, ab_ratio
AgentDef: id, name, role, desc, system_prompt, provider, model, skills[], tools[], tags[]

## LLM Config (DO NOT CHANGE)
Local:  local-mlx / Qwen3.5-mlx :8080
OVH:    minimax / MiniMax-M2.5
Azure:  azure-openai / gpt-5-mini (default), gpt-5.2, gpt-5.2-codex

## Envs
Local dev → localhost:8099, PG localhost:5432
OVH demo  → $OVH_IP, blue-green deploy
Azure prod → $SF_NODE1_IP:8090, $SF_NODE2_IP

## Run
```bash
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
python3 -m pytest tests/ -v          # 52 unit tests
cd platform/tests/e2e && npx playwright test  # 82 E2E tests
```

## Repos
GitHub: macaron-software/software-factory (AGPL-3.0) ← dev here
GitLab La Poste: auto-sync via sync-to-laposte.sh (one-way, never edit)

## DB
PostgreSQL (psycopg, %s params). Tables: agents, sessions, messages, patterns,
workflows, projects, ac_cycles, epics, features, stories, sprints, pattern_runs...

## Conventions
- Workflow YAML phase.config overrides pattern.config (merge at L892-916)
- Agent resolution: explicit → TeamSelector(Darwin) → role-based → dev_fullstack fallback
- pm_driven: true in workflow YAML config → enables PM checkpoint after each phase
- _phase_queue is mutable list — PM can insert/reorder phases dynamically
- _dynamic_patterns dict caches PM-built PatternDefs for the current run
