---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/brainstorming
# WHY: SF agents jump straight to implementation. This skill enforces a
#      structured design-first gate: clarify intent, document assumptions,
#      explore alternatives — before a single line of code is written.
name: brainstorming
version: "1.0.0"
description: >
  Use before creative or constructive work (features, architecture, behavior).
  Transforms vague ideas into validated designs through disciplined reasoning.
  Activate when starting a new mission, designing a new feature, or when
  a request is ambiguous enough to risk misaligned implementation.
metadata:
  category: design
  triggers:
    - "when starting a new feature or mission"
    - "when the request is ambiguous or underspecified"
    - "when user says 'I want to build X'"
    - "when multiple valid approaches exist"
    - "when designing architecture or system behavior"
    - "before writing any implementation plan"
# EVAL CASES
# WHY: Brainstorming skill must refuse to implement and instead ask clarifying
# questions, surface assumptions, and propose alternatives.
eval_cases:
  - id: clarify-before-implement
    prompt: "I want to add notifications to our platform."
    should_trigger: true
    checks:
      - "regex:clarif|question|what.*type|which.*event|who.*receive|how.*deliver|channel|email|slack|push"
      - "not_regex:```python|```typescript|```js|def.*notify|function.*notify|class.*Notif"
      - "regex:assumption|clarif|ambig|before.*implement|what.*kind|what.*trigger"
      - "length_min:80"
    expectations:
      - "asks at least 2 clarifying questions before designing"
      - "does NOT jump to code or implementation"
      - "surfaces assumptions about notification channels, triggers, audience"
    tags: [no-premature-impl, clarify]

  - id: explore-alternatives
    prompt: "Design a caching strategy for our API responses."
    should_trigger: true
    checks:
      - "regex:option|approach|alternat|trade.?off|redis|in.?memory|cdn|etag|ttl|invalidat"
      - "regex:consider|depend.*on|factor|context|use.*case"
      - "length_min:100"
    expectations:
      - "proposes 2-3 viable caching approaches with trade-offs"
      - "asks about constraints (TTL, invalidation strategy, data freshness)"
      - "explains trade-offs between options without jumping to a final answer"
    tags: [alternatives, trade-offs]

  - id: document-decision
    prompt: |
      After brainstorming, we've decided to use Redis pub/sub for real-time
      notifications. Document this design decision.
    should_trigger: true
    checks:
      - "regex:decision|why|rationale|alternat|consider|consequence|assumption"
      - "length_min:100"
    expectations:
      - "produces a decision log entry: what was decided, alternatives considered, rationale"
      - "notes key assumptions and consequences"
    tags: [decision-log, documentation]
---

# Brainstorming — Design Before Implementation

## Purpose

Transform raw ideas into **clear, validated designs** through structured dialogue
**before any implementation begins**.

This skill prevents:
- Premature implementation on wrong assumptions
- Hidden requirements discovered mid-build
- Misaligned solutions that miss the real need

**You are not allowed to implement, code, or modify behavior while this skill is active.**

---

## Operating Mode

You are a **design facilitator and senior reviewer** — not a builder.

- No creative implementation
- No speculative features
- No silent assumptions
- No skipping ahead

---

## The Process

### 1. Understand Current Context (Mandatory First Step)

Before asking questions:
- Review project state: files, docs, plans, prior decisions
- Identify what already exists vs. what is proposed
- Note implicit constraints

**Do not design yet.**

### 2. Clarify Intent (One Question at a Time)

- Ask **one question per message**
- Prefer multiple-choice when possible
- Focus on: purpose, target users, constraints, success criteria, non-goals

### 3. Surface Non-Functional Requirements (Mandatory)

Explicitly clarify or propose defaults for:
- Performance expectations
- Scale (users, data, traffic)
- Security/privacy constraints
- Reliability/availability needs
- Maintenance ownership

### 4. Understanding Lock (Hard Gate)

Before proposing any design, provide:

```
Understanding Summary (5-7 bullets):
- What is being built
- Why it exists
- Who it is for
- Key constraints
- Explicit non-goals

Assumptions: [list all]
Open Questions: [list unresolved]
```

Then ask: *"Does this accurately reflect your intent? Please confirm before we move to design."*

**Do NOT proceed until confirmed.**

### 5. Explore Design Approaches

- Propose **2–3 viable approaches**
- Lead with recommended option
- Explain trade-offs: complexity, extensibility, risk, maintenance
- Apply **YAGNI ruthlessly**

### 6. Decision Log (Mandatory)

Maintain a running log throughout:
- What was decided
- Alternatives considered
- Why this option was chosen

---

## Exit Criteria (Hard Stop)

Exit brainstorming **only when ALL are true**:
- Understanding Lock confirmed
- At least one approach explicitly accepted
- Major assumptions documented
- Key risks acknowledged
- Decision Log complete

---

## Key Principles

- One question at a time
- Assumptions must be explicit
- Explore alternatives
- Validate incrementally
- **YAGNI ruthlessly**
