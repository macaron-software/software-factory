---
# SOURCE: antigravity-awesome-skills (MIT) — skills/software-architecture/SKILL.md
name: software-architecture
version: "1.0.0"
description: >
  Guide for quality-focused software architecture based on Clean Architecture and DDD.
  Use when writing, designing, or reviewing code in any software development context.
metadata:
  category: architecture
  triggers:
    - "when designing software architecture"
    - "when implementing Clean Architecture or DDD"
    - "when reviewing code structure and boundaries"
    - "when avoiding NIH syndrome or over-engineering"
eval_cases:
  - id: early-return-naming
    prompt: "Review this function that uses deep nesting. How should it be improved?"
    should_trigger: true
    checks:
      - "regex:early.return"
      - "regex:nesting|nested"
      - "length_min:100"
      - "no_placeholder"
    expectations:
      - "Suggests early returns to reduce nesting"
    tags: [architecture, clean-code]
  - id: library-first
    prompt: "I need to implement retry logic for HTTP calls in my service."
    should_trigger: true
    checks:
      - "regex:librar|existing|package|npm|pip"
      - "regex:cockatiel|tenacity|retry|backoff"
      - "length_min:80"
      - "no_placeholder"
    expectations:
      - "Recommends existing library over custom implementation"
    tags: [architecture, dependencies]
  - id: naming-convention
    prompt: "I have a file called utils.js with 60 helper functions. Is that OK?"
    should_trigger: true
    checks:
      - "regex:utils|helpers|generic|naming"
      - "regex:domain|specific|purpose|bounded"
      - "length_min:100"
      - "no_placeholder"
    expectations:
      - "Flags utils.js as anti-pattern, suggests domain-specific naming"
    tags: [architecture, naming]
---
# Software Architecture

Clean Architecture and DDD principles for quality-focused development.

## Code Style Rules

### General Principles
- **Early return pattern**: Always use early returns over nested conditions
- Avoid code duplication via reusable functions and modules
- Decompose components >80 lines into smaller units; split files >200 lines
- Use arrow functions over function declarations when possible

### Library-First Approach
- **ALWAYS search for existing solutions before writing custom code**
  - Check npm/pip for existing libraries
  - Evaluate existing services/SaaS
  - Consider third-party APIs for common functionality
- Use libraries instead of custom utils (e.g. `cockatiel`/`tenacity` for retry, not hand-rolled)
- **Custom code IS justified only when:** specific business logic, performance-critical paths, security-sensitive code, or no suitable library exists

### Architecture and Design
- **Clean Architecture & DDD:**
  - Follow domain-driven design and ubiquitous language
  - Separate domain entities from infrastructure
  - Keep business logic framework-independent
  - Define and isolate use cases
- **Naming Conventions:**
  - **AVOID**: `utils`, `helpers`, `common`, `shared`
  - **USE**: domain-specific names: `OrderCalculator`, `UserAuthenticator`, `InvoiceGenerator`
  - Each module = single, clear purpose

### Anti-Patterns to Avoid
- **NIH Syndrome**: Don't build custom auth when Auth0/Supabase exists
- **Mixing concerns**: No business logic in UI components or controllers
- **Generic naming**: `utils.js` with 50 unrelated functions is a liability
- **Deep nesting**: Max 3 levels; use early returns
- **God files**: Max 200 lines per file, max 50 lines per function
