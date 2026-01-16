# Rapport d'Anomalies E2E - Veligo Platform
**Date:** 2026-01-13  
**Auteur:** Agent RLM (Recursive Language Model)  
**Profondeur:** depth=0

---

## 📊 RÉSUMÉ EXÉCUTIF

| Métrique | Valeur |
|----------|--------|
| Tests E2E totaux | ~1,500 |
| Tests SKIPPED (BLOCKERS P0) | **49** |
| Tests avec ANOMALIES | ~150+ |
| Configuration Playwright | 12 fichiers fragmentés |
| Sélecteurs data-testid non standardisés | ~80+ occurrences |

### Répartition des Anomalies

| Priorité | Nombre | Impact |
|----------|--------|--------|
| P0 (Bloquant) | 3 | 49 tests non exécutables |
| P1 (Critique) | 4 | Qualité des tests compromise |
| P2 (Majeur) | 3 | Maintenance et cohérence |

---

## 🚨 ANOMALIES P0 - BLOQUANTES

### ANOMALIE #1: FranceConnect SSO Non Implémenté (IDFM)

**Fichier:** `tests/e2e/journeys/idfm-franceconnect-sso-full.spec.ts`  
**Lignes:** 1-340  
**Tests impactés:** 16

**Description:**
Tous les 16 tests de FranceConnect SSO sont SKIPPED avec statut `TODO`. La fonctionnalité FranceConnect est **OBLIGATOIRE** selon AO IDFM §3.1.3.

**Tests concernés:**
```
[BLOCKER-1] IDFM FranceConnect SSO - OAuth Flow (8 tests)
[BLOCKER-1] IDFM FranceConnect SSO - Logout (3 tests)  
[BLOCKER-1] IDFM FranceConnect SSO - Error Handling (5 tests)
```

**Blockers identifiés:**
- OAuth client registration with FranceConnect
- JWT signature validation (RS256)
- User provisioning flow
- Session management
- Logout callback handling

**Code problématique:**
```typescript
// Line 23-40: Test AC-001 - FranceConnect button check
test('[AO-IDFM-§3.1.3][AC-001] User clicks "Se connecter avec FranceConnect"', async ({ page }) => {
  // TODO: Implement FranceConnect OAuth flow
  // Expected: Redirect to FranceConnect authorization page
  await page.goto('https://idfm.veligo.app/login');
  const fcButton = page.locator('[data-testid="franceconnect-login-btn"]');
  await expect(fcButton).toBeVisible();
  // ...
});
```

**Impact AO:**
- AO-IDFM-§3.1.3: FranceConnect SSO obligatoire pour IDFM
- 23 tests IDFM dépendent de cette implémentation

---

### ANOMALIE #2: Box Sécurisés Nantes Non Implémenté

**Fichier:** `tests/e2e/journeys/nantes-box-securises-full.spec.ts`  
**Lignes:** 1-452  
**Tests impactés:** 18

**Description:**
Tous les 18 tests de Box Sécurisés Nantes sont SKIPPED avec statut `TODO`. La fonctionnalité box sécurisé est **OBLIGATOIRE** selon AO Nantes §2.3.1.

**Tests concernés:**
```
[BLOCKER-2] Nantes Box Sécurisés - Assignment (6 tests)
[BLOCKER-2] Nantes Box Sécurisés - Return & Pickup (4 tests)
[BLOCKER-2] Nantes Box Sécurisés - Admin Management (4 tests)
[BLOCKER-2] Nantes Box Sécurisés - Error Handling (4 tests)
```

**Blockers identifiés:**
- Box inventory database schema
- Access code generation (6-digit)
- SMS integration (Twilio)
- IoT device API (box lock/unlock)
- Admin assignment interface
- Code expiration logic (30 days)
- Rate limiting (3 failed attempts)

**Impact AO:**
- AO-NANTES-§2.3.1: Box Sécurisés - Livraison et stockage sécurisé
- 18 tests Nantes dépendent de cette implémentation

