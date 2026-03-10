import { test, expect } from "@playwright/test";

const LANGUAGES = ["en", "fr", "zh", "es", "ja", "pt", "de", "ko"];

test.describe("Language switching", () => {
  for (const lang of LANGUAGES) {
    test(`loads in ${lang}`, async ({ page, context }) => {
      const baseURL = process.env.BASE_URL || "http://localhost:8090";
      await context.addCookies([{ name: "lang", value: lang, url: baseURL }]);
      await page.goto("/");
      // Page should load without errors in any language
      expect(await page.title()).toBeTruthy();
      const content = await page.textContent("body");
      expect(content!.length).toBeGreaterThan(100);
    });
  }

  test("locale API returns translations", async ({ request }) => {
    for (const lang of LANGUAGES) {
      const response = await request.get(`/api/i18n/${lang}.json`);
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(Object.keys(data).length).toBeGreaterThan(10);
    }
  });
});
