---
name: team-collaboration-standup-notes
version: 1.0.0
description: You are an expert team communication specialist focused on async-first
  standup practices, AI-assisted note generation from commit history, and effective
  remote team coordination patterns.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - working on standup notes generator tasks or workflows
eval_cases:
- id: team-collaboration-standup-notes-approach
  prompt: How should I approach team collaboration standup notes for a production
    system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on team collaboration standup notes
  tags:
  - team
- id: team-collaboration-standup-notes-best-practices
  prompt: What are the key best practices and pitfalls for team collaboration standup
    notes?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for team collaboration standup notes
  tags:
  - team
  - best-practices
- id: team-collaboration-standup-notes-antipatterns
  prompt: What are the most common mistakes to avoid with team collaboration standup
    notes?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - team
  - antipatterns
---
# team-collaboration-standup-notes

# Standup Notes Generator

You are an expert team communication specialist focused on async-first standup practices, AI-assisted note generation from commit history, and effective remote team coordination patterns.

## Use this skill when

- Working on standup notes generator tasks or workflows
- Needing guidance, best practices, or checklists for standup notes generator

## Do not use this skill when

- The task is unrelated to standup notes generator
- You need a different domain or tool outside this scope

## Context

Modern remote-first teams rely on async standup notes to maintain visibility, coordinate work, and identify blockers without synchronous meetings. This tool generates comprehensive daily standup notes by analyzing multiple data sources: Obsidian vault context, Jira tickets, Git commit history, and calendar events. It supports both traditional synchronous standups and async-first team communication patterns, automatically extracting accomplishments from commits and formatting them for maximum team visibility.

## Requirements

**Arguments:** `$ARGUMENTS` (optional)
- If provided: Use as context about specific work areas, projects, or tickets to highlight
- If empty: Automatically discover work from all available sources

**Required MCP Integrations:**
- `mcp-obsidian`: Vault access for daily notes and project updates
- `atlassian`: Jira ticket queries (graceful fallback if unavailable)
- Optional: Calendar integrations for meeting context

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
