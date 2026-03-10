---
name: internal-comms-community
version: 1.0.0
description: A set of resources to help me write all kinds of internal communications,
  using the formats that my company likes to use. Claude should use this skill whenever
  asked to write some sort of internal ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on internal comms community
eval_cases:
- id: internal-comms-community-approach
  prompt: How should I approach internal comms community for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on internal comms community
  tags:
  - internal
- id: internal-comms-community-best-practices
  prompt: What are the key best practices and pitfalls for internal comms community?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for internal comms community
  tags:
  - internal
  - best-practices
- id: internal-comms-community-antipatterns
  prompt: What are the most common mistakes to avoid with internal comms community?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - internal
  - antipatterns
---
# internal-comms-community

## When to use this skill
To write internal communications, use this skill for:
- 3P updates (Progress, Plans, Problems)
- Company newsletters
- FAQ responses
- Status reports
- Leadership updates
- Project updates
- Incident reports

## How to use this skill

To write any internal communication:

1. **Identify the communication type** from the request
2. **Load the appropriate guideline file** from the `examples/` directory:
    - `examples/3p-updates.md` - For Progress/Plans/Problems team updates
    - `examples/company-newsletter.md` - For company-wide newsletters
    - `examples/faq-answers.md` - For answering frequently asked questions
    - `examples/general-comms.md` - For anything else that doesn't explicitly match one of the above
3. **Follow the specific instructions** in that file for formatting, tone, and content gathering

If the communication type doesn't match any existing guideline, ask for clarification or more context about the desired format.

## Keywords
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms
