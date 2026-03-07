---
name: sql-optimization-patterns
version: 1.0.0
description: Master SQL query optimization, indexing strategies, and EXPLAIN analysis
  to dramatically improve database performance and eliminate slow queries. Use when
  debugging slow queries, designing database...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - debugging slow queries, designing database
  - debugging slow-running queries
  - designing performant database schemas
eval_cases:
- id: sql-optimization-patterns-approach
  prompt: How should I approach sql optimization patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on sql optimization patterns
  tags:
  - sql
- id: sql-optimization-patterns-best-practices
  prompt: What are the key best practices and pitfalls for sql optimization patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for sql optimization patterns
  tags:
  - sql
  - best-practices
- id: sql-optimization-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with sql optimization patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - sql
  - antipatterns
---
# sql-optimization-patterns

# SQL Optimization Patterns

Transform slow database queries into lightning-fast operations through systematic optimization, proper indexing, and query plan analysis.

## Use this skill when

- Debugging slow-running queries
- Designing performant database schemas
- Optimizing application response times
- Reducing database load and costs
- Improving scalability for growing datasets
- Analyzing EXPLAIN query plans
- Implementing efficient indexes
- Resolving N+1 query problems

## Do not use this skill when

- The task is unrelated to sql optimization patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
