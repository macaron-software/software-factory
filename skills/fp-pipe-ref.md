---
name: fp-pipe-ref
version: 1.0.0
description: Quick reference for pipe and flow. Use when user needs to chain functions,
  compose operations, or build data pipelines in fp-ts.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - user needs to chain functions, compose operations, or build data pipelines in
    fp
eval_cases:
- id: fp-pipe-ref-approach
  prompt: How should I approach fp pipe ref for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fp pipe ref
  tags:
  - fp
- id: fp-pipe-ref-best-practices
  prompt: What are the key best practices and pitfalls for fp pipe ref?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fp pipe ref
  tags:
  - fp
  - best-practices
- id: fp-pipe-ref-antipatterns
  prompt: What are the most common mistakes to avoid with fp pipe ref?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - fp
  - antipatterns
---
# fp-pipe-ref

# pipe & flow Quick Reference

## pipe - Transform a Value

```typescript
import { pipe } from 'fp-ts/function'

// pipe(startValue, fn1, fn2, fn3)
// = fn3(fn2(fn1(startValue)))

const result = pipe(
  '  hello world  ',
  s => s.trim(),
  s => s.toUpperCase(),
  s => s.split(' ')
)
// ['HELLO', 'WORLD']
```

## flow - Create Reusable Pipeline

```typescript
import { flow } from 'fp-ts/function'

// flow(fn1, fn2, fn3) returns a new function
const process = flow(
  (s: string) => s.trim(),
  s => s.toUpperCase(),
  s => s.split(' ')
)

process('  hello world  ') // ['HELLO', 'WORLD']
process('  foo bar  ')     // ['FOO', 'BAR']
```

## When to Use

| Use | When |
|-----|------|
| `pipe` | Transform a specific value now |
| `flow` | Create reusable transformation |

## With fp-ts Types

```typescript
import * as O from 'fp-ts/Option'
import * as A from 'fp-ts/Array'

// Option chain
pipe(
  O.fromNullable(user),
  O.map(u => u.email),
  O.getOrElse(() => 'no email')
)

// Array chain
pipe(
  users,
  A.filter(u => u.active),
  A.map(u => u.name)
)
```

## Common Pattern

```typescript
// Data last enables partial application
const getActiveNames = flow(
  A.filter((u: User) => u.active),
  A.map(u => u.name)
)

// Reuse anywhere
getActiveNames(users1)
getActiveNames(users2)
```
