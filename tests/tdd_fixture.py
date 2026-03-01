#!/usr/bin/env python3
"""
Fixture pytest pour valider la conformité TDD des agents.
"""

import pytest


@pytest.fixture
def agent_workflow_state():
    """Fixture représentant l'état du workflow agent."""
    return {
        "current_step": None,
        "test_file_created": False,
        "implementation_created": False,
        "validation_performed": False,
        "files_listed": False
    }


def pytest_configure(config):
    """Configure pytest pour le suivi du workflow TDD."""
    config.addinivalue_line(
        "markers", "tdd: mark test as TDD workflow validation"
    )