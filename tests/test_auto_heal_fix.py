"""Tests for agent output validation - Auto-Heal Fix"""
# Ref: feat-ops

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from validators.agent_validator import validate_agent_output, MIN_CONTENT_LENGTH, SLOP_PATTERNS


class TestAgentOutputValidation:
    """Test suite for agent output validation."""

    def test_valid_output_length(self):
        """Test that valid length output passes validation."""
        output = "This is a substantive response with more than 200 characters. " * 5
        context = {"agent": "karim-diallo"}
        
        result = validate_agent_output(output, context)
        
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_too_short_output(self):
        """Test that output below 200 chars fails validation."""
        output = "Too short"
        context = {"agent": "karim-diallo"}
        
        result = validate_agent_output(output, context)
        
        assert result["valid"] is False
        assert any(issue["type"] == "TOO_SHORT" for issue in result["issues"])

    def test_slop_detected(self):
        """Test that SLOP placeholder is detected."""
        output = "SLOP"
        context = {"agent": "karim-diallo"}
        
        result = validate_agent_output(output, context)
        
        assert result["valid"] is False
        assert any(issue["type"] == "SLOP_DETECTED" for issue in result["issues"])

    def test_placeholder_detected(self):
        """Test that [PLACEHOLDER] is detected."""
        output = "[PLACEHOLDER] This needs content"
        context = {"agent": "karim-diallo"}
        
        result = validate_agent_output(output, context)
        
        assert result["valid"] is False

    def test_french_placeholder_detected(self):
        """Test that French placeholders are detected."""
        output = "à compléter"
        context = {"agent": "karim-diallo"}
        
        result = validate_agent_output(output, context)
        
        assert result["valid"] is False
        assert any(issue["type"] == "SLOP_DETECTED" for issue in result["issues"])

    def test_min_content_length_constant(self):
        """Test that MIN_CONTENT_LENGTH is set to 200."""
        assert MIN_CONTENT_LENGTH == 200

    def test_slop_patterns_defined(self):
        """Test that SLOP patterns are properly defined."""
        assert len(SLOP_PATTERNS) > 0
        assert any("SLOP" in p for p in SLOP_PATTERNS)


class TestRetryHandler:
    """Test suite for adversarial retry handler."""

    def test_should_retry_high_score(self):
        """Test retry decision for high adversarial score."""
        from agents.retry_handler import should_retry, RetryConfig
        
        config = RetryConfig()
        
        # Score 9/10 should trigger retry
        assert should_retry(9.0, 0, config) is True
        assert should_retry(9.0, 1, config) is True
        assert should_retry(9.0, 2, config) is True
        assert should_retry(9.0, 3, config) is False  # max_retries exceeded

    def test_should_retry_medium_score(self):
        """Test retry decision for medium adversarial score."""
        from agents.retry_handler import should_retry, RetryConfig
        
        config = RetryConfig()
        
        # Score 7.0 should trigger retry
        assert should_retry(7.0, 0, config) is True

    def test_should_not_retry_low_score(self):
        """Test that low scores don't trigger retry."""
        from agents.retry_handler import should_retry, RetryConfig
        
        config = RetryConfig()
        
        # Score 5.0 should not trigger retry
        assert should_retry(5.0, 0, config) is False

    def test_get_retry_prompt(self):
        """Test enhanced prompt generation for retries."""
        from agents.retry_handler import get_retry_prompt
        
        original = "Generate content about X"
        
        # First retry should add substantive content requirement
        retry1 = get_retry_prompt(original, 0)
        assert "substantive content" in retry1.lower() or "détailed" in retry1.lower()
        
        # Second retry should add more specific guidance
        retry2 = get_retry_prompt(original, 1)
        assert "exemples" in retry2.lower() or "examples" in retry2.lower()


class TestAgentHealthMonitor:
    """Test suite for agent health monitoring."""

    def test_healthy_agent(self):
        """Test health check for healthy agent."""
        from api.health import AgentHealthMonitor
        
        monitor = AgentHealthMonitor()
        outputs = [
            {"content": "A" * 300, "adversarial_score": 3.0},
            {"content": "B" * 300, "adversarial_score": 4.0},
        ]
        
        health = monitor.check_agent_health("karim-diallo", outputs)
        
        assert health["healthy"] is True
        assert len(health["issues"]) == 0

    def test_unhealthy_agent_too_short(self):
):
        """Test health check detects TOO_SHORT issue."""
        from api.health import AgentHealthMonitor
        
        monitor = AgentHealthMonitor()
        outputs = [
            {"content": "short", "adversarial_score": 3.0},
        ]
        
        health = monitor.check_agent_health("karim-diallo", outputs)
        
        assert health["healthy"] is False
        assert any(issue["type"] == "TOO_SHORT" for issue in health["issues"])

    def test_unhealthy_agent_slop(self):
        """Test health check detects SLOP issue."""
        from api.health import AgentHealthMonitor
        
        monitor = AgentHealthMonitor()
        outputs = [
            {"content": "SLOP", "adversarial_score": 9.0},
        ]
        
        health = monitor.check_agent_health("karim-diallo", outputs)
        
        assert health["healthy"] is False
        assert any(issue["type"] == "SLOP_DETECTED" for issue in health["issues"])

    def test_should_alert(self):
        """Test alert threshold calculation."""
        from api.health import AgentHealthMonitor
        
        monitor = AgentHealthMonitor()
        
        # Healthy should not alert
        health = {"healthy": True, "failure_count": 0}
        assert monitor.should_alert(health) is False
        
        # 3 consecutive failures should alert
        health = {"healthy": False, "failure_count": 3}
        assert monitor.should_alert(health) is True
        
        # 2 failures should not alert
        health = {"healthy": False, "failure_count": 2}
        assert monitor.should_alert(health) is False


class TestKarimDialloConfig:
    """Test suite for Karim Diallo agent configuration."""

    def test_agent_config_structure(self):
        """Test that agent config has required fields."""
        from agents.karim_diallo_config import AGENT_CONFIG, VALIDATION_RULES
        
        assert AGENT_CONFIG["name"] == "Karim Diallo"
        assert AGENT_CONFIG["min_output_length"] == 200
        assert AGENT_CONFIG["adversarial_threshold"] == 7.0
        assert AGENT_CONFIG["retry_on_slop"] is True

    def test_validation_rules(self):
        """Test validation rules configuration."""
        from agents.karim_diallo_config import VALIDATION_RULES
        
        assert VALIDATION_RULES["min_characters"] == 200
        assert VALIDATION_RULES["max_characters"] == 10000
        assert len(VALIDATION_RULES["blocked_patterns"]) > 0
        assert "SLOP" in str(VALIDATION_RULES["blocked_patterns"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
