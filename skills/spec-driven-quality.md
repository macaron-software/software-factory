---
# SOURCE: GitHub spec-kit (MIT)
# https://github.com/github/spec-kit
#
# WHY WE PORTED THIS:
#   SF agents jump straight from user request → plan → code. This skips three
#   quality gates that spec-kit formalises:
#     1. Clarify   — surface ambiguities *before* planning (saves rework)
#     2. Checklist — validate requirements completeness like "unit tests for English"
#     3. Analyze   — cross-artifact consistency (spec ↔ plan ↔ tasks coherence)
#   We also port the Constitution concept: project governing principles as a
#   first-class artifact that anchors all subsequent planning decisions.
#
# WHAT WE KEPT:
#   - Constitution structure (governing principles template)
#   - Clarify protocol (question types, disambiguation workflow)
#   - Checklist dimensions (completeness, clarity, consistency, testability, feasibility)
#   - Analyze cross-artifact checks (spec ↔ plan ↔ tasks)
#
# WHAT WE DROPPED:
#   - `specify` and `plan` slash commands (SF uses missions + SAFe lifecycle)
#   - `implement` command (SF has agent loops with tool execution)
#   - `specify init` CLI scaffolding (redundant with `sf` CLI)
#   - Multi-framework/language detection logic (SF is Python-centric)
#   - `.claude/commands/` file generation (SF uses skills/ system)
#
# ADAPTATIONS:
#   - Constitution maps to per-project PRINCIPLES.md (fits SF project config)
#   - Checklist runs inline (not as a separate slash command file)
#   - Analyze targets SF mission artefacts: user_story ↔ plan ↔ task_list
#   - All steps reference SF concepts (mission, backlog item, agent role)
#
# LICENSE: MIT — free to adapt with attribution

name: spec-driven-quality
version: "1.1.0"
description: >
  Pre-code quality gates for SF agents based on spec-kit (GitHub, MIT).
  Activate when: starting a new mission, refining a backlog item, or reviewing
  a plan before agent execution. Provides four structured steps:
    1. constitution — capture project governing principles once
    2. clarify      — surface ambiguities before planning
    3. checklist    — validate requirements like "unit tests for English"
    4. analyze      — cross-artifact consistency (spec ↔ plan ↔ tasks)

eval_cases:
  - id: clarify-ambiguous-feature
    prompt: "Build a photo album feature — albums grouped by date, drag-and-drop reorder."
    should_trigger: true
    checks:
      - "regex:clarif|question|ambig|missing|unclear|assumption"
      - "regex:auth|mobile|offline|drag|touch|keyboard|max|limit|pagina"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - "runs Clarify step: identifies at least 2 ambiguities (auth model? touch support? pagination?)"
      - "runs Checklist: drag-and-drop needs acceptance criteria (touch? keyboard nav?)"
      - "does NOT jump straight to implementation"
    tags: [clarify, checklist]

  - id: clarify-integration-feature
    prompt: "Add Slack notifications when an agent mission completes."
    should_trigger: true
    checks:
      - "regex:clarif|question|which event|opt-in|opt-out|per-user|per-project|webhook|token"
      - "regex:rate.?limit|delivery|retry|fail|down|unavailab"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - "asks clarifying questions before designing the feature (which events? opt-in/out? scope?)"
      - "flags non-functional requirements: message delivery guarantees, rate limits"
      - "identifies a missing failure scenario: what happens if Slack is unavailable?"
    tags: [clarify, non-functional]

  - id: clarify-migration
    prompt: "Migrate the database from SQLite to Postgres."
    should_trigger: true
    checks:
      - "regex:clarif|question|zero.?downtime|rollback|data.*volume|integrit"
      - "regex:success.*criteri|latency|baseline|test|verif|validat"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - "Clarify step asks: zero-downtime requirement? data volume? rollback plan?"
      - "Checklist flags missing success criteria (latency baseline, data integrity check)"
    tags: [clarify, migration]
---

# Spec-Driven Quality Skill

Quality gates to run **before** any agent starts coding. Prevents costly rework
by catching ambiguity, gaps, and contradictions early.

Use in order: **Constitution → Clarify → Checklist → Analyze**. Skip steps that
don't apply (e.g., skip Constitution if PRINCIPLES.md already exists).

---

## Step 1 — Constitution (once per project)

> "What are the governing principles that constrain every decision in this project?"

The Constitution is a PRINCIPLES.md at the project root. It anchors all
subsequent planning so agents don't contradict core decisions mid-implementation.

