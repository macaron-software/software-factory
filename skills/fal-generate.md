---
name: fal-generate
version: 1.0.0
description: Generate images and videos using fal.ai AI models
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/fal-ai-community/skills/blob/main/skills/claude.ai/fal-generate/SKILL.md'
  triggers:
  - when working on fal generate
eval_cases:
- id: fal-generate-approach
  prompt: How should I approach fal generate for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fal generate
  tags:
  - fal
- id: fal-generate-best-practices
  prompt: What are the key best practices and pitfalls for fal generate?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fal generate
  tags:
  - fal
  - best-practices
- id: fal-generate-antipatterns
  prompt: What are the most common mistakes to avoid with fal generate?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - fal
  - antipatterns
---
# fal-generate

# Fal Generate

## Overview

Generate images and videos using fal.ai AI models

## When to Use This Skill

Use this skill when you need to work with generate images and videos using fal.ai ai models.

## Instructions

This skill provides guidance and patterns for generate images and videos using fal.ai ai models.

For more information, see the [source repository](https://github.com/fal-ai-community/skills/blob/main/skills/claude.ai/fal-generate/SKILL.md).
