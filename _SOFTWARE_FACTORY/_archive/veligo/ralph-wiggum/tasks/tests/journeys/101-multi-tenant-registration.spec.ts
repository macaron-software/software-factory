import { test, expect } from '@playwright/test';
import { tenants, users } from '../fixtures/test-data';

test.describe('J-E2E-001: Inscription multi-tenant avec validation email', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register');
  });

  test('DEV-001: Inscription utilisateur tenant IDFM', async ({ page }) => {
    const idfmTenant = tenants.find(t => t.slug === 'idfm');
    await page.selectOption('[data-testid="tenant-select"]', idfmTenant.id);
    
    await page.fill('[data-testid="email"]', 'marie.dupont@test-idfm.fr');
    await page.fill('[data-testid="password"]', 'SecurePass123!');
    await page.fill('[data-testid="firstName"]', 'Marie');
    await page.fill('[data-testid="lastName"]', 'Dupont');
    await page.fill('[data-testid="phone"]', '0612345678');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page).toHaveURL(/\/email-verification/);
    await expect(page.locator('[data-testid="verification-sent"]')).toBeVisible();
  });

  test('DEV-002: Inscription utilisateur tenant Nantes', async ({ page }) => {
    const nantesTenant = tenants.find(t => t.slug === 'nantes');
    await page.selectOption('[data-testid="tenant-select"]', nantesTenant.id);
    
    await page.fill('[data-testid="email"]', 'jean.martin@test-nantes.fr');
    await page.fill('[data-testid="password"]', 'SecurePass123!');
    await page.fill('[data-testid="firstName"]', 'Jean');
    await page.fill('[data-testid="lastName"]', 'Martin');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page.locator('[data-testid="verification-sent"]')).toContainText(nantesTenant.name);
  });

  test('DEV-003: Inscription utilisateur tenant Lyon', async ({ page }) => {
    const lyonTenant = tenants.find(t => t.slug === 'lyon');
    await page.selectOption('[data-testid="tenant-select"]', lyonTenant.id);
    
    await page.fill('[data-testid="email"]', 'pierre.bernard@test-lyon.fr');
    await page.fill('[data-testid="password"]', 'SecurePass123!');
    await page.fill('[data-testid="firstName"]', 'Pierre');
    await page.fill('[data-testid="lastName"]', 'Bernard');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page).toHaveURL(/\/email-verification/);
  });

  test('DEV-004: Validation email avec code 6 chiffres', async ({ page }) => {
    await page.goto('/email-verification');
    
    await page.fill('[data-testid="code-digit-1"]', '1');
    await page.fill('[data-testid="code-digit-2"]', '2');
    await page.fill('[data-testid="code-digit-3"]', '3');
    await page.fill('[data-testid="code-digit-4"]', '4');
    await page.fill('[data-testid="code-digit-5"]', '5');
    await page.fill('[data-testid="code-digit-6"]', '6');
    
    await page.click('[data-testid="verify-code"]');
    
    await expect(page).toHaveURL(/\/onboarding/);
  });

  test('DEV-005: Code de validation expiré après 10 min', async ({ page }) => {
    await page.goto('/email-verification');
    
    await page.fill('[data-testid="code-digit-1"]', '1');
    await page.fill('[data-testid="code-digit-2"]', '2');
    await page.fill('[data-testid="code-digit-3"]', '3');
    await page.fill('[data-testid="code-digit-4"]', '4');
    await page.fill('[data-testid="code-digit-5"]', '5');
    await page.fill('[data-testid="code-digit-6"]', '6');
    
    await page.click('[data-testid="verify-code"]');
    
    await expect(page.locator('[data-testid="code-expired-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="resend-code"]')).toBeEnabled();
  });

  test('DEV-006: Email déjà utilisé', async ({ page }) => {
    await page.goto('/register');
    
    await page.fill('[data-testid="email"]', users.USER_IDFM.email);
    await page.fill('[data-testid="password"]', 'SecurePass123!');
    await page.fill('[data-testid="firstName"]', 'Test');
    await page.fill('[data-testid="lastName"]', 'User');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page.locator('[data-testid="email-exists-error"]')).toContainText('Email déjà enregistré');
  });

  test('DEV-007: Mot de passe trop faible', async ({ page }) => {
    await page.goto('/register');
    
    await page.fill('[data-testid="email"]', 'test@test.fr');
    await page.fill('[data-testid="password"]', '123');
    await page.fill('[data-testid="firstName"]', 'Test');
    await page.fill('[data-testid="lastName"]', 'User');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page.locator('[data-testid="password-error"]')).toContainText('Mot de passe insuffisant');
  });

  test('DEV-008: Tenant inexistant', async ({ page }) => {
    await page.goto('/register');
    
    await page.selectOption('[data-testid="tenant-select"]', 'tenant-inexistant');
    await page.fill('[data-testid="email"]', 'test@test.fr');
    await page.fill('[data-testid="password"]', 'SecurePass123!');
    await page.fill('[data-testid="firstName"]', 'Test');
    await page.fill('[data-testid="lastName"]', 'User');
    
    await page.click('[data-testid="submit-registration"]');
    
    await expect(page.locator('[data-testid="tenant-error"]')).toBeVisible();
  });
});
