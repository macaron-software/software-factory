---
name: e2e-testing-patterns
version: 1.0.0
description: Master end-to-end testing with Playwright and Cypress to build reliable
  test suites that catch bugs, improve confidence, and enable fast deployment. Use
  when implementing E2E tests, debugging flaky...
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing e2e tests, debugging flaky
  - implementing end-to-end test automation
  - debugging flaky or unreliable tests
eval_cases:
- id: e2e-testing-patterns-approach
  prompt: How should I approach e2e testing patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on e2e testing patterns
  tags:
  - e2e
- id: e2e-testing-patterns-best-practices
  prompt: What are the key best practices and pitfalls for e2e testing patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for e2e testing patterns
  tags:
  - e2e
  - best-practices
- id: e2e-testing-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with e2e testing patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - e2e
  - antipatterns
---
# e2e-testing-patterns

# E2E Testing Patterns

Build reliable, fast, and maintainable end-to-end test suites that provide confidence to ship code quickly and catch regressions before users do.

## Use this skill when

- Implementing end-to-end test automation
- Debugging flaky or unreliable tests
- Testing critical user workflows
- Setting up CI/CD test pipelines
- Testing across multiple browsers
- Validating accessibility requirements
- Testing responsive designs
- Establishing E2E testing standards

## Do not use this skill when

- You only need unit or integration tests
- The environment cannot support stable UI automation
- You cannot provision safe test accounts or data

## Instructions

1. Identify critical user journeys and success criteria.
2. Build stable selectors and test data strategies.
3. Implement tests with retries, tracing, and isolation.
4. Run in CI with parallelization and artifact capture.

## Safety

- Avoid running destructive tests against production.
- Use dedicated test data and scrub sensitive output.

## Resources

- `resources/implementation-playbook.md` for detailed E2E patterns and templates.
