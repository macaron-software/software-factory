# Security

## Authentication
- `AuthMiddleware`: Bearer token (`MACARON_API_KEY`)
- GET endpoints: public
- Mutations (POST/PATCH/DELETE): require valid token
- Nginx: basic auth layer (Azure prod)

## HTTP Security Headers
- HSTS (Strict-Transport-Security)
- X-Frame-Options: DENY
- Content-Security-Policy
- X-XSS-Protection
- Referrer-Policy: strict-origin-when-cross-origin

## Code Security
- **XSS**: Jinja2 autoescaping + CSP `connect-src 'self'`
- **SQL Injection**: Parameterized queries (`?` placeholders, zero f-strings)
- **Prompt Injection**: L0 + L1 adversarial guards
- **Secrets**: Externalized `~/.config/factory/*.key`, chmod 600
- **Docker**: Non-root `macaron` user, minimal image

## Adversarial Validation
Multi-vendor, multi-stage code review:
- **L0**: Deterministic checks (test.skip, @ts-ignore, empty catch) → VETO
- **L1**: LLM semantic (slop, hallucination, logic errors) → VETO
- **L2**: Architecture (RBAC, validation, API design) → VETO + ESCALATION
- **Rule**: "Code writers cannot declare their own success"
- **Retry**: 5 attempts max → FAILED

## Rate Limiting
- PostgreSQL-backed per-IP + per-token
- Survives container restart
- Configurable: `LLM_RATE_LIMIT_RPM=50`

## 🇫🇷 [Sécurité (FR)](Security‐FR) · 🇪🇸 [ES](Security‐ES)
