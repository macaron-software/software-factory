---
name: solidity-security
version: 1.0.0
description: Master smart contract security best practices to prevent common vulnerabilities
  and implement secure Solidity patterns. Use when writing smart contracts, auditing
  existing contracts, or implementin...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing smart contracts, auditing existing contracts, or implementin
  - writing secure smart contracts
  - implementing secure defi protocols
eval_cases:
- id: solidity-security-approach
  prompt: How should I approach solidity security for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on solidity security
  tags:
  - solidity
- id: solidity-security-best-practices
  prompt: What are the key best practices and pitfalls for solidity security?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for solidity security
  tags:
  - solidity
  - best-practices
- id: solidity-security-antipatterns
  prompt: What are the most common mistakes to avoid with solidity security?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - solidity
  - antipatterns
---
# solidity-security

# Solidity Security

Master smart contract security best practices, vulnerability prevention, and secure Solidity development patterns.

## Use this skill when

- Writing secure smart contracts
- Auditing existing contracts for vulnerabilities
- Implementing secure DeFi protocols
- Preventing reentrancy, overflow, and access control issues
- Optimizing gas usage while maintaining security
- Preparing contracts for professional audits
- Understanding common attack vectors

## Do not use this skill when

- The task is unrelated to solidity security
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
