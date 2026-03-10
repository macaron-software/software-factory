---
name: exa-search
version: 1.0.0
description: Semantic search, similar content discovery, and structured research using
  Exa API
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on exa search
eval_cases:
- id: exa-search-approach
  prompt: How should I approach exa search for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on exa search
  tags:
  - exa
- id: exa-search-best-practices
  prompt: What are the key best practices and pitfalls for exa search?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for exa search
  tags:
  - exa
  - best-practices
- id: exa-search-antipatterns
  prompt: What are the most common mistakes to avoid with exa search?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - exa
  - antipatterns
---
# exa-search

# exa-search

## Overview
Semantic search, similar content discovery, and structured research using Exa API

## When to Use
- When you need semantic/embeddings-based search
- When finding similar content
- When searching by category (company, people, research papers, etc.)

## Installation
```bash
npx skills add -g BenedictKing/exa-search
```

## Step-by-Step Guide
1. Install the skill using the command above
2. Configure Exa API key
3. Use naturally in Claude Code conversations

## Examples
See [GitHub Repository](https://github.com/BenedictKing/exa-search) for examples.

## Best Practices
- Configure API keys via environment variables

## Troubleshooting
See the GitHub repository for troubleshooting guides.

## Related Skills
- context7-auto-research, tavily-web, firecrawl-scraper, codex-review
