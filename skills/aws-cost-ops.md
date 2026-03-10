---
name: aws-cost-ops
version: 1.0.0
description: Aws Cost Ops
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on aws cost ops
eval_cases:
- id: aws-cost-ops-approach
  prompt: How should I approach aws cost ops for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on aws cost ops
  tags:
  - aws
- id: aws-cost-ops-best-practices
  prompt: What are the key best practices and pitfalls for aws cost ops?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for aws cost ops
  tags:
  - aws
  - best-practices
- id: aws-cost-ops-antipatterns
  prompt: What are the most common mistakes to avoid with aws cost ops?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - aws
  - antipatterns
---
# aws-cost-ops

404: Not Found
