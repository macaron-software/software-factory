# AGENT DISPATCH: EXACT CODE PATHS & SIGNATURES

## 1. AGENT IDENTITY STORAGE

### File: `platform/agents/store.py:43-77`

```python
@dataclass
class AgentDef:
    """An agent definition (stored in DB)."""
    id: str = ""
    name: str = ""
    role: str = "worker"
    description: str = ""
    system_prompt: str = ""
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    permissions: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    icon: str = "bot"
    color: str = "#f78166"
    avatar: str = ""
    tagline: str = ""
    persona: str = ""  # ← PERSONALITY TRAITS
    motivation: str = ""  # ← DRIVES & GOALS
    hierarchy_rank: int = 50  # ← CONTROLS CONTEXT TIER
    is_builtin: bool = False
    disable_thinking: bool | None = None
    created_at: str = ""
    updated_at: str = ""
```

---

## 2. AGENT LOOP: MESSAGE DISPATCH

### File: `platform/agents/loop.py:60-180`

```python
class AgentLoop:
    """Autonomous agent that checks inbox, thinks via LLM, communicates via bus."""
    
    def __init__(
        self,
        agent_def: AgentDef,
        session_id: str,
        project_id: str = "",
        project_path: str = "",
        think_timeout: float = 3600.0,
        max_rounds: int = 10,
        workspace_id: str = "default",
    ):
        self.agent: AgentDef = agent_def  # ← LOADS IDENTITY
        self.session_id = session_id
        self.project_id = project_id
        self.project_path = project_path
        # ...
        self._executor: AgentExecutor | None = None
        self._bus: MessageBus | None = None
```

### File: `platform/agents/loop.py:188-250` — The Main Loop

```python
async def _run_loop(self) -> None:
    """Core event loop: wait for message → think → act → repeat."""
    assert self._executor is not None
    assert self._bus is not None

    while not self._stop_event.is_set():
        # 1. Wait for a message (1s timeout to check stop flag)
        try:
            msg = await asyncio.wait_for(self._inbox.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        # Skip messages that agents shouldn't process
        if self._should_skip(msg):
            continue

        # Veto keyword pre-filter: auto-veto WITHOUT LLM call if content matches
        if await self._keyword_veto_check(msg):
            continue

        try:
            # 2. Update status → THINKING
            await self._set_status(AgentStatus.THINKING)

            # 3. Build execution context ← THIS IS WHERE SKILLS GET INJECTED
            ctx = await self._build_context()

            # 4. Run executor with streaming
            result = None
            async for event_type, data in self._executor.run_streaming(
                ctx, msg.content
            ):
                # ... streaming event handling ...
                if event_type == "result":
                    result = data

            # 5. Track metrics
            self.instance.tokens_used += result.tokens_in + result.tokens_out

            # 6. Parse and execute actions
            actions = self._parse_actions(result.content)
            if actions:
                await self._set_status(AgentStatus.ACTING)
                for action in actions:
                    await self._execute_action(
                        action, parent_id=msg.id, full_context=result.content
                    )

        except Exception:
            logger.exception("AgentLoop error  agent=%s session=%s", self.agent.id, self.session_id)
            await self._set_status(AgentStatus.ERROR)
            continue

        # 7. Back to idle
        await self._set_status(AgentStatus.IDLE)
```

---

## 3. EXECUTION CONTEXT BUILDER: SKILLS INJECTION POINT

### File: `platform/agents/loop.py:330-620` — The Key Function

