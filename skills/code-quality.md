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
# EVAL CASES
# WHY: Code quality skill must catch naming issues, SRP violations, and dead code
# without over-flagging clean, well-structured code.
# Ref: philschmid.de/testing-skills
eval_cases:
  - id: srp-violation
    prompt: |
      Analyze this class for quality issues:
      class UserManager:
          def create_user(self, email, password): ...
          def send_welcome_email(self, email): ...
          def resize_avatar(self, image_bytes): ...
          def log_activity(self, user_id, action): ...
    should_trigger: true
    checks:
      - "regex:single.*responsib|SRP|cohes|too many|concern|separation"
      - "no_placeholder"
      - "length_min:80"
    expectations:
      - "identifies SRP violation — class handles user creation, email, image, and logging"
      - "suggests splitting into focused classes or services"
    tags: [solid, srp]
  - id: naming-and-dead-code
    prompt: |
      Review this Python function for quality:
      def proc(d, f=True):
          x = d.get('u')
          y = d.get('p')
          # TODO: remove this later
          old_result = validate_old(x)
          return check(x, y) if f else None
    should_trigger: true
    checks:
      - "regex:naming|meaningful|descriptive|dead.*code|unused|TODO|no_placeholder"
      - "not_regex:LGTM|looks fine"
    expectations:
      - "flags cryptic parameter names (d, f, x, y)"
      - "flags dead code (old_result is computed but never used)"
      - "flags the TODO comment as unresolved"
    tags: [naming, dead-code]
  - id: clean-diff-no-issues
    prompt: |
      Analyze this code for quality:
      def calculate_compound_interest(principal: float, rate: float, years: int) -> float:
          if principal <= 0 or rate < 0 or years < 0:
              raise ValueError("Invalid inputs")
          return principal * (1 + rate) ** years
    should_trigger: true
    checks:
      - "length_min:40"
    expectations:
      - "does NOT fabricate quality issues that don't exist"
      - "recognizes clean naming, input validation, and focused responsibility"
    tags: [negative]
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
