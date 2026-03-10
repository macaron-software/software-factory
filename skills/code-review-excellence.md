---
name: code-review-excellence
version: 1.0.0
description: Master effective code review practices to provide constructive feedback,
  catch bugs early, and foster knowledge sharing while maintaining team morale. Use
  when reviewing pull requests, establishing...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - reviewing pull requests, establishing
  - reviewing pull requests and code changes
  - establishing code review standards
  - mentoring developers through review feedback
eval_cases:
- id: code-review-excellence-approach
  prompt: How should I approach code review excellence for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on code review excellence
  tags:
  - code
- id: code-review-excellence-best-practices
  prompt: What are the key best practices and pitfalls for code review excellence?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for code review excellence
  tags:
  - code
  - best-practices
- id: code-review-excellence-antipatterns
  prompt: What are the most common mistakes to avoid with code review excellence?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - code
  - antipatterns
---
# code-review-excellence

# Code Review Excellence

Transform code reviews from gatekeeping to knowledge sharing through constructive feedback, systematic analysis, and collaborative improvement.

## Use this skill when

- Reviewing pull requests and code changes
- Establishing code review standards
- Mentoring developers through review feedback
- Auditing for correctness, security, or performance

## Do not use this skill when

- There are no code changes to review
- The task is a design-only discussion without code
- You need to implement fixes instead of reviewing

## Instructions

- Read context, requirements, and test signals first.
- Review for correctness, security, performance, and maintainability.
- Provide actionable feedback with severity and rationale.
- Ask clarifying questions when intent is unclear.
- If detailed checklists are required, open `resources/implementation-playbook.md`.

## Output Format

- High-level summary of findings
- Issues grouped by severity (blocking, important, minor)
- Suggestions and questions
- Test and coverage notes

## Resources

- `resources/implementation-playbook.md` for detailed review patterns and templates.
