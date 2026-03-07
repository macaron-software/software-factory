---
name: architecture-patterns
version: 1.0.0
description: Implement proven backend architecture patterns including Clean Architecture,
  Hexagonal Architecture, and Domain-Driven Design. Use when architecting complex
  backend systems or refactoring existing ...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - architecting complex backend systems or refactoring existing
  - designing new backend systems from scratch
eval_cases:
- id: architecture-patterns-approach
  prompt: How should I approach architecture patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on architecture patterns
  tags:
  - architecture
- id: architecture-patterns-best-practices
  prompt: What are the key best practices and pitfalls for architecture patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for architecture patterns
  tags:
  - architecture
  - best-practices
- id: architecture-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with architecture patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - architecture
  - antipatterns
---
# architecture-patterns

# Architecture Patterns

Master proven backend architecture patterns including Clean Architecture, Hexagonal Architecture, and Domain-Driven Design to build maintainable, testable, and scalable systems.

## Use this skill when

- Designing new backend systems from scratch
- Refactoring monolithic applications for better maintainability
- Establishing architecture standards for your team
- Migrating from tightly coupled to loosely coupled architectures
- Implementing domain-driven design principles
- Creating testable and mockable codebases
- Planning microservices decomposition

## Do not use this skill when

- You only need small, localized refactors
- The system is primarily frontend with no backend architecture changes
- You need implementation details without architectural design

## Instructions

1. Clarify domain boundaries, constraints, and scalability targets.
2. Select an architecture pattern that fits the domain complexity.
3. Define module boundaries, interfaces, and dependency rules.
4. Provide migration steps and validation checks.
5. For workflows that must survive failures (payments, order fulfillment, multi-step processes), use durable execution at the infrastructure layer — frameworks like DBOS persist workflow state, providing crash recovery without adding architectural complexity.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Related Skills

Works well with: `event-sourcing-architect`, `saga-orchestration`, `workflow-automation`, `dbos-*`

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.
