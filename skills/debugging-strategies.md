---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/debugging-strategies
# WHY: SF TDD agents need systematic bug investigation, not guesswork.
#      Provides structured playbook: reproduce → hypothesis → binary search → fix → verify.
name: debugging-strategies
version: "1.0.0"
description: >
  Systematic debugging techniques and root cause analysis for any codebase or
  tech stack. Use when investigating bugs, performance issues, production
  incidents, crash dumps, or unexpected behavior.
metadata:
  category: development
  triggers:
    - "when investigating a bug or unexpected behavior"
    - "when a test fails for unknown reasons"
    - "when analyzing a production incident"
    - "when debugging performance issues"
    - "when stack traces or logs need analysis"
    - "when user says 'it's not working'"
# EVAL CASES
eval_cases:
  - id: systematic-bug-investigation
    prompt: |
      A FastAPI endpoint POST /orders returns 500 intermittently — about 20% of
      requests fail. The logs show: "sqlalchemy.exc.InterfaceError: connection
      already closed". Started after last deploy which added a background task.
    should_trigger: true
    checks:
      - "regex:reproduc|isolat|hypothes|connection.*pool|background.*task|race.*condition|async|thread"
      - "regex:step|first|check|verify|narrow|log|trace"
      - "length_min:100"
      - "no_placeholder"
    expectations:
      - "proposes a systematic investigation: reproduce reliably → narrow scope"
      - "identifies connection pool exhaustion or async/threading issue as likely root cause"
      - "suggests hypothesis: background task not releasing DB connection"
      - "suggests instrumentation: log connection pool stats, add try/finally around DB calls"
    tags: [root-cause, backend, async]

  - id: performance-regression
    prompt: |
      Our API response time went from 50ms to 800ms after we added a new
      analytics tracking call in the request handler. The analytics endpoint
      is an external HTTP call.
    should_trigger: true
    checks:
      - "regex:async|await|non.*blocking|background|queue|fire.*forget|timeout|sync.*call"
      - "regex:profil|measur|trace|bottleneck|latency"
      - "length_min:80"
    expectations:
      - "identifies the synchronous external HTTP call as the bottleneck"
      - "recommends making analytics call async/fire-and-forget or background task"
      - "suggests adding a timeout to the external call"
    tags: [performance, async, external-call]

  - id: test-failure-analysis
    prompt: |
      pytest test_user_auth.py::test_login_rate_limit FAILED
      AssertionError: assert 200 == 429
      Test expects a 429 after 5 failed logins within 60 seconds.
      The test passes locally but fails in CI.
    should_trigger: true
    checks:
      - "regex:ci|environment|clock|time|sleep|race|isolat|state|shared|redis|cache|persist"
      - "regex:differ.*local|environ.*differ|debug.*step"
      - "length_min:80"
    expectations:
      - "identifies CI/local environment difference as root cause"
      - "suspects shared state in rate limiter (Redis/cache not isolated between tests)"
      - "suggests using test fixtures or mocking time/Redis in CI"
    tags: [ci-flaky, test-isolation, rate-limiting]
---

# Debugging Strategies

Transform debugging from frustrating guesswork into **systematic problem-solving**.

## Use this skill when

- Tracking down elusive bugs
- Investigating performance issues
- Debugging production incidents
- Analyzing crash dumps or stack traces
- Debugging distributed systems

## The Debugging Loop

### 1. Reproduce & Capture

- Make the bug **reproducible** — no hypothesis without reproduction
- Capture: logs, stack traces, environment details, timing
- Note: "works on X, fails on Y" — difference IS the clue

### 2. Form Hypotheses

- List possible root causes (aim for 3+)
- Rank by probability and verifiability
- Start with simplest explanation (Occam's Razor)

### 3. Binary Search / Narrow Scope

- Narrow scope: comment code, disable features, simplify inputs
- Use git bisect for regressions: `git bisect start HEAD <last-good-commit>`
- Add targeted instrumentation at boundaries

### 4. Controlled Experiments

- Change ONE variable at a time
- Document each experiment and result
- Don't "fix and hope" — understand before patching

### 5. Verify the Fix

- Fix should explain ALL observed symptoms
- Add a regression test that would have caught this
- Verify in the environment where it failed

---

## High-Signal Patterns

### Connection/Resource Leaks
```python
# Always use context managers
async with db.acquire() as conn:  # released even on exception
    result = await conn.execute(query)
```

### Race Conditions (Async)
- Look for: shared mutable state, missing await, fire-and-forget without error handling
- Instrument: log thread/task IDs, add locks, use atomic operations

### Environment Differences (CI vs Local)
- Check: env vars, external services, clock/time, file permissions, shared state
- Use: test isolation (fresh DB per test), mock external calls, deterministic time

### Performance Regressions
- Always measure before optimizing: `time.perf_counter()`, profiler, APM traces
- N+1 query pattern: look for DB calls inside loops
- Synchronous calls in async paths: external HTTP, disk I/O

---

## Toolbox

| Symptom | Tool |
|---------|------|
| Slow code | `cProfile`, `py-spy`, `perf` |
| Memory leak | `tracemalloc`, `objgraph` |
| DB queries | `EXPLAIN ANALYZE`, query logs |
| API latency | distributed traces (Jaeger/OTEL) |
| Flaky tests | `pytest --count=10 -x`, isolate fixtures |

---

## Common Root Causes by Error Type

| Error | Likely Root Cause |
|-------|-------------------|
| `ConnectionReset`, `InterfaceError: closed` | Connection pool exhausted / leaked |
| `AssertionError` in CI not local | Shared state, env difference, timing |
| `500` intermittently | Race condition, resource exhaustion, unhandled exception path |
| Slow after deploy | Synchronous external call added, N+1 query, missing index |
