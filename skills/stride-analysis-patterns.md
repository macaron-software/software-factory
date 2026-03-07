---
name: stride-analysis-patterns
version: 1.0.0
description: Apply STRIDE methodology to systematically identify threats. Use when
  analyzing system security, conducting threat modeling sessions, or creating security
  documentation.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - analyzing system security, conducting threat modeling sessions, or creating secu
  - reviewing security design decisions
eval_cases:
- id: stride-analysis-patterns-approach
  prompt: How should I approach stride analysis patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on stride analysis patterns
  tags:
  - stride
- id: stride-analysis-patterns-best-practices
  prompt: What are the key best practices and pitfalls for stride analysis patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for stride analysis patterns
  tags:
  - stride
  - best-practices
- id: stride-analysis-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with stride analysis patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - stride
  - antipatterns
---
# stride-analysis-patterns

# STRIDE Analysis Patterns

Systematic threat identification using the STRIDE methodology.

## Use this skill when

- Starting new threat modeling sessions
- Analyzing existing system architecture
- Reviewing security design decisions
- Creating threat documentation
- Training teams on threat identification
- Compliance and audit preparation

## Do not use this skill when

- The task is unrelated to stride analysis patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
