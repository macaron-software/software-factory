---
name: fp-either-ref
version: 1.0.0
description: Quick reference for Either type. Use when user needs error handling,
  validation, or operations that can fail with typed errors.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - user needs error handling, validation, or operations that can fail with typed
    er
eval_cases:
- id: fp-either-ref-approach
  prompt: How should I approach fp either ref for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fp either ref
  tags:
  - fp
- id: fp-either-ref-best-practices
  prompt: What are the key best practices and pitfalls for fp either ref?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fp either ref
  tags:
  - fp
  - best-practices
- id: fp-either-ref-antipatterns
  prompt: What are the most common mistakes to avoid with fp either ref?
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
# fp-either-ref

# Either Quick Reference

Either = success or failure. `Right(value)` or `Left(error)`.

## Create

```typescript
import * as E from 'fp-ts/Either'

E.right(value)           // Success
E.left(error)            // Failure
E.fromNullable(err)(x)   // null → Left(err), else Right(x)
E.tryCatch(fn, toError)  // try/catch → Either
```

## Transform

```typescript
E.map(fn)                // Transform Right value
E.mapLeft(fn)            // Transform Left error
E.flatMap(fn)            // Chain (fn returns Either)
E.filterOrElse(pred, toErr) // Right → Left if pred fails
```

## Extract

```typescript
E.getOrElse(err => default)  // Get Right or default
E.match(onLeft, onRight)     // Pattern match
E.toUnion(either)            // E | A (loses type info)
```

## Common Patterns

```typescript
import { pipe } from 'fp-ts/function'
import * as E from 'fp-ts/Either'

// Validation
const validateEmail = (s: string): E.Either<string, string> =>
  s.includes('@') ? E.right(s) : E.left('Invalid email')

// Chain validations (stops at first error)
pipe(
  E.right({ email: 'test@example.com', age: 25 }),
  E.flatMap(d => pipe(validateEmail(d.email), E.map(() => d))),
  E.flatMap(d => d.age >= 18 ? E.right(d) : E.left('Must be 18+'))
)

// Convert throwing code
const parseJson = (s: string) => E.tryCatch(
  () => JSON.parse(s),
  (e) => `Parse error: ${e}`
)
```

## vs try/catch

```typescript
// ❌ try/catch - errors not in types
try {
  const data = JSON.parse(input)
  process(data)
} catch (e) {
  handleError(e)
}

// ✅ Either - errors explicit in types
pipe(
  E.tryCatch(() => JSON.parse(input), String),
  E.map(process),
  E.match(handleError, identity)
)
```

Use Either when **error type matters** and you want to chain operations.
