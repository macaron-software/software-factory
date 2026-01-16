# TDD-005: Unification Fixtures Users

**Anomalie:** #5 - Fixtures Users Incohérentes  
**Priorité:** P1  
**Fichiers:** `veligo-platform/tests/e2e/fixtures/users.json`, `tests/e2e/helpers/auth.ts`

## 🎯 Objectif

Unifier les fixtures utilisateurs en une source de vérité unique avec domains cohérents.

## 📋 Tasks Détaillées

### Phase 1: Analyse Incohérences

| Fichier | Domain | Email Example |
|---------|--------|---------------|
| users.json | `@test-*.fr` | `marie.dupont@test-idfm.fr` |
| auth.ts | `@*.test` | `admin@idfm.test` |
| payments/* | `@idfm.test` | `user@idfm.test` |
| Multi-tenant | `@veligo.app` | `test@veligo.app` |

### Phase 2: Standardisation

**Décision:** Utiliser domain `@veligo.test` comme standard

```json
// NOUVELLE STRUCTURE UNIFIÉE
{
  "idfm": {
    "admin": { "email": "admin@idfm.veligo.test", "password": "..." },
    "user": { "email": "user@idfm.veligo.test", "password": "..." },
    "subscriber": { "email": "subscriber@idfm.veligo.test", "password": "..." }
  },
  "nantes": {
    "admin": { "email": "admin@nantes.veligo.test", "password": "..." },
    "user": { "email": "user@nantes.veligo.test", "password": "..." }
  },
  "lyon": {
    "admin": { "email": "admin@lyon.veligo.test", "password": "..." },
    "user": { "email": "user@lyon.veligo.test", "password": "..." }
  }
}
```

### Phase 3: Migration

- [ ] Mettre à jour `users.json` avec nouveau format
- [ ] Supprimer `TEST_USERS` en dur dans `auth.ts`
- [ ] Importer depuis fixtures centralisées
- [ ] Mettre à jour tous les tests

### Phase 4: Script Validation

Créer script pour valider cohérence:

```typescript
// tools/validate-fixtures.ts
import users from '../fixtures/users.json';

for (const [tenant, data] of Object.entries(users)) {
  for (const [role, user] of Object.entries(data)) {
    if (!user.email.endsWith('@veligo.test')) {
      throw new Error(`Invalid domain: ${user.email}`);
    }
  }
}
```

## 🔗 Fichiers à Modifier

```
veligo-platform/tests/e2e/fixtures/users.json  # Nouveau format unifié
tests/e2e/helpers/auth.ts                       # Importer depuis fixtures
tests/e2e/payment/*.spec.ts                     # 8 fichiers
tests/e2e/ao-compliance/*.spec.ts               # ~10 fichiers
tests/e2e/journeys/*.spec.ts                    # ~50 fichiers
```

## ✅ Criteria Definition

| Critère | Validation |
|---------|------------|
| Domain unifié | 100% emails finissent par `@veligo.test` |
| Single source of truth | 1 fichier fixtures, 0 duplicatas |
| Scripts passent | `npm run validate:fixtures` |
| Tests passent | `npm run test:e2e` |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Analyse | 1h | - |
| Standardisation | 1h | Phase 1 |
| Migration users.json | 2h | Phase 2 |
| Migration auth.ts | 1h | Phase 2 |
| Update tests | 3h | Phase 3 |
| Script validation | 1h | Phase 4 |

**Total estimé:** 9h
