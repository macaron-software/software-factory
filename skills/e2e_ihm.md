---
name: e2e-browser-testing
description: >
  Guides the agent through end-to-end browser testing with Playwright. Use this skill
  when testing user interface interactions, user journeys, multi-step workflows, and
  visual elements in a real browser. Covers clicks, form fills, navigation, waits,
  and accessibility checks.
metadata:
  category: testing
  triggers:
    - "when user asks to test a web page interaction"
    - "when user wants to test a user journey or workflow"
    - "when testing form submissions in a browser"
    - "when user asks for Playwright tests"
    - "when testing multi-user scenarios"
---

# E2E Browser Testing

This skill enables the agent to write robust Playwright browser tests that simulate real
user interactions. Tests cover clicks, form fills, navigation, multi-user workflows,
and accessibility checks.

## Use this skill when

- Testing user journeys (login → navigate → action → verify)
- Verifying form submissions and validation messages
- Testing multi-user scenarios (admin creates, user views)
- Checking responsive layout behavior
- Verifying navigation flows and routing
- Testing drag-and-drop, file upload, modals

## Do not use this skill when

- Testing API endpoints directly (use e2e-api-testing)
- Testing component logic in isolation (use tdd-mastery)
- Quick page health checks (use smoke-testing)

## Instructions

### Test Structure with test.step()

Always use `test.step()` to break tests into readable phases:

```typescript
import { test, expect } from "@playwright/test";

test("user can create and publish an article", async ({ page }) => {
  await test.step("Login as editor", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("editor@test.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Dashboard")).toBeVisible();
  });

  await test.step("Create a new article", async () => {
    await page.getByRole("link", { name: "New Article" }).click();
    await page.getByLabel("Title").fill("My Test Article");
    await page.getByLabel("Content").fill("This is the article body.");
    await page.getByRole("button", { name: "Save Draft" }).click();
    await expect(page.getByText("Draft saved")).toBeVisible();
  });

  await test.step("Publish the article", async () => {
    await page.getByRole("button", { name: "Publish" }).click();
    await expect(page.getByText("Published")).toBeVisible();
  });

  await test.step("Verify article is visible on homepage", async () => {
    await page.goto("/");
    await expect(page.getByText("My Test Article")).toBeVisible();
  });
});
```

### Locator Strategy (Priority Order)

1. **Role-based** (best): `page.getByRole('button', { name: 'Submit' })`
2. **Label-based**: `page.getByLabel('Email')`
3. **Text-based**: `page.getByText('Welcome back')`
4. **Placeholder**: `page.getByPlaceholder('Search...')`
5. **Test ID** (fallback): `page.getByTestId('submit-btn')`
6. **CSS selector** (last resort): `page.locator('.submit-button')`

Never use fragile selectors like `div > span:nth-child(3)`.

### Page Object Pattern

```typescript
// pages/login.page.ts
import { Page, expect } from "@playwright/test";

export class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto("/login");
  }

  async login(email: string, password: string) {
    await this.page.getByLabel("Email").fill(email);
    await this.page.getByLabel("Password").fill(password);
    await this.page.getByRole("button", { name: "Sign in" }).click();
  }

  async expectError(message: string) {
    await expect(this.page.getByRole("alert")).toContainText(message);
  }

  async expectLoggedIn() {
    await expect(this.page.getByText("Dashboard")).toBeVisible();
  }
}

// tests/login.spec.ts
import { test } from "@playwright/test";
import { LoginPage } from "../pages/login.page";

test("shows error for invalid credentials", async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login("bad@email.com", "wrongpassword");
  await loginPage.expectError("Invalid credentials");
});
```

### Waiting Strategies

```typescript
// ✅ GOOD: Wait for specific element
await expect(page.getByText("Data loaded")).toBeVisible({ timeout: 10000 });

// ✅ GOOD: Wait for network idle after action
await page.getByRole("button", { name: "Load More" }).click();
await page.waitForResponse((resp) => resp.url().includes("/api/items") && resp.status() === 200);

// ✅ GOOD: Wait for navigation
await Promise.all([
  page.waitForURL("/dashboard"),
  page.getByRole("link", { name: "Dashboard" }).click(),
]);

// ❌ BAD: Never use fixed waits
await page.waitForTimeout(3000); // NEVER DO THIS
```

### Multi-User Scenarios

```typescript
import { test, expect, Browser } from "@playwright/test";

test("admin creates item, user sees it", async ({ browser }) => {
  const adminContext = await browser.newContext();
  const userContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  const userPage = await userContext.newPage();

  await test.step("Admin creates item", async () => {
    await adminPage.goto("/login");
    // ... login as admin, create item
  });

  await test.step("User sees the item", async () => {
    await userPage.goto("/items");
    await expect(userPage.getByText("New Item")).toBeVisible();
  });

  await adminContext.close();
  await userContext.close();
});
```

### Screenshot at Every Journey Step (MANDATORY)

**ALWAYS** take a `page.screenshot()` at the end of every `test.step()` when testing user journeys.
Screenshots document the full user journey with real data and must be saved to `screenshots/` in the project workspace.

Naming convention: `NN-feature-state.png` (sequential, kebab-case, describes the UI state shown).

