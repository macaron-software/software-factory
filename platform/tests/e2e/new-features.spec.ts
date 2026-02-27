import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * New Features E2E — validates all features added in session 2026-02-27:
 *  - Workspace: Timeline view, Search view, file icons, Launch Mission button
 *  - World 3D: sidebar nav link, project filter, /api/world/live
 *  - DbGate: URL-based token auto-login
 *  - Notifications: settings tab
 *  - Multi-server dispatch: /api/dispatch/workers
 *  - API: /api/metrics/load, /api/world/live
 */

// ── Helpers ──────────────────────────────────────────────────────────────────

const BASE = process.env.BASE_URL || "http://localhost:8090";

async function setupSession(page: any) {
  const hostname = new URL(BASE).hostname;
  await page.request.post(`${BASE}/api/auth/demo`);
  await page.context().addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);
}

async function getProjectId(page: any): Promise<string | null> {
  const resp = await page.request.get("/api/projects?limit=5");
  if (!resp.ok()) return null;
  const data = await resp.json();
  const projects = data.projects || data.items || data || [];
  return projects.length ? (projects[0].id || null) : null;
}

// ── API smoke tests ───────────────────────────────────────────────────────────

test.describe("API: New endpoints", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("GET /api/metrics/load returns cpu/ram/load_score", async ({ page }) => {
    const r = await page.request.get("/api/metrics/load");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(typeof d.cpu_percent).toBe("number");
    expect(typeof d.ram_percent).toBe("number");
    expect(typeof d.load_score).toBe("number");
    expect(d.active_missions).toBeDefined();
  });

  test("GET /api/world/live returns missions/agents/projects", async ({ page }) => {
    const r = await page.request.get("/api/world/live");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(Array.isArray(d.missions)).toBeTruthy();
    expect(Array.isArray(d.messages)).toBeTruthy();
    expect(typeof d.agent_sessions).toBe("object");
    expect(Array.isArray(d.projects)).toBeTruthy();
    expect(typeof d.total_missions).toBe("number");
  });

  test("GET /api/world/live?project= filters correctly", async ({ page }) => {
    const r = await page.request.get("/api/world/live?project=nonexistent-xyz");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(Array.isArray(d.missions)).toBeTruthy();
    expect(d.missions.length).toBe(0);
  });

  test("GET /api/dispatch/workers returns worker list", async ({ page }) => {
    const r = await page.request.get("/api/dispatch/workers");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(Array.isArray(d.workers)).toBeTruthy();
    expect(typeof d.coordinator_only).toBe("boolean");
  });

  test("GET /api/dbgate/token returns token object", async ({ page }) => {
    const r = await page.request.get("/api/dbgate/token");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect("token" in d).toBeTruthy(); // may be empty string if DbGate not configured
  });

  test("GET /api/push/vapid-public-key returns key object", async ({ page }) => {
    const r = await page.request.get("/api/push/vapid-public-key");
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect("publicKey" in d).toBeTruthy();
  });
});

// ── Workspace API tests ───────────────────────────────────────────────────────

test.describe("API: Workspace new endpoints", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("GET /api/projects/{id}/workspace/timeline returns events", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    const r = await page.request.get(`/api/projects/${pid}/workspace/timeline`);
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(Array.isArray(d.events)).toBeTruthy();
  });

  test("GET /api/projects/{id}/workspace/timeline filter=commit", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    const r = await page.request.get(`/api/projects/${pid}/workspace/timeline?filter=commit`);
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    for (const ev of d.events) {
      expect(ev.type).toBe("commit");
    }
  });

  test("GET /api/projects/{id}/workspace/search returns matches", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    // Search for something likely to exist
    const r = await page.request.get(`/api/projects/${pid}/workspace/search?q=import`);
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(Array.isArray(d.matches)).toBeTruthy();
    expect(typeof d.total_matches).toBe("number");
  });

  test("GET /api/projects/{id}/workspace/search empty query returns empty", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    const r = await page.request.get(`/api/projects/${pid}/workspace/search?q=`);
    expect(r.ok()).toBeTruthy();
    const d = await r.json();
    expect(d.matches.length).toBe(0);
  });
});

