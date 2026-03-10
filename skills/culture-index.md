---
name: culture-index
version: 1.0.0
description: Culture Index
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on culture index
eval_cases:
- id: culture-index-approach
  prompt: How should I approach culture index for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on culture index
  tags:
  - culture
- id: culture-index-best-practices
  prompt: What are the key best practices and pitfalls for culture index?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for culture index
  tags:
  - culture
  - best-practices
- id: culture-index-antipatterns
  prompt: What are the most common mistakes to avoid with culture index?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - culture
  - antipatterns
---
# culture-index

404: Not Found
