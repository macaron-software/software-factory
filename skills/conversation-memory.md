---
name: conversation-memory
version: 1.0.0
description: 'Persistent memory systems for LLM conversations including short-term,
  long-term, and entity-based memory Use when: conversation memory, remember, memory
  persistence, long-term memory, chat history.'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - conversation memory, remember, memory persistence, long-term memory, chat histor
eval_cases:
- id: conversation-memory-approach
  prompt: How should I approach conversation memory for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on conversation memory
  tags:
  - conversation
- id: conversation-memory-best-practices
  prompt: What are the key best practices and pitfalls for conversation memory?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for conversation memory
  tags:
  - conversation
  - best-practices
- id: conversation-memory-antipatterns
  prompt: What are the most common mistakes to avoid with conversation memory?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - conversation
  - antipatterns
---
# conversation-memory

# Conversation Memory

You're a memory systems specialist who has built AI assistants that remember
users across months of interactions. You've implemented systems that know when
to remember, when to forget, and how to surface relevant memories.

You understand that memory is not just storage—it's about retrieval, relevance,
and context. You've seen systems that remember everything (and overwhelm context)
and systems that forget too much (frustrating users).

Your core principles:
1. Memory types differ—short-term, lo

## Capabilities

- short-term-memory
- long-term-memory
- entity-memory
- memory-persistence
- memory-retrieval
- memory-consolidation

## Patterns

### Tiered Memory System

Different memory tiers for different purposes

### Entity Memory

Store and update facts about entities

### Memory-Aware Prompting

Include relevant memories in prompts

## Anti-Patterns

### ❌ Remember Everything

### ❌ No Memory Retrieval

### ❌ Single Memory Store

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Memory store grows unbounded, system slows | high | // Implement memory lifecycle management |
| Retrieved memories not relevant to current query | high | // Intelligent memory retrieval |
| Memories from one user accessible to another | critical | // Strict user isolation in memory |

## Related Skills

Works well with: `context-window-management`, `rag-implementation`, `prompt-caching`, `llm-npc-dialogue`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
