---
description: Security-sensitive code — auth, crypto, secrets, SQL
globs: platform/auth/**/*.py, platform/tools/infisical_tools.py, platform/db/**/*.py
---

- Auth: JWT + bcrypt. Access tokens 15min, refresh 7d. Rate limit 5/60s/IP.
- RBAC enforced: admin, cto, pm, lead_dev, developer, qa, devops, security, viewer, auditor.
- SQL: parameterized queries only. Zero f-strings, zero string concatenation in queries.
- Secrets: Infisical vault. `.env` is bootstrap only (INFISICAL_TOKEN). Never commit secrets.
- Headers: HSTS, X-Frame DENY, CSP, X-XSS, Referrer strict.
- XSS: Jinja2 autoescaping on. CSP connect-src 'self'.
- Prompt injection: L0+L1 adversarial guards on all user input to LLM.
- SBD controls: 25 SecureByDesign checks enforced (SBD-01 through SBD-25).
