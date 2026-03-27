"""
Test for Tool Enforcement Guardrail - Fix for L1 rejection
This test validates that agents use required tools before output generation.

Scenario: Agent Rachid Mansouri was rejected for "No tools used"
Fix: Enforce minimum tool usage before accepting agent output
"""

import pytest
from unittest.mock import Mock, patch
import json


class TestToolEnforcement:
    """TDD Step 1: Write test that FAILS with current implementation"""
    
    def test_agent_must_use_tools_before_output(self):
        """
        GIVEN: An agent generates output
        WHEN: The agent declares 'No tools used' 
        THEN: Output should be REJECTED with L1 NO_TOOLS_USED error
        """
        # Simulate agent output with no tools used
        agent_output = {
            "output_text": "Analysis complete. No changes needed.",
            "tools_used": [],
            "declared": "No tools used"
        }
        
        # This should FAIL currently - no enforcement exists
        result = validate_tool_usage(agent_output)
        
        # Test expects rejection when no tools used
        assert result["status"] == "REJECTED"
        assert result["error_code"] == "L1_NO_TOOLS_USED"
    
    def test_agent_with_minimum_tools_should_pass(self):
        """
        GIVEN: An agent uses at least 3 tools (list_files, code_read, code_write)
        WHEN: Output is generated
        THEN: Output should be ACCEPTED
        """
        agent_output = {
            "output_text": "Fixed the issue by modifying config.yaml",
            "tools_used": ["list_files", "code_read", "code_write"],
            "declared": "Used 3 tools"
        }
        
        result = validate_tool_usage(agent_output)
        
        assert result["status"] == "ACCEPTED"


def validate_tool_usage(agent_output):
    """
    Validates that agent used required tools before output.
    This is the function we need to IMPLEMENT in the fix.
    """
    # TDD Step 2: Implementation goes here
    # Currently returns ACCEPTED unconditionally - TEST WILL FAIL
    return {"status": "ACCEPTED", "error_code": None}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])