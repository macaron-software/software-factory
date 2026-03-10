---
name: modern-javascript-patterns
version: 1.0.0
description: Master ES6+ features including async/await, destructuring, spread operators,
  arrow functions, promises, modules, iterators, generators, and functional programming
  patterns for writing clean, effici...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing functional programming patterns
eval_cases:
- id: modern-javascript-patterns-approach
  prompt: How should I approach modern javascript patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on modern javascript patterns
  tags:
  - modern
- id: modern-javascript-patterns-best-practices
  prompt: What are the key best practices and pitfalls for modern javascript patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for modern javascript patterns
  tags:
  - modern
  - best-practices
- id: modern-javascript-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with modern javascript patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - modern
  - antipatterns
---
# modern-javascript-patterns

# Modern JavaScript Patterns

Comprehensive guide for mastering modern JavaScript (ES6+) features, functional programming patterns, and best practices for writing clean, maintainable, and performant code.

## Use this skill when

- Refactoring legacy JavaScript to modern syntax
- Implementing functional programming patterns
- Optimizing JavaScript performance
- Writing maintainable and readable code
- Working with asynchronous operations
- Building modern web applications
- Migrating from callbacks to Promises/async-await
- Implementing data transformation pipelines

## Do not use this skill when

- The task is unrelated to modern javascript patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
