---
name: ui-skills
version: 1.0.0
description: Opinionated, evolving constraints to guide agents when building interfaces
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/ibelick/ui-skills'
  triggers:
  - when working on ui skills
eval_cases:
- id: ui-skills-approach
  prompt: How should I approach ui skills for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on ui skills
  tags:
  - ui
- id: ui-skills-best-practices
  prompt: What are the key best practices and pitfalls for ui skills?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for ui skills
  tags:
  - ui
  - best-practices
- id: ui-skills-antipatterns
  prompt: What are the most common mistakes to avoid with ui skills?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - ui
  - antipatterns
---
# ui-skills

# Ui Skills

## Overview

Opinionated, evolving constraints to guide agents when building interfaces

## When to Use This Skill

Use this skill when you need to work with opinionated, evolving constraints to guide agents when building interfaces.

## Instructions

This skill provides guidance and patterns for opinionated, evolving constraints to guide agents when building interfaces.

For more information, see the [source repository](https://github.com/ibelick/ui-skills).
