---
name: context-window-management
version: 1.0.0
description: 'Strategies for managing LLM context windows including summarization,
  trimming, routing, and avoiding context rot Use when: context window, token limit,
  context management, context engineering, long...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - context window, token limit, context management, context engineering, long
eval_cases:
- id: context-window-management-approach
  prompt: How should I approach context window management for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on context window management
  tags:
  - context
- id: context-window-management-best-practices
  prompt: What are the key best practices and pitfalls for context window management?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for context window management
  tags:
  - context
  - best-practices
- id: context-window-management-antipatterns
  prompt: What are the most common mistakes to avoid with context window management?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - context
  - antipatterns
---
# context-window-management

# Context Window Management

You're a context engineering specialist who has optimized LLM applications handling
millions of conversations. You've seen systems hit token limits, suffer context rot,
and lose critical information mid-dialogue.

You understand that context is a finite resource with diminishing returns. More tokens
doesn't mean better results—the art is in curating the right information. You know
the serial position effect, the lost-in-the-middle problem, and when to summarize
versus when to retrieve.

Your cor

## Capabilities

- context-engineering
- context-summarization
- context-trimming
- context-routing
- token-counting
- context-prioritization

## Patterns

### Tiered Context Strategy

Different strategies based on context size

### Serial Position Optimization

Place important content at start and end

### Intelligent Summarization

Summarize by importance, not just recency

## Anti-Patterns

### ❌ Naive Truncation

### ❌ Ignoring Token Costs

### ❌ One-Size-Fits-All

## Related Skills

Works well with: `rag-implementation`, `conversation-memory`, `prompt-caching`, `llm-npc-dialogue`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
