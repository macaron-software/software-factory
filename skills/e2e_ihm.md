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

**ALWAYS** take a `page.screenshot()` at the end of every `test.step()`.
Screenshots document the full user journey with real data. They must be saved to `screenshots/` in the project workspace.

**The steps to capture depend entirely on the project and its features.** Before writing tests, identify:
1. What are the distinct features/screens of this app? (auth, dashboard, data views, forms, workflows…)
2. What user journeys exist? (one journey per feature, one journey per user role if multi-user)
3. What are the meaningful UI states within each journey? (initial state, form filled, after action, error state…)

**Capture every meaningful UI state transition**, not a fixed list. Examples by project type:

| Project type | Journey steps to capture |
|---|---|
| CRUD app | empty list → form filled → after create → detail → edit form → after update → after delete |
| Auth app | login form → after login → profile → change password → logout → protected redirect |
| Migration (PHP→new) | same pages as before migration, same data, same behavior — screenshot each route |
| Dashboard/analytics | empty state → with data loaded → filtered view → exported result |
| Real-time / WebSocket | before event → after event received → notification visible |
| Multi-user | admin view → user view → shared state visible in both |
| Wizard/multi-step form | each step → validation errors → summary → confirmation |

Naming convention: `NN-[feature]-[state].png` (sequential, kebab-case).

```typescript
import { test, expect } from "@playwright/test";
import * as fs from "fs";

test.beforeAll(() => fs.mkdirSync("screenshots", { recursive: true }));

// Adapt steps to THIS project's actual features and user journeys
test("[feature name] — full user journey", async ({ page }) => {
  let step = 0;
  const shot = (name: string) =>
    page.screenshot({ path: `screenshots/${String(++step).padStart(2, "0")}-${name}.png`, fullPage: true });

  await test.step("[Step name reflecting actual feature]", async () => {
    // ... interact with the app using real data (not lorem ipsum, not empty strings)
    await expect(/* relevant element */).toBeVisible();
    await shot("[feature]-[state]"); // e.g. "auth-login-success" or "invoices-list-empty"
  });

  await test.step("[Next step]", async () => {
    // ...
    await shot("[feature]-[state]");
  });

  // One test.step() + one shot() per distinct UI state in this journey
});
```

Screenshots must use **real, meaningful data** (names, emails, amounts, dates) — not `"test"`, `"foo"`, or lorem ipsum. The screenshot must be readable and demonstrate the feature works end-to-end.

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

## SF Platform — feature-e2e Phase Rules

When running as `ft-e2e-ihm` in the `feature-e2e` phase:

### STEP 1: Start the container BEFORE any test

```python
# ❌ WRONG — server not running, tests will produce failedTests=[] (false success)
playwright_test(spec="tests/e2e/smoke.spec.ts", cwd=workspace)

# ✅ CORRECT — start container, get URL, then test
deploy_result = docker_deploy(cwd=workspace, mission_id=mission_id)
# deploy_result must contain a URL like http://127.0.0.1:9100
playwright_test(spec="tests/e2e/smoke.spec.ts", cwd=workspace, base_url="http://127.0.0.1:9100")
```

### Detecting false-positives (critical)

A result `{"status": "failed", "failedTests": []}` means **ZERO tests ran** — the server wasn't reachable.  
This is **NOT a success**. Treat it as VETO and report "server not running".

```
# Real pass looks like:
{"status": "passed", "failedTests": [], "passedTests": ["test 1", "test 2"]}

# False-positive to reject:
{"status": "failed", "failedTests": []}   ← ZERO tests ran = FAIL
```

### Screenshot requirements

Every user journey **must** produce screenshots saved to `workspace/screenshots/`.  
Use `screenshot(url=<running_url>, cwd=workspace)` to capture states.  
3 minimum: initial state, mid-interaction, final state (or game-over for games).

## Output Format

```
## User Journey: [Feature Name] — [Project Name]
Container: http://127.0.0.1:9100 ✅ running
Step 01 — [feature]-[state]: ✅ [what was verified]  → screenshots/01-[feature]-[state].png
Step 02 — [feature]-[state]: ✅ [what was verified]  → screenshots/02-[feature]-[state].png
Step 03 — [feature]-[state]: ❌ FAILED [actual result]
```

## Anti-patterns

- **NEVER** run Playwright tests without starting the container first (`docker_deploy`)
- **NEVER** treat `{"status":"failed","failedTests":[]}` as success — it means zero tests ran
- **NEVER** hardcode `localhost:8080` — always use the URL returned by `docker_deploy`
- **NEVER** use `page.waitForTimeout()` — always wait for specific conditions
- **NEVER** use CSS selectors when role/label/text locators work
- **NEVER** write tests that depend on other tests' state
- **NEVER** ignore flaky tests — fix the root cause (usually missing waits)
- **NEVER** test implementation details through the UI — test user-visible behavior
- **NEVER** skip screenshots on journey steps — every UI state must be captured
- **NEVER** use generic screenshot names — always use sequential numbered names
