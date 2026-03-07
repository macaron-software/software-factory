---
name: static-analysis
version: 1.0.0
description: Static Analysis
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on static analysis
eval_cases:
- id: static-analysis-approach
  prompt: How should I approach static analysis for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on static analysis
  tags:
  - static
- id: static-analysis-best-practices
  prompt: What are the key best practices and pitfalls for static analysis?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for static analysis
  tags:
  - static
  - best-practices
- id: static-analysis-antipatterns
  prompt: What are the most common mistakes to avoid with static analysis?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - static
  - antipatterns
---
# static-analysis

404: Not Found
