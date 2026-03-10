---
name: great-tables
version: 1.0.0
description: Great Tables
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on great tables
eval_cases:
- id: great-tables-approach
  prompt: How should I approach great tables for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on great tables
  tags:
  - great
- id: great-tables-best-practices
  prompt: What are the key best practices and pitfalls for great tables?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for great tables
  tags:
  - great
  - best-practices
- id: great-tables-antipatterns
  prompt: What are the most common mistakes to avoid with great tables?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - great
  - antipatterns
---
# great-tables

404: Not Found
