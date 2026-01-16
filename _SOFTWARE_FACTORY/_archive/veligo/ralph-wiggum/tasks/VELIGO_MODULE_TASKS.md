# Task MOD-AUTH-002: Module auth-franceconnect complet

**Priority**: P1
**WSJF Score**: 9.2
**Complexity**: Medium
**Queue**: TDD

## Description
Implémentation complète du module d'authentification FranceConnect v2 avec support:
- OAuth 2.0 / OpenID Connect
- Récupération identité (nom, email, téléphone)
- Binding compte existant ou création automatique
- Déconnexion propagée

## Test File
`modules/auth-franceconnect.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## TDD Process
1. Lire le test: `modules/auth-franceconnect.spec.ts`
2. Comprendre ce que le test attend
3. Écrire le code minimal
4. Compiler: `cargo build -p auth-franceconnect`
5. Tester: `cargo test -p auth-franceconnect`
6. Si RED → corriger et recommencer

## Files to Modify
- `modules/auth-franceconnect/src/lib.rs`
- `modules/auth-franceconnect/src/config.rs`
- `modules/auth-franceconnect/Cargo.toml`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: Medium
MODEL_TIER: TIER2
WSJF: 9.2
---END_RALPH_STATUS---

---

# Task MOD-PAY-001: Module payment-stripe complet

**Priority**: P0
**WSJF Score**: 9.5
**Complexity**: High
**Queue**: TDD

## Description
Module complet de paiement Stripe incluant:
- Paiement CB avec 3D Secure
- Payment Intent API
- Webhooks pour confirmations
- Remboursements partiels/totaux
- Gestion des disputes

## Test File
`modules/payment-stripe.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `modules/payment-stripe/src/lib.rs`
- `modules/payment-stripe/src/webhooks.rs`
- `modules/payment-stripe/Cargo.toml`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: High
MODEL_TIER: TIER2
WSJF: 9.5
---END_RALPH_STATUS---

---

# Task MOD-BIKE-001: Module bike-booking complet

**Priority**: P0
**WSJF Score**: 9.0
**Complexity**: High
**Queue**: TDD

## Description
Module de réservation de vélos avec:
- Recherche par géolocalisation
- Réservation avec timer (15 min)
- Annulation et extension
- Gestion des conflits de réservation
- Historique des locations

## Test File
`modules/bike-booking.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `modules/bike-booking/src/lib.rs`
- `modules/bike-booking/src/reservation.rs`
- `modules/bike-booking/Cargo.toml`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: High
MODEL_TIER: TIER2
WSJF: 9.0
---END_RALPH_STATUS---

---

# Task MOD-TRK-001: Module tracking-velco complet

**Priority**: P1
**WSJF Score**: 8.5
**Complexity**: Medium
**Queue**: TDD

## Description
Module de tracking GPS via Velco:
- Suivi en temps réel position vélo
- Géofencing (entrée/sortie zones)
- Alertes mouvement suspect
- Historique des trajets
- Export GPX

## Test File
`modules/tracking-velco.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `modules/tracking-velco/src/lib.rs`
- `modules/tracking-velco/src/gps.rs`
- `modules/tracking-velco/Cargo.toml`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: Medium
MODEL_TIER: TIER2
WSJF: 8.5
---END_RALPH_STATUS---

---

# Task MOD-RGPD-001: Module gdpr-compliance complet

**Priority**: P1
**WSJF Score**: 8.8
**Complexity**: High
**Queue**: TDD

## Description
Module RGPD complet incluant:
- Export données utilisateur (Article 20)
- Droit à l'effacement (Article 17)
- Consentement granulaire tracking
- Audit trail complet
- Portabilité données

## Test File
`modules/gdpr-compliance.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `modules/gdpr-compliance/src/lib.rs`
- `modules/gdpr-compliance/src/export.rs`
- `modules/gdpr-compliance/Cargo.toml`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: High
MODEL_TIER: TIER2
WSJF: 8.8
---END_RALPH_STATUS---

---

# Task WL-MODULE-001: Activation module per tenant

**Priority**: P1
**WSJF Score**: 8.8
**Complexity**: Medium
**Queue**: TDD

## Description
Système d'activation de modules par tenant:
- Liste modules disponibles
- Activation/désactivation par tenant
- Vérification dépendances
- Gestion quotas

## Test File
`white-label/module-activation.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `veligo-platform/backend/src/services/module.rs`
- `veligo-platform/frontend/src/lib/components/admin/ModuleList.svelte`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: Medium
MODEL_TIER: TIER2
WSJF: 8.8
---END_RALPH_STATUS---

---

# Task TPL-PDF-001: Template contrat location PDF

**Priority**: P2
**WSJF Score**: 8.5
**Complexity**: Medium
**Queue**: TDD

## Description
Template PDF pour contrat de location:
- Génération contrat PDF
- Variables dynamiques (user, bike, dates)
- Signature électronique via Yousign
- Archivage automatique

## Test File
`templates/pdf-contract.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Code compile sans erreur
- [ ] Pas de régression

## Files to Modify
- `veligo-platform/backend/src/infrastructure/pdf/templates/contract.html`
- `veligo-platform/backend/src/services/contracts.rs`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: Medium
MODEL_TIER: TIER2
WSJF: 8.5
---END_RALPH_STATUS---

---

# Task PERF-001: Load test 10k concurrent users

**Priority**: P3
**WSJF Score**: 8.5
**Complexity**: High
**Queue**: TDD

## Description
Tests de performance avec 10k utilisateurs simultanés:
- Endpoint API
- Connexion WebSocket
- Base de données
- Cache Redis

## Test File
`performance/load-10k.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Latence < 200ms au 95ème percentile
- [ ] Pas de timeout

## Files to Modify
- `tests/e2e/performance/load-10k.spec.ts`
- `scripts/load-test.js`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: High
MODEL_TIER: TIER2
WSJF: 8.5
---END_RALPH_STATUS---

---

# Task CHAOS-001: Database failover

**Priority**: P3
**WSJF Score**: 9.0
**Complexity**: High
**Queue**: TDD

## Description
Tests chaos engineering - bascule base de données:
- Simulation panne primaire
- Failover automatique vers secondaire
- Vérification cohérence données
- Temps de reprise < 30s

## Test File
`chaos/db-failover.spec.ts`

## Success Criteria
- [ ] Test passe (GREEN)
- [ ] Failover automatique
- [ ] Données cohérentes

## Files to Modify
- `tests/e2e/chaos/db-failover.spec.ts`
- `scripts/chaos-injector.py`

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: High
MODEL_TIER: TIER2
WSJF: 9.0
---END_RALPH_STATUS---
