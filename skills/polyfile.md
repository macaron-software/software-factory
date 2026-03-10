---
name: polyfile
version: 1.0.0
description: Polyfile
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on polyfile
eval_cases:
- id: polyfile-approach
  prompt: How should I approach polyfile for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on polyfile
  tags:
  - polyfile
- id: polyfile-best-practices
  prompt: What are the key best practices and pitfalls for polyfile?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for polyfile
  tags:
  - polyfile
  - best-practices
- id: polyfile-antipatterns
  prompt: What are the most common mistakes to avoid with polyfile?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - polyfile
  - antipatterns
---
# polyfile

404: Not Found
