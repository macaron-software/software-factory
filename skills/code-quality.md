---
name: code-quality-analyst
description: >
  Analyzes code changes (git diffs) for quality, readability, and structural issues.
  Use this skill to find unclear naming, SRP violations, dead code, and missing error handling.
metadata:
  category: development
  triggers:
    - "when reviewing code quality"
    - "when analyzing a diff for readability"
    - "when simplifying code"
    - "when looking for structural improvements"
---

# Code Quality Analysis

This skill focuses on code quality dimensions that affect long-term maintainability.

## Core analysis areas

### 1. Naming clarity
- Variables named `data`, `result`, `tmp`, `x` without context
- Functions named `process()`, `handle()`, `do_thing()` — too generic
- Boolean variables that don't read as yes/no (`user_flag` vs `is_admin`)
- Inconsistent naming conventions within the same scope

### 2. Single Responsibility Principle
- Functions doing >3 distinct things
- God classes or modules accumulating unrelated logic
- Mixing I/O with business logic (e.g., fetching DB + computing + formatting in one function)

### 3. Dead code in the diff
- Code paths that can never execute (unreachable branches)
- Variables assigned but never read
- Parameters that are never used
- Imports added but not used

### 4. Error handling gaps
- Exceptions caught with bare `except:` (swallowing all errors)
- Missing error handling on I/O operations, network calls, or DB queries
- Silent failures (catching exception and doing nothing)

### 5. Structural clarity
- Overly nested conditionals (>3 levels deep) that could use early returns
- Long parameter lists (>5 params) suggesting missing data class
- Magic numbers/strings without named constants

## Output format

For each finding:
- **Type**: `naming` | `complexity` | `dead-code` | `error-handling` | `structure`
- **Severity**: `high` (blocks understanding or causes bugs) | `medium` (hurts maintainability) | `low` (minor)
- **Suggestion**: specific rename, extraction, or refactoring action

## What to ignore
- Formatting and style (handled by linters)
- Test code structure (different conventions)
- Comments/docs (separate concern)
