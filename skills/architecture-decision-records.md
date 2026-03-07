---
# SOURCE: antigravity-awesome-skills (MIT)
# https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/architecture-decision-records
# WHY: We have a dedicated "ADR Architect" agent (Raphaël Dumont). This skill
#      gives it the templates, lifecycle, and best practices for writing and
#      maintaining Architecture Decision Records.
name: architecture-decision-records
version: "1.0.0"
description: >
  Write and maintain Architecture Decision Records (ADRs) following best practices.
  Use when documenting significant technical decisions, reviewing past architectural
  choices, or establishing a decision-making process for the team.
metadata:
  category: development
  triggers:
    - "when documenting a significant technical decision"
    - "when choosing between technology options"
    - "when a user asks to write an ADR"
    - "when recording design trade-offs for future reference"
    - "when onboarding new team members to past decisions"
    - "when reviewing or superseding an existing ADR"
# EVAL CASES
eval_cases:
  - id: write-adr-database
    prompt: |
      Write an ADR for choosing PostgreSQL over MongoDB for a multi-tenant
      SaaS platform that handles financial transactions and needs ACID compliance.
    should_trigger: true
    checks:
      - "regex:ADR|Status.*Accept|Context|Decision|Consequence"
      - "regex:ACID|transaction|trade.?off|consider|MongoDB|PostgreSQL|relational"
      - "regex:positive|negative|risk|consequence|rationale|because"
      - "length_min:200"
      - "no_placeholder"
    expectations:
      - "produces a properly structured ADR with Status, Context, Decision, Consequences"
      - "documents trade-offs explicitly: pros and cons of each option"
      - "records the rationale for PostgreSQL (ACID, financial data)"
    tags: [adr-template, database-decision]

  - id: adr-lifecycle
    prompt: |
      We adopted Redis for sessions in ADR-0003 two years ago. We now want
      to switch to database-backed sessions for simplicity. How should we
      handle the existing ADR?
    should_trigger: true
    checks:
      - "regex:supersede|deprecat|status|Accepted|new.*ADR|ADR.*0003|link|refer"
      - "regex:lesson|history|previous.*decision|context.*changed|evolution"
      - "length_min:80"
    expectations:
      - "recommends creating a new ADR that supersedes ADR-0003"
      - "explains the ADR lifecycle: Proposed → Accepted → Superseded"
      - "notes that old ADRs should be kept (never deleted) for historical context"
    tags: [lifecycle, superseded, history]

  - id: when-to-write-adr
    prompt: |
      Our team debates when to write ADRs. Should we write one for:
      (A) switching from npm to pnpm, (B) adopting event sourcing for orders,
      (C) fixing a typo in a config file?
    should_trigger: true
    checks:
      - "regex:significant|architectur|irreversib|impact|scope|team|long.*term"
      - "regex:B|event.*sourc|yes.*B|B.*yes|ADR.*B"
      - "not_regex:yes.*A.*C|all three|A.*and.*C"
      - "length_min:60"
    expectations:
      - "recommends ADR only for (B) event sourcing — architectural, significant, long-term impact"
      - "explains: ADRs for decisions that are hard to reverse or affect the whole team"
      - "(A) pnpm switch is borderline — may warrant a brief note, not a full ADR"
    tags: [when-to-write, decision-criteria]
---

# Architecture Decision Records (ADRs)

Capture the **context and rationale** behind significant technical decisions
so future team members understand *why*, not just *what*.

## When to Write an ADR

| Write ADR | Skip ADR |
|-----------|----------|
| New framework/language adoption | Minor version upgrades |
| Database technology choice | Bug fixes |
| API design patterns | Implementation details |
| Security architecture | Routine maintenance |
| Integration patterns | Configuration changes |
| Major refactoring strategy | Style/formatting choices |

**Rule of thumb**: If the decision is hard to reverse, affects the whole team,
or someone will ask "why did we do this?" in 6 months → write an ADR.

---

## ADR Lifecycle

```
Proposed → Accepted → Deprecated → Superseded
              ↓
           Rejected
```

**Never delete ADRs** — keep rejected and superseded ones for history.
Update status, link to new ADR, add lessons learned.

---

## Template: Standard ADR (MADR Format)

```markdown
# ADR-NNNN: [Short Title]

## Status

[Proposed | Accepted | Rejected | Deprecated | Superseded by ADR-MMMM]

## Date

YYYY-MM-DD

## Context

[What is the issue? What forces/constraints led to this decision?
Include scale, team expertise, deadlines, existing systems.]

## Decision Drivers

* [Most important factor]
* [Second factor]
* [...]

## Considered Options

### Option 1: [Name]
- Pros: ...
- Cons: ...

### Option 2: [Name]
- Pros: ...
- Cons: ...

## Decision

We will use **[chosen option]**.

## Rationale

[Why this option was chosen over the alternatives.]

## Consequences

### Positive
- [Benefit 1]

### Negative
- [Drawback 1]

### Risks & Mitigations
- Risk: [X] → Mitigation: [Y]

## Related Decisions
- ADR-NNNN: [Related decision]

## References
- [Link or doc]
```

---

## Template: Lightweight ADR (for smaller decisions)

```markdown
# ADR-NNNN: [Title]

**Status**: Accepted | **Date**: YYYY-MM-DD

## Context
[1-2 sentences: why did we need to decide?]

## Decision
[What was decided, in one sentence.]

## Consequences
Good: [main benefit]
Bad: [main trade-off]
Mitigation: [how we handle the downside]
```

---

## Template: Y-Statement Format (ultra-compact)

```markdown
In the context of **[situation]**,
facing **[concern/force]**,
we decided for **[option]**
and against **[other options]**,
to achieve **[quality/goal]**,
accepting that **[downside]**.
```

---

## ADR Supersession Example

When superseding an old ADR:
1. Add `## Status: Superseded by ADR-MMMM` to the old ADR
2. Add a `## Lessons Learned` section explaining what changed
3. In the new ADR, reference the old one in Context

---

## SF ADR Conventions

- File: `docs/adr/ADR-NNNN-short-title.md`
- Numbering: sequential, never reuse numbers
- One decision per ADR (split large decisions)
- Link ADRs to the missions/backlog items they came from
