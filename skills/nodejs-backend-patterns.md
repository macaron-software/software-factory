---
name: nodejs-backend-patterns
version: 1.0.0
description: Build production-ready Node.js backend services with Express/Fastify,
  implementing middleware patterns, error handling, authentication, database integration,
  and API design best practices. Use when...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building rest apis or graphql servers
  - creating microservices with node.js
  - implementing authentication and authorization
eval_cases:
- id: nodejs-backend-patterns-approach
  prompt: How should I approach nodejs backend patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on nodejs backend patterns
  tags:
  - nodejs
- id: nodejs-backend-patterns-best-practices
  prompt: What are the key best practices and pitfalls for nodejs backend patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for nodejs backend patterns
  tags:
  - nodejs
  - best-practices
- id: nodejs-backend-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with nodejs backend patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - nodejs
  - antipatterns
---
# nodejs-backend-patterns

# Node.js Backend Patterns

Comprehensive guidance for building scalable, maintainable, and production-ready Node.js backend applications with modern frameworks, architectural patterns, and best practices.

## Use this skill when

- Building REST APIs or GraphQL servers
- Creating microservices with Node.js
- Implementing authentication and authorization
- Designing scalable backend architectures
- Setting up middleware and error handling
- Integrating databases (SQL and NoSQL)
- Building real-time applications with WebSockets
- Implementing background job processing

## Do not use this skill when

- The task is unrelated to node.js backend patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
