---
name: wiki-changelog
version: 1.0.0
description: Analyzes git commit history and generates structured changelogs categorized
  by change type. Use when the user asks about recent changes, wants a changelog,
  or needs to understand what changed in th...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - the user asks about recent changes, wants a changelog, or needs to understand
    wh
eval_cases:
- id: wiki-changelog-approach
  prompt: How should I approach wiki changelog for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on wiki changelog
  tags:
  - wiki
- id: wiki-changelog-best-practices
  prompt: What are the key best practices and pitfalls for wiki changelog?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for wiki changelog
  tags:
  - wiki
  - best-practices
- id: wiki-changelog-antipatterns
  prompt: What are the most common mistakes to avoid with wiki changelog?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - wiki
  - antipatterns
---
# wiki-changelog

# Wiki Changelog

Generate structured changelogs from git history.

## When to Activate

- User asks "what changed recently", "generate a changelog", "summarize commits"
- User wants to understand recent development activity

## Procedure

1. Examine git log (commits, dates, authors, messages)
2. Group by time period: daily (last 7 days), weekly (older)
3. Classify each commit: Features (🆕), Fixes (🐛), Refactoring (🔄), Docs (📝), Config (🔧), Dependencies (📦), Breaking (⚠️)
4. Generate concise user-facing descriptions using project terminology

## Constraints

- Focus on user-facing changes
- Merge related commits into coherent descriptions
- Use project terminology from README
- Highlight breaking changes prominently with migration notes

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
