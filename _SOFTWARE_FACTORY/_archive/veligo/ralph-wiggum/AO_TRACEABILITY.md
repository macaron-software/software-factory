# AO Traceability Matrix - Veligo Platform

## Vision
Plateforme de location de vélos en libre-service multi-tenant (IDFM, Nantes, Lyon)
conforme aux exigences des Appels d'Offres (AO) et déployable en marque blanche.

## Mapping AO → User Stories → Tasks

### AO-IDFM (Île-de-France Mobilités)

| AO Ref | Exigence | User Story | Tasks |
|--------|----------|------------|-------|
| AO-IDFM-AUTH-001 | FranceConnect SSO obligatoire | US-001: Login FranceConnect | T001, T002 |
| AO-IDFM-AUTH-002 | MFA pour admins | US-002: MFA Setup | T003 |
| AO-IDFM-PAY-001 | SEPA + CB | US-010: Paiements multiples | T010-T012 |
| AO-IDFM-RGPD-001 | Export données RGPD | US-020: RGPD Compliance | T020-T022 |
| AO-IDFM-A11Y-001 | RGAA AA conformité | US-030: Accessibilité | T030-T032 |
| AO-IDFM-STA-001 | Carte stations temps réel | US-040: Station Map | T040-T042 |
| AO-IDFM-BOOK-001 | Réservation 30 min | US-050: Booking Flow | T050-T055 |

### AO-NANTES (Nantes Métropole)

| AO Ref | Exigence | User Story | Tasks |
|--------|----------|------------|-------|
| AO-NANTES-3.2.1 | Inscription en ligne | US-100: Registration Flow | T100-T102 |
| AO-NANTES-3.2.2 | Abonnements mensuels/annuels | US-110: Subscription Plans | T110-T115 |
| AO-NANTES-3.2.3 | Historique trajets | US-120: Trip History | T120-T122 |
| AO-NANTES-3.3.1 | Dashboard admin | US-130: Admin Dashboard | T130-T135 |
| AO-NANTES-3.3.2 | Rapports AOM | US-140: AOM Reporting | T140-T145 |
| AO-NANTES-3.4.1 | API Open Data | US-150: Open Data API | T150-T152 |

### AO-LYON (Lyon Métropole)

| AO Ref | Exigence | User Story | Tasks |
|--------|----------|------------|-------|
| AO-LYON-TCL-001 | Intégration TCL | US-200: TCL Integration | T200-T205 |
| AO-LYON-PASS-001 | Pass Mobilité | US-210: Multi-modal Pass | T210-T212 |

### White-Label (Marque Blanche)

| Ref | Exigence | User Story | Tasks |
|-----|----------|------------|-------|
| WL-THEME-001 | Thèmes personnalisables | US-300: Tenant Theming | T300-T305 |
| WL-DOMAIN-001 | Multi-domaines | US-310: Custom Domains | T310-T312 |
| WL-CONFIG-001 | Config par tenant | US-320: Tenant Config | T320-T325 |

## Commit Convention

Format: `feat(<TASK_ID>): <description> [<AO_REF>]`

Examples:
```
feat(T001): Implement FranceConnect SSO login [AO-IDFM-AUTH-001]
fix(T020): Fix RGPD data export timeout [AO-IDFM-RGPD-001]
feat(T110): Add subscription plan selector [AO-NANTES-3.2.2]
chore(D008): Deploy T099 changes to production
```

## Traceability Query

Pour trouver tous les commits liés à une exigence AO:
```bash
git log --oneline --grep="AO-IDFM-AUTH"
git log --oneline --grep="AO-NANTES-3.2"
```

Pour voir le statut d'une US:
```bash
grep -r "US-001" tools/ralph-wiggum/tasks/
```
