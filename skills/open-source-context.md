---
name: open-source-context
version: 1.0.0
description: Open Source Context
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on open source context
eval_cases:
- id: open-source-context-approach
  prompt: How should I approach open source context for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on open source context
  tags:
  - open
- id: open-source-context-best-practices
  prompt: What are the key best practices and pitfalls for open source context?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for open source context
  tags:
  - open
  - best-practices
- id: open-source-context-antipatterns
  prompt: What are the most common mistakes to avoid with open source context?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - open
  - antipatterns
---
# open-source-context

404: Not Found
