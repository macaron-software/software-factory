---
name: threat-mitigation-mapping
version: 1.0.0
description: Map identified threats to appropriate security controls and mitigations.
  Use when prioritizing security investments, creating remediation plans, or validating
  control effectiveness.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - prioritizing security investments, creating remediation plans, or validating con
  - creating remediation roadmaps
eval_cases:
- id: threat-mitigation-mapping-approach
  prompt: How should I approach threat mitigation mapping for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on threat mitigation mapping
  tags:
  - threat
- id: threat-mitigation-mapping-best-practices
  prompt: What are the key best practices and pitfalls for threat mitigation mapping?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for threat mitigation mapping
  tags:
  - threat
  - best-practices
- id: threat-mitigation-mapping-antipatterns
  prompt: What are the most common mistakes to avoid with threat mitigation mapping?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - threat
  - antipatterns
---
# threat-mitigation-mapping

# Threat Mitigation Mapping

Connect threats to controls for effective security planning.

## Use this skill when

- Prioritizing security investments
- Creating remediation roadmaps
- Validating control coverage
- Designing defense-in-depth
- Security architecture review
- Risk treatment planning

## Do not use this skill when

- The task is unrelated to threat mitigation mapping
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
