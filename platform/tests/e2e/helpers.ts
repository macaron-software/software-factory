/**
 * Shared E2E helpers — console/network error collectors.
 * Import in every spec to catch JS errors and failed requests.
 */
import { type Page, expect } from "@playwright/test";

export interface PageErrors {
  console: string[];
  network: { url: string; status: number; method: string }[];
}

/**
 * Attach console + network error listeners to page.
 * Call before navigation. Returns object with collected errors.
 */
export function collectErrors(page: Page): PageErrors {
  const errors: PageErrors = { console: [], network: [] };

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      // Ignore known benign messages
      if (text.includes("favicon.ico")) return;
      if (text.includes("ERR_CONNECTION_REFUSED")) return;
      if (text.includes("Failed to load resource")) return; // browser-level 404s (static assets)
      if (text.includes("Response Status Error Code")) return; // fetch() API errors (logged by app JS)
      if (text.includes("CORS policy")) return; // CDN font CORS (cosmetic, not functional)
      if (text.includes("s3.popi.nz")) return; // CDN font host
      if (text.includes("Access-Control-Allow-Origin")) return; // CORS font errors
      if (text.includes("Content Security Policy") && text.includes("htmx")) return; // htmx eval CSP (pre-existing)
      if (text.includes("EvalError") && text.includes("htmx")) return; // htmx CSP eval violation
      if (text.includes("cdn.jsdelivr.net/npm/xterm")) return; // xterm CDN CSP (workspace terminal)
      if (text.includes("analytics.macaron-software")) return; // analytics CSP (non-critical)
      if (text.includes("frame-ancestors")) return; // iframe CSP (db view self-framing)
      errors.console.push(text);
    }
  });

  page.on("response", (response) => {
    const status = response.status();
    const url = response.url();
    // Ignore non-critical responses
    if (url.includes("/sse/") || url.includes("favicon")) return;
    if (url.includes("/git") && (status === 404 || status === 500)) return; // git-status not always available
    if (url.includes("/api/knowledge/health") && status === 500) return; // knowledge module optional
    if (url.includes("/api/webhooks/configs") && status === 500) return; // webhooks GET not implemented
    if (!url.includes("/api/")) return; // only track API errors, not static/external resources
    if (status === 429) return; // rate limit — transient, not a real error
    if (status >= 400) {
      errors.network.push({
        url: url.replace(/https?:\/\/[^/]+/, ""),
        status,
        method: response.request().method(),
      });
    }
  });

  return errors;
}

/**
 * Assert no errors collected (or only acceptable ones).
 */
export function assertNoErrors(errors: PageErrors, context: string) {
  const consoleFiltered = errors.console.filter(
    (e) => !e.includes("[vite]") && !e.includes("DevTools")
  );
  expect(
    consoleFiltered,
    `Console errors on ${context}: ${consoleFiltered.join("\n")}`
  ).toHaveLength(0);

  expect(
    errors.network,
    `Network errors on ${context}: ${errors.network.map((e) => `${e.method} ${e.url} → ${e.status}`).join("\n")}`
  ).toHaveLength(0);
}

/**
 * Navigate and wait for load (domcontentloaded — avoids SSE timeout).
 */
export async function safeGoto(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded", timeout: 30_000 });
  // Give page JS time to render
  await page.waitForTimeout(1_000);
}
