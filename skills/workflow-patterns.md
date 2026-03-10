---
name: workflow-patterns
version: 1.0.0
description: Use this skill when implementing tasks according to Conductor's TDD workflow,
  handling phase checkpoints, managing git commits for tasks, or understanding the
  verification protocol.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing tasks from a track's plan.md
eval_cases:
- id: workflow-patterns-approach
  prompt: How should I approach workflow patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on workflow patterns
  tags:
  - workflow
- id: workflow-patterns-best-practices
  prompt: What are the key best practices and pitfalls for workflow patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for workflow patterns
  tags:
  - workflow
  - best-practices
- id: workflow-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with workflow patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - workflow
  - antipatterns
---
# workflow-patterns

# Workflow Patterns

Guide for implementing tasks using Conductor's TDD workflow, managing phase checkpoints, handling git commits, and executing the verification protocol that ensures quality throughout implementation.

## Use this skill when

- Implementing tasks from a track's plan.md
- Following TDD red-green-refactor cycle
- Completing phase checkpoints
- Managing git commits and notes
- Understanding quality assurance gates
- Handling verification protocols
- Recording progress in plan files

## Do not use this skill when

- The task is unrelated to workflow patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
