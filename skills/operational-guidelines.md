---
name: operational-guidelines
version: 1.0.0
description: Operational Guidelines
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on operational guidelines
eval_cases:
- id: operational-guidelines-approach
  prompt: How should I approach operational guidelines for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on operational guidelines
  tags:
  - operational
- id: operational-guidelines-best-practices
  prompt: What are the key best practices and pitfalls for operational guidelines?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for operational guidelines
  tags:
  - operational
  - best-practices
- id: operational-guidelines-antipatterns
  prompt: What are the most common mistakes to avoid with operational guidelines?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - operational
  - antipatterns
---
# operational-guidelines

404: Not Found
