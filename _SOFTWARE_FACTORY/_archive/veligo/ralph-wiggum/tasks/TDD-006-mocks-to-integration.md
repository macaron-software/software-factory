# TDD-006: Migration Mocks → Vrais Appels Backend

**Anomalie:** #6 - Mocks API au Lieu de Vrais Appels Backend  
**Priorité:** P1  
**Fichiers:** Tous les tests E2E avec mocks

## 🎯 Objectif

Remplacer les mocks hardcodés par de vrais appels backend pour tests d'intégration vrais.

## 📋 Tasks Détaillées

### Phase 1: Cartographie Mocks

| Fichier | Mock Type | Valeur Mockée |
|---------|-----------|---------------|
| lyon-tcl-multimodal-full.spec.ts | JSON hardcodé | TCL API response |
| idfm-franceconnect-sso-full.spec.ts | JWT string | FranceConnect token |
| nantes-box-securises-full.spec.ts | Access code | Code génération |
| 06-ao-compliance-rgpd.spec.ts | API responses | ComplianceService |

### Phase 2: Service Mock Configurable

Créer système de mock contrôlable:

```typescript
// tests/e2e/helpers/mock-server.ts
export class MockServer {
  private static instance: MockServer;
  private mocks: Map<string, unknown> = new Map();
  private enabled: boolean = true;

  static getInstance(): MockServer {
    if (!this.instance) {
      this.instance = new MockServer();
    }
    return this.instance;
  }

  enable() { this.enabled = true; }
  disable() { this.enabled = false; }

  setMock(endpoint: string, response: unknown) {
    this.mocks.set(endpoint, response);
  }

  async handleRequest(url: string): Promise<unknown> {
    if (!this.enabled) return null; // Forward to real backend
    return this.mocks.get(url) || null;
  }
}
```

### Phase 3:TCL Migration

**AVANT (mock):**
```typescript
const tclApiResponse = {
  station_id: 'tcl_metro_bellecour',
  // ... hardcoded
};
```

**APRÈS (vrai appel avec fallback mock):**
```typescript
const tclClient = new TCLClient();
let tclData;

try {
  tclData = await tclClient.getRealTimeArrivals('bellecour');
} catch (error) {
  // Fallback mock si API unavailable en dev
  if (process.env.USE_MOCKS === 'true') {
    tclData = getTCLMock('bellecour');
  } else {
    throw error;
  }
}
```

### Phase 4: FranceConnect Test Environment

Pour FranceConnect, utiliser test environment:
- URL: `https://fcp.integ01.dev-franceconnect.fr`
- Client ID: test credentials
- Mocker la page FranceConnect en local avec Playwright

### Phase 5: Cleanup

- [ ] Supprimer mocks hardcodés des specs
- [ ] Garder mocks comme fallback uniquement
- [ ] Activer mode mock via env var `USE_MOCKS=true`
- [ ] Tests par défaut utilisent vrais appels

## 🔗 Fichiers à Modifier

```
tests/e2e/helpers/mock-server.ts     # NOUVEAU - Service mock
tests/e2e/helpers/tcl-client.ts      # NOUVEAU - Client TCL réel
tests/e2e/journeys/lyon-tcl-*.spec.ts
tests/e2e/journeys/idfm-franceconnect-*.spec.ts
tests/e2e/journeys/nantes-box-*.spec.ts
tests/e2e/journeys/06-ao-compliance-rgpd.spec.ts
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| 0 mocks hardcodés dans specs | `grep -r "const.*ApiResponse.*=" --include="*.spec.ts"` |
| Mocks via service | `grep "MockServer" tests/e2e/` |
| Fallback configurable | `USE_MOCKS=true npm run test:e2e` passent |
| Integration tests | `USE_MOCKS=false npm run test:e2e` passent |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Cartographie | 2h | - |
| Mock Server | 3h | - |
| TCL Migration | 4h | Phase 2 |
| FC Migration | 4h | Phase 2 |
| Box Migration | 3h | Phase 2 |
| Cleanup | 2h | Phases 3-5 |

**Total estimé:** 18h
