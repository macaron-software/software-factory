import { test, expect } from '@playwright/test';

test.describe('Agents page', () => {
  test('loads agents list', async ({ page }) => {
    await page.goto('/agents');
    await expect(page.locator('body')).toContainText(/agent/i);
  });

  test('agents API returns data', async ({ request }) => {
    const response = await request.get('/api/agents');
    expect(response.status()).toBe(200);
    const agents = await response.json();
    expect(Array.isArray(agents)).toBeTruthy();
    expect(agents.length).toBeGreaterThan(0);
  });

  test('each agent has required fields', async ({ request }) => {
    const response = await request.get('/api/agents');
    const agents = await response.json();
    for (const agent of agents.slice(0, 5)) {
      expect(agent).toHaveProperty('name');
      expect(agent).toHaveProperty('role');
    }
  });
});
