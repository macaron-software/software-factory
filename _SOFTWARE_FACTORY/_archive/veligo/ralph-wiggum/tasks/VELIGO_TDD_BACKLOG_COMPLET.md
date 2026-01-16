# Veligo TDD Backlog Complet
**Généré**: 2026-01-14
**Total Tasks**: 156
**Méthode**: WSJF Priority Scoring

---

## 🚴 PHASE 1: JOURNEYS E2E ESSENTIELS (Priority P0)

### 1.1 Inscription & Onboarding

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| J-E2E-001 | Inscription multi-tenant avec validation email | 9.2 | 3 | `journeys/101-multi-tenant-registration.spec.ts` |
| J-E2E-002 | Inscription avec pièce identité (IDNum) | 8.8 | 4 | `journeys/102-idnum-verification.spec.ts` |
| J-E2E-003 | Onboarding complet avec choix plan | 8.5 | 3 | `journeys/103-onboarding-flow.spec.ts` |
| J-E2E-004 | Inscription rapide (social login first) | 7.9 | 3 | `journeys/104-social-first-registration.spec.ts` |

### 1.2 Souscription & Paiement

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| J-E2E-005 | Souscription avec paiement CB 3D Secure | 9.5 | 4 | `journeys/105-subscription-3ds.spec.ts` |
| J-E2E-006 | Souscription SEPA avec mandat | 8.3 | 3 | `journeys/106-sepa-mandate.spec.ts` |
| J-E2E-007 | Renouvellement automatique - échec paiement | 7.8 | 3 | `journeys/107-auto-renewal-failure.spec.ts` |
| J-E2E-008 | Upgrade/downgrade plan en cours d'abonnement | 7.5 | 3 | `journeys/108-plan-change.spec.ts` |

### 1.3 Booking Vélo

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| J-E2E-009 | Réservation vélo avec géolocalisation | 9.0 | 4 | `journeys/109-geo-reservation.spec.ts` |
| J-E2E-010 | Annulation réservation avant expiration | 6.5 | 2 | `journeys/110-cancel-before-expiry.spec.ts` |
| J-E2E-011 | Extension réservation en cours | 6.8 | 3 | `journeys/111-extend-reservation.spec.ts` |
| J-E2E-012 | Location longue durée (>24h) | 7.2 | 4 | `journeys/112-long-term-rental.spec.ts` |
| J-E2E-013 | Bike sharing transitoire (multi-station) | 8.0 | 5 | `journeys/113-bike-sharing.spec.ts` |

### 1.4 Incidents & Support

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| J-E2E-014 | Déclaration incident pendant course | 8.5 | 3 | `journeys/114-incident-during-ride.spec.ts` |
| J-E2E-015 | Signalement vélo endommagé | 7.0 | 2 | `journeys/115-damaged-bike-report.spec.ts` |
| J-E2E-016 | Vol de vélo - procédure | 9.0 | 4 | `journeys/116-theft-procedure.spec.ts` |
| J-E2E-017 | Chat support en temps réel | 6.5 | 3 | `journeys/117-live-support.spec.ts` |

---

## 🎯 PHASE 2: COMPLIANCE AO (Priority P1)

### 2.1 IDFM - FranceConnect

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| AO-IDFM-001 | Authentification FranceConnect v2 | 9.8 | 4 | `ao/idfm-franceconnect-v2.spec.ts` |
| AO-IDFM-002 | Attribution aide IDFM (50%) | 8.5 | 3 | `ao/idfm-subsidy.spec.ts` |
| AO-IDFM-003 | Tarification selon zonage IDFM | 7.5 | 3 | `ao/idfm-zoning.spec.ts` |
| AO-IDFM-004 | Reporting mensuel IDFM | 6.8 | 4 | `ao/idfm-monthly-report.spec.ts` |

