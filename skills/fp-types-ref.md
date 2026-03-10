---
name: fp-types-ref
version: 1.0.0
description: Quick reference for fp-ts types. Use when user asks which type to use,
  needs Option/Either/Task decision help, or wants fp-ts imports.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - user asks which type to use, needs option/either/task decision help, or wants
    fp
eval_cases:
- id: fp-types-ref-approach
  prompt: How should I approach fp types ref for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fp types ref
  tags:
  - fp
- id: fp-types-ref-best-practices
  prompt: What are the key best practices and pitfalls for fp types ref?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fp types ref
  tags:
  - fp
  - best-practices
- id: fp-types-ref-antipatterns
  prompt: What are the most common mistakes to avoid with fp types ref?
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
# fp-types-ref

# fp-ts Quick Reference

## Which Type Should I Use?

```
Is the operation async?
├─ NO: Does it involve errors?
│   ├─ YES → Either<Error, Value>
│   └─ NO: Might value be missing?
│       ├─ YES → Option<Value>
│       └─ NO → Just use the value
└─ YES: Does it involve errors?
    ├─ YES → TaskEither<Error, Value>
    └─ NO: Might value be missing?
        ├─ YES → TaskOption<Value>
        └─ NO → Task<Value>
```

## Common Imports

```typescript
// Core
import { pipe, flow } from 'fp-ts/function'

// Types
import * as O from 'fp-ts/Option'      // Maybe exists
import * as E from 'fp-ts/Either'      // Success or failure
import * as TE from 'fp-ts/TaskEither' // Async + failure
import * as T from 'fp-ts/Task'        // Async (no failure)
import * as A from 'fp-ts/Array'       // Array utilities
```

## One-Line Patterns

| Need | Code |
|------|------|
| Wrap nullable | `O.fromNullable(value)` |
| Default value | `O.getOrElse(() => default)` |
| Transform if exists | `O.map(fn)` |
| Chain optionals | `O.flatMap(fn)` |
| Wrap try/catch | `E.tryCatch(() => risky(), toError)` |
| Wrap async | `TE.tryCatch(() => fetch(url), toError)` |
| Run pipe | `pipe(value, fn1, fn2, fn3)` |

## Pattern Match

```typescript
// Option
pipe(maybe, O.match(
  () => 'nothing',
  (val) => `got ${val}`
))

// Either
pipe(result, E.match(
  (err) => `error: ${err}`,
  (val) => `success: ${val}`
))
```
