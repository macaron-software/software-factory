# SF Platform — Compliance & Traceability Wiki
# SOC2 Type II · ISO 27001:2022 · GDPR · SecureByDesign v1.1

## Table of Contents
1. [Traceability Chain](#1-traceability-chain)
2. [SOC2 Trust Services Criteria](#2-soc2-trust-services-criteria)
3. [ISO 27001:2022 Controls](#3-iso-270012022-controls)
4. [RBAC Matrix](#4-rbac-matrix)
5. [Security Controls (25 SBD)](#5-security-controls-25-sbd)
6. [UX Laws Reference](#6-ux-laws-reference)
7. [UI Components Catalog](#7-ui-components-catalog)
8. [A11Y Patterns](#8-a11y-patterns)
9. [Design Tokens](#9-design-tokens)
10. [i18n Coverage](#10-i18n-coverage)
11. [Observability](#11-observability)
12. [DR & Business Continuity](#12-dr--business-continuity)
13. [GDPR Data Lifecycle](#13-gdpr-data-lifecycle)
14. [Quality Gates](#14-quality-gates)
15. [Audit Evidence Map](#15-audit-evidence-map)

---

## 1. Traceability Chain

### E2E UUID Traceability Model
Every artifact in the SF Platform is tracked with a unique identifier forming an
unbroken chain from business need to deployed code:

```
Persona (agent persona)
  └→ Feature  (feat-XXXXXX)  — business capability
       └→ User Story  (us-XXXXXX)  — user-facing behavior
            └→ Acceptance Criteria  (ac-XXXXXX)  — Gherkin Given/When/Then
                 ├→ IHM/Screen  — route, CRUD ops, RBAC roles
                 ├→ Source Code  — // Ref: feat-XXXXXX header in every file
                 ├→ Unit Test    — // Verify: ac-XXXXXX validates specific AC
                 └→ E2E Test     — validates full user journey
```

### Traceability Agents
| Agent | ID | Role | Tools | Veto |
|-------|----|------|-------|------|
| Nadia Ferreira | trace-lead | Coverage validation | legacy_scan, link, coverage, validate, create_feature, create_story | STRONG |
| Mehdi Ouali | trace-auditor | Gap detection | legacy_scan, coverage, validate, code_read/search | No |
| Sophie Blanchard | trace-writer | Fix gaps | code_write/edit, create_feature/story, traceability_link, git_commit | No |
| Lucas Moreno | trace-monitor | Coverage tracking | coverage, validate, project_health | No |

### Traceability Phase in Product Lifecycle
Phase 13 `traceability-check` (sequential, gate=no_veto):
1. trace-auditor: scans all files for missing `// Ref:` headers
2. trace-writer: adds headers, creates features/stories in DB, updates SPECS.md
3. trace-lead: validates coverage ≥ 80%, VETOs if insufficient

### Automated Enforcement
- **Adversarial L0**: MISSING_TRACEABILITY check catches files without `// Ref:` headers
- **Scheduler**: every 6h, all active projects scanned; mission launched if coverage < 80%
- **Auto-persist**: `_auto_persist_backlog()` parses PM markdown tables → features/stories in DB

---

## 2. SOC2 Trust Services Criteria

### Trust Services Mapping

| TSC | Control | SF Implementation | Evidence | Status |
|-----|---------|-------------------|----------|--------|
| CC1.1 | Control Environment | RBAC module + Agent Personas | `rbac/`, `agents/store.py` 215 agents | ✅ |
| CC1.2 | Board/Mgmt Oversight | CTO Agent (Jarvis) | `a2a/jarvis_mcp.py`, `strat-cto` | ✅ |
| CC1.4 | Workforce Competence | Agent Skills + Thompson Selection | `skills/` 1098 .md, `ac/skill_thompson.py` | ✅ |
| CC2.1 | Info Quality & Communication | SSE Events + Audit Trail | `events/`, `admin_audit_log` table | ✅ |
| CC3.1 | Risk Assessment | Adversarial Guard L0+L1 | `agents/adversarial.py` 25 det checks | ✅ |
| CC4.1 | Monitoring Activities | AC Reward + Convergence | `ac/reward.py` 14-dim, `ac/convergence.py` | ✅ |
| CC4.2 | Evaluate & Communicate | 17 Quality Gates | `metrics/quality.py`, adversarial, CI | ✅ |
| CC5.1 | Control Activities | Tool ACL 5-layer | `agents/permissions.py`, `guardrails.py` | ✅ |
| CC6.1 | Access Control | JWT + bcrypt + rate-limit | `auth/`, `security/` | ✅ |
| CC6.3 | Access Revocation | Session management | `auth/routes.py`, `sessions/` | ✅ |
| CC6.6 | System Operations | Health probes + auto-resume | `/api/health`, `ops/auto_resume.py` | ✅ |
| CC6.8 | Change Management | CI/CD + adversarial gates | `adversarial_guard()`, blue-green deploy | ✅ |
| CC7.1 | System Monitoring | Platform watchdog + metrics | `ops/platform_watchdog.py`, `metrics/` | ✅ |
| CC7.2 | Incident Response | PUA escalation + auto-heal | `agents/pua.py` L1-L4, `ops/auto_heal.py` | ✅ |
| CC8.1 | Change Management | Version control + traceability | git tools, `traceability/` module | ✅ |

---

## 3. ISO 27001:2022 Controls

| Annex A | Control Name | SF Feature | Evidence File | Status |
|---------|-------------|------------|---------------|--------|
| A.5.1 | Info Security Policies | Security module | `security/` (prompt_guard, output_validator) | ✅ |
| A.5.8 | Info Security in Projects | Adversarial guard per phase | `adversarial_guard()` in pattern execution | ✅ |
| A.5.15 | Access Control | RBAC 5-layer | `rbac/`, `agents/permissions.py` | ✅ |
| A.5.17 | Authentication | JWT + bcrypt + MFA-ready | `auth/` module | ✅ |
| A.5.19 | Supplier Relationships | Dependency audit | SBD-14, SBD-16 controls | ⚠️ Partial |
| A.5.24 | Incident Mgmt Planning | Auto-heal + PUA + DR | `ops/auto_heal.py`, `agents/pua.py` | ✅ |
| A.5.34 | Privacy & PII | Sanitize + output validator | `security/sanitize.py`, `output_validator.py` | ✅ |
| A.8.1 | Asset Inventory | Agent store + tool registry | `agents/store.py` ~215, `tools/` 57 modules | ✅ |
| A.8.8 | Technical Vulnerability | CI ruff + complexity gate | `ruff check`, `scripts/complexity_gate.py` | ✅ |
| A.8.15 | Logging | Audit log + SSE events | DB audit tables, `events/` | ✅ |
| A.8.22 | Network Controls | Rate limiting + SSRF block | `rate_limit.py`, SBD-12 | ✅ |
| A.8.24 | Cryptography | Secrets via Infisical/env | `config.py`, no secrets in code | ✅ |
| A.8.25 | Secure Development | Adversarial + quality gates | `agents/adversarial.py`, `metrics/quality.py` | ✅ |
| A.8.26 | App Security Requirements | Output validation + CSP | `security/output_validator.py` | ✅ |

---

## 4. RBAC Matrix

| Role | Create | Read | Update | Delete | Deploy | Veto | Audit | SOC2 |
|------|--------|------|--------|--------|--------|------|-------|------|
| admin | ✅ | ✅ | ✅ | ✅ | ✅ | - | ✅ | CC6.1,CC6.3 |
| cto | ✅ | ✅ | ✅ | - | - | ✅ | - | CC1.1,CC1.2 |
| pm | ✅ | ✅ | ✅ | - | - | - | - | CC1.4 |
| lead_dev | ✅ | ✅ | ✅ | - | - | ✅ | - | CC8.1 |
| developer | ✅ | ✅ | ✅ | - | - | - | - | CC8.1 |
| qa | ✅ | ✅ | ✅ | - | - | ✅ | - | CC7.1 |
| devops | ✅ | ✅ | ✅ | - | ✅ | ✅ | - | CC6.6,CC7.2 |
| security | - | ✅ | - | - | - | ✅ | ✅ | CC6.1,CC6.8 |
| trace_lead | ✅ | ✅ | ✅ | - | - | ✅ | - | CC4.1 |
| viewer | - | ✅ | - | - | - | - | - | CC6.1 |
| auditor | - | ✅ | - | - | - | - | ✅ | CC4.1,CC4.2 |
| scrum_master | ✅ | ✅ | ✅ | - | - | - | - | CC1.4 |

---

## 5. Security Controls (25 SBD)

### Layer 1 — Input & Output Integrity
| ID | Control | Standards | Tier |
|----|---------|-----------|------|
| SBD-01 | Input Validation & Sanitization | OWASP A03, NIST PR.DS-1, ISO A.8.24 | LOW |
| SBD-02 | Prompt Injection Defense | OWASP LLM01, NIST PR.DS-1 | LOW |
| SBD-03 | Output Encoding & CSP | OWASP A03+A05, LLM05, ISO A.8.26 | LOW |

### Layer 2 — Identity & Access
| SBD-04 | Authentication Integrity | OWASP A07, CIS 5 | STANDARD |
| SBD-05 | Authorization (default DENY) | OWASP A01, CIS 6 | STANDARD |
| SBD-06 | Least Privilege | OWASP A01, LLM06, CIS 5+6 | STANDARD |

### Layer 3 — Data & Cryptography
| SBD-07 | Secrets Management | OWASP A02, CIS 4 | LOW |
| SBD-08 | Cryptographic Standards | OWASP A02, CIS 3 | STANDARD |
| SBD-09 | Data Minimization | OWASP A02, ISO A.5.34 | STANDARD |

### Layer 4 — Resilience & Monitoring
| SBD-10 | Security Logging & Audit | OWASP A09, CIS 8 | LOW |
| SBD-11 | Rate Limiting | OWASP A07, LLM10, CIS 13 | LOW |
| SBD-12 | SSRF Prevention | OWASP A10, CIS 13 | STANDARD |
| SBD-13 | Error Handling | OWASP A05, CIS 4 | LOW |

### Layer 5 — Architecture & Supply Chain
| SBD-14 | Dependency Security | OWASP A06, CIS 2 | STANDARD |
| SBD-15 | CI/CD Pipeline Integrity | OWASP A08, CIS 16 | STANDARD |
| SBD-16 | LLM Model Integrity | OWASP LLM03+04 | REGULATED |
| SBD-17 | System Prompt Protection | OWASP LLM07 | STANDARD |
| SBD-18 | RAG & Embedding Security | OWASP LLM08 | REGULATED |
| SBD-19 | LLM Output Validation | OWASP LLM05+09 | STANDARD |
| SBD-20 | Network & CORS | OWASP A05, CIS 13 | STANDARD |
| SBD-21 | Secure Design (Fail Secure) | OWASP A04, CIS 14 | STANDARD |
| SBD-22 | Governance & Posture | OWASP A04, CIS 14 | STANDARD |
| SBD-23 | Asset Inventory & IaC | NIST ID.AM, CIS 1+2 | STANDARD |
| SBD-24 | Incident Response | NIST DE+RS+RC, CIS 17 | STANDARD |
| SBD-25 | Privacy & Compliance | GDPR, CCPA, HIPAA | REGULATED |

---

## 6. UX Laws Reference

| # | Law | Key Takeaway | Category |
|---|-----|-------------|----------|
| 1 | Aesthetic-Usability | Beautiful = perceived usable | Perception |
| 2 | Choice Overload | Limit to 3-5 options | Cognition |
| 3 | Chunking | Group into 5-9 items | Cognition |
| 4 | Cognitive Bias | Design for biases, use defaults wisely | Cognition |
| 5 | Cognitive Load | Minimize extraneous, maximize germane | Cognition |
| 6 | Doherty Threshold | Response < 400ms | Performance |
| 7 | Fitts's Law | Touch targets min 44px, near attention | Interaction |
| 8 | Flow | Clear goals, immediate feedback | Engagement |
| 9 | Goal-Gradient | Show progress, reward near completion | Motivation |
| 10 | Hick's Law | Min choices when speed matters | Cognition |
| 11 | Jakob's Law | Use familiar patterns | Familiarity |
| 12 | Common Region | Bounded area = grouped | Perception |
| 13 | Proximity | Near = related | Perception |
| 14 | Pragnanz | Simplest form perceived | Perception |
| 15 | Similarity | Same style = same group | Perception |
| 16 | Uniform Connectedness | Connected = related | Perception |
| 17 | Mental Model | Match user expectations | Cognition |
| 18 | Miller's Law | 7 plus/minus 2 items | Cognition |
| 19 | Occam's Razor | Simplest solution | Simplicity |
| 20 | Active User Paradox | Users skip manuals, learn by doing | Behavior |
| 21 | Pareto Principle | 80/20 rule | Strategy |
| 22 | Parkinson's Law | Task inflates to fill time | Productivity |
| 23 | Peak-End Rule | Peak + end moments matter most | Experience |
| 24 | Postel's Law | Liberal input, strict output | Robustness |
| 25 | Selective Attention | Focus on goal-related stimuli | Attention |
| 26 | Serial Position | First and last items remembered | Memory |
| 27 | Tesler's Law | Irreducible complexity exists | Complexity |
| 28 | Von Restorff | Different item most remembered | Attention |
| 29 | Working Memory | Temp storage for active tasks | Cognition |
| 30 | Zeigarnik Effect | Incomplete tasks remembered better | Motivation |

---

## 7. UI Components Catalog

### 60 Components by Atomic Level

**Atoms (12)**: Button, Badge, Icon (SVG Feather), Label, Link, Heading, Image, Input, Separator, Spacer, Toggle/Switch, Visually Hidden

**Molecules (28)**: Accordion, Alert, Avatar, Breadcrumb, Card, Checkbox, Combobox, Color Picker, Date Input, Drawer, Dropdown, Empty State, Fieldset, File Upload, Pagination, Popover, Progress Bar, Progress Tracker, Radio, Rating, Search, Segmented Control, Select, Skeleton, Slider, Spinner, Stepper, Tabs, Toast, Tooltip

**Organisms (12)**: Carousel, Data Table, Footer, Form, Header, Hero, Modal/Dialog, Navigation, Rich Text Editor, Tree View, Video Player

### Skeleton Loading Required
Components that MUST have skeleton variants: Avatar, Card, Carousel, Empty State, Header, Hero, Image, List, Progress Bar, Progress Tracker, Skeleton, Table

---

## 8. A11Y Patterns

### 30 WAI-ARIA APG Patterns
Accordion, Alert, Alert Dialog, Breadcrumb, Button, Carousel, Checkbox, Combobox,
Dialog (Modal), Disclosure, Feed, Grid, Landmarks, Link, Listbox, Menu & Menubar,
Menu Button, Meter, Radio Group, Slider, Multi-Thumb Slider, Spinbutton, Switch,
Table, Tabs, Toolbar, Tooltip, Tree View, Treegrid, Window Splitter

### Core Rules
1. Semantic HTML first — ARIA supplements, not replaces
2. All interactive elements keyboard accessible
3. All interactive elements have accessible name
4. Focus management: visible indicator, logical order, traps for modals
5. State changes communicated to assistive technology
6. Color alone NEVER conveys meaning
7. Contrast: 4.5:1 normal text, 3:1 large text (WCAG AA)

---

## 9. Design Tokens

### Color System (Dark Theme, WCAG AA)
| Token | Value | Usage |
|-------|-------|-------|
| --bg-primary | #0f0a1a | Page background |
| --bg-secondary | #1a1425 | Section background |
| --bg-card | #201a2e | Card background |
| --purple | #a855f7 | Accent primary |
| --success | #10b981 | Success states |
| --warning | #f59e0b | Warning states |
| --error | #ef4444 | Error states |
| --info | #3b82f6 | Info states |
| --text-primary | #f8f8ff | Primary text |
| --text-secondary | #a0a0b8 | Secondary text |

### Typography: JetBrains Mono
| Token | Value | Size |
|-------|-------|------|
| --font-size-xs | 0.75rem | 12px |
| --font-size-sm | 0.875rem | 14px |
| --font-size-base | 1rem | 16px |
| --font-size-lg | 1.125rem | 18px |

### Spacing Scale
xs=0.25rem sm=0.5rem md=1rem lg=1.5rem xl=2rem 2xl=3rem

### Radius Scale
sm=0.25rem md=0.5rem lg=0.75rem xl=1rem full=9999px

---

## 10. i18n Coverage

### 40 Languages
**LTR (34)**: en, fr, es, pt, de, it, nl, pl, ro, cs, sk, hu, hr, bg, uk, ru, el, tr, vi, th, ko, ja, zh-CN, zh-TW, id, ms, tl, hi, bn, sw, am, ha, yo, ig

**RTL (6)**: ar, he, fa, ur, ps, ku

### Implementation
- CSS logical properties (margin-inline-start, not margin-left)
- CLDR plural rules per language (Arabic: 6 forms)
- Babel date/number/currency formatting
- ICU message format for interpolation
- Empathetic messages localized per culture

---

## 11. Observability

### OTEL Traces
mission.execute → phase.execute → agent.invoke → tool.call

### Key Metrics
| Metric | Type | Alert Threshold |
|--------|------|-----------------|
| mission.duration_seconds | Histogram | > 2h = CRITICAL |
| llm.request_duration | Histogram | > 30s = WARNING |
| adversarial.reject_count | Counter | > 80% rate = WARNING |
| quality.score | Gauge | < 0.5 = WARNING |
| traceability.coverage_pct | Gauge | < 0.6 = WARNING |

### Health Endpoints
- `GET /api/health` — DB + Redis
- `GET /api/ready` — 503 during drain
- `GET /api/metrics` — Prometheus format

---

## 12. DR & Business Continuity

### RTO/RPO Targets
| Tier | RTO | RPO | Systems |
|------|-----|-----|---------|
| Critical | 15 min | 0 | Auth, DB, API |
| Important | 1 hour | 5 min | Missions, SSE |
| Standard | 4 hours | 1 hour | Analytics |
| Low | 24 hours | 24 hours | Evolution, Darwin |

### Backup Schedule
Hourly pg_dump (48h retention), Daily full (30d), Weekly (90d), Monthly (1y)

### Failover
nginx lb + proxy_next_upstream. Blue-green Docker. PG WAL streaming.

---

## 13. GDPR Data Lifecycle

```
Collection(consent, minimize, notice)
  → Processing(purpose limitation, audit log, lawful basis)
    → Storage(encryption at rest+transit, access control, backup)
      → Retention(30d tokens, 90d logs, 365d audit)
        → Deletion(purge PII, anonymize logs, verify, certify)
```

### Art. 17 — Right to Erasure
1. Delete personal data from users table
2. Anonymize audit logs (keep structure, replace user_id)
3. Delete sessions
4. Schedule backup purge
5. Log deletion event (without PII)

---

## 14. Quality Gates (17 Layers)

| # | Gate | Type | Description |
|---|------|------|-------------|
| 1 | Guardrails | HARD | Regex + destructive action blocking |
| 2 | Veto | HARD | ABSOLUTE/STRONG/ADVISORY hierarchy |
| 3 | Prompt Injection | HARD | Score 0-10, block at 7 |
| 4 | Tool ACL | HARD | 5-layer (acl.sandbox.rate.write.git) |
| 5 | Adversarial L0 | HARD | 25 deterministic checks |
| 6 | Adversarial L1 | SOFT | LLM semantic reasoning |
| 7 | AC Reward | HARD | R in [-1,+1], 14 dimensions, @60% |
| 8 | Convergence | SOFT | Plateau/regression/spike detection |
| 9 | RBAC | HARD | Roles x actions x artifacts |
| 10 | CI Syntax | HARD | ruff check |
| 11 | CI Compile | HARD | Python compile |
| 12 | CI Tests | HARD | pytest |
| 13 | CI Complexity | SOFT | CC>10err, MI<10err, LOC>500err |
| 14 | SonarQube | SOFT | External analysis |
| 15 | Deploy | HARD | Blue-green canary |
| 16 | Output Validator | SOFT | Content safety |
| 17 | Stale Prune | SOFT | Remove outdated builtins |

---

## 15. Audit Evidence Map

### For SOC2 Auditor
| Evidence Type | Location | Frequency |
|---------------|----------|-----------|
| Access logs | `admin_audit_log` table | Continuous |
| Auth events | `auth/` module logs | Continuous |
| Quality reports | `ac_cycles` table | Per mission |
| Adversarial results | Phase results in DB | Per agent execution |
| Code changes | Git history + agent attribution | Per commit |
| Traceability coverage | `traceability_coverage` tool | Every 6h |
| Rate limiting | `rate_limit.py` Redis logs | Continuous |
| Health checks | `/api/health` | Every 30s |
| Backup verification | Monthly restore drill | Monthly |
| Incident response | `ops/auto_heal.py` logs | On event |

### For ISO 27001 Auditor
| Statement of Applicability | Controls: 14 implemented, 1 partial (A.5.19) |
| Risk Treatment Plan | Adversarial guard + 17 quality gates |
| Information Security Policy | `security/` module + SBD controls |
| Asset Register | `agents/store.py` + `tools/` + DB schema |
| Access Control Policy | `rbac/` + `auth/` + `agents/permissions.py` |
| Incident Management | `ops/auto_heal.py` + PUA escalation |

---

*Generated: 2026-03-14 | SF Platform v2.0 | Skills: 1098 | Agents: ~215 | Quality Gates: 17*
*Owner: RBAC role `auditor` or `admin` required for write access*
