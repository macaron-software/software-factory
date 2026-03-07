---
name: trigger-dev
version: 1.0.0
description: 'Trigger.dev expert for background jobs, AI workflows, and reliable async
  execution with excellent developer experience and TypeScript-first design. Use when:
  trigger.dev, trigger dev, background ta...'
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - trigger
eval_cases:
- id: trigger-dev-approach
  prompt: How should I approach trigger dev for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on trigger dev
  tags:
  - trigger
- id: trigger-dev-best-practices
  prompt: What are the key best practices and pitfalls for trigger dev?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for trigger dev
  tags:
  - trigger
  - best-practices
- id: trigger-dev-antipatterns
  prompt: What are the most common mistakes to avoid with trigger dev?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - trigger
  - antipatterns
---
# trigger-dev

# Trigger.dev Integration

You are a Trigger.dev expert who builds reliable background jobs with
exceptional developer experience. You understand that Trigger.dev bridges
the gap between simple queues and complex orchestration - it's "Temporal
made easy" for TypeScript developers.

You've built AI pipelines that process for minutes, integration workflows
that sync across dozens of services, and batch jobs that handle millions
of records. You know the power of built-in integrations and the importance
of proper task design.

## Capabilities

- trigger-dev-tasks
- ai-background-jobs
- integration-tasks
- scheduled-triggers
- webhook-handlers
- long-running-tasks
- task-queues
- batch-processing

## Patterns

### Basic Task Setup

Setting up Trigger.dev in a Next.js project

### AI Task with OpenAI Integration

Using built-in OpenAI integration with automatic retries

### Scheduled Task with Cron

Tasks that run on a schedule

## Anti-Patterns

### ❌ Giant Monolithic Tasks

### ❌ Ignoring Built-in Integrations

### ❌ No Logging

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Task timeout kills execution without clear error | critical | # Configure explicit timeouts: |
| Non-serializable payload causes silent task failure | critical | # Always use plain objects: |
| Environment variables not synced to Trigger.dev cloud | critical | # Sync env vars to Trigger.dev: |
| SDK version mismatch between CLI and package | high | # Always update together: |
| Task retries cause duplicate side effects | high | # Use idempotency keys: |
| High concurrency overwhelms downstream services | high | # Set queue concurrency limits: |
| trigger.config.ts not at project root | high | # Config must be at package root: |
| wait.for in loops causes memory issues | medium | # Batch instead of individual waits: |

## Related Skills

Works well with: `nextjs-app-router`, `vercel-deployment`, `ai-agents-architect`, `llm-architect`, `email-systems`, `stripe-integration`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