### When to run
- New SF project (no PRINCIPLES.md yet)
- Major scope change (new tech stack, new team, architectural pivot)
- When plans keep contradicting each other

### Structure of PRINCIPLES.md

```markdown
# Project Principles

## Tech Stack Constraints
- Language: Python 3.12+
- Framework: FastAPI (no Django, no Flask)
- DB: SQLite for dev / Postgres for prod
- Forbidden: Redis, Celery (use platform task queue instead)

## Code Quality Rules
- No external API calls without retry + timeout
- All new endpoints need at least one integration test
- Type annotations on all public functions

## UX Constraints
- API-first: all features available via REST before any UI
- Latency budget: P99 < 500ms for all synchronous endpoints

## Security Constraints
- No secrets in code or commit messages
- All user inputs validated with Pydantic
- Auth required on all non-public endpoints

## Architectural Decisions
- Agents are stateless — no in-memory state between calls
- All persistence via DB adapter (no direct sqlite3 imports in business logic)
```

### Agent instructions
When generating or reviewing a plan, check it against PRINCIPLES.md first.
If a plan violates a principle, surface the conflict explicitly before proceeding.

---

## Step 2 — Clarify

> "What is underspecified? What would cause a different implementation if assumed differently?"

Run Clarify **before** generating a plan. Its job: transform a vague request into
a spec with no load-bearing ambiguities.

### Protocol

1. **Read the request** — identify every noun, action, and constraint
2. **Classify each ambiguity** by type (see table below)
3. **Ask targeted questions** — one per ambiguity, grouped by priority
4. **Propose defaults** — for each question, offer a sensible default so the
   user can confirm fast rather than drafting answers from scratch

### Ambiguity taxonomy

| Type | Question pattern | Example |
|------|-----------------|---------|
| **Scope** | What's in / out of this change? | "notifications" — push? email? in-app? |
| **Actor** | Who performs this action? | "admin can delete" — which admin role? |
| **Trigger** | When does this happen? | "auto-archive" — after how long? |
| **Volume** | What scale must this handle? | "large files" — >10MB? >1GB? |
| **Edge case** | What happens when X fails? | "if payment fails" — retry? cancel? notify? |
| **Non-functional** | Latency / availability / security requirement? | "real-time" — <100ms? <1s? |
| **Integration** | Which external system? Which API version? | "send to Slack" — which channel? bot or webhook? |
| **Constraint** | Is there a tech or budget constraint? | "use existing infra" — no new services? |

### Output format

```markdown
## Clarification Questions

**High priority** (different answers → different architecture)
1. [Scope] Should this work offline, or is a network connection required?
   → Default: network required (simpler; change if offline is a hard requirement)
2. [Volume] What's the expected number of records per user?
   → Default: <10,000 (SQLite; if >1M, switch to Postgres)

**Medium priority** (different answers → different implementation)
3. [Edge case] What happens if the background job fails mid-way?
   → Default: retry 3× then mark as failed + alert

**Low priority** (can decide later)
4. [Non-functional] Is there a latency budget for this endpoint?
   → Default: P99 < 500ms (matches existing platform budget)
```

### SF-specific checks
- Does the request mention an agent role? Confirm which role handles it.
- Does it touch the DB? Ask: new table, new column, or view?
- Does it cross agent boundaries (A2A)? Ask: sync call or async bus event?

---

## Step 3 — Checklist

> "Are the requirements complete, clear, consistent, testable, and feasible?"

Run Checklist **after** Clarify, **before** generating tasks. It's the
"unit tests for English": each dimension is a pass/fail gate.

### Five dimensions

#### 1. Completeness
Every scenario has a defined outcome, including unhappy paths.

- ✅ Happy path described
- ✅ Error / failure path described
- ✅ Empty state described (no data, first use)
- ✅ Boundary conditions stated (min/max values, limits)
- ✅ Roles and permissions covered

Flag if missing: _"Spec describes the success case but not what happens when X fails."_

#### 2. Clarity
No ambiguous language that two developers would interpret differently.

Vague terms that always need precision:
- "fast", "real-time", "large", "small" → add numbers
- "user", "admin", "system" → specify which role/actor
- "should", "may", "ideally" → replace with MUST / MUST NOT / MAY (RFC 2119)
- "etc.", "and so on", "similar" → enumerate explicitly

#### 3. Consistency
No contradictions within or between artefacts.

- ✅ Same term used for the same concept throughout
- ✅ No conflicting constraints (e.g., "stateless" + "in-memory cache")
- ✅ Roles match what's defined in the Constitution / team YAML
- ✅ Tech choices match PRINCIPLES.md stack constraints

