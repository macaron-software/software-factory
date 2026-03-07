---
name: python-testing-patterns
version: 1.0.0
description: Implement comprehensive testing strategies with pytest, fixtures, mocking,
  and test-driven development. Use when writing Python tests, setting up test suites,
  or implementing testing best practices.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing python tests, setting up test suites, or implementing testing best pract
  - writing unit tests for python code
  - setting up test suites and test infrastructure
  - implementing test-driven development (tdd)
eval_cases:
- id: python-testing-patterns-approach
  prompt: How should I approach python testing patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on python testing patterns
  tags:
  - python
- id: python-testing-patterns-best-practices
  prompt: What are the key best practices and pitfalls for python testing patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for python testing patterns
  tags:
  - python
  - best-practices
- id: python-testing-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with python testing patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - python
  - antipatterns
---
# python-testing-patterns

# Python Testing Patterns

Comprehensive guide to implementing robust testing strategies in Python using pytest, fixtures, mocking, parameterization, and test-driven development practices.

## Use this skill when

- Writing unit tests for Python code
- Setting up test suites and test infrastructure
- Implementing test-driven development (TDD)
- Creating integration tests for APIs and services
- Mocking external dependencies and services
- Testing async code and concurrent operations
- Setting up continuous testing in CI/CD
- Implementing property-based testing
- Testing database operations
- Debugging failing tests

## Do not use this skill when

- The task is unrelated to python testing patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
