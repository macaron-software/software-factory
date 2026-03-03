import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const ARTIFACT_DIR = path.join(process.cwd(), 'artifacts');
const SCREENSHOT = path.join(ARTIFACT_DIR, 'screenshots', 'world.png');
const CONSOLE_LOG = path.join(ARTIFACT_DIR, 'console', 'world.log');
const HAR_PATH = path.join(ARTIFACT_DIR, 'network', 'world.har');
const TRACE_PATH = path.join(ARTIFACT_DIR, 'traces', 'world.zip');
const FAILED_REQS = path.join(ARTIFACT_DIR, 'requests', 'world_failed.json');

function ensureDirs() {
  [
    path.join(ARTIFACT_DIR, 'screenshots'),
    path.join(ARTIFACT_DIR, 'console'),
    path.join(ARTIFACT_DIR, 'network'),
    path.join(ARTIFACT_DIR, 'traces'),
    path.join(ARTIFACT_DIR, 'requests'),
  ].forEach(d => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

test('world page should not emit js-error and three.module stack', async ({ browser }) => {
  ensureDirs();

  const failedRequests: any[] = [];
  const consoleErrors: string[] = [];

  const context = await browser.newContext({
    recordHar: { path: HAR_PATH },
  });

  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();

  page.on('requestfailed', request => {
    failedRequests.push({ url: request.url(), method: request.method(), failure: request.failure()?.errorText });
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = `${new Date().toISOString()} [${msg.type()}] ${msg.text()}`;
      consoleErrors.push(text);
    }
  });

  // navigation and wait
  await page.goto('http://localhost:8099/world', { waitUntil: 'networkidle', timeout: 60000 });

  // allow a short time for async console errors to appear
  await page.waitForTimeout(2000);

  // screenshot
  await page.screenshot({ path: SCREENSHOT, fullPage: true });

  // stop tracing and save
  await context.tracing.stop({ path: TRACE_PATH });

  // write console errors and failed requests
  fs.writeFileSync(CONSOLE_LOG, consoleErrors.join('\n'));
  fs.writeFileSync(FAILED_REQS, JSON.stringify(failedRequests, null, 2));

  // basic assertions: no console errors
  if (consoleErrors.length > 0) {
    // attach console to test output
    console.log('Console errors captured:\n', consoleErrors.join('\n'));
  }

  expect(consoleErrors.length).toBe(0);

  // ensure HAR exists
  expect(fs.existsSync(HAR_PATH)).toBeTruthy();

  // ensure screenshot exists
  expect(fs.existsSync(SCREENSHOT)).toBeTruthy();

  // cleanup
  await context.close();
});
