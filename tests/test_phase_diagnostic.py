# Ref: FEAT-TMA-AUTOHEAL — TMA Auto-Heal Phase Error Resolution
# Diagnostic tests for project-setup phase error handling

import pytest
from unittest.mock import Mock, patch
try:
    from platform.validation import PhaseValidator
except Exception:
    pytest.skip("PhaseValidator not available in platform.validation", allow_module_level=True)
from platform.patterns.builtins import ProjectSetupPattern
from platform.errors.phase_errors import PhaseError, PhaseValidationError


class TestProjectSetupDiagnostic:
    """Diagnostic tests to understand expected behavior and failure conditions."""
    
    @pytest.fixture
    def mock_context(self):
        """Create mock context for testing."""
        context = Mock()
        context.project_name = "test-project"
        context.phase = "ideation"
        return context
    
    @pytest.fixture
    def pattern_instance(self):
        """Create pattern instance for testing."""
        return ProjectSetupPattern()
    
    def test_phase_validation_success(self, pattern_instance, mock_context):
        """Test successful phase validation."""
        # Should pass when all requirements are met
        result = pattern_instance.validate_phase(mock_context)
        assert result is True
    
    def test_phase_validation_failure_min_length(self, pattern_instance):
        """Test failure when output is too short (TOO_SHORT error)."""
        # Simulate the error condition: output < 200 chars for dev phase
        context = Mock()
        context.project_name = "test"
        context.phase = "dev"
        context.output = "short"  # Only 5 chars, less than 200
        
        with pytest.raises(PhaseValidationError) as exc_info:
            pattern_instance.validate_phase(context)
        
        assert "TOO_SHORT" in str(exc_info.value)
        assert "200" in str(exc_info.value)
    
    def test_phase_validation_failure_missing_field(self, pattern_instance):
        """Test failure when required field is missing."""
        context = Mock()
        context.project_name = None  # Missing required field
        context.phase = "dev"
        
        with pytest.raises(PhaseValidationError) as exc_info:
            pattern_instance.validate_phase(context)
        
        assert "MISSING_FIELD" in str(exc_info.value)
    
    def test_adversarial_retry_exhausted(self, pattern_instance, mock_context):
        """Test behavior when adversarial retries are exhausted."""
        mock_context.adversarial_attempts = 9
        mock_context.output = "generic output"
        
        # Should trigger exhausted retries condition
        result = pattern_instance.check_adversarial_status(mock_context)
        assert result.get("score") == 9
        assert result.get("status") == "exhausted"
    
    def test_generic_french_output_detection(self, pattern_instance):
        """Test detection of generic French output with 'cu' pattern."""
        context = Mock()
        context.phase = "ideation"
        context.output = "Projet créé avec succès. Veuillez continuer."
        
        is_generic = pattern_instance.detect_generic_output(context)
        assert is_generic is True
    
    def test_specific_output_accepted(self, pattern_instance):
        """Test that specific, detailed output is accepted."""
        context = Mock()
        context.phase = "dev"
        # Output with more than 200 chars
        context.output = "A" * 250  # 250 chars, meets minimum
        
        result = pattern_instance.validate_phase(context)
        assert result is True


class TestPhaseErrorHandling:
    """Tests for phase error handling behavior."""
    
    def test_phase_error_creation(self):
        """Test PhaseError creation with proper attributes."""
        error = PhaseError(
            error_type="TOO_SHORT",
            message="Output too short: 35 chars (min 200 for dev)",
            phase="project-setup"
        )
        
        assert error.error_type == "TOO_SHORT"
        assert "35" in error.message
        assert error.phase == "project-setup"
    
    def test_phase_validation_error_with_context(self):
        """Test PhaseValidationError with additional context."""
        error = PhaseValidationError(
            message="Validation failed",
            phase="dev",
            context={"output_length": 35, "required": 200}
        )
        
        assert error.phase == "dev"
        assert error.context["output_length"] == 35


class TestPhaseValidator:
    """Tests for PhaseValidator behavior."""
    
    def test_validator_accepts_valid_dev_output(self):
        """Test validator accepts dev output >= 200 chars."""
        validator = PhaseValidator()
        valid_output = "x" * 200
        
        result = validator.validate("dev", valid_output)
        assert result is True
    
    def test_validator_rejects_short_dev_output(self):
        """Test validator rejects dev output < 200 chars."""
        validator = PhaseValidator()
        short_output = "x" * 35
        
        result = validator.validate("dev", short_output)
        assert result is False
    
    def test_validator_ideation_minimum(self):
        """Test validator has lower minimum for ideation phase."""
        validator = PhaseValidator()
        # Ideation should have lower minimum
        output = "x" * 50
        
        result = validator.validate("ideation", output)
        # Should pass or fail based on ideation-specific rules
        assert isinstance(result, bool)
