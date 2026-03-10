---
name: protocol-reverse-engineering
version: 1.0.0
description: Master network protocol reverse engineering including packet analysis,
  protocol dissection, and custom protocol documentation. Use when analyzing network
  traffic, understanding proprietary protocol...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - analyzing network traffic, understanding proprietary protocol
  - working on protocol reverse engineering tasks or workflows
eval_cases:
- id: protocol-reverse-engineering-approach
  prompt: How should I approach protocol reverse engineering for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on protocol reverse engineering
  tags:
  - protocol
- id: protocol-reverse-engineering-best-practices
  prompt: What are the key best practices and pitfalls for protocol reverse engineering?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for protocol reverse engineering
  tags:
  - protocol
  - best-practices
- id: protocol-reverse-engineering-antipatterns
  prompt: What are the most common mistakes to avoid with protocol reverse engineering?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - protocol
  - antipatterns
---
# protocol-reverse-engineering

# Protocol Reverse Engineering

Comprehensive techniques for capturing, analyzing, and documenting network protocols for security research, interoperability, and debugging.

## Use this skill when

- Working on protocol reverse engineering tasks or workflows
- Needing guidance, best practices, or checklists for protocol reverse engineering

## Do not use this skill when

- The task is unrelated to protocol reverse engineering
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
