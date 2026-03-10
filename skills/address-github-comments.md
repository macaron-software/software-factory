---
name: address-github-comments
version: 1.0.0
description: Use when you need to address review or issue comments on an open GitHub
  Pull Request using the gh CLI.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - you need to address review or issue comments on an open github pull request usin
  - list the comments and review threads
eval_cases:
- id: address-github-comments-approach
  prompt: How should I approach address github comments for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on address github comments
  tags:
  - address
- id: address-github-comments-best-practices
  prompt: What are the key best practices and pitfalls for address github comments?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for address github comments
  tags:
  - address
  - best-practices
- id: address-github-comments-antipatterns
  prompt: What are the most common mistakes to avoid with address github comments?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - address
  - antipatterns
---
# address-github-comments

# Address GitHub Comments

## Overview

Efficiently address PR review comments or issue feedback using the GitHub CLI (`gh`). This skill ensures all feedback is addressed systematically.

## Prerequisites

Ensure `gh` is authenticated.

```bash
gh auth status
```

If not logged in, run `gh auth login`.

## Workflow

### 1. Inspect Comments

Fetch the comments for the current branch's PR.

```bash
gh pr view --comments
```

Or use a custom script if available to list threads.

### 2. Categorize and Plan

- List the comments and review threads.
- Propose a fix for each.
- **Wait for user confirmation** on which comments to address first if there are many.

### 3. Apply Fixes

Apply the code changes for the selected comments.

### 4. Respond to Comments

Once fixed, respond to the threads as resolved.

```bash
gh pr comment <PR_NUMBER> --body "Addressed in latest commit."
```

## Common Mistakes

- **Applying fixes without understanding context**: Always read the surrounding code of a comment.
- **Not verifying auth**: Check `gh auth status` before starting.

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
