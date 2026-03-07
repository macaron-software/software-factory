---
name: uv-package-manager
version: 1.0.0
description: Master the uv package manager for fast Python dependency management,
  virtual environments, and modern Python project workflows. Use when setting up Python
  projects, managing dependencies, or optimi...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - setting up python projects, managing dependencies, or optimi
  - setting up new python projects quickly
  - creating and managing virtual environments
eval_cases:
- id: uv-package-manager-approach
  prompt: How should I approach uv package manager for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on uv package manager
  tags:
  - uv
- id: uv-package-manager-best-practices
  prompt: What are the key best practices and pitfalls for uv package manager?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for uv package manager
  tags:
  - uv
  - best-practices
- id: uv-package-manager-antipatterns
  prompt: What are the most common mistakes to avoid with uv package manager?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - uv
  - antipatterns
---
# uv-package-manager

# UV Package Manager

Comprehensive guide to using uv, an extremely fast Python package installer and resolver written in Rust, for modern Python project management and dependency workflows.

## Use this skill when

- Setting up new Python projects quickly
- Managing Python dependencies faster than pip
- Creating and managing virtual environments
- Installing Python interpreters
- Resolving dependency conflicts efficiently
- Migrating from pip/pip-tools/poetry
- Speeding up CI/CD pipelines
- Managing monorepo Python projects
- Working with lockfiles for reproducible builds
- Optimizing Docker builds with Python dependencies

## Do not use this skill when

- The task is unrelated to uv package manager
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
