# TDD-001: FranceConnect SSO Implementation

**Anomalie:** #1 - FranceConnect SSO Non Implémenté (16 tests SKIPPED)  
**Priorité:** P0 - CRITICAL BLOCKER  
**AO Référence:** AO-IDFM-§3.1.3  
**Fichier Source:** `tests/e2e/journeys/idfm-franceconnect-sso-full.spec.ts`

## 🎯 Objectif

Implémenter FranceConnect SSO pour IDFM tenant selon AO-IDFM-§3.1.3

## 📋 Tasks Détaillées

### Phase 1: Infrastructure OAuth (Backend)
- [ ] Créer client OAuth FranceConnect configuration
- [ ] Implémenter endpoint authorization (`/auth/franceconnect/authorize`)
- [ ] Implémenter endpoint token exchange (`/auth/franceconnect/token`)
- [ ] Implémenter validation JWT FranceConnect (RS256)
- [ ] Créer user provisioning (create/link user par FC sub)

### Phase 2: Session Management
- [ ] Créer session àprès callback FranceConnect
- [ ] Stocker FranceConnect sub dans user record
- [ ] Implémenter logout FranceConnect (`/auth/franceconnect/logout`)
- [ ] Gérer logout callback

### Phase 3: Error Handling
- [ ] Gérer user cancellation (`access_denied`)
- [ ] Gérer code invalide
- [ ] Gérer JWT signature failure
- [ ] Gérer token expiré
- [ ] Gérer FranceConnect unavailable (fallback email)

### Phase 4: Tests E2E
- [ ] Activer test AC-001: FranceConnect button visible
- [ ] Activer test AC-002: Authentification on FC
- [ ] Activer test AC-003: Authorization consent
- [ ] Activer test AC-004: Authorization code exchange
- [ ] Activer test AC-005: JWT validation
- [ ] Activer test AC-006: User provisioning
- [ ] Activer test AC-007: Dashboard redirect
- [ ] Activer test AC-008: Session persistence

## 🔗 Fichiers à Créer/Modifier

```
backend/
├── src/
│   ├── auth/
│   │   ├── franceconnect/
│   │   │   ├── mod.rs
│   │   │   ├── config.rs          # OAuth config
│   │   │   ├── oauth.rs           # Authorization flow
│   │   │   ├── token.rs           # Token exchange
│   │   │   ├── jwt.rs             # JWT validation
│   │   │   └── provisioning.rs    # User linking
│   │   └── mod.rs
│   └── routes/
│       └── auth.rs                # Endpoints

frontend/
├── src/
│   ├── auth/
│   │   ├── FranceConnectButton.svelte
│   │   └── franceconnect.ts
│   └── lib/
│       └── config.ts              # FC client ID

tests/e2e/journeys/idfm-franceconnect-sso-full.spec.ts
```

## ✅ Criteria Definition

| AC | Criteria | Test |
|----|----------|------|
| AC-001 | FranceConnect button visible on login | ✅ |
| AC-002 | Redirect to FC authorization | ✅ |
| AC-003 | Authorization consent page shown | ✅ |
| AC-004 | Code exchanged for token | ✅ |
| AC-005 | JWT validated (signature, expiry, claims) | ✅ |
| AC-006 | User created/linked | ✅ |
| AC-007 | Redirect to dashboard | ✅ |
| AC-008 | Session persists after refresh | ✅ |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Infrastructure OAuth | 4h | - |
| Session Management | 2h | Phase 1 |
| Error Handling | 2h | Phase 1 |
| Tests E2E | 2h | Phases 1-3 |

**Total estimé:** 10h
