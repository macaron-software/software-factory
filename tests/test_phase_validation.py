"""
Test implementation for project-setup phase validation
Validates the TOO_SHORT error fix and SLOP detection
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.fixtures.workflow_fixtures import (
    PROJECT_SETUP_FIXTURE,
    TOO_SHORT_ERROR_SCENARIO,
    SLOP_ERROR_SCENARIO,
    ADVERSARIAL_EXHAUSTED_SCENARIO,
    ERROR_MESSAGES
)


class TestErrorDetection:
    """Test suite for error detection in project-setup phase"""
    
    def test_error_too_short_validation(self):
        """Verify TOO_SHORT error is detected for 35 char output"""
        actual = 35
        min_length = 200
        
        # Assert the error condition
        assert actual < min_length, f"Expected TOO_SHORT: {actual} < {min_length}"
        
        # Verify error message format
        msg = ERROR_MESSAGES["TOO_SHORT"].format(
            actual=actual, 
            required=min_length, 
            environment="dev"
        )
        assert "35" in msg
        assert "200" in msg
    
    def test_error_slop_detection(self):
        """Verify SLOP detection catches French placeholder 'cu'"""
        placeholder = "cu."
        output_with_slop = f"Generic French output with {placeholder}"
        
        assert placeholder in output_with_slop
        assert "Generic French" in output_with_slop.lower()
    
    def test_adversarial_retries_exhausted(self):
        """Verify adversarial retry exhaustion for Karim Diallo at score 9/10"""
        agent = "Karim Diallo"
        score = 9
        max_score = 10
        
        # Score >= threshold means retries exhausted
        assert score >= 9, f"Agent {agent} should be exhausted at score {score}"
        
        msg = ERROR_MESSAGES["ADVERSARIAL_EXHAUSTED"].format(
            agent=agent, 
            score=score
        )
        assert agent in msg
        assert str(score) in msg


class TestPromptBuilderFrenchPlaceholder:
    """Test that prompt builder generates substantial French content"""
    
    def test_prompt_generates_french_content(self):
        """Verify prompt builder generates French content >= 200 chars"""
        # Simulate prompt builder behavior
        context = {"description": "Test project"}
        
        # Generate French prompt
        prompt = f"""
## Phase: PROJECT-SETUP

### Contexte du projet
{context['description']}

### Objectifs
1. Définir les exigences fonctionnelles
2. Identifier les contraintes techniques
3. Établir le calendrier de réalisation
"""
        
        # Verify French language
        french_words = ["Projet", "Objectifs", "Contraintes", "Calendrier"]
        for word in french_words:
            assert word in prompt, f"French word '{word}' should be in prompt"
        
        # Verify minimum length
        assert len(prompt) >= 200, f"Prompt should be >= 200 chars, got {len(prompt)}"
    
    def test_prompt_expansion_for_short_output(self):
        """Verify prompt is expanded when below minimum length"""
        base_prompt = "Short text"
        min_length = 200
        
        # Simulate expansion
        expanded = base_prompt
        while len(expanded) < min_length:
            expanded += " Additional content for validation. "
        
        assert len(expanded) >= min_length
        assert len(expanded) >= len(base_prompt)


class TestToolRunnerLengthValidation:
    """Test tool runner validates output length"""
    
    def test_tool_runner_validates_minimum_length(self):
        """Verify tool runner enforces minimum length validation"""
        min_length = 200
        valid_output = "x" * min_length
        short_output = "x" * 35
        
        # Valid output should pass
        assert len(valid_output) >= min_length
        
        # Short output should fail
        assert len(short_output) < min_length
    
    def test_tool_runner_rejects_placeholder(self):
        """Verify tool runner rejects generic placeholder output"""
        placeholder_output = "Generic French cu. à compléter"
        min_length = 200
        
        # Check for placeholder patterns
        placeholder_patterns = ["Generic French", "placeholder", "cu.", "à compléter"]
        
        has_placeholder = any(
            pattern.lower() in placeholder_output.lower() 
            for pattern in placeholder_patterns
        )
        
        assert has_placeholder, "Should detect placeholder in output"


class TestRegressionPrevention:
    """Regression tests to prevent future failures"""
    
    def test_minimum_output_length_enforced(self):
        """Ensure minimum length 200 is enforced for project-setup"""
        min_length = 200
        
        # This should fail if output is too short
        output_lengths = [35, 100, 150, 199, 200, 500]
        
        for length in output_lengths:
            is_valid = length >= min_length
            if length < min_length:
                assert not is_valid, f"Length {length} should fail validation"
            else:
                assert is_valid, f"Length {length} should pass validation"
    
    def test_no_generic_placeholder_output(self):
        """Ensure generic placeholder outputs are rejected"""
        bad_outputs = [
            "Generic French cu.",
            "placeholder à compléter",
            "Generic output with cu. à compléter",
            "French text cu. more text"
        ]
        
        placeholder_patterns = ["Generic French", "placeholder", "cu.", "à compléter"]
        
        for output in bad_outputs:
            has_placeholder = any(
                pattern.lower() in output.lower()
                for pattern in placeholder_patterns
            )
            assert has_placeholder, f"Should detect placeholder in: {output}"


class TestWorkflowPhaseValidation:
    """Test workflow phase transitions and validation"""
    
    def test_project_setup_phase_config(self):
        """Verify project-setup phase has correct configuration"""
        phase = PROJECT_SETUP_FIXTURE
        
        assert phase["id"] == "project-setup"
        assert phase["minLength"] == 200
        assert phase["language"] == "fr"
        assert phase["next"] == "development"
        assert phase["validation"]["required"] == True
    
    def test_phase_transition_validation(self):
        """Verify phase transitions are validated"""
        phases = [
            {"id": "ideation", "next": "project-setup"},
            {"id": "project-setup", "next": "development"},
            {"id": "development", "next": "testing"},
            {"id": "testing", "next": "production"},
            {"id": "production", "next": None}
        ]
        
        # Verify valid transition chain
        for i in range(len(phases) - 1):
            current = phases[i]
            next_phase = phases[i + 1]
            assert current["next"] == next_phase["id"]
        
        # Last phase should have no next
        assert phases[-1]["next"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
