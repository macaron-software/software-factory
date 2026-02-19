---
name: webapp-testing
description: >
  Guides the agent through a complete web application testing strategy covering unit tests,
  integration tests, and E2E tests. Use this skill when planning or implementing a testing
  strategy, deciding what to test at each level, or setting up CI test pipelines. Covers
  the test pyramid, fixtures, factories, mocks, and flaky test handling.
metadata:
  category: testing
  triggers:
    - "when user asks about testing strategy"
    - "when planning what tests to write for a feature"
    - "when user asks about the test pyramid"
    - "when setting up CI test pipeline"
    - "when dealing with flaky tests"
---

# Web Application Testing Strategy

This skill enables the agent to design and implement a comprehensive testing strategy
for web applications, covering unit, integration, and E2E tests at the right levels.

## Use this skill when

- Planning testing strategy for a new feature or project
- Deciding what to test at each level (unit, integration, E2E)
- Setting up test infrastructure and CI pipelines
- Debugging flaky tests
- Creating test fixtures and factories
- Reviewing test coverage gaps

## Do not use this skill when

- Writing specific TDD cycles (use tdd-mastery)
- Writing only E2E browser tests (use e2e-browser-testing)
- Writing only API tests (use e2e-api-testing)

## Instructions

### The Test Pyramid

```
        /  E2E  \         ← Few: critical user journeys (5-10%)
       /----------\
      / Integration \     ← Some: API + component (20-30%)
     /----------------\
    /     Unit Tests    \  ← Many: business logic (60-70%)
   /____________________\
```

### What to Test at Each Level

#### Unit Tests (Vitest)

Test pure logic, calculations, transformations, validation:

```typescript
// ✅ GOOD unit test targets
// - Utility functions
// - Validation logic
// - Data transformations
// - State reducers
// - Business rules

import { describe, it, expect } from 'vitest';
import { formatCurrency, validateEmail, calculateTax } from './utils';

describe('formatCurrency', () => {
  it('formats USD with 2 decimals', () => {
    expect(formatCurrency(1234.5, 'USD')).toBe('$1,234.50');
  });

  it('handles zero', () => {
    expect(formatCurrency(0, 'USD')).toBe('$0.00');
  });

  it('handles negative amounts', () => {
    expect(formatCurrency(-50, 'USD')).toBe('-$50.00');
  });
});

describe('validateEmail', () => {
  it.each([
    ['user@example.com', true],
    ['user@.com', false],
    ['@example.com', false],
    ['user@example', false],
    ['', false],
  ])('validates %s as %s', (email, expected) => {
    expect(validateEmail(email)).toBe(expected);
  });
});
```

#### Integration Tests (API layer)

Test API endpoints with real HTTP calls against a test server:

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createTestServer } from './test-helpers';

describe('Users API', () => {
  let server: TestServer;

  beforeAll(async () => {
    server = await createTestServer();
  });

  afterAll(async () => {
    await server.close();
  });

  it('POST /api/users creates a user', async () => {
    const res = await server.fetch('/api/users', {
      method: 'POST',
      body: { email: 'test@example.com', name: 'Test' },
    });

    expect(res.status).toBe(201);
    expect(res.body.id).toBeDefined();
  });

  it('GET /api/users/:id returns the created user', async () => {
    const created = await server.fetch('/api/users', {
      method: 'POST',
      body: { email: 'get@example.com', name: 'Get Test' },
    });

    const res = await server.fetch(`/api/users/${created.body.id}`);
    expect(res.status).toBe(200);
    expect(res.body.email).toBe('get@example.com');
  });
});
```

#### E2E Tests (Playwright)

Test critical user journeys only:

```typescript
import { test, expect } from '@playwright/test';

test('complete purchase flow', async ({ page }) => {
  await test.step('Browse products', async () => {
    await page.goto('/products');
    await page.getByRole('link', { name: 'Premium Plan' }).click();
  });

  await test.step('Add to cart', async () => {
    await page.getByRole('button', { name: 'Add to Cart' }).click();
    await expect(page.getByText('Added to cart')).toBeVisible();
  });

  await test.step('Checkout', async () => {
    await page.goto('/cart');
    await page.getByRole('button', { name: 'Checkout' }).click();
    await page.getByLabel('Card number').fill('4242424242424242');
    await page.getByRole('button', { name: 'Pay' }).click();
  });

  await test.step('Confirm', async () => {
    await expect(page.getByText('Payment successful')).toBeVisible();
  });
});
```

### Test Fixtures & Factories

```typescript
// factories/user.factory.ts
import { faker } from '@faker-js/faker';

export function createUserFixture(overrides?: Partial<User>): User {
  return {
    id: faker.string.uuid(),
    email: faker.internet.email(),
    name: faker.person.fullName(),
    role: 'member',
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

// Usage in tests
const admin = createUserFixture({ role: 'admin' });
const users = Array.from({ length: 10 }, () => createUserFixture());
```

### Mocking Strategy

```typescript
// Mock external services, NOT your own code
vi.mock('./email-service', () => ({
  sendEmail: vi.fn().mockResolvedValue({ success: true }),
}));

// Use MSW for API mocking in component tests
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

const server = setupServer(
  http.get('/api/users', () => {
    return HttpResponse.json([
      { id: '1', name: 'Alice' },
      { id: '2', name: 'Bob' },
    ]);
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### CI Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx vitest run --coverage
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage/

  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npm run build
      - run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
```

### Flaky Test Handling

1. **Identify**: Mark with `test.fixme()` and file an issue
2. **Diagnose**: Usually race conditions, timing, or shared state
3. **Fix root cause**:
   - Add proper waits (not `setTimeout`)
   - Isolate test data (no shared state)
   - Use `test.describe.serial()` only when truly needed
4. **Retry as last resort**:
```typescript
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
});
```

## Output Format

```
## Testing Strategy: [Feature Name]
### Unit Tests (X tests)
- [List of functions/modules tested]

### Integration Tests (X tests)
- [List of API endpoints tested]

### E2E Tests (X tests)
- [List of user journeys tested]

### Coverage: XX% lines, XX% branches
```

## Anti-patterns

- **NEVER** write only E2E tests — they're slow and flaky
- **NEVER** write unit tests for trivial getters/setters
- **NEVER** mock your own code extensively — mock boundaries (APIs, DB, services)
- **NEVER** share state between tests — each test must be independent
- **NEVER** ignore flaky tests — fix them or delete them
- **NEVER** test implementation details — test behavior and outcomes
- **NEVER** skip error paths — test what happens when things go wrong
- **NEVER** let coverage drop below 80% without justification
