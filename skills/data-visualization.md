---
name: data-visualization
version: 1.0.0
description: Data Visualization
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on data visualization
eval_cases:
- id: data-visualization-approach
  prompt: How should I approach data visualization for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on data visualization
  tags:
  - data
- id: data-visualization-best-practices
  prompt: What are the key best practices and pitfalls for data visualization?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for data visualization
  tags:
  - data
  - best-practices
- id: data-visualization-antipatterns
  prompt: What are the most common mistakes to avoid with data visualization?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - data
  - antipatterns
---
# data-visualization

404: Not Found