```python
async def _build_context(self) -> ExecutionContext:
    """Assemble ExecutionContext with history, memory, skills.
    
    Context is scoped by Uruk capability grade:
    - Organizers (cto, arch, cdp, product): full context, 50 msgs
    - Executors (dev, qa, security): task-scoped, 15 msgs, no vision
    """
    from ..memory.manager import get_memory_manager
    from ..sessions.store import get_session_store
    from .skills_integration import enrich_agent_with_skills
    from ..llm.context_tiers import select_tier, build_tiered_skills

    # Determine capability grade
    grade = _get_capability_grade(self.agent)
    is_organizer = grade == "organizer"

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Load conversation history
    # ─────────────────────────────────────────────────────────────
    history_limit = 50 if is_organizer else 15
    history_dicts: list[dict] = []
    try:
        store = get_session_store()
        messages = store.get_messages(self.session_id, limit=history_limit)
        history_dicts = [
            {
                "from_agent": m.from_agent,
                "content": m.content,
                "message_type": m.message_type,
            }
            for m in messages
        ]
    except Exception as exc:
        logger.debug("Failed to load history: %s", exc)

    # ─────────────────────────────────────────────────────────────
    # STEP 2: Load project memory (knowledge base)
    # ─────────────────────────────────────────────────────────────
    project_context = ""
    if self.project_id:
        try:
            mem = get_memory_manager()
            memory_limit = 10 if is_organizer else 3
            entries = mem.project_get(self.project_id, limit=memory_limit)
            if entries:
                project_context = "\n".join(
                    f"[{e['category']}] {e['key']}: {e['value'][:200]}"
                    for e in entries
                )
        except Exception as exc:
            logger.debug("Failed to load project context: %s", exc)

    # ─────────────────────────────────────────────────────────────
    # STEP 3: Load project memory files
    # ─────────────────────────────────────────────────────────────
    project_memory_str = ""
    if self.project_path:
        try:
            from ..memory.project_files import get_project_memory
            pmem = get_project_memory(self.project_id, self.project_path)
            _max_chars = 4000 if is_organizer else 1500
            project_memory_str = pmem.combined[:_max_chars]
        except Exception as exc:
            logger.debug("Failed to load project memory files: %s", exc)

    # ─────────────────────────────────────────────────────────────
    # STEP 4: AUTO-INJECT SKILLS ← CRITICAL COMPOSITION POINT
    # ─────────────────────────────────────────────────────────────
    skills_prompt = ""
    
    # Select context tier based on agent profile
    from ..llm.context_tiers import select_tier
    tier = select_tier(
        hierarchy_rank=self.agent.hierarchy_rank,
        capability_grade=grade,
    )

    # Try automatic skills injection first
    try:
        from .skills_integration import enrich_agent_with_skills

        # Get mission description for context
        mission_desc = None
        if history_dicts:
            # Use first user message as mission context
            for msg in history_dicts:
                if msg.get("from_agent") == "user":
                    mission_desc = msg.get("content", "")[:500]
                    break

        # ← THIS IS THE SKILLS INJECTION CALL
        skills_prompt = enrich_agent_with_skills(
            agent_id=self.agent.id,
            agent_role=self.agent.role,                    # ← Role used for skill selection
            mission_description=mission_desc,              # ← Mission triggers skill auto-selection
            project_id=self.project_id,
            fallback_skills=self.agent.skills,             # ← Manual fallback
            context_tier=tier.value,                       # ← L0/L1/L2 controls detail
            session_id=self.session_id,
        )
    except Exception as exc:
        logger.debug(f"Auto skills injection failed: {exc}, using manual skills")
        
        # Fallback to manual skill loading
        if self.agent.skills:
            try:
                lib = get_skill_library()
                raw_skills = []
                for sid in self.agent.skills[:10]:
                    skill = lib.get(sid)
                    if skill and (skill.content or skill.l0_summary):
                        raw_skills.append({
                            "name": skill.name,
                            "content": skill.content or "",
                            "l0": skill.l0_summary or "",
                            "similarity": 0.0,
                        })
                skills_prompt = build_tiered_skills(raw_skills, tier)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # STEP 5: Load vision (organizers only)
    # ─────────────────────────────────────────────────────────────
    vision = ""
    if is_organizer and self.project_id:
        try:
            from ..projects.manager import get_project_store
            proj = get_project_store().get(self.project_id)
            if proj and proj.vision:
                vision = proj.vision[:3000]
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # STEP 6: Return complete context
    # ─────────────────────────────────────────────────────────────
    return ExecutionContext(
        agent=self.agent,                 # ← Full identity
        session_id=self.session_id,
        project_id=self.project_id or None,
        project_path=self.project_path or None,
        history=history_dicts,            # ← Conversation
        project_context=project_context,  # ← Knowledge from memory
        project_memory=project_memory_str, # ← Project files
        skills_prompt=skills_prompt,      # ← AUTO-INJECTED SKILLS
        vision=vision,                    # ← Strategic context
        tools_enabled=agent_tools_enabled,
        context_tier=tier.value,
        capability_grade=grade,
        epic_run_id=epic_run_id,
    )
```

---

