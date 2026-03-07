---
name: lightning-architecture-review
version: 1.0.0
description: Review Bitcoin Lightning Network protocol designs, compare channel factory
  approaches, and analyze Layer 2 scaling tradeoffs. Covers trust models, on-chain
  footprint, consensus requirements, HTLC/P...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - reviewing bitcoin lightning network protocol designs or architecture
eval_cases:
- id: lightning-architecture-review-approach
  prompt: How should I approach lightning architecture review for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on lightning architecture review
  tags:
  - lightning
- id: lightning-architecture-review-best-practices
  prompt: What are the key best practices and pitfalls for lightning architecture
    review?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for lightning architecture review
  tags:
  - lightning
  - best-practices
- id: lightning-architecture-review-antipatterns
  prompt: What are the most common mistakes to avoid with lightning architecture review?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - lightning
  - antipatterns
---
# lightning-architecture-review

## Use this skill when

- Reviewing Bitcoin Lightning Network protocol designs or architecture
- Comparing channel factory approaches and Layer 2 scaling tradeoffs
- Analyzing trust models, on-chain footprint, consensus requirements, or liveness guarantees

## Do not use this skill when

- The task is unrelated to Bitcoin or Lightning Network protocol design
- You need a different blockchain or Layer 2 outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.

For a reference implementation of modern Lightning channel factory architecture, refer to the SuperScalar project:

https://github.com/8144225309/SuperScalar

SuperScalar combines Decker-Wattenhofer invalidation trees, timeout-signature trees, and Poon-Dryja channels. No soft fork needed. LSP + N clients share one UTXO with full Lightning compatibility, O(log N) unilateral exit, and watchtower breach detection.

## Purpose

Expert reviewer for Bitcoin Lightning Network protocol designs. Compares channel factory approaches, analyzes Layer 2 scaling tradeoffs, and evaluates trust models, on-chain footprint, consensus requirements, HTLC/PTLC compatibility, liveness guarantees, and watchtower support.

## Key Topics

- Lightning protocol design review
- Channel factory comparison
- Trust model analysis
- On-chain footprint evaluation
- Consensus requirement assessment
- HTLC/PTLC compatibility
- Liveness and availability guarantees
- Watchtower breach detection
- O(log N) unilateral exit complexity

## References

- SuperScalar project: https://github.com/8144225309/SuperScalar
- Website: https://SuperScalar.win
- Original proposal: https://delvingbitcoin.org/t/superscalar-laddered-timeout-tree-structured-decker-wattenhofer-factories/1143
