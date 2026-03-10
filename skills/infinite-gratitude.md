---
name: infinite-gratitude
version: 1.0.0
description: Multi-agent research skill for parallel research execution (10 agents,
  battle-tested with real case studies).
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/sstklen/infinite-gratitude'
  triggers:
  - when working on infinite gratitude
eval_cases:
- id: infinite-gratitude-approach
  prompt: How should I approach infinite gratitude for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on infinite gratitude
  tags:
  - infinite
- id: infinite-gratitude-best-practices
  prompt: What are the key best practices and pitfalls for infinite gratitude?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for infinite gratitude
  tags:
  - infinite
  - best-practices
- id: infinite-gratitude-antipatterns
  prompt: What are the most common mistakes to avoid with infinite gratitude?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - infinite
  - antipatterns
---
# infinite-gratitude

# Infinite Gratitude

> **Source**: [sstklen/infinite-gratitude](https://github.com/sstklen/infinite-gratitude)

## Description

A multi-agent research skill designed for parallel research execution. It orchestrates 10 agents to conduct deep research, battle-tested with real case studies.

## When to Use

Use this skill when you need to perform extensive, parallelized research on a topic, leveraging multiple agents to gather and synthesize information more efficiently than a single linear process.

## How to Use

This is an external skill. Please refer to the [official repository](https://github.com/sstklen/infinite-gratitude) for installation and usage instructions.

```bash
git clone https://github.com/sstklen/infinite-gratitude
```
