"""
Skills Injection Integration - Bridge between agent loop and skills injection system
===================================================================================

Integrates automatic skills injection into the agent execution loop.
Called from AgentLoop._build_execution_context() to enrich agent prompts.
"""
# Ref: feat-skills

import logging
import re

logger = logging.getLogger(__name__)


def enrich_agent_with_skills(
    agent_id: str,
    agent_role: str,
    mission_description: str | None = None,
    project_id: str | None = None,
    fallback_skills: list[str] | None = None,
    context_tier: str = "L1",
) -> str:
    """
    Automatically inject relevant external skills into agent's prompt.

    Priority order:
    1. Azure OpenAI embedding-based injection (if configured)
    2. Trigger-based injection: match mission_description against skill metadata.triggers
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
            return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier)

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
            logger.info(
                "Injected %d skills for %s: %s",
                len(result["injected_skills"]),
                agent_role,
                [s["name"] for s in result["injected_skills"]],
            )
            return _format_skills_section(result["injected_skills"], context_tier)

        logger.debug("No Azure skills matched for %s, using trigger-based injection", agent_role)
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier)

    except ImportError:
        logger.debug("Skills injection system not available, using trigger-based injection")
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier)
    except Exception as exc:
        logger.warning("Skills injection failed: %s, using trigger-based injection", exc)
        return _trigger_and_fallback_prompt(fallback_skills, mission_description, context_tier)


def _trigger_and_fallback_prompt(
    fallback_skills: list[str] | None,
    mission_description: str | None,
    context_tier: str = "L1",
) -> str:
    """
    Build skills prompt by combining:
    - Manually declared skills (fallback_skills from agent YAML)
    - Trigger-matched skills from mission_description
    Deduplicates by skill ID; declared skills always included.
    """
    declared_ids = list(fallback_skills or [])
    trigger_ids = _match_skills_by_trigger(mission_description) if mission_description else []

    # Merge: declared first, then trigger-matched that aren't already listed
    all_ids = declared_ids + [sid for sid in trigger_ids if sid not in declared_ids]

    if not all_ids:
        return ""

    injected = list(trigger_ids)
    if injected:
        logger.info("Trigger-matched skills for mission: %s", injected)

    return _load_skills_prompt(all_ids, context_tier)


def _match_skills_by_trigger(mission_description: str) -> list[str]:
    """
    Match skills against mission_description using metadata.triggers keyword matching.
    Returns list of skill IDs whose triggers overlap with the mission context.
    """
    try:
        from ..skills.library import get_skill_library

        lib = get_skill_library()
        desc_lower = mission_description.lower()
        # Tokenize: split on non-word chars, dedupe
        desc_words = set(re.split(r"\W+", desc_lower))
        matched: list[tuple[int, str]] = []  # (score, skill_id)

        for skill in lib.scan_all():
            if not skill.triggers:
                continue
            score = 0
            for trigger in skill.triggers:
                trigger_lower = trigger.lower()
                # Exact substring match (high confidence)
                if trigger_lower in desc_lower:
                    score += 3
                    continue
                # Word overlap (proportional scoring)
                trigger_words = set(re.split(r"\W+", trigger_lower))
                # Remove stop words
                trigger_words -= {"when", "a", "an", "the", "or", "and", "for", "to", "is", "are", "with", "in", "of"}
                if trigger_words and trigger_words & desc_words:
                    overlap = len(trigger_words & desc_words) / len(trigger_words)
                    if overlap >= 0.75:
                        score += 3
                    elif overlap >= 0.5:
                        score += 2
                    elif overlap >= 0.33:
                        score += 1

            if score >= 2:
                matched.append((score, skill.id))

        # Sort by score descending, return top 5 skill IDs
        matched.sort(key=lambda x: x[0], reverse=True)
        return [sid for _, sid in matched[:5]]

    except Exception as exc:
        logger.debug("Trigger matching failed: %s", exc)
        return []


def _load_skills_prompt(skill_ids: list[str], context_tier: str = "L1") -> str:
    """Load skill content and build formatted prompt for given IDs."""
    try:
        from ..skills.library import get_skill_library
        from ..llm.context_tiers import ContextTier, build_tiered_skills

        tier = ContextTier(context_tier)
        lib = get_skill_library()
        raw_skills = []

        for sid in skill_ids[:12]:
            skill = lib.get(sid)
            if skill and (skill.content or skill.l0_summary):
                raw_skills.append({
                    "name": skill.name or skill.id,
                    "content": skill.content,
                    "l0": skill.l0_summary,
                    "similarity": 0.0,
                })

        return build_tiered_skills(raw_skills, tier)

    except Exception as exc:
        logger.debug("Skill loading failed: %s", exc)
        return ""


def _format_skills_section(skills: list[dict], context_tier: str = "L1") -> str:
    """Format Azure-injected skills into prompt section."""
    if not skills:
        return ""

    from ..llm.context_tiers import ContextTier, build_tiered_skills

    tier = ContextTier(context_tier)
    formatted_skills = [
        {
            "name": s.get("name", "Unknown"),
            "content": s.get("content", ""),
            "similarity": s.get("similarity", 0.0),
            "l0": "",
        }
        for s in skills
    ]
    return build_tiered_skills(formatted_skills, tier)


# ── Legacy alias kept for backwards compatibility ────────────────
def _fallback_skills_prompt(skill_ids: list[str] | None = None, context_tier: str = "L1") -> str:
    return _load_skills_prompt(skill_ids or [], context_tier)

    """
    Automatically inject relevant external skills into agent's prompt.

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
        # Import here to avoid circular dependencies
        import os

        from skills_injection.agent_enhancer import AgentEnhancer

        # Get database path
        db_path = os.environ.get("PLATFORM_DB_PATH", "/app/data/platform.db")

        # Get Azure credentials (if configured)
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_key = os.environ.get("AZURE_API_KEY")

        if not azure_endpoint or not azure_key:
            logger.debug("Azure credentials not configured, skipping skills injection")
            return _fallback_skills_prompt(fallback_skills)

        # Initialize enhancer
        enhancer = AgentEnhancer(
            db_path=db_path,
            azure_endpoint=azure_endpoint,
            azure_key=azure_key,
        )

        # Build base system prompt (for context analysis)
        base_prompt = f"You are a {agent_role}."

        # Use mission description as context
        epic_context = mission_description or f"Working as {agent_role}"

        # Inject skills
        result = enhancer.enhance_agent_prompt(
            base_system_prompt=base_prompt,
            mission_description=epic_context,
            agent_role=agent_role,
            mission_id=project_id,
        )

        if result["injected_skills"]:
            logger.info(
                f"Injected {len(result['injected_skills'])} skills for {agent_role}: "
                f"{[s['name'] for s in result['injected_skills']]}"
            )
            return _format_skills_section(result["injected_skills"], context_tier)
        logger.debug(f"No skills matched for {agent_role}, using fallback")
        return _fallback_skills_prompt(fallback_skills, context_tier)

    except ImportError:
        logger.debug("Skills injection system not available, using fallback")
        return _fallback_skills_prompt(fallback_skills, context_tier)
    except Exception as exc:
        logger.warning(f"Skills injection failed: {exc}, using fallback")
        return _fallback_skills_prompt(fallback_skills, context_tier)