## 4. EXECUTION CONTEXT DATA STRUCTURE

### File: `platform/agents/executor.py:81-136`

```python
@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""

    agent: AgentDef                    # ← Identity + traits
    session_id: str
    project_id: str | None = None
    project_path: str | None = None
    history: list[dict] = field(default_factory=list)  # ← Conversation
    project_context: str = ""          # ← Knowledge from memory
    project_memory: str = ""           # ← VISION.md, SPECS.md
    domain_context: str = ""           # ← Domain guidelines
    skills_prompt: str = ""            # ← AUTO-INJECTED SKILLS
    vision: str = ""                   # ← Strategic vision
    tools_enabled: bool = True
    allowed_tools: list[str] | None = None
    on_tool_call: object | None = None
    epic_run_id: str | None = None
    capability_grade: str = "executor"
    context_tier: str = "L1"           # ← Controls prompt verbosity
    max_rounds: int = 0
    code_files_written: list[str] = field(default_factory=list)
    phase_config: dict = field(default_factory=dict)
```

---

## 5. SKILLS INJECTION SYSTEM

### File: `platform/agents/skills_integration.py:89-166`

```python
def enrich_agent_with_skills(
    agent_id: str,
    agent_role: str,                   # ← Used to determine skill eligibility
    mission_description: str | None = None,
    project_id: str | None = None,
    fallback_skills: list[str] | None = None,
    context_tier: str = "L1",
    session_id: str = "",
) -> str:
    """
    Automatically inject relevant external skills into agent's prompt.

    Priority order:
    1. Azure OpenAI embedding-based injection (if configured)
    2. Trigger-based injection: match mission_description against skill metadata
    3. Fallback to manually declared skills in agent YAML

    Args:
        agent_id: Agent identifier
        agent_role: Agent role name (e.g., "Product Manager", "Backend Dev")
        mission_description: Current mission/task description for context analysis
        project_id: Project identifier
        fallback_skills: Manual skill IDs to use if injection fails
        context_tier: L0/L1/L2 — controls how much detail per skill

    Returns:
        Formatted skills prompt to inject into system_prompt
    """
    try:
        import os
        from skills_injection.agent_enhancer import AgentEnhancer

        db_path = os.environ.get("PLATFORM_DB_PATH", "/app/data/platform.db")
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_key = os.environ.get("AZURE_API_KEY")

        if not azure_endpoint or not azure_key:
            logger.debug("Azure credentials not configured, using trigger-based injection")
            return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier, session_id)

        # Try Azure embeddings
        enhancer = AgentEnhancer(
            db_path=db_path,
            azure_endpoint=azure_endpoint,
            azure_key=azure_key,
        )

        base_prompt = f"You are a {agent_role}."
        epic_context = mission_description or f"Working as {agent_role}"

        result = enhancer.enhance_agent_prompt(
            base_system_prompt=base_prompt,
            mission_description=epic_context,
            agent_role=agent_role,
            mission_id=project_id,
        )

        if result["injected_skills"]:
            skill_ids = [s.get("id") or s.get("name", "") for s in result["injected_skills"]]
            _cache_skills(session_id, [s for s in skill_ids if s])
            logger.info(
                "Injected %d skills for %s: %s",
                len(result["injected_skills"]),
                agent_role,
                skill_ids,
            )
            return _format_skills_section(result["injected_skills"], context_tier)

        logger.debug("No Azure skills matched for %s, using trigger-based injection", agent_role)
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier, session_id)

    except ImportError:
        logger.debug("Skills injection system not available, using trigger-based injection")
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier, session_id)
    except Exception as exc:
        logger.warning("Skills injection failed: %s, using trigger-based injection", exc)
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier, session_id)
```

### File: `platform/agents/skills_integration.py:168-216` — Trigger-Based Fallback

