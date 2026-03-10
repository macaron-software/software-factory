---
name: error-monitoring
version: "1.0.0"
description: >
  Specializes in error monitoring, clustering, severity analysis, and intelligent alert suppression.
  Use this skill when scanning incidents, classifying errors (NEW/REGRESSION/ONGOING),
  deciding whether to trigger auto-heal, or reporting on production error trends.
metadata:
  category: ops
  triggers:
    - "when scanning platform incidents for errors"
    - "when clustering or grouping similar errors"
    - "when determining error severity (S1-S4 / P0-P3)"
    - "when deciding whether to alert on a recurring error"
    - "when reporting on error trends or regressions"
    - "when muting or unmuting noisy error signatures"
    - "when triaging production incidents"
# EVAL CASES — philschmid.de/testing-skills
# WHY: Error monitoring skill must correctly classify errors and not auto-heal
# regressions without flagging them. These cases test the core decision logic.
eval_cases:
  - id: classify-new-error
    prompt: "Classify this error: 'AttributeError: NoneType has no attribute strip' — first seen 3 minutes ago, 47 occurrences in 5 minutes, no similar error in last 7 days."
    should_trigger: true
    checks:
      - "regex:NEW|new error|novel"
      - "regex:alert|notify|page"
      - "no_placeholder"
    expectations:
      - "classifies as NEW (not seen before)"
      - "recommends alerting the on-call team"
      - "does not auto-heal without human approval for a new error type"
    tags: [basic, classification]
  - id: classify-regression
    prompt: "Error: 'KeyError: user_id' — last seen 14 days ago after a deploy. Now appearing after today's deploy at 200 req/min."
    should_trigger: true
    checks:
      - "regex:REGRESSION|regression|re-introduced|reappear"
      - "regex:deploy|rollback|revert"
      - "no_placeholder"
    expectations:
      - "classifies as REGRESSION (previously seen, reintroduced)"
      - "correlates with the recent deploy"
      - "suggests rollback or investigation of recent changes"
    tags: [regression]
  - id: ongoing-no-alert
    prompt: "Error: 'ConnectionReset by peer' — ongoing for 6 days, 3 occurrences/hour, stable rate, already acknowledged."
    should_trigger: true
    checks:
      - "regex:ONGOING|ongoing|suppress|mute|known|stable|acknowledged"
      - "not_regex:ALERT.*urgent|page.*on-call.*now|immediate.*alert|critical.*alert|trigger.*alert|new.*alert"
      - "regex:suppress|mute|silence|known|monitor|no.*action|no.*alert|no.*page"
    expectations:
      - "classifies as ONGOING (not a new regression)"
      - "recommends suppressing/muting the alert — already known"
      - "does NOT recommend immediately paging on-call for this stable known error"
    tags: [suppress, noise-reduction]
---

# Error Monitoring

This skill enables intelligent error monitoring: cluster errors by root cause,
classify severity, detect regressions, and suppress duplicate alerts.

## Use this skill when

- Scanning `platform_incidents` for unresolved errors
- Grouping similar errors into clusters (noise reduction)
- Determining if an error is NEW, a REGRESSION, or ONGOING
- Deciding whether to fire an alert or suppress it
- Reporting error trends, regressions, top error types
- Managing mutes for known/expected error patterns

## Do not use this skill when

- Writing application code (use development skills)
- Setting up infrastructure monitoring (use devops-pipeline)
- Doing security audits (use security-audit)

## Instructions

### Error Pipeline

The error monitoring pipeline has 4 stages, ported from the open-source
`airweave-ai/error-monitoring-agent` (MIT):

```
Raw Incidents → [Clustering] → [Status Detection] → [Suppression] → Alert/Heal
```

### Stage 1: Clustering

Use `ErrorClusterer` from `platform/ops/error_clustering.py`:

```python
from platform.ops.error_clustering import ErrorClusterer

clusterer = ErrorClusterer()
clusters = await clusterer.cluster(incidents)
# Each cluster: {signature, error_class, incident_ids, severity, count, sample_messages}
```

Three stages internally:
1. **Strict** — same `error_type` + `source`
2. **Regex** — same HTTP code / exception class
3. **LLM semantic** — remaining errors via platform LLMClient

