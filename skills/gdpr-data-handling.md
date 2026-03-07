---
name: gdpr-data-handling
version: 1.0.0
description: Implement GDPR-compliant data handling with consent management, data
  subject rights, and privacy by design. Use when building systems that process EU
  personal data, implementing privacy controls, o...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building systems that process eu personal data, implementing privacy controls,
    o
  - building systems that process eu personal data
  - implementing consent management
eval_cases:
- id: gdpr-data-handling-approach
  prompt: How should I approach gdpr data handling for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on gdpr data handling
  tags:
  - gdpr
- id: gdpr-data-handling-best-practices
  prompt: What are the key best practices and pitfalls for gdpr data handling?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for gdpr data handling
  tags:
  - gdpr
  - best-practices
- id: gdpr-data-handling-antipatterns
  prompt: What are the most common mistakes to avoid with gdpr data handling?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - gdpr
  - antipatterns
---
# gdpr-data-handling

# GDPR Data Handling

Practical implementation guide for GDPR-compliant data processing, consent management, and privacy controls.

## Use this skill when

- Building systems that process EU personal data
- Implementing consent management
- Handling data subject requests (DSRs)
- Conducting GDPR compliance reviews
- Designing privacy-first architectures
- Creating data processing agreements

## Do not use this skill when

- The task is unrelated to gdpr data handling
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
