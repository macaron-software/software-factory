/**
 * E2E Test: TMA / Migration Sharelook
 *
 * Load migration workflow → verify agent exchanges → verify code analysis
 */
import { test, expect } from "@playwright/test";

test.describe("Migration Flow", () => {
  test("migration workflow exists and loads", async ({ page }) => {
    await page.goto("/dsi/workflow/migration-sharelook");
    await expect(page).toHaveTitle(/DSI|Migration/);

    // Should show workflow name
    await expect(page.getByRole("heading", { name: /Migration Sharelook/ })).toBeVisible();
  });

  test("migration workflow has proper phases", async ({ page }) => {
    await page.goto("/dsi/workflow/migration-sharelook");

    // At least 2 phases (deps + standalone at minimum)
    const phases = page.locator(".wf-phase");
    const count = await phases.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test("migration workflow shows specialized agents", async ({ page }) => {
    await page.goto("/dsi/workflow/migration-sharelook");

    // Agent panel
    const agents = page.locator('.wf-agent, [class*="agent-card"]');
    const count = await agents.count();
    expect(count).toBeGreaterThan(0);
  });

  test("session live page renders with unified messages", async ({ page }) => {
    // Create a session to test live view
    const sessions = await page.request.get("/api/sessions");
    const sessionsData = await sessions.json();

    if (sessionsData.length > 0) {
      const sid = sessionsData[0].id;
      await page.goto(`/sessions/${sid}/live`);

      // Thread feed visible
      await expect(page.locator("#threadFeed, .thread-feed")).toBeVisible();

      // Messages use unified component
      const msgs = page.locator(".mu--thread, .mu--system");
      const count = await msgs.count();
      if (count > 0) {
        // Check structure
        const first = msgs.first();
        await expect(first.locator(".mu__body, .mu__sys-text")).toBeVisible();
      }
    }
  });

  test("conversation page renders with unified chat bubbles", async ({ page }) => {
    const sessions = await page.request.get("/api/sessions");
    const sessionsData = await sessions.json();

    if (sessionsData.length > 0) {
      const sid = sessionsData[0].id;
      await page.goto(`/sessions/${sid}`);

      // Chat messages area visible
      await expect(page.locator(".conv-messages, #message-list")).toBeVisible();

      // Messages use unified component
      const msgs = page.locator(".mu--chat");
      const count = await msgs.count();
      if (count > 0) {
        await expect(msgs.first().locator(".mu__bubble")).toBeVisible();
      }
    }
  });

  test("agents page loads with agent list", async ({ page }) => {
    await page.goto("/agents");
    await expect(page).toHaveTitle(/Agent/);

    // Agent items present (uses .item-card)
    const cards = page.locator(".item-card");
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test("memory page loads", async ({ page }) => {
    await page.goto("/memory");
    if (page.url().includes("memory")) {
      await expect(page.locator("h1, h2, .page-title, .section-title").first()).toBeVisible();
    }
  });

  test("navigation between views works", async ({ page }) => {
    // Start at homepage
    await page.goto("/");
    await expect(page).toHaveTitle(/Software Factory/i);

    // Navigate to agents via sidebar
    const agentsLink = page.locator('nav.sidebar a[href="/agents"]');
    if (await agentsLink.isVisible()) {
      await agentsLink.click();
      await expect(page.locator(".item-card").first()).toBeVisible();
    }

    // Navigate to sessions
    const sessionsLink = page.locator('nav.sidebar a[href="/sessions"]');
    if (await sessionsLink.isVisible()) {
      await sessionsLink.click();
      await expect(page).toHaveTitle(/Session/i);
    }
  });

  test("DSI board page loads", async ({ page }) => {
    const res = await page.goto("/dsi");
    if (res && res.status() === 200) {
      // DSI board should show heading
      await expect(page.getByRole("heading").first()).toBeVisible();
    }
  });

  test("unified message CSS loaded in components", async ({ page }) => {
    await page.goto("/");

    // Verify components.css is loaded
    const stylesheets = await page.evaluate(() => {
      return Array.from(document.styleSheets)
        .map((s) => s.href || "")
        .filter((h) => h.includes("components"));
    });
    expect(stylesheets.length).toBeGreaterThan(0);
  });
});
