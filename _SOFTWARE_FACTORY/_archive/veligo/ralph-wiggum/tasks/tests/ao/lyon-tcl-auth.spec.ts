import { test, expect } from '@playwright/test';

test.describe('AO-LYON-001: Authentification TCL ID', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('DEV-001: Bouton TCL sur page login tenant Lyon', async ({ page }) => {
    await expect(page.locator('[data-testid="tcl-login-btn"]')).toBeVisible();
  });

  test('DEV-002: Redirect vers portail TCL', async ({ page }) => {
    await page.click('[data-testid="tcl-login-btn"]');
    
    await expect(page).toHaveURL(/tcl\.sytral\.fr/);
  });

  test('DEV-003: Callback TCL avec token', async ({ page }) => {
    await page.goto('/auth/tcl/callback?token=TOKEN_123');
    
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('DEV-004: Abonnement TCL vérifié via API', async ({ page }) => {
    await page.goto('/auth/tcl/callback?token=VALID_TOKEN');
    
    await expect(page.locator('[data-testid="tcl-subscription-ok"]')).toBeVisible();
  });

  test('DEV-005: Échec pas dabonnement TCL actif', async ({ page }) => {
    await page.goto('/auth/tcl/callback?token=NO_SUBSCRIPTION');
    
    await expect(page.locator('[data-testid="tcl-error"]')).toContainText('Abonnement TCL requis');
  });

  test('DEV-006: Intégration tarif multimodal TCL', async ({ page }) => {
    await page.goto('/dashboard');
    
    await expect(page.locator('[data-testid="tcl-tariff"]')).toBeVisible();
  });

  test('DEV-007: Correspondence transport reconnue', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="nearby-stations"]');
    
    await expect(page.locator('[data-testid="tcl-connections"]')).toBeVisible();
  });

  test('DEV-008: Reporting TCL mensuel automatique', async ({ page }) => {
    await page.goto('/admin/reports');
    
    await expect(page.locator('[data-testid="tcl-monthly-report"]')).toBeVisible();
    await expect(page.locator('[data-testid="tcl-export-btn"]')).toBeEnabled();
  });
});
