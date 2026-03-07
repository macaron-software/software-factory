---
name: azure-functions
version: 1.0.0
description: Expert patterns for Azure Functions development including isolated worker
  model, Durable Functions orchestration, cold start optimization, and production
  patterns. Covers .NET, Python, and Node.js ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - when working on azure functions
eval_cases:
- id: azure-functions-approach
  prompt: How should I approach azure functions for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on azure functions
  tags:
  - azure
- id: azure-functions-best-practices
  prompt: What are the key best practices and pitfalls for azure functions?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for azure functions
  tags:
  - azure
  - best-practices
- id: azure-functions-antipatterns
  prompt: What are the most common mistakes to avoid with azure functions?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - azure
  - antipatterns
---
# azure-functions

# Azure Functions

## Patterns

### Isolated Worker Model (.NET)

Modern .NET execution model with process isolation

### Node.js v4 Programming Model

Modern code-centric approach for TypeScript/JavaScript

### Python v2 Programming Model

Decorator-based approach for Python functions

## Anti-Patterns

### ❌ Blocking Async Calls

### ❌ New HttpClient Per Request

### ❌ In-Process Model for New Projects

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | high | ## Use async pattern with Durable Functions |
| Issue | high | ## Use IHttpClientFactory (Recommended) |
| Issue | high | ## Always use async/await |
| Issue | medium | ## Configure maximum timeout (Consumption) |
| Issue | high | ## Use isolated worker for new projects |
| Issue | medium | ## Configure Application Insights properly |
| Issue | medium | ## Check extension bundle (most common) |
| Issue | medium | ## Add warmup trigger to initialize your code |

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
