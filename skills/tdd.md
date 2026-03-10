---
name: tdd-mastery
description: >
  Guides the agent through strict Test-Driven Development using the Red-Green-Refactor cycle.
  Use this skill whenever writing new features, fixing bugs, or refactoring code that requires
  test coverage. The agent writes failing tests FIRST, then implements minimal code to pass,
  then refactors while keeping tests green.
metadata:
  category: testing
  triggers:
    - "when user asks to write tests before code"
    - "when user asks to implement a feature with TDD"
    - "when user asks to fix a bug and wants a regression test"
    - "when user mentions red-green-refactor"
    - "when test coverage needs to increase"
version: "1.2.0"
# EVAL CASES — based on philschmid.de/testing-skills eval harness methodology
# WHY: Skills shipped without evals = untested behavior. These cases verify
# the skill correctly enforces Red-Green-Refactor and test-first discipline.
# Ref: https://www.philschmid.de/testing-skills
eval_cases:
  - id: tdd-new-feature
    prompt: |
      TDD RED phase is done. Here is the failing test:

      ```python
      import pytest
      from finance import compound_interest

      def test_compound_interest_basic():
          result = compound_interest(principal=1000, rate=0.05, years=3)
          assert abs(result - 1157.625) < 0.01  # 1000 * (1.05)^3

      def test_compound_interest_zero_years():
          assert compound_interest(principal=500, rate=0.1, years=0) == 500.0
      ```

      This test FAILS because `compound_interest` doesn't exist yet.
      Now show the GREEN phase (write the minimal implementation to pass both tests)
      and then the REFACTOR phase (improve code while keeping tests green).
      Do NOT rewrite the tests — just write the implementation.
    should_trigger: true
    checks:
      - "regex:def compound_interest|def calculate_compound"
      - 'regex:return.*principal|return.*rate|return.*\*\*|\(1.*rate\)'
      - "regex:refactor|REFACTOR|clean|improve|docstring|type hint"
      - "length_min:100"
    expectations:
      - "Shows GREEN phase: writes minimal compound_interest() with actual formula (principal * (1+rate)**years)"
      - "Does NOT rewrite the tests — just implements the function"
      - "Shows REFACTOR phase: adds type hints, docstring, or error handling"
    tags: [basic, python]
  - id: tdd-bug-regression
    prompt: |
      There's a bug: get_user(0) returns None instead of raising ValueError. Fix it with TDD.
      Show: RED phase (failing test), GREEN phase (minimal fix), result.
      Do NOT use pass or TODO anywhere — write the actual implementation.
    should_trigger: true
    checks:
      - "regex:def test_.*user|class Test.*User|test_get_user"
      - "regex:ValueError|raises"
      - "regex:get_user"
      - "regex:raise ValueError|pytest.raises"
    expectations:
      - "Writes a failing test reproducing the bug FIRST (test_get_user_raises_for_zero or similar)"
      - "Test uses pytest.raises(ValueError) or assertRaises(ValueError)"
      - "Implementation uses 'raise ValueError' for id=0 — actual code, not a stub"
    tags: [bug, regression]
  - id: tdd-no-trigger-doc
    prompt: "Write documentation for a REST API endpoint that returns a list of users."
    should_trigger: false
    checks: []
    expectations:
      - "produces API documentation without forcing Red-Green-Refactor cycle"
    tags: [negative]
---

# TDD Mastery

This skill enables the agent to practice strict Test-Driven Development across TypeScript/Vitest,
Rust, and Python/pytest. The agent never writes implementation code without a failing test first.

## Use this skill when

- Implementing new features or functions
- Fixing bugs (write a failing test that reproduces the bug first)
- Refactoring existing code (ensure tests exist before changing)
- User explicitly asks for TDD or test-first approach
- Increasing test coverage on existing modules

## Do not use this skill when

- Writing quick prototype/spike code explicitly marked as throwaway
- The task is purely configuration (no logic to test)
- Writing documentation only

## Instructions

### The Red-Green-Refactor Cycle

Every feature follows three strict phases:

#### 1. RED — Write a Failing Test

Write the test BEFORE any implementation. The test must:

- Describe the expected behavior clearly in the test name
- Follow Arrange-Act-Assert (AAA) pattern
- Fail for the RIGHT reason (not a syntax error)

