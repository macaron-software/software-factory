"""Tests for PM checkpoint KO drift guard."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_pm_checkpoint_retries_on_ko_drift():
    from platform.memory.manager import get_memory_manager
    from platform.services.pm_checkpoint import BuildResult, TestResult, pm_checkpoint

    project_id = "ko-drift-proj-01"
    mem = get_memory_manager()
    mem.ko_store(
        project_id,
        key="rbac-admin-only",
        value="Only admin can delete users",
        kind="rbac",
        mandatory=True,
        source="test",
    )

    with patch(
        "platform.services.pm_checkpoint.run_build_gate",
        AsyncMock(return_value=BuildResult(success=True, command="ok")),
    ), patch(
        "platform.services.pm_checkpoint.run_test_gate",
        AsyncMock(return_value=TestResult(total=5, passed=5, failed=0, skipped=0)),
    ), patch(
        "platform.services.pm_checkpoint.judge_phase_quality",
        AsyncMock(return_value=(0.9, "APPROVE")),
    ):
        decision = asyncio.run(
            pm_checkpoint(
                phase_name="Development Sprint",
                phase_id="dev-sprint",
                phase_output="Implemented scheduling and calls module only",
                workspace=PROJECT_ROOT,
                phase_success=True,
                project_id=project_id,
                sprint_num=1,
                max_sprints=3,
            )
        )

    assert decision.action == "retry"
    assert "Mandatory knowledge constraints drifted" in decision.reason


def test_pm_checkpoint_allows_when_ko_present():
    from platform.memory.manager import get_memory_manager
    from platform.services.pm_checkpoint import BuildResult, TestResult, pm_checkpoint

    project_id = "ko-drift-proj-02"
    mem = get_memory_manager()
    mem.ko_store(
        project_id,
        key="ac-evaluations-visible-to-teachers",
        value="Evaluations are visible to assigned teachers only",
        kind="acceptance",
        mandatory=True,
        source="test",
    )

    with patch(
        "platform.services.pm_checkpoint.run_build_gate",
        AsyncMock(return_value=BuildResult(success=True, command="ok")),
    ), patch(
        "platform.services.pm_checkpoint.run_test_gate",
        AsyncMock(return_value=TestResult(total=4, passed=4, failed=0, skipped=0)),
    ), patch(
        "platform.services.pm_checkpoint.judge_phase_quality",
        AsyncMock(return_value=(0.8, "APPROVE")),
    ):
        decision = asyncio.run(
            pm_checkpoint(
                phase_name="Development Sprint",
                phase_id="dev-sprint",
                phase_output=(
                    "Implemented evaluations module. "
                    "ac-evaluations-visible-to-teachers enforced in API layer."
                ),
                workspace=PROJECT_ROOT,
                phase_success=True,
                project_id=project_id,
                sprint_num=1,
                max_sprints=3,
            )
        )

    assert decision.action in ("next", "done")
