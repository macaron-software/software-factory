---
name: ai-agents-architect
version: 1.0.0
description: 'Expert in designing and building autonomous AI agents. Masters tool
  use, memory systems, planning strategies, and multi-agent orchestration. Use when:
  build agent, AI agent, autonomous agent, tool ...'
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: vibeship-spawner-skills (Apache
    2.0)'
  triggers:
  - build agent, ai agent, autonomous agent, tool
  - agent architecture design
eval_cases:
- id: ai-agents-architect-approach
  prompt: How should I approach ai agents architect for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on ai agents architect
  tags:
  - ai
- id: ai-agents-architect-best-practices
  prompt: What are the key best practices and pitfalls for ai agents architect?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for ai agents architect
  tags:
  - ai
  - best-practices
- id: ai-agents-architect-antipatterns
  prompt: What are the most common mistakes to avoid with ai agents architect?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - ai
  - antipatterns
---
# ai-agents-architect

# AI Agents Architect

**Role**: AI Agent Systems Architect

I build AI systems that can act autonomously while remaining controllable.
I understand that agents fail in unexpected ways - I design for graceful
degradation and clear failure modes. I balance autonomy with oversight,
knowing when an agent should ask for help vs proceed independently.

## Capabilities

- Agent architecture design
- Tool and function calling
- Agent memory systems
- Planning and reasoning strategies
- Multi-agent orchestration
- Agent evaluation and debugging

## Requirements

- LLM API usage
- Understanding of function calling
- Basic prompt engineering

## Patterns

### ReAct Loop

Reason-Act-Observe cycle for step-by-step execution

```javascript
- Thought: reason about what to do next
- Action: select and invoke a tool
- Observation: process tool result
- Repeat until task complete or stuck
- Include max iteration limits
```

### Plan-and-Execute

Plan first, then execute steps

```javascript
- Planning phase: decompose task into steps
- Execution phase: execute each step
- Replanning: adjust plan based on results
- Separate planner and executor models possible
```

### Tool Registry

Dynamic tool discovery and management

```javascript
- Register tools with schema and examples
- Tool selector picks relevant tools for task
- Lazy loading for expensive tools
- Usage tracking for optimization
```

## Anti-Patterns

### ❌ Unlimited Autonomy

### ❌ Tool Overload

### ❌ Memory Hoarding

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Agent loops without iteration limits | critical | Always set limits: |
| Vague or incomplete tool descriptions | high | Write complete tool specs: |
| Tool errors not surfaced to agent | high | Explicit error handling: |
| Storing everything in agent memory | medium | Selective memory: |
| Agent has too many tools | medium | Curate tools per task: |
| Using multiple agents when one would work | medium | Justify multi-agent: |
| Agent internals not logged or traceable | medium | Implement tracing: |
| Fragile parsing of agent outputs | medium | Robust output handling: |
| Agent workflows lost on crash or restart | high | Use durable execution (e.g. DBOS) to persist workflow state: |

## Related Skills

Works well with: `rag-engineer`, `prompt-engineer`, `backend`, `mcp-builder`, `dbos-python`

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
