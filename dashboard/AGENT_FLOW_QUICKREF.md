# AGENT DISPATCH & PROMPT BUILDING — QUICK REFERENCE

## The Complete Journey (5 Steps)

```
┌────────────────────────────────────────────────────────────────────┐
│ Step 1: MESSAGE ARRIVES                                            │
├────────────────────────────────────────────────────────────────────┤
│ AgentLoop._run_loop() receives message from user                   │
│ File: platform/agents/loop.py:188-250                              │
│ Signal: Agent status → THINKING                                    │
└────────────────────────────────────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│ Step 2: BUILD EXECUTION CONTEXT (Skills Injection!)               │
├────────────────────────────────────────────────────────────────────┤
│ _build_context() in platform/agents/loop.py:330-620               │
│                                                                    │
│ 2a. Load history (15-50 messages based on agent.hierarchy_rank)   │
│ 2b. Load project memory (knowledge base entries)                  │
│ 2c. Load project files (VISION.md, SPECS.md, CLAUDE.md)           │
│ 2d. ★ ENRICH SKILLS ★                                             │
│     → enrich_agent_with_skills(                                   │
│       agent_role="CTO",                                           │
│       mission_description="...",  ← MISSION TEXT TRIGGERS SKILLS  │
│       fallback_skills=agent.skills                                │
│     )                                                              │
│       Result: skills_prompt: str                                  │
│ 2e. Select context tier (L0/L1/L2 based on hierarchy_rank)        │
│ 2f. Load vision (organizers only)                                 │
│                                                                    │
│ Return: ExecutionContext with skills_prompt assembled             │
│ File: platform/agents/executor.py:81-136                          │
└────────────────────────────────────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│ Step 3: ASSEMBLE SYSTEM PROMPT (All Traits Combined)              │
├────────────────────────────────────────────────────────────────────┤
│ _build_system_prompt(ctx) in platform/agents/prompt_builder.py    │
│                                                                    │
│ Compose from (in order):                                          │
│ 1. agent.system_prompt (base instruction)                         │
│ 2. agent.persona (personality traits)                             │
│ 3. agent.motivation (drives and goals)                            │
│ 4. PUA block (Iron Rules + proactivity — tanweai/pua MIT)         │
│ 5. Tool instructions (if tools_enabled)                           │
│ 6. Role-specific block:                                           │
│    • CTO → create_project, create_team, compose_workflow          │
│    • QA → run_e2e_tests (MANDATORY)                               │
│    • Dev → code_read → code_write → build/test cycle              │
│    • Security → SAST scans (bandit, semgrep)                      │
│ 7. Architecture guidelines (from DSI database)                    │
│ 8. Project context (tier-aware: 3-10 memory entries)              │
│ 9. ★ COMPOSED SKILLS ★ (from step 2d)                             │
│ 10. Permissions (delegation, veto, approval)                     │
│                                                                    │
│ Result: full_system_prompt (~8,500-12,000 tokens)                 │
└────────────────────────────────────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│ Step 4: CALL LLM WITH COMPLETE PROMPT                             │
├────────────────────────────────────────────────────────────────────┤
│ LLMClient.chat() in platform/llm/client.py:388-550                │
│                                                                    │
│ POST to provider (Azure OpenAI / NVIDIA / MiniMax):                │
│ {                                                                 │
│   "model": "gpt-5-mini",                                          │
│   "messages": [                                                   │
│     {                                                             │
│       "role": "system",                                           │
│       "content": full_system_prompt  ← 8,500+ TOKENS             │
│     },                                                            │
│     {                                                             │
│       "role": "user",                                             │
│       "content": user_message                                     │
│     }                                                             │
│   ],                                                              │
│   "tools": [tool_schemas],                                        │
│   "temperature": 0.7,                                             │
│   "max_completion_tokens": 4096                                   │
│ }                                                                 │
│                                                                    │
│ Features:                                                         │
│ • Cache (deterministic dedup)                                     │
│ • Multi-provider routing (Thompson Sampling)                      │
│ • RTK compression (saves ~30% tokens)                             │
│ • Circuit breaker (handles provider failures)                     │
│ • Rate limiter (industrial pipeline)                              │
└────────────────────────────────────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────┐
│ Step 5: TOOL EXECUTION LOOP                                        │
├────────────────────────────────────────────────────────────────────┤
│ if llm_resp.tool_calls:                                            │
│   for each tool_call:                                              │
│     result = execute_tool(tool_name, args, ctx)                   │
│     add result to messages                                         │
│   loop back to Step 4 (LLM call with tool results)                │
│ else:                                                              │
│   return final response                                            │
│                                                                    │
│ File: platform/agents/executor.py:716-850                         │
└────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. AGENT IDENTITY (AgentDef)
**File:** `platform/agents/store.py:43-77`

```
name: "Karim Benali"         # Display name
role: "CTO"                   # Role title (triggers role-specific instructions)
persona: "Visionary..."       # Character traits (injected into prompt)
motivation: "Orchestrate..."  # What drives this agent (injected)
skills: [...]                 # Manual skill IDs (fallback)
tools: [...]                  # Tools available (code_read, code_write, etc.)
hierarchy_rank: 0             # 0=CEO, 50=junior (controls context tier)
permissions:                  # can_delegate, can_veto, can_approve
```

### 2. SKILLS INJECTION (The Critical Composition Point)
**File:** `platform/agents/skills_integration.py:89-216`

**Priority:**
1. Azure embeddings (if configured) → embeddings-based matching
2. Context patterns (keywords trigger phase detection) → auto-select skill sets
3. Fallback → manual skills from agent.skills

**Example:**
```
Mission: "Debug the failing deployment"
    ↓