```typescript
import { test, expect } from "@playwright/test";
import * as fs from "fs";

// Ensure screenshots dir exists before tests run
test.beforeAll(() => fs.mkdirSync("screenshots", { recursive: true }));

test("full CRUD user journey", async ({ page }) => {
  await test.step("Login", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@demo.local");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Dashboard")).toBeVisible();
    await page.screenshot({ path: "screenshots/01-login-success.png", fullPage: true });
  });

  await test.step("List — empty state", async () => {
    await page.goto("/items");
    await expect(page.getByText(/no items|empty/i)).toBeVisible();
    await page.screenshot({ path: "screenshots/02-list-empty.png", fullPage: true });
  });

  await test.step("Create — fill form with real data", async () => {
    await page.getByRole("link", { name: /new|create|add/i }).click();
    await page.getByLabel(/name|title/i).fill("Test Item Alpha");
    await page.getByLabel(/description/i).fill("Created by automated journey test");
    await page.screenshot({ path: "screenshots/03-create-form-filled.png", fullPage: true });
    await page.getByRole("button", { name: /save|create|submit/i }).click();
    await expect(page.getByText("Test Item Alpha")).toBeVisible();
    await page.screenshot({ path: "screenshots/04-after-create.png", fullPage: true });
  });

  await test.step("List — populated with real data", async () => {
    await page.goto("/items");
    await expect(page.getByText("Test Item Alpha")).toBeVisible();
    await page.screenshot({ path: "screenshots/05-list-with-data.png", fullPage: true });
  });

  await test.step("Read — detail view", async () => {
    await page.getByText("Test Item Alpha").click();
    await expect(page.getByText("Created by automated journey test")).toBeVisible();
    await page.screenshot({ path: "screenshots/06-detail-view.png", fullPage: true });
  });

  await test.step("Update — edit form with new data", async () => {
    await page.getByRole("button", { name: /edit|update/i }).click();
    await page.getByLabel(/name|title/i).clear();
    await page.getByLabel(/name|title/i).fill("Test Item Alpha — Updated");
    await page.screenshot({ path: "screenshots/07-edit-form-filled.png", fullPage: true });
    await page.getByRole("button", { name: /save|update|submit/i }).click();
    await expect(page.getByText("Test Item Alpha — Updated")).toBeVisible();
    await page.screenshot({ path: "screenshots/08-after-update.png", fullPage: true });
  });

  await test.step("Delete — confirm and verify removal", async () => {
    await page.getByRole("button", { name: /delete|remove/i }).click();
    // Handle confirmation dialog if present
    const dialog = page.getByRole("dialog");
    if (await dialog.isVisible()) {
      await page.screenshot({ path: "screenshots/09-delete-confirm-dialog.png", fullPage: true });
      await dialog.getByRole("button", { name: /confirm|yes|delete/i }).click();
    }
    await expect(page.getByText("Test Item Alpha")).not.toBeVisible();
    await page.screenshot({ path: "screenshots/10-after-delete-list-empty.png", fullPage: true });
  });
});
```

Screenshots must cover **every distinct UI state** of the journey:
- Form (empty) → Form (filled with real data) → Success confirmation
- List (empty) → List (with data) → List (after deletion)
- Detail view → Edit view → Updated detail

### Screenshot on Failure (additionally)

### Accessibility Checks During E2E

```typescript
import AxeBuilder from "@axe-core/playwright";

test("page meets accessibility standards", async ({ page }) => {
  await page.goto("/dashboard");

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();

  expect(results.violations).toEqual([]);
});
```

## Output Format

```
## User Journey: [Journey Name]
Step 01 — Login:              ✅ [Expected result]  → screenshots/01-login-success.png
Step 02 — List empty:         ✅ [Expected result]  → screenshots/02-list-empty.png
Step 03 — Create form filled: ✅ [Expected result]  → screenshots/03-create-form-filled.png
Step 04 — After create:       ✅ [Expected result]  → screenshots/04-after-create.png
Step 05 — List with data:     ✅ [Expected result]  → screenshots/05-list-with-data.png
Step 06 — Detail view:        ✅ [Expected result]  → screenshots/06-detail-view.png
Step 07 — Edit form filled:   ✅ [Expected result]  → screenshots/07-edit-form-filled.png
Step 08 — After update:       ✅ [Expected result]  → screenshots/08-after-update.png
Step 09 — Delete confirm:     ✅ [Expected result]  → screenshots/09-delete-confirm-dialog.png
Step 10 — After delete:       ✅ [Expected result]  → screenshots/10-after-delete-list-empty.png
```

## Anti-patterns

- **NEVER** use `page.waitForTimeout()` — always wait for specific conditions
- **NEVER** use CSS selectors when role/label/text locators work
- **NEVER** write tests that depend on other tests' state
- **NEVER** hardcode URLs — use relative paths and base URL config
- **NEVER** ignore flaky tests — fix the root cause (usually missing waits)
- **NEVER** test implementation details through the UI — test user-visible behavior
- **NEVER** skip cleanup (created data should be cleaned up)
- **NEVER** write mega-tests — keep each test focused on one journey
- **NEVER** skip screenshots on CRUD journey steps — every UI state must be captured
- **NEVER** use generic screenshot names — always use sequential numbered names that describe the UI state
