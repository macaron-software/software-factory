---
name: code-efficiency-analyst
description: >
  Analyzes code changes (git diffs) for performance and efficiency issues.
  Use this skill to find N+1 queries, redundant operations, blocking I/O, and memory issues.
metadata:
  category: development
  triggers:
    - "when reviewing code for performance"
    - "when analyzing a diff for efficiency"
    - "when simplifying code"
    - "when looking for unnecessary complexity"
---

# Code Efficiency Analysis

This skill targets performance and resource efficiency in new code changes.

## Core analysis areas

### 1. N+1 query patterns
- Loop that executes a DB query on each iteration
- Lazy-loaded relationships accessed in a loop (ORM anti-pattern)
- Multiple individual lookups that could be a single bulk query

### 2. Redundant operations
- Sorting a collection that is already sorted
- Re-computing the same value multiple times in a loop
- Re-parsing the same string/JSON repeatedly
- Filtering a list twice when one pass would do

### 3. Unnecessary complexity
- O(n²) operations where O(n) is achievable (nested loops over the same data)
- Linear search (`if x in list`) on large collections where a set/dict would be O(1)
- Building a string in a loop with `+=` instead of `"".join()`

### 4. Blocking I/O in async context
- `time.sleep()` instead of `await asyncio.sleep()` in async functions
- Synchronous file/DB calls inside async route handlers
- Missing `await` on coroutines (fire-and-forget accident)

### 5. Memory concerns
- Files/connections opened without `with` statement (no guaranteed close)
- Building large lists in memory when a generator would do
- Storing entire response body when only a portion is needed

## Output format

For each finding:
- **Type**: `n+1` | `redundant-op` | `memory` | `blocking-io` | `complexity`
- **Severity**: `high` (impacts correctness or causes resource leak) | `medium` (measurable perf impact) | `low` (micro-optimization)
- **Suggestion**: specific fix (use `asyncio.sleep`, batch query, set comprehension, etc.)

## What to ignore
- Micro-optimizations that don't matter at the current scale
- Theoretical inefficiencies in test/seed code
- Framework-managed resources
