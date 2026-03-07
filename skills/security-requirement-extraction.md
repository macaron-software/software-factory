---
name: security-requirement-extraction
version: 1.0.0
description: Derive security requirements from threat models and business context.
  Use when translating threats into actionable requirements, creating security user
  stories, or building security test cases.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - translating threats into actionable requirements, creating security user stories
  - writing security user stories
  - creating security test cases
eval_cases:
- id: security-requirement-extraction-approach
  prompt: How should I approach security requirement extraction for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on security requirement extraction
  tags:
  - security
- id: security-requirement-extraction-best-practices
  prompt: What are the key best practices and pitfalls for security requirement extraction?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for security requirement extraction
  tags:
  - security
  - best-practices
- id: security-requirement-extraction-antipatterns
  prompt: What are the most common mistakes to avoid with security requirement extraction?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - security
  - antipatterns
---
# security-requirement-extraction

# Security Requirement Extraction

Transform threat analysis into actionable security requirements.

## Use this skill when

- Converting threat models to requirements
- Writing security user stories
- Creating security test cases
- Building security acceptance criteria
- Compliance requirement mapping
- Security architecture documentation

## Do not use this skill when

- The task is unrelated to security requirement extraction
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
