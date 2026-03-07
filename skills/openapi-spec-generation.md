---
name: openapi-spec-generation
version: 1.0.0
description: Generate and maintain OpenAPI 3.1 specifications from code, design-first
  specs, and validation patterns. Use when creating API documentation, generating
  SDKs, or ensuring API contract compliance.
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - creating api documentation, generating sdks, or ensuring api contract compliance
  - creating api documentation from scratch
  - designing api contracts (design-first approach)
eval_cases:
- id: openapi-spec-generation-approach
  prompt: How should I approach openapi spec generation for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on openapi spec generation
  tags:
  - openapi
- id: openapi-spec-generation-best-practices
  prompt: What are the key best practices and pitfalls for openapi spec generation?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for openapi spec generation
  tags:
  - openapi
  - best-practices
- id: openapi-spec-generation-antipatterns
  prompt: What are the most common mistakes to avoid with openapi spec generation?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - openapi
  - antipatterns
---
# openapi-spec-generation

# OpenAPI Spec Generation

Comprehensive patterns for creating, maintaining, and validating OpenAPI 3.1 specifications for RESTful APIs.

## Use this skill when

- Creating API documentation from scratch
- Generating OpenAPI specs from existing code
- Designing API contracts (design-first approach)
- Validating API implementations against specs
- Generating client SDKs from specs
- Setting up API documentation portals

## Do not use this skill when

- The task is unrelated to openapi spec generation
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
