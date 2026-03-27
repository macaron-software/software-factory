import { expect, test } from "@playwright/test";
import { assertNoErrors, collectErrors, safeGoto, setupSession } from "./helpers";

const SF_PROJECT_ID = "software-factory";

test.describe("Project product traceability", () => {
  test("shows the lean traceability summary", async ({ page }) => {
    const errors = collectErrors(page);
    await setupSession(page);
    await safeGoto(page, `/projects/${SF_PROJECT_ID}/product?tab=tracabilite`);

    await expect(page.locator("#trace-verdict")).toBeVisible();
    await expect(page.locator("#trace-open-overview")).toBeVisible();
    await expect(page.locator("#trace-open-coverage")).toBeVisible();
    await expect(page.locator("#trace-export-sqlite")).toBeVisible();
    await expect(page.locator("#trace-layer-grid")).not.toBeVisible();

    await page.locator("#trace-open-overview").click();
    await expect(page.locator("#trace-overview-modal")).toBeVisible();
    await page.locator("#trace-overview-modal button:has-text('Fermer')").click();
    await expect(page.locator("#trace-overview-modal")).not.toBeVisible();

    await page.locator("#trace-open-coverage").click();
    await expect(page.locator("#trace-layer-grid")).toBeVisible();

    const layerCards = page.locator("#trace-layer-grid .pv-layer-card");
    expect(await layerCards.count()).toBeGreaterThanOrEqual(5);

    const body = await page.textContent("body");
    expect(body || "").toContain("SQLite export");
    expect(body || "").toContain("Pourquoi");

    assertNoErrors(errors, "Project product traceability");
  });

  test("project traceability APIs return report, validation, and sqlite", async ({ page }) => {
    await setupSession(page);
    await safeGoto(page, `/projects/${SF_PROJECT_ID}/product?tab=tracabilite`);

    const report = await page.evaluate(async (projectId) => {
      const response = await fetch(`/api/projects/${projectId}/traceability/report`);
      return {
        status: response.status,
        body: await response.json(),
      };
    }, SF_PROJECT_ID);
    expect(report.status).toBe(200);
    expect(report.body.project_id).toBe(SF_PROJECT_ID);
    expect(report.body.uuid_policy).toContain("canonical");
    expect(Array.isArray(report.body.features)).toBeTruthy();

    const validate = await page.evaluate(async (projectId) => {
      const response = await fetch(`/api/projects/${projectId}/traceability/validate`);
      return {
        status: response.status,
        body: await response.json(),
      };
    }, SF_PROJECT_ID);
    expect(validate.status).toBe(200);
    expect(validate.body.project_id).toBe(SF_PROJECT_ID);
    expect(["PASS", "FAIL", "SKIP"]).toContain(validate.body.verdict);

    const exportInfo = await page.evaluate(async (projectId) => {
      const response = await fetch(`/api/projects/${projectId}/traceability/export`);
      await response.arrayBuffer();
      return {
        status: response.status,
        contentType: response.headers.get("content-type") || "",
        uuidPolicy: response.headers.get("x-traceability-uuid-policy") || "",
      };
    }, SF_PROJECT_ID);
    expect(exportInfo.status).toBe(200);
    expect(exportInfo.uuidPolicy).toContain("canonical");
    expect(exportInfo.contentType).toContain("sqlite");
  });
});
