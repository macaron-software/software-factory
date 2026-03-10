---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/multi-agent-patterns
# WHY: Our platform IS a multi-agent system. This skill gives orchestrator and
#      LLM-ops agents concrete patterns for context isolation, handoffs, and
#      avoiding the supervisor bottleneck / telephone-game problem.
name: multi-agent-patterns
version: "1.0.0"
description: >
  Multi-agent architecture patterns for designing, coordinating, and debugging
  systems with multiple LLM agents. Use when designing agent orchestration,
  implementing supervisor/swarm/hierarchical patterns, or debugging context
  saturation and agent coordination failures.
metadata:
  category: ai
  triggers:
    - "when designing a multi-agent system"
    - "when implementing supervisor or orchestrator pattern"
    - "when coordinating multiple specialized agents"
    - "when debugging context saturation or agent drift"
    - "when choosing between swarm, supervisor, or hierarchical architecture"
    - "when agents are producing degraded output due to context accumulation"
# EVAL CASES
eval_cases:
  - id: choose-architecture
    prompt: |
      We're building a code review pipeline: one agent analyzes security,
      another checks code quality, a third verifies test coverage. Results
      need to be combined into a final report. Which multi-agent pattern fits?
    should_trigger: true
    checks:
      - "regex:supervisor|orchestrat|parallel|swarm|hierarch"
      - "regex:context.*isolat|separate.*context|indepen|parallel.*exec"
      - "length_min:80"
    expectations:
      - "recommends supervisor/orchestrator pattern for parallel specialist agents"
      - "explains context isolation benefit: each specialist gets clean context"
      - "notes the aggregation step at supervisor level"
    tags: [architecture, orchestrator, parallelism]

  - id: telephone-game-problem
    prompt: |
      Our supervisor agent coordinates 3 sub-agents. The final output often
      misses important details from the sub-agent responses. What's wrong?
    should_trigger: true
    checks:
      - "regex:telephone|paraphras|pass.*through|direct.*response|synthesis.*loss|fidelit"
      - "regex:forward|direct|bypass.*supervisor|structured.*output"
      - "length_min:80"
    expectations:
      - "identifies the 'telephone game' problem: supervisor paraphrases and loses fidelity"
      - "recommends direct pass-through: sub-agents return structured output, supervisor routes not rewrites"
      - "suggests using structured schemas so sub-agents return exact data"
    tags: [supervisor, fidelity, coordination]

  - id: context-saturation
    prompt: |
      Our orchestrator agent starts performing poorly after 10+ tool calls —
      it forgets earlier decisions and starts contradicting itself.
    should_trigger: true
    checks:
      - "regex:context.*saturat|context.*window|compres|summar|checkpoint|handoff|fresh.*context"
      - "regex:lost.*middle|attention|token.*limit|context.*poison"
      - "length_min:80"
    expectations:
      - "diagnoses context window saturation / lost-in-middle degradation"
      - "recommends periodic checkpointing/summarization of decision state"
      - "suggests offloading to sub-agents with fresh contexts for new subtasks"
    tags: [context-window, saturation, degradation]
---

# Multi-Agent Architecture Patterns

Multi-agent systems distribute work across multiple LLM instances, each with their
own context window. The primary purpose is **context isolation**, not role-playing.

## When to Use Multi-Agent

Use multi-agent when:
- Single-agent context limits constrain task complexity
- Tasks decompose naturally into **parallel** subtasks
- Different subtasks need different tools or system prompts
- Context window saturation is degrading quality

**Token Reality**: Multi-agent ~15× token multiplier vs single-agent. Only add
agents when the parallelization/isolation benefit outweighs the cost.

---

## Three Core Patterns

### Pattern 1: Supervisor/Orchestrator

```
User → Supervisor → [Specialist A | Specialist B | Specialist C] → Aggregation → Output
```

**Use when**: Tasks with clear decomposition, human-in-the-loop required, strict workflow control.

**⚠️ The Telephone Game Problem**: Supervisors that paraphrase sub-agent responses
lose fidelity. Benchmark data shows 50% degradation vs optimized versions.

**Fix**: Implement direct pass-through — sub-agents return structured output, supervisor routes without rewriting:
```python
def forward_message(message: str):
    """Sub-agent passes response directly, bypassing supervisor synthesis."""
    return {"type": "direct_response", "content": message}
```

### Pattern 2: Peer-to-Peer / Swarm

```
Agent A ←→ Agent B ←→ Agent C  (any can hand off to any)
```

**Use when**: Flexible exploration, emergent requirements, no rigid predefined plan.

**⚠️ Risk**: Without convergence constraints, agents diverge. Define explicit handoff protocols with state passing.

### Pattern 3: Hierarchical

```
Strategy Layer → Planning Layer → Execution Layer
```

**Use when**: Large-scale projects with management layers, complex planning+execution separation.

---

## Context Isolation Mechanisms

| Mechanism | Best for | Tradeoff |
|-----------|----------|----------|
| **Full context delegation** | Complex tasks needing full understanding | Defeats isolation purpose |
| **Instruction passing** | Well-defined atomic subtasks | Limits sub-agent flexibility |
| **File system memory** | Shared state across agents | Latency + consistency challenges |

---

## Consensus & Coordination

**Don't use simple majority voting** — hallucinations get equal weight to correct reasoning.

**Debate Protocol** (better):
- Agents critique each other's outputs over rounds
- Adversarial critique → higher accuracy than collaborative consensus

**Triggers**:
- Stall trigger: no progress after N rounds → supervisor intervention
- Sycophancy trigger: agents mimicking each other → inject dissent

---

## Failure Modes & Mitigations

| Failure | Cause | Mitigation |
|---------|-------|------------|
| **Supervisor bottleneck** | Supervisor accumulates all worker context | Output schema constraints, checkpointing |
| **Telephone game** | Supervisor paraphrases, loses detail | Direct pass-through mechanism |
| **Context saturation** | Long-running agent fills context window | Periodic summarization, fresh sub-agents |
| **Divergence** | Agents pursue different goals | Clear objective boundaries per agent |
| **Coordination overhead** | Too much agent communication | Batch results, async communication |

---

## SF Platform Patterns

In our Software Factory:
- **Orchestrator** = Supervisor pattern (Gabriel Mercier)
- **AC Team** = Hierarchical (ac-architect → ac-codex → ac-adversarial → ac-cicd)
- **Security workflow** = Swarm (pentester → researcher → exploit-dev ← ciso supervises)
- **Context isolation**: Each AC agent reads previous outputs via `code_read` — not from supervisor context
