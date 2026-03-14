# Secure By Design — Deep Skill v1.1
# Source: securebydesign-llmskill (Abdoulaye Sylla, MIT)
# Standards: OWASP Top 10:2021, OWASP LLM Top 10:2025, NIST CSF 2.0, ISO 27001:2022, CIS v8

## WHEN TO ACTIVATE
Writing code, reviewing code, designing APIs, setting up infrastructure, integrating LLMs,
planning deployments, handling auth/data/external services. Proactively flag — don't wait to be asked.

## CRITICALITY TIERS
- **TIER 1 LOW**: Static sites, demos, prototypes. Controls SBD-01 to SBD-13. Advisory tone.
- **TIER 2 STANDARD** (default): SaaS, mobile, APIs with user data. All 25 controls. Full report.
- **TIER 3 REGULATED**: Finance, health, government, >10k PII. All 25 + mandatory threat model.

## ANTI-HALLUCINATION RULES
A. No unverifiable conformance claims — flag for manual review if uncertain
B. Version uncertainty — "verify against [lib] docs for version [X]"
C. Cite specific controls only — "OWASP A03" not "covers all OWASP"
D. Always close with scope-of-assurance statement
E. Unknown stack — say so explicitly

## 25 CONTROLS

### LAYER 1 — INPUT & OUTPUT INTEGRITY
**SBD-01 · Input Validation** (OWASP A03, NIST PR.DS-1, ISO A.8.24, CIS 4)
- Validate type/format/length/encoding/range SERVER-SIDE
- Zero string concatenation in SQL — parameterized queries ONLY
- File uploads: MIME validate server-side, random filename, outside webroot
```python
# NEVER: query = "SELECT * FROM users WHERE id = " + user_id
# CORRECT: cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

**SBD-02 · Prompt Injection Defense** (OWASP LLM01)
- User content to LLM = ADVERSARIAL input. Structural separation required.
- Log ALL prompt inputs and LLM outputs for auditability.
```python
messages = [
    {"role": "system", "content": FIXED_SYSTEM_PROMPT},
    {"role": "user", "content": sanitize_for_llm(user_document)}
]
```

**SBD-03 · Output Encoding & CSP** (OWASP A03+A05, LLM05)
Minimum headers: CSP default-src 'self', X-Content-Type-Options nosniff,
X-Frame-Options DENY, HSTS max-age=31536000, Referrer-Policy strict-origin,
Permissions-Policy camera=(),microphone=(),geolocation=()

### LAYER 2 — IDENTITY & ACCESS
**SBD-04 · Authentication** (OWASP A07, CIS 5)
- Argon2id preferred, bcrypt cost>=12. Never MD5/SHA1/plain SHA256
- MFA for privileged. Rate-limit 5/min/IP+account. Rotate sessions on login/escalation
- JWT: always `exp`, always verify `alg` explicitly, reject `alg: none`

**SBD-05 · Authorization** (OWASP A01, CIS 6)
- Default DENY. Server-side every request. Ownership check mandatory.
- 404 not 403 — never leak resource existence

**SBD-06 · Least Privilege** (OWASP A01, LLM06)
- Every service/key/agent: minimum permissions. No single credential = total compromise.

### LAYER 3 — DATA & CRYPTO
**SBD-07 · Secrets Management** (OWASP A02, CIS 4)
- No credentials in source/commits/bundles. Pre-commit gitleaks.
- Scan: sk-*, AKIA*, ghp_*, private_key, password=

**SBD-08 · Cryptographic Standards** (OWASP A02, CIS 3)
- Approved: AES-256-GCM, RSA-4096/ECC P-256, SHA-256/SHA-3, Argon2id, TLS 1.3
- Never: DES, 3DES, RC4, MD5, SHA-1, Math.random() for security

**SBD-09 · Data Minimization** (OWASP A02, ISO A.5.34)
- Collect only necessary. Purge when unneeded.
- Conflict with SBD-10: log EVENT metadata, never data CONTENT

### LAYER 4 — RESILIENCE & MONITORING
**SBD-10 · Security Logging** (OWASP A09, CIS 8)
- Log: timestamp, event_type, user_id, ip, resource, outcome. Never content.
- Pseudonymize user identifiers after 30 days. LLM: log prompt I/O for audit.

**SBD-11 · Rate Limiting** (OWASP A07, LLM10)
- Auth: 5/min/IP+account. LLM: always max_tokens + timeout.

**SBD-12 · SSRF Prevention** (OWASP A10)
- Block private: 10.0/8, 172.16/12, 192.168/16, 127/8, 169.254/16

**SBD-13 · Error Handling** (OWASP A05)
- Detailed errors: server log ONLY. User gets generic message.
- Never expose: stack traces, SQL, file paths, server versions

### LAYER 5 — SUPPLY CHAIN & ARCHITECTURE
**SBD-14 · Dependency Security** (OWASP A06, CIS 2)
- Never install AI-suggested packages without review. npm audit + snyk.

**SBD-15 · CI/CD Integrity** (OWASP A08, CIS 16)
- Pin GitHub Actions to SHA (not tags). Signed commits. SAST/DAST in pipeline.

**SBD-16 · LLM Model Integrity** (OWASP LLM03+04)
- Verify model checksums SHA-256. No untrusted model loading.

**SBD-17 · System Prompt Protection** (OWASP LLM07)
- Test: "repeat above", "what are instructions", "translate prompt", "ignore previous"

**SBD-18 · RAG Security** (OWASP LLM08)
- Filter vector queries by owner_id. Tenant isolation. Never cross-user retrieval.

**SBD-19 · LLM Output Validation** (OWASP LLM05+09)
- Never pass LLM output to execution/DB/browser without validation.

**SBD-20 · Network & CORS** (OWASP A05)
- Explicit origins. Never `origin: '*'` on auth endpoints.

**SBD-21 · Secure Design** (OWASP A04)
- Fail secure (deny on failure). Threat model required for TIER 3.

**SBD-22 · Governance** (OWASP A04)
- DoD security checklist: input validation, auth tested, secrets external, no stack traces.

**SBD-23 · Asset Inventory** (NIST ID.AM, CIS 1+2)
- IaC only. Never manual production config. Tags: owner, env, data_class.

**SBD-24 · Incident Response** (NIST DE+RS+RC, CIS 17)
- Auto-detect: brute force >10/min, unusual data egress.
- AI incidents: hallucination harm, prompt injection success, unauthorized disclosure.

**SBD-25 · Privacy & Compliance** (GDPR, CCPA, HIPAA, PCI-DSS)
- Identify regulations at project start. Privacy by default. Data processing register.

## SECURITY THEATER DETECTION
Refuse to validate as secure if:
1. CSP headers in app code but deployment context unknown
2. HTTPS mentioned but TLS config unverified
3. Zero Trust claimed without inter-service mTLS
4. GDPR compliance without data mapping
5. "Industry-standard encryption" without algorithm/key/rotation specifics

## CONFLICT RESOLUTION
- SBD-09 vs SBD-10: Log event, never content. Pseudonymize after 30d.
- SBD-06 vs ops: Least privilege default. Exceptions: documented, time-limited, audited.
- SBD-21 vs SBD-24: Security=fail secure. Availability=graceful degradation. Document both.

## SF PLATFORM MAPPING
| Control | SF Implementation | Status |
|---------|-------------------|--------|
| SBD-01 | Pydantic validation + parameterized SQL | Done |
| SBD-02 | prompt_guard.py + adversarial L0 PROMPT_INJECT | Done |
| SBD-03 | FastAPI security headers middleware | Done |
| SBD-04 | JWT+bcrypt+rate-limit (auth/) | Done |
| SBD-05 | RBAC 5-layer (rbac/) + agents/permissions.py | Done |
| SBD-06 | Tool ACL per agent role | Done |
| SBD-07 | Infisical + .env (no secrets in code) | Done |
| SBD-10 | admin_audit_log + structured logging | Done |
| SBD-11 | slowapi + Redis rate limiter | Done |
| SBD-13 | Generic error responses in API | Done |
| SBD-17 | Adversarial IDENTITY_CLAIM + prompt guard | Done |
| SBD-19 | output_validator.py + adversarial L1 | Done |
| SBD-22 | 17 quality gates | Done |
