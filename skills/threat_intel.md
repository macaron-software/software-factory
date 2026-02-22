# Threat Intelligence — CVE Research & Exploit Chain Analysis

## Methodology

### 1. Stack Identification
- Read `package.json`, `Cargo.toml`, `requirements.txt`, `go.mod`
- Identify frameworks: FastAPI, Express, Actix, Django, Spring
- Map runtime: Node.js version, Python version, Rust edition
- Identify infrastructure: Docker base images, cloud services

### 2. CVE Research Sources
| Source | URL | Focus |
|--------|-----|-------|
| NVD | nvd.nist.gov | Official CVE database |
| GitHub Advisories | github.com/advisories | Package-specific vulns |
| MITRE CVE | cve.mitre.org | CVE identifiers |
| ExploitDB | exploit-db.com | Public exploits |
| Vendor bulletins | varies | Framework-specific |
| CISA KEV | cisa.gov/known-exploited-vulnerabilities | Actively exploited |

### 3. CVSS v3.1 Scoring

```
CVSS = Base × Temporal × Environmental

Base: Attack Vector / Complexity / Privileges / User Interaction
      Scope / Confidentiality / Integrity / Availability

Temporal: Exploit Code Maturity / Remediation Level / Report Confidence

Environmental: Modified Base + Security Requirements
```

| Score | Severity | Action |
|-------|----------|--------|
| 9.0-10.0 | CRITICAL | Fix immediately, block release |
| 7.0-8.9 | HIGH | Fix before release |
| 4.0-6.9 | MEDIUM | Fix within 30 days |
| 0.1-3.9 | LOW | Accept or fix opportunistically |

### 4. Exploit Chain Analysis

```
Minor vuln A (CVSS 3.2) + Minor vuln B (CVSS 4.1)
  → Chain: SSRF to read internal config → config contains DB creds
  → Combined CVSS: 9.1 (CRITICAL)
```

Always look for:
- Information disclosure → privilege escalation
- SSRF → internal service access → data exfiltration
- Auth bypass → admin access → RCE
- Dependency vuln → supply chain compromise

### 5. Supply Chain Risks
- Typosquatting: similar package names (e.g., `lodash` vs `l0dash`)
- Compromised maintainers: account takeover on npm/PyPI
- Dependency confusion: private vs public package names
- Transitive vulnerabilities: deps of deps

## Report Template

```markdown
## Threat Intel Report — [Project Name]

### Stack Profile
- Runtime: [versions]
- Dependencies: [count] packages, [critical count] with known vulns
- Infrastructure: [Docker/K8s/Cloud]

### Active Threats
| CVE | Package | CVSS | Exploited? | Our Exposure | Priority |
|-----|---------|------|------------|--------------|----------|

### Exploit Chains Identified
1. [Chain description with combined CVSS]

### Supply Chain Risks
- [Risk 1]

### Recommendations (priority order)
1. [Most urgent]
```

## Rules
- NEVER invent CVE numbers — verify against NVD
- Always check if vulnerability applies to OUR version
- Distinguish between theoretical and practically exploitable
- Flag CISA KEV entries — these are actively exploited in the wild
- Update research before each audit — threats change daily
