---
name: paper-analysis
version: 1.0.0
description: Paper Analysis
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on paper analysis
eval_cases:
- id: paper-analysis-approach
  prompt: How should I approach paper analysis for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on paper analysis
  tags:
  - paper
- id: paper-analysis-best-practices
  prompt: What are the key best practices and pitfalls for paper analysis?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for paper analysis
  tags:
  - paper
  - best-practices
- id: paper-analysis-antipatterns
  prompt: What are the most common mistakes to avoid with paper analysis?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - paper
  - antipatterns
---
# paper-analysis

404: Not Found
