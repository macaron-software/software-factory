"""Role-to-tool mapping and agent classification helpers.

WHY: extracted from tool_schemas.py to isolate role-based access control logic.
ROLE_TOOL_MAP determines which tools each agent role can call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..store import AgentDef

ROLE_TOOL_MAP: dict[str, list[str]] = {
    # ── AC Supervisors — READ-ONLY tools, NO code_write/git_commit/docker_deploy ──
    # ⚠️ AC = SUPERVISION: supervisors grade builder outputs, never write project code
    "ac-supervisor": [
        # Code reading (read-only)
        "code_read",
        "code_search",
        "list_files",
        "read_file",
        "read_many_files",
        # Memory & context
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        # Git read-only
        "git_status",
        "git_log",
        "git_diff",
        # Validation (screenshot for grading, not building)
        "screenshot",
        "playwright_test",
        # AC-specific (inject supervision results)
        "ac_inject_cycle",
        "ac_get_project_state",
        # Quality inspection (read-only)
        "quality_scan",
        "complexity_check",
        "coverage_check",
        "doc_coverage_check",
    ],
    "cto": [
        # SF Platform — primary tools for project/mission queries
        "platform_missions",
        "platform_metrics",
        "platform_agents",
        "platform_memory_search",
        "platform_sessions",
        "platform_workflows",
        # Memory
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        # Project context (read-only, no filesystem browsing)
        "get_project_context",
        # Git read (on explicit user request with workspace context)
        "git_status",
        "git_log",
        "git_diff",
        # Git write ops (explicit user requests only)
        "git_clone",
        "git_create_branch",
        "git_init",
        "git_commit",
        "git_push",
        "git_create_pr",
        # GitHub
        "github_issues",
        "github_prs",
        "github_code_search",
        # Orchestration (delegate / create)
        "create_project",
        "create_team",
        "create_mission",
        "create_sub_mission",
        "compose_workflow",
        "launch_epic_run",
        "check_run_status",
        "resume_run",
        "create_sprint",
        "run_e2e_tests",
        "screenshot",
        # Ideation & community delegation
        "launch_ideation",
        "launch_mkt_ideation",
        "launch_group_ideation",
        # Web / fetch
        "mcp_fetch_fetch",
        "deep_search",
        # Confluence write
        "confluence_write_page",
    ],
    "product": [
        "code_read",
        "code_write",
        "code_edit",
        "code_search",
        "list_files",
        "deep_search",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "create_feature",
        "create_story",
        "screenshot",
        "github_issues",
        "github_prs",
        "jira_search",
        "jira_create",
        "jira_update",
        "jira_transition",
        "jira_board_issues",
        "jira_add_comment",
        "jira_sync_from_platform",
        "confluence_read",
        "confluence_write_page",
        "mcp_fetch_fetch",
        "mcp_memory_create_entities",
        "mcp_memory_search_nodes",
        "mcp_memory_create_relations",
        "lrm_component_gallery_list",
        "lrm_component_gallery_get",
        "lrm_component_gallery_search",
        "lrm_component_gallery_ds",
    ],
    "architecture": [
        "code_read",
        "code_write",
        "code_edit",
        "code_search",
        "list_files",
        "deep_search",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "git_log",
        "git_diff",
        "git_status",
        "git_commit",
        "lrm_conventions",
        "lrm_context",
        "lrm_summarize",
        "github_code_search",
        "get_si_blueprint",
        "compose_workflow",
        "create_team",
        "create_sub_mission",
        "list_sub_missions",
        "set_constraints",
        "confluence_write_page",
        "mcp_fetch_fetch",
        "mcp_memory_create_entities",
        "mcp_memory_search_nodes",
        "mcp_memory_create_relations",
        "lrm_guidelines_summary",
        "lrm_guidelines_search",
        "lrm_guidelines_get",
        "lrm_guidelines_stack",
    ],
    "ux": [
        "code_read",
        "code_write",
        "code_search",
        "list_files",
        "screenshot",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "create_feature",
        "figma_get_node",
        "figma_get_styles",
        "solaris_wcag",
        "solaris_component",
        "lrm_component_gallery_list",
        "lrm_component_gallery_get",
        "lrm_component_gallery_search",
        "lrm_component_gallery_ds",
    ],
    "dev": [
        "code_read",
        "code_write",
        "code_edit",
        "code_search",
        "git_status",
        "git_log",
        "git_diff",
        "git_clone",
        "git_create_branch",
        "git_commit",
        "git_create_pr",
        "list_files",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "build",
        "test",
        "lint",
        "docker_deploy",
        "docker_status",
        "docker_build_verify",
        "screenshot",
        "simulator_screenshot",
        "create_ticket",
        "lrm_locate",
        "lrm_conventions",
        "lrm_build",
        "lrm_examples",
        "lrm_confluence_search",
        "lrm_confluence_read",
        "lrm_jira_search",
        "github_prs",
        "github_code_search",
        "android_build",
        "android_test",
        "android_lint",
        "mcp_fetch_fetch",
        "mcp_memory_create_entities",
        "mcp_memory_search_nodes",
        "mcp_memory_create_relations",
        "lrm_guidelines_summary",
        "lrm_guidelines_search",
        "lrm_guidelines_get",
        "lrm_guidelines_stack",
    ],
    "qa": [
        "code_read",
        "code_write",
        "code_edit",
        "code_search",
        "list_files",
        "deep_search",
        "screenshot",
        "simulator_screenshot",
        "playwright_test",
        "build",
        "test",
        "lint",
        "docker_deploy",
        "docker_status",
        "docker_build_verify",
        "cicd_runner",
        "browser_screenshot",
        "browse",
        "take_screenshot",
        "inspect_page",
        "run_e2e_tests",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "git_diff",
        "git_log",
        "git_status",
        "git_commit",
        "github_issues",
        "github_prs",
        "jira_search",
        "jira_create",
        "jira_update",
        "jira_transition",
        "jira_board_issues",
        "jira_add_comment",
        "chaos_test",
        "tmc_load_test",
        "android_build",
        "android_test",
        "android_lint",
        "android_emulator_test",
        "mcp_fetch_fetch",
        "mcp_playwright_browser_navigate",
        "mcp_playwright_browser_snapshot",
        "mcp_playwright_browser_click",
        "mcp_playwright_browser_take_screenshot",
        "mcp_playwright_browser_type",
        "mcp_memory_search_nodes",
    ],
    "devops": [
        "code_read",
        "code_write",
        "code_edit",
        "code_search",
        "git_status",
        "git_log",
        "git_diff",
        "git_commit",
        "git_push",
        "git_clone",
        "git_create_branch",
        "git_create_pr",
        "list_files",
        "docker_deploy",
        "docker_stop",
        "docker_status",
        "build",
        "test",
        "browser_screenshot",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "lrm_build",
        "github_actions",
        "github_prs",
        "infra_check",
        "chaos_test",
        "tmc_load_test",
        "local_ci",
        "create_ticket",
        "get_si_blueprint",
    ],
    "security": [
        "code_read",
        "code_search",
        "list_files",
        "deep_search",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "git_log",
        "git_diff",
        "github_code_search",
        "github_issues",
        "sast_scan",
        "dependency_audit",
        "secrets_scan",
        "recon_portscan",
        "recon_subdomain",
        "recon_fingerprint",
        "pentest_fuzz_api",
        "pentest_inject",
        "pentest_auth",
        "pentest_ssrf",
        "get_si_blueprint",
        "lrm_guidelines_summary",
        "lrm_guidelines_search",
        "lrm_guidelines_stack",
    ],
    "cdp": [
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "list_files",
        "deep_search",
        "code_read",
        "run_phase",
        "get_phase_status",
        "list_phases",
        "request_validation",
        "compose_workflow",
        "create_team",
        "create_sub_mission",
        "list_sub_missions",
        "set_constraints",
        "github_issues",
        "github_prs",
        "jira_search",
        "jira_create",
        "jira_update",
        "jira_transition",
        "jira_board_issues",
        "jira_sync_from_platform",
    ],
    "reviewer": [
        "code_read",
        "code_search",
        "list_files",
        "deep_search",
        "git_diff",
        "git_log",
        "git_status",
        "git_get_pr_diff",
        "git_post_pr_review",
        "github_prs",
        "github_issues",
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
    ],
    # Diagnostic agent — root cause analysis, runtime investigation
    # Activated by incident-diag module. Read-only: no code_write, no deploys.
    "diagnostic": [
        # Investigation tools (diag_tools.py — incident-diag module)
        "diag_logs",
        "diag_process_stats",
        "diag_db_stats",
        "diag_endpoint_latency",
        "diag_queue_depth",
        "diag_correlate",
        # Existing infra/health tools
        "infra_check",
        "docker_status",
        # Error monitoring (read — clustering, status, history)
        "monitoring_scan_incidents",
        "monitoring_cluster_incidents",
        "monitoring_get_error_status",
        "monitoring_should_alert",
        # Perf audit tools (if perf-auditor module also enabled)
        "perf_audit_lighthouse",
        "perf_network_slow",
        "perf_console_errors",
        # Code read (to correlate with recent changes)
        "code_read",
        "code_search",
        "list_files",
        "git_log",
        "git_diff",
        "git_status",
        "github_prs",
        # Memory + context
        "memory_search",
        "memory_store",
        "plan_create",
        "plan_update",
        "plan_get",
        "get_project_context",
        "get_si_blueprint",
        "get_project_health",
        # Escalation (create TMA epic from confirmed root cause)
        "monitoring_create_heal_epic",
        "create_ticket",
        "deep_search",
    ],
}

# Quality tools — available to qa, devops, architecture, cdp roles
_QUALITY_TOOLS = [
    "quality_scan",
    "complexity_check",
    "coverage_check",
    "doc_coverage_check",
]
for _qrole in ("qa", "devops", "architecture", "cdp"):
    if _qrole in ROLE_TOOL_MAP:
        ROLE_TOOL_MAP[_qrole].extend(_QUALITY_TOOLS)

# Claude-compatible aliases — MiniMax/Claude models use these names from training data
# Maps to: read_file→code_read, write_file→code_write, edit_file→code_edit, etc.
_CLAUDE_ALIAS_TOOLS = ["read_file", "write_file", "read_many_files", "edit_file"]
for _arole in ("dev", "reviewer", "qa", "security", "devops", "architecture"):
    if _arole in ROLE_TOOL_MAP:
        ROLE_TOOL_MAP[_arole].extend(_CLAUDE_ALIAS_TOOLS)


# Platform introspection tools — available to ALL agent roles
_PLATFORM_TOOLS = [
    "platform_agents",
    "platform_missions",
    "platform_memory_search",
    "platform_metrics",
    "platform_sessions",
    "platform_workflows",
    "platform_guide",  # BMAD /bmad-help inspired — context-aware next-step guidance
    "ac_inject_cycle",
    "ac_get_project_state",
]
for _role_key in ROLE_TOOL_MAP:
    ROLE_TOOL_MAP[_role_key].extend(_PLATFORM_TOOLS)


# Project lifecycle tools — available to CDP (PM) and architecture roles
_PROJECT_TOOLS = [
    "get_project_health",
    "get_phase_gate",
    "set_project_phase",
    "suggest_next_missions",
    "read_project_doc",
    "update_project_doc",
]
for _prole in ("cdp", "architecture"):
    if _prole in ROLE_TOOL_MAP:
        ROLE_TOOL_MAP[_prole].extend(_PROJECT_TOOLS)


# Reward tools (agent-reward module) — qa, devops, cdp, diagnostic can score runs
_REWARD_TOOLS = [
    "reward_score_run",
    "reward_get_history",
    "reward_summary",
    "reward_export_art",
]
for _rrole in ("qa", "devops", "cdp", "diagnostic"):
    if _rrole in ROLE_TOOL_MAP:
        ROLE_TOOL_MAP[_rrole].extend(_REWARD_TOOLS)


# Memory management tools (AgeMem pattern) — all roles that have memory_search/store also get
# explicit retrieve + prune. WHY: agents need to control what to forget and do exact lookups.
# Ref: AgeMem arXiv:2601.01885, 2026-03.
_MEMORY_EXPLICIT_TOOLS = ["memory_retrieve", "memory_prune"]
for _mrole in ROLE_TOOL_MAP:
    if "memory_search" in ROLE_TOOL_MAP[_mrole]:
        ROLE_TOOL_MAP[_mrole].extend(_MEMORY_EXPLICIT_TOOLS)


def _classify_agent_role(agent) -> str:
    """Classify an agent into a tool-mapping role category.

    ⚠️ AC SUPERVISION RULE: ac-* agents (except ac-codex/ac-cicd builders)
    are classified as 'ac-supervisor' → read-only tools, NO code_write/git_commit.
    """
    role = (agent.role or "").lower()
    name = (agent.name or "").lower()
    agent_id = (agent.id or "").lower()
    combined = f"{role} {name} {agent_id}"

    # ── AC Supervisors (MUST be checked first — before architect/qa/reviewer matches) ──
    # ac-adversarial, ac-coach, ac-security, ac-refactor = supervisors (read-only)
    # ac-codex, ac-codex-v2, ac-cicd, ac-cicd-agent, ac-architect, ac-qa-agent = builders
    _AC_BUILDERS = ("ac-codex", "ac-codex-v2", "ac-cicd", "ac-cicd-agent", "ac-architect", "ac-qa-agent")
    if agent_id.startswith("ac-") and agent_id not in _AC_BUILDERS:
        return "ac-supervisor"

    if any(
        k in combined
        for k in (
            "product",
            "business",
            "analyste",
            "ba ",
            "fonctionnel",
            "product-manager",
        )
    ):
        return "product"
    if (
        any(
            k in combined
            for k in ("chief technology", "directeur technique", "tech lead")
        )
        or " cto " in f" {combined} "
    ):
        return "cto"
    if any(
        k in combined
        for k in (
            "reviewer",
            "code review",
            "code-reviewer",
            "code_reviewer",
            "adversarial",
        )
    ):
        return "reviewer"
    if any(k in combined for k in ("archi", "architect")):
        return "architecture"
    if any(k in combined for k in ("ux", "ui", "design", "ergon")):
        return "ux"
    if any(k in combined for k in ("qa", "test", "qualit", "fixture", "perf")):
        return "qa"
    if any(
        k in combined
        for k in (
            "devops",
            "sre",
            "pipeline",
            "infra",
            "deploy",
            "cicd",
            "ci-cd",
            "ci_cd",
            "release",
            "backup",
            "recovery",
            "monitoring",
            "observ",
            "canary",
        )
    ):
        return "devops"
    if any(
        k in combined
        for k in ("secur", "secu", "cyber", "license", "compliance officer", "scanner")
    ):
        return "security"
    if any(
        k in combined for k in ("contractual", "conformit", " ao ", "cctp", "recette")
    ):
        return "product"
    if any(k in combined for k in ("migration", "etl", "migrat")):
        return "devops"
    if any(
        k in combined for k in ("programme", "projet", "cdp", "scrum", "coach", "pm ")
    ):
        return "cdp"
    if any(
        k in combined
        for k in ("dev", "lead", "engineer", "backend", "frontend", "fullstack")
    ):
        return "dev"
    return "dev"  # default to dev (most permissive set)


def _get_tools_for_agent(agent: AgentDef) -> list[str] | None:
    """Return allowed tool names for this agent.

    Layered approach:
    1. Role floor  — ROLE_TOOL_MAP[role] guarantees minimum set (phase can't fail)
    2. Agent tools — agent.tools (stored in tools_json) are UNIONED on top of the floor
                     This allows specialized agents (e.g. Angular dev) to declare extra
                     tools without losing the baseline role tools.
    Returns None = all tools (only when no project context).
    """
    role_cat = _classify_agent_role(agent)
    role_floor = list(ROLE_TOOL_MAP.get(role_cat) or [])
    if not agent.tools:
        return role_floor
    # Union: role floor guaranteed + agent-specific additions
    return list(set(role_floor) | set(agent.tools))


# Uruk model: Organizers receive full project-scoped context (constitution, ADRs, vision,
# full history). Executors receive task-scoped context only (recent history, no vision).
# See: https://gitlab.com/Akanoa/orthanc — ADR-0010, ADR-0013
_ORGANIZER_ROLES: frozenset[str] = frozenset(
    {"cto", "architecture", "cdp", "product", "reviewer"}
)


def _get_capability_grade(agent) -> str:
    """Return 'organizer' or 'executor' for an agent.

    Organizers (cto, architect, cdp, product, reviewer) receive full project-scoped
    context and longer history windows. Executors (dev, qa, security, ux, devops)
    receive task-scoped context only — reduces token usage by 60-80% for dev agents.
    """
    return (
        "organizer" if _classify_agent_role(agent) in _ORGANIZER_ROLES else "executor"
    )


def _filter_schemas(schemas: list[dict], allowed: list[str] | None) -> list[dict]:
    """Filter tool schemas to only include allowed tool names."""
    if allowed is None:
        return schemas
    allowed_set = set(allowed)
    return [s for s in schemas if s.get("function", {}).get("name") in allowed_set]
