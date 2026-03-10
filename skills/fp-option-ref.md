---
name: fp-option-ref
version: 1.0.0
description: Quick reference for Option type. Use when user needs to handle nullable
  values, optional data, or wants to avoid null checks.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - user needs to handle nullable values, optional data, or wants to avoid null chec
eval_cases:
- id: fp-option-ref-approach
  prompt: How should I approach fp option ref for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fp option ref
  tags:
  - fp
- id: fp-option-ref-best-practices
  prompt: What are the key best practices and pitfalls for fp option ref?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fp option ref
  tags:
  - fp
  - best-practices
- id: fp-option-ref-antipatterns
  prompt: What are the most common mistakes to avoid with fp option ref?
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
# fp-option-ref

# Option Quick Reference

Option = value that might not exist. `Some(value)` or `None`.

## Create

```typescript
import * as O from 'fp-ts/Option'

O.some(5)              // Some(5)
O.none                 // None
O.fromNullable(x)      // null/undefined → None, else Some(x)
O.fromPredicate(x > 0)(x) // false → None, true → Some(x)
```

## Transform

```typescript
O.map(fn)              // Transform inner value
O.flatMap(fn)          // Chain Options (fn returns Option)
O.filter(predicate)    // None if predicate false
```

## Extract

```typescript
O.getOrElse(() => default)  // Get value or default
O.toNullable(opt)           // Back to T | null
O.toUndefined(opt)          // Back to T | undefined
O.match(onNone, onSome)     // Pattern match
```

## Common Patterns

```typescript
import { pipe } from 'fp-ts/function'
import * as O from 'fp-ts/Option'

// Safe property access
pipe(
  O.fromNullable(user),
  O.map(u => u.profile),
  O.flatMap(p => O.fromNullable(p.avatar)),
  O.getOrElse(() => '/default-avatar.png')
)

// Array first element
import * as A from 'fp-ts/Array'
pipe(
  users,
  A.head,  // Option<User>
  O.map(u => u.name),
  O.getOrElse(() => 'No users')
)
```

## vs Nullable

```typescript
// ❌ Nullable - easy to forget checks
const name = user?.profile?.name ?? 'Guest'

// ✅ Option - explicit, composable
pipe(
  O.fromNullable(user),
  O.flatMap(u => O.fromNullable(u.profile)),
  O.map(p => p.name),
  O.getOrElse(() => 'Guest')
)
```

Use Option when you need to **chain** operations on optional values.