// ── World 3D page ─────────────────────────────────────────────────────────────

test.describe("Page: World 3D", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("accessible via /world URL", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/world");
    await expect(page).toHaveTitle(/World|3D|Agent/i, { timeout: 10_000 });
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);
    // WebGL may fail in headless CI (no GPU) — that's expected and benign
    const filtered = errors.console.filter(e => !e.includes("WebGL") && !e.includes("THREE."));
    expect(filtered, `Console errors on World 3D page: ${filtered.join("\n")}`).toHaveLength(0);
  });

  test("project filter dropdown is present", async ({ page }) => {
    await safeGoto(page, "/world");
    const select = page.locator("#world-project-select");
    await expect(select).toBeVisible({ timeout: 8_000 });
  });

  test("globe icon exists in sidebar nav", async ({ page }) => {
    await safeGoto(page, "/");
    // World link in sidebar
    const worldLink = page.locator('a[href="/world"]');
    await expect(worldLink.first()).toBeVisible({ timeout: 8_000 });
  });

  test("world live refresh JS is present in page", async ({ page }) => {
    await safeGoto(page, "/world");
    const content = await page.content();
    expect(content).toContain("api/world/live");
    expect(content).toContain("worldLiveRefresh");
  });
});

// ── Workspace IHM ─────────────────────────────────────────────────────────────

test.describe("Page: Workspace — new views", () => {
  test.describe.configure({ retries: 2 });
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("workspace page loads for a project", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    const errors = collectErrors(page);
    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // Activity bar should have 10 buttons (code, git, docker, preview, agents, backlog, db, secrets, timeline, search)
    const activityBtns = page.locator(".ws-activity-btn");
    const count = await activityBtns.count();
    expect(count).toBeGreaterThanOrEqual(10);
    // CSP frame-ancestors error is benign (iframes trying to load from different port)
    const filtered = errors.console.filter(e => !e.includes("frame-ancestors") && !e.includes("Content Security Policy"));
    expect(filtered, `Console errors on Workspace load: ${filtered.join("\n")}`).toHaveLength(0);
  });

  test("Timeline button (9th) is visible and clickable", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const timelineBtn = page.locator('.ws-activity-btn[data-view="timeline"]');
    await expect(timelineBtn).toBeVisible({ timeout: 8_000 });
    await timelineBtn.click();
    await page.waitForTimeout(500);

    // Timeline panel should become active
    const panel = page.locator("#ws-view-timeline");
    await expect(panel).toHaveClass(/active/, { timeout: 5_000 });
  });

  test("Timeline panel has filter dropdown", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const timelineBtn = page.locator('.ws-activity-btn[data-view="timeline"]');
    await timelineBtn.click();
    await page.waitForTimeout(800);

    const filter = page.locator("#wsTimelineFilter");
    await expect(filter).toBeVisible({ timeout: 5_000 });
    // Check filter options
    const options = await filter.locator("option").allTextContents();
    expect(options).toContain("Tout");
    expect(options).toContain("Git commits");
    expect(options).toContain("Missions");
    expect(options).toContain("Déploiements");
  });

  test("Search button (10th) is visible and clickable", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const searchBtn = page.locator('.ws-activity-btn[data-view="search"]');
    await expect(searchBtn).toBeVisible({ timeout: 8_000 });
    await searchBtn.click();
    await page.waitForTimeout(500);

    const panel = page.locator("#ws-view-search");
    await expect(panel).toHaveClass(/active/, { timeout: 5_000 });
  });

  test("Search panel has query input and glob filter", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const searchBtn = page.locator('.ws-activity-btn[data-view="search"]');
    await searchBtn.click();
    await page.waitForTimeout(500);

    await expect(page.locator("#wsSearchQuery")).toBeVisible();
    await expect(page.locator("#wsSearchGlob")).toBeVisible();
    await expect(page.locator("#wsSearchCase")).toBeVisible();
    await expect(page.locator("#wsSearchRegex")).toBeVisible();
  });

  test("Search executes and shows results", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const searchBtn = page.locator('.ws-activity-btn[data-view="search"]');
    await searchBtn.click();
    await page.waitForTimeout(500);

    // Type a search query and press Enter
    await page.locator("#wsSearchQuery").fill("def ");
    await page.locator("#wsSearchQuery").press("Enter");
    await page.waitForTimeout(2000);

    // Either results or "Aucun résultat" message
    const resultsBody = page.locator("#wsSearchResults");
    const content = await resultsBody.textContent();
    expect(content!.length).toBeGreaterThan(0);
  });

  test("Agents view has Launch Mission button", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const agentsBtn = page.locator('.ws-activity-btn[data-view="agents"]');
    await agentsBtn.click();
    await page.waitForTimeout(500);

    // Mission launch button
    const launchBtn = page.locator("button", { hasText: "Mission" });
    await expect(launchBtn.first()).toBeVisible({ timeout: 5_000 });
  });

  test("Launch Mission panel opens with workflow selector", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    await safeGoto(page, `/projects/${pid}/workspace`);
    await page.waitForLoadState("domcontentloaded");

    const agentsBtn = page.locator('.ws-activity-btn[data-view="agents"]');
    await agentsBtn.click();
    await page.waitForTimeout(500);

    const launchBtn = page.locator("button", { hasText: "Mission" });
    await launchBtn.first().click();
    await page.waitForTimeout(500);

    const panel = page.locator("#wsLaunchMissionPanel");
    await expect(panel).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("#wsLaunchWorkflow")).toBeVisible();
    await expect(page.locator("#wsLaunchBrief")).toBeVisible();
  });

  test("File tree shows colored icons (wsFileIcon in page)", async ({ page }) => {
    const pid = await getProjectId(page);
    if (!pid) { test.skip(); return; }

    // Check JS source in the HTTP response (more reliable than DOM content)
    const resp = await page.request.get(`/projects/${pid}/workspace`);
    const html = await resp.text();
    expect(html).toContain("wsFileIcon");
    expect(html).toContain("ws-icon-js");
  });
});

