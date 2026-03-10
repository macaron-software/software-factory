---
name: incident-diagnosis
version: "1.0.0"
description: >
  Structured root cause analysis (RCA) skill for SF diagnostic agents.
  Covers the full investigation workflow: collect symptoms → correlate →
  hypothesise → confirm → recommend fix. Activate when: something is broken
  or slow, auto-heal hasn't triggered, or the TMA needs a root cause before acting.

eval_cases:
  - input: "The dashboard is taking 8 seconds to load"
    checks:
      - "regex:latency|slow|query|hypothesis|root.?cause|index"
      - "length_min:80"
      - "no_placeholder"
    expect:
      - Runs diag_endpoint_latency on dashboard URL
      - Runs diag_logs to find slow query or error
      - Runs diag_db_stats to check for missing indexes or fragmentation
      - Runs diag_correlate with all findings
      - Produces ranked hypotheses with confidence levels
  - input: "Agents are stuck, missions not progressing"
    checks:
      - "regex:queue|mission|stuck|stall|memory|error"
      - "length_min:80"
      - "no_placeholder"
    expect:
      - Runs diag_queue_depth first
      - Checks for stalled missions (>30min no update)
      - Runs diag_process_stats to check memory/CPU
      - Runs diag_logs on platform container filtering for errors
      - Identifies if it's a queue, memory, or error loop issue
  - input: "Memory is growing over time, suspecting a leak"
    checks:
      - "regex:leak|memory|RSS|tracemalloc|OOM|GC"
      - "length_min:80"
      - "no_placeholder"
    expect:
      - Runs diag_process_stats with include_children=true
      - Notes RSS trend over multiple calls
      - Runs diag_logs filtering for OOM or GC pressure
      - Runs diag_queue_depth to check if backlog is growing
      - Recommends tracemalloc profiling if leak confirmed
---

# Incident Diagnosis Skill

Structured root cause analysis for production incidents. Use this skill
when something is broken or slow and you need to find *why* before fixing.

**This skill is NOT:**
- Error clustering (use `error-monitoring` skill)
- Auto-healing (use `ops/auto_heal.py`)
- Browser perf audits (use `perf-audit` skill)

**This skill IS:** the investigation phase that precedes all of the above.

---

## Investigation workflow

```
1. COLLECT    → Run diag tools to gather raw evidence
2. CORRELATE  → Feed all evidence into diag_correlate
3. HYPOTHESISE → Ranked root cause hypotheses with confidence
4. CONFIRM    → Quick test of top hypothesis (one targeted check)
5. RECOMMEND  → Fix + monitoring gap
```

Always go in this order. Don't skip to step 5 without evidence.

---

## Step 1 — Collect symptoms

Run all relevant diag tools for the incident type:

### Incident: "page/endpoint is slow"
```
diag_endpoint_latency(url, n=20)        → P50/P95/P99 baseline
diag_logs(source, lines=200, level="error")  → any errors during slow period
diag_db_stats()                          → missing indexes, fragmentation
diag_process_stats()                     → CPU/memory pressure
```

### Incident: "agents stuck / missions not progressing"
```
diag_queue_depth()                       → backlog, stalled missions count
diag_process_stats()                     → memory/thread saturation
diag_logs(source="platform", lines=200, level="error")  → error loop
diag_db_stats()                          → lock waits, table bloat
```

### Incident: "memory growing / suspected leak"
```
diag_process_stats(include_children=true)  → RSS/VMS trend
diag_logs(source, filter="oom|memory|killed")
diag_queue_depth()                         → growing backlog = growing queue
```

### Incident: "service crashed / container restarted"
```
diag_logs(source, lines=500, level="error")   → last error before crash
diag_process_stats()                           → current state
diag_logs(source, filter="exit|signal|killed")
```

### Incident: "errors spiking in production"
```
diag_logs(source, lines=500, level="error")
diag_endpoint_latency(url)               → are errors causing latency too?
diag_db_stats()                          → DB connectivity issues
```

