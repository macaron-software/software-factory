---
name: auth-implementation-patterns
version: 1.0.0
description: Master authentication and authorization patterns including JWT, OAuth2,
  session management, and RBAC to build secure, scalable access control systems. Use
  when implementing auth systems, securing A...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing auth systems, securing a
  - implementing user authentication systems
eval_cases:
- id: auth-implementation-patterns-approach
  prompt: How should I approach auth implementation patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on auth implementation patterns
  tags:
  - auth
- id: auth-implementation-patterns-best-practices
  prompt: What are the key best practices and pitfalls for auth implementation patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for auth implementation patterns
  tags:
  - auth
  - best-practices
- id: auth-implementation-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with auth implementation patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - auth
  - antipatterns
---
# auth-implementation-patterns

# Authentication & Authorization Implementation Patterns

Build secure, scalable authentication and authorization systems using industry-standard patterns and modern best practices.

## Use this skill when

- Implementing user authentication systems
- Securing REST or GraphQL APIs
- Adding OAuth2/social login or SSO
- Designing session management or RBAC
- Debugging authentication or authorization issues

## Do not use this skill when

- You only need UI copy or login page styling
- The task is infrastructure-only without identity concerns
- You cannot change auth policies or credential storage

## Instructions

- Define users, tenants, flows, and threat model constraints.
- Choose auth strategy (session, JWT, OIDC) and token lifecycle.
- Design authorization model and policy enforcement points.
- Plan secrets storage, rotation, logging, and audit requirements.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Safety

- Never log secrets, tokens, or credentials.
- Enforce least privilege and secure storage for keys.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