---

### ANOMALIE #3: TCL Multimodal Lyon Non Implémenté

**Fichier:** `tests/e2e/journeys/lyon-tcl-multimodal-full.spec.ts`  
**Lignes:** 1-484  
**Tests impactés:** 15

**Description:**
Tous les 15 tests d'intégration TCL Multimodal sont SKIPPED avec statut `TODO`. L'intégration TCL est **OBLIGATOIRE** selon AO Lyon §4.2.1.

**Tests concernés:**
```
[BLOCKER-3] Lyon TCL Multimodal - Real-Time Data (5 tests)
[BLOCKER-3] Lyon TCL Multimodal - Itinerary Planning (5 tests)
[BLOCKER-3] Lyon TCL Multimodal - Subscriptions (3 tests)
[BLOCKER-3] Lyon TCL Multimodal - Error Handling (2 tests)
```

**Blockers identifiés:**
- TCL Open Data API integration (real-time arrivals)
- Multimodal route planner algorithm
- TCL + Véligo combined pricing logic
- TCL Techniques card validation API
- Dynamic rerouting on delays/disruptions
- Caching strategy (30s refresh)
- Rate limiting handling (429 responses)
- Map overlay for TCL stations (metro, tram, bus)

**Impact AO:**
- AO-LYON-§4.2.1: TCL Multimodal Integration - Real-time + Itinerary Planning
- 15 tests Lyon dépendent de cette implémentation

---

## ⚠️ ANOMALIES P1 - CRITIQUES

### ANOMALIE #4: Incohérence des Sélecteurs data-testid

**Fichier:** `tests/e2e/helpers/auth.ts`  
**Lignes:** 42-44, 106-115, 155

**Description:**
Les helpers utilisent des sélecteurs multiples alternatifs au lieu de data-testid standardisés. Cela indique une migration incomplète ou une absence de convention.

**Code problématique:**
```typescript
// Line 42-44: Sélecteurs multiples non standardisés
await page.fill('[data-testid="login-email"], [data-testid="email-input"], input[type="email"]', email);
await page.fill('[data-testid="login-password"], [data-testid="password-input"], input[type="password"]', password);
await page.click('[data-testid="login-submit"], [data-testid="submit-button"], button[type="submit"]');

// Line 106-115: Même problème pour l'inscription
await page.fill('[data-testid="register-email"], input[type="email"]', email);
await page.fill('[data-testid="register-password"], input[type="password"]', password);
```

**Impact:**
- Les sélecteurs génériques (`input[type="email"]`) peuvent matcher plusieurs éléments
- Pas de traçabilité entre test et élément IHM
- Maintenance difficile quand l'UI change

**Occurrences:** ~80+ dans le codebase test

---

### ANOMALIE #5: Fixtures Users Incohérentes

**Fichier 1:** `veligo-platform/tests/e2e/fixtures/users.json`  
**Fichier 2:** `tests/e2e/helpers/auth.ts`

**Description:**
Les emails de test utilisent des domaines différents entre les fixtures, causant des échecs de login potentiels.

**Conflit:**
```json
// users.json - Ligne 3
"email": "marie.dupont@test-idfm.fr"

// auth.ts - Ligne 16
admin: { email: 'admin@idfm.test', password: 'AdminIdfm123!' },
```

**Domaines utilisés:**
- `@test-*.fr` (users.json)
- `@*.test` (auth.ts)
- `@veligo.app` (fixtures mélangées)

**Impact:**
- Tests peuvent échouer si le backend n'accepte pas ces domaines
- Pas de source de vérité unique pour les credentials

---

### ANOMALIE #6: Mocks API au Lieu de Vrais Appels Backend

**Fichier:** `tests/e2e/journeys/lyon-tcl-multimodal-full.spec.ts`  
**Lignes:** 56-73

**Description:**
Les réponses API sont mockées (hardcodées) au lieu d'appeler le vrai backend. Les tests ne valident pas l'intégration réelle.

