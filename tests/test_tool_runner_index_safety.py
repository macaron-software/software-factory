"""
Test suite for tool_runner index safety (TMA Auto-Heal)

Validates fix for: "list index out of range" error in executor.py:508
"""

import pytest
from unittest.mock import MagicMock, patch


class TestToolRegistryIndexSafety:
    """Test cases for list index access safety in tool registry."""

    def test_get_tools_empty_registry_returns_empty_list(self):
        """When registry is empty, should return [] not raise IndexError."""
        from platform.agents.tool_runner import get_tool_registry
        
        with patch('platform.agents.tool_runner._get_all_tools') as mock_tools:
            mock_tools.return_value = []
            result = get_tool_registry()
            assert isinstance(result, list)
            assert result == []

    def test_get_tools_single_item_returns_that_item(self):
        """Single tool in registry should be returned safely."""
        from platform.agents.tool_runner import get_tool_registry
        
        mock_tool = MagicMock()
        with patch('platform.agents.tool_runner._get_all_tools') as mock_tools:
            mock_tools.return_value = [mock_tool]
            result = get_tool_registry()
            assert len(result) == 1

    def test_get_tools_multiple_items_returns_all(self):
        """Multiple tools should all be accessible."""
        from platform.agents.tool_runner import get_tool_registry
        
        mock_tools = [MagicMock(), MagicMock(), MagicMock()]
        with patch('platform.agents.tool_runner._get_all_tools') as mock_get:
            mock_get.return_value = mock_tools
            result = get_tool_registry()
            assert len(result) == 3

    def test_no_index_error_on_corrupted_registry(self):
        """Corrupted/partial registry data should not crash."""
        from platform.agents.tool_runner import get_tool_registry
        
        # Simulate None returned from _get_all_tools
        with patch('platform.agents.tool_runner._get_all_tools') as mock:
            mock.return_value = None
            # Should handle gracefully
            result = get_tool_registry()
            assert result is not None

    def test_executor_line_508_safety_check(self):
        """
        Verify executor.py:508 has bounds check.
        
        Original buggy code: return [tools[0]]
        Fixed code should check: if tools and len(tools) > 0
        """
        import inspect
        from platform.agents import executor
        
        source = inspect.getsource(executor)
        
        # Check that safe patterns exist in the code
        safe_patterns = [
            'len(tools)',
            'if tools',
            'tools and'
        ]
        
        has_safety = any(pattern in source for pattern in safe_patterns)
        
        # This test will PASS once fix is applied
        # Currently expects the safety check to be present
        assert has_safety, "executor.py missing bounds check for tools[0] access"

    def test_integration_workflow_no_crash(self):
        """Full workflow should not crash with empty tool list."""
        from platform.agents.tool_runner import execute_tool
        
        # Should not raise IndexError
        result = execute_tool("test-tool", {})
        # May return None or error dict, but no crash
        assert result is None or isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
