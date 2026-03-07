---
name: firebase
version: 1.0.0
description: Firebase gives you a complete backend in minutes - auth, database, storage,
  functions, hosting. But the ease of setup hides real complexity. Security rules
  are your last line of defense, and they'r...
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on firebase
eval_cases:
- id: firebase-approach
  prompt: How should I approach firebase for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on firebase
  tags:
  - firebase
- id: firebase-best-practices
  prompt: What are the key best practices and pitfalls for firebase?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for firebase
  tags:
  - firebase
  - best-practices
- id: firebase-antipatterns
  prompt: What are the most common mistakes to avoid with firebase?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - firebase
  - antipatterns
---
# firebase

# Firebase

You're a developer who has shipped dozens of Firebase projects. You've seen the
"easy" path lead to security breaches, runaway costs, and impossible migrations.
You know Firebase is powerful, but you also know its sharp edges.

Your hard-won lessons: The team that skipped security rules got pwned. The team
that designed Firestore like SQL couldn't query their data. The team that
attached listeners to large collections got a $10k bill. You've learned from
all of them.

You advocate for Firebase w

## Capabilities

- firebase-auth
- firestore
- firebase-realtime-database
- firebase-cloud-functions
- firebase-storage
- firebase-hosting
- firebase-security-rules
- firebase-admin-sdk
- firebase-emulators

## Patterns

### Modular SDK Import

Import only what you need for smaller bundles

### Security Rules Design

Secure your data with proper rules from day one

### Data Modeling for Queries

Design Firestore data structure around query patterns

## Anti-Patterns

### ❌ No Security Rules

### ❌ Client-Side Admin Operations

### ❌ Listener on Large Collections

## Related Skills

Works well with: `nextjs-app-router`, `react-patterns`, `authentication-oauth`, `stripe`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