```python
def _trigger_and_fallback_prompt(
    fallback_skills: list[str] | None,
    mission_description: str | None,
    context_tier: str = "L1",
    session_id: str = "",
) -> str:
    """
    Build skills prompt by combining:
    - Context-pattern skills (auto-triggered by task phase detection)
    - Manually declared skills (fallback_skills from agent YAML)
    - Trigger-matched skills from mission_description
    Deduplicates by skill ID; context patterns always included first.
    """
    # 1. Auto-trigger: detect context phase and inject mandatory skills
    context_ids: list[str] = []
    if mission_description:
        phases = _detect_context_phase(mission_description)  # ← Phase detection
        for phase in phases:
            for sid in _CONTEXT_PATTERNS.get(phase, []):
                if sid not in context_ids:
                    context_ids.append(sid)
        if context_ids:
            logger.info("Context auto-trigger [%s]: %s", ",".join(phases), context_ids)

    # 2. Declared skills from agent YAML
    declared_ids = list(fallback_skills or [])

    # 3. Trigger-matched skills from keyword analysis
    trigger_ids = _match_skills_by_trigger(mission_description) if mission_description else []

    # Merge: context-patterns first, then declared, then trigger-matched (deduped)
    all_ids: list[str] = list(context_ids)
    for sid in declared_ids:
        if sid not in all_ids:
            all_ids.append(sid)
    for sid in trigger_ids:
        if sid not in all_ids:
            all_ids.append(sid)

    if not all_ids:
        return ""

    injected = [sid for sid in (context_ids + trigger_ids) if sid not in declared_ids]
    if injected:
        logger.info("Auto-injected skills: %s", injected)

    _cache_skills(session_id, all_ids)
    return _load_skills_prompt(all_ids, context_tier)
```

### File: `platform/agents/skills_integration.py:23-65` — Context Patterns

```python
_CONTEXT_PATTERNS: dict[str, list[str]] = {
    # Phase → skill IDs auto-injected when mission matches
    "debug": [
        "systematic-debugging",      # 4-phase root cause process
        "debugging-strategies",      # debug methodology
        "ac-adversarial",            # quality gates
    ],
    "review": [
        "code-review",               # review checklist
        "ac-adversarial-v2",         # adversarial quality check
        "ac-security",               # security review
    ],
    "implement": [
        "automated-testing",         # TDD enforcement
        "software-architecture",     # arch patterns
    ],
    "plan": [
        "ac-architect",              # architecture supervision
        "architecture-design",       # design guidance
    ],
    "test": [
        "automated-testing",
        "debugging-strategies",
    ],
    "security": [
        "ac-security",
        "api-security-testing",
    ],
    "deploy": ["ac-cicd"],
}

# Keyword → context phase mapping (lowercased)
_PHASE_KEYWORDS: dict[str, list[str]] = {
    "debug": ["debug", "bug", "fix", "error", "crash", "failure", "traceback", "exception"],
    "review": ["review", "audit", "inspect", "quality", "critique", "veto", "approve"],
    "implement": ["implement", "build", "create", "develop", "code", "feature", "sprint"],
    "plan": ["plan", "design", "architect", "spec", "inception", "brainstorm"],
    "test": ["test", "tdd", "coverage", "assertion", "pytest", "jest", "playwright"],
    "security": ["security", "vulnerability", "cve", "owasp", "pentest", "injection", "xss"],
    "deploy": ["deploy", "release", "pipeline", "ci/cd", "staging", "production"],
}
```

---

## 6. SYSTEM PROMPT BUILDER

### File: `platform/agents/prompt_builder.py:125-360` — Main Assembly

