---
name: error-debugging-error-trace
version: 1.0.0
description: You are an error tracking and observability expert specializing in implementing
  comprehensive error monitoring solutions. Set up error tracking systems, configure
  alerts, implement structured loggi...
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - implementing or improving error monitoring
  - setting up structured logging and tracing
eval_cases:
- id: error-debugging-error-trace-approach
  prompt: How should I approach error debugging error trace for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on error debugging error trace
  tags:
  - error
- id: error-debugging-error-trace-best-practices
  prompt: What are the key best practices and pitfalls for error debugging error trace?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for error debugging error trace
  tags:
  - error
  - best-practices
- id: error-debugging-error-trace-antipatterns
  prompt: What are the most common mistakes to avoid with error debugging error trace?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - error
  - antipatterns
---
# error-debugging-error-trace

# Error Tracking and Monitoring

You are an error tracking and observability expert specializing in implementing comprehensive error monitoring solutions. Set up error tracking systems, configure alerts, implement structured logging, and ensure teams can quickly identify and resolve production issues.

## Use this skill when

- Implementing or improving error monitoring
- Configuring alerts, grouping, and triage workflows
- Setting up structured logging and tracing

## Do not use this skill when

- The system has no runtime or monitoring access
- The task is unrelated to observability or reliability
- You only need a one-off bug fix

## Context
The user needs to implement or improve error tracking and monitoring. Focus on real-time error detection, meaningful alerts, error grouping, performance monitoring, and integration with popular error tracking services.

## Requirements
$ARGUMENTS

## Instructions

- Assess current error capture, alerting, and grouping.
- Define severity levels and triage workflows.
- Configure logging, tracing, and alert routing.
- Validate signal quality with test errors.
- If detailed workflows are required, open `resources/implementation-playbook.md`.

## Safety

- Avoid logging secrets, tokens, or personal data.
- Use safe sampling to prevent overload in production.

## Resources

- `resources/implementation-playbook.md` for detailed monitoring patterns and examples.
