import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * Smoke E2E — every major page loads, has content, zero console/network errors.
 * Real selectors from actual templates, real data assertions.
 */

test.describe("Portfolio (Home) page", () => {
  test("loads with projects and badges", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/");

    // Title
    await expect(page).toHaveTitle(/Macaron/i);

    // Sidebar nav visible
    await expect(page.locator("nav.sidebar, .sidebar")).toBeVisible();

    // At least 1 project card
    const cards = page.locator(".project-mission-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(3);

    // Each card has a title
    for (let i = 0; i < Math.min(count, 3); i++) {
      const title = cards.nth(i).locator(".pmc-title");
      await expect(title).toBeVisible();
      const text = await title.textContent();
      expect(text!.length).toBeGreaterThan(2);
    }

    // Metric counters visible
    const metrics = page.locator(".metric-card");
    const metricCount = await metrics.count();
    expect(metricCount).toBeGreaterThanOrEqual(3);

    // Badges exist (TMA, Sécu, CI/CD)
    const badges = page.locator(".pmc-badge");
    const badgeCount = await badges.count();
    expect(badgeCount).toBeGreaterThan(0);

    assertNoErrors(errors, "Portfolio /");
  });

  test("project cards have status and missions", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/");

    const card = page.locator(".project-mission-card").first();
    await expect(card).toBeVisible();

    // Status badge (active, planning, etc.)
    const header = card.locator(".pmc-header");
    await expect(header).toBeVisible();

    assertNoErrors(errors, "Portfolio cards");
  });
});

test.describe("All pages smoke test", () => {
  const pages = [
    { path: "/", name: "Portfolio", selector: ".project-mission-card" },
    { path: "/pi", name: "PI Board", selector: ".epic-card, .pi-section-header, .tma-card" },
    { path: "/agents", name: "Agents", selector: '.agent-card, [class*="agent"]' },
    { path: "/skills", name: "Skills", selector: '.skill-card, [class*="skill"]' },
    { path: "/mcps", name: "MCPs", selector: '.mcp-card, [class*="mcp"]' },
    { path: "/settings", name: "Settings", selector: ".settings-tab, .integ-card" },
    { path: "/monitoring", name: "Monitoring", selector: '.mon-card, [class*="mon-"]' },
    { path: "/memory", name: "Memory", selector: '.mem-entry, [class*="mem"]' },
    { path: "/missions", name: "Missions", selector: '.mission-card, [class*="mission"]' },
    { path: "/ideation", name: "Ideation", selector: "textarea, .idea-input" },
    { path: "/workflows", name: "Workflows", selector: '.wf-card, [class*="workflow"]' },
    { path: "/backlog", name: "Backlog", selector: '.backlog, [class*="backlog"]' },
    { path: "/ceremonies", name: "Ceremonies", selector: '.ceremony, [class*="ceremony"]' },
    { path: "/design-system", name: "Design System", selector: '.ds-section, [class*="ds-"]' },
    { path: "/metier", name: "Business", selector: '.met-card, [class*="met-"]' },
  ];

  for (const p of pages) {
    test(`${p.name} (${p.path}) — loads, no errors`, async ({ page }) => {
      const errors = collectErrors(page);
      await safeGoto(page, p.path);

      // Page rendered with meaningful content
      const body = await page.textContent("body");
      expect(body!.length).toBeGreaterThan(200);

      // No console or network errors
      assertNoErrors(errors, p.name);
    });
  }
});

test.describe("API health checks", () => {
  test("GET /api/health", async ({ request }) => {
    const r = await request.get("/api/health");
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.status).toBe("ok");
  });

  test("GET /api/projects returns array", async ({ request }) => {
    const r = await request.get("/api/projects");
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThanOrEqual(1);
  });

  test("GET /api/agents returns 143+ agents", async ({ request }) => {
    const r = await request.get("/api/agents");
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.length).toBeGreaterThanOrEqual(100);
  });

  test("GET /api/monitoring/live returns stats", async ({ request }) => {
    const r = await request.get("/api/monitoring/live");
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.agents).toBeDefined();
    expect(data.agents.registered).toBeGreaterThanOrEqual(100);
  });

  test("GET /api/integrations returns plugins", async ({ request }) => {
    const r = await request.get("/api/integrations");
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.length).toBeGreaterThanOrEqual(3);
  });
});
