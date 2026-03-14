"""
Unit tests for workflows/builtins.py
Tests PromptBuilder, ToolRunner, and validation logic
"""
# Ref: feat-workflows
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from workflows.builtins import (
    PromptBuilder,
    ToolRunner,
    AdversarialRetries,
    ValidationResult,
    WORKFLOW_PHASES,
    get_workflow_definition,
    validate_phase_transition
)


class TestPromptBuilder:
    """Test PromptBuilder class functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.builder = PromptBuilder()
    
    def test_prompt_builder_initialization(self):
        """Verify PromptBuilder initializes with correct config"""
        assert self.builder.PHASE_CONFIGS is not None
        assert "project-setup" in self.builder.PHASE_CONFIGS
    
    def test_project_setup_config(self):
        """Verify project-setup has correct configuration"""
        config = self.builder.PHASE_CONFIGS["project-setup"]
        
        assert config["min_length"] == 200
        assert config["language"] == "fr"
        assert "required_fields" in config
    
    def test_build_prompt_for_project_setup(self):
        """Verify build generates valid prompt for project-setup"""
        context = {
            "description": "Test project",
            "budget": "10k",
            "timeline": "3 months"
        }
        
        prompt = self.builder.build("project-setup", context)
        
        # Verify it's French
        assert "Projet" in prompt or "projet" in prompt.lower()
        
        # Verify minimum length
        assert len(prompt) >= 200, f"Prompt too short: {len(prompt)}"
    
    def test_build_prompt_expansion(self):
        """Verify short prompts are expanded"""
        context = {"description": "Short"}
        
        prompt = self.builder.build("project-setup", context)
        
        # Should meet minimum length
        assert len(prompt) >= 200
    
    def test_generate_french_prompt(self):
        """Verify French prompt generation"""
        context = {"description": "Mon projet"}
        
        prompt = self.builder._generate_french_prompt("project-setup", context)
        
        # Should contain French keywords
        french_keywords = ["contexte", "objectifs", "livrables"]
        found = any(kw in prompt.lower() for kw in french_keywords)
        assert found or len(prompt) > 50
    
    def test_expand_prompt_recursive(self):
        """Verify recursive prompt expansion"""
        short_prompt = "Short"
        min_length = 200
        
        expanded = self.builder._expand_prompt(short_prompt, min_length)
        
        assert len(expanded) >= min_length


class TestToolRunner:
    """Test ToolRunner class functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.builder = PromptBuilder()
        self.runner = ToolRunner(self.builder)
    
    def test_tool_runner_initialization(self):
        """Verify ToolRunner initializes correctly"""
        assert self.runner.prompt_builder is not None
    
    def test_run_validates_output(self):
        """Verify run method validates output"""
        context = {"description": "Test project"}
        
        result = self.runner.run("project-setup", context)
        
        assert result is not None
        assert "validation" in result
        assert result["status"] == "success"
    
    def test_validate_output_minimum_length(self):
        """Verify validation checks minimum length"""
        # Short output should fail
        short_output = "x" * 35
        
        validation = self.runner.validate_output(short_output, "project-setup")
        
        assert not validation.is_valid
        assert validation.error_type == "TOO_SHORT"
        assert validation.actual_length == 35
        assert validation.min_length == 200
    
    def test_validate_output_valid_length(self):
        """Verify validation passes for valid length"""
        valid_output = "x" * 250
        
        validation = self.runner.validate_output(valid_output, "project-setup")
        
        assert validation.is_valid
        assert validation.actual_length >= validation.min_length
    
    def test_validate_output_detects_slop(self):
        """Verify validation detects generic placeholder"""
        slop_output = "Generic French cu. à compléter placeholder"
        
        validation = self.runner.validate_output(slop_output, "project-setup")
        
        assert not validation.is_valid
        assert validation.error_type in ["SLOP", "TOO_SHORT"]


class TestAdversarialRetries:
    """Test AdversarialRetries class"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.retries = AdversarialRetries(max_retries=3)
    
    def test_initialization(self):
        """Verify AdversarialRetries initializes correctly"""
        assert self.retries.max_retries == 3
        assert self.retries.retry_count == 0
        assert self.retries.agent_scores == {}
    
    def test_should_retry_low_score(self):
        """Verify low score allows retry"""
        should_retry = self.retries.should_retry("agent1", score=5)
        
        assert should_retry is True
    
    def test_should_retry_high_score_exhausted(self):
        """Verify high score (>=9) exhausts retries"""
        should_retry = self.retries.should_retry("agent1", score=9)
        
        assert should_retry is False
    
    def test_should_retry_tracks_scores(self):
        """Verify scores are tracked per agent"""
        self.retries.should_retry("agent1", score=5)
        self.retries.should_retry("agent1", score=7)
        
        assert "agent1" in self.retries.agent_scores
        assert len(self.retries.agent_scores["agent1"]) == 2
    
    def test_increment(self):
        """Verify retry count increments"""
        initial = self.retries.retry_count
        self.retries.increment()
        
        assert self.retries.retry_count == initial + 1


class TestWorkflowPhases:
    """Test workflow phase definitions"""
    
    def test_workflow_phases_defined(self):
        """Verify all workflow phases are defined"""
        expected_phases = ["ideation", "project-setup", "development", "testing", "production"]
        
        for phase in expected_phases:
            assert phase in WORKFLOW_PHASES
    
    def test_project_setup_phase(self):
        """Verify project-setup phase has correct properties"""
        phase = WORKFLOW_PHASES["project-setup"]
        
        assert phase["next"] == "development"
        assert phase["validation"] == "strict"
        assert "min_length" in phase
        assert phase["required"] is True
    
    def test_get_workflow_definition(self):
        """Verify get_workflow_definition returns correct data"""
        definition = get_workflow_definition("project-setup")
        
        assert definition is not None
        assert definition["next"] == "development"
    
    def test_get_workflow_definition_unknown(self):
        """Verify unknown workflow returns empty dict"""
        definition = get_workflow_definition("unknown-phase")
        
        assert definition == {}
    
    def test_validate_phase_transition_valid(self):
        """Verify valid phase transitions pass"""
        assert validate_phase_transition("project-setup", "development") is True
        assert validate_phase_transition("ideation", "project-setup") is True
    
    def test_validate_phase_transition_invalid(self):
        """Verify invalid phase transitions fail"""
        assert validate_phase_transition("project-setup", "ideation") is False
        assert validate_phase_transition("development", "project-setup") is False


class TestValidationResult:
    """Test ValidationResult dataclass"""
    
    def test_valid_result(self):
        """Verify valid ValidationResult"""
        result = ValidationResult(
            is_valid=True,
            actual_length=250,
            min_length=200
        )
        
        assert result.is_valid
        assert result.actual_length >= result.min_length
    
    def test_invalid_too_short(self):
        """Verify TOO_SHORT ValidationResult"""
        result = ValidationResult(
            is_valid=False,
            error_type="TOO_SHORT",
            error_message="Output too short: 35 chars (min 200)",
            actual_length=35,
            min_length=200
        )
        
        assert not result.is_valid
        assert result.error_type == "TOO_SHORT"
    
    def test_invalid_slop(self):
        """Verify SLOP ValidationResult"""
        result = ValidationResult(
            is_valid=False,
            error_type="SLOP",
            error_message="Output contains generic placeholder",
            actual_length=300,
            min_length=200
        )
        
        assert not result.is_valid
        assert result.error_type == "SLOP"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
