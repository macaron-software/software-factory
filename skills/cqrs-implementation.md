---
name: cqrs-implementation
version: 1.0.0
description: Implement Command Query Responsibility Segregation for scalable architectures.
  Use when separating read and write models, optimizing query performance, or building
  event-sourced systems.
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - separating read and write models, optimizing query performance, or building even
  - building event-sourced systems
eval_cases:
- id: cqrs-implementation-approach
  prompt: How should I approach cqrs implementation for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on cqrs implementation
  tags:
  - cqrs
- id: cqrs-implementation-best-practices
  prompt: What are the key best practices and pitfalls for cqrs implementation?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for cqrs implementation
  tags:
  - cqrs
  - best-practices
- id: cqrs-implementation-antipatterns
  prompt: What are the most common mistakes to avoid with cqrs implementation?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - cqrs
  - antipatterns
---
# cqrs-implementation

# CQRS Implementation

Comprehensive guide to implementing CQRS (Command Query Responsibility Segregation) patterns.

## Use this skill when

- Separating read and write concerns
- Scaling reads independently from writes
- Building event-sourced systems
- Optimizing complex query scenarios
- Different read/write data models are needed
- High-performance reporting is required

## Do not use this skill when

- The domain is simple and CRUD is sufficient
- You cannot operate separate read/write models
- Strong immediate consistency is required everywhere

## Instructions

- Identify read/write workloads and consistency needs.
- Define command and query models with clear boundaries.
- Implement read model projections and synchronization.
- Validate performance, recovery, and failure modes.
- If detailed patterns are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed CQRS patterns and templates.
