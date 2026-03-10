---
name: fastapi-templates
version: 1.0.0
description: Create production-ready FastAPI projects with async patterns, dependency
  injection, and comprehensive error handling. Use when building new FastAPI applications
  or setting up backend API projects.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building new fastapi applications or setting up backend api projects
  - implementing async rest apis with python
  - building high-performance web services and microservices
eval_cases:
- id: fastapi-templates-approach
  prompt: How should I approach fastapi templates for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fastapi templates
  tags:
  - fastapi
- id: fastapi-templates-best-practices
  prompt: What are the key best practices and pitfalls for fastapi templates?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fastapi templates
  tags:
  - fastapi
  - best-practices
- id: fastapi-templates-antipatterns
  prompt: What are the most common mistakes to avoid with fastapi templates?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - fastapi
  - antipatterns
---
# fastapi-templates

# FastAPI Project Templates

Production-ready FastAPI project structures with async patterns, dependency injection, middleware, and best practices for building high-performance APIs.

## Use this skill when

- Starting new FastAPI projects from scratch
- Implementing async REST APIs with Python
- Building high-performance web services and microservices
- Creating async applications with PostgreSQL, MongoDB
- Setting up API projects with proper structure and testing

## Do not use this skill when

- The task is unrelated to fastapi project templates
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
