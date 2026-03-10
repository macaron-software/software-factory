---
name: python-packaging
version: 1.0.0
description: Create distributable Python packages with proper project structure, setup.py/pyproject.toml,
  and publishing to PyPI. Use when packaging Python libraries, creating CLI tools,
  or distributing Python ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - packaging python libraries, creating cli tools, or distributing python
  - creating python libraries for distribution
  - building command-line tools with entry points
eval_cases:
- id: python-packaging-approach
  prompt: How should I approach python packaging for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on python packaging
  tags:
  - python
- id: python-packaging-best-practices
  prompt: What are the key best practices and pitfalls for python packaging?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for python packaging
  tags:
  - python
  - best-practices
- id: python-packaging-antipatterns
  prompt: What are the most common mistakes to avoid with python packaging?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - python
  - antipatterns
---
# python-packaging

# Python Packaging

Comprehensive guide to creating, structuring, and distributing Python packages using modern packaging tools, pyproject.toml, and publishing to PyPI.

## Use this skill when

- Creating Python libraries for distribution
- Building command-line tools with entry points
- Publishing packages to PyPI or private repositories
- Setting up Python project structure
- Creating installable packages with dependencies
- Building wheels and source distributions
- Versioning and releasing Python packages
- Creating namespace packages
- Implementing package metadata and classifiers

## Do not use this skill when

- The task is unrelated to python packaging
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
