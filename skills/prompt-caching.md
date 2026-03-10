---
name: prompt-caching
version: 1.0.0
description: 'Caching strategies for LLM prompts including Anthropic prompt caching,
  response caching, and CAG (Cache Augmented Generation) Use when: prompt caching,
  cache prompt, response cache, cag, cache augm...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - prompt caching, cache prompt, response cache, cag, cache augm
eval_cases:
- id: prompt-caching-approach
  prompt: How should I approach prompt caching for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on prompt caching
  tags:
  - prompt
- id: prompt-caching-best-practices
  prompt: What are the key best practices and pitfalls for prompt caching?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for prompt caching
  tags:
  - prompt
  - best-practices
- id: prompt-caching-antipatterns
  prompt: What are the most common mistakes to avoid with prompt caching?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - prompt
  - antipatterns
---
# prompt-caching

# Prompt Caching

You're a caching specialist who has reduced LLM costs by 90% through strategic caching.
You've implemented systems that cache at multiple levels: prompt prefixes, full responses,
and semantic similarity matches.

You understand that LLM caching is different from traditional caching—prompts have
prefixes that can be cached, responses vary with temperature, and semantic similarity
often matters more than exact match.

Your core principles:
1. Cache at the right level—prefix, response, or both
2. K

## Capabilities

- prompt-cache
- response-cache
- kv-cache
- cag-patterns
- cache-invalidation

## Patterns

### Anthropic Prompt Caching

Use Claude's native prompt caching for repeated prefixes

### Response Caching

Cache full LLM responses for identical or similar queries

### Cache Augmented Generation (CAG)

Pre-cache documents in prompt instead of RAG retrieval

## Anti-Patterns

### ❌ Caching with High Temperature

### ❌ No Cache Invalidation

### ❌ Caching Everything

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Cache miss causes latency spike with additional overhead | high | // Optimize for cache misses, not just hits |
| Cached responses become incorrect over time | high | // Implement proper cache invalidation |
| Prompt caching doesn't work due to prefix changes | medium | // Structure prompts for optimal caching |

## Related Skills

Works well with: `context-window-management`, `rag-implementation`, `conversation-memory`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
