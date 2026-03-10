---
name: memory-safety-patterns
version: 1.0.0
description: Implement memory-safe programming with RAII, ownership, smart pointers,
  and resource management across Rust, C++, and C. Use when writing safe systems code,
  managing resources, or preventing memory...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing safe systems code, managing resources, or preventing memory
  - writing memory-safe systems code
eval_cases:
- id: memory-safety-patterns-approach
  prompt: How should I approach memory safety patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on memory safety patterns
  tags:
  - memory
- id: memory-safety-patterns-best-practices
  prompt: What are the key best practices and pitfalls for memory safety patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for memory safety patterns
  tags:
  - memory
  - best-practices
- id: memory-safety-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with memory safety patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - memory
  - antipatterns
---
# memory-safety-patterns

# Memory Safety Patterns

Cross-language patterns for memory-safe programming including RAII, ownership, smart pointers, and resource management.

## Use this skill when

- Writing memory-safe systems code
- Managing resources (files, sockets, memory)
- Preventing use-after-free and leaks
- Implementing RAII patterns
- Choosing between languages for safety
- Debugging memory issues

## Do not use this skill when

- The task is unrelated to memory safety patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
