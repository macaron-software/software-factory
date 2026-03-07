---
name: airflow-dag-patterns
version: 1.0.0
description: Build production Apache Airflow DAGs with best practices for operators,
  sensors, testing, and deployment. Use when creating data pipelines, orchestrating
  workflows, or scheduling batch jobs.
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - creating data pipelines, orchestrating workflows, or scheduling batch jobs
  - creating data pipeline orchestration with airflow
  - designing dag structures and dependencies
  - implementing custom operators and sensors
eval_cases:
- id: airflow-dag-patterns-approach
  prompt: How should I approach airflow dag patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on airflow dag patterns
  tags:
  - airflow
- id: airflow-dag-patterns-best-practices
  prompt: What are the key best practices and pitfalls for airflow dag patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for airflow dag patterns
  tags:
  - airflow
  - best-practices
- id: airflow-dag-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with airflow dag patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - airflow
  - antipatterns
---
# airflow-dag-patterns

# Apache Airflow DAG Patterns

Production-ready patterns for Apache Airflow including DAG design, operators, sensors, testing, and deployment strategies.

## Use this skill when

- Creating data pipeline orchestration with Airflow
- Designing DAG structures and dependencies
- Implementing custom operators and sensors
- Testing Airflow DAGs locally
- Setting up Airflow in production
- Debugging failed DAG runs

## Do not use this skill when

- You only need a simple cron job or shell script
- Airflow is not part of the tooling stack
- The task is unrelated to workflow orchestration

## Instructions

1. Identify data sources, schedules, and dependencies.
2. Design idempotent tasks with clear ownership and retries.
3. Implement DAGs with observability and alerting hooks.
4. Validate in staging and document operational runbooks.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Safety

- Avoid changing production DAG schedules without approval.
- Test backfills and retries carefully to prevent data duplication.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.
