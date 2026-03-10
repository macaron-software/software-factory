---
name: codex-review
version: 1.0.0
description: Professional code review with auto CHANGELOG generation, integrated with
  Codex AI
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when you want professional code review before commits
  - when reviewing large-scale refactoring
eval_cases:
- id: codex-review-approach
  prompt: How should I approach codex review for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on codex review
  tags:
  - codex
- id: codex-review-best-practices
  prompt: What are the key best practices and pitfalls for codex review?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for codex review
  tags:
  - codex
  - best-practices
- id: codex-review-antipatterns
  prompt: What are the most common mistakes to avoid with codex review?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - codex
  - antipatterns
---
# codex-review

# codex-review

## Overview
Professional code review with auto CHANGELOG generation, integrated with Codex AI

## When to Use
- When you want professional code review before commits
- When you need automatic CHANGELOG generation
- When reviewing large-scale refactoring

## Installation
```bash
npx skills add -g BenedictKing/codex-review
```

## Step-by-Step Guide
1. Install the skill using the command above
2. Ensure Codex CLI is installed
3. Use `/codex-review` or natural language triggers

## Examples
See [GitHub Repository](https://github.com/BenedictKing/codex-review) for examples.

## Best Practices
- Keep CHANGELOG.md in your project root
- Use conventional commit messages

## Troubleshooting
See the GitHub repository for troubleshooting guides.

## Related Skills
- context7-auto-research, tavily-web, exa-search, firecrawl-scraper
