<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.2.x   | Yes       |
| 2.1.x   | Yes       |
| < 2.1   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Send an email to **security@macaron-software.com**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Measures

### Authentication & Authorization

- JWT-based authentication with token refresh
- Role-Based Access Control (RBAC): admin, project_manager, developer, viewer
- OAuth 2.0 integration (GitHub, Azure AD)
- Session management with secure cookie handling

### Input Validation

- Prompt injection guard on all LLM inputs
- Input sanitization on all API endpoints
- SQL parameterized queries (no raw SQL interpolation)
- File path traversal protection

### Data Protection

- Secret scrubbing in agent outputs (API keys, passwords, tokens)
- No secrets stored in source code or logs
- Environment-based configuration for sensitive values
- SQLite WAL mode for data integrity

### Network Security

- Content Security Policy (CSP) headers
- CORS configuration for API endpoints
- Rate limiting per user/IP
- HTTPS enforced in production (via Nginx)

### Dependency Management

- Regular dependency audits via `pip-audit`
- SAST scanning with bandit and semgrep
- Automated security missions per project (weekly scans)

## Disclosure Policy

We follow coordinated disclosure. After a fix is released, we will:
1. Credit the reporter (unless anonymity is requested)
2. Publish a security advisory on GitHub
3. Update the changelog with security fixes