**Code problématique:**
```typescript
// Mock hardcodé au lieu de vrai appel API
const tclApiResponse = {
  station_id: 'tcl_metro_bellecour',
  station_name: 'Bellecour',
  lines: [
    {
      line_id: 'A',
      line_type: 'metro',
      direction: 'Vaulx-en-Velin La Soie',
      next_arrivals: ['2 min', '7 min', '12 min']
    },
    // ...
  ]
};
```

**Problème équivalent dans FranceConnect (idfm-franceconnect-sso-full.spec.ts):**
```typescript
// Line 106: JWT mocké
const idToken = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...'; // Mock JWT
```

**Impact:**
- Tests ne valident pas l'intégration réelle
- Les mocks peuvent diverger de la réalité
- Aucune validation des endpoints backend réels

---

### ANOMALIE #10: Sélecteurs Non Validés vs Frontend Réel

**Description:**
Les tests utilisent des sélecteurs `data-testid` qui ne sont pas vérifiés contre le frontend réel. Il n'y a pas de test de validaton des sélecteurs.

**Exemples de sélecteurs utilisés sans vérification:**
```typescript
'[data-testid="franceconnect-login-btn"]'      // Non vérifié frontend
'[data-testid="box-access-code"]'               // Non vérifié frontend  
'[data-testid="tcl-multimodal-toggle"]'         // Non vérifié frontend
'[data-testid="qr-scanner"]'                    // Non vérifié frontend
'[data-testid="journey-planner"]'               // Non vérifié frontend
```

**Impact:**
- Les tests peuvent échouer à cause de selecteurs incorrects
- Pas de documentation vivante des éléments IHM
- Refactoring UI risqué sans détection de breakage

---

## 📋 ANOMALIES P2 - MAJEURES

### ANOMALIE #7: Configuration Playwright Fragmentée

**Fichiers identifiés:** 12 configurations Playwright

```
/Users/sylvain/_LAPOSTE/_VELIGO2/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/veligo-platform/frontend/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/veligo-platform/tests/e2e/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/tests/e2e/multi-tenant/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/tests/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/tests/e2e/laposte/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/tenant/frontend-user/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/veligo-platform/design-system/playwright.config.ts
/Users/sylvain/_LAPOSTE/_VELIGO2/llama-cpp-local/tools/server/webui/playwright.config.ts
```

**Problèmes:**
- Duplication de configuration
- Paramètres potentiellement contradictoires
- Pas de的标准化 (standardisation)
- Maintenance complexe

---

### ANOMALIE #8: URLs Backend Incohérentes

**REST vs gRPC:**
```typescript
// REST
'/api/v1/auth/login'
'/api/v1/auth/register'
'/api/bikes/unlock'

// gRPC (format probable)
'/compliance.ComplianceService/SaveConsent'
'/subscription.SubscriptionService/UpgradePlan'

// URL absolues
'https://idfm.veligo.app/login'
'http://idfm.localhost:8040/login'
```

**Problèmes:**
- Pas de convention d'URL claire
- Mix de REST et gRPC dans les mêmes tests
- URLs localhost vs production

---

### ANOMALIE #9: Gestion d'Erreurs Non Standardisée

**Code problématique:**
```typescript
// Line 267: .catch(() => false) - masque les erreurs
const errorVisible = await errorMessage.isVisible().catch(() => false);
expect(errorVisible).toBe(false);

// Line 42: .catch(() => false) dans auth.ts
const buttonVisible = await fcButton.isVisible().catch(() => false);

// Line 183: try/catch silencieux
await expect(firstBike.locator('[data-testid="bike-status"]')).toBeVisible()
  .catch(() => { /* silent fail */ });
```

**Impact:**
- Les erreurs sont masquées
- Debug difficile
- Tests peuvent passer faussement

---

## 🎯 MICRO-TÂCHES TDD GÉNÉRÉES

