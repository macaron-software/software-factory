---
name: vector-index-tuning
version: 1.0.0
description: Optimize vector index performance for latency, recall, and memory. Use
  when tuning HNSW parameters, selecting quantization strategies, or scaling vector
  search infrastructure.
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - tuning hnsw parameters, selecting quantization strategies, or scaling vector sea
  - implementing quantization
eval_cases:
- id: vector-index-tuning-approach
  prompt: How should I approach vector index tuning for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on vector index tuning
  tags:
  - vector
- id: vector-index-tuning-best-practices
  prompt: What are the key best practices and pitfalls for vector index tuning?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for vector index tuning
  tags:
  - vector
  - best-practices
- id: vector-index-tuning-antipatterns
  prompt: What are the most common mistakes to avoid with vector index tuning?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - vector
  - antipatterns
---
# vector-index-tuning

# Vector Index Tuning

Guide to optimizing vector indexes for production performance.

## Use this skill when

- Tuning HNSW parameters
- Implementing quantization
- Optimizing memory usage
- Reducing search latency
- Balancing recall vs speed
- Scaling to billions of vectors

## Do not use this skill when

- You only need exact search on small datasets (use a flat index)
- You lack workload metrics or ground truth to validate recall
- You need end-to-end retrieval system design beyond index tuning

## Instructions

1. Gather workload targets (latency, recall, QPS), data size, and memory budget.
2. Choose an index type and establish a baseline with default parameters.
3. Benchmark parameter sweeps using real queries and track recall, latency, and memory.
4. Validate changes on a staging dataset before rolling out to production.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Safety

- Avoid reindexing in production without a rollback plan.
- Validate changes under realistic load before applying globally.
- Track recall regressions and revert if quality drops.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.
