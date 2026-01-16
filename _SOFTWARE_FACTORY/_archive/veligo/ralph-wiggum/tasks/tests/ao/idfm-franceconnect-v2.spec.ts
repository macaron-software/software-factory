import { test, expect } from '@playwright/test';

test.describe('AO-IDFM-001: Authentification FranceConnect v2', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('DEV-001: Bouton FranceConnect sur page login', async ({ page }) => {
    await expect(page.locator('[data-testid="franceconnect-btn"]')).toBeVisible();
  });

  test('DEV-002: Redirect vers FranceConnect', async ({ page }) => {
    await page.click('[data-testid="franceconnect-btn"]');
    
    await expect(page).toHaveURL(/franceconnect\.gouv\.fr/);
  });

  test('DEV-003: Callback avec code authorization', async ({ page }) => {
    await page.goto('/auth/franceconnect/callback?code=AUTH_CODE_123');
    
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('DEV-004: Utilisateur créé après premier login FC', async ({ page }) => {
    await page.goto('/auth/franceconnect/callback?code=NEW_USER_CODE');
    
    await expect(page.locator('[data-testid="welcome-message"]')).toContainText('Bienvenue');
  });

  test('DEV-005: Login FC utilisateur existant', async ({ page }) => {
    await page.goto('/auth/franceconnect/callback?code=EXISTING_USER_CODE');
    
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator('[data-testid="user-name"]')).toBeVisible();
  });

  test('DEV-006: Échec token FC expiré', async ({ page }) => {
    await page.goto('/auth/franceconnect/callback?error=access_denied');
    
    await expect(page.locator('[data-testid="fc-error"]')).toBeVisible();
  });

  test('DEV-007: Scope FC données personnelles', async ({ page }) => {
    await page.click('[data-testid="franceconnect-btn"]');
    
    const fcUrl = page.url();
    expect(fcUrl).toContain('scope=openid%20profile%20email%20address%20phone');
  });

  test('DEV-008: Revoke token FC', async ({ page }) => {
    await page.goto('/settings/security');
    await page.click('[data-testid="revoke-franceconnect"]');
    await page.click('[data-testid="confirm-revoke"]');
    
    await expect(page.locator('[data-testid="fc-revoked"]')).toBeVisible();
  });
});
