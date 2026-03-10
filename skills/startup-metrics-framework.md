---
name: startup-metrics-framework
version: 1.0.0
description: This skill should be used when the user asks about \\\"key startup metrics",
  "SaaS metrics", "CAC and LTV", "unit economics", "burn multiple", "rule of 40",
  "marketplace metrics", or requests...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - working on startup metrics framework tasks or workflows
eval_cases:
- id: startup-metrics-framework-approach
  prompt: How should I approach startup metrics framework for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on startup metrics framework
  tags:
  - startup
- id: startup-metrics-framework-best-practices
  prompt: What are the key best practices and pitfalls for startup metrics framework?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for startup metrics framework
  tags:
  - startup
  - best-practices
- id: startup-metrics-framework-antipatterns
  prompt: What are the most common mistakes to avoid with startup metrics framework?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - startup
  - antipatterns
---
# startup-metrics-framework

# Startup Metrics Framework

Comprehensive guide to tracking, calculating, and optimizing key performance metrics for different startup business models from seed through Series A.

## Use this skill when

- Working on startup metrics framework tasks or workflows
- Needing guidance, best practices, or checklists for startup metrics framework

## Do not use this skill when

- The task is unrelated to startup metrics framework
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
