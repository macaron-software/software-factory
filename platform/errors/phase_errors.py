# Ref: FEAT-TMA-AUTOHEAL — TMA Auto-Heal Phase Error Resolution

"""
Phase-specific error definitions for the TMA Auto-Heal system.

This module defines error types and exception classes used across
the platform for phase-related error handling.
"""

from typing import Optional, Dict, Any
from datetime import datetime


class PhaseError(Exception):
    """Base exception for phase-related errors."""
    
    def __init__(
        self,
        error_type: str,
        message: str,
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.message = message
        self.phase = phase
        self.context = context or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "phase": self.phase,
            "context": self.context,
            "timestamp": self.timestamp
        }


class PhaseValidationError(PhaseError):
    """Raised when phase validation fails."""
    
    def __init__(
        self,
        message: str,
        phase: str,
        context: Optional[Dict[str, Any]] = None,
        validation_rule: Optional[str] = None
    ):
        super().__init__(
            error_type="PHASE_VALIDATION_ERROR",
            message=message,
            phase=phase,
            context=context
        )
        self.validation_rule = validation_rule


class TooShortError(PhaseValidationError):
    """Raised when output is too short for the required phase."""
    
    def __init__(
        self,
        actual_length: int,
        required_minimum: int,
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Output too short: {actual_length} chars (min {required_minimum} for {phase})"
        super().__init__(
            message=message,
            phase=phase,
            context=context or {},
            validation_rule=f"min_length_{phase}"
        )
        self.actual_length = actual_length
        self.required_minimum = required_minimum


class MissingFieldError(PhaseValidationError):
    """Raised when a required field is missing."""
    
    def __init__(
        self,
        field_name: str,
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Missing required field: {field_name}"
        super().__init__(
            message=message,
            phase=phase,
            context=context or {},
            validation_rule=f"required_field_{field_name}"
        )
        self.field_name = field_name


class AdversarialRetryExhaustedError(PhaseError):
    """Raised when adversarial retry mechanism is exhausted."""
    
    def __init__(
        self,
        max_attempts: int,
        current_attempt: int,
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Adversarial retries exhausted: {current_attempt}/{max_attempts}"
        super().__init__(
            error_type="ADVERSARIAL_RETRY_EXHAUSTED",
            message=message,
            phase=phase,
            context=context or {}
        )
        self.max_attempts = max_attempts
        self.current_attempt = current_attempt


class GenericOutputError(PhaseValidationError):
    """Raised when output is detected as too generic."""
    
    def __init__(
        self,
        detected_patterns: list,
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Generic output detected with patterns: {', '.join(detected_patterns)}"
        super().__init__(
            message=message,
            phase=phase,
            context=context or {},
            validation_rule="generic_output_detection"
        )
        self.detected_patterns = detected_patterns


class PhaseTransitionError(PhaseError):
    """Raised when phase transition fails."""
    
    def __init__(
        self,
        from_phase: str,
        to_phase: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Failed to transition from {from_phase} to {to_phase}: {reason}"
        super().__init__(
            error_type="PHASE_TRANSITION_ERROR",
            message=message,
            phase=from_phase,
            context=context or {}
        )
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.reason = reason


# Error code mappings for API responses
ERROR_CODE_MAP = {
    "PHASE_VALIDATION_ERROR": 400,
    "TOO_SHORT": 400,
    "MISSING_FIELD": 400,
    "ADVERSARIAL_RETRY_EXHAUSTED": 429,
    "GENERIC_OUTPUT_ERROR": 422,
    "PHASE_TRANSITION_ERROR": 409
}


def get_http_status_code(error_type: str) -> int:
    """Get HTTP status code for a given error type."""
    return ERROR_CODE_MAP.get(error_type, 500)
