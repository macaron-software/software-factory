"""
Auto-Heal Quality Validator Tests
=================================
Tests for validating agent outputs and preventing quality rejections.
"""

import pytest
import re
from typing import Dict, List, Tuple


class TestToolUsageValidation:
    """Test suite for validating tool usage in agent outputs."""
    
    def test_detects_no_tools_used(self):
        """Should detect when TOOLS ACTUALLY USED shows no tools."""
        output = {
            "TOOLS ACTUALLY USED": "No tools used",
            "content": "Task completed successfully"
        }
        validator = ToolUsageValidator()
        issues = validator.validate(output)
        assert any("NO_TOOLS_USED" in issue for issue in issues)
    
    def test_accepts_valid_tool_call(self):
        """Should accept output with valid tool usage."""
        output = {
            "TOOLS ACTUALLY USED": "code_write (1 tool call)",
            "content": "File created: agents/auto_heal.py"
        }
        validator = ToolUsageValidator()
        issues = validator.validate(output)
        assert len(issues) == 0
    
    def test_rejects_nonexistent_tools(self):
        """Should reject when agent claims to use non-existent tools."""
        output = {
            "TOOLS ACTUALLY USED": "read_file, glob, tool_schemas",
            "content": "Files analyzed"
        }
        available_tools = ["code_write", "list_files", "deep_search"]
        validator = ToolUsageValidator(available_tools)
        issues = validator.validate(output)
        assert any("INVALID_TOOL" in issue for issue in issues)


class TestHallucinationDetection:
    """Test suite for detecting hallucinations in agent outputs."""
    
    def test_detects_claimed_file_not_created(self):
        """Should detect when agent claims file created but no tool evidence."""
        output = {
            "content": "Successfully created agents/auto_heal.py with 201 lines",
            "TOOLS ACTUALLY USED": "No tools used"
        }
        detector = HallucinationDetector()
        assert detector.is_hallucinating(output) is True
    
    def test_accepts_genuine_file_creation(self):
        """Should accept when tool was actually called."""
        output = {
            "content": "Created agents/auto_heal.py",
            "TOOLS ACTUALLY USED": "code_write (1 tool call)"
        }
        detector = HallucinationDetector()
        assert detector.is_hallucinating(output) is False
    
    def test_detects_contradiction_in_output(self):
        """Should detect contradictions between claims and evidence."""
        output = {
            "content": "success: true",
            "error": "path is outside allowed workspace directories",
            "TOOLS ACTUALLY USED": "code_write (1 tool call)"
        }
        detector = HallucinationDetector()
        assert detector.is_hallucinating(output) is True


class TestCodeQuality:
    """Test suite for code quality validation."""
    
    def test_rejects_empty_code(self):
        """Should reject code with less than minimum lines."""
        code = "pass"
        validator = CodeQualityValidator(min_lines=30)
        assert validator.is_valid(code) is False
    
    def test_accepts_minimum_code(self):
        """Should accept code meeting minimum line requirement."""
        code = "\n".join(["def test():"] + ["    pass"] * 29)
        validator = CodeQualityValidator(min_lines=30)
        assert validator.is_valid(code) is True
    
    def test_rejects_only_comments(self):
        """Should reject code that is only comments."""
        code = "# This is a comment\n# Another comment"
        validator = CodeQualityValidator(min_lines=30)
        assert validator.is_valid(code) is False


class ToolUsageValidator:
    """Validates that agents use correct tools."""
    
    def __init__(self, available_tools: List[str] = None):
        self.available_tools = available_tools or [
            "code_write", "list_files", "deep_search", "edit_file"
        ]
    
    def validate(self, output: Dict) -> List[str]:
        issues = []
        tools_used = output.get("TOOLS ACTUALLY USED", "")
        
        if "No tools used" in tools_used:
            issues.append("L1: NO_TOOLS_USED - Agent claimed work but used no tools")
        
        # Check for non-existent tools
        for tool in self._extract_tools(tools_used):
            if tool not in self.available_tools:
                issues.append(f"L1: INVALID_TOOL - {tool} not in available set")
        
        return issues
    
    def _extract_tools(self, tools_str: str) -> List[str]:
        """Extract tool names from tools string."""
        return [t.strip().split("(")[0] for t in tools_str.split(",") if t.strip()]


class HallucinationDetector:
    """Detects hallucinations in agent outputs."""
    
    def is_hallucinating(self, output: Dict) -> bool:
        """Check if output contains hallucinations."""
        content = output.get("content", "")
        tools_used = output.get("TOOLS ACTUALLY USED", "")
        error = output.get("error", "")
        
        # Claimed file creation but no tools
        if "created" in content.lower() and "No tools used" in tools_used:
            return True
        
        # Contradiction: success claim but error present
        if "success" in content.lower() and error:
            return True
        
        return False


class CodeQualityValidator:
    """Validates code quality meets minimum standards."""
    
    def __init__(self, min_lines: int = 30):
        self.min_lines = min_lines
    
    def is_valid(self, code: str) -> bool:
        """Validate code meets quality standards."""
        if not code or not code.strip():
            return False
        
        lines = [l.strip() for l in code.split("\n") if l.strip()]
        
        # Must have minimum lines
        if len(lines) < self.min_lines:
            return False
        
        # Must not be only comments
        comment_lines = [l for l in lines if l.startswith("#")]
        if len(comment_lines) == len(lines):
            return False
        
        return True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])