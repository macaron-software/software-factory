---
name: web-security-testing
version: 1.0.0
description: Web application security testing workflow for OWASP Top 10 vulnerabilities
  including injection, XSS, authentication flaws, and access control issues.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: personal'
  triggers:
  - when working on web security testing
eval_cases:
- id: web-security-testing-approach
  prompt: How should I approach web security testing for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on web security testing
  tags:
  - web
- id: web-security-testing-best-practices
  prompt: What are the key best practices and pitfalls for web security testing?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for web security testing
  tags:
  - web
  - best-practices
- id: web-security-testing-antipatterns
  prompt: What are the most common mistakes to avoid with web security testing?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - web
  - antipatterns
---
# web-security-testing

# Web Security Testing Workflow

## Overview

Specialized workflow for testing web applications against OWASP Top 10 vulnerabilities including injection attacks, XSS, broken authentication, and access control issues.

## When to Use This Workflow

Use this workflow when:
- Testing web application security
- Performing OWASP Top 10 assessment
- Conducting penetration tests
- Validating security controls
- Bug bounty hunting

## Workflow Phases

### Phase 1: Reconnaissance

#### Skills to Invoke
- `scanning-tools` - Security scanning
- `top-web-vulnerabilities` - OWASP knowledge

#### Actions
1. Map application surface
2. Identify technologies
3. Discover endpoints
4. Find subdomains
5. Document findings

#### Copy-Paste Prompts
```
Use @scanning-tools to perform web application reconnaissance
```

### Phase 2: Injection Testing

#### Skills to Invoke
- `sql-injection-testing` - SQL injection
- `sqlmap-database-pentesting` - SQLMap

#### Actions
1. Test SQL injection
2. Test NoSQL injection
3. Test command injection
4. Test LDAP injection
5. Document vulnerabilities

#### Copy-Paste Prompts
```
Use @sql-injection-testing to test for SQL injection
```

```
Use @sqlmap-database-pentesting to automate SQL injection testing
```

### Phase 3: XSS Testing

#### Skills to Invoke
- `xss-html-injection` - XSS testing
- `html-injection-testing` - HTML injection

#### Actions
1. Test reflected XSS
2. Test stored XSS
3. Test DOM-based XSS
4. Test XSS filters
5. Document findings

#### Copy-Paste Prompts
```
Use @xss-html-injection to test for cross-site scripting
```

### Phase 4: Authentication Testing

#### Skills to Invoke
- `broken-authentication` - Authentication testing

#### Actions
1. Test credential stuffing
2. Test brute force protection
3. Test session management
4. Test password policies
5. Test MFA implementation

#### Copy-Paste Prompts
```
Use @broken-authentication to test authentication security
```

### Phase 5: Access Control Testing

#### Skills to Invoke
- `idor-testing` - IDOR testing
- `file-path-traversal` - Path traversal

#### Actions
1. Test vertical privilege escalation
2. Test horizontal privilege escalation
3. Test IDOR vulnerabilities
4. Test directory traversal
5. Test unauthorized access

#### Copy-Paste Prompts
```
Use @idor-testing to test for insecure direct object references
```

```
Use @file-path-traversal to test for path traversal
```

### Phase 6: Security Headers

#### Skills to Invoke
- `api-security-best-practices` - Security headers

#### Actions
1. Check CSP implementation
2. Verify HSTS configuration
3. Test X-Frame-Options
4. Check X-Content-Type-Options
5. Verify referrer policy

#### Copy-Paste Prompts
```
Use @api-security-best-practices to audit security headers
```

### Phase 7: Reporting

#### Skills to Invoke
- `reporting-standards` - Security reporting

#### Actions
1. Document vulnerabilities
2. Assess risk levels
3. Provide remediation
4. Create proof of concept
5. Generate report

#### Copy-Paste Prompts
```
Use @reporting-standards to create security report
```

## OWASP Top 10 Checklist

- [ ] A01: Broken Access Control
- [ ] A02: Cryptographic Failures
- [ ] A03: Injection
- [ ] A04: Insecure Design
- [ ] A05: Security Misconfiguration
- [ ] A06: Vulnerable Components
- [ ] A07: Authentication Failures
- [ ] A08: Software/Data Integrity
- [ ] A09: Logging/Monitoring
- [ ] A10: SSRF

## Quality Gates

- [ ] All OWASP Top 10 tested
- [ ] Vulnerabilities documented
- [ ] Proof of concepts captured
- [ ] Remediation provided
- [ ] Report generated

## Related Workflow Bundles

- `security-audit` - Security auditing
- `api-security-testing` - API security
- `wordpress-security` - WordPress security
