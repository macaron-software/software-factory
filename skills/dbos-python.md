---
name: dbos-python
version: 1.0.0
description: DBOS Python SDK for building reliable, fault-tolerant applications with
  durable workflows. Use this skill when writing Python code with DBOS, creating workflows
  and steps, using queues, using DBOSC...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://docs.dbos.dev/'
  triggers:
  - creating workflows and steps
eval_cases:
- id: dbos-python-approach
  prompt: How should I approach dbos python for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on dbos python
  tags:
  - dbos
- id: dbos-python-best-practices
  prompt: What are the key best practices and pitfalls for dbos python?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for dbos python
  tags:
  - dbos
  - best-practices
- id: dbos-python-antipatterns
  prompt: What are the most common mistakes to avoid with dbos python?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - dbos
  - antipatterns
---
# dbos-python

# DBOS Python Best Practices

Guide for building reliable, fault-tolerant Python applications with DBOS durable workflows.

## When to Use

Reference these guidelines when:
- Adding DBOS to existing Python code
- Creating workflows and steps
- Using queues for concurrency control
- Implementing workflow communication (events, messages, streams)
- Configuring and launching DBOS applications
- Using DBOSClient from external applications
- Testing DBOS applications

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Lifecycle | CRITICAL | `lifecycle-` |
| 2 | Workflow | CRITICAL | `workflow-` |
| 3 | Step | HIGH | `step-` |
| 4 | Queue | HIGH | `queue-` |
| 5 | Communication | MEDIUM | `comm-` |
| 6 | Pattern | MEDIUM | `pattern-` |
| 7 | Testing | LOW-MEDIUM | `test-` |
| 8 | Client | MEDIUM | `client-` |
| 9 | Advanced | LOW | `advanced-` |

## Critical Rules

### DBOS Configuration and Launch

A DBOS application MUST configure and launch DBOS inside its main function:

```python
import os
from dbos import DBOS, DBOSConfig

@DBOS.workflow()
def my_workflow():
    pass

if __name__ == "__main__":
    config: DBOSConfig = {
        "name": "my-app",
        "system_database_url": os.environ.get("DBOS_SYSTEM_DATABASE_URL"),
    }
    DBOS(config=config)
    DBOS.launch()
```

### Workflow and Step Structure

Workflows are comprised of steps. Any function performing complex operations or accessing external services must be a step:

```python
@DBOS.step()
def call_external_api():
    return requests.get("https://api.example.com").json()

@DBOS.workflow()
def my_workflow():
    result = call_external_api()
    return result
```

### Key Constraints

- Do NOT call `DBOS.start_workflow` or `DBOS.recv` from a step
- Do NOT use threads to start workflows - use `DBOS.start_workflow` or queues
- Workflows MUST be deterministic - non-deterministic operations go in steps
- Do NOT create/update global variables from workflows or steps

## How to Use

Read individual rule files for detailed explanations and examples:

```
references/lifecycle-config.md
references/workflow-determinism.md
references/queue-concurrency.md
```

## References

- https://docs.dbos.dev/
- https://github.com/dbos-inc/dbos-transact-py
