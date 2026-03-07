---
name: literature-analysis
version: 1.0.0
description: Literature Analysis
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on literature analysis
eval_cases:
- id: literature-analysis-approach
  prompt: How should I approach literature analysis for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on literature analysis
  tags:
  - literature
- id: literature-analysis-best-practices
  prompt: What are the key best practices and pitfalls for literature analysis?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for literature analysis
  tags:
  - literature
  - best-practices
- id: literature-analysis-antipatterns
  prompt: What are the most common mistakes to avoid with literature analysis?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - literature
  - antipatterns
---
# literature-analysis

404: Not Found
