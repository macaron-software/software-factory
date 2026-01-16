# TDD-007: Consolidation Configuration Playwright

**Anomalie:** #7 - Configuration Playwright Fragmentée (12 fichiers)  
**Priorité:** P2  
**Fichiers:** 12 playwright.config.ts dans le repo

## 🎯 Objectif

Rationaliser les 12 configurations Playwright vers 1-2 configurations principales.

## 📋 Tasks Détaillées

### Phase 1: Audit Configurations

Lister et analyser chaque configuration:

| Fichier | Usage | Différences Clés |
|---------|-------|------------------|
| `/playwright.config.ts` | Principal | Base config |
| `/veligo-platform/frontend/playwright.config.ts` | Frontend tests | +baseURL |
| `/veligo-platform/tests/e2e/playwright.config.ts` | E2E tests | +fixtures |
| `/tests/playwright.config.ts` | Tests root | Duplicata? |
| `/tests/e2e/laposte/playwright.config.ts` | LaPoste | +projects |
| `/tests/e2e/multi-tenant/playwright.config.ts` | Multi-tenant | +tenants |

### Phase 2: Base Config Partagée

Créer configuration de base:

```typescript
// playwright.config.base.ts
export const baseConfig = {
  timeout: 30000,
  expect: { timeout: 5000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8040',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
};
```

### Phase 3: Consolidation

**Stratégie:** 1 config principale, configs spécifiques minimales

```
playwright.config.ts              # Config principale (hérite base)
├── use projects/ pour variations
└── use overrides pour cas spécifiques
```

Supprimer configs redondantes:
- [ ] `/tests/playwright.config.ts` → supprimer (duplicata)
- [ ] `/veligo-platform/tests/e2e/playwright.config.ts` → utiliser principal
- [ ] `/llama-cpp-local/...` → hors scope principal

### Phase 4: Migration Dossiers

Regrouper les tests:

```
tests/
├── e2e/
│   ├── journeys/
│   ├── ao-compliance/
│   ├── payment/
│   ├── lapose/
│   └── multi-tenant/
└── playwright.config.ts           # UNIQUE config
```

## 🔗 Fichiers à Modifier/Supprimer

```
À SUPPRIMER:
- /tests/playwright.config.ts
- /veligo-platform/tests/e2e/playwright.config.ts
- /llama-cpp-local/tools/server/webui/playwright.config.ts

À UNIFIER:
- /playwright.config.ts (DEVenir principal)
- /veligo-platform/frontend/playwright.config.ts
- /tests/e2e/laposte/playwright.config.ts
- /tests/e2e/multi-tenant/playwright.config.ts
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 1 seul playwright.config.ts principal | `find . -name "playwright.config.ts" \| grep -v node_modules` |
| Tests passent | `npm run test:e2e` |
| Pas de duplication config | `grep "timeout: 30000" *.ts` unique |
| CI utilise config principal | `cat .github/workflows/*.yml` |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Audit | 2h | - |
| Base Config | 3h | Phase 1 |
| Consolidation | 4h | Phase 2 |
| Migration Tests | 3h | Phase 3 |
| Validation | 2h | Phases 1-4 |

**Total estimé:** 14h
