---
name: screen-reader-testing
version: 1.0.0
description: Test web applications with screen readers including VoiceOver, NVDA,
  and JAWS. Use when validating screen reader compatibility, debugging accessibility
  issues, or ensuring assistive technology supp...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - validating screen reader compatibility, debugging accessibility issues, or ensur
  - testing aria implementations
  - debugging assistive technology issues
eval_cases:
- id: screen-reader-testing-approach
  prompt: How should I approach screen reader testing for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on screen reader testing
  tags:
  - screen
- id: screen-reader-testing-best-practices
  prompt: What are the key best practices and pitfalls for screen reader testing?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for screen reader testing
  tags:
  - screen
  - best-practices
- id: screen-reader-testing-antipatterns
  prompt: What are the most common mistakes to avoid with screen reader testing?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - screen
  - antipatterns
---
# screen-reader-testing

# Screen Reader Testing

Practical guide to testing web applications with screen readers for comprehensive accessibility validation.

## Use this skill when

- Validating screen reader compatibility
- Testing ARIA implementations
- Debugging assistive technology issues
- Verifying form accessibility
- Testing dynamic content announcements
- Ensuring navigation accessibility

## Do not use this skill when

- The task is unrelated to screen reader testing
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
