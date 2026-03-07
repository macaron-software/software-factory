---
name: python-performance-optimization
version: 1.0.0
description: Profile and optimize Python code using cProfile, memory profilers, and
  performance best practices. Use when debugging slow Python code, optimizing bottlenecks,
  or improving application performance.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - debugging slow python code, optimizing bottlenecks, or improving application per
eval_cases:
- id: python-performance-optimization-approach
  prompt: How should I approach python performance optimization for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on python performance optimization
  tags:
  - python
- id: python-performance-optimization-best-practices
  prompt: What are the key best practices and pitfalls for python performance optimization?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for python performance optimization
  tags:
  - python
  - best-practices
- id: python-performance-optimization-antipatterns
  prompt: What are the most common mistakes to avoid with python performance optimization?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - python
  - antipatterns
---
# python-performance-optimization

# Python Performance Optimization

Comprehensive guide to profiling, analyzing, and optimizing Python code for better performance, including CPU profiling, memory optimization, and implementation best practices.

## Use this skill when

- Identifying performance bottlenecks in Python applications
- Reducing application latency and response times
- Optimizing CPU-intensive operations
- Reducing memory consumption and memory leaks
- Improving database query performance
- Optimizing I/O operations
- Speeding up data processing pipelines
- Implementing high-performance algorithms
- Profiling production applications

## Do not use this skill when

- The task is unrelated to python performance optimization
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
