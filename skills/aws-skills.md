---
name: aws-skills
version: 1.0.0
description: AWS development with infrastructure automation and cloud architecture
  patterns
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: https://github.com/zxkane/aws-skills'
  triggers:
  - when working on aws skills
eval_cases:
- id: aws-skills-approach
  prompt: How should I approach aws skills for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on aws skills
  tags:
  - aws
- id: aws-skills-best-practices
  prompt: What are the key best practices and pitfalls for aws skills?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for aws skills
  tags:
  - aws
  - best-practices
- id: aws-skills-antipatterns
  prompt: What are the most common mistakes to avoid with aws skills?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - aws
  - antipatterns
---
# aws-skills

# Aws Skills

## Overview

AWS development with infrastructure automation and cloud architecture patterns

## When to Use This Skill

Use this skill when you need to work with aws development with infrastructure automation and cloud architecture patterns.

## Instructions

This skill provides guidance and patterns for aws development with infrastructure automation and cloud architecture patterns.

For more information, see the [source repository](https://github.com/zxkane/aws-skills).
