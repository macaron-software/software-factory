---
name: competitive-landscape
version: 1.0.0
description: This skill should be used when the user asks to \\\"analyze competitors",
  "assess competitive landscape", "identify differentiation", "evaluate market positioning",
  "apply Porter's Five Forces",...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - working on competitive landscape analysis tasks or workflows
eval_cases:
- id: competitive-landscape-approach
  prompt: How should I approach competitive landscape for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on competitive landscape
  tags:
  - competitive
- id: competitive-landscape-best-practices
  prompt: What are the key best practices and pitfalls for competitive landscape?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for competitive landscape
  tags:
  - competitive
  - best-practices
- id: competitive-landscape-antipatterns
  prompt: What are the most common mistakes to avoid with competitive landscape?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - competitive
  - antipatterns
---
# competitive-landscape

# Competitive Landscape Analysis

Comprehensive frameworks for analyzing competition, identifying differentiation opportunities, and developing winning market positioning strategies.

## Use this skill when

- Working on competitive landscape analysis tasks or workflows
- Needing guidance, best practices, or checklists for competitive landscape analysis

## Do not use this skill when

- The task is unrelated to competitive landscape analysis
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