### Stage 2: Status Detection

```python
from platform.ops.error_state import get_error_state_manager

state = get_error_state_manager()
status = state.determine_status(signature)
# Returns: "NEW" | "REGRESSION" | "ONGOING"
```

| Status | Meaning | Action |
|--------|---------|--------|
| `NEW` | First occurrence | Always alert → create TMA epic |
| `REGRESSION` | Was fixed, came back | Always alert → reopen |
| `ONGOING` | Known open issue | Usually suppress |

### Stage 3: Suppression Logic

```python
should_alert, reason = state.should_alert(
    signature=sig,
    status=status,          # NEW / REGRESSION / ONGOING
    severity=sev,           # S1 / S2 / S3 / S4
    has_open_ticket=False,
    suppress_window_hours=24,
)
```

Suppression rules (in priority order):
1. Muted → suppress
2. S1/S2 → **always** alert (override everything)
3. NEW → alert
4. REGRESSION → alert
5. ONGOING + open ticket → suppress
6. Alerted within 24h → suppress

### Stage 4: Actions

- **Alert worthy** → call `create_heal_epic(group)` then `launch_tma_workflow(mission_id)`
- **Mark alerted** → `state.mark_alerted(signature)`
- **Notify** → `emit_notification(...)` in `platform/services/notifications.py`

### Severity Mapping

| Platform | Error Monitor |
|----------|--------------|
| P0 | S1 (Critical) — full outage |
| P1 | S2 (High) — major feature broken |
| P2 | S3 (Medium) — degraded |
| P3 | S4 (Low) — minor |

### Mute Management

```python
# Mute for 48h (known maintenance window)
state.add_mute(signature, duration_hours=48, muted_by="operator", reason="planned maintenance")

# Remove mute
state.remove_mute(signature)

# List active mutes
mutes = state.get_active_mutes()
```

**Semantic mutes** — une règle de mute s'applique aussi aux erreurs similaires (même cause racine, wording différent) via le `SemanticMatcher` :

```python
from platform.ops.semantic_matcher import get_semantic_matcher

matcher = get_semantic_matcher()
is_muted, reason = await matcher.check_mute_match(
    signature="HTTP 429 uploading files to storage",
    sample_messages=["Too many requests"],
    active_mutes=state.get_active_mutes(),
)
# → True, "Semantically matches muted: HTTP 429 rate limiting in downloads"
```

La version async de `should_alert` intègre automatiquement ce check :

```python
# Dans le pipeline async (recommandé) :
should_alert, reason = await state.should_alert_async(
    signature=sig, status=status, severity=sev,
    sample_messages=sample_messages,
)

# Sync (mutes exactes uniquement, pas de LLM) :
should_alert, reason = state.should_alert(signature, status, severity)
```

### Querying Incidents

```sql
-- Top error types last 24h
SELECT error_type, COUNT(*) as n, MIN(severity) as worst
FROM platform_incidents
WHERE status = 'open' AND created_at > datetime('now', '-24 hours')
GROUP BY error_type ORDER BY n DESC LIMIT 20;

-- Check signature history
SELECT signature, last_status, last_severity, times_seen, last_alerted
FROM error_signatures ORDER BY last_seen DESC LIMIT 20;

-- Active mutes
SELECT signature, muted_until, reason FROM error_mutes
WHERE muted_until > datetime('now');
```

### Reporting

When asked to report on errors, provide:
1. **Summary table**: error type, count, severity, status (NEW/REGRESSION/ONGOING)
2. **Top regressions**: errors that re-appeared after being resolved
3. **Suppression rate**: how many incidents were suppressed vs alerted
4. **Muted patterns**: what's currently muted and why

Example report format:
```
## Error Monitor Report — last 2h

| Signature | Count | Severity | Status | Action |
|-----------|-------|----------|--------|--------|
| HTTP 429 rate limiting in downloads | 12 | S2 | REGRESSION | ✅ Alert sent |
| DB timeout in sync worker | 4 | S3 | ONGOING | ⏸ Suppressed (open ticket) |
| Auth token refresh failure | 1 | S4 | NEW | ✅ Alert sent |

Suppression rate: 1/3 (33%)
```
