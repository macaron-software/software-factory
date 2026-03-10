---
name: ffuf-claude-skill
version: 1.0.0
description: Web fuzzing with ffuf
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/jthack/ffuf_claude_skill'
  triggers:
  - when working on ffuf claude skill
eval_cases:
- id: ffuf-claude-skill-approach
  prompt: How should I approach ffuf claude skill for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on ffuf claude skill
  tags:
  - ffuf
- id: ffuf-claude-skill-best-practices
  prompt: What are the key best practices and pitfalls for ffuf claude skill?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for ffuf claude skill
  tags:
  - ffuf
  - best-practices
- id: ffuf-claude-skill-antipatterns
  prompt: What are the most common mistakes to avoid with ffuf claude skill?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - ffuf
  - antipatterns
---
# ffuf-claude-skill

# Ffuf Claude Skill

## Overview

Web fuzzing with ffuf

## When to Use This Skill

Use this skill when you need to work with web fuzzing with ffuf.

## Instructions

This skill provides guidance and patterns for web fuzzing with ffuf.

For more information, see the [source repository](https://github.com/jthack/ffuf_claude_skill).
