import { test, expect } from "@playwright/test";

test.describe("Thompson Sampling", () => {
  test("API /api/analytics/agents/scores returns valid structure", async ({
    request,
  }) => {
    const res = await request.get("/api/analytics/agents/scores");
    expect(res.status()).toBe(200);
    const d = await res.json();
    expect(d.success).toBe(true);
    expect(d).toHaveProperty("agents");
    expect(d).toHaveProperty("providers");
    expect(d).toHaveProperty("summary");
    expect(d.summary).toHaveProperty("total_agents");
    expect(d.summary).toHaveProperty("total_accepted");
    expect(d.summary).toHaveProperty("total_rejected");
    expect(d.summary).toHaveProperty("high_rejection_count");
  });

  test("each agent entry has required fields", async ({ request }) => {
    const res = await request.get("/api/analytics/agents/scores");
    const d = await res.json();
    for (const agent of d.agents.slice(0, 5)) {
      expect(agent).toHaveProperty("agent_id");
      expect(agent).toHaveProperty("agent_name");
      expect(agent).toHaveProperty("provider");
      expect(agent).toHaveProperty("accepted");
      expect(agent).toHaveProperty("rejected");
      expect(agent).toHaveProperty("success_pct");
      expect(agent).toHaveProperty("rejection_pct");
      expect(agent).toHaveProperty("quality_score");
      expect(agent.success_pct).toBeGreaterThanOrEqual(0);
      expect(agent.success_pct).toBeLessThanOrEqual(100);
    }
  });

  test("Teams/ART page has Thompson Sampling tab", async ({ page }) => {
    await page.goto("/art");
    await expect(page.locator(".tabs")).toContainText("Thompson Sampling");
  });

  test("Thompson Sampling tab loads data on click", async ({ page }) => {
    await page.goto("/art");
    const tab = page.locator(".tabs button", { hasText: "Thompson Sampling" });
    await tab.click();
    // Wait for table to load (either data or empty message)
    await expect(
      page.locator("#ts-art-tbody tr:first-child td")
    ).not.toContainText("Chargement", { timeout: 5000 });
  });

  test("A/B provider panels are visible in Thompson tab", async ({ page }) => {
    await page.goto("/art");
    await page.locator(".tabs button", { hasText: "Thompson Sampling" }).click();
    await expect(page.locator("#ts-ab-grid")).toBeVisible();
    await expect(page.locator("text=Équipe A")).toBeVisible();
    await expect(page.locator("text=Équipe B")).toBeVisible();
  });
});
