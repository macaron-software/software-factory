import { test, expect } from '@playwright/test';

test.describe('AO-NANTES-001: Paiement PayNum wallet', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/payment');
  });

  test('DEV-001: Option PayNum dans moyens de paiement', async ({ page }) => {
    await expect(page.locator('[data-testid="paynum-option"]')).toBeVisible();
  });

  test('DEV-002: Redirect vers wallet PayNum', async ({ page }) => {
    await page.click('[data-testid="paynum-option"]');
    
    await expect(page).toHaveURL(/paynum\.fr\/wallet/);
  });

  test('DEV-003: Callback PayNum avec transaction ID', async ({ page }) => {
    await page.goto('/payment/paynum/callback?tx_id=PAYNUM_123&status=success');
    
    await expect(page.locator('[data-testid="payment-success"]')).toBeVisible();
  });

  test('DEV-004: Échec paiement PayNum', async ({ page }) => {
    await page.goto('/payment/paynum/callback?tx_id=PAYNUM_123&status=failed');
    
    await expect(page.locator('[data-testid="payment-failed"]')).toBeVisible();
    await expect(page.locator('[data-testid="retry-paynum"]')).toBeEnabled();
  });

  test('DEV-005: Remboursement via PayNum', async ({ page }) => {
    await page.goto('/admin/refunds');
    await page.click('[data-testid="refund-paynum-btn"]');
    
    await expect(page.locator('[data-testid="refund-success"]')).toBeVisible();
  });

  test('DEV-006: Box Nantes sécurisée disponible', async ({ page }) => {
    await page.goto('/dashboard');
    
    await expect(page.locator('[data-testid="nantes-box"]')).toBeVisible();
  });

  test('DEV-007: Réservation box sécurisée', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="nantes-box"]');
    await page.click('[data-testid="reserve-box"]');
    
    await expect(page.locator('[data-testid="box-reservation-success"]')).toBeVisible();
  });

  test('DEV-008: Accès box via code', async ({ page }) => {
    await page.goto('/box/access');
    await page.fill('[data-testid="access-code"]', 'BOX1234');
    await page.click('[data-testid="open-box"]');
    
    await expect(page.locator('[data-testid="box-opened"]')).toBeVisible();
  });
});
