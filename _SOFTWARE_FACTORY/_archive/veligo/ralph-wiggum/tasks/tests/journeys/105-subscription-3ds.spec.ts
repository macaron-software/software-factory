import { test, expect } from '@playwright/test';
import { users, plans } from '../fixtures/test-data';

test.describe('J-E2E-005: Souscription avec paiement CB 3D Secure', () => {
  let testUser: { email: string; password: string };

  test.beforeAll(async () => {
    testUser = {
      email: `test.3ds.${Date.now()}@veligo.app`,
      password: 'SecurePass123!'
    };
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/subscription');
  });

  test('DEV-001: Sélection plan Standard', async ({ page }) => {
    const standardPlan = plans.find(p => p.id === 'standard');
    
    await page.click(`[data-testid="plan-${standardPlan.id}"]`);
    
    await expect(page.locator('[data-testid="selected-plan"]')).toContainText(standardPlan.name);
    await expect(page.locator('[data-testid="plan-price"]')).toContainText(`${standardPlan.price}€`);
  });

  test('DEV-002: Navigation vers paiement après sélection plan', async ({ page }) => {
    await page.click('[data-testid="plan-standard"]');
    await page.click('[data-testid="continue-to-payment"]');
    
    await expect(page).toHaveURL(/\/payment/);
    await expect(page.locator('[data-testid="card-number-input"]')).toBeVisible();
  });

  test('DEV-003: Paiement CB 3D Secure redirect', async ({ page }) => {
    await page.fill('[data-testid="card-number-input"]', '4000000000000002');
    await page.fill('[data-testid="card-expiry-input"]', '12/26');
    await page.fill('[data-testid="card-cvc-input"]', '123');
    
    await page.click('[data-testid="pay-button"]');
    
    await expect(page).toHaveURL(/3d-secure/);
    await expect(page.locator('[data-testid="secure-badge"]')).toBeVisible();
  });

  test('DEV-004: Succès paiement après validation 3DS', async ({ page }) => {
    await page.goto('/payment/success');
    
    await expect(page.locator('[data-testid="payment-success"]')).toBeVisible();
    await expect(page.locator('[data-testid="subscription-active"]')).toBeVisible();
  });

  test('DEV-005: Échec carte expirée', async ({ page }) => {
    await page.fill('[data-testid="card-number-input"]', '4000000000000000');
    await page.fill('[data-testid="card-expiry-input"]', '01/20');
    await page.fill('[data-testid="card-cvc-input"]', '123');
    
    await page.click('[data-testid="pay-button"]');
    
    await expect(page.locator('[data-testid="card-expired-error"]')).toBeVisible();
  });

  test('DEV-006: Échec carte refusée', async ({ page }) => {
    await page.fill('[data-testid="card-number-input"]', '4000000000000001');
    await page.fill('[data-testid="card-expiry-input"]', '12/26');
    await page.fill('[data-testid="card-cvc-input"]', '123');
    
    await page.click('[data-testid="pay-button"]');
    
    await expect(page.locator('[data-testid="card-declined-error"]')).toBeVisible();
  });

  test('DEV-007: Création subscription en base', async ({ page }) => {
    await page.goto('/payment/success');
    
    const subscriptionId = await page.locator('[data-testid="subscription-id"]').textContent();
    
    expect(subscriptionId).toMatch(/^sub_/);
  });

  test('DEV-008: Accèsbike après subscription active', async ({ page }) => {
    await page.goto('/dashboard');
    
    await expect(page.locator('[data-testid="book-bike-btn"]')).toBeEnabled();
    await expect(page.locator('[data-testid="subscription-badge"]')).toContainText('Active');
  });
});
