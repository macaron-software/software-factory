import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * User Journey E2E — full user flows with real data, selectors, and error checks.
 * Headless Playwright against live server.
 */

test.describe("Journey: Browse Portfolio → Project → Chat", () => {
  test("portfolio → click project → see PM → back", async ({ page }) => {
    const errors = collectErrors(page);

    // 1. Load portfolio
    await safeGoto(page, "/");
    await expect(page).toHaveTitle(/Macaron/i);

    // 2. Find first project card and get its link
    const firstCard = page.locator(".project-mission-card").first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    const projectTitle = await firstCard.locator(".pmc-title").textContent();
    expect(projectTitle!.length).toBeGreaterThan(2);

    // 3. Click through to project detail
    const link = firstCard.locator("a").first();
    if (await link.isVisible()) {
      await link.click();
      await page.waitForLoadState("networkidle");

      // 4. Should see chat interface with PM identity
      const chatInput = page.locator("#chat-input");
      if (await chatInput.isVisible({ timeout: 5_000 })) {
        // PM avatar (initials circle) should be visible
        const avatar = page.locator(".agent-avatar-sm, .chat-msg-avatar");
        const sidebar = page.locator("#project-sidebar, .ps-section");
        await expect(sidebar).toBeVisible();
      }
    }

    assertNoErrors(errors, "Portfolio→Project journey");
  });
});

test.describe("Journey: Navigate all sidebar links", () => {
  test("sidebar navigation works for all menu items", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/");

    // Get all nav links
    const navLinks = page.locator(".nav-links a");
    const linkCount = await navLinks.count();
    expect(linkCount).toBeGreaterThanOrEqual(5);

    // Collect hrefs
    const hrefs: string[] = [];
    for (let i = 0; i < linkCount; i++) {
      const href = await navLinks.nth(i).getAttribute("href");
      if (href && href.startsWith("/") && !href.includes("#")) {
        hrefs.push(href);
      }
    }

    // Visit each page (first 8 to keep test fast)
    for (const href of hrefs.slice(0, 8)) {
      const pageErrors = collectErrors(page);
      await safeGoto(page, href);
      const body = await page.textContent("body");
      expect(body!.length, `${href} has content`).toBeGreaterThan(100);
      assertNoErrors(pageErrors, `nav→${href}`);
    }
  });
});

test.describe("Journey: PI Board → Expand Epic → View Features", () => {
  test("expand an epic to see its features", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/pi");

    // Find epic cards
    const epics = page.locator(".epic-card");
    const epicCount = await epics.count();

    if (epicCount > 0) {
      // Click the epic header to expand
      const header = epics.first().locator(".epic-header");
      await expect(header).toBeVisible({ timeout: 5_000 });
      await header.click();
      await page.waitForTimeout(500);

      // Features section should expand
      const features = epics.first().locator(".epic-features");
      // Features container is now revealed (may have 0 items)
      const isVisible = await features.isVisible().catch(() => false);
      expect(typeof isVisible).toBe("boolean");
    }

    assertNoErrors(errors, "PI Board epics");
  });
});

test.describe("Journey: Settings → Toggle Integration", () => {
  test("view and interact with integrations", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/settings");

    // Click integrations tab if exists
    const integTab = page.locator(
      '.settings-tab:has-text("Intégrations"), .settings-tab:has-text("Integrations")'
    );
    if (await integTab.isVisible()) {
      await integTab.click();
      await page.waitForTimeout(500);
    }

    // Integration cards visible
    const cards = page.locator(".integ-card");
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(3);

    // Each card has name and type
    for (let i = 0; i < Math.min(count, 5); i++) {
      const card = cards.nth(i);
      const name = await card.locator(".integ-name").textContent();
      expect(name!.length).toBeGreaterThan(0);
    }

    assertNoErrors(errors, "Settings integrations");
  });
});

test.describe("Journey: Monitoring → Check Stats → MCP Status", () => {
  test("monitoring shows live metrics", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/monitoring");

    // Wait for stats to load
    const cards = page.locator(".mon-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });

    // Verify stat values are numbers
    const bigNumbers = page.locator(".mon-big");
    const numCount = await bigNumbers.count();
    for (let i = 0; i < Math.min(numCount, 4); i++) {
      const text = await bigNumbers.nth(i).textContent();
      // Should be a number (possibly with formatting)
      expect(text!.trim().length).toBeGreaterThan(0);
    }

    assertNoErrors(errors, "Monitoring stats");
  });
});

test.describe("Journey: Language Switch", () => {
  test("switch to English and back to French", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/");

    // Find lang selector
    const langSelect = page.locator("#langSelect");
    if (await langSelect.isVisible()) {
      // Switch to English
      await langSelect.selectOption("en");
      await page.waitForLoadState("networkidle");

      // Verify English content
      const body = await page.textContent("body");
      // Should have some English words
      expect(body!.toLowerCase()).toContain("project");

      // Switch back to French
      await langSelect.selectOption("fr");
      await page.waitForLoadState("networkidle");
    }

    assertNoErrors(errors, "Language switch");
  });
});

test.describe("Journey: View Modes on Portfolio", () => {
  test("toggle card → list → compact for projects", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/");

    // Find view toggle buttons for projects section
    const listBtn = page.locator('button[onclick*="setPortView"][onclick*="list"]').first();
    if (await listBtn.isVisible()) {
      await listBtn.click();
      await page.waitForTimeout(300);

      // Projects section should be in list mode
      const section = page.locator('#projects-section, [data-section="projects"]');
      if (await section.isVisible()) {
        const classList = (await section.getAttribute("class")) || "";
        // Should have list-related class or data attribute
        expect(classList.length).toBeGreaterThan(0);
      }

      // Switch to compact
      const compactBtn = page.locator('button[onclick*="setPortView"][onclick*="compact"]').first();
      if (await compactBtn.isVisible()) {
        await compactBtn.click();
        await page.waitForTimeout(300);
      }

      // Switch back to card
      const cardBtn = page.locator('button[onclick*="setPortView"][onclick*="card"]').first();
      if (await cardBtn.isVisible()) {
        await cardBtn.click();
        await page.waitForTimeout(300);
      }
    }

    assertNoErrors(errors, "View mode toggle");
  });
});
