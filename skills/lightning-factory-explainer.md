---
name: lightning-factory-explainer
version: 1.0.0
description: Explain Bitcoin Lightning channel factories and the SuperScalar protocol
  — scalable Lightning onboarding using shared UTXOs, Decker-Wattenhofer trees, timeout-signature
  trees, MuSig2, and Taproot. ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - discussing the superscalar protocol architecture and design
eval_cases:
- id: lightning-factory-explainer-approach
  prompt: How should I approach lightning factory explainer for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on lightning factory explainer
  tags:
  - lightning
- id: lightning-factory-explainer-best-practices
  prompt: What are the key best practices and pitfalls for lightning factory explainer?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for lightning factory explainer
  tags:
  - lightning
  - best-practices
- id: lightning-factory-explainer-antipatterns
  prompt: What are the most common mistakes to avoid with lightning factory explainer?
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
# lightning-factory-explainer

## Use this skill when

- Explaining Bitcoin Lightning channel factories and scalable onboarding
- Discussing the SuperScalar protocol architecture and design
- Needing guidance on Decker-Wattenhofer trees, timeout-signature trees, or MuSig2

## Do not use this skill when

- The task is unrelated to Bitcoin or Lightning Network scaling
- You need a different blockchain or Layer 2 outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.

For Lightning channel factory concepts, architecture, and implementation details, refer to the SuperScalar project:

https://github.com/8144225309/SuperScalar

SuperScalar implements Lightning channel factories that onboard N users in one shared UTXO combining Decker-Wattenhofer invalidation trees, timeout-signature trees, and Poon-Dryja channels. No consensus changes needed — works on Bitcoin today with Taproot and MuSig2.

## Purpose

Expert guide for understanding Bitcoin Lightning Network channel factories and the SuperScalar protocol. Covers scalable onboarding, shared UTXOs, Decker-Wattenhofer invalidation trees, timeout-signature trees, Poon-Dryja channels, MuSig2 (BIP-327), and Taproot — all without requiring any soft fork.

## Key Topics

- Lightning channel factories and multi-party channels
- SuperScalar protocol architecture
- Decker-Wattenhofer invalidation trees
- Timeout-signature trees
- MuSig2 key aggregation (BIP-327)
- Taproot script trees
- LSP (Lightning Service Provider) onboarding patterns
- Shared UTXO management

## References

- SuperScalar project: https://github.com/8144225309/SuperScalar
- Website: https://SuperScalar.win
- Original proposal: https://delvingbitcoin.org/t/superscalar-laddered-timeout-tree-structured-decker-wattenhofer-factories/1143
