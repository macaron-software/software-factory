---
name: it-depends
version: 1.0.0
description: It Depends
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on it depends
eval_cases:
- id: it-depends-approach
  prompt: How should I approach it depends for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on it depends
  tags:
  - it
- id: it-depends-best-practices
  prompt: What are the key best practices and pitfalls for it depends?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for it depends
  tags:
  - it
  - best-practices
- id: it-depends-antipatterns
  prompt: What are the most common mistakes to avoid with it depends?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - it
  - antipatterns
---
# it-depends

404: Not Found
