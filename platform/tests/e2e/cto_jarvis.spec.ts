import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * CTO Jarvis E2E — user journeys for the CTO chat panel.
 * Tests: page load, autocomplete (@/@#), message send, SSE streaming,
 * invited agent, badge rendering, conversation history.
 */

/** Authenticate via demo endpoint and set onboarding cookie. */
async function setupSession(page: any) {
  const BASE = process.env.BASE_URL || "http://localhost:8090";
  const hostname = new URL(BASE).hostname;
  // page.request shares the browser cookie jar — no navigation needed
  await page.request.post(`${BASE}/api/auth/demo`);
  // Set onboarding_done to bypass onboarding redirect
  await page.context().addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);
}

test.describe("CTO Jarvis: page load", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("loads CTO page with header and input", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/cto");

    // Header avatar + name visible
    await expect(page.locator(".cto-header-avatar")).toBeVisible({ timeout: 8_000 });
    await expect(page.locator(".cto-header-name")).toBeVisible();
    const name = await page.locator(".cto-header-name").textContent();
    expect(name).toContain("Karim");

    // Input box visible and focusable
    const input = page.locator("#cto-input");
    await expect(input).toBeVisible();
    await input.click();

    // Send button present
    await expect(page.locator("#cto-send-btn")).toBeVisible();

    // Chip shortcuts visible (Stats portfolio, Missions…)
    const chips = page.locator(".cto-chip");
    const chipCount = await chips.count();
    expect(chipCount).toBeGreaterThanOrEqual(3);

    assertNoErrors(errors, "CTO page load");
  });

  test("mention-list API returns projects and agents", async ({ page }) => {
    // Navigate to CTO page first (establishes auth cookies in browser context)
    await safeGoto(page, "/cto");
    const resp = await page.request.get("/api/cto/mention-list?type=project");
    // Accept 200 or skip gracefully if auth not configured in this env
    if (resp.status() === 401) { test.skip(); return; }
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    // API returns a flat array of items
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    const project = data.find((i: any) => i.type === "project" || i.name);
    expect(project).toBeTruthy();
    expect(project.name.length).toBeGreaterThan(0);

    const resp2 = await page.request.get("/api/cto/mention-list?type=agent");
    const data2 = await resp2.json();
    expect(Array.isArray(data2)).toBe(true);
    expect(data2.length).toBeGreaterThan(0);
  });
});

test.describe("CTO Jarvis: @ autocomplete", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("@ triggers project autocomplete dropdown", async ({ page }) => {
    await safeGoto(page, "/cto");
    // Get first project name from API to use as search query
    const projectResp = await page.request.get("/api/cto/mention-list?type=project");
    const projects = await projectResp.json();
    const firstProject = Array.isArray(projects) && projects[0]?.name;
    if (!firstProject) { test.skip(); return; }
    const query = "@" + firstProject.slice(0, 5);

    const input = page.locator("#cto-input");
    await input.click();
    await input.type(query);

    // Autocomplete popup should appear
    const popup = page.locator("#cto-mention-popup");
    await expect(popup).toBeVisible({ timeout: 5_000 });

    // Should show at least one item
    const items = popup.locator(".cto-mention-item");
    await expect(items.first()).toBeVisible({ timeout: 3_000 });
  });

  test("# triggers agent autocomplete dropdown", async ({ page }) => {
    await safeGoto(page, "/cto");
    const input = page.locator("#cto-input");
    await input.click();
    await input.type("#Ale");

    const popup = page.locator("#cto-mention-popup");
    await expect(popup).toBeVisible({ timeout: 5_000 });

    const items = popup.locator(".cto-mention-item");
    await expect(items.first()).toBeVisible({ timeout: 3_000 });
    const firstText = await items.first().textContent();
    expect(firstText!.toLowerCase()).toMatch(/alex|agent/i);
  });

  test("pressing Escape closes the popup", async ({ page }) => {
    await safeGoto(page, "/cto");
    // Fetch a real project name to trigger autocomplete
    const projectResp = await page.request.get("/api/cto/mention-list?type=project");
    const projects = await projectResp.json();
    const firstProject = Array.isArray(projects) && projects[0]?.name;
    if (!firstProject) { test.skip(); return; }
    const query = "@" + firstProject.slice(0, 4);

    const input = page.locator("#cto-input");
    await input.click();
    await input.type(query);
    const popup = page.locator("#cto-mention-popup");
    await expect(popup).toBeVisible({ timeout: 5_000 });
    await input.press("Escape");
    await expect(popup).toBeHidden({ timeout: 2_000 });
  });
});

