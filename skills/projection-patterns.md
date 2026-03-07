---
name: projection-patterns
version: 1.0.0
description: Build read models and projections from event streams. Use when implementing
  CQRS read sides, building materialized views, or optimizing query performance in
  event-sourced systems.
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing cqrs read sides, building materialized views, or optimizing query
    p
  - building cqrs read models
  - creating materialized views from events
eval_cases:
- id: projection-patterns-approach
  prompt: How should I approach projection patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on projection patterns
  tags:
  - projection
- id: projection-patterns-best-practices
  prompt: What are the key best practices and pitfalls for projection patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for projection patterns
  tags:
  - projection
  - best-practices
- id: projection-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with projection patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - projection
  - antipatterns
---
# projection-patterns

# Projection Patterns

Comprehensive guide to building projections and read models for event-sourced systems.

## Use this skill when

- Building CQRS read models
- Creating materialized views from events
- Optimizing query performance
- Implementing real-time dashboards
- Building search indexes from events
- Aggregating data across streams

## Do not use this skill when

- The task is unrelated to projection patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
