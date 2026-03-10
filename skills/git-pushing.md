---
name: git-pushing
version: 1.0.0
description: Stage, commit, and push git changes with conventional commit messages.
  Use when user wants to commit and push changes, mentions pushing to remote, or asks
  to save and push their work. Also activate...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - user wants to commit and push changes, mentions pushing to remote, or asks to
    sa
eval_cases:
- id: git-pushing-approach
  prompt: How should I approach git pushing for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on git pushing
  tags:
  - git
- id: git-pushing-best-practices
  prompt: What are the key best practices and pitfalls for git pushing?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for git pushing
  tags:
  - git
  - best-practices
- id: git-pushing-antipatterns
  prompt: What are the most common mistakes to avoid with git pushing?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - git
  - antipatterns
---
# git-pushing

# Git Push Workflow

Stage all changes, create a conventional commit, and push to the remote branch.

## When to Use

Automatically activate when the user:

- Explicitly asks to push changes ("push this", "commit and push")
- Mentions saving work to remote ("save to github", "push to remote")
- Completes a feature and wants to share it
- Says phrases like "let's push this up" or "commit these changes"

## Workflow

**ALWAYS use the script** - do NOT use manual git commands:

```bash
bash skills/git-pushing/scripts/smart_commit.sh
```

With custom message:

```bash
bash skills/git-pushing/scripts/smart_commit.sh "feat: add feature"
```

Script handles: staging, conventional commit message, Claude footer, push with -u flag.
