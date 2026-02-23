import { test, expect } from "@playwright/test";
import { collectErrors, assertNoErrors, safeGoto } from "./helpers";

/**
 * Project Chat E2E — verify PM persona, chat UI, and streaming.
 * Tests against live server with real project data.
 */

test.describe("Project Detail Page", () => {
  test("project page shows PM identity", async ({ page }) => {
    const errors = collectErrors(page);

    // Get first project
    const r = await page.request.get("/api/projects");
    const projects = await r.json();
    expect(projects.length).toBeGreaterThan(0);
    const pid = projects[0].id;

    await safeGoto(page, `/projects/${pid}`);

    // Chat input area
    const chatInput = page.locator("#chat-input");
    await expect(chatInput).toBeVisible({ timeout: 10_000 });

    // Send button
    const sendBtn = page.locator(".chat-send-btn");
    await expect(sendBtn).toBeVisible();

    // Sidebar with project info
    const sidebar = page.locator("#project-sidebar");
    await expect(sidebar).toBeVisible();

    // PM identity in sidebar (name + role)
    const pmSection = page.locator(".ps-section");
    const count = await pmSection.count();
    expect(count).toBeGreaterThanOrEqual(1);

    assertNoErrors(errors, `Project /${pid}`);
  });

  test("project page has conversation list", async ({ page }) => {
    const errors = collectErrors(page);

    const r = await page.request.get("/api/projects");
    const projects = await r.json();
    const pid = projects[0].id;

    await safeGoto(page, `/projects/${pid}`);

    // Conversation list panel
    const convList = page.locator("#chat-conv-list, .chat-conv-item");
    // May be empty for fresh projects, but the container should exist
    await expect(page.locator("#chat-conv-list")).toBeAttached();

    assertNoErrors(errors, `Project conversations /${pid}`);
  });

  test("project overview tab loads", async ({ page }) => {
    const errors = collectErrors(page);

    const r = await page.request.get("/api/projects");
    const projects = await r.json();
    const pid = projects[0].id;

    await safeGoto(page, `/projects/${pid}/overview`);

    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);

    assertNoErrors(errors, `Project overview /${pid}`);
  });

  test("project board loads kanban view", async ({ page }) => {
    const errors = collectErrors(page);

    const r = await page.request.get("/api/projects");
    const projects = await r.json();
    const pid = projects[0].id;

    await safeGoto(page, `/projects/${pid}/board`);

    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(200);

    assertNoErrors(errors, `Project board /${pid}`);
  });
});

test.describe("Project Chat Interaction", () => {
  test("type message in chat input", async ({ page }) => {
    const errors = collectErrors(page);

    const r = await page.request.get("/api/projects");
    const projects = await r.json();
    const pid = projects[0].id;

    await safeGoto(page, `/projects/${pid}`);

    const chatInput = page.locator("#chat-input");
    await expect(chatInput).toBeVisible({ timeout: 10_000 });

    // Type a message (don't send — we don't want to trigger LLM in tests)
    await chatInput.fill("Bonjour, quel est le statut du projet ?");
    const value = await chatInput.inputValue();
    expect(value).toContain("statut du projet");

    assertNoErrors(errors, "Project chat input");
  });
});

test.describe("All Projects Load", () => {
  test("every project page loads without errors", async ({ page }) => {
    const r = await page.request.get("/api/projects");
    const projects = await r.json();

    for (const p of projects.slice(0, 5)) {
      const errors = collectErrors(page);
      await safeGoto(page, `/projects/${p.id}`);

      // Wait for chat input to be rendered (proves page fully loaded)
      const chatInput = page.locator("#chat-input");
      await expect(chatInput).toBeVisible({ timeout: 10_000 });

      const body = await page.textContent("body");
      expect(body!.length, `Project ${p.id} has content`).toBeGreaterThan(200);

      assertNoErrors(errors, `Project ${p.id}`);
    }
  });
});
