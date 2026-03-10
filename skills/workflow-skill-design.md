---
name: workflow-skill-design
version: 1.0.0
description: Workflow Skill Design
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on workflow skill design
eval_cases:
- id: workflow-skill-design-approach
  prompt: How should I approach workflow skill design for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on workflow skill design
  tags:
  - workflow
- id: workflow-skill-design-best-practices
  prompt: What are the key best practices and pitfalls for workflow skill design?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for workflow skill design
  tags:
  - workflow
  - best-practices
- id: workflow-skill-design-antipatterns
  prompt: What are the most common mistakes to avoid with workflow skill design?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - workflow
  - antipatterns
---
# workflow-skill-design

404: Not Found
