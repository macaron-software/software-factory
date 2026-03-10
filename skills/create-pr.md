---
name: create-pr
version: 1.0.0
description: Alias for sentry-skills:pr-writer. Use when users explicitly ask for
  "create-pr" or reference the legacy skill name. Redirects to the canonical PR writing
  workflow.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - users explicitly ask for "create-pr" or reference the legacy skill name
eval_cases:
- id: create-pr-approach
  prompt: How should I approach create pr for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on create pr
  tags:
  - create
- id: create-pr-best-practices
  prompt: What are the key best practices and pitfalls for create pr?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for create pr
  tags:
  - create
  - best-practices
- id: create-pr-antipatterns
  prompt: What are the most common mistakes to avoid with create pr?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - create
  - antipatterns
---
# create-pr

# Alias: create-pr

This skill name is kept for compatibility.

Use `sentry-skills:pr-writer` as the canonical skill for creating and editing pull requests.

If invoked via `create-pr`, run the same workflow and conventions documented in `sentry-skills:pr-writer`.
