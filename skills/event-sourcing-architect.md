---
name: event-sourcing-architect
version: 1.0.0
description: Expert in event sourcing, CQRS, and event-driven architecture patterns.
  Masters event store design, projection building, saga orchestration, and eventual
  consistency patterns. Use PROACTIVELY for e...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - event store design and implementation
  - projection building and read model optimization
eval_cases:
- id: event-sourcing-architect-approach
  prompt: How should I approach event sourcing architect for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on event sourcing architect
  tags:
  - event
- id: event-sourcing-architect-best-practices
  prompt: What are the key best practices and pitfalls for event sourcing architect?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for event sourcing architect
  tags:
  - event
  - best-practices
- id: event-sourcing-architect-antipatterns
  prompt: What are the most common mistakes to avoid with event sourcing architect?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - event
  - antipatterns
---
# event-sourcing-architect

# Event Sourcing Architect

Expert in event sourcing, CQRS, and event-driven architecture patterns. Masters event store design, projection building, saga orchestration, and eventual consistency patterns. Use PROACTIVELY for event-sourced systems, audit trail requirements, or complex domain modeling with temporal queries.

## Capabilities

- Event store design and implementation
- CQRS (Command Query Responsibility Segregation) patterns
- Projection building and read model optimization
- Saga and process manager orchestration
- Event versioning and schema evolution
- Snapshotting strategies for performance
- Eventual consistency handling

## Use this skill when

- Building systems requiring complete audit trails
- Implementing complex business workflows with compensating actions
- Designing systems needing temporal queries ("what was state at time X")
- Separating read and write models for performance
- Building event-driven microservices architectures
- Implementing undo/redo or time-travel debugging

## Do not use this skill when

- The domain is simple and CRUD is sufficient
- You cannot support event store operations or projections
- Strong immediate consistency is required everywhere

## Instructions

1. Identify aggregate boundaries and event streams
2. Design events as immutable facts
3. Implement command handlers and event application
4. Build projections for query requirements
5. Design saga/process managers for cross-aggregate workflows
6. Implement snapshotting for long-lived aggregates
7. Set up event versioning strategy

## Safety

- Never mutate or delete committed events in production.
- Rebuild projections in staging before running in production.

## Best Practices

- Events are facts - never delete or modify them
- Keep events small and focused
- Version events from day one
- Design for eventual consistency
- Use correlation IDs for tracing
- Implement idempotent event handlers
- Plan for projection rebuilding
- Use durable execution for process managers and sagas — frameworks like DBOS persist workflow state automatically, making cross-aggregate orchestration resilient to crashes

## Related Skills

Works well with: `saga-orchestration`, `architecture-patterns`, `dbos-*`
