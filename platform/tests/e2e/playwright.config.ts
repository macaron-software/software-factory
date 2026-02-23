import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: process.env.BASE_URL || "http://4.233.64.30",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    headless: true,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
