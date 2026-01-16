# TDD-008: Standardisation URLs Backend

**Anomalie:** #8 - URLs Backend Incohérentes (REST vs gRPC)  
**Priorité:** P2  
**Fichiers:** Tous les fichiers tests E2E

## 🎯 Objectif

Définir et appliquer une convention d'URL claire et cohérente pour tous les appels backend.

## 📋 Tasks Détaillées

### Phase 1: Convention d'URL

**REST API:**
```
GET    /api/v1/{resource}          # Lister
GET    /api/v1/{resource}/{id}     # Récupérer
POST   /api/v1/{resource}          # Créer
PUT    /api/v1/{resource}/{id}     # Remplacer
PATCH  /api/v1/{resource}/{id}     # Modifier partiel
DELETE /api/v1/{resource}/{id}     # Supprimer

EXAMPLES:
GET    /api/v1/auth/login
POST   /api/v1/auth/register
GET    /api/v1/bikes?available=true
POST   /api/v1/bookings
PATCH  /api/v1/bookings/{id}/cancel
```

**gRPC API (via nginx):**
```
Format: /{service}.{version}/{method}

EXAMPLES:
/auth.v1.AuthService/Login
/subscription.v1.SubscriptionService/CreatePlan
/compliance.v1.ComplianceService/RequestDataAccess
```

**Frontend Routes:**
```
/auth/login
/auth/register
/dashboard
/bikes
/bookings/{id}
```

### Phase 2: Helper Centralisé

```typescript
// tests/e2e/helpers/urls.ts
export class UrlBuilder {
  private baseUrl: string;

  constructor(baseUrl: string = process.env.BASE_URL || 'http://localhost:8040') {
    this.baseUrl = baseUrl;
  }

  // Frontend routes
  login() { return `${this.baseUrl}/auth/login`; }
  register() { return `${this.baseUrl}/auth/register`; }
  dashboard() { return `${this.baseUrl}/dashboard`; }
  bikes() { return `${this.baseUrl}/bikes`; }

  // REST API
  api(path: string) { return `${this.baseUrl}/api/v1${path}`; }
  auth() { return this.api('/auth'); }
  bikes() { return this.api('/bikes'); }
  bookings() { return this.api('/bookings'); }

  // gRPC
  grpc(service: string) { return `${this.baseUrl}/${service}`; }
}

export const urls = new UrlBuilder();
```

### Phase 3: Migration Tests

**AVANT (incohérent):**
```typescript
await page.waitForResponse(resp => resp.url().includes('/api/v1/auth/login'));
await page.waitForResponse(resp => resp.url().includes('/subscription.SubscriptionService/UpgradePlan'));
await page.goto('https://idfm.veligo.app/login');
await page.goto('http://idfm.localhost:8040/login');
```

**APRÈS (standardisé):**
```typescript
import { urls } from '../helpers/urls';

await page.waitForResponse(resp => resp.url().includes('/api/v1/auth/login'));
await page.waitForResponse(resp => resp.url().includes('/subscription.v1.SubscriptionService/UpgradePlan'));
await page.goto(urls.login());
```

### Phase 4: Constantes Backend

```typescript
// tests/e2e/helpers/backend-endpoints.ts
export const BACKEND_ENDPOINTS = {
  AUTH: {
    LOGIN: '/api/v1/auth/login',
    REGISTER: '/api/v1/auth/register',
    LOGOUT: '/api/v1/auth/logout',
    ME: '/api/v1/auth/me',
  },
  BIKES: {
    LIST: '/api/v1/bikes',
    AVAILABILITY: '/api/v1/bikes/availability',
    UNLOCK: '/api/v1/bikes/unlock',
  },
  GRPC: {
    SUBSCRIPTION_UPGRADE: '/subscription.v1.SubscriptionService/UpgradePlan',
    COMPLIANCE_SAVE_CONSENT: '/compliance.v1.ComplianceService/SaveConsent',
  },
};
```

## 🔗 Fichiers à Modifier

```
tests/e2e/helpers/urls.ts                  # NOUVEAU - UrlBuilder
tests/e2e/helpers/backend-endpoints.ts     # NOUVEAU - Constantes
tests/e2e/journeys/*.spec.ts               # ~50 fichiers
tests/e2e/payment/*.spec.ts                # ~8 fichiers
tests/e2e/ao-compliance/*.spec.ts          # ~10 fichiers
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 0 URLs hardcodées absolues | `grep "https://.*\.veligo\.app" tests/e2e --include="*.ts"` |
| URLs via helper | `grep "urls\." tests/e2e/*.ts` count > 0 |
| Convention respectée | 100% matching pattern REST ou gRPC |
| baseURL configurable | `BASE_URL=prod npm run test:e2e` |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Convention | 2h | - |
| UrlBuilder | 3h | Phase 1 |
| Constantes | 2h | Phase 1 |
| Migration Tests | 6h | Phases 2-3 |
| Validation | 2h | Phases 1-4 |

**Total estimé:** 15h
