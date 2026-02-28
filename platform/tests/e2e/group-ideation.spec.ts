/**
 * E2E Tests: Group Ideation Tabs
 *
 * Tests the 5 home tabs: Knowledge, Architecture, Security, Data & AI, PI Planning
 * - Tab navigation (no 404)
 * - UI loads correctly (layout, agents graph, input bar)
 * - Session creation (POST /api/group/{id})
 * - SSE connection (/api/sessions/{id}/sse)
 * - Message appears in chat
 */
import { test, expect, type Page } from "@playwright/test";

const GROUP_TABS = [
  { id: "knowledge", label: "Knowledge", tabText: /knowledge/i },
  { id: "archi", label: "Architecture", tabText: /architecture/i },
  { id: "security", label: "Sécurité", tabText: /s.curit/i },
  { id: "data-ai", label: "Data & IA", tabText: /data/i },
  { id: "pi-planning", label: "PI Planning", tabText: /pi planning/i },
];

test.describe("Group Ideation Tabs", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for home page to load
    await expect(page.locator(".home-tabs")).toBeVisible({ timeout: 15_000 });
  });

  // ── Tab navigation ──────────────────────────────────────────────────────────

  for (const tab of GROUP_TABS) {
    test(`tab ${tab.label} loads without 404`, async ({ page }) => {
      // Monitor for 404 responses
      const failed: string[] = [];
      page.on("response", (resp) => {
        if (resp.status() === 404) failed.push(resp.url());
      });

      // Click the tab button
      const tabBtn = page
        .locator(".home-tab")
        .filter({ hasText: tab.tabText })
        .first();
      await expect(tabBtn).toBeVisible({ timeout: 10_000 });
      await tabBtn.click();

      // Content should load in #home-tab-content
      await page.waitForTimeout(2_000);
      const content = page.locator("#home-tab-content");
      await expect(content).toBeVisible();

      // No 404 on the group route
      const groupFailed = failed.filter(
        (u) => u.includes(`/group/${tab.id}`) || u.includes("/api/group/")
      );
      expect(groupFailed, `404s for ${tab.label}: ${groupFailed.join(", ")}`).toHaveLength(0);
    });
  }

  // ── UI layout ───────────────────────────────────────────────────────────────

  test("knowledge tab renders full layout", async ({ page }) => {
    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");

    // mkt-layout with chat + panel
    await expect(content.locator(".mkt-layout")).toBeVisible({ timeout: 10_000 });
    await expect(content.locator(".mkt-chat")).toBeVisible();
    await expect(content.locator(".mkt-panel")).toBeVisible();

    // Input bar
    await expect(content.locator("#grpInput")).toBeVisible();
    await expect(content.locator("#grpSend")).toBeVisible();

    // Agent graph area
    await expect(content.locator(".idea-graph")).toBeVisible();
    await expect(content.locator("#grpGraphSvg")).toBeVisible();

    // Empty state visible (no messages yet)
    await expect(content.locator("#grpPlaceholder")).toBeVisible();
  });

  test("SVG icons are properly sized (no flash size > 100px)", async ({ page }) => {
    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    await page.waitForTimeout(500);
    const content = page.locator("#home-tab-content");

    // The empty state SVG should be 52x52 per CSS
    const emptyIcon = content.locator(".mkt-empty svg").first();
    if (await emptyIcon.isVisible()) {
      const box = await emptyIcon.boundingBox();
      if (box) {
        expect(box.width, "empty state SVG width should be ~52px").toBeLessThan(100);
        expect(box.height, "empty state SVG height should be ~52px").toBeLessThan(100);
      }
    }
  });

  // ── Session creation ─────────────────────────────────────────────────────────

  test("knowledge tab: submit message creates session", async ({ page }) => {
    // Intercept the POST to /api/group/knowledge
    const sessionPromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/group/knowledge") && resp.request().method() === "POST",
      { timeout: 15_000 }
    );

    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");
    await expect(content.locator("#grpInput")).toBeVisible({ timeout: 10_000 });

    // Type a message
    await content.locator("#grpInput").fill("Quels sont les patterns de base de connaissances disponibles ?");
    await content.locator("#grpSend").click();

    // POST should succeed (not 404)
    const resp = await sessionPromise;
    expect(resp.status(), "POST /api/group/knowledge should not be 404").not.toBe(404);
    expect(resp.status(), "POST /api/group/knowledge should succeed").toBeLessThan(500);

    // Response should contain session_id
    const body = await resp.json().catch(() => null);
    expect(body).toBeTruthy();
    expect(body?.session_id, "Response should have session_id").toBeTruthy();
    expect(body?.sse_url, "Response should have sse_url").toMatch(/\/api\/sessions\/.*\/sse/);
  });

  test("knowledge tab: SSE endpoint responds after session creation", async ({ page }) => {
    // Intercept SSE connection
    const ssePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/sessions/") &&
        resp.url().includes("/sse") &&
        resp.status() !== 404,
      { timeout: 20_000 }
    );

    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");
    await expect(content.locator("#grpInput")).toBeVisible({ timeout: 10_000 });

    await content.locator("#grpInput").fill("Test de connexion SSE");
    await content.locator("#grpSend").click();

    // SSE should connect (status 200, not 404)
    const sseResp = await ssePromise;
    expect(sseResp.status(), "SSE /api/sessions/{id}/sse must not be 404").toBe(200);
  });

  test("knowledge tab: user message appears in chat after send", async ({ page }) => {
    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");
    await expect(content.locator("#grpInput")).toBeVisible({ timeout: 10_000 });

    const testMsg = "Question de test sur la base de connaissances";
    await content.locator("#grpInput").fill(testMsg);
    await content.locator("#grpSend").click();

    // Placeholder should disappear
    await expect(content.locator("#grpPlaceholder")).not.toBeVisible({ timeout: 10_000 });

    // User message should appear
    await expect(content.locator("#grpMessages .mu--chat").first()).toBeVisible({
      timeout: 10_000,
    });

    // Input should be cleared
    await expect(content.locator("#grpInput")).toHaveValue("");
  });

  // ── Tab switching ────────────────────────────────────────────────────────────

  test("switching between group tabs works without errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("response", (resp) => {
      if (resp.status() >= 400) errors.push(`${resp.status()} ${resp.url()}`);
    });

    const tabs = ["knowledge", "archi", "security", "data-ai"];
    for (const tabId of tabs) {
      // Navigate via URL to avoid timing issues
      await page.goto(`/?tab=${tabId}`);
      await page.waitForTimeout(1_500);

      const content = page.locator("#home-tab-content");
      await expect(content.locator(".mkt-layout")).toBeVisible({ timeout: 15_000 });
    }

    const criticalErrors = errors.filter(
      (e) => e.includes("/group/") || e.includes("/api/group/")
    );
    expect(criticalErrors, `Critical errors during tab switching: ${criticalErrors.join(", ")}`).toHaveLength(0);
  });

  // ── History ──────────────────────────────────────────────────────────────────

  test("knowledge tab: history button shows past sessions", async ({ page }) => {
    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");
    await expect(content.locator(".mkt-history-btn")).toBeVisible({ timeout: 10_000 });

    await content.locator(".mkt-history-btn").click();
    await expect(content.locator(".mkt-sidebar")).toBeVisible({ timeout: 5_000 });

    // Close sidebar
    const closeBtn = content.locator(".mkt-sidebar-close");
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    }
  });

  // ── Agent graph ──────────────────────────────────────────────────────────────

  test("agent graph renders nodes for knowledge group", async ({ page }) => {
    const tabBtn = page.locator(".home-tab").filter({ hasText: /knowledge/i }).first();
    await tabBtn.click();

    const content = page.locator("#home-tab-content");
    await page.waitForTimeout(1_000); // let JS render graph

    // SVG should have rendered nodes (g elements in #grpNodes)
    const nodes = content.locator("#grpNodes g");
    const count = await nodes.count();
    expect(count, "Agent graph should have at least 1 node").toBeGreaterThanOrEqual(1);
  });
});
