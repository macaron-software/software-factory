---
name: web-design-guidelines
version: 1.0.0
description: Review UI code for Web Interface Guidelines compliance. Use when asked
  to \"review my UI\", \"check accessibility\", \"audit design\", \"review UX\", or
  \"check my site aga...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - asked to \"review my ui\", \"check accessibility\", \"audit design\", \"review
    u
eval_cases:
- id: web-design-guidelines-approach
  prompt: How should I approach web design guidelines for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on web design guidelines
  tags:
  - web
- id: web-design-guidelines-best-practices
  prompt: What are the key best practices and pitfalls for web design guidelines?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for web design guidelines
  tags:
  - web
  - best-practices
- id: web-design-guidelines-antipatterns
  prompt: What are the most common mistakes to avoid with web design guidelines?
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
# web-design-guidelines

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Fetch the latest guidelines from the source URL below
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use WebFetch to retrieve the latest rules. The fetched content contains all the rules and output format instructions.

## Usage

When a user provides a file or pattern argument:
1. Fetch guidelines from the source URL above
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
