---
name: research-engineer
version: 1.0.0
description: Research Engineer
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on research engineer
eval_cases:
- id: research-engineer-approach
  prompt: How should I approach research engineer for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on research engineer
  tags:
  - research
- id: research-engineer-best-practices
  prompt: What are the key best practices and pitfalls for research engineer?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for research engineer
  tags:
  - research
  - best-practices
- id: research-engineer-antipatterns
  prompt: What are the most common mistakes to avoid with research engineer?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - research
  - antipatterns
---
# research-engineer

404: Not Found
