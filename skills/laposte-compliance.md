---
name: laposte-compliance
description: >
  Validates code and architecture against La Poste / BSCC mandatory technical standards.
  Used by compliance critic agents on La Poste domain projects.
metadata:
  category: compliance
  domain: la-poste
  triggers:
    - "after any milestone on La Poste or BSCC projects"
    - "when reviewing code for La Poste compliance"
    - "when checking stack conformity"
---

# La Poste / BSCC Compliance Review

## MANDATORY STACK — NON-NEGOTIABLE

| Layer | Required | Forbidden |
|-------|----------|-----------|
| Backend | Java 17 + Spring Boot 3.x | Python, Node.js, Go, Ruby (unless explicitly authorized) |
| Frontend | Angular 17+ TypeScript strict | React, Vue, plain JS |
| Database | PostgreSQL 15+ | **SQLite**, MongoDB, MySQL, H2 in prod |
| Cache | Redis 7 | Memcached, in-memory only |
| CI/CD | GitLab CI/CD (gitlab.azure.innovation-laposte.io) | GitHub Actions, Jenkins (unless federated) |
| Auth | SAML2 / SSO La Poste (Keycloak) | Custom JWT, BasicAuth on public endpoints |
| Infra | Azure AKS francecentral | Any non-sovereign cloud storage for PII |

## COMPLIANCE CHECKLIST — Run after every milestone

### 1. Stack Conformity
- [ ] No SQLite dependency in pom.xml / build.gradle
- [ ] Spring Boot version ≥ 3.x
- [ ] Java version = 17 (not 11, not 21 without waiver)
- [ ] Angular version ≥ 17 with strict TypeScript

### 2. API Contract
- [ ] OpenAPI 3.1 spec present and up-to-date
- [ ] All new endpoints documented in openapi.yaml
- [ ] Versioning scheme: `/api/v{N}/` prefix
- [ ] Rate limiting configured (Spring Cloud Gateway or filter)

### 3. Security (OWASP / ANSSI)
- [ ] Input validation: Bean Validation (Jakarta) on all DTOs
- [ ] No raw SQL queries — use JPA/JPQL or named queries
- [ ] CORS policy explicitly defined (not wildcard `*`)
- [ ] No secrets in source code (use Azure Key Vault / env vars)
- [ ] Dependencies: no known CVE in pom.xml (run `mvn dependency-check`)

### 4. Audit Trail (BSCC-specific)
- [ ] Every citizen action logged to audit trail service
- [ ] Log format: JSON structured, includes timestamp, user_id (anonymized), action, resource_id
- [ ] Logs shipped to ELK Stack
- [ ] Sensitive data anonymized in logs (CNIL)

### 5. Accessibility (RGAA 4.1 Level AA)
- [ ] All Solaris Design System components used (no custom equivalents)
- [ ] `aria-*` attributes on interactive elements
- [ ] Color contrast ≥ 4.5:1 (normal text), ≥ 3:1 (large text)
- [ ] Keyboard navigation functional for all features
- [ ] No `<div>` used for buttons/links

### 6. RGPD
- [ ] No PII logged in plain text
- [ ] Data retention policy documented
- [ ] Consentement collecté si données personnelles

## VERDICT FORMAT

After checking, output:
```
## Compliance Report — {milestone_name}

### ✅ Compliant
- (list passing checks)

### ❌ Non-Compliant (BLOCKING)
- (list violations with file:line if applicable)

### ⚠️ Warnings (non-blocking)
- (list items to fix before production)

### Verdict: PASS | FAIL
```

If verdict is FAIL, list exact fixes required. Do NOT approve until all blocking items resolved.
