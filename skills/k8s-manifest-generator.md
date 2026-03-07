---
name: k8s-manifest-generator
version: 1.0.0
description: Create production-ready Kubernetes manifests for Deployments, Services,
  ConfigMaps, and Secrets following best practices and security standards. Use when
  generating Kubernetes YAML manifests, creat...
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - generating kubernetes yaml manifests, creat
  - create new kubernetes deployment manifests
eval_cases:
- id: k8s-manifest-generator-approach
  prompt: How should I approach k8s manifest generator for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on k8s manifest generator
  tags:
  - k8s
- id: k8s-manifest-generator-best-practices
  prompt: What are the key best practices and pitfalls for k8s manifest generator?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for k8s manifest generator
  tags:
  - k8s
  - best-practices
- id: k8s-manifest-generator-antipatterns
  prompt: What are the most common mistakes to avoid with k8s manifest generator?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - k8s
  - antipatterns
---
# k8s-manifest-generator

# Kubernetes Manifest Generator

Step-by-step guidance for creating production-ready Kubernetes manifests including Deployments, Services, ConfigMaps, Secrets, and PersistentVolumeClaims.

## Use this skill when

Use this skill when you need to:
- Create new Kubernetes Deployment manifests
- Define Service resources for network connectivity
- Generate ConfigMap and Secret resources for configuration management
- Create PersistentVolumeClaim manifests for stateful workloads
- Follow Kubernetes best practices and naming conventions
- Implement resource limits, health checks, and security contexts
- Design manifests for multi-environment deployments

## Do not use this skill when

- The task is unrelated to kubernetes manifest generator
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