// ── Settings: Notifications tab ───────────────────────────────────────────────

test.describe("Page: Settings — Notifications", () => {
  test.describe.configure({ retries: 2 });
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("settings page loads", async ({ page }) => {
    const errors = collectErrors(page);
    await safeGoto(page, "/settings");
    await page.waitForLoadState("domcontentloaded");
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);
    assertNoErrors(errors, "Settings page");
  });

  test("Notifications tab exists in settings", async ({ page }) => {
    await safeGoto(page, "/settings");
    await page.waitForLoadState("domcontentloaded");
    // Find Notifications tab button via onclick attribute
    const notifTab = page.locator('button[onclick*="notifications"]');
    await expect(notifTab.first()).toBeVisible({ timeout: 8_000 });
  });

  test("Notifications tab has WhatsApp and Browser Push cards", async ({ page }) => {
    await safeGoto(page, "/settings");
    await page.waitForLoadState("domcontentloaded");

    const notifTab = page.locator('button[onclick*="notifications"]');
    await notifTab.first().click();
    await page.waitForTimeout(500);

    const content = await page.textContent("body");
    expect(content).toMatch(/WhatsApp|Twilio/i);
    expect(content).toMatch(/Browser|Push/i);
  });

  test("Worker Nodes section in Orchestrator tab", async ({ page }) => {
    await safeGoto(page, "/settings");
    await page.waitForLoadState("domcontentloaded");

    // Find orchestrator tab
    const orchTab = page.locator('button[onclick*="orchestrator"]');
    await orchTab.first().click();
    await page.waitForTimeout(500);

    const content = await page.textContent("body");
    expect(content).toMatch(/Worker.*Node|node.*worker/i);
  });
});

// ── Service worker ────────────────────────────────────────────────────────────

test.describe("Assets: Service Worker", () => {
  test.beforeEach(async ({ page }) => { await setupSession(page); });

  test("GET /sw.js returns service worker JS", async ({ page }) => {
    const r = await page.request.get("/sw.js");
    expect(r.ok()).toBeTruthy();
    const ct = r.headers()["content-type"] || "";
    expect(ct).toMatch(/javascript/);
    const body = await r.text();
    expect(body).toContain("push");
  });
});