### 2.2 Nantes - PayNum

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| AO-NANTES-001 | Paiement PayNum wallet | 9.2 | 4 | `ao/nantes-paynum.spec.ts` |
| AO-NANTES-002 | Intégrationbox Nantes sécurisés | 8.8 | 5 | `ao/nantes-box-secure.spec.ts` |
| AO-NANTES-003 | Correspondance transport Naolib | 7.2 | 4 | `ao/nantes-naolib.spec.ts` |
| AO-NANTES-004 | Subvention Nantes Métropole | 6.5 | 3 | `ao/nantes-subsidy.spec.ts` |

### 2.3 Lyon - TCL

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| AO-LYON-001 | Authentification TCL ID | 9.5 | 4 | `ao/lyon-tcl-auth.spec.ts` |
| AO-LYON-002 | Tarification multimodal TCL | 8.0 | 4 | `ao/lyon-multimodal.spec.ts` |
| AO-LYON-003 | Correspondance métro/tram | 7.8 | 4 | `ao/lyon-correspondence.spec.ts` |
| AO-LYON-004 | ReportingTCL mensuel | 6.2 | 3 | `ao/lyon-tcl-report.spec.ts` |

### 2.4 RGPD & Accessibilité

| ID | Task | WSJF File |
|----|------|------|---- | Files | Test---|-----------|
| AO-RGPD-001 | Export données GDPR (Article 20) | 9.0 | 3 | `ao/rgpd-data-export.spec.ts` |
| AO-RGPD-002 | Droit à l'effacement (Article 17) | 8.8 | 3 | `ao/rgpd-right-erasure.spec.ts` |
| AO-RGPD-003 | Consentement granulaire tracking | 7.5 | 3 | `ao/rgpd-consent.spec.ts` |
| AO-RGPD-004 | Audit trail RGPD | 6.8 | 4 | `ao/rgpd-audit.spec.ts` |
| AO-RGAA-001 | Navigation clavier complète | 8.5 | 3 | `ao/rgaa-keyboard.spec.ts` |
| AO-RGAA-002 | Compatibilité lecteurs d'écran | 8.0 | 3 | `ao/rgaa-screen-reader.spec.ts` |
| AO-RGAA-003 | Contraste et zoom 200% | 7.5 | 2 | `ao/rgaa-contrast.spec.ts` |

---

## 🎨 PHASE 3: WHITE-LABEL (Priority P1)

### 3.1 Thèmes & Personnalisation

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| WL-THEME-001 | Changement theme dynamique | 7.8 | 3 | `white-label/theme-dynamic.spec.ts` |
| WL-THEME-002 | Logos custom par tenant | 7.2 | 2 | `white-label/custom-logo.spec.ts` |
| WL-THEME-003 | Couleurs personnalisables | 6.5 | 2 | `white-label/custom-colors.spec.ts` |
| WL-THEME-004 | Polices custom (Google Fonts) | 5.8 | 2 | `white-label/custom-font.spec.ts` |

### 3.2 Domaines & Multi-tenant

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| WL-DOMAIN-001 | Multiple sous-domaines | 8.5 | 4 | `white-label/multi-subdomain.spec.ts` |
| WL-DOMAIN-002 | Domaines personnalisés (CNAME) | 7.8 | 4 | `white-label/custom-domain.spec.ts` |
| WL-DOMAIN-003 | DNS validation automatique | 6.5 | 3 | `white-label/dns-validation.spec.ts` |
| WL-DOMAIN-004 | SSL automatique par domain | 8.0 | 4 | `white-label/ssl-wildcard.spec.ts` |

### 3.3 Modules Activables

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| WL-MODULE-001 | Activation module per tenant | 8.8 | 3 | `white-label/module-activation.spec.ts` |
| WL-MODULE-002 | Module trial (7 jours) | 6.5 | 3 | `white-label/module-trial.spec.ts` |
| WL-MODULE-003 | Dépendances modules | 7.2 | 4 | `white-label/module-deps.spec.ts` |
| WL-MODULE-004 | Quotas par tenant | 6.8 | 3 | `white-label/tenant-quotas.spec.ts` |

