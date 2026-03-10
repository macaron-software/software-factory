---
name: bash-defensive-patterns
version: 1.0.0
description: Master defensive Bash programming techniques for production-grade scripts.
  Use when writing robust shell scripts, CI/CD pipelines, or system utilities requiring
  fault tolerance and safety.
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - writing robust shell scripts, ci/cd pipelines, or system utilities requiring fau
  - writing production automation scripts
  - building ci/cd pipeline scripts
  - creating system administration utilities
eval_cases:
- id: bash-defensive-patterns-approach
  prompt: How should I approach bash defensive patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on bash defensive patterns
  tags:
  - bash
- id: bash-defensive-patterns-best-practices
  prompt: What are the key best practices and pitfalls for bash defensive patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for bash defensive patterns
  tags:
  - bash
  - best-practices
- id: bash-defensive-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with bash defensive patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - bash
  - antipatterns
---
# bash-defensive-patterns

# Bash Defensive Patterns

Comprehensive guidance for writing production-ready Bash scripts using defensive programming techniques, error handling, and safety best practices to prevent common pitfalls and ensure reliability.

## Use this skill when

- Writing production automation scripts
- Building CI/CD pipeline scripts
- Creating system administration utilities
- Developing error-resilient deployment automation
- Writing scripts that must handle edge cases safely
- Building maintainable shell script libraries
- Implementing comprehensive logging and monitoring
- Creating scripts that must work across different platforms

## Do not use this skill when

- You need a single ad-hoc shell command, not a script
- The target environment requires strict POSIX sh only
- The task is unrelated to shell scripting or automation

## Instructions

1. Confirm the target shell, OS, and execution environment.
2. Enable strict mode and safe defaults from the start.
3. Validate inputs, quote variables, and handle files safely.
4. Add logging, error traps, and basic tests.

## Safety

- Avoid destructive commands without confirmation or dry-run flags.
- Do not run scripts as root unless strictly required.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.
