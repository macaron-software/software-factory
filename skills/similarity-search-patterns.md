---
name: similarity-search-patterns
version: 1.0.0
description: Implement efficient similarity search with vector databases. Use when
  building semantic search, implementing nearest neighbor queries, or optimizing retrieval
  performance.
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building semantic search, implementing nearest neighbor queries, or optimizing
    r
  - building semantic search systems
  - implementing rag retrieval
  - creating recommendation engines
eval_cases:
- id: similarity-search-patterns-approach
  prompt: How should I approach similarity search patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on similarity search patterns
  tags:
  - similarity
- id: similarity-search-patterns-best-practices
  prompt: What are the key best practices and pitfalls for similarity search patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for similarity search patterns
  tags:
  - similarity
  - best-practices
- id: similarity-search-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with similarity search patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - similarity
  - antipatterns
---
# similarity-search-patterns

# Similarity Search Patterns

Patterns for implementing efficient similarity search in production systems.

## Use this skill when

- Building semantic search systems
- Implementing RAG retrieval
- Creating recommendation engines
- Optimizing search latency
- Scaling to millions of vectors
- Combining semantic and keyword search

## Do not use this skill when

- The task is unrelated to similarity search patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