### 3.4 Templates

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| WL-TPL-001 | Templates email custom | 7.5 | 3 | `white-label/email-templates.spec.ts` |
| WL-TPL-002 | Templates SMS custom | 6.8 | 3 | `white-label/sms-templates.spec.ts` |
| WL-TPL-003 | PDF contract custom | 7.2 | 4 | `white-label/pdf-templates.spec.ts` |
| WL-TPL-004 | Variables dynamiques | 6.5 | 2 | `white-label/template-vars.spec.ts` |

---

## 📦 PHASE 4: MODULES BACKEND (Priority P2)

### 4.1 Auth Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-AUTH-001 | Module auth-email complet | 8.5 | 4 | `modules/auth-email.spec.ts` |
| MOD-AUTH-002 | Module auth-franceconnect | 9.2 | 5 | `modules/auth-franceconnect.spec.ts` |
| MOD-AUTH-003 | Module auth-idnum | 8.8 | 4 | `modules/auth-idnum.spec.ts` |
| MOD-AUTH-004 | Module auth-magic-link | 7.5 | 4 | `modules/auth-magic-link.spec.ts` |
| MOD-AUTH-005 | Module auth-phone-sms | 7.8 | 4 | `modules/auth-phone-sms.spec.ts` |
| MOD-AUTH-006 | Module auth-biometric | 6.5 | 4 | `modules/auth-biometric.spec.ts` |
| MOD-AUTH-007 | Module mfa-security TOTP | 8.0 | 4 | `modules/mfa-security.spec.ts` |

### 4.2 Payment Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-PAY-001 | Module payment-stripe | 9.5 | 5 | `modules/payment-stripe.spec.ts` |
| MOD-PAY-002 | Module payment-paynum | 8.8 | 5 | `modules/payment-paynum.spec.ts` |
| MOD-PAY-003 | Module payment-sepa | 8.0 | 4 | `modules/payment-sepa.spec.ts` |
| MOD-PAY-004 | Module payment-cb | 7.8 | 4 | `modules/payment-cb.spec.ts` |
| MOD-PAY-005 | Module payment-paypal | 7.2 | 4 | `modules/payment-paypal.spec.ts` |
| MOD-PAY-006 | Module payment-apple-pay | 7.5 | 4 | `modules/payment-apple-pay.spec.ts` |
| MOD-PAY-007 | Module payment-google-pay | 7.5 | 4 | `modules/payment-google-pay.spec.ts` |
| MOD-PAY-008 | Module billing-invoicing | 6.8 | 4 | `modules/billing-invoicing.spec.ts` |

### 4.3 Tracking Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-TRK-001 | Module tracking-velco | 8.5 | 4 | `modules/tracking-velco.spec.ts` |
| MOD-TRK-002 | Module tracking-invoxia | 7.8 | 4 | `modules/tracking-invoxia.spec.ts` |
| MOD-TRK-003 | Module tracking-sherlock | 7.5 | 4 | `modules/tracking-sherlock.spec.ts` |
| MOD-TRK-004 | Module tracking-airtag | 7.2 | 4 | `modules/tracking-airtag.spec.ts` |
| MOD-TRK-005 | Module tracking-gps | 8.0 | 4 | `modules/tracking-gps.spec.ts` |
| MOD-TRK-006 | Module tracking-bluetooth | 6.5 | 3 | `modules/tracking-bluetooth.spec.ts` |
| MOD-TRK-007 | Module tracking-abeeway | 6.8 | 4 | `modules/tracking-abeeway.spec.ts` |

### 4.4 Notification Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-NTF-001 | Module notification-email | 8.0 | 4 | `modules/notification-email.spec.ts` |
| MOD-NTF-002 | Module notification-sms | 7.5 | 4 | `modules/notification-sms.spec.ts` |
| MOD-NTF-003 | Module notification-push | 7.8 | 4 | `modules/notification-push.spec.ts` |

