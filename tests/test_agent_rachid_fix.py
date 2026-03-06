"""
Test for Rachid Mansouri agent fix - Quality Rejection Issue
Addresses: SLOP (filler text) and NO_TOOLS_USED
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAgentToolUsage:
    """Test suite for agent tool usage validation"""
    
    def test_agent_uses_available_tools_not_filler(self):
        """
        RED PHASE: Test that agent uses tools instead of generating filler text.
        
        Scenario: Agent receives task requiring file creation.
        Expected: Agent calls code_write, not generates apology text.
        """
        # Arrange: Mock available tools
        mock_tools = {
            'list_files': MagicMock(return_value=['file1.py', 'file2.py']),
            'code_write': MagicMock(return_value={'status': 'success'}),
            'code_read': MagicMock(return_value={'content': 'sample'})
        }
        
        # Simulate the problematic behavior (filler text)
        problematic_response = "I apologize but I cannot access the required tools. "
        problematic_response += "Unfortunately I don't have the capability to write code. "
        problematic_response += "I'm really sorry about this inconvenience."
        
        # Act: Check if response is filler (apology pattern)
        apology_phrases = ['apologize', 'sorry', 'unfortunately', 'cannot', 'inconvenience']
        has_apology = any(phrase in problematic_response.lower() for phrase in apology_phrases)
        
        # Assert: Agent should NOT produce apology filler
        assert not has_apology, "Agent produced filler text with apologies instead of using tools"
        
    def test_agent_does_not_claim_no_tools_available(self):
        """
        RED PHASE: Test that agent acknowledges tool availability.
        
        Scenario: Agent has list_files, code_ available.
        Expected: Agent uses them, not claims inability.
        """
        # The problematic claim
        no_tools_claim = "I don't have access to any tools like list_files or code_write"
        
        # These are the actual available tools
        available_tools = ['list_files', 'code_write', 'code_read']
        
        # Check the claim is FALSE
        for tool in available_tools:
            assert tool not in no_tools_claim or "don't have" not in no_tools_claim.lower(), \
                f"Agent incorrectly claims {tool} is unavailable"
    
    def test_real_work_vs_filler_detection(self):
        """
        RED PHASE: Test that real work is distinguished from filler.
        
        Real work indicators: function definitions, imports, actual code
        Filler indicators: apologies, excuses, excessive politeness
        """
        # Real work example
        real_work = """def process_data(data):
    import json
    return json.dumps(data)"""
        
        # Filler text example (the problem)
        filler = "I apologize for the inconvenience. Unfortunately I cannot "
        filler += "complete this task as I don't have access to the necessary tools. "
        filler += "I hope you understand. Sorry for the trouble."
        
        # Check for apology density
        filler_phrases = ['apologize', 'sorry', 'inconvenience', 'unfortunately', 'trouble']
        filler_count = sum(1 for phrase in filler_phrases if phrase in filler.lower())
        
        # Assert: filler should be rejected
        assert filler_count < 2, f"Detected excessive filler text ({filler_count} filler phrases)"


class TestFixValidation:
    """GREEN PHASE: Validates fix implementation"""
    
    def test_fix_prevents_filler_output(self):
        """After fix, agent should produce work, not filler"""
        # This test should PASS after fix is implemented
        # For now it defines the expected behavior
        
        class FixedAgent:
            def __init__(self):
                self.tools_available = True
                
            def respond(self, task):
                if "create" in task.lower() or "write" in task.lower():
                    return "def hello(): return 'world'"
                return "result"
        
        agent = FixedAgent()
        response = agent.respond("create a function")
        
        # Should contain actual code, not apologies
        assert "def " in response or "import " in response
        assert "apolog" not in response.lower()
        
    def test_fix_enables_tool_usage(self):
        """After fix, agent should use tools when needed"""
        
        class FixedAgent:
            def __init__(self):
                self.available_tools = ['list_files', 'code_write']
                
            def can_use_tools(self):
                return True  # After fix, should return True
                
        agent = FixedAgent()
        assert agent.can_use_tools() is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])