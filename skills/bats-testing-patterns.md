---
name: bats-testing-patterns
version: 1.0.0
description: Master Bash Automated Testing System (Bats) for comprehensive shell script
  testing. Use when writing tests for shell scripts, CI/CD pipelines, or requiring
  test-driven development of shell utilities.
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing tests for shell scripts, ci/cd pipelines, or requiring test-driven devel
  - writing unit tests for shell scripts
  - implementing tdd for scripts
  - setting up automated testing in ci/cd pipelines
eval_cases:
- id: bats-testing-patterns-approach
  prompt: How should I approach bats testing patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on bats testing patterns
  tags:
  - bats
- id: bats-testing-patterns-best-practices
  prompt: What are the key best practices and pitfalls for bats testing patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for bats testing patterns
  tags:
  - bats
  - best-practices
- id: bats-testing-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with bats testing patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - bats
  - antipatterns
---
# bats-testing-patterns

# Bats Testing Patterns

Comprehensive guidance for writing comprehensive unit tests for shell scripts using Bats (Bash Automated Testing System), including test patterns, fixtures, and best practices for production-grade shell testing.

## Use this skill when

- Writing unit tests for shell scripts
- Implementing TDD for scripts
- Setting up automated testing in CI/CD pipelines
- Testing edge cases and error conditions
- Validating behavior across shell environments

## Do not use this skill when

- The project does not use shell scripts
- You need integration tests beyond shell behavior
- The goal is only linting or formatting

## Instructions

- Confirm shell dialects and supported environments.
- Set up a test structure with helpers and fixtures.
- Write tests for exit codes, output, and side effects.
- Add setup/teardown and run tests in CI.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
