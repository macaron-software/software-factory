/**
 * Playwright global setup — authenticate once via /api/auth/demo
 * and save storage state for all test files to reuse.
 */
import { chromium, FullConfig } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

export const STORAGE_STATE = path.join(__dirname, ".auth-state.json");

export default async function globalSetup(config: FullConfig) {
  const rawBase = process.env.BASE_URL || "http://localhost:8090";
  // Node may resolve 'localhost' to ::1 (IPv6). Force IPv4 to avoid ECONNREFUSED.
  const baseURL = rawBase.replace("localhost", "127.0.0.1");
  const hostname = new URL(rawBase).hostname;

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Authenticate via demo endpoint
  await page.request.post(`${baseURL}/api/auth/demo`);

  // Set onboarding cookie to bypass redirect
  await context.addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);

  // Save storage state (cookies + localStorage)
  await context.storageState({ path: STORAGE_STATE });

  await browser.close();
}
