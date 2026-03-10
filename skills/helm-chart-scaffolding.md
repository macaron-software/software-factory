---
name: helm-chart-scaffolding
version: 1.0.0
description: Design, organize, and manage Helm charts for templating and packaging
  Kubernetes applications with reusable configurations. Use when creating Helm charts,
  packaging Kubernetes applications, or impl...
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - creating helm charts, packaging kubernetes applications, or impl
  - create new helm charts from scratch
eval_cases:
- id: helm-chart-scaffolding-approach
  prompt: How should I approach helm chart scaffolding for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on helm chart scaffolding
  tags:
  - helm
- id: helm-chart-scaffolding-best-practices
  prompt: What are the key best practices and pitfalls for helm chart scaffolding?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for helm chart scaffolding
  tags:
  - helm
  - best-practices
- id: helm-chart-scaffolding-antipatterns
  prompt: What are the most common mistakes to avoid with helm chart scaffolding?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - helm
  - antipatterns
---
# helm-chart-scaffolding

# Helm Chart Scaffolding

Comprehensive guidance for creating, organizing, and managing Helm charts for packaging and deploying Kubernetes applications.

## Use this skill when

Use this skill when you need to:
- Create new Helm charts from scratch
- Package Kubernetes applications for distribution
- Manage multi-environment deployments with Helm
- Implement templating for reusable Kubernetes manifests
- Set up Helm chart repositories
- Follow Helm best practices and conventions

## Do not use this skill when

- The task is unrelated to helm chart scaffolding
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
