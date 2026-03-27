# Agent Dispatch & System Prompt Architecture Analysis

**Repository:** `/Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY`  
**Date:** March 15, 2025  
**Status:** Complete ✓

---

## Overview

This analysis traces the complete flow of how agents are dispatched, how their system prompts are built, and how skills are injected into LLM calls in the Software Factory platform.

**Key Finding:** Agent identity and skills are **dynamically composed** based on mission context at runtime, not pre-templated. This enables mission-aware, role-appropriate, and seniority-aware prompt generation.

---

## Documents in This Package

### 1. **AGENT_FLOW_QUICKREF.md** (17 KB)
**Best for:** Quick understanding of the complete flow  
**Time to read:** 5-10 minutes

- 5-step journey visualization
- 5 key concepts with examples
- Context tier reference table
- Role-specific instruction mapping
- 11-part system prompt assembly diagram
- Quick file reference map
- Full CTO example with complete prompt

**Start here if:** You want a quick overview of the flow.

---

### 2. **AGENT_DISPATCH_SUMMARY.txt** (15 KB)
**Best for:** Complete understanding with examples  
**Time to read:** 15-20 minutes

- Complete overview of all components
- Data structure flow diagram
- Detailed example: CTO receiving "debug" mission
- Composition & blending mechanisms
- 30+ key takeaways
- Complete file reference table
- Built-in agent examples (CTO, Backend Dev, QA Lead)

**Start here if:** You want to understand the "why" and mechanisms.

---

### 3. **CODE_PATHS.md** (35 KB)
**Best for:** Implementing or modifying the system  
**Time to read:** 20-30 minutes

- Exact file paths and line numbers
- Complete function signatures with full signatures
- Code snippets for all 8 major components:
  1. AgentDef (identity storage)
  2. AgentLoop (message dispatch)
  3. ExecutionContext builder (skills injection)
  4. ExecutionContext dataclass
  5. Skills injection system (context patterns)
  6. System prompt builder (11-part assembly)
  7. Executor (LLM call)
  8. LLM client (chat completion)
- Complete end-to-end data flow with all types

**Start here if:** You need to understand or modify the implementation.

---

## The Complete Flow (5 Steps)

```
Step 1: Message Arrives
  └─ AgentLoop._run_loop() waits in inbox
     File: platform/agents/loop.py:188-250

Step 2: Build Execution Context (← Skills Injected Here)
  └─ _build_context() assembles:
     • History (15-50 messages)
     • Project memory entries
     • Project files (VISION.md, SPECS.md)
     • ★ AUTO-INJECTED SKILLS from mission text + agent role
     • Context tier (L0/L1/L2)
     File: platform/agents/loop.py:330-620

Step 3: Build System Prompt (11-Part Assembly)
  └─ _build_system_prompt(ctx) combines:
     1. Base system_prompt
     2. Persona
     3. Motivation
     4. PUA framework (Iron Rules + proactivity)
     5. Tool instructions
     6. Role-specific block (CTO vs QA vs Dev)
     7. Architecture guidelines
     8. Project context (tier-aware)
     9. ★ COMPOSED SKILLS (from step 2)
     10. Permissions (delegation, veto, approval)
     11. Traceability (for dev roles)
     File: platform/agents/prompt_builder.py:125-360

Step 4: Call LLM with Complete Prompt
  └─ LLMClient.chat(
       messages=[system_prompt + history + user_msg],
       provider="azure-openai",
       model="gpt-5-mini",
       system_prompt=full_assembled_prompt,  ← 8,500-12,000 tokens
       tools=[...]
     )
     File: platform/llm/client.py:388-550

Step 5: Tool Execution Loop
  └─ if tool_calls: execute → add to messages → loop back to step 4
     else: return final response
     File: platform/agents/executor.py:716-850
```

---

## Key Components

### Agent Identity (`AgentDef`)
**File:** `platform/agents/store.py:43-77`

