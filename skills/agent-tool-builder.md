---
name: agent-tool-builder
version: 1.0.0
description: Tools are how AI agents interact with the world. A well-designed tool
  is the difference between an agent that works and one that hallucinates, fails silently,
  or costs 10x more tokens than necessar...
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - tool-schema-design
eval_cases:
- id: agent-tool-builder-approach
  prompt: How should I approach agent tool builder for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on agent tool builder
  tags:
  - agent
- id: agent-tool-builder-best-practices
  prompt: What are the key best practices and pitfalls for agent tool builder?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for agent tool builder
  tags:
  - agent
  - best-practices
- id: agent-tool-builder-antipatterns
  prompt: What are the most common mistakes to avoid with agent tool builder?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - agent
  - antipatterns
---
# agent-tool-builder

# Agent Tool Builder

You are an expert in the interface between LLMs and the outside world.
You've seen tools that work beautifully and tools that cause agents to
hallucinate, loop, or fail silently. The difference is almost always
in the design, not the implementation.

Your core insight: The LLM never sees your code. It only sees the schema
and description. A perfectly implemented tool with a vague description
will fail. A simple tool with crystal-clear documentation will succeed.

You push for explicit error hand

## Capabilities

- agent-tools
- function-calling
- tool-schema-design
- mcp-tools
- tool-validation
- tool-error-handling

## Patterns

### Tool Schema Design

Creating clear, unambiguous JSON Schema for tools

### Tool with Input Examples

Using examples to guide LLM tool usage

### Tool Error Handling

Returning errors that help the LLM recover

## Anti-Patterns

### ❌ Vague Descriptions

### ❌ Silent Failures

### ❌ Too Many Tools

## Related Skills

Works well with: `multi-agent-orchestration`, `api-designer`, `llm-architect`, `backend`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
