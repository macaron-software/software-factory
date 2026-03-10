import { defineConfig } from "@playwright/test";
import { STORAGE_STATE } from "./global-setup";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  globalSetup: "./global-setup.ts",
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:8090",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    headless: true,
    storageState: STORAGE_STATE,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
