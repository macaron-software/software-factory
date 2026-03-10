---
name: aws-mcp-setup
version: 1.0.0
description: Aws Mcp Setup
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on aws mcp setup
eval_cases:
- id: aws-mcp-setup-approach
  prompt: How should I approach aws mcp setup for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on aws mcp setup
  tags:
  - aws
- id: aws-mcp-setup-best-practices
  prompt: What are the key best practices and pitfalls for aws mcp setup?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for aws mcp setup
  tags:
  - aws
  - best-practices
- id: aws-mcp-setup-antipatterns
  prompt: What are the most common mistakes to avoid with aws mcp setup?
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
# aws-mcp-setup

404: Not Found
