---
name: fal-audio
version: 1.0.0
description: Text-to-speech and speech-to-text using fal.ai audio models
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/fal-ai-community/skills/blob/main/skills/claude.ai/fal-audio/SKILL.md'
  triggers:
  - when working on fal audio
eval_cases:
- id: fal-audio-approach
  prompt: How should I approach fal audio for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on fal audio
  tags:
  - fal
- id: fal-audio-best-practices
  prompt: What are the key best practices and pitfalls for fal audio?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for fal audio
  tags:
  - fal
  - best-practices
- id: fal-audio-antipatterns
  prompt: What are the most common mistakes to avoid with fal audio?
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
# fal-audio

# Fal Audio

## Overview

Text-to-speech and speech-to-text using fal.ai audio models

## When to Use This Skill

Use this skill when you need to work with text-to-speech and speech-to-text using fal.ai audio models.

## Instructions

This skill provides guidance and patterns for text-to-speech and speech-to-text using fal.ai audio models.

For more information, see the [source repository](https://github.com/fal-ai-community/skills/blob/main/skills/claude.ai/fal-audio/SKILL.md).
