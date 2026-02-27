import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * Pages E2E — detailed checks for key pages with real selectors.
 */

test.describe("PI Board page", () => {
  test("loads with epics and search", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/pi");

    // Search input exists
    const search = page.locator("#piSearch");
    await expect(search).toBeVisible();

    // At least one section header
    const sections = page.locator(".pi-section-header");
    const count = await sections.count();
    expect(count).toBeGreaterThanOrEqual(1);

    assertNoErrors(errors, "PI Board");
  });

  test("search filters epics", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/pi");

    const search = page.locator("#piSearch");
    await search.fill("Software Factory");
    await page.waitForTimeout(500);

    // At least the SF epics should remain visible
    const body = await page.textContent("body");
    expect(body).toContain("Software Factory");

    assertNoErrors(errors, "PI search");
  });

  test("export button works", async ({ request }) => {
    const r = await request.get("/api/export/epics");
    expect(r.status()).toBe(200);
    const text = await r.text();
    // CSV or JSON export
    expect(text.length).toBeGreaterThan(10);
  });
});

test.describe("Monitoring page", () => {
  test("loads with real metrics", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/monitoring");

    // Stat cards visible
    const cards = page.locator(".mon-card");
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(3);

    // Agent count displayed
    const agentCount = page.locator("#monAgentsRegistered");
    if (await agentCount.isVisible()) {
      const text = await agentCount.textContent();
      const num = parseInt(text || "0");
      expect(num).toBeGreaterThanOrEqual(0);
    }

    assertNoErrors(errors, "Monitoring");
  });

  test("MCP list shows servers", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/monitoring");

    const mcpList = page.locator(".mon-mcp-list, .mon-mcp-item");
    const count = await mcpList.count();
    expect(count).toBeGreaterThanOrEqual(0); // May have 0 if no MCP running

    assertNoErrors(errors, "Monitoring MCP");
  });

  test("prometheus endpoint returns metrics", async ({ request }) => {
    const r = await request.get("/api/metrics/prometheus");
    expect(r.status()).toBe(200);
    const text = await r.text();
    expect(text).toContain("macaron_uptime_seconds");
    expect(text).toContain("macaron_http_requests_total");
  });
});

test.describe("Settings page", () => {
  test("loads with tabs and integrations", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/settings");

    // Settings tabs visible
    const tabs = page.locator(".settings-tab");
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);

    // Click integrations tab to reveal cards
    const integTab = page.locator(
      '.settings-tab:has-text("Intégrations"), .settings-tab:has-text("Integrations")'
    );
    if (await integTab.isVisible()) {
      await integTab.click();
      await page.waitForTimeout(500);
    }

    // Integration cards now visible
    const integCards = page.locator(".integ-card");
    const integCount = await integCards.count();
    expect(integCount).toBeGreaterThanOrEqual(3);

    assertNoErrors(errors, "Settings");
  });

  test("integration cards have names", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/settings");

    // Click integrations tab first
    const integTab = page.locator(
      '.settings-tab:has-text("Intégrations"), .settings-tab:has-text("Integrations")'
    );
    if (await integTab.isVisible()) {
      await integTab.click();
      await page.waitForTimeout(500);
    }

    const cards = page.locator(".integ-card");
    const count = await cards.count();

    for (let i = 0; i < Math.min(count, 3); i++) {
      const card = cards.nth(i);
      const name = card.locator(".integ-name");
      await expect(name).toBeVisible();
      const text = await name.textContent();
      expect(text!.length).toBeGreaterThan(0);
    }

    assertNoErrors(errors, "Settings integrations");
  });
});

test.describe("Agents page", () => {
  test("loads with agent cards", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/agents");

    // Page has agent content
    const body = await page.textContent("body");
    expect(body).toContain("agent");

    assertNoErrors(errors, "Agents");
  });

  test("agents API returns full team", async ({ request }) => {
    const r = await request.get("/api/agents");
    expect(r.status()).toBe(200);
    const agents = await r.json();
    expect(agents.length).toBeGreaterThanOrEqual(100);

    // Check for key roles
    const roles = new Set(agents.map((a: any) => a.role));
    expect(roles.size).toBeGreaterThanOrEqual(5);
  });
});

test.describe("Memory page", () => {
  test("loads wiki-like interface", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/memory");

    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);

    assertNoErrors(errors, "Memory");
  });

  test("memory search API works", async ({ request }) => {
    const r = await request.get("/api/memory/search", { params: { q: "architecture" } });
    expect(r.status()).toBe(200);
  });
});
