---
name: attack-tree-construction
version: 1.0.0
description: Build comprehensive attack trees to visualize threat paths. Use when
  mapping attack scenarios, identifying defense gaps, or communicating security risks
  to stakeholders.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - mapping attack scenarios, identifying defense gaps, or communicating security
    ri
eval_cases:
- id: attack-tree-construction-approach
  prompt: How should I approach attack tree construction for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on attack tree construction
  tags:
  - attack
- id: attack-tree-construction-best-practices
  prompt: What are the key best practices and pitfalls for attack tree construction?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for attack tree construction
  tags:
  - attack
  - best-practices
- id: attack-tree-construction-antipatterns
  prompt: What are the most common mistakes to avoid with attack tree construction?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - attack
  - antipatterns
---
# attack-tree-construction

# Attack Tree Construction

Systematic attack path visualization and analysis.

## Use this skill when

- Visualizing complex attack scenarios
- Identifying defense gaps and priorities
- Communicating risks to stakeholders
- Planning defensive investments or test scopes

## Do not use this skill when

- You lack authorization or a defined scope to model the system
- The task is a general risk review without attack-path modeling
- The request is unrelated to security assessment or design

## Instructions

- Confirm scope, assets, and the attacker goal for the root node.
- Decompose into sub-goals with AND/OR structure.
- Annotate leaves with cost, skill, time, and detectability.
- Map mitigations per branch and prioritize high-impact paths.
- If detailed templates are required, open `resources/implementation-playbook.md`.

## Safety

- Share attack trees only with authorized stakeholders.
- Avoid including sensitive exploit details unless required.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, templates, and examples.
