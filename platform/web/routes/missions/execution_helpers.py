"""Mission execution helpers — context builders and role instruction constants.

Extracted from execution.py to reduce its size.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Role-specific tool instructions ──────────────────────────────────────────
# Keyed by agent_id. Injected into the system prompt for chat/stream endpoint.
ROLE_INSTRUCTIONS: dict[str, str] = {
    "lead_dev": (
        "\n\nTu es le Lead Dev. Tu peux LIRE et MODIFIER le code du projet. "
        "Utilise code_read pour examiner les fichiers, code_write/code_edit pour les modifier, "
        "et git_commit pour committer tes changements. Quand l'utilisateur te demande de modifier "
        "quelque chose, fais-le directement avec les outils."
    ),
    "dev_backend": (
        "\n\nTu es développeur backend. Tu peux LIRE et MODIFIER le code. "
        "Utilise code_read, code_write, code_edit, git_commit."
    ),
    "dev_frontend": (
        "\n\nTu es développeur frontend. Tu peux LIRE et MODIFIER le code. "
        "Utilise code_read, code_write, code_edit, git_commit."
    ),
    "architecte": (
        "\n\nTu es l'Architecte Solution. Tu peux LIRE et MODIFIER l'architecture du projet. "
        "Utilise code_read pour examiner les fichiers, code_write/code_edit pour modifier "
        "Architecture.md ou d'autres docs d'architecture, et git_commit pour committer. "
        "Quand l'utilisateur te demande de mettre à jour l'architecture, fais-le directement."
    ),
    "qa_lead": (
        "\n\nTu es le QA Lead. Tu peux LIRE et MODIFIER les tests du projet. "
        "Utilise code_read pour examiner les tests, code_write/code_edit pour créer ou modifier "
        "des fichiers de test, et git_commit pour committer."
    ),
    "test_manager": (
        "\n\nTu es le Test Manager. Tu peux LIRE et MODIFIER les tests. "
        "Utilise code_read, code_write, code_edit, git_commit."
    ),
    "test_automation": (
        "\n\nTu es l'ingénieur test automation. Tu peux LIRE et ÉCRIRE des tests automatisés. "
        "Utilise code_read, code_write, code_edit, git_commit."
    ),
    "tech_writer": (
        "\n\nTu es le Technical Writer. Tu peux LIRE et MODIFIER la documentation du projet "
        "(README.md, docs/, wiki). Utilise code_read pour examiner les docs, "
        "code_write/code_edit pour les mettre à jour, memory_store pour sauvegarder des "
        "connaissances, et git_commit pour committer."
    ),
    "product_owner": (
        "\n\nTu es le Product Owner. Tu peux consulter le code, les features et la mémoire "
        "projet. Utilise memory_store pour sauvegarder des décisions produit."
    ),
    "product_manager": (
        "\n\nTu es le Product Manager. Tu peux consulter le backlog, les features et la mémoire. "
        "Utilise memory_store pour les décisions."
    ),
    "chef_de_programme": """

Tu es le Chef de Programme (CDP). Tu ORCHESTRE activement le projet.

RÈGLE FONDAMENTALE: Quand l'utilisateur te demande d'agir (lancer, relancer, fixer, itérer), tu DOIS utiliser tes outils. Ne te contente JAMAIS de décrire ce que tu ferais — FAIS-LE.

Tes outils d'orchestration:
- run_phase(phase_id, brief): Lance une phase du pipeline (idéation, dev-sprint, qa-campaign, etc.)
- get_phase_status(phase_id): Vérifie le statut d'une phase
- list_phases(): Liste toutes les phases et leur statut
- request_validation(phase_id, decision): Demande GO/NOGO

Tes outils d'investigation:
- code_read(path): Lire un fichier du projet
- code_search(query, path): Chercher dans le code
- git_log(cwd): View git history
- git_diff(cwd): View changes
- memory_search(query): Chercher dans la mémoire projet
- platform_missions(): État des missions
- platform_agents(): Liste des agents

WORKFLOW: Quand on te dit "go" ou "lance":
1. D'abord list_phases() pour voir l'état
2. Identifie la prochaine phase à lancer
3. Appelle run_phase(phase_id="...", brief="...") pour la lancer
4. Rapporte le résultat

N'écris JAMAIS [TOOL_CALL] en texte — utilise le vrai mécanisme de function calling.""",
}

_DEFAULT_ROLE_INSTRUCTION = (
    "\n\nTu peux LIRE et MODIFIER les fichiers du projet avec code_read, code_write, "
    "code_edit, git_commit, et sauvegarder des connaissances avec memory_store."
)


def get_role_instruction(agent_id: str) -> str:
    """Return role-specific tool instruction for the given agent_id."""
    return ROLE_INSTRUCTIONS.get(agent_id, _DEFAULT_ROLE_INSTRUCTION)


def build_mission_context(mission, session_id: str, sess_store) -> str:
    """Build the mission context string injected into agent system prompts during chat.

    Includes: brief, status, workspace, phases, project memory, recent agent conversations.
    """
    from ....memory.manager import get_memory_manager

    # Phase summary
    phase_summary = []
    if mission.phases:
        for p in mission.phases:
            phase_summary.append(
                f"- {p.phase_id}: {p.status.value if hasattr(p.status, 'value') else p.status}"
            )
    phases_str = "\n".join(phase_summary) if phase_summary else "No phases yet"

    # Project memory
    mem_ctx = ""
    try:
        mem = get_memory_manager()
        entries = mem.project_get(mission.id, limit=20)
        if entries:
            mem_ctx = "\n".join(
                f"[{e['category']}] {e['key']}: {e['value'][:200]}" for e in entries
            )
    except Exception:
        pass

    # Recent agent conversations
    recent = sess_store.get_messages(session_id, limit=30)
    agent_msgs = [
        f"[{m.from_agent}] {m.content[:300]}"
        for m in recent
        if m.from_agent not in ("user", "system") and m.content
    ]
    agent_conv = (
        "\n".join(agent_msgs[-10:]) if agent_msgs else "No agent conversations yet"
    )

    return (
        f"MISSION BRIEF: {mission.brief or 'N/A'}\n"
        f"MISSION STATUS: {mission.status.value if hasattr(mission.status, 'value') else mission.status}\n"
        f"WORKSPACE: {mission.workspace_path or 'N/A'}\n\n"
        f"PHASES STATUS:\n{phases_str}\n\n"
        f"PROJECT MEMORY (knowledge from agents):\n{mem_ctx or 'No memory entries yet'}\n\n"
        f"RECENT AGENT CONVERSATIONS (last 10):\n{agent_conv}\n\n"
        "Answer the user's question about this mission with concrete data.\n"
        "If they ask about PRs, features, sprints, git — use the appropriate tools to search.\n"
        "Answer in the same language as the user. Be precise and data-driven."
    )