| ID | Anomalie | Priorité | Tâche TDD |
|----|----------|----------|-----------|
| TDD-001 | FranceConnect SSO | P0 | Créer endpoint OAuth FranceConnect backend |
| TDD-001 | FranceConnect SSO | P0 | Implémenter callback handler FranceConnect |
| TDD-001 | FranceConnect SSO | P0 | Valider JWT FranceConnect (RS256) |
| TDD-001 | FranceConnect SSO | P0 | Créer flow user provisioning |
| TDD-001 | FranceConnect SSO | P0 | Implémenter session management |
| TDD-002 | Box Sécurisés | P0 | Créer schema DB boxes |
| TDD-002 | Box Sécurisés | P0 | Implémenter génération code 6-digit |
| TDD-002 | Box Sécurisés | P0 | Intégrer SMS gateway (Twilio) |
| TDD-002 | Box Sécurisés | P0 | Créer API IoT box lock/unlock |
| TDD-002 | Box Sécurisés | P0 | Implémenter interface admin box |
| TDD-003 | TCL Lyon | P0 | Intégrer TCL Open Data API |
| TDD-003 | TCL Lyon | P0 | Créer route planner multimodal |
| TDD-003 | TCL Lyon | P0 | Implémenter caching TCL (30s) |
| TDD-003 | TCL Lyon | P0 | Gérer rate limiting 429 |
| TDD-003 | TCL Lyon | P0 | Créer overlay map TCL stations |
| TDD-004 | data-testid | P1 | Audit sélecteurs existants |
| TDD-004 | data-testid | P1 | Créer standard naming convention |
| TDD-004 | data-testid | P1 | Refactoriser auth.ts vers sélecteurs stricts |
| TDD-005 | Fixtures users | P1 | Unifier domain users.json → @veligo.test |
| TDD-005 | Fixtures users | P1 | Supprimer auth.ts users alternatifs |
| TDD-005 | Fixtures users | P1 | Créer script validation fixtures |
| TDD-006 | Mocks API | P1 | Remplacer mocks TCL par vrais appels |
| TDD-006 | Mocks API | P1 | Implémenter FranceConnect test environment |
| TDD-006 | Mocks API | P1 | Créer service mock configurable |
| TDD-010 | Sélecteurs frontend | P1 | Scanner frontend pour data-testid existants |
| TDD-010 | Sélecteurs frontend | P1 | Créer test validation sélecteurs |
| TDD-010 | Sélecteurs frontend | P1 | Documenter mapping test→IHM |
| TDD-007 | Playwright config | P2 | Unifier vers 1 config principale |
| TDD-007 | Playwright config | P2 | Supprimer configs dupliquées |
| TDD-007 | Playwright config | P2 | Créer base config partagée |
| TDD-008 | URLs backend | P2 | Définir convention URL REST vs gRPC |
| TDD-008 | URLs backend | P2 |统一化 base URLs (localhost vs prod) |
| TDD-008 | URLs backend | P2 | Créer helper URLs centralisé |
| TDD-009 | Error handling | P2 | Remplacer .catch(() => false) par proper handling |
| TDD-009 | Error handling | P2 | Créer wrapper error handling standard |
| TDD-009 | Error handling | P2 | Ajouter logging erreurs tests |

---

## 📝 RECOMMANDATIONS

### Priorité Immediate (Cette semaine)
1. **FranceConnect SSO:** Commencer implémentation OAuth backend
2. **TCL API:** Établir contrat avec TCL Open Data
3. **Fixtures:** Unifier domains de test

### Court Terme (Ce mois)
4. **Standardiser sélecteurs:** Créer convention et refactoriser
5. **Validation sélecteurs:** Créer tests de validation IHM
6. **Mocks → Vrais appels:** Gradual migration vers integration tests

### Moyen Terme (Ce trimestre)
7. **Configuration Playwright:** Rationaliser vers 1-2 configs
8. **Documentation:** Créer living documentation des sélecteurs
9. **Formation:** Équipe sur conventions tests E2E

---

**Fin du rapport**
