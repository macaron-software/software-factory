---
name: llm-application-dev-prompt-optimize
version: 1.0.0
description: You are an expert prompt engineer specializing in crafting effective
  prompts for LLMs through advanced techniques including constitutional AI, chain-of-thought
  reasoning, and model-specific optimizati
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - working on prompt optimization tasks or workflows
eval_cases:
- id: llm-application-dev-prompt-optimize-approach
  prompt: How should I approach llm application dev prompt optimize for a production
    system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on llm application dev prompt optimize
  tags:
  - llm
- id: llm-application-dev-prompt-optimize-best-practices
  prompt: What are the key best practices and pitfalls for llm application dev prompt
    optimize?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for llm application dev prompt optimize
  tags:
  - llm
  - best-practices
- id: llm-application-dev-prompt-optimize-antipatterns
  prompt: What are the most common mistakes to avoid with llm application dev prompt
    optimize?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - llm
  - antipatterns
---
# llm-application-dev-prompt-optimize

# Prompt Optimization

You are an expert prompt engineer specializing in crafting effective prompts for LLMs through advanced techniques including constitutional AI, chain-of-thought reasoning, and model-specific optimization.

## Use this skill when

- Working on prompt optimization tasks or workflows
- Needing guidance, best practices, or checklists for prompt optimization

## Do not use this skill when

- The task is unrelated to prompt optimization
- You need a different domain or tool outside this scope

## Context

Transform basic instructions into production-ready prompts. Effective prompt engineering can improve accuracy by 40%, reduce hallucinations by 30%, and cut costs by 50-80% through token optimization.

## Requirements

$ARGUMENTS

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
