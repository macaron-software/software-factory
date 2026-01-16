import { test, expect } from '@playwright/test';
import { users, stations, bikes } from '../fixtures/test-data';

test.describe('J-E2E-009: Réservation vélo avec géolocalisation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('DEV-001: Géolocalisation demandée au chargement', async ({ page }) => {
    await expect(page.locator('[data-testid="geolocation-prompt"]')).toBeVisible();
  });

  test('DEV-002: Acceptation géolocalisation', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    
    await expect(page.locator('[data-testid="nearby-stations"]')).toBeVisible();
  });

  test('DEV-003: Stations triées par distance', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    
    const stations = await page.locator('[data-testid="station-card"]').all();
    expect(stations.length).toBeGreaterThan(0);
    
    const distances = await page.locator('[data-testid="station-distance"]').allTextContents();
    const sortedDistances = [...distances].sort((a, b) => parseFloat(a) - parseFloat(b));
    expect(distances).toEqual(sortedDistances);
  });

  test('DEV-004: Sélection station affiche vélos disponibles', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    await page.click('[data-testid="station-card"]:first-child');
    
    await expect(page.locator('[data-testid="available-bikes"]')).toBeVisible();
  });

  test('DEV-005: Réservation vélo électrique', async ({ page }) => {
    const availableBike = bikes.find(b => b.status === 'available' && b.type === 'electric');
    
    await page.click('[data-testid="accept-geolocation"]');
    await page.click('[data-testid="station-card"]:first-child');
    await page.click(`[data-testid="bike-${availableBike.id}"]`);
    await page.click('[data-testid="reserve-button"]');
    
    await expect(page.locator('[data-testid="reservation-success"]')).toBeVisible();
    await expect(page.locator('[data-testid="reservation-timer"]')).toBeVisible();
  });

  test('DEV-006: Code retrait généré', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    await page.click('[data-testid="station-card"]:first-child');
    await page.click('[data-testid="bike-IDFM-VAE-001"]');
    await page.click('[data-testid="reserve-button"]');
    
    const code = await page.locator('[data-testid="pickup-code"]').textContent();
    expect(code).toMatch(/^[A-Z0-9]{6}$/);
  });

  test('DEV-007: Timer décompte 15 minutes', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    await page.click('[data-testid="station-card"]:first-child');
    await page.click('[data-testid="bike-IDFM-VAE-001"]');
    await page.click('[data-testid="reserve-button"]');
    
    await expect(page.locator('[data-testid="reservation-timer"]')).toContainText('15:00');
  });

  test('DEV-008: Pas de vélos disponibles', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    await page.click('[data-testid="station-card"]:first-child');
    
    const bikes = await page.locator('[data-testid="available-bike"]').all();
    if (bikes.length === 0) {
      await expect(page.locator('[data-testid="no-bikes-message"]')).toBeVisible();
    }
  });

  test('DEV-009: Géolocalisation refusée - stations par défaut', async ({ page }) => {
    await page.click('[data-testid="deny-geolocation"]');
    
    await expect(page.locator('[data-testid="default-stations"]')).toBeVisible();
    await expect(page.locator('[data-testid="station-card"]').first()).toBeVisible();
  });

  test('DEV-010: Erreur GPS timeout', async ({ page }) => {
    await page.click('[data-testid="accept-geolocation"]');
    await page.waitForTimeout(60000);
    
    await expect(page.locator('[data-testid="gps-timeout-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="retry-geolocation"]')).toBeEnabled();
  });
});
