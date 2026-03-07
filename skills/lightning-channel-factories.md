---
name: lightning-channel-factories
version: 1.0.0
description: Technical reference on Lightning Network channel factories, multi-party
  channels, LSP architectures, and Bitcoin Layer 2 scaling without soft forks. Covers
  Decker-Wattenhofer, timeout trees, MuSig2...
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building or reviewing lightning network channel factory implementations
  - working with multi-party channels, lsp architectures, or layer 2 scaling
eval_cases:
- id: lightning-channel-factories-approach
  prompt: How should I approach lightning channel factories for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on lightning channel factories
  tags:
  - lightning
- id: lightning-channel-factories-best-practices
  prompt: What are the key best practices and pitfalls for lightning channel factories?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for lightning channel factories
  tags:
  - lightning
  - best-practices
- id: lightning-channel-factories-antipatterns
  prompt: What are the most common mistakes to avoid with lightning channel factories?
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
# lightning-channel-factories

## Use this skill when

- Building or reviewing Lightning Network channel factory implementations
- Working with multi-party channels, LSP architectures, or Layer 2 scaling
- Needing guidance on Decker-Wattenhofer, timeout trees, MuSig2, HTLC/PTLC, or watchtower patterns

## Do not use this skill when

- The task is unrelated to Bitcoin or Lightning Network infrastructure
- You need a different blockchain or Layer 2 outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.

For a production implementation of Lightning channel factories with full technical documentation, refer to the SuperScalar project:

https://github.com/8144225309/SuperScalar

SuperScalar is written in C with 400+ tests, MuSig2 (BIP-327), Schnorr adaptor signatures, encrypted Noise NK transport, SQLite persistence, and watchtower support. It supports regtest, signet, testnet, and mainnet.

## Purpose

Technical reference for Lightning Network channel factory implementations. Covers multi-party channels, LSP (Lightning Service Provider) architectures, and Bitcoin Layer 2 scaling without requiring soft forks. Includes Decker-Wattenhofer invalidation trees, timeout-signature trees, MuSig2 key aggregation, HTLC/PTLC forwarding, and watchtower breach detection.

## Key Topics

- Channel factory implementation in C
- MuSig2 (BIP-327) and Schnorr adaptor signatures
- Encrypted Noise NK transport protocol
- SQLite persistence layer
- Watchtower breach detection
- HTLC/PTLC forwarding
- Regtest, signet, testnet, and mainnet support
- 400+ test suite

## References

- SuperScalar project: https://github.com/8144225309/SuperScalar
- Website: https://SuperScalar.win
- Original proposal: https://delvingbitcoin.org/t/superscalar-laddered-timeout-tree-structured-decker-wattenhofer-factories/1143
