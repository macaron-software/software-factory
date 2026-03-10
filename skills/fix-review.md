---
name: fix-review
version: 1.0.0
description: Verify fix commits address audit findings without new bugs
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/trailofbits/skills/tree/main/plugins/fix-review'
  triggers:
  - reviewing commits that address security audit findings
eval_cases:
- id: fix-review-approach
  prompt: How should I approach fix review for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fix review
  tags:
  - fix
- id: fix-review-best-practices
  prompt: What are the key best practices and pitfalls for fix review?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fix review
  tags:
  - fix
  - best-practices
- id: fix-review-antipatterns
  prompt: What are the most common mistakes to avoid with fix review?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - fix
  - antipatterns
---
# fix-review

# Fix Review

## Overview

Verify that fix commits properly address audit findings without introducing new bugs or security vulnerabilities.

## When to Use This Skill

Use this skill when you need to verify fix commits address audit findings without new bugs.

Use this skill when:
- Reviewing commits that address security audit findings
- Verifying that fixes don't introduce new vulnerabilities
- Ensuring code changes properly resolve identified issues
- Validating that remediation efforts are complete and correct

## Instructions

This skill helps verify that fix commits properly address audit findings:

1. **Review Fix Commits**: Analyze commits that claim to fix audit findings
2. **Verify Resolution**: Ensure the original issue is properly addressed
3. **Check for Regressions**: Verify no new bugs or vulnerabilities are introduced
4. **Validate Completeness**: Ensure all aspects of the finding are resolved

## Review Process

When reviewing fix commits:

1. Compare the fix against the original audit finding
2. Verify the fix addresses the root cause, not just symptoms
3. Check for potential side effects or new issues
4. Validate that tests cover the fixed scenario
5. Ensure no similar vulnerabilities exist elsewhere

## Best Practices

- Review fixes in context of the full codebase
- Verify test coverage for the fixed issue
- Check for similar patterns that might need fixing
- Ensure fixes follow security best practices
- Document the resolution approach

## Resources

For more information, see the [source repository](https://github.com/trailofbits/skills/tree/main/plugins/fix-review).
