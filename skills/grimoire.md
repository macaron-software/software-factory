---
name: grimoire
version: 1.0.0
description: Grimoire
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on grimoire
eval_cases:
- id: grimoire-approach
  prompt: How should I approach grimoire for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on grimoire
  tags:
  - grimoire
- id: grimoire-best-practices
  prompt: What are the key best practices and pitfalls for grimoire?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for grimoire
  tags:
  - grimoire
  - best-practices
- id: grimoire-antipatterns
  prompt: What are the most common mistakes to avoid with grimoire?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - grimoire
  - antipatterns
---
# grimoire

404: Not Found