### 4.5 Bike & Fleet Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-BIKE-001 | Module bike-booking | 9.0 | 5 | `modules/bike-booking.spec.ts` |
| MOD-BIKE-002 | Module bike-catalog | 7.5 | 4 | `modules/bike-catalog.spec.ts` |
| MOD-BIKE-003 | Module bike-cargo-pro | 8.2 | 5 | `modules/bike-cargo-pro.spec.ts` |
| MOD-BIKE-004 | Module bike-origin-tracking | 7.8 | 4 | `modules/bike-origin-tracking.spec.ts` |
| MOD-BIKE-005 | Module fleet-management | 8.5 | 5 | `modules/fleet-management.spec.ts` |
| MOD-BIKE-006 | Module station-management | 8.8 | 5 | `modules/station-management.spec.ts` |

### 4.6 RGPD & Compliance Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-RGPD-001 | Module gdpr-compliance | 8.8 | 4 | `modules/gdpr-compliance.spec.ts` |
| MOD-RGPD-002 | Module breach-notification | 8.0 | 4 | `modules/breach-notification.spec.ts` |
| MOD-RGPD-003 | Module dpo-interface | 7.2 | 4 | `modules/dpo-interface.spec.ts` |
| MOD-RGPD-004 | Module audit-logs | 7.5 | 4 | `modules/audit-logs.spec.ts` |
| MOD-RGPD-005 | Module rgaa-accessibility | 8.5 | 4 | `modules/rgaa-accessibility.spec.ts` |
| MOD-RGPD-006 | Module open-data-api | 6.5 | 4 | `modules/open-data-api.spec.ts` |

### 4.7 Signing Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-SIGN-001 | Module signing-yousign | 8.5 | 5 | `modules/signing-yousign.spec.ts` |
| MOD-SIGN-002 | Module signing-docusign | 8.0 | 5 | `modules/signing-docusign.spec.ts` |
| MOD-SIGN-003 | Module signing-adobe-sign | 7.5 | 5 | `modules/signing-adobe-sign.spec.ts` |
| MOD-SIGN-004 | Module signing-universign | 7.2 | 5 | `modules/signing-universign.spec.ts` |

### 4.8 Map & Integration Modules

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| MOD-MAP-001 | Module map-google | 8.0 | 4 | `modules/map-google.spec.ts` |
| MOD-MAP-002 | Module map-mapbox | 7.8 | 4 | `modules/map-mapbox.spec.ts` |
| MOD-MAP-003 | Module map-openstreetmap | 7.5 | 4 | `modules/map-openstreetmap.spec.ts` |
| MOD-TCL-001 | Module tcl-integration | 8.5 | 5 | `modules/tcl-integration.spec.ts` |
| MOD-TCL-002 | Module tcl-realtime | 8.0 | 5 | `modules/tcl-realtime.spec.ts` |

---

## 📧 PHASE 5: TEMPLATES (Priority P2)

### 5.1 Email Templates

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| TPL-EMAIL-001 | Template welcome email | 7.5 | 2 | `templates/email-welcome.spec.ts` |
| TPL-EMAIL-002 | Template verification email | 7.2 | 2 | `templates/email-verification.spec.ts` |
| TPL-EMAIL-003 | Template password reset | 6.8 | 2 | `templates/email-password-reset.spec.ts` |
| TPL-EMAIL-004 | Template booking confirmation | 7.0 | 2 | `templates/email-booking-confirm.spec.ts` |
| TPL-EMAIL-005 | Template payment receipt | 6.5 | 2 | `templates/email-payment-receipt.spec.ts` |
| TPL-EMAIL-006 | Template subscription renewal | 6.8 | 2 | `templates/email-subscription-renewal.spec.ts` |
| TPL-EMAIL-007 | Template incident reported | 6.2 | 2 | `templates/email-incident.spec.ts` |
| TPL-EMAIL-008 | Template RGPD notification | 7.5 | 2 | `templates/email-rgpd.spec.ts` |

