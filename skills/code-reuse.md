---
name: code-reuse-analyst
description: >
  Analyzes code changes (git diffs) specifically for duplication and reuse opportunities.
  Use this skill to detect copy-pasted logic, re-implemented utilities, and extractable patterns.
metadata:
  category: development
  triggers:
    - "when reviewing code for duplication"
    - "when looking for refactoring opportunities"
    - "when analyzing a diff for reuse issues"
    - "when simplifying code"
---

# Code Reuse Analysis

This skill focuses exclusively on identifying code reuse opportunities in a git diff.

## Core analysis areas

### 1. Duplicated logic
- Identical or near-identical code blocks repeated across files
- Same computation done in multiple places
- Copy-pasted functions with minor variable changes

### 2. Re-implemented utilities
- Standard library functions being reimplemented manually
- Project utilities being duplicated instead of imported
- Common patterns (retry logic, pagination, error wrapping) coded from scratch

### 3. Extractable patterns
- Sequences of operations repeated 2+ times that could be a helper function
- Inline logic that belongs in an existing class/module
- Conditional branches that could be a lookup table or mapping

## Output format

For each finding, report:
- **File and approximate line**
- **Type**: `duplication` | `extractable` | `reimplemented`
- **Severity**: `high` (same block repeated 3+ times or >20 lines) | `medium` (2x or 10-20 lines) | `low` (minor)
- **Concrete suggestion**: name of the function to extract, or import to use

## What to ignore
- Single-use utility code that happens to be simple
- Test fixtures (some repetition is intentional)
- Configuration constants (not logic)
