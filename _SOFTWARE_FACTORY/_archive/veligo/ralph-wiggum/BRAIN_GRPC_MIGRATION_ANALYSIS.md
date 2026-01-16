# BRAIN ANALYSIS: gRPC Migration & Test Rewrite

**Date**: 2026-01-14
**Priority**: P0 CRITICAL
**Source**: Production Bug Analysis

---

## PROBLÈME DÉTECTÉ EN PRODUCTION

```
gRPC Error (INVALID_ARGUMENT): Invalid tenant_id: invalid length: expected length 32 for simple format, found 0
```

### Root Cause Analysis

1. **Frontend envoie `tenant_id = 'default'` ou `''`** au lieu d'un UUID
2. **Backend `subscription.rs` utilise `Uuid::parse_str()` directement** sans `resolve_tenant_id()`
3. **Les tests E2E ne détectent pas l'erreur** car ils utilisent REST au lieu de gRPC

---

## 3 PROBLÈMES SYSTÉMIQUES IDENTIFIÉS

### PROBLÈME 1: REST existe encore (devrait être supprimé)

**Fichier**: `veligo-platform/backend/src/bin/http-server.rs`

```rust
.nest("/api/auth", auth::auth_routes())           // DEVRAIT ÊTRE gRPC
.nest("/api/stations", station_routes())          // DEVRAIT ÊTRE gRPC
.nest("/api/subscriptions", subscription_e2e_routes())  // DEVRAIT ÊTRE gRPC

// Seuls ceux-ci doivent rester REST (callbacks externes)
.nest("/api/auth/franceconnect", ...)  // OAuth callback - GARDER
.nest("/api/auth/google", ...)         // OAuth callback - GARDER
.nest("/api/webhooks/stripe", ...)     // Webhook externe - GARDER
```

### PROBLÈME 2: Tests E2E utilisent REST + appels directs

**Fichiers**: `tests/e2e/journeys/*.spec.ts`

Les tests mélangent:
- `page.locator()`, `page.click()` - UI Playwright (BON)
- `request.post('/api/auth/login')` - Appels REST directs (MAUVAIS)

Cela ne teste PAS le vrai flux utilisateur frontend → gRPC → backend.

### PROBLÈME 3: tenant_id slug vs UUID

**Frontend** (`+layout.ts`):
```typescript
return { tenant: { slug: "idfm" } }  // Retourne SLUG
```

**Pages** (`subscriptions/new/+page.svelte`):
```typescript
const tenantId = $page.data.tenantId || 'default';  // Attend tenantId (n'existe pas)
$: tenantId = $page.data.tenant?.id || 'default';   // Attend .id (n'existe pas)
```

**Backend** (`subscription.rs`):
```rust
Uuid::parse_str(&req.tenant_id)  // Attend UUID 32 chars
// DEVRAIT utiliser resolve_tenant_id() comme bike.rs, station.rs
```

---

## TÂCHES À CRÉER (PRIORITÉ P0)

### Migration gRPC (supprimer REST inutile)

```
T-GRPC-001: Migrer /api/auth/login → gRPC AuthService.Login
T-GRPC-002: Migrer /api/auth/register → gRPC AuthService.Register
T-GRPC-003: Migrer /api/subscriptions → gRPC SubscriptionService (CreateSubscription déjà gRPC)
T-GRPC-004: Supprimer REST routes de http-server.rs (sauf webhooks/OAuth)
T-GRPC-005: Supprimer http-server.rs complètement si plus utilisé
```

### Fix tenant_id (P0 - Bug Production)

```
T-FIX-001: subscription.rs - utiliser resolve_tenant_id() au lieu de Uuid::parse_str()
T-FIX-002: +layout.ts - retourner tenant.id (UUID) en plus de tenant.slug
T-FIX-003: Ajouter lookup tenant slug → UUID dans frontend ou interceptor gRPC
```

### Réécriture Tests E2E (vrais tests utilisateur)

```
T-TEST-001: auth.journey.spec.ts - supprimer request.post(), UI only
T-TEST-002: subscription.journey.spec.ts - supprimer request.get/post(), UI only
T-TEST-003: Tous journeys - remplacer appels API par interactions UI
T-TEST-004: Ajouter tests gRPC directs dans tests/e2e/api/ (séparés des journeys)
T-TEST-005: Ajouter assertions sur erreurs gRPC (pas juste page.isVisible)
```

---

## FICHIERS IMPACTÉS

### Backend
- `veligo-platform/backend/src/grpc/services/subscription.rs` (ligne 56)
- `veligo-platform/backend/src/bin/http-server.rs` (supprimer)
- `veligo-platform/backend/src/api/auth.rs` (migrer vers gRPC)

### Frontend
- `veligo-platform/frontend/src/routes/(app)/+layout.ts`
- `veligo-platform/frontend/src/routes/(app)/subscriptions/new/+page.svelte`
- `veligo-platform/frontend/src/routes/(app)/checkout/payment/+page.svelte`
- `veligo-platform/frontend/src/routes/login/+page.svelte`

### Tests
- `veligo-platform/tests/e2e/journeys/auth.journey.spec.ts`
- `veligo-platform/tests/e2e/journeys/subscription.journey.spec.ts`
- `veligo-platform/tests/e2e/journeys/07-whitelabel.spec.ts`
- `veligo-platform/tests/e2e/journeys/08-payment-flow.spec.ts`

---

## ORDRE D'EXÉCUTION

1. **T-FIX-001** (P0): Fix subscription.rs resolve_tenant_id() - URGENT prod bug
2. **T-FIX-002** (P0): Fix +layout.ts tenant.id
3. **T-TEST-001-005**: Réécrire tests pour détecter ce type d'erreur
4. **T-GRPC-001-005**: Migration complète REST → gRPC
5. **D-xxx**: Deploy après chaque fix validé

---

## CRITÈRES DE SUCCÈS

- [ ] Production: plus d'erreur `Invalid tenant_id`
- [ ] Tests E2E: 0 appels `request.post/get` dans journeys
- [ ] Tests E2E: utilisent uniquement Playwright UI
- [ ] Backend: http-server.rs supprimé (sauf webhooks)
- [ ] Pipeline: TDD workers détectent ce type d'erreur AVANT deploy
