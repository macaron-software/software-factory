---
name: ddd-tactical-patterns
version: 1.0.0
description: Apply DDD tactical patterns in code using entities, value objects, aggregates,
  repositories, and domain events with explicit invariants.
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: self'
  triggers:
  - designing aggregate boundaries and invariants
eval_cases:
- id: ddd-tactical-patterns-approach
  prompt: How should I approach ddd tactical patterns for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on ddd tactical patterns
  tags:
  - ddd
- id: ddd-tactical-patterns-best-practices
  prompt: What are the key best practices and pitfalls for ddd tactical patterns?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for ddd tactical patterns
  tags:
  - ddd
  - best-practices
- id: ddd-tactical-patterns-antipatterns
  prompt: What are the most common mistakes to avoid with ddd tactical patterns?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - ddd
  - antipatterns
---
# ddd-tactical-patterns

# DDD Tactical Patterns

## Use this skill when

- Translating domain rules into code structures.
- Designing aggregate boundaries and invariants.
- Refactoring an anemic model into behavior-rich domain objects.
- Defining repository contracts and domain event boundaries.

## Do not use this skill when

- You are still defining strategic boundaries.
- The task is only API documentation or UI layout.
- Full DDD complexity is not justified.

## Instructions

1. Identify invariants first and design aggregates around them.
2. Model immutable value objects for validated concepts.
3. Keep domain behavior in domain objects, not controllers.
4. Emit domain events for meaningful state transitions.
5. Keep repositories at aggregate root boundaries.

If detailed checklists are needed, open `references/tactical-checklist.md`.

## Example

```typescript
class Order {
  private status: "draft" | "submitted" = "draft";

  submit(itemsCount: number): void {
    if (itemsCount === 0) throw new Error("Order cannot be submitted empty");
    if (this.status !== "draft") throw new Error("Order already submitted");
    this.status = "submitted";
  }
}
```

## Limitations

- This skill does not define deployment architecture.
- It does not choose databases or transport protocols.
- It should be paired with testing patterns for invariant coverage.
