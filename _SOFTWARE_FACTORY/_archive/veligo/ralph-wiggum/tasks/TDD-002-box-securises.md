# TDD-002: Box Sécurisés Nantes Implementation

**Anomalie:** #2 - Box Sécurisés Non Implémenté (18 tests SKIPPED)  
**Priorité:** P0 - CRITICAL BLOCKER  
**AO Référence:** AO-NANTES-§2.3.1  
**Fichier Source:** `tests/e2e/journeys/nantes-box-securises-full.spec.ts`

## 🎯 Objectif

Implémenter Box Sécurisés pour Nantes tenant selon AO-NANTES-§2.3.1

## 📋 Tasks Détaillées

### Phase 1: Database Schema
- [ ] Créer table `boxes` (id, location, status, type, capacity)
- [ ] Créer table `box_assignments` (id, user_id, box_id, access_code, expiry)
- [ ] Créer table `box_access_logs` (id, box_id, user_id, action, timestamp)
- [ ] Créer migrations Seed data: boxes initiaux

### Phase 2: Access Code System
- [ ] Implémenter génération code 6-digit (RNG cryptographique)
- [ ] Implémenter validation code
- [ ] Implémenter expiration 30 jours
- [ ] Implémenter rate limiting (3 tentatives max)
- [ ] Implémenter renewal code

### Phase 3: SMS Integration
- [ ] Configurer Twilio client
- [ ] Créer service notification SMS
- [ ] Envoyer code par SMS lors allocation
- [ ] Envoyer reminder 7 jours avant expiration

### Phase 4: IoT Device API
- [ ] Créer mock IoT device API
- [ ] Implémenter endpoint unlock (`/api/boxes/{id}/unlock`)
- [ ] Implémenter endpoint lock (`/api/boxes/{id}/lock`)
- [ ] Implémenter status update webhook

### Phase 5: Admin Interface
- [ ] Créer page assignment admin (`/admin/boxes/assign`)
- [ ] Créer page dashboard boxes (`/admin/boxes/dashboard`)
- [ ] Créer page création box (`/admin/boxes/new`)
- [ ] Créer page maintenance (`/admin/boxes/{id}/maintenance`)

### Phase 6: Tests E2E
- [ ] Activer tests Assignment (AC-001 à AC-006)
- [ ] Activer tests Return & Pickup (AC-007 à AC-010)
- [ ] Activer tests Admin Management (AC-011 à AC-014)
- [ ] Activer tests Error Handling (AC-015 à AC-018)

## 🔗 Fichiers à Créer/Modifier

```
backend/
├── src/
│   ├── models/
│   │   ├── box.rs
│   │   ├── box_assignment.rs
│   │   └── box_access_log.rs
│   ├── services/
│   │   ├── box_service.rs
│   │   ├── access_code_service.rs
│   │   └── iot_device_service.rs
│   ├── sms/
│   │   └── twilio_client.rs
│   └── routes/
│       └── boxes.rs

frontend/
├── src/
│   ├── admin/
│   │   ├── BoxAssignment.svelte
│   │   ├── BoxDashboard.svelte
│   │   └── BoxCreate.svelte
│   └── user/
│       ├── BoxAccess.svelte
│       └── MyBoxes.svelte

tests/e2e/journeys/nantes-box-securises-full.spec.ts
```

## ✅ Criteria Definition

| AC | Criteria | Test |
|----|----------|------|
| AC-001 | Box option visible checkout | ✅ |
| AC-002 | Admin peut assigner box | ✅ |
| AC-003 | Code 6-digit généré | ✅ |
| AC-004 | Code envoyé SMS + Email | ✅ |
| AC-005 | Box ouvre avec code | ✅ |
| AC-006 | Status box mis à jour | ✅ |
| AC-007 | Retour bike box | ✅ |
| AC-008 | Admin pickup bike | ✅ |
| AC-009 | Code expire 30 jours | ✅ |
| AC-010 | Renewal code fonctionnel | ✅ |
| AC-011 | Admin crée box | ✅ |
| AC-012 | Dashboard occupancy visible | ✅ |
| AC-013 | Maintenance flag box | ✅ |
| AC-014 | Déactivation box | ✅ |
| AC-015 | Rate limiting (3 essais) | ✅ |
| AC-016 | Occupation double prevention | ✅ |
| AC-017 | IoT offline handling | ✅ |
| AC-018 | Subscription check | ✅ |

## 📊 Estimations

| Phase | Effort | Dépendances |
|-------|--------|-------------|
| Database Schema | 2h | - |
| Access Code System | 3h | Phase 1 |
| SMS Integration | 2h | Phase 2 |
| IoT Device API | 4h | Phase 2 |
| Admin Interface | 3h | Phases 1-4 |
| Tests E2E | 2h | Phases 1-5 |

**Total estimé:** 16h
