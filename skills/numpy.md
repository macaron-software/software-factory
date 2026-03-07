---
name: numpy
version: 1.0.0
description: Numpy
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on numpy
eval_cases:
- id: numpy-approach
  prompt: How should I approach numpy for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on numpy
  tags:
  - numpy
- id: numpy-best-practices
  prompt: What are the key best practices and pitfalls for numpy?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for numpy
  tags:
  - numpy
  - best-practices
- id: numpy-antipatterns
  prompt: What are the most common mistakes to avoid with numpy?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - numpy
  - antipatterns
---
# numpy

404: Not Found
