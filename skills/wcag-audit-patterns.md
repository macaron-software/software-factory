---
name: wcag-audit-patterns
version: 1.0.0
description: Conduct WCAG 2.2 accessibility audits with automated testing, manual
  verification, and remediation guidance. Use when auditing websites for accessibility,
  fixing WCAG violations, or implementing ac...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - auditing websites for accessibility, fixing wcag violations, or implementing ac
  - implementing accessible components
eval_cases:
- id: wcag-audit-patterns-approach
  prompt: How should I approach wcag audit patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on wcag audit patterns
  tags:
  - wcag
- id: wcag-audit-patterns-best-practices
  prompt: What are the key best practices and pitfalls for wcag audit patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for wcag audit patterns
  tags:
  - wcag
  - best-practices
- id: wcag-audit-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with wcag audit patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - wcag
  - antipatterns
---
# wcag-audit-patterns

# WCAG Audit Patterns

Comprehensive guide to auditing web content against WCAG 2.2 guidelines with actionable remediation strategies.

## Use this skill when

- Conducting accessibility audits
- Fixing WCAG violations
- Implementing accessible components
- Preparing for accessibility lawsuits
- Meeting ADA/Section 508 requirements
- Achieving VPAT compliance

## Do not use this skill when

- You need legal advice or formal certification
- You only want a quick automated scan without manual verification
- You cannot access the UI or source for remediation work

## Instructions

1. Run automated scans (axe, Lighthouse, WAVE) to collect initial findings.
2. Perform manual checks (keyboard navigation, focus order, screen reader flows).
3. Map each issue to a WCAG criterion, severity, and remediation guidance.
4. Re-test after fixes and document residual risk and compliance status.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Safety

- Avoid claiming legal compliance without expert review.
- Keep evidence of test steps and results for audit trails.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.
