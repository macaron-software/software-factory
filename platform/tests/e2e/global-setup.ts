/**
 * Playwright global setup — authenticate once via /api/auth/demo
 * and save storage state for all test files to reuse.
 */
import { chromium, FullConfig } from "@playwright/test";
import * as http from "http";
import * as https from "https";
import * as path from "path";

export const STORAGE_STATE = path.join(__dirname, ".auth-state.json");

/** Make a raw HTTP POST and return all Set-Cookie header values. */
function postAndGetCookies(url: string): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const lib = parsed.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: parsed.pathname,
        method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": 0 },
      },
      (res) => {
        // Drain response body
        res.resume();
        const raw = res.headers["set-cookie"] ?? [];
        resolve(Array.isArray(raw) ? raw : [raw]);
      }
    );
    req.on("error", reject);
    req.end();
  });
}

/** Parse "name=value; ..." into {name, value} */
function parseCookieHeader(header: string): { name: string; value: string } | null {
  const eq = header.indexOf("=");
  if (eq === -1) return null;
  const semi = header.indexOf(";");
  const name = header.slice(0, eq).trim();
  const value = header.slice(eq + 1, semi === -1 ? undefined : semi).trim();
  return { name, value };
}

export default async function globalSetup(_config: FullConfig) {
  const rawBase = process.env.BASE_URL || "http://localhost:8090";
  // Use 127.0.0.1 to avoid IPv6 ECONNREFUSED on Node, but store cookies for hostname
  const ipBase = rawBase.replace("localhost", "127.0.0.1");
  const hostname = new URL(rawBase).hostname;

  // ── 1. Raw HTTP POST → extract Set-Cookie headers directly ────────────────
  const setCookieHeaders = await postAndGetCookies(`${ipBase}/api/auth/demo`);

  // ── 2. Parse token cookies ─────────────────────────────────────────────────
  const authCookies = setCookieHeaders
    .map(parseCookieHeader)
    .filter((c): c is { name: string; value: string } =>
      c !== null &&
      (c.name === "access_token" || c.name === "refresh_token" || c.name === "session" || c.name.startsWith("sf_"))
    );

  // ── 3. Build Playwright browser context with correct cookies ───────────────
  const browser = await chromium.launch();
  const context = await browser.newContext();

  if (authCookies.length > 0) {
    await context.addCookies(
      authCookies.map((c) => ({
        name: c.name,
        value: c.value,
        domain: hostname,
        path: "/",
        httpOnly: true,
        sameSite: "Lax" as const,
      }))
    );
  }

  // Set onboarding cookie to bypass first-run redirect
  await context.addCookies([
    { name: "onboarding_done", value: "1", domain: hostname, path: "/" },
  ]);

  // ── 4. Save storage state ──────────────────────────────────────────────────
  await context.storageState({ path: STORAGE_STATE });
  await browser.close();

  const names = authCookies.map((c) => c.name).join(", ");
  console.log(`[global-setup] Auth cookies captured: [${names || "none"}] → ${STORAGE_STATE}`);
}
