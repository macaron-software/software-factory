import { test, expect } from "@playwright/test";

test.describe("Agents page", () => {
  test("loads agents list", async ({ page }) => {
    await page.goto("/agents");
    await expect(page.locator("body")).toContainText(/agent/i, { timeout: 30_000 });
  });

  test("agents API returns data", async ({ request }) => {
    const response = await request.get("/api/agents");
    expect(response.status()).toBe(200);
    const body = await response.json();
    // API returns {agents: [...]} or direct array
    const agents = Array.isArray(body) ? body : (body.agents || body.items || []);
    expect(Array.isArray(agents)).toBeTruthy();
    expect(agents.length).toBeGreaterThan(0);
  });

  test("each agent has required fields", async ({ request }) => {
    const response = await request.get("/api/agents");
    const body = await response.json();
    const agents = Array.isArray(body) ? body : (body.agents || body.items || []);
    for (const agent of agents.slice(0, 5)) {
      expect(agent).toHaveProperty("name");
      expect(agent).toHaveProperty("role");
    }
  });
});
