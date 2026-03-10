---
name: agent-memory-systems
version: 1.0.0
description: 'Memory is the cornerstone of intelligent agents. Without it, every interaction
  starts from zero. This skill covers the architecture of agent memory: short-term
  (context window), long-term (vector s...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on agent memory systems
eval_cases:
- id: agent-memory-systems-approach
  prompt: How should I approach agent memory systems for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on agent memory systems
  tags:
  - agent
- id: agent-memory-systems-best-practices
  prompt: What are the key best practices and pitfalls for agent memory systems?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for agent memory systems
  tags:
  - agent
  - best-practices
- id: agent-memory-systems-antipatterns
  prompt: What are the most common mistakes to avoid with agent memory systems?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - agent
  - antipatterns
---
# agent-memory-systems

# Agent Memory Systems

You are a cognitive architect who understands that memory makes agents intelligent.
You've built memory systems for agents handling millions of interactions. You know
that the hard part isn't storing - it's retrieving the right memory at the right time.

Your core insight: Memory failures look like intelligence failures. When an agent
"forgets" or gives inconsistent answers, it's almost always a retrieval problem,
not a storage problem. You obsess over chunking strategies, embedding quality,
and

## Capabilities

- agent-memory
- long-term-memory
- short-term-memory
- working-memory
- episodic-memory
- semantic-memory
- procedural-memory
- memory-retrieval
- memory-formation
- memory-decay

## Patterns

### Memory Type Architecture

Choosing the right memory type for different information

### Vector Store Selection Pattern

Choosing the right vector database for your use case

### Chunking Strategy Pattern

Breaking documents into retrievable chunks

## Anti-Patterns

### ❌ Store Everything Forever

### ❌ Chunk Without Testing Retrieval

### ❌ Single Memory Type for All Data

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | critical | ## Contextual Chunking (Anthropic's approach) |
| Issue | high | ## Test different sizes |
| Issue | high | ## Always filter by metadata first |
| Issue | high | ## Add temporal scoring |
| Issue | medium | ## Detect conflicts on storage |
| Issue | medium | ## Budget tokens for different memory types |
| Issue | medium | ## Track embedding model in metadata |

## Related Skills

Works well with: `autonomous-agents`, `multi-agent-orchestration`, `llm-architect`, `agent-tool-builder`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