```python
def _build_system_prompt(ctx: ExecutionContext) -> str:
    """Compose the full system prompt from agent config + skills + context."""
    parts = []
    agent = ctx.agent

    # 1. Base system prompt (from AgentDef)
    if agent.system_prompt:
        parts.append(agent.system_prompt)

    # 2. Persona (personality traits)
    if agent.persona:
        parts.append(f"\n## Persona & Character\n{agent.persona}")

    # 3. Motivation (what drives this agent)
    if agent.motivation:
        parts.append(f"\n## Motivation & Drive\n{agent.motivation}")

    # 4. Identity statement
    parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
    if agent.description:
        parts.append(f"Description: {agent.description}")

    # 5. PUA motivation block (source: github.com/tanweai/pua MIT)
    from .pua import build_motivation_block
    parts.append(build_motivation_block())

    # 6. Tool instructions
    if ctx.tools_enabled:
        parts.append("""
You have access to tools via function calling. When you need to take action, call the tools directly.
CRITICAL: When the user asks you to DO something, USE your tools immediately.

## Memory (MANDATORY)
1. ALWAYS call memory_search(query="<topic>") at the START
2. ALWAYS call memory_store() at the END
""")

        # Deep search / RLM
        if ctx.allowed_tools is None or "deep_search" in (ctx.allowed_tools or []):
            parts.append("""
## Deep Search / RLM (MANDATORY)
After calling memory_search, if the question involves exploration or architectural decisions:
ALWAYS call deep_search(query="<your question>") BEFORE synthesizing your answer.
""")

        # Role-specific instructions
        role_cat = _classify_agent_role(agent)
        if role_cat == "cto":
            parts.append("""
## Software Factory — Rôle CTO
Tu es Karim Benali, CTO de la Software Factory. Tu es opérationnel : tu peux CONSULTER et CRÉER.
Tu peux: create_project(), create_mission(), create_team(), compose_workflow()
""")
        elif role_cat == "qa":
            parts.append("""
## QA Testing (MANDATORY)
You have run_e2e_tests. You MUST call it.
STEP 1: Call run_e2e_tests()
STEP 2: Read results and report bugs
STEP 3: Call build(command="npm test") if needed
""")
        # ... more role-specific blocks ...

        # Execution mandate (prevent hallucination)
        if role_cat in ("dev", "qa", "devops", "security"):
            parts.append("""
## Tool Usage (MANDATORY)
You are an EXECUTION agent. Every response MUST include tool calls.
1. READ: code_read / list_files
2. WRITE: code_write / code_edit
3. VERIFY: build / test
NEVER describe what you would do — DO IT.
""")

    # 7. Architecture guidelines (if available)
    guidelines = _load_guidelines_for_prompt(ctx)
    if guidelines:
        tiered = apply_tier_to_context(tier, guidelines=guidelines)
        if tiered["guidelines"]:
            parts.append(f"\n## Architecture & Tech Guidelines\n{tiered['guidelines']}")

    # 8. Project context (tier-aware)
    tier = ContextTier(ctx.context_tier)
    if tier == ContextTier.L2:
        if tiered.get("vision"):
            parts.append(f"\n## Project Vision\n{tiered['vision']}")
        if tiered.get("project_context"):
            parts.append(f"\n## Project Context\n{tiered['project_context']}")
        if tiered.get("project_memory"):
            parts.append(f"\n## Project Memory\n{tiered['project_memory']}")
    elif tier == ContextTier.L1:
        if tiered.get("project_context"):
            parts.append(f"\n## Task Context\n{tiered['project_context']}")

    # 9. SKILLS ← KEY COMPOSITION POINT
    if ctx.skills_prompt:
        parts.append(f"\n## Skills\n{ctx.skills_prompt}")

    # 10. Permissions
    perms = agent.permissions or {}
    if perms.get("can_delegate"):
        parts.append("""
## Delegation
You MUST delegate using: [DELEGATE:agent_id] clear task description
""")
    if perms.get("can_veto"):
        parts.append("\nYou CAN veto by writing: [VETO] reason")
    if perms.get("can_approve"):
        parts.append("\nYou CAN approve by writing: [APPROVE] reason")

    return "\n".join(parts)
```

### File: `platform/agents/prompt_builder.py:362-377` — Build Messages

```python
def _build_messages(ctx: ExecutionContext, user_message: str) -> list[LLMMessage]:
    """Build the message list from conversation history."""
    messages = []
    for h in ctx.history[-20:]:
        role = "assistant" if h.get("from_agent") != "user" else "user"
        name = h.get("from_agent")
        messages.append(
            LLMMessage(
                role=role,
                content=h.get("content", ""),
                name=name if name != "user" else None,
            )
        )
    messages.append(LLMMessage(role="user", content=user_message))
    return messages
```

---

## 7. EXECUTOR: RUNS AGENT WITH LLM

### File: `platform/agents/executor.py:716-850`

