---
name: monorepo-architect
version: 1.0.0
description: Expert in monorepo architecture, build systems, and dependency management
  at scale. Masters Nx, Turborepo, Bazel, and Lerna for efficient multi-project development.
  Use PROACTIVELY for monorepo setup,
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on monorepo architect
eval_cases:
- id: monorepo-architect-approach
  prompt: How should I approach monorepo architect for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on monorepo architect
  tags:
  - monorepo
- id: monorepo-architect-best-practices
  prompt: What are the key best practices and pitfalls for monorepo architect?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for monorepo architect
  tags:
  - monorepo
  - best-practices
- id: monorepo-architect-antipatterns
  prompt: What are the most common mistakes to avoid with monorepo architect?
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
# monorepo-architect

# Monorepo Architect

Expert in monorepo architecture, build systems, and dependency management at scale. Masters Nx, Turborepo, Bazel, and Lerna for efficient multi-project development. Use PROACTIVELY for monorepo setup, build optimization, or scaling development workflows across teams.

## Do not use this skill when

- The task is unrelated to monorepo architect
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Capabilities

- Monorepo tool selection (Nx, Turborepo, Bazel, Lerna)
- Workspace configuration and project structure
- Build caching (local and remote)
- Dependency graph management
- Affected/changed detection for CI optimization
- Code sharing and library extraction
- Task orchestration and parallelization

## Use this skill when

- Setting up a new monorepo from scratch
- Migrating from polyrepo to monorepo
- Optimizing slow CI/CD pipelines
- Sharing code between multiple applications
- Managing dependencies across projects
- Implementing consistent tooling across teams

## Workflow

1. Assess codebase size and team structure
2. Select appropriate monorepo tooling
3. Design workspace and project structure
4. Configure build caching strategy
5. Set up affected/changed detection
6. Implement task pipelines
7. Configure remote caching for CI
8. Document conventions and workflows

## Best Practices

- Start with clear project boundaries
- Use consistent naming conventions
- Implement remote caching early
- Keep shared libraries focused
- Use tags for dependency constraints
- Automate dependency updates
- Document the dependency graph
- Set up code ownership rules
