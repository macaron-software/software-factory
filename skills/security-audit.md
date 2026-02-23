---
name: security-audit
description: >
  Guides the agent through web application security auditing based on OWASP Top 10
  and common vulnerability patterns. Use this skill when checking code for security
  vulnerabilities, reviewing authentication/authorization, scanning for secrets,
  or assessing input validation and sanitization.
metadata:
  category: security
  triggers:
    - "when user asks for a security review"
    - "when checking code for vulnerabilities"
    - "when user mentions OWASP or security audit"
    - "when reviewing authentication or authorization code"
    - "when scanning for hardcoded secrets"
---

# Security Audit

This skill enables the agent to perform security audits on web applications, covering
OWASP Top 10 vulnerabilities, secret detection, auth review, and input validation.

## Use this skill when

- Reviewing code for security vulnerabilities
- Checking for OWASP Top 10 issues
- Auditing authentication and authorization logic
- Scanning for hardcoded secrets or credentials
- Reviewing input validation and sanitization
- Checking dependency CVEs

## Do not use this skill when

- Doing general code review (use code-review-excellence)
- Implementing security features (use relevant development skills)
- Testing functionality (use testing skills)

## Instructions

### OWASP Top 10 Checklist (2021)

#### A01: Broken Access Control

```typescript
// ❌ VULNERABLE: No authorization check
app.get("/api/users/:id", async (req, res) => {
  const user = await db.getUser(req.params.id);
  res.json(user); // Any authenticated user can access any user's data
});

// ✅ SECURE: Check authorization
app.get("/api/users/:id", authenticate, async (req, res) => {
  if (req.user.id !== req.params.id && req.user.role !== "admin") {
    return res.status(403).json({ error: "Forbidden" });
  }
  const user = await db.getUser(req.params.id);
  res.json(user);
});
```

Check for:

- [ ] Every endpoint has authentication
- [ ] Authorization checks prevent horizontal privilege escalation
- [ ] Admin functions verify admin role
- [ ] CORS is properly configured
- [ ] Directory listing is disabled

#### A02: Cryptographic Failures

```typescript
// ❌ VULNERABLE
const hash = md5(password); // MD5 is broken
const token = Math.random().toString(36); // Not cryptographically secure

// ✅ SECURE
import bcrypt from "bcrypt";
import crypto from "crypto";
const hash = await bcrypt.hash(password, 12);
const token = crypto.randomBytes(32).toString("hex");
```

Check for:

- [ ] Passwords hashed with bcrypt/argon2 (not MD5/SHA1)
- [ ] Sensitive data encrypted at rest
- [ ] HTTPS enforced (no mixed content)
- [ ] Cryptographically secure random number generation
- [ ] No sensitive data in URLs or logs

#### A03: Injection

```typescript
// ❌ VULNERABLE: SQL Injection
const query = `SELECT * FROM users WHERE email = '${email}'`;

// ✅ SECURE: Parameterized query
const query = "SELECT * FROM users WHERE email = $1";
const result = await db.query(query, [email]);

// ❌ VULNERABLE: Command Injection
exec(`convert ${filename} output.png`);

// ✅ SECURE: Use library, validate input
import { execFile } from "child_process";
if (!/^[a-zA-Z0-9._-]+$/.test(filename)) throw new Error("Invalid filename");
execFile("convert", [filename, "output.png"]);
```

Check for:

- [ ] All SQL uses parameterized queries or ORM
- [ ] No string concatenation in queries
- [ ] OS commands use execFile with validated args
- [ ] NoSQL injection patterns checked (MongoDB $where, $regex)
- [ ] LDAP injection checked if applicable

#### A04: Insecure Design

- [ ] Rate limiting on authentication endpoints
- [ ] Account lockout after failed attempts
- [ ] CAPTCHA for sensitive operations
- [ ] Business logic validated server-side (not just client)

#### A05: Security Misconfiguration

```typescript
// ❌ VULNERABLE: Detailed errors in production
app.use((err, req, res, next) => {
  res.status(500).json({ error: err.stack }); // Leaks internals
});

// ✅ SECURE: Generic errors in production
app.use((err, req, res, next) => {
  console.error(err); // Log internally
  res.status(500).json({ error: "Internal server error" });
});
```

Check for:

- [ ] Debug mode disabled in production
- [ ] Default credentials changed
- [ ] Error messages don't leak internals
- [ ] Security headers set (CSP, HSTS, X-Frame-Options)
- [ ] Unnecessary features/endpoints disabled

#### A06: Vulnerable Components

```bash
# Check for known vulnerabilities
npm audit
pip audit
cargo audit
```

Check for:

