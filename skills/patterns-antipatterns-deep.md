# Patterns & Anti-Patterns — Deep Skill
# SF Platform Software Engineering Patterns Reference

## WHEN TO ACTIVATE
Reviewing architecture decisions, designing new features, code review,
evaluating agent output, or any system design work.

## DESIGN PATTERNS (Used in SF Platform)

### Creational
1. **Singleton** — `get_agent_store()`, `get_llm_client()`, `get_db()`
   APPLY: Shared resources, connection pools, caches. Store singletons with @dataclass.
2. **Factory Method** — Pattern creation in `engine.py`, Agent creation from AgentDef
   APPLY: When creation logic varies by type but interface is uniform.
3. **Builder** — `_build_phase_prompt()`, `build_retry_prompt()`
   APPLY: Complex objects assembled step by step with many optional parts.

### Structural
4. **Adapter** — `db/adapter.py` (PG/SQLite), LLM client (5 providers)
   APPLY: Unified interface over different implementations. Provider pattern.
5. **Decorator** — Auth middleware, rate limiting, adversarial guard wrapping
   APPLY: Cross-cutting concerns. Layered behavior. Swiss cheese model.
6. **Facade** — `epic_orchestrator.py` hiding pattern/agent/tool complexity
   APPLY: Simplify complex subsystem access. Single entry point.
7. **Proxy** — Tool runner mediating agent-to-tool execution
   APPLY: Access control, logging, caching between caller and target.

### Behavioral
8. **Strategy** — Thompson selection, LLM provider fallback, pattern selection
   APPLY: Interchangeable algorithms at runtime. Config-driven behavior.
9. **Observer** — SSE events, A2A bus, veto notifications
   APPLY: Event-driven. Decoupled producers/consumers. Pub/sub.
10. **Chain of Responsibility** — Quality gates (17 layers), adversarial L0→L1
    APPLY: Sequential filters. Each can pass/reject/modify. Swiss cheese.
11. **State Machine** — EpicRun status (PENDING→RUNNING→COMPLETED/FAILED/VETOED)
    APPLY: Finite states with defined transitions. Prevent invalid state changes.
12. **Command** — Tool calls as serialized commands, git operations
    APPLY: Encapsulate operations as objects. Undo/redo. Queue. Log.
13. **Template Method** — Phase execution loop (setup→execute→gate→cleanup)
    APPLY: Algorithm skeleton with hooks. Subclasses override steps.
14. **Iterator** — Phase queue iteration, sprint loop
    APPLY: Sequential access without exposing internal structure.
15. **Mediator** — A2A bus, PM checkpoint, orchestrator
    APPLY: Centralize complex communications. Reduce coupling.

### Concurrency
16. **Circuit Breaker** — LLM provider cooldown (30s), rate limiter
    APPLY: Prevent cascade failures. Fail fast. Auto-recovery.
17. **Bulkhead** — Mission semaphore, per-mission PG advisory locks
    APPLY: Isolate failures. Resource partitioning. Blast radius control.
18. **Leader Election** — Redis SET NX EX for evolution/simulation tasks
    APPLY: Single writer in distributed system. TTL-based. Fallback=proceed.
19. **Saga** — Multi-phase mission execution with rollback
    APPLY: Distributed transactions. Compensation actions on failure.

### AI/ML Specific
20. **Multi-Agent Orchestration** — 26 patterns (solo to fractal)
    APPLY: Decompose complex tasks. Specialized agents. Coordination protocols.
21. **Thompson Sampling** — Agent selection with Beta distribution
    APPLY: Explore/exploit tradeoff. Bayesian online learning.
22. **Genetic Algorithm** — Phase spec evolution, population=40
    APPLY: Configuration optimization. Mutation + crossover + selection.
23. **Reinforcement Learning** — Q-learning for phase strategy
    APPLY: Learn from experience. State-action-reward. Epsilon-greedy.
24. **RAG** — Memory manager with 4 layers
    APPLY: Context augmentation. Project/global/vector/short-term memory.
25. **Adversarial Testing** — L0 deterministic + L1 semantic
    APPLY: Quality assurance. Multi-layer defense. Swiss cheese model.

## ANTI-PATTERNS TO DETECT & REJECT

### Code Anti-Patterns (Adversarial L0 catches)
1. **God File** — >3 types in one file, >500 LOC. Score +3/+6.
2. **Deep Nesting** — >4 levels. Score +3.
3. **High Coupling** — >12 imports. Score +2.
4. **Cognitive Complexity** — >25 per function. Score +4.
5. **Code Slop** — Hardcoded hex, !important, linear-gradient, emoji. Variable score.
6. **Copy-Paste (Echo)** — Duplicate code blocks. Score +3.
7. **Fake Tests** — Tests that always pass or test nothing. Score +7.
8. **LOC Regression** — Overwriting without reading existing code. Score +6.

### Architecture Anti-Patterns
9. **Monolith creep** — Single file growing without decomposition.
   FIX: Extract to modules when >300 LOC or >3 responsibilities.
10. **Distributed monolith** — Microservices with tight coupling.
    FIX: Async events. Loose coupling. Independent deployment.
11. **Golden hammer** — Same solution for every problem.
    FIX: Match pattern to problem. Solo for simple, hierarchical for complex.
12. **Premature optimization** — Optimizing before measuring.
    FIX: Profile first. Optimize hot paths. YAGNI for the rest.
13. **Not invented here** — Rewriting existing solutions.
    FIX: Use established libraries. Focus on unique business value.

### AI/LLM Anti-Patterns
14. **Hallucination acceptance** — Trusting LLM output without verification.
    FIX: Adversarial guard. Output validation. Tool-based verification.
15. **Prompt injection blindness** — No input sanitization for LLM.
    FIX: SBD-02. Structural separation. Sanitize. Monitor.
16. **Token waste** — Sending full context when summary suffices.
    FIX: Tiered context loading L0/L1/L2. Compress. Focus.
17. **Model worship** — Treating LLM as infallible oracle.
    FIX: Adversarial testing. Human review for critical decisions.
18. **Stack mismatch** — Wrong language/framework for project type.
    FIX: Stack enforcement. adversarial STACK_MISMATCH check. Score +7.

### Process Anti-Patterns
19. **Waterfall in disguise** — Big design up front with no iteration.
    FIX: Sprint loops. PM checkpoint. Quality gates per phase.
20. **Testing as afterthought** — Tests written after deployment.
    FIX: TDD sprint template. adversarial NO_TESTS check.
21. **Traceability gap** — Code without feature/story references.
    FIX: # Ref: headers. Traceability-check phase. UUID chain.
22. **Security bolt-on** — Security added after development.
    FIX: Secure by design. SBD controls from TIER assessment.

## LEAN/KISS PRINCIPLES
1. **KISS** — Keep It Simple, Stupid. Simplest solution that works.
2. **YAGNI** — You Aren't Gonna Need It. Don't build for hypothetical futures.
3. **DRY** — Don't Repeat Yourself. But don't over-abstract either (WET when 3+ uses).
4. **SOLID** — Single responsibility, Open/closed, Liskov, Interface segregation, Dependency inversion.
5. **Fail Fast** — Detect errors early. Validate at boundaries.
6. **Measure First** — Don't optimize without data. Profile, then improve.
7. **Convention over Configuration** — Sane defaults. Override only when needed.
8. **Composition over Inheritance** — Prefer composing behaviors. @dataclass + mixins.
