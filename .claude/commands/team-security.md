Launch a security hacking workflow with the offensive security team.

Workflow: `security-hacking` (8 phases: Recon -> Enum -> Vuln Analysis -> Exploit Dev -> Post-Exploit -> Lateral -> Report -> Remediation)

## Instructions

1. Ask the user for: **project ID** and **target scope** (URLs, APIs, or codebase area).
2. Call the SF API:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "security-hacking", "brief": "<SCOPE>"}'
```

3. Monitor and report findings. Flag CRITICAL vulns immediately.

## Team Composition
- **pentester-lead** (recon + coordination)
- **exploit-dev** (vulnerability exploitation)
- **security-researcher** (analysis + CVE correlation)
- **securite** (OWASP Top 10 validation)
- **devsecops** (remediation + CI/CD hardening)
- **security-architect** (architecture review)