- [ ] Dependencies scanned for CVEs
- [ ] No unmaintained packages
- [ ] Lock files committed (package-lock.json, Pipfile.lock)

#### A07: Authentication Failures

```typescript
// ❌ VULNERABLE: Weak session management
app.use(
  session({
    secret: "mysecret", // Hardcoded, weak secret
    cookie: { secure: false }, // Not HTTPS-only
  })
);

// ✅ SECURE
app.use(
  session({
    secret: process.env.SESSION_SECRET, // From environment
    cookie: {
      secure: true, // HTTPS only
      httpOnly: true, // No JavaScript access
      sameSite: "strict", // CSRF protection
      maxAge: 3600000, // 1 hour expiry
    },
  })
);
```

Check for:

- [ ] Passwords have minimum complexity requirements
- [ ] Sessions expire after inactivity
- [ ] JWT tokens have reasonable expiration
- [ ] Password reset is secure (time-limited tokens)
- [ ] Multi-factor authentication for sensitive operations

#### A08: Software and Data Integrity

- [ ] CI/CD pipeline validates integrity of dependencies
- [ ] Subresource integrity (SRI) for CDN resources
- [ ] Code signing for releases

#### A09: Logging and Monitoring

- [ ] Authentication attempts logged
- [ ] Authorization failures logged
- [ ] Sensitive data NOT logged (passwords, tokens, PII)
- [ ] Log injection prevented (sanitize user input in logs)

#### A10: Server-Side Request Forgery (SSRF)

```typescript
// ❌ VULNERABLE: User controls URL
const response = await fetch(req.body.url); // Attacker can access internal services

// ✅ SECURE: Validate and restrict
const url = new URL(req.body.url);
const allowedHosts = ["api.example.com", "cdn.example.com"];
if (!allowedHosts.includes(url.hostname)) {
  throw new Error("URL not allowed");
}
```

### Secret Detection

```bash
# Patterns to search for
grep -rn 'password\s*=' --include='*.{ts,js,py,env}'
grep -rn 'api[_-]?key\s*=' --include='*.{ts,js,py,env}'
grep -rn 'secret\s*=' --include='*.{ts,js,py,env}'
grep -rn 'token\s*=' --include='*.{ts,js,py,env}'
grep -rn 'AWS_' --include='*.{ts,js,py,env}'
grep -rn 'PRIVATE.KEY' --include='*.{ts,js,py,pem}'

# Check .gitignore includes:
# .env, *.pem, *.key, credentials.json
```

### XSS Prevention

```typescript
// ❌ VULNERABLE: Direct HTML injection
element.innerHTML = userInput;
res.send(`<div>${userInput}</div>`);

// ✅ SECURE: Escape output
element.textContent = userInput;
import { escape } from "html-escaper";
res.send(`<div>${escape(userInput)}</div>`);
```

### CSRF Prevention

```typescript
// ✅ Implement CSRF tokens
import csrf from "csurf";
app.use(csrf({ cookie: true }));

// In forms:
// <input type="hidden" name="_csrf" value="{{csrfToken}}">

// Or use SameSite cookies + custom headers for APIs
```

## Output Format

```
## Security Audit Report: [Application/Module]
### Date: [Date]
### Scope: [What was audited]

### Executive Summary
Risk Level: [Critical / High / Medium / Low]
Total Findings: X (Y critical, Z high)

### OWASP Top 10 Assessment
| Category | Status | Findings |
|----------|--------|----------|
| A01 Broken Access Control | ❌ | 2 issues |
| A02 Cryptographic Failures | ✅ | 0 issues |
| A03 Injection | ❌ | 1 issue |
| ... | ... | ... |

### Findings
| # | Severity | OWASP | Description | Location | Remediation |
|---|----------|-------|-------------|----------|-------------|
| 1 | 🔴 Critical | A03 | SQL injection | api/users.ts:42 | Use parameterized queries |
| 2 | 🟠 High | A01 | Missing auth check | api/admin.ts:15 | Add role verification |

### Secret Scan
- ✅ No hardcoded secrets found / ❌ X secrets detected

### Dependency Audit
- Packages scanned: X
- Vulnerabilities: Y (Z critical)
```

## Anti-patterns

- **NEVER** store secrets in source code, even in test files
- **NEVER** trust client-side validation alone — always validate server-side
- **NEVER** use MD5 or SHA1 for password hashing
- **NEVER** return stack traces or internal errors to users
- **NEVER** disable CORS entirely (`Access-Control-Allow-Origin: *` with credentials)
- **NEVER** use `eval()` or `new Function()` with user input
- **NEVER** log passwords, tokens, or personally identifiable information
- **NEVER** skip rate limiting on authentication endpoints
