---
name: claude-ally-health
version: 1.0.0
description: A health assistant skill for medical information analysis, symptom tracking,
  and wellness guidance.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/huifer/Claude-Ally-Health'
  triggers:
  - when working on claude ally health
eval_cases:
- id: claude-ally-health-approach
  prompt: How should I approach claude ally health for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on claude ally health
  tags:
  - claude
- id: claude-ally-health-best-practices
  prompt: What are the key best practices and pitfalls for claude ally health?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for claude ally health
  tags:
  - claude
  - best-practices
- id: claude-ally-health-antipatterns
  prompt: What are the most common mistakes to avoid with claude ally health?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - claude
  - antipatterns
---
# claude-ally-health

# Claude Ally Health

## Overview

A health assistant skill for medical information analysis, symptom tracking, and wellness guidance.

## When to Use This Skill

Use this skill when you need to work with a health assistant skill for medical information analysis, symptom tracking, and wellness guidance..

## Instructions

This skill provides guidance and patterns for a health assistant skill for medical information analysis, symptom tracking, and wellness guidance..

For more information, see the [source repository](https://github.com/huifer/Claude-Ally-Health).
