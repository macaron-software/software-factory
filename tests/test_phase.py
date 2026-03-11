"""
Tests for Phase core module.

Validates Phase generation, validation logic, and grace period handling
for the TMA Auto-Heal sprint fix.
"""

import pytest
from datetime import datetime
from src.core.phase import (
    Phase,
    PhaseGenerator,
    PhaseValidator,
    PhaseValidationResult,
    PhaseGenerationError,
    MIN_PHASE_CONTENT_LENGTH,
    MAX_PHASE_CONTENT_LENGTH,
    ADVERSARIAL_RETRY_THRESHOLD,
)


class TestPhaseValidation:
    """Test Phase content validation."""
    
    def test_valid_phase_content(self):
        """Valid Phase content should pass validation."""
        content = "Cette phase constitue la première étape du projet de développement. " * 5
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is True
        assert result.error_code is None
    
    def test_phase_too_short(self):
        """Phase content too short should fail validation."""
        content = "Trop court"  # 11 chars
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is False
        assert result.error_code == "TOO_SHORT"
        assert result.content_length < MIN_PHASE_CONTENT_LENGTH
    
    def test_phase_contains_placeholder(self):
        """Phase with placeholder should fail with SLOP error."""
        content = "Cette phase contient [à compléter] pour le projet."
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is False
        assert result.error_code == "SLOP"
        assert result.has_placeholder is True
    
    def test_phase_contains_french_placeholder(self):
        """Phase with French placeholder text should fail."""
        content = "Phase en cours - détails à venir"
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is False
        assert result.error_code == "SLOP"
    
    def test_phase_too_long(self):
        """Phase content exceeding max length should fail."""
        content = "a" * (MAX_PHASE_CONTENT_LENGTH + 1)
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is False
        assert result.error_code == "TOO_LONG"


class TestPhaseValidatorGracePeriod:
    """Test grace period logic for adversarial retry exhaustion."""
    
    def test_grace_period_applied_for_high_retry(self):
        """High retry score with acceptable content should pass with grace period."""
        # Content close to minimum (80% threshold)
        min_acceptable = MIN_PHASE_CONTENT_LENGTH * 0.8
        content = "x" * int(min_acceptable)
        
        phase = Phase(
            name="Phase 1",
            content=content,
            metadata={"retry_score": ADVERSARIAL_RETRY_THRESHOLD + 2}
        )
        
        validator = PhaseValidator(enable_grace_period=True)
        result = validator.validate(phase)
        
        assert result.is_valid is True
        assert result.retry_score > ADVERSARIAL_RETRY_THRESHOLD
    
    def test_grace_period_not_applied_for_low_retry(self):
        """Low retry score should not trigger grace period."""
        content = "x" * 100  # Too short but low retry
        phase = Phase(
            name="Phase 1",
            content=content,
            metadata={"retry_score": 2}
        )
        
        validator = PhaseValidator(enable_grace_period=True)
        result = validator.validate(phase)
        
        assert result.is_valid is False
    
    def test_grace_period_disabled(self):
        """Grace period can be disabled."""
        min_acceptable = MIN_PHASE_CONTENT_LENGTH * 0.8
        content = "x" * int(min_acceptable)
        
        phase = Phase(
            name="Phase 1",
            content=content,
            metadata={"retry_score": ADVERSARIAL_RETRY_THRESHOLD + 5}
        )
        
        validator = PhaseValidator(enable_grace_period=False)
        result = validator.validate(phase)
        
        assert result.is_valid is False


class TestPhaseGenerator:
    """Test Phase generation with retry logic."""
    
    def test_generate_raises_on_exhaustion(self):
        """Generator should raise exception after max retries."""
        # Mock LLM that always returns invalid content
        class MockLLM:
            def complete(self, prompt):
                return "Court"  # Always too short
        
        generator = PhaseGenerator(llm_client=MockLLM(), max_retries=2)
        
        with pytest.raises(PhaseGenerationError):
            generator.generate({"phase_name": "Test", "project_name": "Test"})
    
    def test_generate_succeeds_with_valid_content(self):
        """Generator should succeed with valid LLM response."""
        valid_content = "Description détaillée de la phase. " * 20
        
        class MockLLM:
            call_count = 0
            def complete(self, prompt):
                MockLLM.call_count += 1
                return valid_content
        
        generator = PhaseGenerator(llm_client=MockLLM(), max_retries=3)
        phase = generator.generate({"phase_name": "Test", "project_name": "Test"})
        
        assert phase.validate().is_valid is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_content(self):
        """Empty content should fail validation."""
        phase = Phase(name="Phase 1", content="")
        result = phase.validate()
        
        assert result.is_valid is False
        assert result.error_code == "TOO_SHORT"
    
    def test_whitespace_only(self):
        """Whitespace-only content should fail."""
        phase = Phase(name="Phase 1", content="   \n\t   ")
        result = phase.validate()
        
        assert result.is_valid is False
    
    def test_minimum_boundary_length(self):
        """Content at minimum length should pass."""
        content = "a" * MIN_PHASE_CONTENT_LENGTH
        phase = Phase(name="Phase 1", content=content)
        result = phase.validate()
        
        assert result.is_valid is True
    
    def test_retry_score_tracking(self):
        """Retry score should be tracked in metadata."""
        phase = Phase(
            name="Phase 1",
            content="x" * 300,
            metadata={"retry_score": 5}
        )
        result = phase.validate()
        
        assert result.retry_score == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