Stores agent definition in database:
- `name` — Display name (e.g., "Karim Benali")
- `role` — Role title (e.g., "CTO", "Backend Developer")
- `persona` — Personality traits (injected into prompt)
- `motivation` — Drives and goals (injected into prompt)
- `skills` — Manual skill IDs (fallback for injection)
- `tools` — Available tools (code_read, code_write, etc.)
- `hierarchy_rank` — 0=CEO, 50=junior (controls context tier)
- `permissions` — can_delegate, can_veto, can_approve

### Skills Injection (The Critical Point)
**File:** `platform/agents/skills_integration.py:89-216`

**Priority order:**
1. Azure embeddings (if configured)
2. Trigger-based injection (keywords in mission text)
3. Fallback to manual skills (agent.skills)

**Example:**
```
Mission: "Debug the failing deployment"
  → Keyword "debug" detected
  → Phase = "debug"
  → Auto-inject: [systematic-debugging, debugging-strategies, ac-adversarial]
```

### Context Tiers
**File:** `platform/llm/context_tiers.py`

- **L0:** Abstract/routing (no memory/vision, ~500 chars)
- **L1:** Standard agents (3-5 memory entries, no vision, ~3,000 chars)
- **L2:** Organizers (10 memory entries, full vision, ~6,000 chars)

Selected by: `hierarchy_rank + capability_grade`

### System Prompt Builder
**File:** `platform/agents/prompt_builder.py:125-360`

Assembles 11-part prompt from:
1. Base system_prompt
2. Persona
3. Motivation
4. PUA framework
5. Tool instructions
6. Role-specific block
7. Architecture guidelines
8. Project context (tier-aware)
9. ★ **AUTO-INJECTED SKILLS** ← Key composition point
10. Permissions
11. Traceability (for dev roles)

---

## Entry Points

### Agent Dispatch
- **Start:** `platform/agents/loop.py:60` — `class AgentLoop`
- **Run loop:** `platform/agents/loop.py:188` — `async def _run_loop(self)`

### Skills Injection
- **Build context:** `platform/agents/loop.py:330` — `async def _build_context(self)`
- **Enrich skills:** `platform/agents/skills_integration.py:89` — `def enrich_agent_with_skills(...)`

### Prompt Assembly
- **Build prompt:** `platform/agents/prompt_builder.py:125` — `def _build_system_prompt(ctx)`
- **Build messages:** `platform/agents/prompt_builder.py:362` — `def _build_messages(ctx, user_message)`

### Executor
- **Run agent:** `platform/agents/executor.py:716` — `async def run(self, ctx, user_message)`
- **Streaming:** `platform/agents/executor.py:1313` — `async def run_streaming(...)`

### LLM Client
- **Chat:** `platform/llm/client.py:388` — `async def chat(...)`
- **HTTP call:** `platform/llm/client.py:1047` — `async def _do_chat(...)`

---

## Composition & Blending Mechanisms

### 1. Skills Injection (Dynamic)
Mission keywords → Phase detection → Context patterns → Skill sets

### 2. Role-Specific Instructions (Static per role)
Agent role → Classification → Role-specific instruction block

Example roles:
- **CTO:** create_project, create_team, create_mission, compose_workflow
- **QA:** run_e2e_tests (MANDATORY), create_ticket for failures
- **Dev:** code_read → code_write → build/test cycle (MANDATORY)
- **Security:** SAST scans (bandit, semgrep, npm audit)
- **Product:** create_feature, create_story (AO traceability)

### 3. Context Tier Blending (Seniority-aware)
hierarchy_rank → tier selection → context density (L0/L1/L2)

### 4. Permission Synthesis (Authority-aware)
permissions dict → delegation/veto/approval blocks

### 5. PUA Framework (Universal)
Applied to ALL agents → Iron Rules + proactivity mandate  
Source: github.com/tanweai/pua (MIT license)

---

## Complete Example: CTO Debugging Deployment

**Input:**
```
Agent: Karim Benali (CTO, hierarchy_rank=0, can_delegate=true)
Mission: "Debug the failing deployment"
```

