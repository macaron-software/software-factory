"""Token rewards — hooks for mission/task success."""

from __future__ import annotations

from .service import get_mercato_service

MISSION_REWARD = 500
FEATURE_REWARD = 200
TOOL_CALL_REWARD = 10


def reward_mission_success(project_id: str, mission_id: str) -> int:
    svc = get_mercato_service()
    svc.adjust_balance(project_id, MISSION_REWARD, "mission_reward", mission_id)
    return MISSION_REWARD


def reward_feature_done(project_id: str, feature_id: str) -> int:
    svc = get_mercato_service()
    svc.adjust_balance(project_id, FEATURE_REWARD, "feature_reward", feature_id)
    return FEATURE_REWARD


def reward_tool_call(project_id: str, tool_call_id: str | None = None) -> int:
    svc = get_mercato_service()
    svc.adjust_balance(project_id, TOOL_CALL_REWARD, "tool_call_reward", tool_call_id)
    return TOOL_CALL_REWARD
