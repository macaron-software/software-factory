---
name: osint-evals
version: 1.0.0
description: Osint Evals
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on osint evals
eval_cases:
- id: osint-evals-approach
  prompt: How should I approach osint evals for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on osint evals
  tags:
  - osint
- id: osint-evals-best-practices
  prompt: What are the key best practices and pitfalls for osint evals?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for osint evals
  tags:
  - osint
  - best-practices
- id: osint-evals-antipatterns
  prompt: What are the most common mistakes to avoid with osint evals?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - osint
  - antipatterns
---
# osint-evals

404: Not Found
