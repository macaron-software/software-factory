---
name: hybrid-search-implementation
version: 1.0.0
description: Combine vector and keyword search for improved retrieval. Use when implementing
  RAG systems, building search engines, or when neither approach alone provides sufficient
  recall.
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing rag systems, building search engines, or when neither approach alon
  - building rag systems with improved recall
eval_cases:
- id: hybrid-search-implementation-approach
  prompt: How should I approach hybrid search implementation for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on hybrid search implementation
  tags:
  - hybrid
- id: hybrid-search-implementation-best-practices
  prompt: What are the key best practices and pitfalls for hybrid search implementation?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for hybrid search implementation
  tags:
  - hybrid
  - best-practices
- id: hybrid-search-implementation-antipatterns
  prompt: What are the most common mistakes to avoid with hybrid search implementation?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - hybrid
  - antipatterns
---
# hybrid-search-implementation

# Hybrid Search Implementation

Patterns for combining vector similarity and keyword-based search.

## Use this skill when

- Building RAG systems with improved recall
- Combining semantic understanding with exact matching
- Handling queries with specific terms (names, codes)
- Improving search for domain-specific vocabulary
- When pure vector search misses keyword matches

## Do not use this skill when

- The task is unrelated to hybrid search implementation
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
