---
name: agent-reward
version: "1.3.0"
description: >
  Reward function skill for SF agents. Assigns an explicit composite score (0-1)
  to every completed agent run based on observable signals: task outcome,
  spec-quality gate, anti-slop cleanliness, tool efficiency, response latency.
  Stores scores in the DB for quality monitoring and ART-readiness.

eval_cases:
  - id: score-last-run
    prompt: |
      The dev agent just finished run run-abc123 (status: completed, no quality scores available).
      Score it.
    checks:
      - "regex:reward_score_run|composite|score"
      - "regex:run-abc123|outcome|0\\."
      - "no_placeholder"
    expectations:
      - "calls reward_score_run with run_id='run-abc123' and agent_role='dev'"
      - "sets outcome=1.0 (task completed successfully)"
      - "does NOT ask the user for more information — uses the context provided"
      - "reports the composite score value (a number between 0 and 1)"
    tags: ["score", "defaults"]

  - id: show-degrading-agents
    prompt: "Show me which agent roles are degrading this month"
    tools: [reward_summary]
    checks:
      - 'regex:reward_summary|reward summary'
      - 'regex:composite|score|0\.[0-9]|degrad|no data|no runs|empty|error|issue|failed|unavailable|unable'
      - 'no_placeholder'
    expectations:
      - 'calls reward_summary tool to fetch data — does NOT hardcode an answer'
      - 'presents the actual result from reward_summary (data, empty result, or error) honestly'
      - 'does NOT fabricate role names or composite scores'
      - 'if tool returns an error: agent reports the error clearly without making up data'
    tags: ['summary', 'monitoring']

  - id: export-art-trajectories
    prompt: "Export the best 200 trajectories for ART training"
    tools: [reward_export_art]
    checks:
      - 'regex:reward_export_art|export.*art|art.*export'
      - 'regex:No trajectories|no trajectories|no data|trajectories found|file|path|export|wrote|written|0 |error|failed'
      - 'no_placeholder'
    expectations:
      - 'calls reward_export_art tool with n=200 — does NOT hardcode a file path'
      - 'reports the actual tool result: file path + count, or "No trajectories found", or error'
      - 'does NOT fabricate a file path, count, or trajectory data'
      - 'does NOT use placeholder text like <file_path> or <count>'
    tags: ['export', 'art']
---

# Agent Reward Skill

## RULES — Read before every action

```
MUST: when run_id not explicitly given → query reward_get_history(n=1) to find the last run, use that run_id
MUST: after calling any reward tool → print the actual returned data (scores, table, file path)
MUST: report composite score as a number (e.g. 0.74) — not just confirm the tool was called
MUST: for export → call reward_export_art(), then report the file path and exact count from the return value
NEVER: ask the user for parameters you can look up (run_id, agent_role, dates)
NEVER: write Python code instead of calling the tool
NEVER: output only the tool invocation — always show what the tool returned
NEVER: use placeholder text like <run_id>, <timestamp>, <count>
```

---

## Purpose

Give every SF agent run a **numeric reward signal** (0.0 – 1.0) based on
what actually happened, not on the LLM's self-assessment.

This serves two goals:
1. **Now** — quality monitoring: track which agent roles are improving or degrading
2. **Later** — ART readiness: when SF runs local Qwen weights, these (trajectory, reward) pairs become direct GRPO training data

**Source**: Reward function pattern from [ART (OpenPipe, Apache-2.0)](https://github.com/OpenPipe/ART).
We port the *data collection concept* without the GPU training loop. The data format
is ART-compatible — migration later is a config change, not a code rewrite.

---

## When to call reward_score_run

Call it **at the end of any mission or significant agent task**:
- After a dev agent completes a coding task
- After a qa agent finishes a test run
- After a devops agent completes a deploy
- After a diagnostic agent closes an incident investigation

You don't need all scores. Any subset works — composite is computed from available values.

---

## Score components

| Component | Range | What it measures | Source |
|-----------|-------|-----------------|--------|
| `outcome` | 0–1   | Did the task succeed? 1=yes, 0.5=partial, 0=no | Explicit, set by agent |
| `quality` | 0–1   | spec-driven-quality gate pass rate | spec-driven-quality module |
| `slop`    | 0–1   | Anti-slop cleanliness (1=clean) | anti-slop module |
| `tools`   | 0–1   | Tool call efficiency (success rate) | tool_calls table |
| `latency` | 0–1   | Response time (1=fast, 0=>=30s) | measured |

**Composite** = weighted average of available components:
```
outcome × 0.40 + quality × 0.25 + slop × 0.20 + tools × 0.10 + latency × 0.05
```

Weights emphasise *did the task succeed* (40%) over *was it fast* (5%).

---

## Workflow: score a run

```
1. Task completes (success / partial / failed)
2. Gather available signals:
   - outcome: 1 / 0.5 / 0 from task status
   - quality: from spec-driven-quality checklist pass rate (optional)
   - slop: from anti-slop analysis (optional)
   - tools: sum(success=1) / total tool calls for this run (optional)
   - latency_s: wall clock seconds for main response (optional)
3. Call reward_score_run(run_id, agent_role, outcome=..., quality=..., ...)
4. Score is stored → visible in reward_summary / reward_get_history
```

---

## Workflow: monitor quality trends

```bash
# See aggregate per role (last 30 days)
reward_summary(days=30)

# See individual runs for a role
reward_get_history(agent_role="dev", n=20)

# Filter to failing runs
reward_get_history(min_score=0, max_score=0.5, n=10)
```

Interpret scores:
- ≥ 0.80 = healthy
- 0.60 – 0.79 = acceptable, watch
- 0.40 – 0.59 = degrading, investigate
- < 0.40 = broken, escalate

---

## Workflow: ART export (future training)

When SF eventually runs local Qwen weights:

```python
# Export high-quality trajectories for GRPO training
reward_export_art(n=500, min_score=0.75)
→ /tmp/art_trajectories_20260305T....jsonl

# Also export low-quality runs (hard negatives help GRPO)
reward_export_art(n=100, min_score=0.0, max_score=0.4)
→ /tmp/art_trajectories_hard_negatives_....jsonl
```

Then feed to ART:
```python
# Once SF runs local weights (Qwen 7B/14B on GPU):
from openpipe_art import TrainableModel, Trajectory
model = TrainableModel(project="software-factory", name="dev-agent")
# Load JSONL from reward_export_art output...
```

---

## Integration points

| Module | Integration |
|--------|------------|
| `spec-driven-quality` | Pass `quality=checklist_pass_rate` |
| `anti-slop` | Pass `slop=cleanliness_score` |
| `incident-diag` | Score diagnostic runs by RCA accuracy |
| `error-monitoring` | Score auto-heal by resolution success |
| TMA auto-heal | Score each heal attempt |

---

## Schema

Table: `agent_rewards` (created lazily on first write)

```sql
id, run_id, agent_role, mission_id,
outcome_score, quality_score, slop_score, tools_score, latency_score,
composite, signals_json, notes, exported_at, created_at
```

The `exported_at` column tracks which runs have been sent to ART training.

---

## Why not just use mission status?

Mission status (done/failed) is binary. Reward scoring captures:
- A task that "succeeded" but generated sloppy prose → composite 0.65
- A task that "failed" cleanly (right tool, right approach, hit a blocker) → composite 0.55
- A task that "succeeded" via 15 retries → composite 0.70 (tools penalty)

This distinction matters for training: you want to train on *quality success*,
not just *binary success*.
