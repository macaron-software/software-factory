---
name: dotnet-backend-patterns
version: 1.0.0
description: Master C#/.NET backend development patterns for building robust APIs,
  MCP servers, and enterprise applications. Covers async/await, dependency injection,
  Entity Framework Core, Dapper, configuratio...
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - reviewing c# code for quality and performance
  - designing service architectures with dependency injection
eval_cases:
- id: dotnet-backend-patterns-approach
  prompt: How should I approach dotnet backend patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on dotnet backend patterns
  tags:
  - dotnet
- id: dotnet-backend-patterns-best-practices
  prompt: What are the key best practices and pitfalls for dotnet backend patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for dotnet backend patterns
  tags:
  - dotnet
  - best-practices
- id: dotnet-backend-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with dotnet backend patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - dotnet
  - antipatterns
---
# dotnet-backend-patterns

# .NET Backend Development Patterns

Master C#/.NET patterns for building production-grade APIs, MCP servers, and enterprise backends with modern best practices (2024/2025).

## Use this skill when

- Developing new .NET Web APIs or MCP servers
- Reviewing C# code for quality and performance
- Designing service architectures with dependency injection
- Implementing caching strategies with Redis
- Writing unit and integration tests
- Optimizing database access with EF Core or Dapper
- Configuring applications with IOptions pattern
- Handling errors and implementing resilience patterns

## Do not use this skill when

- The project is not using .NET or C#
- You only need frontend or client guidance
- The task is unrelated to backend architecture

## Instructions

- Define architecture boundaries, modules, and layering.
- Apply DI, async patterns, and resilience strategies.
- Validate data access performance and caching.
- Add tests and observability for critical flows.
- If detailed patterns are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed .NET patterns and examples.
