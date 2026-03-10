---
name: firecrawl-scraper
version: 1.0.0
description: Deep web scraping, screenshots, PDF parsing, and website crawling using
  Firecrawl API
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on firecrawl scraper
eval_cases:
- id: firecrawl-scraper-approach
  prompt: How should I approach firecrawl scraper for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on firecrawl scraper
  tags:
  - firecrawl
- id: firecrawl-scraper-best-practices
  prompt: What are the key best practices and pitfalls for firecrawl scraper?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for firecrawl scraper
  tags:
  - firecrawl
  - best-practices
- id: firecrawl-scraper-antipatterns
  prompt: What are the most common mistakes to avoid with firecrawl scraper?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - firecrawl
  - antipatterns
---
# firecrawl-scraper

# firecrawl-scraper

## Overview
Deep web scraping, screenshots, PDF parsing, and website crawling using Firecrawl API

## When to Use
- When you need deep content extraction from web pages
- When page interaction is required (clicking, scrolling, etc.)
- When you want screenshots or PDF parsing
- When batch scraping multiple URLs

## Installation
```bash
npx skills add -g BenedictKing/firecrawl-scraper
```

## Step-by-Step Guide
1. Install the skill using the command above
2. Configure Firecrawl API key
3. Use naturally in Claude Code conversations

## Examples
See [GitHub Repository](https://github.com/BenedictKing/firecrawl-scraper) for examples.

## Best Practices
- Configure API keys via environment variables

## Troubleshooting
See the GitHub repository for troubleshooting guides.

## Related Skills
- context7-auto-research, tavily-web, exa-search, codex-review