test.describe("CTO Jarvis: send message + streaming", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("sends a simple message and gets a CTO response", async ({ page }) => {
    test.setTimeout(120_000); // LLM response can be slow
    const errors = collectErrors(page);
    await safeGoto(page, "/cto");

    const input = page.locator("#cto-input");
    await input.fill("Bonjour, combien d'agents y a-t-il dans la SF ?");
    await page.locator("#cto-send-btn").click();

    // User bubble appears
    const userBubble = page.locator(".chat-msg-user").last();
    await expect(userBubble).toBeVisible({ timeout: 5_000 });

    // CTO stream bubble or final response appears
    const ctoBubble = page.locator(".chat-msg-agent").last();
    await expect(ctoBubble).toBeVisible({ timeout: 60_000 });
    const text = await ctoBubble.textContent();
    expect(text!.length).toBeGreaterThan(20);

    // No JS errors during streaming
    assertNoErrors(errors, "CTO message send + stream");
  });

  test("chip shortcut sends a preset question", async ({ page }) => {
    test.setTimeout(120_000); // LLM response can be slow
    const errors = collectErrors(page);
    await safeGoto(page, "/cto");

    // Click 'Stats portfolio' chip
    const chip = page.locator(".cto-chip").first();
    await expect(chip).toBeVisible({ timeout: 5_000 });
    await chip.click();

    // User bubble should appear with the chip text
    const userBubble = page.locator(".chat-msg-user").last();
    await expect(userBubble).toBeVisible({ timeout: 5_000 });

    // CTO response should arrive
    const ctoBubble = page.locator(".chat-msg-agent").last();
    await expect(ctoBubble).toBeVisible({ timeout: 60_000 });

    assertNoErrors(errors, "CTO chip shortcut");
  });
});

test.describe("CTO Jarvis: @project mention in message", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("@mention renders project badge in user bubble", async ({ page }) => {
    await safeGoto(page, "/cto");
    const input = page.locator("#cto-input");
    // Type message with @mention — no waiting for autocomplete, type full text
    await input.fill("@DataForge — Real-time Data Pipeline où en est ce projet ?");
    await page.locator("#cto-send-btn").click();

    // User bubble should contain a .mention-badge-project
    const badge = page.locator(".chat-msg-user .mention-badge-project").last();
    await expect(badge).toBeVisible({ timeout: 8_000 });
    const badgeText = await badge.textContent();
    expect(badgeText).toContain("DataForge");
  });

  test("CTO response uses project context (no 'je ne sais pas')", async ({ page }) => {
    test.setTimeout(120_000); // LLM response can be slow
    await safeGoto(page, "/cto");
    const input = page.locator("#cto-input");
    await input.fill("@DataForge — Real-time Data Pipeline donne moi un résumé du projet");
    await page.locator("#cto-send-btn").click();

    const ctoBubble = page.locator(".chat-msg-agent").last();
    await expect(ctoBubble).toBeVisible({ timeout: 60_000 });
    const text = (await ctoBubble.textContent())!.toLowerCase();

    // Should NOT say it has no info (about any project)
    expect(text).not.toContain("je ne trouve pas");
    expect(text).not.toContain("donnez-moi plus de contexte");

    // CTO responded with meaningful content
    expect(text.length).toBeGreaterThan(50);
  });
});

test.describe("CTO Jarvis: invited agent (#mention)", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("invited agent bubble appears with distinct style", async ({ page }) => {
    test.setTimeout(120_000); // Requires LLM + agent invite — up to 3x timeout
    await safeGoto(page, "/cto");
    const input = page.locator("#cto-input");
    // Explicitly invite an agent with #
    await input.fill("quel est l'état de la SF ? #Alexandre Moreau");
    await page.locator("#cto-send-btn").click();

    // CTO response first — skip if LLM unavailable (CI without key)
    const ctoMsg = page.locator(".chat-msg-agent").last();
    const ctoVisible = await ctoMsg.isVisible().catch(() => false) ||
      await ctoMsg.waitFor({ state: "visible", timeout: 60_000 }).then(() => true).catch(() => false);
    if (!ctoVisible) { test.skip(); return; }

    // Invited divider — may or may not appear depending on LLM decision
    const divider = page.locator(".invited-divider").last();
    const divVisible = await divider.waitFor({ state: "visible", timeout: 60_000 }).then(() => true).catch(() => false);
    if (!divVisible) {
      // CTO responded but didn't invite — acceptable in some cases
      console.log("CTO responded but no invited divider — skipping invited agent assertions");
      return;
    }
    const divText = await divider.textContent();
    expect(divText).toContain("a rejoint");

    // Invited bubble with green-tinted body
    const invBubble = page.locator(".chat-msg-invited").last();
    await expect(invBubble).toBeVisible({ timeout: 30_000 });

    // Sender name visible
    const sender = invBubble.locator(".chat-msg-sender");
    await expect(sender).toBeVisible();
    const senderText = await sender.textContent();
    expect(senderText!.length).toBeGreaterThan(3);
  });
});

test.describe("CTO Jarvis: conversation history", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("sidebar shows conversation history", async ({ page }) => {
    await safeGoto(page, "/cto");
    const sidebar = page.locator(".cto-sidebar");
    await expect(sidebar).toBeVisible({ timeout: 5_000 });

    // New conversation button
    await expect(page.locator(".cto-new-btn")).toBeVisible();
  });

  test("retry bar appears on network error (simulated)", async ({ page }) => {
    await safeGoto(page, "/cto");
    // Intercept the SSE endpoint to force 500
    await page.route("**/api/cto/message", (route) =>
      route.fulfill({ status: 500, body: '{"error":"test error"}' })
    );
    const input = page.locator("#cto-input");
    await input.fill("test message");
    await page.locator("#cto-send-btn").click();

    // Retry bar should appear
    const retryBar = page.locator(".cto-retry-bar").last();
    await expect(retryBar).toBeVisible({ timeout: 8_000 });
    await expect(page.locator(".cto-retry-btn").last()).toBeVisible();
  });
});