def _format_skills_section(skills: list[dict], context_tier: str = "L1") -> str:
    """Format injected skills into prompt section, respecting context tier."""
    if not skills:
        return ""

    from ..llm.context_tiers import ContextTier, build_tiered_skills

    tier = ContextTier(context_tier)
    formatted_skills = []
    for skill in skills:
        formatted_skills.append({
            "name": skill.get("name", "Unknown"),
            "content": skill.get("content", ""),
            "similarity": skill.get("similarity", 0.0),
            "l0": "",
        })
    return build_tiered_skills(formatted_skills, tier)


def _fallback_skills_prompt(skill_ids: list[str] | None = None, context_tier: str = "L1") -> str:
    """Fallback to manual skill loading if injection fails."""
    if not skill_ids:
        return ""

    try:
        from ..skills.library import get_skill_library
        from ..llm.context_tiers import ContextTier, build_tiered_skills

        tier = ContextTier(context_tier)
        lib = get_skill_library()
        raw_skills = []

        for sid in skill_ids[:10]:
            skill = lib.get(sid)
            if skill and (skill.get("content") or skill.get("l0_summary")):
                raw_skills.append({
                    "name": skill["name"],
                    "content": skill.get("content", ""),
                    "l0": skill.get("l0_summary", ""),
                    "similarity": 0.0,
                })

        return build_tiered_skills(raw_skills, tier)
    except Exception as exc:
        logger.debug(f"Fallback skill loading failed: {exc}")
        return ""
