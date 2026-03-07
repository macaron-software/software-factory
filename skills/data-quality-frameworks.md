---
name: data-quality-frameworks
version: 1.0.0
description: Implement data quality validation with Great Expectations, dbt tests,
  and data contracts. Use when building data quality pipelines, implementing validation
  rules, or establishing data contracts.
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - 'building data quality pipelines, implementing validation rules, or establishing '
  - implementing data quality checks in pipelines
  - setting up great expectations validation
  - building comprehensive dbt test suites
eval_cases:
- id: data-quality-frameworks-approach
  prompt: How should I approach data quality frameworks for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on data quality frameworks
  tags:
  - data
- id: data-quality-frameworks-best-practices
  prompt: What are the key best practices and pitfalls for data quality frameworks?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for data quality frameworks
  tags:
  - data
  - best-practices
- id: data-quality-frameworks-antipatterns
  prompt: What are the most common mistakes to avoid with data quality frameworks?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - data
  - antipatterns
---
# data-quality-frameworks

# Data Quality Frameworks

Production patterns for implementing data quality with Great Expectations, dbt tests, and data contracts to ensure reliable data pipelines.

## Use this skill when

- Implementing data quality checks in pipelines
- Setting up Great Expectations validation
- Building comprehensive dbt test suites
- Establishing data contracts between teams
- Monitoring data quality metrics
- Automating data validation in CI/CD

## Do not use this skill when

- The data sources are undefined or unavailable
- You cannot modify validation rules or schemas
- The task is unrelated to data quality or contracts

## Instructions

- Identify critical datasets and quality dimensions.
- Define expectations/tests and contract rules.
- Automate validation in CI/CD and schedule checks.
- Set alerting, ownership, and remediation steps.
- If detailed patterns are required, open `resources/implementation-playbook.md`.

## Safety

- Avoid blocking critical pipelines without a fallback plan.
- Handle sensitive data securely in validation outputs.

## Resources

- `resources/implementation-playbook.md` for detailed frameworks, templates, and examples.
