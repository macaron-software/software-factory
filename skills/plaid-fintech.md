---
name: plaid-fintech
version: 1.0.0
description: Expert patterns for Plaid API integration including Link token flows,
  transactions sync, identity verification, Auth for ACH, balance checks, webhook
  handling, and fintech compliance best practices...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on plaid fintech
eval_cases:
- id: plaid-fintech-approach
  prompt: How should I approach plaid fintech for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on plaid fintech
  tags:
  - plaid
- id: plaid-fintech-best-practices
  prompt: What are the key best practices and pitfalls for plaid fintech?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for plaid fintech
  tags:
  - plaid
  - best-practices
- id: plaid-fintech-antipatterns
  prompt: What are the most common mistakes to avoid with plaid fintech?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - plaid
  - antipatterns
---
# plaid-fintech

# Plaid Fintech

## Patterns

### Link Token Creation and Exchange

Create a link_token for Plaid Link, exchange public_token for access_token.
Link tokens are short-lived, one-time use. Access tokens don't expire but
may need updating when users change passwords.


### Transactions Sync

Use /transactions/sync for incremental transaction updates. More efficient
than /transactions/get. Handle webhooks for real-time updates instead of
polling.


### Item Error Handling and Update Mode

Handle ITEM_LOGIN_REQUIRED errors by putting users through Link update mode.
Listen for PENDING_DISCONNECT webhook to proactively prompt users.


## Anti-Patterns

### ❌ Storing Access Tokens in Plain Text

### ❌ Polling Instead of Webhooks

### ❌ Ignoring Item Errors

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | critical | See docs |
| Issue | high | See docs |
| Issue | high | See docs |
| Issue | high | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |
| Issue | medium | See docs |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