```typescript
// TypeScript + Vitest example
import { describe, it, expect } from "vitest";
import { calculateDiscount } from "./pricing";

describe("calculateDiscount", () => {
  it("should apply 10% discount for orders over $100", () => {
    // Arrange
    const orderTotal = 150;
    const discountTier = "standard";

    // Act
    const result = calculateDiscount(orderTotal, discountTier);

    // Assert
    expect(result).toBe(135);
  });

  it("should return original price for orders under $100", () => {
    const result = calculateDiscount(50, "standard");
    expect(result).toBe(50);
  });

  it("should throw for negative amounts", () => {
    expect(() => calculateDiscount(-10, "standard")).toThrow("Amount must be positive");
  });
});
```

```rust
// Rust example
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calculates_discount_for_large_orders() {
        let result = calculate_discount(150.0, DiscountTier::Standard);
        assert_eq!(result, 135.0);
    }

    #[test]
    #[should_panic(expected = "Amount must be positive")]
    fn rejects_negative_amounts() {
        calculate_discount(-10.0, DiscountTier::Standard);
    }
}
```

```python
# Python + pytest example
import pytest
from pricing import calculate_discount

def test_applies_10_percent_discount_over_100():
    result = calculate_discount(150, "standard")
    assert result == 135

def test_returns_original_price_under_100():
    assert calculate_discount(50, "standard") == 50

def test_rejects_negative_amounts():
    with pytest.raises(ValueError, match="Amount must be positive"):
        calculate_discount(-10, "standard")
```

#### 2. GREEN — Write Minimal Code to Pass

Implement ONLY what's needed to make the failing test pass. No extra features, no premature optimization.

```typescript
export function calculateDiscount(amount: number, tier: string): number {
  if (amount < 0) throw new Error("Amount must be positive");
  if (amount > 100 && tier === "standard") {
    return amount * 0.9;
  }
  return amount;
}
```

#### 3. REFACTOR — Improve Without Changing Behavior

With green tests as safety net, improve:

- Extract constants/enums
- Remove duplication
- Improve naming
- Simplify logic

Run tests after EVERY refactor step. If any test fails, revert immediately.

### Mocking Strategies

Use mocks ONLY when:

- External services (APIs, databases)
- Non-deterministic behavior (dates, random)
- Slow dependencies (file system, network)

```typescript
import { vi, describe, it, expect, beforeEach } from "vitest";
import { UserService } from "./user-service";
import { EmailClient } from "./email-client";

vi.mock("./email-client");

describe("UserService", () => {
  let service: UserService;
  let mockEmailClient: EmailClient;

  beforeEach(() => {
    mockEmailClient = {
      send: vi.fn().mockResolvedValue({ success: true }),
    } as unknown as EmailClient;
    service = new UserService(mockEmailClient);
  });

  it("should send welcome email on registration", async () => {
    await service.register("user@example.com", "password123");

    expect(mockEmailClient.send).toHaveBeenCalledWith({
      to: "user@example.com",
      template: "welcome",
    });
  });
});
```

### Coverage Enforcement

- Target: **80% minimum** line coverage, **70% minimum** branch coverage
- Run coverage after each feature: `vitest run --coverage`
- Never skip edge cases: null, undefined, empty strings, boundary values
- Test error paths as thoroughly as happy paths

### Test Naming Convention

Use descriptive names that read like specifications:

- `it('should reject passwords shorter than 8 characters')`
- `it('returns empty array when no results match filter')`
- `test_raises_permission_error_for_non_admin_users`

## Output Format

When applying TDD, output each phase clearly:

```
## RED Phase
[Test code that fails]
Expected failure: [description]

## GREEN Phase
[Minimal implementation]
All tests passing: ✅

## REFACTOR Phase
[Improved code]
All tests still passing: ✅
Coverage: XX%
```

## Anti-patterns

- **NEVER** write implementation before the test
- **NEVER** write a test that passes immediately (it proves nothing)
- **NEVER** mock everything — prefer real implementations for value objects and pure functions
- **NEVER** skip the refactor phase — technical debt accumulates
- **NEVER** test implementation details (private methods, internal state) — test behavior
- **NEVER** use `test.skip()` or `@pytest.mark.skip` without a linked issue/ticket
- **NEVER** write tests without assertions (test must assert something meaningful)
- **NEVER** copy-paste tests — use parameterized tests for similar cases
