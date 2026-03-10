---
name: incident-response-smart-fix
version: 1.0.0
description: '[Extended thinking: This workflow implements a sophisticated debugging
  and resolution pipeline that leverages AI-assisted debugging tools and observability
  platforms to systematically diagnose and res'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - when working on incident response smart fix
eval_cases:
- id: incident-response-smart-fix-approach
  prompt: How should I approach incident response smart fix for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on incident response smart fix
  tags:
  - incident
- id: incident-response-smart-fix-best-practices
  prompt: What are the key best practices and pitfalls for incident response smart
    fix?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for incident response smart fix
  tags:
  - incident
  - best-practices
- id: incident-response-smart-fix-antipatterns
  prompt: What are the most common mistakes to avoid with incident response smart
    fix?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - incident
  - antipatterns
---
# incident-response-smart-fix

# Intelligent Issue Resolution with Multi-Agent Orchestration

[Extended thinking: This workflow implements a sophisticated debugging and resolution pipeline that leverages AI-assisted debugging tools and observability platforms to systematically diagnose and resolve production issues. The intelligent debugging strategy combines automated root cause analysis with human expertise, using modern 2024/2025 practices including AI code assistants (GitHub Copilot, Claude Code), observability platforms (Sentry, DataDog, OpenTelemetry), git bisect automation for regression tracking, and production-safe debugging techniques like distributed tracing and structured logging. The process follows a rigorous four-phase approach: (1) Issue Analysis Phase - error-detective and debugger agents analyze error traces, logs, reproduction steps, and observability data to understand the full context of the failure including upstream/downstream impacts, (2) Root Cause Investigation Phase - debugger and code-reviewer agents perform deep code analysis, automated git bisect to identify introducing commit, dependency compatibility checks, and state inspection to isolate the exact failure mechanism, (3) Fix Implementation Phase - domain-specific agents (python-pro, typescript-pro, rust-expert, etc.) implement minimal fixes with comprehensive test coverage including unit, integration, and edge case tests while following production-safe practices, (4) Verification Phase - test-automator and performance-engineer agents run regression suites, performance benchmarks, security scans, and verify no new issues are introduced. Complex issues spanning multiple systems require orchestrated coordination between specialist agents (database-optimizer → performance-engineer → devops-troubleshooter) with explicit context passing and state sharing. The workflow emphasizes understanding root causes over treating symptoms, implementing lasting architectural improvements, automating detection through enhanced monitoring and alerting, and preventing future occurrences through type system enhancements, static analysis rules, and improved error handling patterns. Success is measured not just by issue resolution but by reduced mean time to recovery (MTTR), prevention of similar issues, and improved system resilience.]

## Use this skill when

- Working on intelligent issue resolution with multi-agent orchestration tasks or workflows
- Needing guidance, best practices, or checklists for intelligent issue resolution with multi-agent orchestration

## Do not use this skill when

- The task is unrelated to intelligent issue resolution with multi-agent orchestration
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
