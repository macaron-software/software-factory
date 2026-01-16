# TDD-009: Standardisation Error Handling Tests

**Anomalie:** #9 - Gestion d'Erreurs Non Standardisée dans Tests  
**Priorité:** P2  
**Fichiers:** Tous les fichiers tests E2E

## 🎯 Objectif

Remplacer les `.catch(() => false)` et try/catch silencieux par une gestion d'erreurs standardisée.

## 📋 Tasks Détaillées

### Phase 1: Audit Error Handling

Identifier les patterns problématiques:

```bash
# Rechercher patterns non standardisés
grep -rn "\.catch(() => false)" tests/e2e/
grep -rn "\.catch(() => {})" tests/e2e/
grep -rn "catch\s*(\)\s*\{[^}]*//.*silent" tests/e2e/
grep -rn "try\s*\{[^}]*catch[^}]*\}" tests/e2e/ | head -20
```

**Patterns identifiés:**

| Pattern | Fichier | Ligne | Impact |
|---------|---------|-------|--------|
| `.catch(() => false)` | auth.ts | 267 | Masque erreurs visibility |
| `.catch(() => false)` | idfm-franceconnect-*.spec.ts | 316 | Masque FC button check |
| `.catch(() => false)` | bike-booking-*.spec.ts | 183 | Masque QR scanner |

### Phase 2: Helper Error Handling

```typescript
// tests/e2e/helpers/errors.ts
export class TestErrorHandler {
  /**
   * Wrapper pour expect(isVisible()) avec logging
   */
  static async expectVisible(
    locator: Locator,
    selector: string,
    options?: { timeout?: number; log?: string }
  ): Promise<void> {
    try {
      await expect(locator, `Element ${selector} should be visible`).toBeVisible({
        timeout: options?.timeout ?? 5000,
      });
    } catch (error) {
      console.error(`❌ Selector not found: ${selector}`);
      if (options?.log) {
        console.error(`   Context: ${options.log}`);
      }
      throw error;
    }
  }

  /**
   * Wrapper pour expect(count) avec logging
   */
  static expectCount(
    locator: Locator,
    expected: number,
    selector: string
  ): void {
    expect(locator, `Selector ${selector} should have ${expected} elements`).toHaveCount(expected);
  }

  /**
   * Safe get text avec fallback
   */
  static async getTextOrNull(locator: Locator): Promise<string | null> {
    try {
      return await locator.textContent();
    } catch {
      return null;
    }
  }

  /**
   * Safe isVisible avec logging
   */
  static async isVisibleWithLog(locator: Locator, selector: string): Promise<boolean> {
    try {
      return await locator.isVisible();
    } catch (error) {
      console.warn(`⚠️  Error checking visibility of ${selector}: ${error}`);
      return false;
    }
  }
}
```

### Phase 3: Migration

**AVANT (problématique):**
```typescript
const errorVisible = await errorMessage.isVisible().catch(() => false);
expect(errorVisible).toBe(false);

const hasSuccess = await page.locator('[data-testid="unlock-success"]').isVisible({ timeout: 3000 }).catch(() => false);
```

**APRÈS (standardisé):**
```typescript
import { TestErrorHandler } from '../helpers/errors';

const errorVisible = await TestErrorHandler.isVisibleWithLog(errorMessage, 'error-alert');
expect(errorVisible).toBe(false);

const hasSuccess = await TestErrorHandler.expectVisible(
  page.locator('[data-testid="unlock-success"]'),
  'unlock-success',
  { timeout: 3000 }
);
```

### Phase 4: Logging Centralisé

```typescript
// tests/e2e/helpers/logger.ts
export class TestLogger {
  private static enabled = process.env.TEST_LOGGING !== 'false';

  static log(action: string, details: Record<string, unknown> = {}) {
    if (!this.enabled) return;
    console.log(`[TEST] ${action}`, JSON.stringify(details, null, 2));
  }

  static step(name: string) {
    console.log(`\n📍 STEP: ${name}`);
  }

  static success(message: string) {
    console.log(`✅ ${message}`);
  }

  static error(message: string, error?: unknown) {
    console.error(`❌ ${message}`, error);
  }

  static warn(message: string) {
    console.warn(`⚠️  ${message}`);
  }
}
```

### Phase 5: Convention Error Handling

**RÈGLES:**

| Situation | Approach |
|-----------|----------|
| Vérification élément UI | `expect(locator).toBeVisible()` (fail le test) |
| Optional element check | `TestErrorHandler.isVisibleWithLog()` (log + continue) |
| API call error | `expect(response.ok()).toBe(true)` (fail le test) |
| Async operation | `await expectAsync(locator).toBeVisible()` (fail le test) |
| Network error | Propager l'erreur, ne pas masquer |

## 🔗 Fichiers à Modifier

```
tests/e2e/helpers/errors.ts              # NOUVEAU - ErrorHandler
tests/e2e/helpers/logger.ts              # NOUVEAU - Logger
tests/e2e/helpers/auth.ts                # Migration
tests/e2e/journeys/*.spec.ts             # ~50 fichiers
tests/e2e/payment/*.spec.ts              # ~8 fichiers
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 0 `.catch(() => false)` pour assertions | `grep "\.catch(() => false)" tests/e2e --include="*.ts"` |
| ErrorHandler utilisé | `grep "TestErrorHandler" tests/e2e/*.ts` |
| Logging cohérent | `grep "TestLogger" tests/e2e/*.ts` |
| Tests échouent sur erreur réelle | Couverture 100% |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Audit | 2h | - |
| ErrorHandler | 3h | - |
| Logger | 2h | - |
| Migration auth.ts | 2h | Phases 2-3 |
| Migration tests | 4h | Phases 2-4 |
| Validation | 2h | Phases 1-5 |

**Total estimé:** 15h
