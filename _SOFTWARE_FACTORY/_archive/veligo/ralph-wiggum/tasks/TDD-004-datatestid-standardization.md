# TDD-004: Standardisation data-testid Selectors

**Anomalie:** #4 - Incohérence des Sélecteurs data-testid  
**Priorité:** P1  
**Fichiers:** `tests/e2e/helpers/auth.ts`, tous les tests E2E

## 🎯 Objectif

Standardiser les sélecteurs data-testid dans tous les tests E2E selon une convention stricte.

## 📋 Tasks Détaillées

### Phase 1: Audit & Convention
- [ ] Auditor tous les sélecteurs actuels (~100+)
- [ ] Créer document convention naming (voir ci-dessous)
- [ ] Lister sélecteurs manquants par page
- [ ] Définir mapping sélecteur → élément IHM

### Phase 2: Convention Naming

```
FORMAT: [data-testid="{component}-{element}-{variant}"]

EXAMPLES:
✅ [data-testid="login-form"]
✅ [data-testid="login-email-input"]
✅ [data-testid="login-password-input"]
✅ [data-testid="login-submit-button"]
✅ [data-testid="franceconnect-login-button"]
❌ [data-testid="login-email"], [data-testid="email-input"], input[type="email"]
```

### Phase 3: Refactorisation auth.ts

**AVANT (problématique):**
```typescript
await page.fill('[data-testid="login-email"], [data-testid="email-input"], input[type="email"]', email);
```

**APRÈS (standardisé):**
```typescript
await page.fill('[data-testid="login-email-input"]', email);
```

### Phase 4: Validation Frontend

- [ ] Scanner composants Svelte pour data-testid
- [ ] Identifier sélecteurs manquants
- [ ] Ajouter data-testid aux composants
- [ ] Créer test validation sélecteurs

## 📋 Convention Détaillée

| Category | Pattern | Example |
|----------|---------|---------|
| Auth | `auth-{action}-{element}` | `auth-login-form`, `auth-register-submit` |
| Subscription | `subscription-{page}-{element}` | `subscription-plans-card`, `subscription-checkout-button` |
| Booking | `booking-{action}-{element}` | `booking-bike-list`, `booking-confirm-button` |
| Payment | `payment-{method}-{element}` | `payment-stripe-button`, `payment-sepa-form` |
| Admin | `admin-{section}-{element}` | `admin-users-table`, `admin-stats-chart` |
| Modal | `modal-{name}` | `modal-confirm-delete`, `modal-success` |
| Form | `{page}-{field}-input` | `profile-phone-input`, `settings-email-input` |
| Button | `{action}-button` | `save-changes-button`, `cancel-button` |
| Toast | `toast-{type}` | `toast-success`, `toast-error` |

## 🔗 Fichiers à Modifier

```
tests/e2e/helpers/auth.ts         # Refactoriser tous les sélecteurs
tests/e2e/journeys/*.spec.ts      # ~50 fichiers
tests/e2e/payment/*.spec.ts       # ~8 fichiers
tests/e2e/ao-compliance/*.spec.ts # ~10 fichiers

frontend/src/lib/components/      # Ajouter data-testid manquants
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 0 sélecteurs alternatifs (`A, B, C`) | Recherche grep `\[data-testid="[^"]+".*\[data-testid` |
| Convention naming respectée | 100% matching pattern |
| Tous sélecteurs validés frontend | Test de validation passent |
| Documentation vivante | Mapping HTML → test |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Audit & Convention | 2h | - |
| Convention Document | 1h | Phase 1 |
| Refactorisation auth.ts | 3h | Phase 2 |
| Scan Frontend | 2h | - |
| Ajout data-testid Frontend | 4h | Phase 4 |
| Validation | 2h | Phases 3-5 |

**Total estimé:** 14h
