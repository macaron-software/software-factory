"""
Skills Injection Integration - Bridge between agent loop and skills injection system
===================================================================================

Integrates automatic skills injection into the agent execution loop.
Called from AgentLoop._build_execution_context() to enrich agent prompts.
"""

import logging

logger = logging.getLogger(__name__)


def enrich_agent_with_skills(
    agent_id: str,
    agent_role: str,
    mission_description: str | None = None,
    project_id: str | None = None,
    fallback_skills: list[str] | None = None,
) -> str:
    """
    Automatically inject relevant external skills into agent's prompt.

    Args:
        agent_id: Agent identifier
        agent_role: Agent role name (e.g., "Product Manager", "Backend Dev")
        mission_description: Current mission/task description for context analysis
        project_id: Project identifier
        fallback_skills: Manual skill IDs to use if injection fails

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
        mission_context = mission_description or f"Working as {agent_role}"

        # Inject skills
        result = enhancer.enhance_agent_prompt(
            base_system_prompt=base_prompt,
            mission_description=mission_context,
            agent_role=agent_role,
            mission_id=project_id,
        )

        if result["injected_skills"]:
            logger.info(
                f"Injected {len(result['injected_skills'])} skills for {agent_role}: "
                f"{[s['name'] for s in result['injected_skills']]}"
            )
            return _format_skills_section(result["injected_skills"])
        logger.debug(f"No skills matched for {agent_role}, using fallback")
        return _fallback_skills_prompt(fallback_skills)

    except ImportError:
        logger.debug("Skills injection system not available, using fallback")
        return _fallback_skills_prompt(fallback_skills)
    except Exception as exc:
        logger.warning(f"Skills injection failed: {exc}, using fallback")
        return _fallback_skills_prompt(fallback_skills)


def _format_skills_section(skills: list[dict]) -> str:
    """Format injected skills into prompt section."""
    if not skills:
        return ""

    parts = []
    for skill in skills[:10]:  # Max 10 skills
        name = skill.get("name", "Unknown")
        content = skill.get("content", "")
        similarity = skill.get("similarity", 0.0)

        # Truncate long skills
        if len(content) > 1500:
            content = content[:1500] + "..."

        parts.append(f"### {name} (relevance: {similarity:.2f})\n{content}")

    return "\n\n".join(parts)


def _fallback_skills_prompt(skill_ids: list[str] | None = None) -> str:
    """Fallback to manual skill loading if injection fails."""
    if not skill_ids:
        return ""

    try:
        from ..skills.library import get_skill_library

        lib = get_skill_library()
        parts = []

        for sid in skill_ids[:5]:  # Max 5 fallback skills
            skill = lib.get(sid)
            if skill and skill.get("content"):
                parts.append(f"### {skill['name']}\n{skill['content'][:1500]}")

        return "\n\n".join(parts)
    except Exception as exc:
        logger.debug(f"Fallback skill loading failed: {exc}")
        return ""
