---
name: risk-modeling
version: 1.0.0
description: Risk Modeling
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on risk modeling
eval_cases:
- id: risk-modeling-approach
  prompt: How should I approach risk modeling for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on risk modeling
  tags:
  - risk
- id: risk-modeling-best-practices
  prompt: What are the key best practices and pitfalls for risk modeling?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for risk modeling
  tags:
  - risk
  - best-practices
- id: risk-modeling-antipatterns
  prompt: What are the most common mistakes to avoid with risk modeling?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - risk
  - antipatterns
---
# risk-modeling

404: Not Found
