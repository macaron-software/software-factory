---
name: conductor-validator
version: 1.0.0
description: 'Validates Conductor project artifacts for completeness,

  consistency, and correctness. Use after setup, when diagnosing issues, or

  before implementation to verify project context.

  '
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - working on check if conductor directory exists tasks or workflows
eval_cases:
- id: conductor-validator-approach
  prompt: How should I approach conductor validator for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on conductor validator
  tags:
  - conductor
- id: conductor-validator-best-practices
  prompt: What are the key best practices and pitfalls for conductor validator?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for conductor validator
  tags:
  - conductor
  - best-practices
- id: conductor-validator-antipatterns
  prompt: What are the most common mistakes to avoid with conductor validator?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - conductor
  - antipatterns
---
# conductor-validator

# Check if conductor directory exists
ls -la conductor/

# Find all track directories
ls -la conductor/tracks/

# Check for required files
ls conductor/index.md conductor/product.md conductor/tech-stack.md conductor/workflow.md conductor/tracks.md
```

## Use this skill when

- Working on check if conductor directory exists tasks or workflows
- Needing guidance, best practices, or checklists for check if conductor directory exists

## Do not use this skill when

- The task is unrelated to check if conductor directory exists
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Pattern Matching

**Status markers in tracks.md:**

```
- [ ] Track Name  # Not started
- [~] Track Name  # In progress
- [x] Track Name  # Complete
```

**Task markers in plan.md:**

```
- [ ] Task description  # Pending
- [~] Task description  # In progress
- [x] Task description  # Complete
```

**Track ID pattern:**

```
<type>_<name>_<YYYYMMDD>
Example: feature_user_auth_20250115
```