Keyword "debug" detected
    ↓
Phase = "debug"
    ↓
Auto-inject: [
  "systematic-debugging",     # 4-phase root cause
  "debugging-strategies",     # methodology
  "ac-adversarial"            # quality gates
]
    ↓
Load skill content from library
    ↓
Format for tier (L0/L1/L2)
    ↓
Return formatted skills block
```

### 3. CONTEXT TIERS (Control Prompt Verbosity)
**File:** `platform/llm/context_tiers.py`

| Tier | Use Case | Memory Entries | Vision | Context Size |
|------|----------|---|---|---|
| **L0** | Routing only | 0 | No | ~500 chars |
| **L1** | Standard agents (devs, QA) | 3-5 | No | ~3,000 chars |
| **L2** | Organizers (CTO, Product, Architect) | 10 | Yes | ~6,000 chars |

Selected by: `hierarchy_rank + capability_grade`

### 4. ROLE-SPECIFIC INSTRUCTION BLOCKS
**File:** `platform/agents/prompt_builder.py:172-278`

| Role | Special Instructions | Mandatory Tools |
|------|---|---|
| **CTO** | create_project, create_team, create_mission, compose_workflow | memory_search, deep_search, memory_store |
| **QA** | run_e2e_tests (REQUIRED), create_ticket for failures | code_read, run_e2e_tests, create_ticket |
| **Dev** | code_read → code_write → build/test cycle (MANDATORY) | code_read, code_write, code_edit, build, test |
| **Security** | SAST scans (bandit, semgrep, npm audit) | code_read, build, memory_store |
| **Product** | create_feature, create_story (AO traceability) | memory_search, memory_store, jira_search |

### 5. PUA FRAMEWORK (Universal Mandate)
**File:** `platform/agents/pua.py`

**Iron Rules:**
- Proactive: anticipate problems, take initiative
- Urgent: time-aware, respond quickly
- Aggressive: go for it, don't hesitate

**QA-Specific Block:**
```
You are REVIEWER/VALIDATOR — NOT implementer
FORBIDDEN: code_write for implementation
ALLOWED: code_write for TEST files only (test_*.py, *.spec.ts)
MANDATORY: run_e2e_tests() FIRST → read results → create_ticket()
```

---

## The 11-Part System Prompt Assembly

```
1. Base system_prompt (from AgentDef)
   ↓
2. Persona (personality traits)
   ↓
3. Motivation (drives and goals)
   ↓
4. PUA Framework (Iron Rules + proactivity)
   ↓
5. Tool Instructions (function calling rules)
   ↓
6. Role-Specific Block (CTO/QA/Dev/Security/etc.)
   ↓
7. Architecture Guidelines (from DSI database)
   ↓
8. Project Context (tier-aware: 3-10 memory entries)
   ↓
9. ★ COMPOSED SKILLS ★ (auto-injected from mission text)
   ↓
10. Permissions Block (delegation, veto, approval)
    ↓
11. [OPTIONAL] Traceability (for dev roles)
    ↓
