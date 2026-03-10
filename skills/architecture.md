---
name: architecture
version: 1.0.0
description: Architectural decision-making framework. Requirements analysis, trade-off
  evaluation, ADR documentation. Use when making architecture decisions or analyzing
  system design.
metadata:
  category: architecture
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - making architecture decisions or analyzing system design
eval_cases:
- id: architecture-approach
  prompt: How should I approach architecture for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on architecture
  tags:
  - architecture
- id: architecture-best-practices
  prompt: What are the key best practices and pitfalls for architecture?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for architecture
  tags:
  - architecture
  - best-practices
- id: architecture-antipatterns
  prompt: What are the most common mistakes to avoid with architecture?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - architecture
  - antipatterns
---
# architecture

# Architecture Decision Framework

> "Requirements drive architecture. Trade-offs inform decisions. ADRs capture rationale."

## 🎯 Selective Reading Rule

**Read ONLY files relevant to the request!** Check the content map, find what you need.

| File | Description | When to Read |
|------|-------------|--------------|
| `context-discovery.md` | Questions to ask, project classification | Starting architecture design |
| `trade-off-analysis.md` | ADR templates, trade-off framework | Documenting decisions |
| `pattern-selection.md` | Decision trees, anti-patterns | Choosing patterns |
| `examples.md` | MVP, SaaS, Enterprise examples | Reference implementations |
| `patterns-reference.md` | Quick lookup for patterns | Pattern comparison |

---

## 🔗 Related Skills

| Skill | Use For |
|-------|---------|
| `@[skills/database-design]` | Database schema design |
| `@[skills/api-patterns]` | API design patterns |
| `@[skills/deployment-procedures]` | Deployment architecture |

---

## Core Principle

**"Simplicity is the ultimate sophistication."**

- Start simple
- Add complexity ONLY when proven necessary
- You can always add patterns later
- Removing complexity is MUCH harder than adding it

---

## Validation Checklist

Before finalizing architecture:

- [ ] Requirements clearly understood
- [ ] Constraints identified
- [ ] Each decision has trade-off analysis
- [ ] Simpler alternatives considered
- [ ] ADRs written for significant decisions
- [ ] Team expertise matches chosen patterns

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