```python
async def run(self, ctx: ExecutionContext, user_message: str) -> ExecutionResult:
    """Run the agent with tool-calling loop."""
    t0 = time.monotonic()
    agent = ctx.agent
    total_tokens_in = 0
    total_tokens_out = 0
    all_tool_calls = []

    # Build the SYSTEM PROMPT (all components combined)
    system = _build_system_prompt(ctx)
    
    # Build messages (conversation history + user message)
    messages = _build_messages(ctx, user_message)
    
    # Get tools for the LLM to call
    tools = (
        _filter_schemas(_get_tool_schemas(), ctx.allowed_tools)
        if ctx.tools_enabled
        else None
    )

    # Route provider (Thompson Sampling)
    use_provider, use_model = _route_provider(agent, tools, mission_id=ctx.epic_run_id)

    # Tool-calling loop (up to MAX_TOOL_ROUNDS)
    for round_num in range(MAX_TOOL_ROUNDS):
        # SANITIZE TOOL PAIRS before LLM call
        messages = _sanitize_tool_pairs(messages)
        
        # THIS IS WHERE THE SYSTEM PROMPT GETS SENT ← CRITICAL
        llm_resp = await self._llm.chat(
            messages=messages,
            provider=use_provider,
            model=use_model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            system_prompt=system if round_num == 0 else "",  # ← FULL ASSEMBLED PROMPT
            tools=tools,
            disable_thinking=_project_disable_thinking,
        )

        total_tokens_in += llm_resp.tokens_in
        total_tokens_out += llm_resp.tokens_out

        # Check if we got tool calls
        if llm_resp.tool_calls:
            # Execute tools and add results to messages
            for tool_call in llm_resp.tool_calls:
                tool_name = tool_call.get("function", {}).get("name")
                args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                
                tool_result = await _execute_tool(tool_name, args, ctx)
                
                messages.append(LLMMessage(role="assistant", content="", tool_calls=[tool_call]))
                messages.append(LLMMessage(
                    role="tool",
                    content=tool_result,
                    tool_call_id=tool_call["id"],
                ))
        else:
            # No tool calls → done
            break

    return ExecutionResult(
        content=llm_resp.content,
        agent_id=agent.id,
        model=llm_resp.model,
        provider=llm_resp.provider,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        duration_ms=int((time.monotonic() - t0) * 1000),
        tool_calls=all_tool_calls,
    )
```

---

## 8. LLM CLIENT: CHAT COMPLETION

### File: `platform/llm/client.py:388-550`

```python
async def chat(
    self,
    messages: list[LLMMessage],
    provider: str = _primary,
    model: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    system_prompt: str = "",                   # ← FULL ASSEMBLED PROMPT HERE
    tools: list[dict] | None = None,
    disable_thinking: bool | None = None,
) -> LLMResponse:
    """Send a chat completion request. Falls back to next provider on failure."""
    
    # Cache lookup
    from .cache import get_cache
    _llm_cache = get_cache()
    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
    cache_model = model or provider
    cached = _llm_cache.get(cache_model, msg_dicts, temperature, tools)
    if cached:
        logger.info("LLM cache HIT (%s, saved %d tokens)", cache_model, cached["tokens_in"] + cached["tokens_out"])
        return LLMResponse(...)

    # Provider routing (Thompson Sampling)
    if _is_azure:
        provider = "azure-openai"
    providers_to_try = [provider] + [p for p in _FALLBACK_CHAIN if p != provider]

    for prov in providers_to_try:
        # Check cooldown
        cooldown_until = self._provider_cooldown.get(prov, 0)
        now = time.monotonic()
        if cooldown_until > now:
            logger.warning("LLM %s in cooldown (%ds left), skipping", prov, int(cooldown_until - now))
            continue

        # Check circuit breaker
        if self._cb_is_open(prov):
            logger.warning("LLM %s circuit breaker OPEN, skipping", prov)
            continue

        pcfg = self._get_provider_config(prov)
        key = self._get_api_key(pcfg)
        if not pcfg.get("no_auth") and (not key or key == "no-key"):
            logger.warning("LLM %s skipped (no API key)", prov)
            continue

        use_model = (
            model
            if (prov == provider and model and model in pcfg.get("models", []))
            else pcfg["default"]
        )

        # Rate limiter
        try:
            await _rate_limiter.acquire(timeout=86400.0)
        except TimeoutError:
            logger.warning("LLM rate limiter timeout — retrying")
            await asyncio.sleep(10)
            continue

        logger.warning("LLM trying %s/%s ... [rate: %s]", prov, use_model, _rate_limiter.usage)

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # RTK-inspired prompt compression (saves ~30% tokens)
                _send_messages = messages
                _send_system = system_prompt
                
                if _rtk_cache.get("enabled", True):
                    try:
                        from .prompt_compressor import compress_messages as _rtk_compress
                        _send_messages, _send_system, _rtk_stats = _rtk_compress(
                            messages, system_prompt, provider=prov
                        )
                        if _rtk_stats["savings_pct"] > 0:
                            logger.warning(
                                "RTK compress %s: %d→%d tokens (-%s%%)",
                                prov,
                                _rtk_stats["original_tokens"],
                                _rtk_stats["compressed_tokens"],
                                _rtk_stats["savings_pct"],
                            )
                    except Exception as _ce:
                        logger.debug("RTK compressor error (skipped): %s", _ce)

                # Make the actual LLM call
                result = await self._do_chat(
                    pcfg,
                    prov,
                    use_model,
                    _send_messages,
                    temperature,
                    max_tokens,
                    _send_system,    # ← SYSTEM PROMPT SENT HERE
                    tools,
                    disable_thinking=disable_thinking,
                )
                
                # Handle response
                return result
                
            except Exception as e:
                logger.warning("LLM %s/%s attempt %d failed: %s", prov, use_model, attempt + 1, e)
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)

        # If all attempts failed, try next provider
        self._cb_record_failure(prov)
        continue

    # All providers exhausted
    raise RuntimeError("All LLM providers exhausted")
```

