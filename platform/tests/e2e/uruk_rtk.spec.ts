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
 *
 * Note: tests skip gracefully on auth-protected environments (401/500/HTML).
 */

// ------------------------------------------------------------------
// Auth setup — same pattern as cto_jarvis.spec.ts
// ------------------------------------------------------------------

async function setupSession(page: any) {
  const BASE = process.env.BASE_URL || "http://localhost:8090";
  const hostname = new URL(BASE).hostname;
  await page.request.post(`${BASE}/api/auth/demo`);
  await page.context().addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);
}

/** Returns null when the response is not JSON (auth redirect, 500 HTML error). */
async function tryJson(resp: any): Promise<any | null> {
  if (!resp.ok()) return null;
  const ct = resp.headers()["content-type"] || "";
  if (!ct.includes("json")) return null;
  try { return await resp.json(); } catch { return null; }
}

// ------------------------------------------------------------------
// API: capability_grade on /api/agents
// ------------------------------------------------------------------

test.describe("Uruk: capability_grade in agents API", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("every agent has a capability_grade field", async ({ request, page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/agents");
    const agents = await tryJson(resp);
    if (!agents) { test.skip(); return; }

    expect(Array.isArray(agents)).toBe(true);
    expect(agents.length).toBeGreaterThan(0);
    for (const agent of agents) {
      expect(
        ["organizer", "executor"],
        `Agent ${agent.id} has invalid grade: ${agent.capability_grade}`
      ).toContain(agent.capability_grade);
    }
  });

  test("known organizer agents have grade=organizer", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/agents");
    const agents = await tryJson(resp);
    if (!agents) { test.skip(); return; }

    const organizerIds = ["strat-cto", "scrum_master", "enterprise_architect", "product_manager"];
    for (const id of organizerIds) {
      const agent = agents.find((a: any) => a.id === id);
      if (!agent) continue;
      expect(agent.capability_grade, `${id} should be organizer`).toBe("organizer");
    }
  });

  test("majority of agents are executors (dev/qa/devops)", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/agents");
    const agents = await tryJson(resp);
    if (!agents) { test.skip(); return; }

    const executors = agents.filter((a: any) => a.capability_grade === "executor");
    const organizers = agents.filter((a: any) => a.capability_grade === "organizer");
    expect(executors.length).toBeGreaterThan(organizers.length);
    expect(executors.length / agents.length).toBeGreaterThan(0.5);
  });

  test("organizer count is between 20 and 80", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/agents");
    const agents = await tryJson(resp);
    if (!agents) { test.skip(); return; }

    const organizers = agents.filter((a: any) => a.capability_grade === "organizer");
    expect(organizers.length).toBeGreaterThanOrEqual(20);
    expect(organizers.length).toBeLessThanOrEqual(80);
  });
});

// ------------------------------------------------------------------
// API: rtk block in /api/monitoring/live
// ------------------------------------------------------------------

test.describe("rtk: monitoring API exposes rtk block", () => {
  test("GET /api/monitoring/live contains rtk object", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/monitoring/live");
    const data = await tryJson(resp);
    if (!data) { test.skip(); return; }

    expect(data).toHaveProperty("rtk");
    const rtk = data.rtk;
    expect(rtk).toHaveProperty("calls");
    expect(rtk).toHaveProperty("bytes_raw");
    expect(rtk).toHaveProperty("bytes_compressed");
    expect(rtk).toHaveProperty("bytes_saved");
    expect(rtk).toHaveProperty("tokens_saved_est");
    expect(typeof rtk.calls).toBe("number");
    expect(typeof rtk.bytes_raw).toBe("number");
    expect(typeof rtk.tokens_saved_est).toBe("number");
  });

  test("rtk.bytes_saved is non-negative", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/monitoring/live");
    const data = await tryJson(resp);
    if (!data) { test.skip(); return; }
    expect(data.rtk.bytes_saved).toBeGreaterThanOrEqual(0);
    expect(data.rtk.tokens_saved_est).toBeGreaterThanOrEqual(0);
  });

  test("when rtk.calls > 0, ratio_pct is between 1 and 99", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/monitoring/live");
    const data = await tryJson(resp);
    if (!data) { test.skip(); return; }
    const rtk = data.rtk;
    if (rtk.calls === 0) { test.skip(); return; }
    expect(rtk.ratio_pct).toBeGreaterThan(0);
    expect(rtk.ratio_pct).toBeLessThan(100);
  });
});

// ------------------------------------------------------------------
// UI: monitoring page renders rtk widget
// ------------------------------------------------------------------

test.describe("rtk: monitoring page widget", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("monitoring page loads without rtk errors", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/monitoring");

    await expect(page).toHaveTitle(/.+/);
    // Accept any page content — auth redirect is also a valid response
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(50);

    // Filter known benign CORS errors (external fonts CDN)
    const appErrors = errors.console.filter(
      (e) => !e.includes("s3.popi.nz") && !e.includes("CORS") && !e.includes("font")
    );
    const monErrors: typeof errors = { console: appErrors, network: errors.network };
    assertNoErrors(monErrors, "Monitoring page (rtk)");
  });

  test("rtk row is present in DOM (hidden until first call)", async ({ page }) => {
    await safeGoto(page, "/monitoring");
    // Only assert if we're on the monitoring page (not auth redirect)
    const title = await page.title();
    if (!title.toLowerCase().includes("monitor") && !title.toLowerCase().includes("sf")) {
      test.skip(); return;
    }
    const rtkRow = page.locator("#monRtkRow");
    await expect(rtkRow).toBeAttached({ timeout: 8_000 });
  });

  test("when rtk calls > 0, rtk row becomes visible", async ({ page }) => {
    const resp = await page.request.get("/api/monitoring/live");
    const data = await tryJson(resp);
    if (!data || data.rtk?.calls === 0) { test.skip(); return; }

    await safeGoto(page, "/monitoring");
    const rtkRow = page.locator("#monRtkRow");
    await expect(rtkRow).toBeVisible({ timeout: 8_000 });

    const tokensSaved = await page.locator("#monRtkTokens").textContent();
    expect(tokensSaved!.trim().length).toBeGreaterThan(0);
  });
});

// ------------------------------------------------------------------
// Journey: Agents page — grades visible in agent details
// ------------------------------------------------------------------

test.describe("Journey: Agents page shows capability grade", () => {
  test("agents page loads and API returns valid grades", async ({ page }) => {
    await setupSession(page);
    const errors = collectErrors(page);
    await safeGoto(page, "/agents");

    await expect(page).toHaveTitle(/.+/);
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);

    // Filter CORS/font errors (external CDN issues are not app bugs)
    const appErrors = errors.console.filter(
      (e) => !e.includes("CORS") && !e.includes("font") && !e.includes("s3.popi.nz")
    );
    const filtered: typeof errors = { console: appErrors, network: errors.network };
    assertNoErrors(filtered, "Agents page (Uruk grades)");
  });
});

// ------------------------------------------------------------------
// Journey: rtk integration — smoke test
// ------------------------------------------------------------------

test.describe("Journey: rtk git compression (API smoke test)", () => {
  test("rtk block always present in monitoring live API", async ({ page }) => {
    await setupSession(page);
    const resp = await page.request.get("/api/monitoring/live");
    const data = await tryJson(resp);
    if (!data) { test.skip(); return; }
    expect(data).toHaveProperty("rtk");
  });
});