---

## Step 2 — Correlate with diag_correlate

After collecting evidence, call `diag_correlate` with ALL findings:

```
diag_correlate(
  symptoms="<paste ALL diag tool outputs here>",
  context="deploy was done 30min ago, PR #47 merged (new DB query in /api/dashboard)"
)
```

The context field is critical: include what changed recently.

---

## Step 3 — Root cause hypotheses

Structure hypotheses by confidence:

```markdown
### Hypothesis 1 — Missing DB index on missions.status (HIGH confidence)
Evidence:
  - P95 latency jumped from 120ms to 3.8s after PR #47
  - diag_db_stats: missions table has 82,000 rows, no index on status column
  - diag_logs: "full table scan" in SQLite explain output
Fix:
  CREATE INDEX idx_missions_status ON missions(status);
  → Estimated improvement: P95 back to ~150ms
Verify: diag_endpoint_latency(url, n=10) after index creation

### Hypothesis 2 — N+1 query in new dashboard endpoint (MEDIUM confidence)
Evidence:
  - PR #47 adds /api/dashboard/stats with nested loop
  - diag_logs: 47 identical SELECT statements in 200ms window
Fix:
  Refactor loop to single JOIN query
Verify: diag_logs(filter="SELECT", lines=50) after fix
```

---

## Step 4 — Confirm top hypothesis

Do ONE targeted check to confirm before acting:

| Hypothesis type | Confirmation check |
|----------------|-------------------|
| DB index missing | `EXPLAIN QUERY PLAN SELECT ...` via diag_db_stats |
| Memory leak | Run diag_process_stats twice, 60s apart — compare RSS |
| Error loop | diag_logs with filter on specific error pattern |
| CPU saturation | diag_process_stats with 2s CPU interval |
| Queue backup | diag_queue_depth twice, 30s apart — compare stalled count |

---

## Step 5 — Recommend fix + monitoring gap

Every RCA output must include:

```markdown
## Recommended Fix
[specific code change / command / config]

## Monitoring gap
"This issue would have been caught earlier if we had:
- Alert on P95 > 500ms (currently no latency alert)
- Alert on table size > 50,000 rows without index
- Add DB query duration logging to all endpoints"

## Escalation
[if fix requires > 1h or touches production data: create TMA epic via monitoring_create_heal_epic]
```

---

## Common root causes in SF

| Symptom | Most common cause | First check |
|---------|------------------|-------------|
| Slow endpoint | Missing DB index | diag_db_stats |
| Agents stuck | Memory saturation or error loop | diag_queue_depth + diag_process_stats |
| Memory growing | Unbounded cache or queue | diag_queue_depth |
| Container restart | OOM or uncaught exception | diag_logs (last 500 lines before crash) |
| Error spike | Deploy regression | diag_logs + git log --oneline -5 |
| Slow DB | Table fragmentation | diag_db_stats (freelist %) |

---

## Diagnostic tool quick reference

| Tool | Data | Use when |
|------|------|----------|
| `diag_logs` | Container/service logs | First step always |
| `diag_process_stats` | CPU/memory/threads | Suspecting resource saturation |
| `diag_db_stats` | Table sizes, slow queries, indexes | Suspecting DB bottleneck |
| `diag_endpoint_latency` | P50/P95/P99 response times | Endpoint feels slow |
| `diag_queue_depth` | Mission backlog, stalled agents | Platform feels stuck |
| `diag_correlate` | Structured RCA | After collecting all evidence |

---

## Integration with TMA auto-heal

When RCA is complete:
1. If fix is safe (no data migration, < 30min): apply directly
2. If fix is risky or complex: `monitoring_create_heal_epic(cluster_signature, fix_plan)`
3. Always: `monitoring_mark_alerted(signature)` to prevent duplicate alerts
4. Document root cause in mission memory: `memory_store(key="rca", value=...)`