**Context built (_build_context):**
```
• History: 50 messages (rank=0 → max history)
• Project memory: 10 entries (organizer)
• Project files: VISION.md, SPECS.md (full)
• Skills auto-injected:
  - Mission keyword "debug" detected
  - Phase = "debug"
  - Context pattern "debug" → [systematic-debugging, debugging-strategies, ac-adversarial]
• Context tier: L2 (full context for rank=0)
• Vision: Full 3,000 chars
```

**System prompt assembled (_build_system_prompt):**
```
1. Base: (agent.system_prompt)
2. Persona: "Visionary, decisive, detail-oriented..."
3. Motivation: "Orchestrate factory, empower teams..."
4. PUA: Iron Rules + proactivity mandate
5. Tools: memory_search, memory_store, deep_search, code_read, ...
6. CTO block: create_project, create_team, create_mission, compose_workflow
7. Guidelines: Architecture/tech guidelines from DSI
8. Context: 10 memory entries about architecture, decisions, tech stack
9. ★ SKILLS:
   - Systematic Debugging (4-phase root cause)
   - Debugging Strategies (binary search, profiling)
   - Adversarial Quality Check (edge cases, error paths)
10. Delegation: [DELEGATE:dev-backend] Investigate...
11. Permissions: Can veto, can approve
```

**LLM receives:** Full assembled prompt (~10,000 tokens) + conversation history

**Result:** Cohesive CTO persona ready to debug effectively

---

## Key Insights

✓ **Skills are NOT hardcoded** — they're dynamically injected based on mission + role + tier

✓ **Agent identity flows:** DB → Config → ExecutionContext → SystemPrompt → LLM

✓ **The "11-part assembly"** ensures all traits are represented without duplication

✓ **Multi-agent composition** via delegation syntax + hierarchical permissions

✓ **"Blending" works through:**
  - Automatic skill injection (mission-aware)
  - Context tier selection (seniority-aware)
  - Role-specific instructions (role-aware)
  - Permission synthesis (authority-aware)

---

## File Structure

```
platform/agents/
├── store.py                    # AgentDef model + storage
├── loop.py                     # AgentLoop + _build_context
├── executor.py                 # AgentExecutor.run() + ExecutionContext
├── prompt_builder.py           # _build_system_prompt() + _build_messages
├── skills_integration.py       # enrich_agent_with_skills()
├── pua.py                      # build_motivation_block()
├── tool_schemas.py             # _get_tool_schemas(), _classify_agent_role()
└── tool_runner.py              # _execute_tool()

platform/llm/
├── client.py                   # LLMClient.chat()
├── context_tiers.py            # ContextTier, select_tier()
└── providers.py                # Provider configs
```

---

## How to Use This Documentation

**For quick understanding (5 min):**
→ Read `AGENT_FLOW_QUICKREF.md`

**For complete understanding (20 min):**
→ Read `AGENT_DISPATCH_SUMMARY.txt`

**For implementation (30 min):**
→ Read `CODE_PATHS.md`

**For deep dive:**
→ Follow the entry points in the code with reference to `CODE_PATHS.md`

---

## Next Steps

1. **Understand the flow:** Read AGENT_FLOW_QUICKREF.md
2. **Learn the mechanisms:** Read AGENT_DISPATCH_SUMMARY.txt
3. **Study the code:** Read CODE_PATHS.md
4. **Explore implementation:**
   - `platform/agents/loop.py:330` — _build_context()
   - `platform/agents/skills_integration.py:89` — enrich_agent_with_skills()
   - `platform/agents/prompt_builder.py:125` — _build_system_prompt()
   - `platform/agents/executor.py:716` — AgentExecutor.run()

---

## Questions?

Each document contains examples, code snippets, and file references. Use CODE_PATHS.md as a reference for exact signatures and implementations.

---

**Analysis Date:** March 15, 2025  
**Repository:** Software Factory Platform  
**Status:** ✓ Complete
