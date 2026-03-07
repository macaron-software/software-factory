---
name: yara-authoring
version: 1.0.0
description: Yara Authoring
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on yara authoring
eval_cases:
- id: yara-authoring-approach
  prompt: How should I approach yara authoring for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on yara authoring
  tags:
  - yara
- id: yara-authoring-best-practices
  prompt: What are the key best practices and pitfalls for yara authoring?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for yara authoring
  tags:
  - yara
  - best-practices
- id: yara-authoring-antipatterns
  prompt: What are the most common mistakes to avoid with yara authoring?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - yara
  - antipatterns
---
# yara-authoring

404: Not Found
