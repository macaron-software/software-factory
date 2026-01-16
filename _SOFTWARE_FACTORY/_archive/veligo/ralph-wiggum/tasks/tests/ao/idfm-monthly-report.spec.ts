import { test, expect } from '@playwright/test';

test.describe('AO-IDFM-004: Reporting Mensuel IDFM', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/reports/idfm');
  });

  test('DEV-001: Accès à la page de reporting mensuel IDFM', async ({ page }) => {
    await expect(page.locator('[data-testid="idfm-monthly-report-title"]')).toBeVisible();
  });

  test('DEV-002: Affichage du résumé des revenus', async ({ page }) => {
    await expect(page.locator('[data-testid="total-revenue"]')).toBeVisible();
  });

  test('DEV-003: Affichage du tableau des transactions', async ({ page }) => {
    await expect(page.locator('[data-testid="transactions-table"]')).toBeVisible();
  });

  test('DEV-004: Filtrage par période fonctionne', async ({ page }) => {
    const monthFilter = page.locator('[data-testid="month-filter"]');
    await expect(monthFilter).toBeVisible();
    await monthFilter.click();
    await page.locator('[data-testid="month-option-12"]').click();
    await expect(page.locator('[data-testid="transactions-table"]')).toBeVisible();
  });

  test('DEV-005: Export CSV disponible', async ({ page }) => {
    await expect(page.locator('[data-testid="export-csv-btn"]')).toBeVisible();
  });
});