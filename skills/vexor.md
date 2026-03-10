---
name: vexor
version: 1.0.0
description: Vector-powered CLI for semantic file search with a Claude/Codex skill
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/scarletkc/vexor'
  triggers:
  - when working on vexor
eval_cases:
- id: vexor-approach
  prompt: How should I approach vexor for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on vexor
  tags:
  - vexor
- id: vexor-best-practices
  prompt: What are the key best practices and pitfalls for vexor?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for vexor
  tags:
  - vexor
  - best-practices
- id: vexor-antipatterns
  prompt: What are the most common mistakes to avoid with vexor?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - vexor
  - antipatterns
---
# vexor

# Vexor

## Overview

Vector-powered CLI for semantic file search with a Claude/Codex skill

## When to Use This Skill

Use this skill when you need to work with vector-powered cli for semantic file search with a claude/codex skill.

## Instructions

This skill provides guidance and patterns for vector-powered cli for semantic file search with a claude/codex skill.

For more information, see the [source repository](https://github.com/scarletkc/vexor).
