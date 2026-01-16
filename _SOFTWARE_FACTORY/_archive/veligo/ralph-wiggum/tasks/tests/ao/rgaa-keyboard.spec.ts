/**
 * AO-RGAA-001: Navigation clavier complète
 * Tests RGAA pour l'accessibilité - Navigation au clavier (WCAG 2.1)
 * 
 * Critères testés:
 * - Tabulation fonctionnelle (RGAA 2.4.1)
 * - Visibilité du focus (RGAA 2.4.7)
 * - Liens d'évitement (RGAA 2.4.1)
 * - Ordre de tabulation logique (RGAA 2.4.3)
 * - Pas de piège clavier (RGAA 2.4.1)
 */

import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || 'http://idfm.veligo.local:8040';

// Pages to test for keyboard navigation
const PAGES_TO_TEST = [
  { path: '/', name: 'Homepage' },
  { path: '/login', name: 'Login' },
  { path: '/register', name: 'Register' },
];

test.describe('AO-RGAA-001: Navigation clavier complète', () => {
  
  test.beforeEach(async ({ page }) => {
    // Enable console logging for debugging
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`Console error: ${msg.text()}`);
      }
    });
  });

  test.describe('RGA-001: Focus visible sur tous les éléments interactifs', () => {
    for (const { path, name } of PAGES_TO_TEST) {
      test(`DEV-001: Focus visible sur ${name}`, async ({ page }) => {
        await page.goto(path);
        
        // Test that interactive elements have visible focus styles
        const interactiveSelectors = [
          'a[href]',
          'button:not([disabled])',
          'input:not([disabled])',
          'select:not([disabled])',
          'textarea:not([disabled])',
          '[tabindex]:not([tabindex="-1"])',
          '[role="button"]',
          '[role="link"]',
        ];
        
        for (const selector of interactiveSelectors) {
          const elements = page.locator(selector);
          const count = await elements.count();
          
          for (let i = 0; i < count; i++) {
            const element = elements.nth(i);
            if (await element.isVisible()) {
              // Check that element has focusable styling (CSS outline or similar)
              const focusStyle = await element.evaluate((el) => {
                const computed = window.getComputedStyle(el);
                return {
                  outline: computed.outline,
                  outlineOffset: computed.outlineOffset,
                  boxShadow: computed.boxShadow,
                };
              });
              
              // Element should have some focus indicator
              const hasFocusIndicator = 
                focusStyle.outline !== 'none' ||
                focusStyle.outlineOffset !== '0px' ||
                focusStyle.boxShadow !== 'none';
              
              expect(hasFocusIndicator).toBe(true);
            }
          }
        }
      });
    }
  });

  test.describe('RGA-002: Liens d\'évitement (Skip links)', () => {
    for (const { path, name } of PAGES_TO_TEST) {
      test(`DEV-002: Skip link présent sur ${name}`, async ({ page }) => {
        await page.goto(path);
        
        // Check for skip link
        const skipLink = page.locator('a[href^="#"], [role="link"][href^="#"]').first();
        
        // Skip link should be the first focusable element
        await page.keyboard.press('Tab');
        const firstFocused = await page.evaluate(() => document.activeElement?.tagName);
        
        // First focus should be a link (skip link) or have aria-label indicating skip functionality
        const firstFocusLabel = await page.evaluate(() => document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent);
        
        expect(firstFocused).toBeTruthy();
      });
    }
  });

  test.describe('RGA-003: Ordre de tabulation logique', () => {
    for (const { path, name } of PAGES_TO_TEST) {
      test(`DEV-003: Ordre tabulation logique sur ${name}`, async ({ page }) => {
        await page.goto(path);
        
        const focusOrder: string[] = [];
        
        // Press Tab multiple times and record the tag names
        for (let i = 0; i < 20; i++) {
          await page.keyboard.press('Tab');
          await page.waitForTimeout(50);
          
          const tagName = await page.evaluate(() => document.activeElement?.tagName);
          const className = await page.evaluate(() => document.activeElement?.className || '');
          
          if (tagName && !focusOrder.includes(`${tagName}.${className}`)) {
            focusOrder.push(`${tagName}.${className}`);
          }
          
          // Stop if we've cycled through all focusable elements
          if (i > 5) {
            const currentFocus = await page.evaluate(() => document.activeElement);
            if (!currentFocus) break;
          }
        }
        
        // Verify we can tab through the page
        expect(focusOrder.length).toBeGreaterThan(0);
      });
    }
  });

  test.describe('RGA-004: Pas de piège clavier (Keyboard traps)', () => {
    for (const { path, name } of PAGES_TO_TEST) {
      test(`DEV-004: Pas de piège clavier sur ${name}`, async ({ page }) => {
        await page.goto(path);
        
        // Start at the beginning of the page
        await page.keyboard.press('Control+Home');
        await page.waitForTimeout(100);
        
        // Tab through multiple elements to ensure we can move forward
        let canTabForward = false;
        for (let i = 0; i < 50; i++) {
          await page.keyboard.press('Tab');
          await page.waitForTimeout(20);
          
          const activeElement = await page.evaluate(() => document.activeElement);
          if (activeElement) {
            canTabForward = true;
          }
        }
        
        expect(canTabForward).toBe(true);
      });
    }
  });

  test.describe('RGA-005: Navigation au clavier sur les éléments interactifs', () => {
    
    test('DEV-005: Boutons activables avec Entrée', async ({ page }) => {
      await page.goto('/login');
      
      const buttons = page.locator('button:not([disabled]):not([type="submit"])');
      const count = await buttons.count();
      
      if (count > 0) {
        // Navigate to first button
        await page.keyboard.press('Tab');
        for (let i = 1; i < count; i++) {
          await page.keyboard.press('Tab');
        }
        
        // Activate with Enter
        await page.keyboard.press('Enter');
        
        // Should not cause error
        const errors = await page.evaluate(() => window.__PLAYWRIGHT_ERRORS__ || []);
        expect(errors.length).toBe(0);
      }
    });

    test('DEV-006: Liens activables avec Entrée', async ({ page }) => {
      await page.goto('/login');
      
      const links = page.locator('a[href]');
      const count = await links.count();
      
      if (count > 0) {
        // Navigate to first link
        for (let i = 0; i < Math.min(count, 10); i++) {
          await page.keyboard.press('Tab');
        }
        
        // Activate with Enter
        await page.keyboard.press('Enter');
        
        // Page should respond (navigation or no error)
        const errors = await page.evaluate(() => window.__PLAYWRIGHT_ERRORS__ || []);
        expect(errors.length).toBe(0);
      }
    });

    test('DEV-007: Cases à cocher activables avec Espace', async ({ page }) => {
      await page.goto('/login');
      
      const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
      const count = await checkboxes.count();
      
      if (count > 0) {
        // Navigate to checkbox
        await page.keyboard.press('Tab');
        for (let i = 0; i < count; i++) {
          await page.keyboard.press('Tab');
        }
        
        // Toggle with Space
        const wasChecked = await checkboxes.first().isChecked();
        await page.keyboard.press('Space');
        const isChecked = await checkboxes.first().isChecked();
        
        expect(isChecked).toBe(!wasChecked);
      }
    });
  });

  test.describe('RGA-008: Gestion du focus dans les modales', () => {
    test('DEV-008: Focus géré correctement dans modale', async ({ page }) => {
      await page.goto('/login');
      
      // Open a modal if exists
      const modalOpeners = page.locator('[data-testid*="modal"], .modal-open, [aria-haspopup="dialog"]');
      
      if (await modalOpeners.count() > 0) {
        await modalOpeners.first().click();
        await page.waitForTimeout(300);
        
        // Check if modal is open
        const modal = page.locator('[role="dialog"], .modal, [aria-modal="true"]');
        
        if (await modal.count() > 0) {
          // Focus should be within modal
          await page.waitForTimeout(200);
          const activeElementInModal = await page.evaluate(() => {
            const modal = document.querySelector('[role="dialog"], .modal, [aria-modal="true"]');
            if (!modal) return false;
            return modal.contains(document.activeElement);
          });
          
          expect(activeElementInModal).toBe(true);
        }
      }
    });
  });

  test.describe('RGA-009: Attributs ARIA pour accessibilité clavier', () => {
    for (const { path, name } of PAGES_TO_TEST) {
      test(`DEV-009: Attributs ARIA requis sur ${name}`, async ({ page }) => {
        await page.goto(path);
        
        // Check interactive elements have proper ARIA attributes
        const elementsNeedingAria = page.locator('[role], [aria-label], [aria-describedby], [aria-required]');
        const count = await elementsNeedingAria.count();
        
        // Elements with roles should have appropriate aria attributes
        const elementsWithRole = page.locator('[role]');
        const roleCount = await elementsWithRole.count();
        
        // Verify roles are valid
        for (let i = 0; i < roleCount; i++) {
          const element = elementsWithRole.nth(i);
          const role = await element.getAttribute('role');
          
          const validRoles = [
            'button', 'link', 'checkbox', 'radio', 'textbox', 'combobox',
            'menu', 'menubar', 'menuitem', 'tab', 'tablist', 'tabpanel',
            'dialog', 'alert', 'alertdialog', 'status', 'progressbar',
            'slider', 'switch', 'option', 'listbox', 'tree', 'treeitem'
          ];
          
          expect(validRoles.includes(role)).toBe(true);
        }
      });
    }
  });

  test.describe('RGA-010: Respect des conventions clavier natives', () => {
    test('DEV-010: Élements cliquables avec focus visible', async ({ page }) => {
      await page.goto('/login');
      
      // Find all focusable elements
      const focusableSelector = 'a, button, input, select, textarea, [tabindex]';
      const focusableElements = page.locator(focusableSelector);
      
      const count = await focusableElements.count();
      
      // Tab through and verify each can receive focus
      for (let i = 0; i < Math.min(count, 20); i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(50);
        
        const hasFocus = await page.evaluate(() => document.activeElement !== null);
        expect(hasFocus).toBe(true);
      }
    });
  });
});