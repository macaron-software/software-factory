---
name: error-handling-patterns
version: 1.0.0
description: Master error handling patterns across languages including exceptions,
  Result types, error propagation, and graceful degradation to build resilient applications.
  Use when implementing error handling...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing error handling
  - implementing error handling in new features
  - designing error-resilient apis
  - debugging production issues
eval_cases:
- id: error-handling-patterns-approach
  prompt: How should I approach error handling patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on error handling patterns
  tags:
  - error
- id: error-handling-patterns-best-practices
  prompt: What are the key best practices and pitfalls for error handling patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for error handling patterns
  tags:
  - error
  - best-practices
- id: error-handling-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with error handling patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - error
  - antipatterns
---
# error-handling-patterns

# Error Handling Patterns

Build resilient applications with robust error handling strategies that gracefully handle failures and provide excellent debugging experiences.

## Use this skill when

- Implementing error handling in new features
- Designing error-resilient APIs
- Debugging production issues
- Improving application reliability
- Creating better error messages for users and developers
- Implementing retry and circuit breaker patterns
- Handling async/concurrent errors
- Building fault-tolerant distributed systems

## Do not use this skill when

- The task is unrelated to error handling patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
