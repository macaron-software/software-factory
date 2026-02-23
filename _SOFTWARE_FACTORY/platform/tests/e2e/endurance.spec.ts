/**
 * Endurance E2E — UI monitoring during long-running missions.
 * Run: npx playwright test endurance.spec.ts --timeout 300000
 */
import { test, expect, type Page } from "@playwright/test";
import { collectErrors } from "./helpers";

const BASE = process.env.BASE_URL || "http://4.233.64.30";

test.describe("Endurance Dashboard", () => {
  test("monitoring shows active agents", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(`${BASE}/monitoring`);
    await expect(page.locator("body")).toContainText(/agent/i);
    // Should show agent count
    const text = await page.textContent("body");
    expect(text).toBeTruthy();
    expect(errors.console).toHaveLength(0);
  });

  test("missions page loads and lists missions", async ({ page }) => {
    await page.goto(`${BASE}/missions`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("LLM stats accessible from monitoring", async ({ page }) => {
    await page.goto(`${BASE}/monitoring`);
    // Check LLM section exists or API returns data
    const r = await page.request.get(`${BASE}/api/llm/stats`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data).toBeTruthy();
  });

  test("project board shows canvas project", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto(`${BASE}/projects`);
    await expect(page.locator("body")).toContainText(/project/i);
    expect(errors.console).toHaveLength(0);
  });
});

test.describe("Endurance Health", () => {
  test("all main pages load with 200", async ({ page }) => {
    const pages = ["/", "/projects", "/missions", "/agents", "/monitoring", "/settings", "/metier"];
    for (const p of pages) {
      const r = await page.request.get(`${BASE}${p}`);
      expect(r.status(), `${p} should return 200`).toBe(200);
    }
  });

  test("API endpoints respond within 3s", async ({ page }) => {
    const endpoints = ["/api/health", "/api/projects", "/api/missions", "/api/agents"];
    for (const ep of endpoints) {
      const start = Date.now();
      const r = await page.request.get(`${BASE}${ep}`);
      const elapsed = Date.now() - start;
      expect(r.status(), `${ep}`).toBe(200);
      expect(elapsed, `${ep} should respond < 3s`).toBeLessThan(3000);
    }
  });

  test("health endpoint returns valid JSON", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/health`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.status).toBe("ok");
  });

  test("Prometheus metrics available", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/metrics/prometheus`);
    expect(r.status()).toBe(200);
    const text = await r.text();
    expect(text).toContain("macaron_uptime_seconds");
  });
});

test.describe("Endurance Data Integrity", () => {
  test("projects API returns array with fields", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/projects`);
    expect(r.status()).toBe(200);
    const projects = await r.json();
    expect(Array.isArray(projects)).toBe(true);
    if (projects.length > 0) {
      expect(projects[0]).toHaveProperty("id");
      expect(projects[0]).toHaveProperty("name");
    }
  });

  test("missions API returns data with fields", async ({ page }) => {
    const r = await page.request.get(`${BASE}/api/missions`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    const missions = Array.isArray(data) ? data : data.missions || [];
    expect(Array.isArray(missions)).toBe(true);
    if (missions.length > 0) {
      expect(missions[0]).toHaveProperty("id");
      expect(missions[0]).toHaveProperty("name");
    }
  });

  test("agents count is consistent", async ({ page }) => {
    const r1 = await page.request.get(`${BASE}/api/agents`);
    const agents1 = await r1.json();
    // Wait and recheck
    await page.waitForTimeout(2000);
    const r2 = await page.request.get(`${BASE}/api/agents`);
    const agents2 = await r2.json();
    expect(agents2.length).toBe(agents1.length);
  });
});
