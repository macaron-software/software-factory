---
name: monorepo-management
version: 1.0.0
description: Master monorepo management with Turborepo, Nx, and pnpm workspaces to
  build efficient, scalable multi-package repositories with optimized builds and dependency
  management. Use when setting up monor...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - setting up monor
  - setting up new monorepo projects
  - optimizing build and test performance
eval_cases:
- id: monorepo-management-approach
  prompt: How should I approach monorepo management for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on monorepo management
  tags:
  - monorepo
- id: monorepo-management-best-practices
  prompt: What are the key best practices and pitfalls for monorepo management?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for monorepo management
  tags:
  - monorepo
  - best-practices
- id: monorepo-management-antipatterns
  prompt: What are the most common mistakes to avoid with monorepo management?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - monorepo
  - antipatterns
---
# monorepo-management

# Monorepo Management

Build efficient, scalable monorepos that enable code sharing, consistent tooling, and atomic changes across multiple packages and applications.

## Use this skill when

- Setting up new monorepo projects
- Migrating from multi-repo to monorepo
- Optimizing build and test performance
- Managing shared dependencies
- Implementing code sharing strategies
- Setting up CI/CD for monorepos
- Versioning and publishing packages
- Debugging monorepo-specific issues

## Do not use this skill when

- The task is unrelated to monorepo management
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
