---
name: ux-laws
version: "1.0.0"
description: >
  Applies the 30 Laws of UX (Jon Yablonski, MIT — https://lawsofux.com) to user story
  writing, UX audit, and design critique. Triggered when agents write acceptance criteria,
  review UI proposals, or evaluate user flows against cognitive science principles.
metadata:
  category: design
  source: "https://lawsofux.com — Jon Yablonski (MIT)"
  integrated_by: "macaron-software/software-factory"
  integration_rationale: >
    Evidence-based cognitive laws reduce the subjective gap in UX review.
    Applied in 3 contexts: (1) US acceptance criteria — agents embed measurable
    cognitive constraints; (2) UX audit — 30-law checklist replaces opinion-based
    review; (3) design critique — agents explain WHY a proposal violates a law,
    not just THAT it does.
  triggers:
    - "when writing user stories or acceptance criteria"
    - "when reviewing or auditing a UI/UX"
    - "when critiquing a design proposal"
    - "when doing a UX heuristic evaluation"
    - "when discussing cognitive load or user mental models"
    - "when agent must evaluate if a UI is too complex"
    - "when defining performance SLAs for user-facing interactions"
---

# Laws of UX — Agent Application Guide

Source: https://lawsofux.com (Jon Yablonski, MIT License)
Integrated into SF skills for US writing, UX audit, and design critique.

---

## CONTEXT A — Writing User Stories and Acceptance Criteria

When writing US, use these laws to make acceptance criteria **measurable and cognitive-science-backed**.

### Hick's Law
*The time to make a decision increases with the number and complexity of choices.*
- **Apply when**: designing navigation menus, forms with options, dashboards
- **AC pattern**: "Given N choices are presented, the user reaches a decision in under X seconds"
- **Rule**: max 5–7 primary actions per screen; progressively disclose the rest
- **Violation example**: "As a user I can configure 15 settings on the first screen" → violates Hick's

### Miller's Law
*The average person can only keep 7 (±2) items in working memory.*
- **Apply when**: list views, multi-step forms, navigation trees
- **AC pattern**: "No single view presents more than 7 items without pagination or grouping"
- **Rule**: chunk related items; use progressive disclosure beyond 7
- **Violation example**: flat list of 20 filters without grouping

### Cognitive Load
*The amount of mental resources needed to understand and interact with an interface.*
- **Apply when**: any story that adds a new UI element or step to an existing flow
- **AC pattern**: "The feature does not add a new required input field to an existing flow"
- **Rule**: each story must reduce, not increase, the cognitive load of the overall flow
- **Question to ask**: "What decision or memory burden does this remove from the user?"

### Doherty Threshold
*Productivity soars when computer+user interact at <400ms — neither waits on the other.*
- **Apply when**: any user action that triggers a backend call
- **AC pattern**: "The page responds to user action within 400ms (visual feedback or result)"
- **Rule**: if backend takes >400ms, show immediate optimistic feedback
- **SLA standard**: 0–100ms = instant, 100–400ms = fast, 400ms–1s = acceptable with indicator, >1s = loading state required

### Goal-Gradient Effect
*The tendency to approach a goal increases with proximity to the goal.*
- **Apply when**: multi-step flows, onboarding, long forms
- **AC pattern**: "A progress indicator shows the user's position in the X-step flow"
- **Rule**: always show how close the user is to completion; break long tasks into visible milestones

### Peak-End Rule
*People judge an experience based on its peak and its ending, not the average.*
- **Apply when**: checkout flows, onboarding sequences, error recovery, form submission
- **AC pattern**: "On form submission, the user sees a clear success confirmation with next step"
- **Rule**: design the best moment (peak) and a clean closing (end); the middle is less important
- **Violation example**: 8-step form that ends with "Your request was submitted" (flat ending)

### Pareto Principle (80/20)
*Roughly 80% of effects come from 20% of causes.*
- **Apply when**: prioritizing backlog, scoping US, defining MVP
- **Rule**: identify the 20% of features that deliver 80% of user value; deprioritize the rest
- **AC pattern**: N/A — use this as a scoping filter, not a UI constraint

### Tesler's Law (Law of Conservation of Complexity)
*For any system, there is a certain amount of complexity that cannot be reduced.*
- **Apply when**: simplifying flows, debating where to hide complexity
- **Rule**: complexity cannot be destroyed — only moved. Move it to the system (backend, defaults) not the user
- **Question**: "Which side — user or system — is better equipped to handle this complexity?"

### Occam's Razor
*Among competing solutions, the one with fewest assumptions should be selected.*
- **Apply when**: choosing between implementation approaches, designing feature scope
- **Rule**: the simplest solution that meets the AC is correct; don't over-engineer
- **AC pattern**: "The feature can be used without reading documentation"

### Parkinson's Law
*Any task inflates to fill the available time.*
- **Apply when**: writing stories, sprint planning
- **Rule**: constrain story scope explicitly. An unbounded story will expand to fill the sprint.
- **Tactic**: add explicit exclusion lines to US: "OUT OF SCOPE: X, Y, Z"

### Zeigarnik Effect
*People remember uncompleted or interrupted tasks better than completed tasks.*
- **Apply when**: long flows, background tasks, async operations
- **AC pattern**: "If the user leaves a multi-step flow, their progress is saved and a reminder is shown on return"
- **Rule**: use saved-state and re-engagement prompts to leverage the Zeigarnik memory effect

---

## CONTEXT B — UX Audit Checklist (30 Laws)

When auditing a UI, check each applicable law. Report: **Law | Status (OK/FAIL/NA) | Evidence | Recommendation**.

### Perception & Grouping (Gestalt)
| Law | What to check |
|-----|--------------|
| Law of Proximity | Related items are visually close; unrelated items have whitespace separation |
| Law of Common Region | Related items share a container/border |
| Law of Similarity | Items with similar function look similar (color, shape, size) |
| Law of Uniform Connectedness | Connected items (lines, borders) imply relationship |
| Law of Prägnanz | Complex graphics simplify to their most readable form |

### Attention & Memory
| Law | What to check |
|-----|--------------|
| Miller's Law | No list/menu/set exceeds 7 (±2) ungrouped items |
| Von Restorff Effect | The primary CTA is visually distinct from secondary actions |
| Serial Position Effect | Most important items are first or last in lists/navs |
| Selective Attention | Non-critical information doesn't compete with the main task |
| Working Memory | Users don't need to remember info from one screen to use another |
| Mental Model | The UI matches what users already know from other apps (Jakob's Law) |

### Decision & Interaction
| Law | What to check |
|-----|--------------|
| Hick's Law | Primary options ≤7; secondary options are hidden until needed |
| Fitts's Law | Click targets are large and close to the natural cursor path |
| Cognitive Load | Each page asks the user to do exactly one thing |
| Choice Overload | Dropdowns/filters have a sensible default; options are ≤10 visible |
| Flow | The interaction sequence is uninterrupted; no dead-ends or U-turns |

### Time & Performance
| Law | What to check |
|-----|--------------|
| Doherty Threshold | Every user action gets feedback in <400ms |
| Goal-Gradient Effect | Progress is shown in multi-step flows |
| Peak-End Rule | The key moment and the closing confirmation are well-designed |
| Zeigarnik Effect | Long/async tasks show state on return |

### Cognitive Principles
| Law | What to check |
|-----|--------------|
| Aesthetic-Usability Effect | The UI is visually clean (users perceive prettier = more usable) |
| Chunking | Information is grouped into meaningful units |
| Cognitive Bias | No dark patterns that exploit anchoring, scarcity, or social proof |
| Paradox of Active User | Core actions require no manual reading |
| Postel's Law | Input: liberal (accept multiple formats); Output: consistent and strict |
| Tesler's Law | Complexity is hidden from users, not removed from the system |

### Strategy
| Law | What to check |
|-----|--------------|
| Jakob's Law | Conventions from other apps are respected (save = floppy icon, etc.) |
| Occam's Razor | No feature exists without a clear user need |
| Pareto Principle | The 20% of features used most are the most prominent |
| Parkinson's Law | Feature scope is explicit; no scope creep in the stories that built it |

---

## CONTEXT C — Design Critique Template

When an agent critiques a design proposal, structure output as:

```
## UX Laws Critique — [Feature Name]

### Violations (must fix)
- **[Law Name]**: [What is violated] → [Recommended fix]

### Warnings (should fix)
- **[Law Name]**: [Potential issue] → [Suggested improvement]

### Compliant (notable strengths)
- **[Law Name]**: [What the design does right]

### Net Assessment
Cognitive load: [Low/Medium/High]
Decision complexity: [Low/Medium/High — Hick's score: N options at primary level]
Memory demand: [Low/Medium/High — Miller's score: N ungrouped items]
```

---

## Quick Reference — Law to Law Category

| Category | Laws |
|----------|------|
| **Scope / Prioritization** | Pareto, Occam's Razor, Parkinson's Law, Tesler's |
| **Decision UX** | Hick's, Choice Overload, Cognitive Load |
| **Memory** | Miller's, Working Memory, Chunking, Zeigarnik |
| **Perception** | Gestalt × 5 (Proximity, Common Region, Similarity, Connectedness, Prägnanz) |
| **Interaction** | Fitts's, Doherty Threshold, Flow |
| **Emotional / Narrative** | Peak-End Rule, Aesthetic-Usability Effect, Goal-Gradient, Von Restorff |
| **Mental Models** | Jakob's Law, Mental Model, Paradox of Active User |
| **System Design** | Postel's Law, Tesler's Law |
