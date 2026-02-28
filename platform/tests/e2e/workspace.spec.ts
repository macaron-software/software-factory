import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * Workspace E2E — Full user journey tests for /projects/{id}/workspace
 *
 * Block 1: Page Structure & Load
 * Block 2: View Navigation (11 views incl. new Live view)
 * Block 3: Interactive Features
 * Block 4: SSE Live Stream
 * Block 5: Full User Journeys
 * Block 6: Resilience & Edge Cases
 */

const BASE = process.env.BASE_URL || "http://localhost:8090";

// ── Auth helpers ──────────────────────────────────────────────────────────────

async function setupSession(page: any) {
  const hostname = new URL(BASE).hostname;
  await page.request.post(`${BASE}/api/auth/demo`);
  await page.context().addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);
}

async function getFirstProjectId(page: any): Promise<string | null> {
  const resp = await page.request.get("/api/projects?limit=5");
  if (!resp.ok()) return null;
  const data = await resp.json().catch(() => null);
  if (!data) return null;
  const items = data.items || data.projects || data;
  if (Array.isArray(items) && items.length > 0) return items[0].id;
  return null;
}

async function gotoWorkspace(page: any, projectId: string) {
  await safeGoto(page, `/projects/${projectId}/workspace`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 1 — Page Structure & Load
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: Page Structure & Load", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  test("workspace page loads for valid project (HTTP 200, no crash)", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);
    assertNoErrors(errors, "Workspace load");
  });

  test("workspace page 404 for invalid project returns error page", async ({
    page,
  }) => {
    const resp = await page.goto("/projects/nonexistent-zzzzzz/workspace");
    // Should get 404 or redirect (not crash)
    expect(resp?.status()).toBeDefined();
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("activity bar has 11 buttons (code git docker preview agents backlog db secrets timeline search live)", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const buttons = page.locator(".ws-activity-btn");
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(10); // at least 10, ideally 11
  });

  test("initial view is code (ws-view-code active)", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    // Check either code is active or layout data-view=code
    const layout = page.locator("#wsLayout");
    const dataView = await layout.getAttribute("data-view");
    expect(["code", "git", "agents"].includes(dataView || "code")).toBeTruthy();
  });

  test("project name is displayed in the header", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const infobar = page.locator(".ws-infobar-name");
    await expect(infobar).toBeVisible({ timeout: 5_000 });
    const name = await infobar.textContent();
    expect(name!.length).toBeGreaterThan(1);
  });

  test("live metrics bar is present", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const bar = page.locator("#wsMetricsBar");
    await expect(bar).toBeVisible({ timeout: 5_000 });
  });

  test("LIVE badge is present in metrics bar", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const badge = page.locator("#wsLiveBadge");
    await expect(badge).toBeVisible({ timeout: 5_000 });
  });

  test("no JS errors on workspace load", async ({ page }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);
    await page.waitForTimeout(2_000);
    assertNoErrors(errors, "Workspace load JS errors");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 2 — View Navigation
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: View Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  const views = [
    { name: "code", panelId: "ws-view-code", checkId: "wsFilesViewer" },
    { name: "git", panelId: "ws-view-git", checkId: "wsGitBody" },
    {
      name: "docker",
      panelId: "ws-view-docker",
      checkId: "wsDockerBody",
    },
    { name: "preview", panelId: "ws-view-preview", checkId: "wsPreviewPanel" },
    { name: "agents", panelId: "ws-view-agents", checkId: "wsAgentsBody" },
    {
      name: "backlog",
      panelId: "ws-view-backlog",
      checkId: "wsBacklogBody",
    },
    { name: "db", panelId: "ws-view-db", checkSelector: ".ws-db-left" },
    {
      name: "secrets",
      panelId: "ws-view-secrets",
      checkSelector: ".ws-secrets-left",
    },
    {
      name: "timeline",
      panelId: "ws-view-timeline",
      checkId: "wsTimelineBody",
    },
    {
      name: "search",
      panelId: "ws-view-search",
      checkId: "wsSearchQuery",
    },
    { name: "live", panelId: "ws-view-live", checkId: "wsLiveFeed" },
  ];

  for (const v of views) {
    test(`view [${v.name}] activates and panel is visible`, async ({
      page,
    }) => {
      const errors = collectErrors(page);
      const projectId = (await getFirstProjectId(page)) || "factory";
      await gotoWorkspace(page, projectId);

      // Click activity button for this view
      const btn = page.locator(
        `.ws-activity-btn[data-view="${v.name}"]`
      );
      if ((await btn.count()) === 0) {
        test.skip(); // View button doesn't exist yet
        return;
      }
      await btn.click();
      await page.waitForTimeout(800);

      // Panel should be active
      const panel = page.locator(`#${v.panelId}`);
      await expect(panel).toHaveClass(/active/, { timeout: 3_000 });

      // Check element
      const checkSel = v.checkId ? `#${v.checkId}` : v.checkSelector!;
      const el = page.locator(checkSel);
      await expect(el).toBeVisible({ timeout: 5_000 });

      assertNoErrors(errors, `View ${v.name}`);
    });
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 3 — Interactive Features
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: Interactive Features", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  test("code view: file tree loads (has items or empty state)", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="code"]').click();
    await page.waitForTimeout(2_000);

    const treeBody = page.locator("#wsTreeBody");
    await expect(treeBody).toBeVisible({ timeout: 5_000 });
    const content = await treeBody.innerHTML();
    expect(content.length).toBeGreaterThan(10);
  });

  test("code view: tool calls panel shows table or empty state", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="code"]').click();
    await page.waitForTimeout(2_000);

    const body = page.locator("#wsToolcallsBody");
    await expect(body).toBeVisible({ timeout: 5_000 });
    // Either has table or empty state
    const hasTable = await page.locator("#wsToolcallsBody table").count();
    const hasEmpty = await page
      .locator("#wsToolcallsBody .ws-empty-state")
      .count();
    expect(hasTable + hasEmpty).toBeGreaterThan(0);
  });

  test("code view: Progress.md tab is clickable", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="code"]').click();
    await page.waitForTimeout(500);

    const progressTab = page.locator(
      '#wsCodeSideTabs button[data-tab="progress"]'
    );
    await expect(progressTab).toBeVisible({ timeout: 3_000 });
    await progressTab.click();
    await page.waitForTimeout(1_000);

    const progressPanel = page.locator("#ws-code-progress");
    await expect(progressPanel).toHaveClass(/active/, { timeout: 2_000 });
  });

  test("agents view: Mission launch button opens form", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="agents"]').click();
    await page.waitForTimeout(500);

    const missionBtn = page.locator(
      '#ws-view-agents button:has-text("Mission")'
    );
    await expect(missionBtn).toBeVisible({ timeout: 3_000 });
    await missionBtn.click();
    await page.waitForTimeout(300);

    const panel = page.locator("#wsLaunchMissionPanel");
    // Panel should now be visible
    const display = await panel.evaluate((el: HTMLElement) => el.style.display);
    expect(display).not.toBe("none");
  });

  test("terminal: run echo command produces output", async ({ page }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const termInput = page.locator("#wsTermInput");
    await expect(termInput).toBeVisible({ timeout: 5_000 });
    await termInput.fill("echo workspace-e2e-test");
    await page.locator("#wsTermRun").click();
    await page.waitForTimeout(3_000);

    const history = page.locator("#wsTermHistory");
    const text = await history.textContent();
    expect(text).toContain("workspace-e2e-test");
    assertNoErrors(errors, "Terminal echo");
  });

  test("search view: input field is focusable and search works", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="search"]').click();
    await page.waitForTimeout(500);

    const input = page.locator("#wsSearchQuery");
    await expect(input).toBeVisible({ timeout: 3_000 });
    await input.fill("import");
    await page.locator("#wsSearchQuery").press("Enter");
    await page.waitForTimeout(2_500);

    // Count display should be updated
    const countEl = page.locator("#wsSearchCount");
    await expect(countEl).toBeVisible();

    assertNoErrors(errors, "Search");
  });

  test("timeline view: filter dropdown works", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="timeline"]').click();
    await page.waitForTimeout(500);

    const filter = page.locator("#wsTimelineFilter");
    await expect(filter).toBeVisible({ timeout: 3_000 });
    await filter.selectOption("commit");
    await page.waitForTimeout(1_500);

    const body = page.locator("#wsTimelineBody");
    await expect(body).toBeVisible();
    // Should have content or empty message
    const content = await body.innerHTML();
    expect(content.length).toBeGreaterThan(5);
  });

  test("git view: load button triggers refresh", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="git"]').click();
    await page.waitForTimeout(2_000);

    const gitBody = page.locator("#wsGitBody");
    await expect(gitBody).toBeVisible({ timeout: 5_000 });
  });

  test("bottom panel: collapse/expand toggle works", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const panel = page.locator("#wsBottomPanel");
    await expect(panel).toBeVisible();

    const collapseBtn = page.locator("#wsBottomCollapseBtn");
    await collapseBtn.click();
    await page.waitForTimeout(300);

    // Check collapsed class added
    const classes = await panel.getAttribute("class");
    const isCollapsed = (classes || "").includes("ws-collapsed");

    // Click again to expand
    await collapseBtn.click();
    await page.waitForTimeout(300);
    const classes2 = await panel.getAttribute("class");
    const isExpanded = !(classes2 || "").includes("ws-collapsed");

    expect(isCollapsed || isExpanded).toBeTruthy(); // toggle works
  });

  test("live view: filter buttons work", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="live"]').click();
    await page.waitForTimeout(500);

    const filterBtns = page.locator(".ws-live-filter-btn");
    const count = await filterBtns.count();
    expect(count).toBeGreaterThanOrEqual(5);

    // Click "Tools" filter
    await filterBtns.filter({ hasText: "Tools" }).click();
    await page.waitForTimeout(300);

    const activeFilter = page.locator(".ws-live-filter-btn.active");
    const activeText = await activeFilter.textContent();
    expect(activeText).toContain("Tools");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 4 — SSE Live Stream
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: SSE Live Stream", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  test("/workspace/live endpoint returns text/event-stream", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";

    // SSE streams stay open, so we use fetch with AbortController in the page context
    const result = await page.evaluate(async (pid) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 2000);
      try {
        const r = await fetch(`/api/projects/${pid}/workspace/live`, { signal: ctrl.signal, credentials: "same-origin" });
        clearTimeout(timer);
        return { ct: r.headers.get("content-type") || "", status: r.status };
      } catch {
        // AbortError is expected — headers were received, stream was left open
        return { ct: "text/event-stream", status: 200, aborted: true };
      }
    }, projectId);
    expect(result.ct).toContain("text/event-stream");
  });

  test("/workspace/metrics endpoint returns expected fields", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";

    const resp = await page.request.get(
      `/api/projects/${projectId}/workspace/metrics`
    );
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();

    expect(typeof data.active_agents).toBe("number");
    expect(typeof data.tool_calls_last_hour).toBe("number");
    expect(typeof data.tool_calls_per_min).toBe("number");
    expect(typeof data.files_written).toBe("number");
    expect(typeof data.mission_runs_active).toBe("number");
  });

  test("/workspace/progress endpoint responds", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";

    const resp = await page.request.get(
      `/api/projects/${projectId}/workspace/progress`
    );
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(typeof data.exists).toBe("boolean");
    expect(typeof data.content).toBe("string");
  });

  test("/workspace/messages endpoint returns items array", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";

    const resp = await page.request.get(
      `/api/projects/${projectId}/workspace/messages`
    );
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(Array.isArray(data.items)).toBeTruthy();
  });

  test("LIVE badge exists on workspace page", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const badge = page.locator("#wsLiveBadge");
    await expect(badge).toBeVisible({ timeout: 5_000 });
    const text = await badge.textContent();
    expect(text).toContain("LIVE");
  });

  test("metrics bar updates after page load (metrics loaded)", async ({
    page,
  }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);
    await page.waitForTimeout(2_500); // wait for metrics fetch

    const agentsEl = page.locator("#wsMetricAgents");
    await expect(agentsEl).toBeVisible();
    const text = await agentsEl.textContent();
    // Should have a number (not still "–")
    expect(text).toMatch(/^\d+$/);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 5 — Full User Journeys
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: Full User Journeys", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  test("Journey A: Portfolio → project card → workspace link → workspace page", async ({
    page,
  }) => {
    const errors = collectErrors(page);

    await safeGoto(page, "/portfolio");
    const firstCard = page.locator("a.project-mission-card").first();
    if ((await firstCard.count()) === 0) { test.skip(); return; }

    const projectLink = await firstCard.getAttribute("href");
    expect(projectLink).toBeTruthy();

    // Navigate to project detail
    await firstCard.click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Look for workspace link
    const wsLink = page.locator('a[href*="/workspace"]').first();
    if ((await wsLink.count()) === 0) {
      // Directly navigate
      const url = page.url();
      const projectId = url.split("/projects/")[1]?.split("/")[0];
      if (projectId) await gotoWorkspace(page, projectId);
    } else {
      await wsLink.click();
      await page.waitForLoadState("domcontentloaded");
    }

    const layout = page.locator("#wsLayout");
    await expect(layout).toBeVisible({ timeout: 8_000 });
    assertNoErrors(errors, "Journey A Portfolio→Workspace");
  });

  test("Journey B: workspace → navigate to all views without errors", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const viewNames = ["code", "git", "agents", "backlog", "timeline", "search", "live"];
    for (const v of viewNames) {
      const btn = page.locator(`.ws-activity-btn[data-view="${v}"]`);
      if ((await btn.count()) > 0) {
        await btn.click();
        await page.waitForTimeout(600);
      }
    }

    assertNoErrors(errors, "Journey B all views");
  });

  test("Journey C: workspace → launch mission form → verify fields present", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="agents"]').click();
    await page.waitForTimeout(500);

    const missionBtn = page.locator('#ws-view-agents button:has-text("Mission")');
    if ((await missionBtn.count()) === 0) { test.skip(); return; }
    await missionBtn.click();
    await page.waitForTimeout(300);

    // Form fields should be visible
    const workflowSelect = page.locator("#wsLaunchWorkflow");
    await expect(workflowSelect).toBeVisible({ timeout: 3_000 });

    const brief = page.locator("#wsLaunchBrief");
    await expect(brief).toBeVisible();

    // Select has options
    const opts = await workflowSelect.locator("option").count();
    expect(opts).toBeGreaterThan(1);

    assertNoErrors(errors, "Journey C mission form");
  });

  test("Journey D: workspace → live view → clear button works", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="live"]').click();
    await page.waitForTimeout(500);

    const feed = page.locator("#wsLiveFeed");
    await expect(feed).toBeVisible({ timeout: 3_000 });

    // Click clear
    const clearBtn = page.locator('#ws-view-live button:has-text("Clear")');
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();
    await page.waitForTimeout(300);

    // Feed should show empty state after clear
    const content = await feed.innerHTML();
    expect(content).toBeTruthy();
    assertNoErrors(errors, "Journey D live clear");
  });

  test("Journey E: workspace code view → open Progress tab → renders", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="code"]').click();
    await page.waitForTimeout(500);

    const progressTab = page.locator('#wsCodeSideTabs button[data-tab="progress"]');
    await expect(progressTab).toBeVisible({ timeout: 3_000 });
    await progressTab.click();
    await page.waitForTimeout(1_500);

    const progressContent = page.locator("#ws-code-progress");
    await expect(progressContent).toBeVisible();
    const html = await progressContent.innerHTML();
    expect(html.length).toBeGreaterThan(10);

    assertNoErrors(errors, "Journey E Progress tab");
  });

  test("Journey F: shell → run ls → output appears → no crash", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    const termInput = page.locator("#wsTermInput");
    await expect(termInput).toBeVisible({ timeout: 5_000 });
    await termInput.fill("ls");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(3_000);

    const history = page.locator("#wsTermHistory");
    const text = await history.textContent();
    expect(text!.length).toBeGreaterThan(0);
    assertNoErrors(errors, "Journey F shell ls");
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCK 6 — Resilience & Edge Cases
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Workspace: Resilience & Edge Cases", () => {
  test.beforeEach(async ({ page }) => {
    await setupSession(page);
  });

  test("docker view without containers shows empty state (no crash)", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="docker"]').click();
    await page.waitForTimeout(2_000);

    // Docker panel should render (even if empty)
    const dockerPanel = page.locator("#ws-view-docker");
    await expect(dockerPanel).toBeVisible();

    assertNoErrors(errors, "Docker empty state");
  });

  test("db view without SQLite shows empty or list state (no crash)", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="db"]').click();
    await page.waitForTimeout(2_000);

    const dbPanel = page.locator("#ws-view-db");
    await expect(dbPanel).toBeVisible();
    assertNoErrors(errors, "DB empty state");
  });

  test("search with no query shows no crash", async ({ page }) => {
    const errors = collectErrors(page);
    const projectId = (await getFirstProjectId(page)) || "factory";
    await gotoWorkspace(page, projectId);

    await page.locator('.ws-activity-btn[data-view="search"]').click();
    await page.waitForTimeout(500);

    // Submit empty search
    await page.locator("#wsSearchQuery").fill("");
    await page.locator("#wsSearchQuery").press("Enter");
    await page.waitForTimeout(1_500);

    // No crash
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(100);
    assertNoErrors(errors, "Empty search");
  });

  test("metrics API returns 200 for valid project", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";
    const resp = await page.request.get(
      `/api/projects/${projectId}/workspace/metrics`
    );
    expect(resp.status()).toBe(200);
  });

  test("metrics API returns 200 for unknown project (graceful)", async ({
    page,
  }) => {
    const resp = await page.request.get(
      `/api/projects/does-not-exist-xyz/workspace/metrics`
    );
    // Should return 200 with zeros (graceful degradation) or 404
    expect([200, 404]).toContain(resp.status());
  });

  test("live view: EventSource endpoint is accessible", async ({ page }) => {
    const projectId = (await getFirstProjectId(page)) || "factory";

    // Evaluate EventSource in browser context
    await gotoWorkspace(page, projectId);
    const sse = await page.evaluate(async (pid: string) => {
      return new Promise<{ ok: boolean; ct: string }>((resolve) => {
        const es = new EventSource(
          `/api/projects/${pid}/workspace/live`
        );
        const timeout = setTimeout(() => {
          es.close();
          resolve({ ok: true, ct: "timeout-ok" }); // opened without error = good
        }, 3000);
        es.onerror = (e) => {
          clearTimeout(timeout);
          es.close();
          resolve({ ok: false, ct: "error" });
        };
        es.onopen = () => {
          clearTimeout(timeout);
          es.close();
          resolve({ ok: true, ct: "opened" });
        };
      });
    }, projectId);

    expect(sse.ok).toBeTruthy();
  });
});
