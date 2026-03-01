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
  const ipBase = rawBase.replace("localhost", "127.0.0.1");
  const hostname = new URL(rawBase).hostname;

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Authenticate via demo endpoint (IP to avoid IPv6 issues)
  const resp = await page.request.post(`${ipBase}/api/auth/demo`);

  // Extract session cookie and duplicate it for all relevant domains
  const cookies = await context.cookies();
  const sessionCookies = cookies.filter(
    (c) => c.name === "access_token" || c.name === "refresh_token" || c.name === "session" || c.name.startsWith("sf_")
  );
  if (sessionCookies.length > 0 && hostname !== "127.0.0.1") {
    // Add the same session cookies for the actual hostname (localhost, sf.macaron-software.com, etc.)
    await context.addCookies(sessionCookies.map((c) => ({ ...c, domain: hostname })));
  }

  // Set onboarding cookie to bypass redirect
  await context.addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);

  // Save storage state (cookies + localStorage)
  await context.storageState({ path: STORAGE_STATE });

  await browser.close();
}
