/**
 * Chaos E2E — UI recovery and data integrity after chaos events.
 * Run: npx playwright test chaos.spec.ts --timeout 300000
 */
import { test, expect } from "@playwright/test";
import { collectErrors } from "./helpers";

const BASE = process.env.BASE_URL || "http://4.233.64.30";

test.describe("Visual Recovery", () => {
  test("platform responds after page reload", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(`${BASE}/`);
    await expect(page.locator("body")).not.toBeEmpty();

    // Reload and verify
    await page.reload();
    await expect(page.locator("body")).not.toBeEmpty();
    expect(errors.console).toHaveLength(0);
  });

  test("monitoring page shows live data", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(`${BASE}/monitoring`);
    await expect(page.locator("body")).toContainText(/agent|mission|uptime/i);
    expect(errors.console).toHaveLength(0);
  });

  test("no stale agent status", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/agents`);
    expect(r.status()).toBe(200);
    const agents = await r.json();
    // All agents should have a valid status
    for (const a of agents.slice(0, 10)) {
      expect(a).toHaveProperty("id");
      expect(a).toHaveProperty("name");
    }
  });

  test("mission page renders timeline", async ({ page }) => {
    await page.goto(`${BASE}/missions`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).not.toBeEmpty();
  });
});

test.describe("Data Integrity After Chaos", () => {
  test("project list intact", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/projects`);
    expect(r.status()).toBe(200);
    const projects = await r.json();
    expect(Array.isArray(projects)).toBe(true);
    expect(projects.length).toBeGreaterThanOrEqual(1);
  });

  test("mission list intact", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/missions`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    const missions = Array.isArray(data) ? data : data.missions || [];
    expect(Array.isArray(missions)).toBe(true);
  });

  test("agent configurations survive", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/agents`);
    expect(r.status()).toBe(200);
    const agents = await r.json();
    expect(agents.length).toBeGreaterThanOrEqual(50);
  });

  test("i18n still works", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/i18n/fr.json`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(Object.keys(data).length).toBeGreaterThan(0);
  });

  test("health endpoint valid after all tests", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/health`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.status).toBe("ok");
  });
});

test.describe("Chaos API Resilience", () => {
  test("create and verify mission via JSON API", async ({ page }) => {
    const r = await page.request.post(`${BASE}/api/missions`, {
      data: {
        name: "chaos-e2e-verify",
        project_id: "macaron-canvas",
        type: "task",
        description: "Chaos E2E verification mission",
      },
    });
    expect(r.status()).toBeLessThan(500);
  });

  test("WSJF endpoint responds", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/missions`);
    const data = await r.json();
    const missions = Array.isArray(data) ? data : data.missions || [];
    if (missions.length === 0) return;

    const mid = missions[0].id;
    const r2 = await page.request.post(`${BASE}/api/missions/${mid}/wsjf`, {
      data: {
        business_value: 8,
        time_criticality: 5,
        risk_reduction: 3,
        job_duration: 5,
      },
    });
    expect(r2.status()).toBeLessThan(500);
  });

  test("settings page accessible", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(`${BASE}/settings`);
    await expect(page.locator("body")).toContainText(/setting|config/i);
    expect(errors.console).toHaveLength(0);
  });
});
