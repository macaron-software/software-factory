---
name: microservices-patterns
version: 1.0.0
description: Design microservices architectures with service boundaries, event-driven
  communication, and resilience patterns. Use when building distributed systems, decomposing
  monoliths, or implementing micros...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building distributed systems, decomposing monoliths, or implementing micros
  - designing service boundaries and contracts
  - implementing inter-service communication
eval_cases:
- id: microservices-patterns-approach
  prompt: How should I approach microservices patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on microservices patterns
  tags:
  - microservices
- id: microservices-patterns-best-practices
  prompt: What are the key best practices and pitfalls for microservices patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for microservices patterns
  tags:
  - microservices
  - best-practices
- id: microservices-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with microservices patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - microservices
  - antipatterns
---
# microservices-patterns

# Microservices Patterns

Master microservices architecture patterns including service boundaries, inter-service communication, data management, and resilience patterns for building distributed systems.

## Use this skill when

- Decomposing monoliths into microservices
- Designing service boundaries and contracts
- Implementing inter-service communication
- Managing distributed data and transactions
- Building resilient distributed systems
- Implementing service discovery and load balancing
- Designing event-driven architectures

## Do not use this skill when

- The system is small enough for a modular monolith
- You need a quick prototype without distributed complexity
- There is no operational support for distributed systems

## Instructions

1. Identify domain boundaries and ownership for each service.
2. Define contracts, data ownership, and communication patterns.
3. Plan resilience, observability, and deployment strategy.
4. Provide migration steps and operational guardrails.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
