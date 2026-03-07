---
name: rust-async-patterns
version: 1.0.0
description: Master Rust async programming with Tokio, async traits, error handling,
  and concurrent patterns. Use when building async Rust applications, implementing
  concurrent systems, or debugging async code.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - 'building async rust applications, implementing concurrent systems, or debugging '
  - building async rust applications
  - implementing concurrent network services
eval_cases:
- id: rust-async-patterns-approach
  prompt: How should I approach rust async patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on rust async patterns
  tags:
  - rust
- id: rust-async-patterns-best-practices
  prompt: What are the key best practices and pitfalls for rust async patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for rust async patterns
  tags:
  - rust
  - best-practices
- id: rust-async-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with rust async patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - rust
  - antipatterns
---
# rust-async-patterns

# Rust Async Patterns

Production patterns for async Rust programming with Tokio runtime, including tasks, channels, streams, and error handling.

## Use this skill when

- Building async Rust applications
- Implementing concurrent network services
- Using Tokio for async I/O
- Handling async errors properly
- Debugging async code issues
- Optimizing async performance

## Do not use this skill when

- The task is unrelated to rust async patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