### 5.2 SMS Templates

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| TPL-SMS-001 | Template SMS booking code | 7.8 | 2 | `templates/sms-booking-code.spec.ts` |
| TPL-SMS-002 | Template SMS reminder | 6.5 | 2 | `templates/sms-reminder.spec.ts` |
| TPL-SMS-003 | Template SMS OTP | 7.2 | 2 | `templates/sms-otp.spec.ts` |
| TPL-SMS-004 | Template SMS incident alert | 6.8 | 2 | `templates/sms-incident-alert.spec.ts` |

### 5.3 PDF Templates

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| TPL-PDF-001 | Template contrat location | 8.5 | 3 | `templates/pdf-contract.spec.ts` |
| TPL-PDF-002 | Template facture | 7.8 | 3 | `templates/pdf-invoice.spec.ts` |
| TPL-PDF-003 | Template attestation | 6.5 | 2 | `templates/pdf-certificate.spec.ts` |
| TPL-PDF-004 | Template rapport mensuel | 7.2 | 3 | `templates/pdf-monthly-report.spec.ts` |
| TPL-PDF-005 | Template rapport AOM | 8.0 | 3 | `templates/pdf-aom-report.spec.ts` |

---

## 📊 PHASE 6: PERFORMANCE & CHAOS (Priority P3)

### 6.1 Performance Tests

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| PERF-001 | Load test: 10k concurrent users | 8.5 | 3 | `performance/load-10k.spec.ts` |
| PERF-002 | Stress test: API limits | 7.8 | 3 | `performance/stress-api.spec.ts` |
| PERF-003 | Endurance test: 24h continuous | 6.5 | 2 | `performance/endurance.spec.ts` |
| PERF-004 | Spike test: traffic surge | 7.2 | 2 | `performance/spike.spec.ts` |

### 6.2 Chaos Engineering

| ID | Task | WSJF | Files | Test File |
|----|------|------|-------|-----------|
| CHAOS-001 | Database failover | 9.0 | 3 | `chaos/db-failover.spec.ts` |
| CHAOS-002 | Redis cache failure | 8.5 | 3 | `chaos/redis-failure.spec.ts` |
| CHAOS-003 | API service degradation | 8.0 | 3 | `chaos/service-degradation.spec.ts` |
| CHAOS-004 | Network partition simulation | 7.5 | 3 | `chaos/network-partition.spec.ts` |
| CHAOS-005 | Region failover | 9.2 | 4 | `chaos/region-failover.spec.ts` |

---

## 📋 SUMMARY

| Phase | Tasks | Total WSJF | Priority |
|-------|-------|------------|----------|
| Phase 1: Journeys E2E | 17 | 134.8 | P0 |
| Phase 2: AO Compliance | 15 | 117.5 | P1 |
| Phase 3: White-Label | 14 | 96.5 | P1 |
| Phase 4: Modules | 45 | 349.8 | P2 |
| Phase 5: Templates | 17 | 112.3 | P2 |
| Phase 6: Performance | 9 | 55.7 | P3 |
| **TOTAL** | **156** | **866.6** | |

---

## 🚀 EXECUTION ORDER (WSJF Sorted)

1. MOD-PAY-001 (payment-stripe) - WSJF 9.5
2. AO-IDFM-001 (FranceConnect v2) - WSJF 9.8
3. MOD-BIKE-001 (bike-booking) - WSJF 9.0
4. CHAOS-005 (region failover) - WSJF 9.2
5. J-E2E-005 (subscription 3DS) - WSJF 9.5
6. AO-LYON-001 (TCL ID) - WSJF 9.5
7. MOD-AUTH-002 (FranceConnect) - WSJF 9.2
8. J-E2E-014 (incident during ride) - WSJF 8.5
9. J-E2E-016 (theft procedure) - WSJF 9.0
10. MOD-TRK-001 (tracking-velco) - WSJF 8.5

