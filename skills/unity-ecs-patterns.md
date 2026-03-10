---
name: unity-ecs-patterns
version: 1.0.0
description: Master Unity ECS (Entity Component System) with DOTS, Jobs, and Burst
  for high-performance game development. Use when building data-oriented games, optimizing
  performance, or working with large ent...
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building data-oriented games, optimizing performance, or working with large ent
  - building high-performance unity games
  - implementing data-oriented game systems
eval_cases:
- id: unity-ecs-patterns-approach
  prompt: How should I approach unity ecs patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on unity ecs patterns
  tags:
  - unity
- id: unity-ecs-patterns-best-practices
  prompt: What are the key best practices and pitfalls for unity ecs patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for unity ecs patterns
  tags:
  - unity
  - best-practices
- id: unity-ecs-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with unity ecs patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - unity
  - antipatterns
---
# unity-ecs-patterns

# Unity ECS Patterns

Production patterns for Unity's Data-Oriented Technology Stack (DOTS) including Entity Component System, Job System, and Burst Compiler.

## Use this skill when

- Building high-performance Unity games
- Managing thousands of entities efficiently
- Implementing data-oriented game systems
- Optimizing CPU-bound game logic
- Converting OOP game code to ECS
- Using Jobs and Burst for parallelization

## Do not use this skill when

- The task is unrelated to unity ecs patterns
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
