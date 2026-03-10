---
name: dbos-golang
version: 1.0.0
description: DBOS Go SDK for building reliable, fault-tolerant applications with durable
  workflows. Use this skill when writing Go code with DBOS, creating workflows and
  steps, using queues, using the DBOS Clie...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: https://docs.dbos.dev/'
  triggers:
  - creating workflows and steps
eval_cases:
- id: dbos-golang-approach
  prompt: How should I approach dbos golang for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on dbos golang
  tags:
  - dbos
- id: dbos-golang-best-practices
  prompt: What are the key best practices and pitfalls for dbos golang?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for dbos golang
  tags:
  - dbos
  - best-practices
- id: dbos-golang-antipatterns
  prompt: What are the most common mistakes to avoid with dbos golang?
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
# dbos-golang

# DBOS Go Best Practices

Guide for building reliable, fault-tolerant Go applications with DBOS durable workflows.

## When to Use

Reference these guidelines when:
- Adding DBOS to existing Go code
- Creating workflows and steps
- Using queues for concurrency control
- Implementing workflow communication (events, messages, streams)
- Configuring and launching DBOS applications
- Using the DBOS Client from external applications
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

Install the DBOS Go module:

```bash
go get github.com/dbos-inc/dbos-transact-golang/dbos@latest
```

### DBOS Configuration and Launch

A DBOS application MUST create a context, register workflows, and launch before running any workflows:

```go
package main

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/dbos-inc/dbos-transact-golang/dbos"
)

func main() {
	ctx, err := dbos.NewDBOSContext(context.Background(), dbos.Config{
		AppName:     "my-app",
		DatabaseURL: os.Getenv("DBOS_SYSTEM_DATABASE_URL"),
	})
	if err != nil {
		log.Fatal(err)
	}
	defer dbos.Shutdown(ctx, 30*time.Second)

	dbos.RegisterWorkflow(ctx, myWorkflow)

	if err := dbos.Launch(ctx); err != nil {
		log.Fatal(err)
	}
}
```

### Workflow and Step Structure

Workflows are comprised of steps. Any function performing complex operations or accessing external services must be run as a step using `dbos.RunAsStep`:

```go
func fetchData(ctx context.Context) (string, error) {
	resp, err := http.Get("https://api.example.com/data")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return string(body), nil
}

func myWorkflow(ctx dbos.DBOSContext, input string) (string, error) {
	result, err := dbos.RunAsStep(ctx, fetchData, dbos.WithStepName("fetchData"))
	if err != nil {
		return "", err
	}
	return result, nil
}
```

### Key Constraints

- Do NOT start or enqueue workflows from within steps
- Do NOT use uncontrolled goroutines to start workflows - use `dbos.RunWorkflow` with queues or `dbos.Go`/`dbos.Select` for concurrent steps
- Workflows MUST be deterministic - non-deterministic operations go in steps
- Do NOT modify global variables from workflows or steps
- All workflows and queues MUST be registered before calling `Launch()`

## How to Use

Read individual rule files for detailed explanations and examples:

```
references/lifecycle-config.md
references/workflow-determinism.md
references/queue-concurrency.md
```

## References

- https://docs.dbos.dev/
- https://github.com/dbos-inc/dbos-transact-golang
