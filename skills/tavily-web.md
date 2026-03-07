---
name: tavily-web
version: 1.0.0
description: Web search, content extraction, crawling, and research capabilities using
  Tavily API
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on tavily web
eval_cases:
- id: tavily-web-approach
  prompt: How should I approach tavily web for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on tavily web
  tags:
  - tavily
- id: tavily-web-best-practices
  prompt: What are the key best practices and pitfalls for tavily web?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for tavily web
  tags:
  - tavily
  - best-practices
- id: tavily-web-antipatterns
  prompt: What are the most common mistakes to avoid with tavily web?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - tavily
  - antipatterns
---
# tavily-web

# tavily-web

## Overview
Web search, content extraction, crawling, and research capabilities using Tavily API

## When to Use
- When you need to search the web for current information
- When extracting content from URLs
- When crawling websites

## Installation
```bash
npx skills add -g BenedictKing/tavily-web
```

## Step-by-Step Guide
1. Install the skill using the command above
2. Configure Tavily API key
3. Use naturally in Claude Code conversations

## Examples
See [GitHub Repository](https://github.com/BenedictKing/tavily-web) for examples.

## Best Practices
- Configure API keys via environment variables

## Troubleshooting
See the GitHub repository for troubleshooting guides.

## Related Skills
- context7-auto-research, exa-search, firecrawl-scraper, codex-review
