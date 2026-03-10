---
name: scipy
version: 1.0.0
description: Scipy
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on scipy
eval_cases:
- id: scipy-approach
  prompt: How should I approach scipy for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on scipy
  tags:
  - scipy
- id: scipy-best-practices
  prompt: What are the key best practices and pitfalls for scipy?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for scipy
  tags:
  - scipy
  - best-practices
- id: scipy-antipatterns
  prompt: What are the most common mistakes to avoid with scipy?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - scipy
  - antipatterns
---
# scipy

404: Not Found
