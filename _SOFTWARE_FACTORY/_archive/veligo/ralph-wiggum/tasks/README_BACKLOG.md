# Backlog TDD Veligo - Résumé Exécutif

## 📊 Vue d'ensemble

| Métrique | Valeur |
|----------|--------|
| **Total Tasks** | 156 |
| **Phases** | 6 |
| **WSJF Total** | 866.6 |
| **Tests E2E** | 93+ existants + 68 nouveaux |
| **Modules Backend** | 45 tâches |
| **Templates** | 17 tâches |

## 🚀 Ordre d'exécution (Top 10 WSJF)

| # | Task ID | Description | WSJF | Priority |
|---|---------|-------------|------|----------|
| 1 | AO-IDFM-001 | FranceConnect v2 | 9.8 | P1 |
| 2 | MOD-PAY-001 | Stripe 3DS | 9.5 | P0 |
| 3 | AO-LYON-001 | TCL ID Auth | 9.5 | P1 |
| 4 | J-E2E-005 | Souscription 3DS | 9.5 | P0 |
| 5 | CHAOS-001 | DB Failover | 9.0 | P3 |
| 6 | AO-NANTES-001 | PayNum | 9.2 | P1 |
| 7 | J-E2E-009 | Geo Réservation | 9.0 | P0 |
| 8 | J-E2E-016 | Vol procédure | 9.0 | P0 |
| 9 | MOD-BIKE-001 | Bike Booking | 9.0 | P0 |
| 10 | MOD-AUTH-002 | FranceConnect | 9.2 | P1 |

## 📁 Fichiers générés

```
tools/ralph-wiggum/tasks/
├── VELIGO_TDD_BACKLOG_COMPLET.md    # Backlog complet (156 tâches)
├── VELIGO_MODULE_TASKS.md           # Tâches modules détaillés
├── backlog_veligo_tdd.json          # Format JSON pour Ralph Wiggum
└── tests/
    ├── journeys/
    │   ├── 101-multi-tenant-registration.spec.ts
    │   ├── 105-subscription-3ds.spec.ts
    │   └── 109-geo-reservation.spec.ts
    ├── ao/
    │   ├── idfm-franceconnect-v2.spec.ts
    │   ├── lyon-tcl-auth.spec.ts
    │   └── nantes-paynum.spec.ts
    └── fixtures/
        └── test-data.ts
```

## 🎯 Phases de développement

### Phase 1: Journeys E2E (17 tâches, P0)
- Inscription multi-tenant
- Souscription & paiement
- Booking vélo
- Incidents & support

### Phase 2: AO Compliance (15 tâches, P1)
- IDFM FranceConnect
- Nantes PayNum
- Lyon TCL
- RGPD & RGAA

### Phase 3: White-Label (14 tâches, P1)
- Thèmes & personnalisation
- Domaines multi-tenant
- Modules activables
- Templates

### Phase 4: Modules Backend (45 tâches, P2)
- Auth (7 modules)
- Payment (8 modules)
- Tracking (7 modules)
- Notification (3 modules)
- Bike & Fleet (6 modules)
- RGPD (6 modules)
- Signing (4 modules)
- Map & Integration (4 modules)

### Phase 5: Templates (17 tâches, P2)
- Email (8 templates)
- SMS (4 templates)
- PDF (5 templates)

### Phase 6: Performance & Chaos (9 tâches, P3)
- Load testing
- Chaos engineering

## ✅ Prochaine action

Lancer le pipeline TDD avec les 10 tâches prioritaires:

```bash
# cd /Users/sylvain/_LAPOSTE/_VELIGO2/tools/ralph-wiggum
# python3 wiggum_tdd.py --task backlog_veligo_tdd.json --workers 10
```

## 📈 Métriques de couverture

| Catégorie | Existant | Nouveau | Total |
|-----------|----------|---------|-------|
| Tests E2E | 93 | 68 | 161 |
| Modules Rust | 71 | 0 | 71 |
| Templates | 6 | 17 | 23 |
| Performance | 2 | 9 | 11 |
