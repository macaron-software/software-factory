---
name: async-python-patterns
version: 1.0.0
description: Master Python asyncio, concurrent programming, and async/await patterns
  for high-performance applications. Use when building async APIs, concurrent systems,
  or I/O-bound applications requiring non-...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - building async apis, concurrent systems, or i/o-bound applications requiring non
  - building async web apis (fastapi, aiohttp, sanic)
  - implementing concurrent i/o operations (database, file, network)
  - creating web scrapers with concurrent requests
eval_cases:
- id: async-python-patterns-approach
  prompt: How should I approach async python patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on async python patterns
  tags:
  - async
- id: async-python-patterns-best-practices
  prompt: What are the key best practices and pitfalls for async python patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for async python patterns
  tags:
  - async
  - best-practices
- id: async-python-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with async python patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - async
  - antipatterns
---
# async-python-patterns

# Async Python Patterns

Comprehensive guidance for implementing asynchronous Python applications using asyncio, concurrent programming patterns, and async/await for building high-performance, non-blocking systems.

## Use this skill when

- Building async web APIs (FastAPI, aiohttp, Sanic)
- Implementing concurrent I/O operations (database, file, network)
- Creating web scrapers with concurrent requests
- Developing real-time applications (WebSocket servers, chat systems)
- Processing multiple independent tasks simultaneously
- Building microservices with async communication
- Optimizing I/O-bound workloads
- Implementing async background tasks and queues

## Do not use this skill when

- The workload is CPU-bound with minimal I/O.
- A simple synchronous script is sufficient.
- The runtime environment cannot support asyncio/event loop usage.

## Instructions

- Clarify workload characteristics (I/O vs CPU), targets, and runtime constraints.
- Pick concurrency patterns (tasks, gather, queues, pools) with cancellation rules.
- Add timeouts, backpressure, and structured error handling.
- Include testing and debugging guidance for async code paths.
- If detailed examples are required, open `resources/implementation-playbook.md`.

Refer to `resources/implementation-playbook.md` for detailed patterns and examples.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
