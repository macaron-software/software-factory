---
name: antigravity-workflows
version: 1.0.0
description: Orchestrate multiple Antigravity skills through guided workflows for
  SaaS MVP delivery, security audits, AI agent builds, and browser QA.
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: self'
  triggers:
  - 'the goal is multi-phase (for example: plan, build, test, ship)'
eval_cases:
- id: antigravity-workflows-approach
  prompt: How should I approach antigravity workflows for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on antigravity workflows
  tags:
  - antigravity
- id: antigravity-workflows-best-practices
  prompt: What are the key best practices and pitfalls for antigravity workflows?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for antigravity workflows
  tags:
  - antigravity
  - best-practices
- id: antigravity-workflows-antipatterns
  prompt: What are the most common mistakes to avoid with antigravity workflows?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - antigravity
  - antipatterns
---
# antigravity-workflows

# Antigravity Workflows

Use this skill to turn a complex objective into a guided sequence of skill invocations.

## When to Use This Skill

Use this skill when:
- The user wants to combine several skills without manually selecting each one.
- The goal is multi-phase (for example: plan, build, test, ship).
- The user asks for best-practice execution for common scenarios like:
  - Shipping a SaaS MVP
  - Running a web security audit
  - Building an AI agent system
  - Implementing browser automation and E2E QA

## Workflow Source of Truth

Read workflows in this order:
1. `docs/WORKFLOWS.md` for human-readable playbooks.
2. `data/workflows.json` for machine-readable workflow metadata.

## How to Run This Skill

1. Identify the user's concrete outcome.
2. Propose the 1-2 best matching workflows.
3. Ask the user to choose one.
4. Execute step-by-step:
   - Announce current step and expected artifact.
   - Invoke recommended skills for that step.
   - Verify completion criteria before moving to next step.
5. At the end, provide:
   - Completed artifacts
   - Validation evidence
   - Remaining risks and next actions

## Default Workflow Routing

- Product delivery request -> `ship-saas-mvp`
- Security review request -> `security-audit-web-app`
- Agent/LLM product request -> `build-ai-agent-system`
- E2E/browser testing request -> `qa-browser-automation`

## Copy-Paste Prompts

```text
Use @antigravity-workflows to run the "Ship a SaaS MVP" workflow for my project idea.
```

```text
Use @antigravity-workflows and execute a full "Security Audit for a Web App" workflow.
```

```text
Use @antigravity-workflows to guide me through "Build an AI Agent System" with checkpoints.
```

```text
Use @antigravity-workflows to execute the "QA and Browser Automation" workflow and stabilize flaky tests.
```

## Limitations

- This skill orchestrates; it does not replace specialized skills.
- It depends on the local availability of referenced skills.
- It does not guarantee success without environment access, credentials, or required infrastructure.
- For stack-specific browser automation in Go, `go-playwright` may require the corresponding skill to be present in your local skills repository.

## Related Skills

- `concise-planning`
- `brainstorming`
- `workflow-automation`
- `verification-before-completion`
