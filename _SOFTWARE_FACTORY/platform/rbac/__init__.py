"""RBAC — Role-Based Access Control for agents and human users.

Defines who can create/read/update/approve each product artifact type.
Enforced at ProductBacklog, Executor, and API route levels.

Hierarchy of product artifacts:
  Product Brief → PRD → Epic → Feature → User Story → Tasks
  Sprint Goal (per sprint), Release Note (per release)

Permission matrix: role_category × artifact_type × action
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


# ── Actions ──────────────────────────────────────────────────────

class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    VETO = "veto"
    ASSIGN = "assign"


# ── Product Artifact types ───────────────────────────────────────

class ProductArtifact(str, Enum):
    PRODUCT_BRIEF = "product_brief"
    PRD = "prd"
    EPIC = "epic"
    FEATURE = "feature"
    USER_STORY = "user_story"
    SPRINT_GOAL = "sprint_goal"
    RELEASE_NOTE = "release_note"
    CODE = "code"
    TEST = "test"
    CONFIG = "config"
    REVIEW = "review"


# ── Human roles ──────────────────────────────────────────────────

class HumanRole(str, Enum):
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    VIEWER = "viewer"


# ── Agent role → category mapping ────────────────────────────────

AGENT_ROLE_CATEGORY: dict[str, str] = {
    # Strategic
    "dsi": "strategic",
    "lean_portfolio_manager": "strategic",
    "enterprise_architect": "strategic",
    # Product
    "business_owner": "product",
    "metier": "product",
    "product_manager": "product",
    "epic_owner": "product",
    "solution_manager": "product",
    # Management
    "chef_projet": "management",
    "scrum_master": "management",
    "agile_coach": "management",
    "pmo": "management",
    "release_train_engineer": "management",
    "solution_train_engineer": "management",
    "change_manager": "management",
    # Architecture
    "architecte": "architecture",
    "lead_dev": "architecture",
    "solution_architect": "architecture",
    "system_architect_art": "architecture",
    "cloud_architect": "architecture",
    "tech_lead_mobile": "architecture",
    # Development
    "dev": "development",
    "dev_frontend": "development",
    "dev_backend": "development",
    "dev_fullstack": "development",
    "dev_mobile": "development",
    "ux_designer": "development",
    "data_analyst": "development",
    "data_engineer": "development",
    "ml_engineer": "development",
    "dba": "development",
    "tech_writer": "development",
    # Quality
    "qa_lead": "quality",
    "testeur": "quality",
    "performance_engineer": "quality",
    "accessibility_expert": "quality",
    # Security
    "securite": "security",
    "compliance_officer": "security",
    "devsecops": "security",
    # Ops
    "devops": "ops",
    "sre": "ops",
}


# ── Permission Matrix ────────────────────────────────────────────
# agent_category → artifact → allowed actions
#
# Design principles:
# - Product roles OWN briefs/PRDs/epics/features/stories
# - Strategic roles APPROVE/VETO product artifacts
# - Management coordinates (sprint goals, assignments, release notes)
# - Architecture bridges product→code (can update PRD technical aspects)
# - Development owns code/tests, reads product artifacts
# - Quality owns reviews/tests, can veto code
# - Security can veto code/config
# - Ops owns config/release notes

_AGENT_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    "strategic": {
        "product_brief": {"create", "read", "update", "approve", "veto"},
        "prd":           {"create", "read", "update", "approve", "veto"},
        "epic":          {"create", "read", "update", "approve", "veto"},
        "feature":       {"read", "approve", "veto"},
        "user_story":    {"read", "approve"},
        "sprint_goal":   {"read", "approve", "veto"},
        "release_note":  {"read", "approve", "veto"},
        "code":          {"read"},
        "test":          {"read"},
        "config":        {"read"},
        "review":        {"read"},
    },
    "product": {
        "product_brief": {"create", "read", "update"},
        "prd":           {"create", "read", "update"},
        "epic":          {"create", "read", "update"},
        "feature":       {"create", "read", "update", "assign"},
        "user_story":    {"create", "read", "update", "assign"},
        "sprint_goal":   {"read"},
        "release_note":  {"read"},
        "code":          {"read"},
        "test":          {"read"},
        "config":        {"read"},
        "review":        {"read"},
    },
    "management": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read", "update", "approve"},
        "feature":       {"read", "update", "assign", "approve"},
        "user_story":    {"read", "update", "assign"},
        "sprint_goal":   {"create", "read", "update", "approve"},
        "release_note":  {"create", "read", "update"},
        "code":          {"read"},
        "test":          {"read"},
        "config":        {"read"},
        "review":        {"read", "approve"},
    },
    "architecture": {
        "product_brief": {"read"},
        "prd":           {"read", "update"},
        "epic":          {"read", "update"},
        "feature":       {"read", "update"},
        "user_story":    {"read", "update", "create"},
        "sprint_goal":   {"read"},
        "release_note":  {"read", "update"},
        "code":          {"create", "read", "update", "approve", "veto"},
        "test":          {"create", "read", "update"},
        "config":        {"create", "read", "update", "approve"},
        "review":        {"create", "read", "approve", "veto"},
    },
    "development": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read"},
        "feature":       {"read"},
        "user_story":    {"read", "update"},
        "sprint_goal":   {"read"},
        "release_note":  {"read"},
        "code":          {"create", "read", "update"},
        "test":          {"create", "read", "update"},
        "config":        {"create", "read", "update"},
        "review":        {"read"},
    },
    "quality": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read"},
        "feature":       {"read"},
        "user_story":    {"read", "update"},
        "sprint_goal":   {"read"},
        "release_note":  {"read", "update"},
        "code":          {"read"},
        "test":          {"create", "read", "update", "approve", "veto"},
        "config":        {"read"},
        "review":        {"create", "read", "approve", "veto"},
    },
    "security": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read"},
        "feature":       {"read"},
        "user_story":    {"read"},
        "sprint_goal":   {"read"},
        "release_note":  {"read"},
        "code":          {"read", "veto"},
        "test":          {"create", "read", "update"},
        "config":        {"read", "veto"},
        "review":        {"create", "read", "approve", "veto"},
    },
    "ops": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read"},
        "feature":       {"read"},
        "user_story":    {"read"},
        "sprint_goal":   {"read"},
        "release_note":  {"create", "read", "update"},
        "code":          {"read", "update"},
        "test":          {"read"},
        "config":        {"create", "read", "update", "approve"},
        "review":        {"create", "read"},
    },
}


# ── Human Permissions ────────────────────────────────────────────

_ALL_ACTIONS = {"create", "read", "update", "delete", "approve", "veto", "assign"}

_HUMAN_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    "admin": {art.value: _ALL_ACTIONS for art in ProductArtifact},
    "project_manager": {
        "product_brief": {"create", "read", "update", "delete", "approve"},
        "prd":           {"create", "read", "update", "delete", "approve"},
        "epic":          {"create", "read", "update", "delete", "approve"},
        "feature":       {"create", "read", "update", "delete", "assign", "approve"},
        "user_story":    {"create", "read", "update", "delete", "assign", "approve"},
        "sprint_goal":   {"create", "read", "update", "approve"},
        "release_note":  {"create", "read", "update", "approve"},
        "code":          {"read"},
        "test":          {"read"},
        "config":        {"read"},
        "review":        {"read", "approve"},
    },
    "developer": {
        "product_brief": {"read"},
        "prd":           {"read"},
        "epic":          {"read"},
        "feature":       {"read"},
        "user_story":    {"read", "update"},
        "sprint_goal":   {"read"},
        "release_note":  {"read"},
        "code":          {"create", "read", "update"},
        "test":          {"create", "read", "update"},
        "config":        {"create", "read", "update"},
        "review":        {"create", "read"},
    },
    "viewer": {art.value: {"read"} for art in ProductArtifact},
}


# ── Public API ───────────────────────────────────────────────────

def get_agent_category(agent_id: str) -> str:
    """Resolve agent ID to role category. Handles cloned agents (dev_frontend_1)."""
    base_id = agent_id
    parts = agent_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        base_id = parts[0]
    return AGENT_ROLE_CATEGORY.get(base_id, "development")


def agent_can(agent_id: str, artifact: str, action: str) -> bool:
    """Check if an agent is allowed to perform an action on an artifact type."""
    category = get_agent_category(agent_id)
    perms = _AGENT_PERMISSIONS.get(category, {})
    return action in perms.get(artifact, set())


def human_can(role: str, artifact: str, action: str) -> bool:
    """Check if a human role is allowed to perform an action on an artifact type."""
    perms = _HUMAN_PERMISSIONS.get(role, _HUMAN_PERMISSIONS.get("viewer", {}))
    return action in perms.get(artifact, set())


def check_agent_permission(agent_id: str, artifact: str, action: str) -> tuple[bool, str]:
    """Check permission, return (allowed, reason)."""
    if agent_can(agent_id, artifact, action):
        return True, "ok"
    category = get_agent_category(agent_id)
    return False, f"Agent '{agent_id}' (category: {category}) cannot {action} '{artifact}'"


def check_human_permission(role: str, artifact: str, action: str) -> tuple[bool, str]:
    """Check permission, return (allowed, reason)."""
    if human_can(role, artifact, action):
        return True, "ok"
    return False, f"Human role '{role}' cannot {action} '{artifact}'"


def agent_permissions_summary(agent_id: str) -> dict[str, list[str]]:
    """All permissions for an agent as {artifact: [actions]}."""
    category = get_agent_category(agent_id)
    perms = _AGENT_PERMISSIONS.get(category, {})
    return {art: sorted(actions) for art, actions in perms.items() if actions}


def human_permissions_summary(role: str) -> dict[str, list[str]]:
    """All permissions for a human role as {artifact: [actions]}."""
    perms = _HUMAN_PERMISSIONS.get(role, {})
    return {art: sorted(actions) for art, actions in perms.items() if actions}


# ── Platform Resource RBAC (Jira-like) ───────────────────────────
# Controls what users can do on platform resources (projects, missions, etc.)
# This is separate from product artifact RBAC above.

class PlatformResource(str, Enum):
    PROJECTS = "projects"
    MISSIONS = "missions"
    AGENTS = "agents"
    SESSIONS = "sessions"
    FEATURES = "features"
    WORKFLOWS = "workflows"
    SETTINGS = "settings"
    USERS = "users"
    TMA = "tma"


class PlatformAction(str, Enum):
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


_ALL_PLATFORM_ACTIONS = {a.value for a in PlatformAction}

# Permission matrix: role → resource → set of actions
_PLATFORM_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    "admin": {r.value: _ALL_PLATFORM_ACTIONS for r in PlatformResource},
    "project_manager": {
        "projects":  {"view", "create", "edit"},
        "missions":  {"view", "create", "edit", "delete", "execute"},
        "agents":    {"view"},
        "sessions":  {"view", "create", "edit", "delete"},
        "features":  {"view", "create", "edit", "delete"},
        "workflows": {"view", "execute"},
        "settings":  {"view"},
        "users":     {"view"},
        "tma":       {"view", "create", "edit", "delete"},
    },
    "developer": {
        "projects":  {"view"},
        "missions":  {"view", "execute"},
        "agents":    {"view"},
        "sessions":  {"view", "create"},
        "features":  {"view", "edit"},
        "workflows": {"view"},
        "settings":  set(),
        "users":     set(),
        "tma":       {"view", "edit"},
    },
    "viewer": {
        "projects":  {"view"},
        "missions":  {"view"},
        "agents":    {"view"},
        "sessions":  {"view"},
        "features":  {"view"},
        "workflows": {"view"},
        "settings":  set(),
        "users":     set(),
        "tma":       {"view"},
    },
}


def platform_can(role: str, resource: str, action: str) -> bool:
    """Check if a human role can perform an action on a platform resource."""
    perms = _PLATFORM_PERMISSIONS.get(role, _PLATFORM_PERMISSIONS.get("viewer", {}))
    return action in perms.get(resource, set())


def check_platform_permission(
    role: str, resource: str, action: str
) -> tuple[bool, str]:
    """Check platform permission, return (allowed, reason)."""
    if platform_can(role, resource, action):
        return True, "ok"
    return False, f"Role '{role}' cannot {action} '{resource}'"


def platform_permissions_summary(role: str) -> dict[str, list[str]]:
    """All platform permissions for a role as {resource: [actions]}."""
    perms = _PLATFORM_PERMISSIONS.get(role, {})
    return {res: sorted(actions) for res, actions in perms.items() if actions}
