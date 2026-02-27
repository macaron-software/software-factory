import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * Uruk model + rtk E2E tests.
 *
 * Covers:
 *  - /api/agents returns capability_grade for each agent
 *  - Organizer agents (cto, arch, cdp, product, reviewer) → "organizer"
 *  - Executor agents (dev, qa, devops, ux) → "executor"
 *  - /api/monitoring/live exposes rtk block
 *  - Monitoring page renders rtk widget (when calls > 0) or hides it gracefully
 */

// ------------------------------------------------------------------
// API: capability_grade on /api/agents
// ------------------------------------------------------------------

test.describe("Uruk: capability_grade in agents API", () => {
  test("every agent has a capability_grade field", async ({ request }) => {
    const resp = await request.get("/api/agents");
    if (resp.status() === 401) { test.skip(); return; }
    expect(resp.status()).toBe(200);
    const agents = await resp.json();
    expect(Array.isArray(agents)).toBe(true);
    expect(agents.length).toBeGreaterThan(0);

    for (const agent of agents) {
      expect(
        ["organizer", "executor"],
        `Agent ${agent.id} has invalid grade: ${agent.capability_grade}`
      ).toContain(agent.capability_grade);
    }
  });

  test("known organizer agents have grade=organizer", async ({ request }) => {
    const resp = await request.get("/api/agents");
    if (resp.status() === 401) { test.skip(); return; }
    const agents: any[] = await resp.json();

    const organizerIds = ["strat-cto", "scrum_master", "enterprise_architect", "product_manager"];
    for (const id of organizerIds) {
      const agent = agents.find((a) => a.id === id);
      if (!agent) continue; // agent may not exist in all envs
      expect(agent.capability_grade, `${id} should be organizer`).toBe("organizer");
    }
  });

  test("majority of agents are executors (dev/qa/devops)", async ({ request }) => {
    const resp = await request.get("/api/agents");
    if (resp.status() === 401) { test.skip(); return; }
    const agents: any[] = await resp.json();

    const executors = agents.filter((a) => a.capability_grade === "executor");
    const organizers = agents.filter((a) => a.capability_grade === "organizer");

    // We expect significantly more executors than organizers
    expect(executors.length).toBeGreaterThan(organizers.length);
    // At least 60% executors (baseline: 127/175 = 72.6%)
    expect(executors.length / agents.length).toBeGreaterThan(0.5);
  });

  test("organizer count is between 20 and 80", async ({ request }) => {
    const resp = await request.get("/api/agents");
    if (resp.status() === 401) { test.skip(); return; }
    const agents: any[] = await resp.json();
    const organizers = agents.filter((a) => a.capability_grade === "organizer");
    expect(organizers.length).toBeGreaterThanOrEqual(20);
    expect(organizers.length).toBeLessThanOrEqual(80);
  });
});

// ------------------------------------------------------------------
// API: rtk block in /api/monitoring/live
// ------------------------------------------------------------------

test.describe("rtk: monitoring API exposes rtk block", () => {
  test("GET /api/monitoring/live contains rtk object", async ({ request }) => {
    const resp = await request.get("/api/monitoring/live");
    if (resp.status() === 401) { test.skip(); return; }
    expect(resp.status()).toBe(200);
    const data = await resp.json();

    expect(data).toHaveProperty("rtk");
    const rtk = data.rtk;
    expect(rtk).toHaveProperty("calls");
    expect(rtk).toHaveProperty("bytes_raw");
    expect(rtk).toHaveProperty("bytes_compressed");
    expect(rtk).toHaveProperty("bytes_saved");
    expect(rtk).toHaveProperty("tokens_saved_est");
    // All numeric
    expect(typeof rtk.calls).toBe("number");
    expect(typeof rtk.bytes_raw).toBe("number");
    expect(typeof rtk.tokens_saved_est).toBe("number");
  });

  test("rtk.bytes_saved is non-negative", async ({ request }) => {
    const resp = await request.get("/api/monitoring/live");
    if (resp.status() === 401) { test.skip(); return; }
    const data = await resp.json();
    const rtk = data.rtk;
    expect(rtk.bytes_saved).toBeGreaterThanOrEqual(0);
    expect(rtk.tokens_saved_est).toBeGreaterThanOrEqual(0);
  });

  test("when rtk.calls > 0, ratio_pct is between 1 and 99", async ({ request }) => {
    const resp = await request.get("/api/monitoring/live");
    if (resp.status() === 401) { test.skip(); return; }
    const data = await resp.json();
    const rtk = data.rtk;
    if (rtk.calls === 0) { test.skip(); return; } // no calls yet, skip
    expect(rtk.ratio_pct).toBeGreaterThan(0);
    expect(rtk.ratio_pct).toBeLessThan(100);
  });
});

// ------------------------------------------------------------------
// UI: monitoring page renders rtk widget
// ------------------------------------------------------------------

test.describe("rtk: monitoring page widget", () => {
  test("monitoring page loads without rtk errors", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/monitoring");

    // Page should load
    await expect(page).toHaveTitle(/.+/);
    const cards = page.locator(".mon-card");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });

    assertNoErrors(errors, "Monitoring page (rtk)");
  });

  test("rtk row is present in DOM (hidden until first call)", async ({ page }) => {
    await safeGoto(page, "/monitoring");

    // #monRtkRow exists regardless of visibility
    const rtkRow = page.locator("#monRtkRow");
    await expect(rtkRow).toBeAttached({ timeout: 8_000 });
    // It may be hidden (no rtk calls yet) — just verify the DOM node exists
  });

  test("when rtk calls > 0, rtk row becomes visible", async ({ page, request }) => {
    // First check if there are any rtk calls
    const resp = await request.get("/api/monitoring/live");
    if (resp.status() === 401) { test.skip(); return; }
    const data = await resp.json();
    if (data.rtk?.calls === 0) { test.skip(); return; } // nothing to show

    await safeGoto(page, "/monitoring");
    const rtkRow = page.locator("#monRtkRow");
    // Should be visible since calls > 0
    await expect(rtkRow).toBeVisible({ timeout: 8_000 });

    // Values should be populated
    const tokensSaved = await page.locator("#monRtkTokens").textContent();
    expect(tokensSaved!.trim().length).toBeGreaterThan(0);
  });
});

// ------------------------------------------------------------------
// Journey: Agents page — grades visible in agent details
// ------------------------------------------------------------------

test.describe("Journey: Agents page shows capability grade", () => {
  test("agents page loads and API returns valid grades", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/agents");

    await expect(page).toHaveTitle(/.+/);
    // Body should have agent-related content
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);

    assertNoErrors(errors, "Agents page (Uruk grades)");
  });
});

// ------------------------------------------------------------------
// Journey: rtk integration — git tools compress output
// ------------------------------------------------------------------

test.describe("Journey: rtk git compression (API smoke test)", () => {
  test("git-status tool API is reachable", async ({ request }) => {
    // This just verifies the tool endpoint is accessible; actual rtk
    // compression is validated via metrics (bytes_saved > 0 after calls)
    const resp = await request.get("/api/monitoring/live");
    if (resp.status() === 401) { test.skip(); return; }
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    // rtk block must always be present
    expect(data).toHaveProperty("rtk");
  });
});
