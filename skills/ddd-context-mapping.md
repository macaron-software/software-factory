---
name: ddd-context-mapping
version: 1.0.0
description: Map relationships between bounded contexts and define integration contracts
  using DDD context mapping patterns.
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: self'
  triggers:
  - when working on ddd context mapping
eval_cases:
- id: ddd-context-mapping-approach
  prompt: How should I approach ddd context mapping for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on ddd context mapping
  tags:
  - ddd
- id: ddd-context-mapping-best-practices
  prompt: What are the key best practices and pitfalls for ddd context mapping?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for ddd context mapping
  tags:
  - ddd
  - best-practices
- id: ddd-context-mapping-antipatterns
  prompt: What are the most common mistakes to avoid with ddd context mapping?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - ddd
  - antipatterns
---
# ddd-context-mapping

# DDD Context Mapping

## Use this skill when

- Defining integration patterns between bounded contexts.
- Preventing domain leakage across service boundaries.
- Planning anti-corruption layers during migration.
- Clarifying upstream and downstream ownership for contracts.

## Do not use this skill when

- You have a single-context system with no integrations.
- You only need internal class design.
- You are selecting cloud infrastructure tooling.

## Instructions

1. List all context pairs and dependency direction.
2. Choose relationship patterns per pair.
3. Define translation rules and ownership boundaries.
4. Add failure modes, fallback behavior, and versioning policy.

If detailed mapping structures are needed, open `references/context-map-patterns.md`.

## Output requirements

- Relationship map for all context pairs
- Contract ownership matrix
- Translation and anti-corruption decisions
- Known coupling risks and mitigation plan

## Examples

```text
Use @ddd-context-mapping to define how Checkout integrates with Billing,
Inventory, and Fraud contexts, including ACL and contract ownership.
```

## Limitations

- This skill does not replace API-level schema design.
- It does not guarantee organizational alignment by itself.
- It should be revisited when team ownership changes.
