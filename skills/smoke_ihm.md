---
name: smoke-testing
description: >
  Guides the agent through quick post-deploy smoke testing to verify pages load correctly.
  Use this skill after deployments or when doing a quick health check on web pages.
  Checks HTTP status, visible content, console errors, network errors, and basic
  responsive layout.
metadata:
  category: testing
  triggers:
    - "when user asks to verify pages load correctly"
    - "when doing post-deployment verification"
    - "when user wants a quick health check on the app"
    - "when checking for console or network errors on pages"
---

# Smoke Testing

This skill enables the agent to perform quick post-deploy health checks on web pages.
Smoke tests verify that pages load, return HTTP 200, display expected content, and
have no console or network errors.

## Use this skill when

- After deploying to staging or production
- Quick verification that all pages are accessible
- Checking for broken pages after a dependency update
- Verifying no console errors appear on key pages
- Basic responsive layout check

## Do not use this skill when

- Testing user interactions or workflows (use e2e-browser-testing)
- Testing API endpoints (use e2e-api-testing)
- Doing deep accessibility audits (use accessibility-audit)

## Instructions

### Basic Page Health Check

```typescript
import { test, expect, Page } from "@playwright/test";

const PAGES = [
  { path: "/", title: "Home", expectedText: "Welcome" },
  { path: "/login", title: "Login", expectedText: "Sign in" },
  { path: "/dashboard", title: "Dashboard", expectedText: "Overview" },
  { path: "/settings", title: "Settings", expectedText: "Preferences" },
];

for (const { path, title, expectedText } of PAGES) {
  test(`Smoke: ${title} page loads correctly`, async ({ page }) => {
    const errors: string[] = [];
    const networkFailures: string[] = [];

    // Capture console errors
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    // Capture network failures
    page.on("requestfailed", (request) => {
      networkFailures.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`);
    });

    // Navigate and check HTTP status
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);

    // Check expected content is visible
    await expect(page.getByText(expectedText)).toBeVisible({ timeout: 5000 });

    // Assert no console errors
    expect(errors).toHaveLength(0);

    // Assert no network failures
    expect(networkFailures).toHaveLength(0);
  });
}
```

### Responsive Smoke Check

```typescript
const VIEWPORTS = [
  { name: "mobile", width: 375, height: 667 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

for (const viewport of VIEWPORTS) {
  test(`Smoke: Home page renders on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    const response = await page.goto("/");

    expect(response?.status()).toBe(200);
    await expect(page.locator("body")).toBeVisible();

    // Check no horizontal overflow
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(viewport.width + 1);
  });
}
```

### Quick Auth Smoke Check

```typescript
test("Smoke: Protected pages redirect to login", async ({ page }) => {
  const protectedPages = ["/dashboard", "/settings", "/profile"];

  for (const path of protectedPages) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login/);
  }
});

test("Smoke: Login works with valid credentials", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("smoke@test.com");
  await page.getByLabel("Password").fill("smoketest123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/dashboard");
});
```

### Performance Smoke Check

```typescript
test("Smoke: Pages load within acceptable time", async ({ page }) => {
  const start = Date.now();
  await page.goto("/");
  const loadTime = Date.now() - start;

  expect(loadTime).toBeLessThan(3000); // 3 second max
});
```

### CI Integration

```yaml
# In CI pipeline, run smoke tests after deploy:
# npx playwright test --grep @smoke --reporter=list
```

Tag smoke tests with:

```typescript
test("@smoke Home page loads", async ({ page }) => {
  /* ... */
});
```

## Output Format

```
## Smoke Test Report — [Environment]
| Page | Status | Content | Console Errors | Network Errors | Load Time |
|------|--------|---------|----------------|----------------|-----------|
| /    | 200 ✅ | ✅      | 0 ✅           | 0 ✅           | 1.2s ✅   |
| /login | 200 ✅ | ✅    | 0 ✅           | 0 ✅           | 0.8s ✅   |
| /dashboard | 200 ✅ | ✅ | 1 ❌          | 0 ✅           | 2.1s ✅   |
```

## Anti-patterns

- **NEVER** use smoke tests for deep functionality testing — they check health, not features
- **NEVER** skip console error capture — hidden errors indicate real problems
- **NEVER** ignore network failures — failed API calls break the user experience
- **NEVER** hardcode viewport sizes differently each time — use a consistent set
- **NEVER** make smoke tests dependent on specific data — they should work on any environment
- **NEVER** include slow operations in smoke tests — they must run fast (< 30s total)
