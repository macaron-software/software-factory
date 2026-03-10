---
name: dbos-typescript
version: 1.0.0
description: DBOS TypeScript SDK for building reliable, fault-tolerant applications
  with durable workflows. Use this skill when writing TypeScript code with DBOS, creating
  workflows and steps, using queues, usi...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://docs.dbos.dev/'
  triggers:
  - creating workflows and steps
eval_cases:
- id: dbos-typescript-approach
  prompt: How should I approach dbos typescript for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on dbos typescript
  tags:
  - dbos
- id: dbos-typescript-best-practices
  prompt: What are the key best practices and pitfalls for dbos typescript?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for dbos typescript
  tags:
  - dbos
  - best-practices
- id: dbos-typescript-antipatterns
  prompt: What are the most common mistakes to avoid with dbos typescript?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - dbos
  - antipatterns
---
# dbos-typescript

# DBOS TypeScript Best Practices

Guide for building reliable, fault-tolerant TypeScript applications with DBOS durable workflows.

## When to Use

Reference these guidelines when:
- Adding DBOS to existing TypeScript code
- Creating workflows and steps
- Using queues for concurrency control
- Implementing workflow communication (events, messages, streams)
- Configuring and launching DBOS applications
- Using DBOSClient from external applications
- Testing DBOS applications

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Lifecycle | CRITICAL | `lifecycle-` |
| 2 | Workflow | CRITICAL | `workflow-` |
| 3 | Step | HIGH | `step-` |
| 4 | Queue | HIGH | `queue-` |
| 5 | Communication | MEDIUM | `comm-` |
| 6 | Pattern | MEDIUM | `pattern-` |
| 7 | Testing | LOW-MEDIUM | `test-` |
| 8 | Client | MEDIUM | `client-` |
| 9 | Advanced | LOW | `advanced-` |

## Critical Rules

### Installation

Always install the latest version of DBOS:

```bash
npm install @dbos-inc/dbos-sdk@latest
```

### DBOS Configuration and Launch

A DBOS application MUST configure and launch DBOS before running any workflows:

```typescript
import { DBOS } from "@dbos-inc/dbos-sdk";

async function main() {
  DBOS.setConfig({
    name: "my-app",
    systemDatabaseUrl: process.env.DBOS_SYSTEM_DATABASE_URL,
  });
  await DBOS.launch();
  await myWorkflow();
}

main().catch(console.log);
```

### Workflow and Step Structure

Workflows are comprised of steps. Any function performing complex operations or accessing external services must be run as a step using `DBOS.runStep`:

```typescript
import { DBOS } from "@dbos-inc/dbos-sdk";

async function fetchData() {
  return await fetch("https://api.example.com").then(r => r.json());
}

async function myWorkflowFn() {
  const result = await DBOS.runStep(fetchData, { name: "fetchData" });
  return result;
}
const myWorkflow = DBOS.registerWorkflow(myWorkflowFn);
```

### Key Constraints

- Do NOT call, start, or enqueue workflows from within steps
- Do NOT use threads or uncontrolled concurrency to start workflows - use `DBOS.startWorkflow` or queues
- Workflows MUST be deterministic - non-deterministic operations go in steps
- Do NOT modify global variables from workflows or steps

## How to Use

Read individual rule files for detailed explanations and examples:

```
references/lifecycle-config.md
references/workflow-determinism.md
references/queue-concurrency.md
```

## References

- https://docs.dbos.dev/
- https://github.com/dbos-inc/dbos-transact-ts
