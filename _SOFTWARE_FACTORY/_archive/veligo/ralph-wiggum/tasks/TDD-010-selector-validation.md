# TDD-010: Validation Sélecteurs Frontend

**Anomalie:** #10 - Sélecteurs Non Validés vs Frontend Réel  
**Priorité:** P1  
**Fichiers:** Tous les tests E2E avec data-testid

## 🎯 Objectif

Créer système de validation des sélecteurs data-testid contre le frontend réel pour garantir que les tests matchent l'IHM.

## 📋 Tasks Détaillées

### Phase 1: Scanner Frontend

Créer script pour extraire tous les data-testid du frontend:

```bash
#!/bin/bash
# tools/scan-testids.sh

echo "=== Scanning Svelte components for data-testid ==="
grep -r "data-testid=" veligo-platform/frontend/src --include="*.svelte" | \
  sed 's/.*data-testid="\([^"]*\)".*/\1/' | \
  sort -u > frontend-testids.txt

echo "Total data-testid found: $(wc -l < frontend-testids.txt)"
cat frontend-testids.txt
```

### Phase 2: Extraire Sélecteurs Tests

```bash
#!/bin/bash
# tools/scan-testids.sh (suite)

echo "=== Scanning E2E tests for data-testid ==="
grep -r "\[data-testid=" tests/e2e --include="*.ts" | \
  sed 's/.*\[data-testid="\([^"]*\)".*/\1/' | \
  sort -u > test-testids.txt

echo "Total data-testid in tests: $(wc -l < test-testids.txt)"
cat test-testids.txt
```

### Phase 3: Comparaison & Gap Analysis

```typescript
// tools/compare-testids.ts
import { readFileSync } from 'fs';

const frontend = new Set(readFileSync('frontend-testids.txt', 'utf-8').split('\n').filter(Boolean));
const tests = new Set(readFileSync('test-testids.txt', 'utf-8').split('\n').filter(Boolean));

const missingInFrontend = [...tests].filter(id => !frontend.has(id));
const missingInTests = [...frontend].filter(id => !tests.has(id));

console.log('=== GAP ANALYSIS ===');
console.log(`Missing in frontend: ${missingInFrontend.length}`);
missingInFrontend.forEach(id => console.log(`  ❌ ${id}`));

console.log(`\nUnused in tests: ${missingInTests.length}`);
missingInTests.forEach(id => console.log(`  ⚠️  ${id}`));
```

### Phase 4: Test Validation Automatisé

Créer test qui vérifie les sélecteurs:

```typescript
// tests/e2e/selector-validator.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Selector Validation', () => {
  const testids = require('../fixtures/valid-testids.json');

  for (const [page, selectors] of Object.entries(testids)) {
    test(`Validate ${page} selectors`, async ({ page: browserPage }) => {
      await browserPage.goto(page);

      for (const selector of selectors) {
        const element = browserPage.locator(`[data-testid="${selector}"]`);
        const count = await element.count();

        if (count === 0) {
          console.warn(`⚠️  Selector not found: ${selector} on ${page}`);
        }

        expect(count, `Selector ${selector} should exist`).toBeGreaterThan(0);
      }
    });
  }
});
```

### Phase 5: Living Documentation

Créer fichier de référence:

```json
// fixtures/valid-testids.json
{
  "http://idfm.localhost:8040/login": [
    "login-email-input",
    "login-password-input",
    "login-submit-button",
    "franceconnect-login-button",
    "forgot-password-link"
  ],
  "http://idfm.localhost:8040/dashboard": [
    "user-menu",
    "logout-button",
    "stats-overview"
  ]
}
```

### Phase 6: CI Integration

Ajouter à playwright.config.ts:

```typescript
// run selector validation before other tests
projects: [
  {
    name: 'selector-validation',
    testMatch: /selector-validator\.spec\.ts/,
  },
  // ... autres projets
]
```

## 🔗 Fichiers à Créer

```
tools/scan-testids.sh              # Script scan frontend
tools/compare-testids.ts           # Gap analysis
tests/e2e/selector-validator.spec.ts # Test validation
fixtures/valid-testids.json        # Living documentation
playwright.config.ts               # CI integration
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 0 sélecteurs non trouvés | Test selector-validator passe |
| Documentation à jour | valid-testids.json sync avec frontend |
| CI valide | `npm run test:selectors` dans pipeline |
| Mapping complet | 100% data-testid documentés |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Scanner Frontend | 1h | - |
| Extraire Tests | 1h | - |
| Gap Analysis | 2h | Phases 1-2 |
| Test Validation | 4h | Phase 3 |
| Living Doc | 2h | Phase 4 |
| CI Integration | 2h | Phase 5 |

**Total estimé:** 12h