FINAL: full_system_prompt (~8,500-12,000 tokens)
```

---

## File Reference

| Component | File Path | Key Function |
|-----------|-----------|---|
| **Agent Identity** | `platform/agents/store.py` | `AgentDef` dataclass |
| **Dispatch** | `platform/agents/loop.py` | `AgentLoop._run_loop()` |
| **Context Builder** | `platform/agents/loop.py` | `_build_context()` ← Skills injected here |
| **Skills Injection** | `platform/agents/skills_integration.py` | `enrich_agent_with_skills()` |
| **Prompt Builder** | `platform/agents/prompt_builder.py` | `_build_system_prompt()` |
| **Executor** | `platform/agents/executor.py` | `AgentExecutor.run()` |
| **LLM Client** | `platform/llm/client.py` | `LLMClient.chat()` |
| **PUA Framework** | `platform/agents/pua.py` | `build_motivation_block()` |
| **Context Tiers** | `platform/llm/context_tiers.py` | `select_tier()` |

---

## Example: Full Prompt for CTO Responding to "Debug the deployment"

```
═══════════════════════════════════════════════════════════════

You are Karim Benali, role: CTO.
Description: Strategic orchestrator and software factory lead.

## Persona & Character
Visionary, decisive, hands-on. I connect teams and ideas.
Speaks French and English. I value clarity and execution.

## Motivation & Drive
Orchestrate the entire factory: balance innovation with stability,
empower teams, deliver on time. Lead by example. Remove blockers.

## PUA Framework (Iron Rules — from tanweai/pua MIT)
[... Iron Rules + L1-L4 pressure model + 5-step debug methodology ...]

## Tools
You have access to: memory_search, memory_store, deep_search,
code_read, list_files, create_project, create_team, create_mission,
compose_workflow, platform_metrics, jira_search, confluence_read

## Memory (MANDATORY)
1. ALWAYS call memory_search() at START
2. ALWAYS call memory_store() at END
3. Store: decisions, tech choices, API contracts, blockers, verdicts, risks

## Deep Search / RLM
For codebase exploration & architectural questions:
ALWAYS call deep_search(query="...") after memory_search

## Software Factory — Rôle CTO
Tu peux:
  • create_project(name, description, vision, factory_type)
  • create_team(team_name, domain, stack, roles=[...])
  • create_mission(name, goal, project_id, workflow_id)
  • compose_workflow(workflow_id, project_id, overrides)

## Architecture & Tech Guidelines
[... 300-600 chars of domain/project-specific rules ...]

## Project Vision
[... Full 3,000 chars from project vision document ...]

## Project Context
[... 10 recent memory entries from project KB ...]

## Skills ★ (AUTO-INJECTED from "Debug" mission)
1. Systematic Debugging
   4-phase root cause analysis: reproduce → isolate → hypothesize → verify
   
2. Debugging Strategies
   Binary search, dynamic analysis, profiling, log analysis
   
3. Adversarial Quality Check
   Think like an attacker: edge cases, error paths, race conditions

## Delegation
You MUST delegate using: [DELEGATE:agent_id] clear task description
Example: [DELEGATE:dev-backend] Investigate failed deployment logs

You CAN veto decisions: [VETO] reason
You CAN approve work: [APPROVE] reason

═══════════════════════════════════════════════════════════════
```

---

## Composition in Action

**Input:**
```
Agent: CTO (hierarchy_rank=0, can_delegate=true)
Mission: "Debug the failing deployment"
```

**Output (what LLM receives):**
1. **Base identity** → Name + role + description
2. **Persona** → Personality traits injected
3. **Motivation** → Drives and ambitions injected
4. **PUA** → Universal Iron Rules framework
5. **CTO tools** → create_project, create_team, etc.
6. **Debug context** → Mission detected → "debug" phase
7. **Auto-injected skills** → systematic-debugging, debugging-strategies, ac-adversarial
8. **Full context** → 10 memory entries + full vision (L2 tier)
9. **Permissions** → Can delegate, can veto, can approve
10. **Result** → Cohesive persona ready to debug effectively

---

## The Key Insight

The **skills_prompt** injected in Step 9 is built from:
- **Phase detection** (keywords in mission text) → context patterns
- **Role eligibility** (agent.role determines skill availability)
- **Fallback skills** (agent.skills from DB as manual override)
- **Context tier** (L0/L1/L2 controls detail level per skill)

This creates **dynamic, mission-aware persona blending** without modifying the base agent definition.

