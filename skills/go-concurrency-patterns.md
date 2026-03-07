---
name: go-concurrency-patterns
version: 1.0.0
description: Master Go concurrency with goroutines, channels, sync primitives, and
  context. Use when building concurrent Go applications, implementing worker pools,
  or debugging race conditions.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building concurrent go applications, implementing worker pools, or debugging rac
  - building concurrent go applications
  - implementing worker pools and pipelines
eval_cases:
- id: go-concurrency-patterns-approach
  prompt: How should I approach go concurrency patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on go concurrency patterns
  tags:
  - go
- id: go-concurrency-patterns-best-practices
  prompt: What are the key best practices and pitfalls for go concurrency patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for go concurrency patterns
  tags:
  - go
  - best-practices
- id: go-concurrency-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with go concurrency patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - go
  - antipatterns
---
# go-concurrency-patterns

# Go Concurrency Patterns

Production patterns for Go concurrency including goroutines, channels, synchronization primitives, and context management.

## Use this skill when

- Building concurrent Go applications
- Implementing worker pools and pipelines
- Managing goroutine lifecycles
- Using channels for communication
- Debugging race conditions
- Implementing graceful shutdown

## Do not use this skill when

- The task is unrelated to go concurrency patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
