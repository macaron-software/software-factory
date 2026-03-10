---
name: track-management
version: 1.0.0
description: Use this skill when creating, managing, or working with Conductor tracks
  - the logical work units for features, bugs, and refactors. Applies to spec.md,
  plan.md, and track lifecycle operations.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - creating new feature, bug, or refactor tracks
  - writing or reviewing spec.md files
  - creating or updating plan.md files
eval_cases:
- id: track-management-approach
  prompt: How should I approach track management for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on track management
  tags:
  - track
- id: track-management-best-practices
  prompt: What are the key best practices and pitfalls for track management?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for track management
  tags:
  - track
  - best-practices
- id: track-management-antipatterns
  prompt: What are the most common mistakes to avoid with track management?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - track
  - antipatterns
---
# track-management

# Track Management

Guide for creating, managing, and completing Conductor tracks - the logical work units that organize features, bugs, and refactors through specification, planning, and implementation phases.

## Use this skill when

- Creating new feature, bug, or refactor tracks
- Writing or reviewing spec.md files
- Creating or updating plan.md files
- Managing track lifecycle from creation to completion
- Understanding track status markers and conventions
- Working with the tracks.md registry
- Interpreting or updating track metadata

## Do not use this skill when

- The task is unrelated to track management
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