#### 4. Testability
Every requirement can be verified with a concrete test.

Ask: "How would I write a test that proves this requirement is met?"
- ✅ Acceptance criteria stated in observable terms (not "feels fast")
- ✅ Each requirement has at least one verifiable assertion
- ✅ Non-functional requirements have measurable thresholds

#### 5. Feasibility
The requirement can be implemented within the project's constraints.

- ✅ No tech stack violations (check against PRINCIPLES.md)
- ✅ No dependency on unavailable external services
- ✅ Estimated effort is realistic for a single mission scope
- ✅ No security or compliance showstoppers

### Checklist output format

```markdown
## Requirements Checklist

| Dimension     | Status | Notes |
|---------------|--------|-------|
| Completeness  | ⚠️ WARN | Missing: error path when DB write fails |
| Clarity       | ✅ PASS | All terms well-defined |
| Consistency   | ❌ FAIL | "stateless agent" + "in-memory session" contradict each other |
| Testability   | ⚠️ WARN | "fast response" needs a latency threshold |
| Feasibility   | ✅ PASS | Within platform constraints |

**Blockers (must fix before planning):** Consistency ❌
**Warnings (fix or accept risk):** Completeness, Testability
```

Stop and fix all ❌ FAIL items before proceeding to plan. ⚠️ WARN items can
proceed if explicitly acknowledged.

---

## Step 4 — Analyze

> "Do the spec, plan, and task list agree with each other?"

Run Analyze **after** tasks are generated, **before** agent execution starts.
Catches drift introduced during the planning → task decomposition step.

### What to check

#### Spec ↔ Plan alignment
- Every requirement in the spec has at least one plan item that addresses it
- The plan introduces no new requirements not in the spec
- Tech stack choices in the plan match PRINCIPLES.md

#### Plan ↔ Tasks alignment
- Every plan item has at least one task
- Tasks collectively cover all plan items (no orphan plan items)
- No task contradicts its parent plan item
- Task dependencies form a DAG (no cycles)

#### Tasks ↔ Spec traceability
- Each task can be traced back to a spec requirement
- No "ghost tasks" (tasks with no spec origin — signals scope creep)
- Acceptance criteria from spec are reflected in task done-criteria

### Coverage matrix

Build a simple matrix to surface gaps:

```
Requirement R1 → Plan item P2 → Tasks T4, T5  ✅
Requirement R2 → Plan item P3 → Tasks T6      ✅
Requirement R3 → (no plan item)               ❌ GAP
Plan item P4  → Tasks T7, T8                  (no requirement origin) ⚠️ SCOPE CREEP
```

### Analyze output format

```markdown
## Cross-Artifact Analysis

**Coverage gaps (requirements with no plan/task coverage):**
- R3: "User can export data as CSV" — not addressed in plan

**Scope creep (plan/tasks with no requirement origin):**
- P4 → T7, T8: "Add Redis caching layer" — not in spec, not in Constitution

**Contradictions:**
- Plan says "use async queue" but Task T3 calls the endpoint synchronously

**Missing error handling:**
- Spec mentions "retry on failure" but no retry task exists

**Verdict:** ⛔ Fix 2 gaps + 1 contradiction before proceeding
```

---

## Integration with SF Missions

In SF, run these steps at the following mission lifecycle stages:

```
Mission created (user story received)
    │
    ▼
[Constitution check] — does plan violate PRINCIPLES.md?
    │
    ▼
[Clarify] — ask questions, get defaults confirmed
    │
    ▼
[Checklist] — validate requirements quality
    │
    ▼
Mission Plan generated
    │
    ▼
Tasks generated
    │
    ▼
[Analyze] — cross-artifact consistency check
    │
    ▼
Agent execution starts (no surprises)
```

Agents with the `architect` or `product_manager` role should run these steps
automatically when `spec-driven-quality` module is enabled. Other roles (dev,
qa, security) should run Checklist and Analyze as reviewers.

---

## Quick Reference

| Step | When | Key question | Output |
|------|------|-------------|--------|
| **Constitution** | Once per project | What constrains every decision? | `PRINCIPLES.md` |
| **Clarify** | Before planning | What's ambiguous? | Prioritised Q&A with defaults |
| **Checklist** | Before tasks | Are requirements quality-complete? | Pass/fail/warn per dimension |
| **Analyze** | Before execution | Do spec/plan/tasks agree? | Coverage matrix + gap list |
