---
name: pandas
version: 1.0.0
description: Pandas
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on pandas
eval_cases:
- id: pandas-approach
  prompt: How should I approach pandas for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on pandas
  tags:
  - pandas
- id: pandas-best-practices
  prompt: What are the key best practices and pitfalls for pandas?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for pandas
  tags:
  - pandas
  - best-practices
- id: pandas-antipatterns
  prompt: What are the most common mistakes to avoid with pandas?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - pandas
  - antipatterns
---
# pandas

404: Not Found

## When to Use

Use this skill when tackling tasks related to its primary domain or functionality as described above.