### File: `platform/llm/client.py:1047-1120` — HTTP Request

```python
async def _do_chat(
    self,
    pcfg: dict,
    provider: str,
    model: str,
    messages: list[LLMMessage],
    temperature: float,
    max_tokens: int,
    system_prompt: str,              # ← FULL PROMPT
    tools: list[dict] | None,
    disable_thinking: bool | None,
) -> LLMResponse:
    """Execute actual API call to provider."""
    
    # Prepare request body
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt} if system_prompt else {},
            *[
                {
                    "role": m.role,
                    "content": m.content,
                    "name": m.name if m.name and m.role != "system" else None,
                }
                for m in messages
            ],
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": tools if tools else None,
    }

    # Build URL and headers
    url = self._build_url(pcfg, model)
    headers = self._build_headers(pcfg)

    # Make async HTTP request
    http = await self._get_http()
    response = await http.post(url, json=request_body, headers=headers, timeout=120.0)

    # Parse response
    data = response.json()
    content = data["choices"][0]["message"].get("content", "")
    tool_calls = data["choices"][0]["message"].get("tool_calls", [])
    finish_reason = data["choices"][0].get("finish_reason", "")

    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        tokens_in=data["usage"]["prompt_tokens"],
        tokens_out=data["usage"]["completion_tokens"],
        model=model,
        provider=provider,
        finish_reason=finish_reason,
    )
```

---

## COMPLETE FLOW: Data Classes & Function Calls

```
AgentDef (config)
  ↓
AgentLoop.__init__(agent_def: AgentDef)
  ↓
AgentLoop.start()
  ↓
AgentLoop._run_loop()
  └─ msg = await inbox.get()
  └─ ctx = await _build_context()
       ├─ load history
       ├─ load project_context
       ├─ load project_memory
       ├─ enrich_agent_with_skills()
       │    ├─ _trigger_and_fallback_prompt()
       │    │  ├─ _detect_context_phase(mission_desc)
       │    │  └─ _load_skills_prompt(skill_ids, tier)
       │    └─ return skills_prompt: str
       ├─ select_tier()
       └─ return ExecutionContext
  └─ result = await executor.run(ctx, user_message)
       ├─ system = _build_system_prompt(ctx)
       │    ├─ agent.system_prompt
       │    ├─ agent.persona
       │    ├─ agent.motivation
       │    ├─ build_motivation_block()
       │    ├─ _classify_agent_role() → role-specific block
       │    ├─ project context (tier-aware)
       │    ├─ ctx.skills_prompt ← KEY COMPOSITION
       │    └─ permissions block
       ├─ messages = _build_messages(ctx, user_message)
       ├─ tools = _filter_schemas(_get_tool_schemas(), ctx.allowed_tools)
       ├─ for round in range(MAX_TOOL_ROUNDS):
       │    └─ llm_resp = await llm.chat(
       │         messages=messages,
       │         system_prompt=system,  ← FULL ASSEMBLED PROMPT
       │         provider=use_provider,
       │         model=use_model,
       │         tools=tools
       │       )
       │    └─ if llm_resp.tool_calls:
       │       └─ execute tools → add to messages → loop
       └─ return ExecutionResult
```

